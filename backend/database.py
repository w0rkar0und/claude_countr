import json
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional

from config import SQLITE_DB_PATH

_db_path: str = SQLITE_DB_PATH


def _get_conn() -> sqlite3.Connection:
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                timestamp_end TEXT DEFAULT '',
                model TEXT NOT NULL,
                workspace_id TEXT DEFAULT '',
                api_key_id TEXT DEFAULT '',
                input_tokens INTEGER DEFAULT 0,
                uncached_input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_creation INTEGER DEFAULT 0,
                cache_read INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                bucket_width TEXT DEFAULT '1m',
                service_tier TEXT DEFAULT '',
                context_window TEXT DEFAULT '',
                inference_geo TEXT DEFAULT '',
                speed TEXT DEFAULT '',
                web_search_requests INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp);
            CREATE INDEX IF NOT EXISTS idx_api_usage_workspace ON api_usage(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_api_usage_model ON api_usage(model);

            CREATE TABLE IF NOT EXISTS claude_code_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                total_cache_creation INTEGER DEFAULT 0,
                total_cache_read INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed')),
                estimated_cost REAL DEFAULT 0.0,
                model TEXT DEFAULT '',
                project TEXT DEFAULT '',
                git_branch TEXT DEFAULT '',
                version TEXT DEFAULT '',
                is_subagent INTEGER DEFAULT 0,
                tool_usage TEXT DEFAULT '{}',
                inference_geo TEXT DEFAULT '',
                service_tier TEXT DEFAULT '',
                speed TEXT DEFAULT '',
                message_count INTEGER DEFAULT 0,
                user_messages INTEGER DEFAULT 0,
                assistant_messages INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON claude_code_sessions(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON claude_code_sessions(started_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_project ON claude_code_sessions(project);

            CREATE TABLE IF NOT EXISTS claude_code_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                actor TEXT DEFAULT '',
                organization_id TEXT DEFAULT '',
                customer_type TEXT DEFAULT '',
                terminal_type TEXT DEFAULT '',
                num_sessions INTEGER DEFAULT 0,
                lines_added INTEGER DEFAULT 0,
                lines_removed INTEGER DEFAULT 0,
                commits INTEGER DEFAULT 0,
                pull_requests INTEGER DEFAULT 0,
                tools_accepted INTEGER DEFAULT 0,
                tools_rejected INTEGER DEFAULT 0,
                model_breakdown TEXT DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_analytics_date ON claude_code_analytics(date);
            CREATE INDEX IF NOT EXISTS idx_analytics_actor ON claude_code_analytics(actor);

            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                workspace_id TEXT DEFAULT '',
                model TEXT DEFAULT '',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                source TEXT DEFAULT 'api' CHECK(source IN ('api', 'claude_code', 'both'))
            );
            CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_summary(date);
            CREATE INDEX IF NOT EXISTS idx_daily_workspace ON daily_summary(workspace_id);

            CREATE TABLE IF NOT EXISTS cost_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                threshold_percent REAL DEFAULT 0.0
            );
        """)
        conn.commit()

        # Add columns if they don't exist (migration for existing DBs)
        _migrate_columns(conn)
    finally:
        conn.close()


def _migrate_columns(conn: sqlite3.Connection):
    """Add new columns to existing tables if missing."""
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(api_usage)").fetchall()
    }
    migrations = {
        "timestamp_end": "ALTER TABLE api_usage ADD COLUMN timestamp_end TEXT DEFAULT ''",
        "api_key_id": "ALTER TABLE api_usage ADD COLUMN api_key_id TEXT DEFAULT ''",
        "uncached_input_tokens": "ALTER TABLE api_usage ADD COLUMN uncached_input_tokens INTEGER DEFAULT 0",
        "service_tier": "ALTER TABLE api_usage ADD COLUMN service_tier TEXT DEFAULT ''",
        "context_window": "ALTER TABLE api_usage ADD COLUMN context_window TEXT DEFAULT ''",
        "inference_geo": "ALTER TABLE api_usage ADD COLUMN inference_geo TEXT DEFAULT ''",
        "speed": "ALTER TABLE api_usage ADD COLUMN speed TEXT DEFAULT ''",
        "web_search_requests": "ALTER TABLE api_usage ADD COLUMN web_search_requests INTEGER DEFAULT 0",
    }
    for col, sql in migrations.items():
        if col not in existing:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass

    # Sessions table migrations
    existing_sess = {
        row[1]
        for row in conn.execute("PRAGMA table_info(claude_code_sessions)").fetchall()
    }
    sess_migrations = {
        "model": "ALTER TABLE claude_code_sessions ADD COLUMN model TEXT DEFAULT ''",
        "project": "ALTER TABLE claude_code_sessions ADD COLUMN project TEXT DEFAULT ''",
        "git_branch": "ALTER TABLE claude_code_sessions ADD COLUMN git_branch TEXT DEFAULT ''",
        "version": "ALTER TABLE claude_code_sessions ADD COLUMN version TEXT DEFAULT ''",
        "is_subagent": "ALTER TABLE claude_code_sessions ADD COLUMN is_subagent INTEGER DEFAULT 0",
        "tool_usage": "ALTER TABLE claude_code_sessions ADD COLUMN tool_usage TEXT DEFAULT '{}'",
        "inference_geo": "ALTER TABLE claude_code_sessions ADD COLUMN inference_geo TEXT DEFAULT ''",
        "service_tier": "ALTER TABLE claude_code_sessions ADD COLUMN service_tier TEXT DEFAULT ''",
        "speed": "ALTER TABLE claude_code_sessions ADD COLUMN speed TEXT DEFAULT ''",
        "message_count": "ALTER TABLE claude_code_sessions ADD COLUMN message_count INTEGER DEFAULT 0",
        "user_messages": "ALTER TABLE claude_code_sessions ADD COLUMN user_messages INTEGER DEFAULT 0",
        "assistant_messages": "ALTER TABLE claude_code_sessions ADD COLUMN assistant_messages INTEGER DEFAULT 0",
    }
    for col, sql in sess_migrations.items():
        if col not in existing_sess:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass

    conn.commit()


# --- API Usage ---

def record_api_usage(data: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO api_usage
               (timestamp, timestamp_end, model, workspace_id, api_key_id,
                input_tokens, uncached_input_tokens, output_tokens,
                cache_creation, cache_read, cost, bucket_width,
                service_tier, context_window, inference_geo, speed, web_search_requests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["timestamp"],
                data.get("timestamp_end", ""),
                data["model"],
                data.get("workspace_id", ""),
                data.get("api_key_id", ""),
                data.get("input_tokens", 0),
                data.get("uncached_input_tokens", 0),
                data.get("output_tokens", 0),
                data.get("cache_creation", 0),
                data.get("cache_read", 0),
                data.get("cost", 0.0),
                data.get("bucket_width", "1m"),
                data.get("service_tier", ""),
                data.get("context_window", ""),
                data.get("inference_geo", ""),
                data.get("speed", ""),
                data.get("web_search_requests", 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_api_usage_batch(records: List[dict]) -> int:
    """Insert multiple API usage records. Returns count inserted."""
    if not records:
        return 0
    conn = _get_conn()
    try:
        conn.executemany(
            """INSERT INTO api_usage
               (timestamp, timestamp_end, model, workspace_id, api_key_id,
                input_tokens, uncached_input_tokens, output_tokens,
                cache_creation, cache_read, cost, bucket_width,
                service_tier, context_window, inference_geo, speed, web_search_requests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["timestamp"],
                    r.get("timestamp_end", ""),
                    r["model"],
                    r.get("workspace_id", ""),
                    r.get("api_key_id", ""),
                    r.get("input_tokens", 0),
                    r.get("uncached_input_tokens", 0),
                    r.get("output_tokens", 0),
                    r.get("cache_creation", 0),
                    r.get("cache_read", 0),
                    r.get("cost", 0.0),
                    r.get("bucket_width", "1m"),
                    r.get("service_tier", ""),
                    r.get("context_window", ""),
                    r.get("inference_geo", ""),
                    r.get("speed", ""),
                    r.get("web_search_requests", 0),
                )
                for r in records
            ],
        )
        conn.commit()
        return len(records)
    finally:
        conn.close()


# --- Claude Code Sessions ---

def record_claude_code_session(session: dict) -> None:
    conn = _get_conn()
    try:
        tool_usage = session.get("tool_usage", {})
        if isinstance(tool_usage, dict):
            tool_usage = json.dumps(tool_usage)

        conn.execute(
            """INSERT OR REPLACE INTO claude_code_sessions
               (session_id, started_at, ended_at, total_input_tokens, total_output_tokens,
                total_cache_creation, total_cache_read, status, estimated_cost,
                model, project, git_branch, version, is_subagent, tool_usage,
                inference_geo, service_tier, speed, message_count, user_messages, assistant_messages)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session["session_id"],
                session["started_at"],
                session.get("ended_at"),
                session.get("total_input_tokens", 0),
                session.get("total_output_tokens", 0),
                session.get("total_cache_creation", 0),
                session.get("total_cache_read", 0),
                session.get("status", "active"),
                session.get("estimated_cost", 0.0),
                session.get("model", ""),
                session.get("project", ""),
                session.get("git_branch", ""),
                session.get("version", ""),
                1 if session.get("is_subagent") else 0,
                tool_usage,
                session.get("inference_geo", ""),
                session.get("service_tier", ""),
                session.get("speed", ""),
                session.get("message_count", 0),
                session.get("user_messages", 0),
                session.get("assistant_messages", 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_session_tokens(session_id: str, tokens: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE claude_code_sessions
               SET total_input_tokens = ?,
                   total_output_tokens = ?,
                   total_cache_creation = ?,
                   total_cache_read = ?,
                   estimated_cost = ?,
                   status = ?,
                   ended_at = ?
               WHERE session_id = ?""",
            (
                tokens.get("input_tokens", 0),
                tokens.get("output_tokens", 0),
                tokens.get("cache_creation", 0),
                tokens.get("cache_read", 0),
                tokens.get("cost", 0.0),
                tokens.get("status", "active"),
                tokens.get("ended_at"),
                session_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_active_sessions() -> List[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM claude_code_sessions WHERE status = 'active' ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_sessions(limit: int = 50) -> List[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM claude_code_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Claude Code Analytics ---

def record_analytics_batch(records: List[dict]) -> int:
    """Insert Claude Code analytics records."""
    if not records:
        return 0
    conn = _get_conn()
    try:
        conn.executemany(
            """INSERT INTO claude_code_analytics
               (date, actor, organization_id, customer_type, terminal_type,
                num_sessions, lines_added, lines_removed, commits, pull_requests,
                tools_accepted, tools_rejected, model_breakdown)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["date"],
                    r.get("actor", ""),
                    r.get("organization_id", ""),
                    r.get("customer_type", ""),
                    r.get("terminal_type", ""),
                    r.get("num_sessions", 0),
                    r.get("lines_added", 0),
                    r.get("lines_removed", 0),
                    r.get("commits", 0),
                    r.get("pull_requests", 0),
                    r.get("tools_accepted", 0),
                    r.get("tools_rejected", 0),
                    json.dumps(r.get("model_breakdown", [])),
                )
                for r in records
            ],
        )
        conn.commit()
        return len(records)
    finally:
        conn.close()


def get_analytics_summary(days: int = 7) -> dict:
    """Get aggregated Claude Code analytics for recent days."""
    conn = _get_conn()
    try:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT
                 SUM(num_sessions) as total_sessions,
                 SUM(lines_added) as lines_added,
                 SUM(lines_removed) as lines_removed,
                 SUM(commits) as commits,
                 SUM(pull_requests) as pull_requests,
                 SUM(tools_accepted) as tools_accepted,
                 SUM(tools_rejected) as tools_rejected
               FROM claude_code_analytics
               WHERE date >= ?""",
            (cutoff,),
        ).fetchone()

        terminal_rows = conn.execute(
            """SELECT terminal_type, COUNT(*) as count, SUM(num_sessions) as sessions
               FROM claude_code_analytics
               WHERE date >= ? AND terminal_type != ''
               GROUP BY terminal_type
               ORDER BY sessions DESC""",
            (cutoff,),
        ).fetchall()

        return {
            "total_sessions": rows["total_sessions"] or 0,
            "lines_added": rows["lines_added"] or 0,
            "lines_removed": rows["lines_removed"] or 0,
            "commits": rows["commits"] or 0,
            "pull_requests": rows["pull_requests"] or 0,
            "tools_accepted": rows["tools_accepted"] or 0,
            "tools_rejected": rows["tools_rejected"] or 0,
            "by_terminal": [
                {"terminal": r["terminal_type"], "sessions": r["sessions"]}
                for r in terminal_rows
            ],
        }
    finally:
        conn.close()


# --- Summaries ---

def get_daily_summary(date_str: str) -> dict:
    conn = _get_conn()
    try:
        # Aggregate from api_usage
        api_row = conn.execute(
            """SELECT
                 COALESCE(SUM(input_tokens), 0) as input_tokens,
                 COALESCE(SUM(output_tokens), 0) as output_tokens,
                 COALESCE(SUM(cache_creation + cache_read), 0) as cache_tokens,
                 COALESCE(SUM(cost), 0) as cost
               FROM api_usage
               WHERE date(timestamp) = ?""",
            (date_str,),
        ).fetchone()

        # Aggregate from claude_code_sessions
        cc_row = conn.execute(
            """SELECT
                 COALESCE(SUM(total_input_tokens), 0) as input_tokens,
                 COALESCE(SUM(total_output_tokens), 0) as output_tokens,
                 COALESCE(SUM(total_cache_creation + total_cache_read), 0) as cache_tokens,
                 COALESCE(SUM(estimated_cost), 0) as cost
               FROM claude_code_sessions
               WHERE date(started_at) = ?""",
            (date_str,),
        ).fetchone()

        # Model breakdown from api_usage
        model_rows = conn.execute(
            """SELECT model,
                 SUM(input_tokens) as input_tokens,
                 SUM(output_tokens) as output_tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE date(timestamp) = ?
               GROUP BY model""",
            (date_str,),
        ).fetchall()

        # Hourly breakdown
        hourly_rows = conn.execute(
            """SELECT
                 CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                 SUM(input_tokens + output_tokens) as tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE date(timestamp) = ?
               GROUP BY hour
               ORDER BY hour""",
            (date_str,),
        ).fetchall()

        by_model = {
            r["model"]: {
                "inputTokens": r["input_tokens"],
                "outputTokens": r["output_tokens"],
                "cost": r["cost"],
            }
            for r in model_rows
        }

        hourly = [{"hour": r["hour"], "tokens": r["tokens"], "cost": r["cost"]} for r in hourly_rows]

        return {
            "date": date_str,
            "totalInputTokens": api_row["input_tokens"] + cc_row["input_tokens"],
            "totalOutputTokens": api_row["output_tokens"] + cc_row["output_tokens"],
            "totalCacheTokens": api_row["cache_tokens"] + cc_row["cache_tokens"],
            "totalTokens": (
                api_row["input_tokens"] + cc_row["input_tokens"]
                + api_row["output_tokens"] + cc_row["output_tokens"]
                + api_row["cache_tokens"] + cc_row["cache_tokens"]
            ),
            "estimatedCost": round(api_row["cost"] + cc_row["cost"], 6),
            "byModel": by_model,
            "hourly": hourly,
        }
    finally:
        conn.close()


def get_weekly_summary(start_date: str, end_date: str) -> dict:
    conn = _get_conn()
    try:
        daily_rows = conn.execute(
            """SELECT date(timestamp) as day,
                 SUM(input_tokens + output_tokens + cache_creation + cache_read) as tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE date(timestamp) BETWEEN ? AND ?
               GROUP BY day
               ORDER BY day""",
            (start_date, end_date),
        ).fetchall()

        model_rows = conn.execute(
            """SELECT model,
                 SUM(input_tokens + output_tokens) as tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE date(timestamp) BETWEEN ? AND ?
               GROUP BY model""",
            (start_date, end_date),
        ).fetchall()

        daily = [{"date": r["day"], "tokens": r["tokens"], "cost": r["cost"]} for r in daily_rows]
        total_tokens = sum(d["tokens"] for d in daily)
        total_cost = sum(d["cost"] for d in daily)
        num_days = max(len(daily), 1)

        return {
            "startDate": start_date,
            "endDate": end_date,
            "dailyBreakdown": daily,
            "totalTokens": total_tokens,
            "totalCost": round(total_cost, 6),
            "averageDailyCost": round(total_cost / num_days, 6),
            "byModel": {
                r["model"]: {"tokens": r["tokens"], "cost": r["cost"]}
                for r in model_rows
            },
        }
    finally:
        conn.close()


def get_monthly_summary(month: str) -> dict:
    """month format: YYYY-MM"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT
                 strftime('%W', timestamp) as week,
                 SUM(input_tokens + output_tokens + cache_creation + cache_read) as tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE strftime('%Y-%m', timestamp) = ?
               GROUP BY week
               ORDER BY week""",
            (month,),
        ).fetchall()

        model_rows = conn.execute(
            """SELECT model,
                 SUM(input_tokens + output_tokens) as tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE strftime('%Y-%m', timestamp) = ?
               GROUP BY model""",
            (month,),
        ).fetchall()

        workspace_rows = conn.execute(
            """SELECT workspace_id,
                 SUM(input_tokens + output_tokens) as tokens,
                 SUM(cost) as cost
               FROM api_usage
               WHERE strftime('%Y-%m', timestamp) = ?
               GROUP BY workspace_id""",
            (month,),
        ).fetchall()

        weekly = [{"week": int(r["week"]), "tokens": r["tokens"], "cost": r["cost"]} for r in rows]
        total_tokens = sum(w["tokens"] for w in weekly)
        total_cost = sum(w["cost"] for w in weekly)

        year, mo = month.split("-")
        if int(mo) == 12:
            next_month = date(int(year) + 1, 1, 1)
        else:
            next_month = date(int(year), int(mo) + 1, 1)
        days_in_month = (next_month - date(int(year), int(mo), 1)).days

        return {
            "month": month,
            "weeklyBreakdown": weekly,
            "totalTokens": total_tokens,
            "totalCost": round(total_cost, 6),
            "averageDailyCost": round(total_cost / days_in_month, 6),
            "byModel": {
                r["model"]: {"tokens": r["tokens"], "cost": r["cost"]}
                for r in model_rows
            },
            "byWorkspace": {
                r["workspace_id"]: {"tokens": r["tokens"], "cost": r["cost"]}
                for r in workspace_rows
            },
        }
    finally:
        conn.close()


def get_cost_by_model(start_date: str, end_date: str) -> dict:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT model, SUM(cost) as cost, SUM(input_tokens + output_tokens) as tokens
               FROM api_usage
               WHERE date(timestamp) BETWEEN ? AND ?
               GROUP BY model""",
            (start_date, end_date),
        ).fetchall()
        return {r["model"]: {"cost": r["cost"], "tokens": r["tokens"]} for r in rows}
    finally:
        conn.close()


def get_cost_by_workspace(start_date: str, end_date: str) -> dict:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT workspace_id, SUM(cost) as cost, SUM(input_tokens + output_tokens) as tokens
               FROM api_usage
               WHERE date(timestamp) BETWEEN ? AND ?
               GROUP BY workspace_id""",
            (start_date, end_date),
        ).fetchall()
        return {r["workspace_id"]: {"cost": r["cost"], "tokens": r["tokens"]} for r in rows}
    finally:
        conn.close()


# --- Alerts ---

def record_alert(session_id: str, alert_type: str, message: str, threshold: float) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO cost_alerts (created_at, session_id, alert_type, message, threshold_percent)
               VALUES (?, ?, ?, ?, ?)""",
            (datetime.utcnow().isoformat(), session_id, alert_type, message, threshold),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_alerts(limit: int = 20) -> List[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM cost_alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_last_api_usage_timestamp() -> Optional[str]:
    """Return the most recent API usage timestamp, or None if empty."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT MAX(timestamp) as ts FROM api_usage").fetchone()
        return row["ts"] if row and row["ts"] else None
    finally:
        conn.close()
