"""Usage history storage and retrieval.

Provides functions for persisting and loading usage history data.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# History file location
HISTORY_FILE = Path.home() / ".claude" / ".usage_history.json"

# Default retention period (can be overridden with CLAUDE_WATCH_HISTORY_DAYS)
MAX_HISTORY_DAYS = 180  # 6 months

# Apply environment variable override
if os.environ.get("CLAUDE_WATCH_HISTORY_DAYS"):
    try:
        MAX_HISTORY_DAYS = int(os.environ["CLAUDE_WATCH_HISTORY_DAYS"])
    except ValueError:
        pass  # Keep default if invalid


def load_history() -> list[dict[str, Any]]:
    """Load usage history from file.

    Returns:
        List of history entries, or empty list if file doesn't exist.
    """
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: list[dict[str, Any]]) -> None:
    """Save usage history to file.

    Automatically prunes entries older than MAX_HISTORY_DAYS.

    Args:
        history: List of history entries to save.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_HISTORY_DAYS)
    cutoff_str = cutoff.isoformat()
    history = [h for h in history if h.get("timestamp", "") > cutoff_str]

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_usage(data: dict[str, Any]) -> None:
    """Record current usage data to history.

    Args:
        data: Usage data dict with five_hour, seven_day, etc. keys.
    """
    history = load_history()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "five_hour": data.get("five_hour", {}).get("utilization"),
        "seven_day": data.get("seven_day", {}).get("utilization"),
        "seven_day_sonnet": (
            data.get("seven_day_sonnet", {}).get("utilization")
            if data.get("seven_day_sonnet")
            else None
        ),
        "seven_day_opus": (
            data.get("seven_day_opus", {}).get("utilization")
            if data.get("seven_day_opus")
            else None
        ),
    }
    history.append(entry)
    save_history(history)


__all__ = [
    "HISTORY_FILE",
    "MAX_HISTORY_DAYS",
    "load_history",
    "save_history",
    "record_usage",
]
