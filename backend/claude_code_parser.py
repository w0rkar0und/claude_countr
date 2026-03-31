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
        # Try nested message structure
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
    # Use the parent directory name + filename as session identifier
    return f"{file_path.parent.name}/{file_path.stem}"


def _extract_model(entry: dict) -> str:
    """Extract model name from a JSONL entry."""
    model = entry.get("model", "")
    if not model:
        message = entry.get("message", {})
        model = message.get("model", "unknown")
    return model


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
    Parse all Claude Code session files and return session summaries.

    Returns list of dicts:
        session_id, started_at, ended_at, total_input_tokens, total_output_tokens,
        total_cache_creation, total_cache_read, status, estimated_cost, model
    """
    files = _find_jsonl_files(base_path)

    for file_path in files:
        session_id = _extract_session_id(file_path)
        entries = parse_file_incremental(file_path)

        if session_id not in _sessions:
            # Initialize session
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
    Get detailed state for a specific session.

    Returns:
        Dict with time_to_reset, tokens used, burn rate, etc.
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
