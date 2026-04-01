import httpx
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from config import ADMIN_API_KEY, calculate_cost

BASE_URL = "https://api.anthropic.com/v1/organizations"


def _headers() -> dict:
    return {
        "x-api-key": ADMIN_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


# ---------------------------------------------------------------------------
# Messages Usage Report
# ---------------------------------------------------------------------------

async def fetch_usage_report(
    starting_at: str,
    ending_at: str,
    bucket_width: str = "1m",
    group_by: Optional[List[str]] = None,
) -> dict:
    """
    Query /v1/organizations/usage_report/messages.

    Args:
        starting_at: ISO8601 datetime (e.g. "2026-03-30T00:00:00Z")
        ending_at: ISO8601 datetime
        bucket_width: "1m", "1h", or "1d"
        group_by: list of dimensions to group by
                  (model, workspace_id, api_key_id, service_tier,
                   context_window, inference_geo, speed)
    """
    params: dict = {
        "starting_at": starting_at,
        "ending_at": ending_at,
        "bucket_width": bucket_width,
    }
    if group_by:
        for g in group_by:
            params.setdefault("group_by[]", [])
            if isinstance(params["group_by[]"], list):
                params["group_by[]"] = g  # httpx handles repeated keys via list
        # Use explicit repeated params for httpx
        param_list = [
            ("starting_at", starting_at),
            ("ending_at", ending_at),
            ("bucket_width", bucket_width),
        ]
        for g in group_by:
            param_list.append(("group_by[]", g))
    else:
        param_list = None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/usage_report/messages",
            headers=_headers(),
            params=param_list or params,
        )
        resp.raise_for_status()
        return resp.json()


def parse_usage_response(raw: dict) -> List[dict]:
    """
    Parse raw API response into normalized records for database storage.

    The API returns:
        data: [ { starting_at, ending_at, results: [ {...usage fields...} ] } ]

    Each result contains:
        uncached_input_tokens, output_tokens, cache_read_input_tokens,
        cache_creation: { ephemeral_5m_input_tokens, ephemeral_1h_input_tokens },
        model, workspace_id, api_key_id, service_tier, context_window,
        inference_geo, speed, server_tool_use: { web_search_requests }
    """
    records = []
    for bucket in raw.get("data", []):
        bucket_start = bucket.get("starting_at", "")
        bucket_end = bucket.get("ending_at", "")

        for result in bucket.get("results", []):
            model = result.get("model") or "unknown"
            uncached_input = result.get("uncached_input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            cache_read = result.get("cache_read_input_tokens", 0)

            # cache_creation is a nested object
            cache_creation_obj = result.get("cache_creation", {})
            if isinstance(cache_creation_obj, dict):
                cache_creation = (
                    cache_creation_obj.get("ephemeral_5m_input_tokens", 0)
                    + cache_creation_obj.get("ephemeral_1h_input_tokens", 0)
                )
            else:
                # Fallback for older API responses
                cache_creation = int(cache_creation_obj or 0)

            # Total input = uncached + cache_read + cache_creation
            total_input = uncached_input + cache_read + cache_creation

            cost = calculate_cost(
                model=model,
                input_tokens=uncached_input,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_creation,
                cache_read_tokens=cache_read,
            )

            # Server tool use
            server_tools = result.get("server_tool_use", {})
            web_searches = server_tools.get("web_search_requests", 0) if server_tools else 0

            records.append({
                "timestamp": bucket_start,
                "timestamp_end": bucket_end,
                "model": model,
                "workspace_id": result.get("workspace_id") or "",
                "api_key_id": result.get("api_key_id") or "",
                "input_tokens": total_input,
                "uncached_input_tokens": uncached_input,
                "output_tokens": output_tokens,
                "cache_creation": cache_creation,
                "cache_read": cache_read,
                "cost": cost,
                "bucket_width": raw.get("bucket_width", "1m"),
                "service_tier": result.get("service_tier") or "",
                "context_window": result.get("context_window") or "",
                "inference_geo": result.get("inference_geo") or "",
                "speed": result.get("speed") or "",
                "web_search_requests": web_searches,
            })

    return records


async def poll_latest_usage(since_minutes: int = 5) -> List[dict]:
    """Fetch the last N minutes of usage and return parsed records."""
    now = datetime.now(timezone.utc)
    starting_at = (now - timedelta(minutes=since_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ending_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Use appropriate bucket width based on time range
    if since_minutes > 60 * 24:
        bucket_width = "1d"
    elif since_minutes > 60:
        bucket_width = "1h"
    else:
        bucket_width = "1m"

    try:
        raw = await fetch_usage_report(
            starting_at,
            ending_at,
            bucket_width=bucket_width,
            group_by=["model", "workspace_id"],
        )
        print(f"[api_client] Raw response: {len(raw.get('data', []))} buckets")
        return parse_usage_response(raw)
    except httpx.HTTPStatusError as e:
        print(f"[api_client] HTTP error polling usage: {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        print(f"[api_client] Request error polling usage: {e}")
        return []


# ---------------------------------------------------------------------------
# Claude Code Analytics Report
# ---------------------------------------------------------------------------

async def fetch_claude_code_analytics(
    starting_at: str,
    ending_at: str,
) -> dict:
    """
    Query /v1/organizations/usage_report/claude_code for per-user,
    per-day Claude Code analytics including:
    - actor (email or api_key_name)
    - terminal_type (vscode, iTerm, tmux, etc.)
    - lines of code added/removed
    - commits and PRs by Claude Code
    - tool actions (edit/write accepted/rejected)
    - per-model cost breakdown
    """
    params = {
        "starting_at": starting_at,
        "ending_at": ending_at,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/usage_report/claude_code",
            headers=_headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def parse_claude_code_analytics(raw: dict) -> List[dict]:
    """Parse Claude Code analytics response into normalized records."""
    records = []
    for entry in raw.get("data", []):
        actor = entry.get("actor", {})
        user_actor = actor.get("user_actor", {})
        api_actor = actor.get("api_actor", {})

        email = user_actor.get("email_address", "")
        api_key_name = api_actor.get("api_key_name", "")
        actor_name = email or api_key_name or "unknown"

        core = entry.get("core_metrics", {})
        loc = core.get("lines_of_code", {})
        tool_actions = entry.get("tool_actions", {})

        # Aggregate tool action counts
        tools_accepted = 0
        tools_rejected = 0
        for tool_name, counts in tool_actions.items():
            if isinstance(counts, dict):
                tools_accepted += counts.get("accepted", 0)
                tools_rejected += counts.get("rejected", 0)

        # Per-model breakdown
        model_breakdown = []
        for mb in entry.get("model_breakdown", []):
            tokens = mb.get("tokens", {})
            est_cost = mb.get("estimated_cost", {})
            model_breakdown.append({
                "model": mb.get("model", "unknown"),
                "input_tokens": tokens.get("input", 0),
                "output_tokens": tokens.get("output", 0),
                "cache_read": tokens.get("cache_read", 0),
                "cache_creation": tokens.get("cache_creation", 0),
                "cost": est_cost.get("amount", 0.0),
                "currency": est_cost.get("currency", "USD"),
            })

        records.append({
            "date": entry.get("starting_at", "")[:10],
            "actor": actor_name,
            "organization_id": entry.get("organization_id", ""),
            "customer_type": entry.get("customer_type", ""),
            "terminal_type": entry.get("terminal_type", ""),
            "num_sessions": core.get("num_sessions", 0),
            "lines_added": loc.get("added", 0),
            "lines_removed": loc.get("removed", 0),
            "commits": core.get("commits_by_claude_code", 0),
            "pull_requests": core.get("pull_requests_by_claude_code", 0),
            "tools_accepted": tools_accepted,
            "tools_rejected": tools_rejected,
            "model_breakdown": model_breakdown,
        })

    return records


async def poll_claude_code_analytics(since_days: int = 7) -> List[dict]:
    """Fetch the last N days of Claude Code analytics."""
    now = datetime.now(timezone.utc)
    starting_at = (now - timedelta(days=since_days)).strftime("%Y-%m-%d")
    ending_at = now.strftime("%Y-%m-%d")

    try:
        raw = await fetch_claude_code_analytics(starting_at, ending_at)
        return parse_claude_code_analytics(raw)
    except httpx.HTTPStatusError as e:
        print(f"[api_client] HTTP error polling CC analytics: {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        print(f"[api_client] Request error polling CC analytics: {e}")
        return []
