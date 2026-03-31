import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
CLAUDE_CODE_HOME = os.path.expanduser(os.getenv("CLAUDE_CODE_HOME", "~/.claude/projects"))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/tokens.db")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))
SESSION_RESET_HOURS = int(os.getenv("SESSION_RESET_HOURS", "5"))
COST_ALERT_THRESHOLDS = [
    float(t) for t in os.getenv("COST_ALERT_THRESHOLDS", "0.8,0.9,0.95").split(",")
]
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Anthropic model pricing (per million tokens)
MODEL_PRICING = {
    "claude-opus-4-6": {
        "input": 15.00,
        "output": 75.00,
        "cache_creation": 18.75,
        "cache_read": 1.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.00,
        "cache_creation": 1.00,
        "cache_read": 0.08,
    },
    # Legacy model names
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_creation": 1.00,
        "cache_read": 0.08,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
        "cache_creation": 18.75,
        "cache_read": 1.50,
    },
}

# Default pricing for unknown models
DEFAULT_PRICING = {
    "input": 3.00,
    "output": 15.00,
    "cache_creation": 3.75,
    "cache_read": 0.30,
}


def get_model_pricing(model: str) -> dict:
    """Return pricing for a model, falling back to default."""
    return MODEL_PRICING.get(model, DEFAULT_PRICING)


def calculate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Calculate cost in dollars for given token counts."""
    pricing = get_model_pricing(model)
    cost = (
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"]
        + (cache_creation_tokens / 1_000_000) * pricing["cache_creation"]
        + (cache_read_tokens / 1_000_000) * pricing["cache_read"]
    )
    return round(cost, 6)
