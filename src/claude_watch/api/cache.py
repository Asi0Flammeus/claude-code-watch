"""Response caching with TTL support.

Provides functions for caching API responses to reduce network calls.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Cache file location
CACHE_FILE = Path.home() / ".claude" / ".usage_cache.json"

# Default cache TTL in seconds (can be overridden with CLAUDE_WATCH_CACHE_TTL)
CACHE_MAX_AGE = 60

# Apply environment variable override
if os.environ.get("CLAUDE_WATCH_CACHE_TTL"):
    try:
        CACHE_MAX_AGE = int(os.environ["CLAUDE_WATCH_CACHE_TTL"])
    except ValueError:
        pass  # Keep default if invalid


def load_cache() -> dict[str, Any] | None:
    """Load cached usage data if valid.

    Returns:
        Cached data if exists and not expired, None otherwise.
    """
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        # Check cache age
        cached_at = cache.get("cached_at")
        if not cached_at:
            return None
        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - cached_dt).total_seconds()
        if age > CACHE_MAX_AGE:
            return None
        return cache.get("data")
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def save_cache(data: dict[str, Any]) -> None:
    """Save usage data to cache.

    Args:
        data: Usage data to cache.
    """
    cache = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass  # Silent fail for cache write errors


def get_stale_cache() -> dict[str, Any] | None:
    """Get cached data even if stale (for fallback).

    Returns:
        Cached data regardless of age, or None if no cache exists.
    """
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        return cache.get("data")
    except (json.JSONDecodeError, OSError):
        return None


__all__ = [
    "CACHE_FILE",
    "CACHE_MAX_AGE",
    "load_cache",
    "save_cache",
    "get_stale_cache",
]
