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


async def fetch_usage_report(
    starting_at: str,
    ending_at: str,
    bucket_width: str = "1m",
) -> dict:
    """
    Query the Admin API usage report endpoint.

    Args:
        starting_at: ISO8601 datetime (e.g. "2026-03-30T00:00:00Z")
        ending_at: ISO8601 datetime
        bucket_width: "1m", "1h", or "1d"

    Returns:
        Raw API response dict.
    """
    params = {
        "starting_at": starting_at,
        "ending_at": ending_at,
        "bucket_width": bucket_width,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/usage_report/messages",
            headers=_headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_cost_report(
    starting_at: str,
    ending_at: str,
    group_by: Optional[List[str]] = None,
) -> dict:
    """Fetch cost report grouped by workspace or other dimensions."""
    params = {
        "starting_at": starting_at,
        "ending_at": ending_at,
    }
    if group_by:
        params["group_by"] = ",".join(group_by)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/usage_report/messages",
            headers=_headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def parse_usage_response(raw: dict) -> List[dict]:
    """
    Parse raw API response into normalized records for database storage.

    Returns list of dicts with keys:
        timestamp, model, workspace_id, input_tokens, output_tokens,
        cache_creation, cache_read, cost, bucket_width
    """
    records = []
    for bucket in raw.get("data", []):
        model = bucket.get("model", "unknown")
        input_tokens = bucket.get("input_tokens", 0)
        output_tokens = bucket.get("output_tokens", 0)
        cache_creation = bucket.get("cache_creation_input_tokens", 0)
        cache_read = bucket.get("cache_read_input_tokens", 0)

        cost = calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
        )

        records.append({
            "timestamp": bucket.get("started_at", datetime.now(timezone.utc).isoformat()),
            "model": model,
            "workspace_id": bucket.get("workspace_id", ""),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation": cache_creation,
            "cache_read": cache_read,
            "cost": cost,
            "bucket_width": raw.get("bucket_width", "1m"),
        })

    return records


async def poll_latest_usage(since_minutes: int = 5) -> List[dict]:
    """
    Convenience function: fetch the last N minutes of usage and return parsed records.
    """
    now = datetime.now(timezone.utc)
    starting_at = (now - timedelta(minutes=since_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ending_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        raw = await fetch_usage_report(starting_at, ending_at, bucket_width="1m")
        return parse_usage_response(raw)
    except httpx.HTTPStatusError as e:
        print(f"[api_client] HTTP error polling usage: {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        print(f"[api_client] Request error polling usage: {e}")
        return []
