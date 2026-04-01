from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import FRONTEND_URL, BACKEND_PORT
from database import (
    init_db,
    get_active_sessions,
    get_all_sessions,
    get_daily_summary,
    get_weekly_summary,
    get_monthly_summary,
    get_recent_alerts,
    get_last_api_usage_timestamp,
    get_analytics_summary,
)
from api_client import poll_latest_usage, poll_claude_code_analytics
from claude_code_parser import (
    parse_claude_code_sessions,
    get_session_state,
    get_aggregate_tool_usage,
    get_project_summary,
    watch_projects_directory,
    stop_watching,
)
from scheduler import (
    manager,
    start_scheduler,
    stop_scheduler,
    on_file_change,
    broadcast_update_task,
)
import database as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("[main] Database initialized")

    # Parse existing Claude Code sessions on startup
    sessions = parse_claude_code_sessions()
    for s in sessions:
        db.record_claude_code_session(s)
    print(f"[main] Initial parse: {len(sessions)} Claude Code sessions")

    # Backfill Admin API data (last 30 days) on fresh start
    try:
        records = await poll_latest_usage(since_minutes=60 * 24 * 30)
        if records:
            count = db.record_api_usage_batch(records)
            print(f"[main] Admin API backfill: {count} records")
        else:
            print("[main] Admin API backfill: no records returned")
    except Exception as e:
        print(f"[main] Admin API backfill error: {e}")

    # Start background scheduler
    start_scheduler()

    # Start file watcher for live Claude Code session updates
    watch_projects_directory(on_file_change)

    yield

    # Shutdown
    stop_watching()
    stop_scheduler()
    print("[main] Shut down cleanly")


app = FastAPI(
    title="claude_countr",
    description="Token Usage Dashboard API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "https://claude.hydrae.mx", "https://claude-countr.vercel.app", "http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await broadcast_update_task()
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text('{"event":"pong"}')
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    try:
        active = get_active_sessions()
        last_ts = get_last_api_usage_timestamp()
        return {
            "active_sessions": len(active),
            "last_update": last_ts,
            "websocket_clients": manager.active_count,
            "data_sources": {
                "admin_api": bool(last_ts),
                "claude_code": True,
            },
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/current")
async def get_current():
    try:
        sessions = parse_claude_code_sessions()
        active = [s for s in sessions if s.get("status") == "active"]

        session_details = []
        warnings = []

        for s in active:
            state = get_session_state(s["session_id"])
            if state:
                session_details.append(state)

                pct = state.get("percent_to_limit", 0)
                if pct >= 95:
                    warnings.append({
                        "sessionId": s["session_id"],
                        "type": "approaching_limit",
                        "message": f"Session at {pct}% of 5-hour window",
                        "severity": "critical",
                    })
                elif pct >= 90:
                    warnings.append({
                        "sessionId": s["session_id"],
                        "type": "approaching_limit",
                        "message": f"Session at {pct}% of 5-hour window",
                        "severity": "warning",
                    })
                elif pct >= 80:
                    warnings.append({
                        "sessionId": s["session_id"],
                        "type": "approaching_limit",
                        "message": f"Session at {pct}% of 5-hour window",
                        "severity": "info",
                    })

        total_burn = sum(s.get("burn_rate", 0) for s in session_details)

        return {
            "sessions": session_details,
            "totalActiveSessions": len(active),
            "aggregateBurnRate": round(total_burn, 1),
            "lastUpdate": datetime.now(timezone.utc).isoformat(),
            "warnings": warnings,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/daily")
async def get_daily(date_str: str = ""):
    try:
        if not date_str:
            date_str = date.today().isoformat()
        return get_daily_summary(date_str)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/weekly")
async def get_weekly(start_date: str = "", end_date: str = ""):
    try:
        if not end_date:
            end_date = date.today().isoformat()
        if not start_date:
            start_date = (date.today() - timedelta(days=6)).isoformat()
        return get_weekly_summary(start_date, end_date)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/monthly")
async def get_monthly(month: str = ""):
    try:
        if not month:
            month = date.today().strftime("%Y-%m")
        return get_monthly_summary(month)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/sessions")
async def list_sessions():
    try:
        sessions = parse_claude_code_sessions()
        result = []
        for s in sessions:
            state = get_session_state(s["session_id"])
            if state:
                result.append({
                    "sessionId": state["session_id"],
                    "status": state["status"],
                    "startedAt": state.get("started_at"),
                    "tokensUsed": (
                        state["total_input_tokens"]
                        + state["total_output_tokens"]
                        + state["total_cache_creation"]
                        + state["total_cache_read"]
                    ),
                    "estimatedCost": state["estimated_cost"],
                    "timeRemaining": state.get("time_remaining", "N/A"),
                    "model": state.get("model", "unknown"),
                    "project": state.get("project", ""),
                    "gitBranch": state.get("git_branch", ""),
                    "isSubagent": state.get("is_subagent", False),
                    "toolUsage": state.get("tool_usage", {}),
                    "messageCount": state.get("message_count", 0),
                })
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/tools")
async def get_tools():
    """Aggregate tool usage across all sessions."""
    try:
        return get_aggregate_tool_usage()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/projects")
async def get_projects():
    """Get project-level aggregated summaries."""
    try:
        return get_project_summary()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/analytics")
async def get_analytics(days: int = 7):
    """Get Claude Code analytics summary."""
    try:
        return get_analytics_summary(days)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/refresh")
async def refresh_data():
    try:
        # Poll Admin API (last 24 hours on manual refresh)
        records = await poll_latest_usage(since_minutes=60 * 24)
        if records:
            db.record_api_usage_batch(records)

        # Poll Claude Code Analytics
        analytics = await poll_claude_code_analytics(since_days=7)
        analytics_count = 0
        if analytics:
            analytics_count = db.record_analytics_batch(analytics)

        # Re-parse Claude Code sessions
        sessions = parse_claude_code_sessions()
        for s in sessions:
            db.record_claude_code_session(s)

        # Push fresh data to WebSocket clients
        await broadcast_update_task()

        return {
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "api_records_fetched": len(records),
            "analytics_records_fetched": analytics_count,
            "sessions_parsed": len(sessions),
            "data_freshness": "live",
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/date-range")
async def get_date_range():
    """Return the min/max dates that have data in api_usage."""
    conn = db._get_conn()
    try:
        row = conn.execute(
            "SELECT MIN(date(timestamp)) as min_date, MAX(date(timestamp)) as max_date FROM api_usage"
        ).fetchone()
        return {
            "minDate": row["min_date"],
            "maxDate": row["max_date"],
        }
    finally:
        conn.close()


@app.get("/api/debug/db")
async def debug_db():
    """Temporary debug endpoint to inspect stored data."""
    conn = db._get_conn()
    try:
        api_count = conn.execute("SELECT COUNT(*) as c FROM api_usage").fetchone()["c"]
        sample = conn.execute("SELECT timestamp, model, input_tokens, output_tokens, cost FROM api_usage LIMIT 5").fetchall()
        return {
            "api_usage_count": api_count,
            "sample_rows": [dict(r) for r in sample],
        }
    finally:
        conn.close()


@app.get("/api/alerts")
async def get_alerts():
    try:
        return get_recent_alerts()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT)
