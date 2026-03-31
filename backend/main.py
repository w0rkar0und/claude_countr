from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
)
from api_client import poll_latest_usage
from claude_code_parser import parse_claude_code_sessions, get_session_state
import database as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("[main] Database initialized")
    # Parse existing Claude Code sessions on startup
    parse_claude_code_sessions()
    print("[main] Initial Claude Code session parse complete")
    yield
    # Shutdown
    print("[main] Shutting down")


app = FastAPI(
    title="claude_countr",
    description="Token Usage Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def get_status():
    active = get_active_sessions()
    last_ts = get_last_api_usage_timestamp()
    return {
        "active_sessions": len(active),
        "last_update": last_ts,
        "data_sources": {
            "admin_api": bool(last_ts),
            "claude_code": True,
        },
    }


@app.get("/api/current")
async def get_current():
    sessions = parse_claude_code_sessions()
    active = [s for s in sessions if s.get("status") == "active"]

    session_details = []
    warnings = []

    for s in active:
        state = get_session_state(s["session_id"])
        if state:
            session_details.append(state)

            # Check alert thresholds
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
        "lastUpdate": datetime.utcnow().isoformat(),
        "warnings": warnings,
    }


@app.get("/api/daily")
async def get_daily(date_str: str = ""):
    if not date_str:
        date_str = date.today().isoformat()
    return get_daily_summary(date_str)


@app.get("/api/weekly")
async def get_weekly(start_date: str = "", end_date: str = ""):
    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=6)).isoformat()
    return get_weekly_summary(start_date, end_date)


@app.get("/api/monthly")
async def get_monthly(month: str = ""):
    if not month:
        month = date.today().strftime("%Y-%m")
    return get_monthly_summary(month)


@app.get("/api/sessions")
async def list_sessions():
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
            })
    return result


@app.post("/api/refresh")
async def refresh_data():
    # Poll Admin API
    records = await poll_latest_usage(since_minutes=5)
    if records:
        db.record_api_usage_batch(records)

    # Re-parse Claude Code sessions
    sessions = parse_claude_code_sessions()
    for s in sessions:
        db.record_claude_code_session(s)

    return {
        "refreshed_at": datetime.utcnow().isoformat(),
        "api_records_fetched": len(records),
        "sessions_parsed": len(sessions),
        "data_freshness": "live",
    }


@app.get("/api/alerts")
async def get_alerts():
    return get_recent_alerts()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT)
