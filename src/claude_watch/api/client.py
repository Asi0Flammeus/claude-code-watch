"""API client for Claude Code usage endpoints.

Provides functions for fetching usage data from OAuth and Admin APIs.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from claude_watch._version import __version__
from claude_watch.api.cache import get_stale_cache, load_cache, save_cache
from claude_watch.config.credentials import get_access_token

# API endpoints
API_URL = "https://api.anthropic.com/api/oauth/usage"
ADMIN_API_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
API_BETA_HEADER = "oauth-2025-04-20"


def fetch_usage() -> dict:
    """Fetch current usage from OAuth API.

    Returns:
        Usage data dictionary with 'five_hour', 'seven_day', etc. keys.

    Raises:
        RuntimeError: If authentication fails or network error occurs.
    """
    token = get_access_token()

    req = Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": API_BETA_HEADER,
            "Content-Type": "application/json",
            "User-Agent": f"claude-watch/{__version__}",
        },
    )

    try:
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        if e.code == 401:
            raise RuntimeError(
                "Authentication failed. Your session may have expired.\n"
                "Please re-authenticate with Claude Code."
            ) from None
        raise RuntimeError(f"API error: {e.code} {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e


def fetch_usage_cached(
    cache_ttl: Optional[int] = None,
    silent: bool = False,
) -> Optional[dict]:
    """Fetch usage with caching support.

    Args:
        cache_ttl: Override default cache TTL in seconds.
        silent: If True, return None on error instead of raising.
            If cache exists, return stale cache on error.

    Returns:
        Usage data dict, or None if silent mode and error occurred.

    Raises:
        RuntimeError: If not in silent mode and API/network error occurs.
    """
    # Note: cache_ttl parameter is now handled by the cache module's CACHE_MAX_AGE
    # For custom TTL, the cache module needs to be configured beforehand
    try:
        # Try to load from cache first
        cached = load_cache()
        if cached is not None:
            return cached

        # Cache miss or stale, fetch fresh data
        data = fetch_usage()
        save_cache(data)
        return data

    except Exception:
        if silent:
            # Try to return stale cache as fallback
            stale = get_stale_cache()
            if stale is not None:
                return stale
            return None
        raise


def fetch_admin_usage(admin_key: str, days: int = 180) -> list:
    """Fetch historical usage from Admin API with pagination.

    Args:
        admin_key: Admin API key for authentication.
        days: Number of days of history to fetch (default 180 / 6 months).

    Returns:
        List of usage bucket dictionaries.

    Raises:
        RuntimeError: If authentication fails, access denied, or network error.
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    all_data = []
    next_page = None

    while True:
        # Build URL with pagination
        url = (
            f"{ADMIN_API_URL}?"
            f"starting_at={start_date.strftime('%Y-%m-%dT00:00:00Z')}&"
            f"ending_at={end_date.strftime('%Y-%m-%dT23:59:59Z')}&"
            f"bucket_width=1d&"
            f"limit=31&"
            f"group_by[]=model"
        )
        if next_page:
            url += f"&page={next_page}"

        req = Request(
            url,
            headers={
                "x-api-key": admin_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": f"claude-watch/{__version__}",
            },
        )

        try:
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                all_data.extend(data.get("data", []))

                # Check for more pages
                if data.get("has_more") and data.get("next_page"):
                    next_page = data["next_page"]
                else:
                    break
        except HTTPError as e:
            if e.code == 401:
                raise RuntimeError("Admin API authentication failed. Check your API key.") from None
            if e.code == 403:
                raise RuntimeError("Admin API access denied. Ensure you have admin role.") from None
            raise RuntimeError(f"Admin API error: {e.code} {e.reason}") from e
        except URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e

    return all_data


def get_mock_usage_data() -> dict:
    """Generate mock usage data for dry-run mode.

    Returns realistic mock data that matches the API response format.
    Useful for testing and development without making API calls.

    Returns:
        Mock usage data dictionary.
    """
    now = datetime.now(timezone.utc)

    return {
        "five_hour": {
            "utilization": 34.5,
            "resets_at": (now + timedelta(hours=3, minutes=15)).isoformat().replace("+00:00", "Z"),
        },
        "seven_day": {
            "utilization": 12.3,
            "resets_at": (now + timedelta(days=4, hours=9)).isoformat().replace("+00:00", "Z"),
        },
        "seven_day_sonnet": {
            "utilization": 8.1,
            "resets_at": (now + timedelta(days=3, hours=15)).isoformat().replace("+00:00", "Z"),
        },
        "seven_day_opus": None,
        "extra_usage": {
            "is_enabled": False,
        },
    }


__all__ = [
    "API_URL",
    "ADMIN_API_URL",
    "API_BETA_HEADER",
    "fetch_usage",
    "fetch_usage_cached",
    "fetch_admin_usage",
    "get_mock_usage_data",
]
