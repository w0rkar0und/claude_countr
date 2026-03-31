import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from config import CLAUDE_CODE_HOME, SESSION_RESET_HOURS, calculate_cost

# Track file read positions for incremental parsing
_file_positions: Dict[str, int] = {}

# Track known sessions
_sessions: Dict[str, dict] = {}


def _find_jsonl_files(base_path: Optional[str] = None) -> List[Path]:
    """Find all JSONL files under the Claude Code projects directory."""
    root = Path(base_path or CLAUDE_CODE_HOME)
    if not root.exists():
        return []
    return sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def _parse_jsonl_entry(line: str) -> Optional[dict]:
    """Parse a single JSONL line, returning None if invalid."""
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _extract_token_counts(entry: dict) -> dict:
    """Extract token counts from a JSONL entry."""
    usage = entry.get("usage", {})
    if not usage:
        message = entry.get("message", {})
        usage = message.get("usage", {})

    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
    }


def _extract_session_id(file_path: Path) -> str:
    """Derive a session ID from the file path."""
    return f"{file_path.parent.name}/{file_path.stem}"


def _extract_model(entry: dict) -> str:
    """Extract model name from a JSONL entry."""
    model = entry.get("model", "")
    if not model:
        message = entry.get("message", {})
        model = message.get("model", "unknown")
    return model


def _extract_project_name(entry: dict, file_path: Path) -> str:
    """Extract project name from cwd or file path."""
    cwd = entry.get("cwd", "")
    if cwd:
        # Use last directory component as project name
        return Path(cwd).name
    # Fall back to parent dir from JSONL path
    # Path structure: ~/.claude/projects/-Users-foo-Documents-project/session.jsonl
    parent = file_path.parent.name
    # The encoded path uses hyphens; extract last meaningful segment
    parts = parent.split("-")
    if len(parts) > 1:
        return parts[-1]
    return parent


def _extract_tool_uses(entry: dict) -> List[str]:
    """Extract tool names from assistant message content blocks."""
    tools = []
    message = entry.get("message", {})
    content = message.get("content", [])
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = block.get("name", "")
                if name:
                    tools.append(name)
    return tools


def _extract_metadata(entry: dict) -> dict:
    """Extract additional metadata fields from a JSONL entry."""
    message = entry.get("message", {})
    usage = message.get("usage", {}) or entry.get("usage", {})

    return {
        "version": entry.get("version", ""),
        "git_branch": entry.get("gitBranch", ""),
        "is_subagent": bool(entry.get("isSidechain", False)),
        "agent_id": entry.get("agentId", ""),
        "entry_type": entry.get("type", ""),
        "inference_geo": usage.get("inference_geo", ""),
        "service_tier": usage.get("service_tier", ""),
        "speed": usage.get("speed", ""),
        "cwd": entry.get("cwd", ""),
    }


def _is_session_active(started_at: str) -> bool:
    """Check if a session is still within the 5-hour window."""
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - start) < timedelta(hours=SESSION_RESET_HOURS)
    except (ValueError, TypeError):
        return False


def parse_file_incremental(file_path: Path) -> List[dict]:
    """Parse only new entries from a JSONL file since last read."""
    path_str = str(file_path)
    last_pos = _file_positions.get(path_str, 0)

    entries = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(last_pos)
            for line in f:
                entry = _parse_jsonl_entry(line)
                if entry:
                    entries.append(entry)
            _file_positions[path_str] = f.tell()
    except (OSError, IOError) as e:
        print(f"[parser] Error reading {file_path}: {e}")

    return entries


def parse_claude_code_sessions(base_path: Optional[str] = None) -> List[dict]:
    """
    Parse all Claude Code session files and return enriched session summaries.

    Returns list of dicts with:
        session_id, started_at, ended_at, total_input_tokens, total_output_tokens,
        total_cache_creation, total_cache_read, status, estimated_cost, model,
        project, git_branch, version, is_subagent, tool_usage, inference_geo,
        service_tier, speed, message_count
    """
    files = _find_jsonl_files(base_path)

    for file_path in files:
        session_id = _extract_session_id(file_path)
        entries = parse_file_incremental(file_path)

        if session_id not in _sessions:
            _sessions[session_id] = {
                "session_id": session_id,
                "started_at": None,
                "ended_at": None,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_creation": 0,
                "total_cache_read": 0,
                "status": "active",
                "estimated_cost": 0.0,
                "model": "unknown",
                "file_path": str(file_path),
                # New enriched fields
                "project": "",
                "git_branch": "",
                "version": "",
                "is_subagent": False,
                "tool_usage": {},  # { "Read": 5, "Write": 3, ... }
                "inference_geo": "",
                "service_tier": "",
                "speed": "",
                "message_count": 0,
                "user_messages": 0,
                "assistant_messages": 0,
            }

        session = _sessions[session_id]

        for entry in entries:
            # Update timestamps
            ts = entry.get("timestamp") or entry.get("created_at")
            if ts:
                if not session["started_at"] or ts < session["started_at"]:
                    session["started_at"] = ts
                if not session["ended_at"] or ts > session["ended_at"]:
                    session["ended_at"] = ts

            # Accumulate tokens
            tokens = _extract_token_counts(entry)
            session["total_input_tokens"] += tokens["input_tokens"]
            session["total_output_tokens"] += tokens["output_tokens"]
            session["total_cache_creation"] += tokens["cache_creation"]
            session["total_cache_read"] += tokens["cache_read"]

            # Update model
            model = _extract_model(entry)
            if model and model != "unknown":
                session["model"] = model

            # Extract project name
            project = _extract_project_name(entry, file_path)
            if project and not session["project"]:
                session["project"] = project

            # Extract tool usage from assistant messages
            tools = _extract_tool_uses(entry)
            for tool in tools:
                session["tool_usage"][tool] = session["tool_usage"].get(tool, 0) + 1

            # Extract metadata
            meta = _extract_metadata(entry)
            if meta["version"] and not session["version"]:
                session["version"] = meta["version"]
            if meta["git_branch"]:
                session["git_branch"] = meta["git_branch"]
            if meta["is_subagent"]:
                session["is_subagent"] = True
            if meta["inference_geo"] and not session["inference_geo"]:
                session["inference_geo"] = meta["inference_geo"]
            if meta["service_tier"] and not session["service_tier"]:
                session["service_tier"] = meta["service_tier"]
            if meta["speed"] and not session["speed"]:
                session["speed"] = meta["speed"]

            # Count messages by type
            entry_type = meta["entry_type"]
            if entry_type == "user":
                session["user_messages"] += 1
            elif entry_type == "assistant":
                session["assistant_messages"] += 1
            session["message_count"] += 1

        # Recalculate cost
        session["estimated_cost"] = calculate_cost(
            model=session["model"],
            input_tokens=session["total_input_tokens"],
            output_tokens=session["total_output_tokens"],
            cache_creation_tokens=session["total_cache_creation"],
            cache_read_tokens=session["total_cache_read"],
        )

        # Update status
        if session["started_at"]:
            session["status"] = "active" if _is_session_active(session["started_at"]) else "completed"

    return list(_sessions.values())


def get_session_state(session_id: str) -> Optional[dict]:
    """
    Get detailed state for a specific session including enriched fields.
    """
    session = _sessions.get(session_id)
    if not session:
        return None

    result = {**session}

    if session["started_at"]:
        try:
            start = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            elapsed = now - start
            window = timedelta(hours=SESSION_RESET_HOURS)
            remaining = window - elapsed

            if remaining.total_seconds() > 0:
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                result["time_remaining"] = f"{hours}h {minutes}m"
                result["percent_to_limit"] = min(
                    100, round((elapsed / window) * 100, 1)
                )
            else:
                result["time_remaining"] = "0h 0m"
                result["percent_to_limit"] = 100.0

            # Burn rate: tokens per minute
            elapsed_minutes = max(elapsed.total_seconds() / 60, 1)
            total_tokens = (
                session["total_input_tokens"]
                + session["total_output_tokens"]
                + session["total_cache_creation"]
                + session["total_cache_read"]
            )
            result["burn_rate"] = round(total_tokens / elapsed_minutes, 1)
        except (ValueError, TypeError):
            result["time_remaining"] = "unknown"
            result["percent_to_limit"] = 0.0
            result["burn_rate"] = 0.0

    return result


def get_aggregate_tool_usage() -> dict:
    """Aggregate tool usage across all sessions. Returns {tool_name: count}."""
    totals: Dict[str, int] = {}
    for session in _sessions.values():
        for tool, count in session.get("tool_usage", {}).items():
            totals[tool] = totals.get(tool, 0) + count
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


def get_project_summary() -> List[dict]:
    """Aggregate sessions by project. Returns list of project summaries."""
    projects: Dict[str, dict] = {}

    for session in _sessions.values():
        proj = session.get("project") or "unknown"
        if proj not in projects:
            projects[proj] = {
                "project": proj,
                "session_count": 0,
                "active_sessions": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "models_used": set(),
                "tools_used": {},
                "git_branches": set(),
            }

        p = projects[proj]
        p["session_count"] += 1
        if session.get("status") == "active":
            p["active_sessions"] += 1
        p["total_tokens"] += (
            session["total_input_tokens"]
            + session["total_output_tokens"]
            + session["total_cache_creation"]
            + session["total_cache_read"]
        )
        p["total_cost"] += session["estimated_cost"]
        if session.get("model") and session["model"] != "unknown":
            p["models_used"].add(session["model"])
        if session.get("git_branch"):
            p["git_branches"].add(session["git_branch"])
        for tool, count in session.get("tool_usage", {}).items():
            p["tools_used"][tool] = p["tools_used"].get(tool, 0) + count

    # Convert sets to lists for JSON serialization
    result = []
    for p in sorted(projects.values(), key=lambda x: x["total_cost"], reverse=True):
        p["models_used"] = list(p["models_used"])
        p["git_branches"] = list(p["git_branches"])
        p["total_cost"] = round(p["total_cost"], 4)
        result.append(p)

    return result


class _ProjectsHandler(FileSystemEventHandler):
    """Watch for JSONL file changes in the Claude Code projects directory."""

    def __init__(self, callback: Callable):
        self.callback = callback

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent) and event.src_path.endswith(".jsonl"):
            self.callback(event.src_path)

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and event.src_path.endswith(".jsonl"):
            self.callback(event.src_path)


_observer: Optional[Observer] = None


def watch_projects_directory(callback: Callable) -> None:
    """Start watching the Claude Code projects directory for changes."""
    global _observer

    watch_path = CLAUDE_CODE_HOME
    if not os.path.exists(watch_path):
        print(f"[parser] Watch path does not exist: {watch_path}")
        return

    handler = _ProjectsHandler(callback)
    _observer = Observer()
    _observer.schedule(handler, watch_path, recursive=True)
    _observer.daemon = True
    _observer.start()
    print(f"[parser] Watching {watch_path} for JSONL changes")


def stop_watching() -> None:
    """Stop the file watcher."""
    global _observer
    if _observer:
        _observer.stop()
        _observer.join(timeout=5)
        _observer = None
