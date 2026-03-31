import asyncio
import json
from datetime import datetime, timezone
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import POLLING_INTERVAL, COST_ALERT_THRESHOLDS
from api_client import poll_latest_usage
from claude_code_parser import parse_claude_code_sessions, get_session_state
import database as db


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections and broadcasts updates."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        print(f"[ws] Client connected ({len(self._connections)} total)")

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        print(f"[ws] Client disconnected ({len(self._connections)} total)")

    async def broadcast(self, data: dict):
        """Send data to all connected clients. Removes dead connections."""
        if not self._connections:
            return
        payload = json.dumps(data, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Scheduled Tasks
# ---------------------------------------------------------------------------

async def poll_admin_api_task():
    """Fetch latest usage from Admin API and store in database."""
    try:
        records = await poll_latest_usage(since_minutes=max(POLLING_INTERVAL // 60 + 2, 5))
        if records:
            count = db.record_api_usage_batch(records)
            print(f"[scheduler] Admin API: stored {count} records")
    except Exception as e:
        print(f"[scheduler] Admin API poll error: {e}")


async def process_claude_code_task():
    """Re-parse Claude Code session files, update database, check alerts."""
    try:
        sessions = parse_claude_code_sessions()
        for s in sessions:
            db.record_claude_code_session(s)
        _check_alerts(sessions)
        print(f"[scheduler] Claude Code: processed {len(sessions)} sessions")
    except Exception as e:
        print(f"[scheduler] Claude Code processing error: {e}")


async def broadcast_update_task():
    """Build current state snapshot and push to all WebSocket clients."""
    if manager.active_count == 0:
        return

    try:
        sessions = parse_claude_code_sessions()
        active = [s for s in sessions if s.get("status") == "active"]

        session_details = []
        warnings = []
        for s in active:
            state = get_session_state(s["session_id"])
            if state:
                session_details.append(state)
                _collect_warnings(state, warnings)

        total_burn = sum(s.get("burn_rate", 0) for s in session_details)

        payload = {
            "event": "update",
            "data": {
                "sessions": session_details,
                "totalActiveSessions": len(active),
                "aggregateBurnRate": round(total_burn, 1),
                "lastUpdate": datetime.now(timezone.utc).isoformat(),
                "warnings": warnings,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await manager.broadcast(payload)
    except Exception as e:
        print(f"[scheduler] Broadcast error: {e}")


# ---------------------------------------------------------------------------
# Alert Helpers
# ---------------------------------------------------------------------------

def _collect_warnings(state: dict, warnings: list):
    """Append any threshold warnings for a session state."""
    pct = state.get("percent_to_limit", 0)
    sid = state.get("session_id", "")
    for threshold in sorted(COST_ALERT_THRESHOLDS):
        threshold_pct = threshold * 100
        if pct >= threshold_pct:
            severity = "critical" if threshold >= 0.95 else ("warning" if threshold >= 0.90 else "info")
            warnings.append({
                "sessionId": sid,
                "type": "approaching_limit",
                "message": f"Session at {pct}% of 5-hour window",
                "severity": severity,
            })
            break  # Only report highest matched threshold


def _check_alerts(sessions: list):
    """Record alerts in the database when thresholds are crossed."""
    for s in sessions:
        if s.get("status") != "active":
            continue
        state = get_session_state(s["session_id"])
        if not state:
            continue
        pct = state.get("percent_to_limit", 0)
        for threshold in COST_ALERT_THRESHOLDS:
            threshold_pct = threshold * 100
            if pct >= threshold_pct:
                db.record_alert(
                    session_id=s["session_id"],
                    alert_type="approaching_limit",
                    message=f"Session at {pct}% of 5-hour window (threshold: {threshold_pct}%)",
                    threshold=threshold,
                )
                break  # One alert per session per poll cycle


# ---------------------------------------------------------------------------
# File Watcher Callback
# ---------------------------------------------------------------------------

_broadcast_loop: asyncio.AbstractEventLoop | None = None


def on_file_change(file_path: str):
    """Called by watchdog when a JSONL file changes. Triggers async broadcast."""
    if _broadcast_loop is None:
        return
    try:
        _broadcast_loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(broadcast_update_task())
        )
    except RuntimeError:
        pass  # Loop closed during shutdown


# ---------------------------------------------------------------------------
# Scheduler Lifecycle
# ---------------------------------------------------------------------------

_scheduler: AsyncIOScheduler | None = None


def start_scheduler():
    """Initialize and start APScheduler with all background jobs."""
    global _scheduler, _broadcast_loop

    _broadcast_loop = asyncio.get_event_loop()
    _scheduler = AsyncIOScheduler()

    # Poll Admin API every POLLING_INTERVAL seconds
    _scheduler.add_job(
        poll_admin_api_task,
        trigger=IntervalTrigger(seconds=POLLING_INTERVAL),
        id="poll_admin_api",
        name="Poll Admin API",
        replace_existing=True,
    )

    # Process Claude Code sessions every POLLING_INTERVAL seconds
    _scheduler.add_job(
        process_claude_code_task,
        trigger=IntervalTrigger(seconds=POLLING_INTERVAL),
        id="process_claude_code",
        name="Process Claude Code Sessions",
        replace_existing=True,
    )

    # Broadcast WebSocket updates every POLLING_INTERVAL seconds
    _scheduler.add_job(
        broadcast_update_task,
        trigger=IntervalTrigger(seconds=POLLING_INTERVAL),
        id="broadcast_update",
        name="Broadcast WebSocket Update",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"[scheduler] Started with {POLLING_INTERVAL}s polling interval")


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    global _scheduler, _broadcast_loop
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[scheduler] Stopped")
    _broadcast_loop = None
