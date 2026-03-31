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
                model TEXT NOT NULL,
                workspace_id TEXT DEFAULT '',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_creation INTEGER DEFAULT 0,
                cache_read INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                bucket_width TEXT DEFAULT '1m'
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
                estimated_cost REAL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON claude_code_sessions(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON claude_code_sessions(started_at);

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
    finally:
        conn.close()


# --- API Usage ---

def record_api_usage(data: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO api_usage
               (timestamp, model, workspace_id, input_tokens, output_tokens,
                cache_creation, cache_read, cost, bucket_width)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["timestamp"],
                data["model"],
                data.get("workspace_id", ""),
                data.get("input_tokens", 0),
                data.get("output_tokens", 0),
                data.get("cache_creation", 0),
                data.get("cache_read", 0),
                data.get("cost", 0.0),
                data.get("bucket_width", "1m"),
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
               (timestamp, model, workspace_id, input_tokens, output_tokens,
                cache_creation, cache_read, cost, bucket_width)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["timestamp"],
                    r["model"],
                    r.get("workspace_id", ""),
                    r.get("input_tokens", 0),
                    r.get("output_tokens", 0),
                    r.get("cache_creation", 0),
                    r.get("cache_read", 0),
                    r.get("cost", 0.0),
                    r.get("bucket_width", "1m"),
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
        conn.execute(
            """INSERT OR REPLACE INTO claude_code_sessions
               (session_id, started_at, ended_at, total_input_tokens, total_output_tokens,
                total_cache_creation, total_cache_read, status, estimated_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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

        # Estimate number of days in the month for average
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
