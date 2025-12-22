"""API client for Claude Code usage endpoints.

Provides functions for fetching usage data from OAuth and Admin APIs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from claude_watch._version import __version__
from claude_watch.api.cache import get_stale_cache, load_cache, save_cache
from claude_watch.api.retry import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    check_network_connectivity,
    is_retryable_error,
    retry_request,
    setup_proxy_handler,
)
from claude_watch.config.audit import is_audit_enabled, log_api_request, log_credential_access
from claude_watch.config.credentials import get_access_token

# API endpoints
API_URL = "https://api.anthropic.com/api/oauth/usage"
ADMIN_API_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
API_BETA_HEADER = "oauth-2025-04-20"


def fetch_usage(
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    proxy: str | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> dict:
    """Fetch current usage from OAuth API with retry support.

    Args:
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        proxy: Optional proxy URL (overrides environment variables).
        on_retry: Optional callback for retry events.

    Returns:
        Usage data dictionary with 'five_hour', 'seven_day', etc. keys.

    Raises:
        RuntimeError: If authentication fails or network error occurs.
    """
    # Setup proxy if specified
    if proxy:
        setup_proxy_handler(proxy)
    else:
        # Use environment variables
        setup_proxy_handler()

    token = get_access_token()

    # Audit log credential access
    if is_audit_enabled():
        log_credential_access("oauth", success=bool(token))

    req = Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": API_BETA_HEADER,
            "Content-Type": "application/json",
            "User-Agent": f"claude-watch/{__version__}",
        },
    )

    retry_count = 0

    def make_request() -> dict:
        nonlocal retry_count
        try:
            with urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode())
                # Audit log successful request
                if is_audit_enabled():
                    log_api_request(
                        endpoint="oauth/usage",
                        method="GET",
                        success=True,
                        status_code=200,
                        retry_count=retry_count,
                    )
                return result
        except HTTPError as e:
            if e.code == 401:
                # Audit log auth failure
                if is_audit_enabled():
                    log_api_request(
                        endpoint="oauth/usage",
                        method="GET",
                        success=False,
                        status_code=401,
                        error="Authentication failed",
                    )
                # Don't retry auth failures
                raise RuntimeError(
                    "Authentication failed. Your session may have expired.\n"
                    "Please re-authenticate with Claude Code."
                ) from None
            if not is_retryable_error(e):
                # Audit log non-retryable error
                if is_audit_enabled():
                    log_api_request(
                        endpoint="oauth/usage",
                        method="GET",
                        success=False,
                        status_code=e.code,
                        error=str(e.reason),
                    )
                raise RuntimeError(f"API error: {e.code} {e.reason}") from e
            retry_count += 1
            raise  # Let retry handler catch retryable errors
        except URLError as e:
            if not is_retryable_error(e):
                # Audit log network error
                if is_audit_enabled():
                    log_api_request(
                        endpoint="oauth/usage",
                        method="GET",
                        success=False,
                        error=str(e.reason),
                    )
                raise RuntimeError(f"Network error: {e.reason}") from e
            retry_count += 1
            raise  # Let retry handler catch retryable errors

    try:
        return retry_request(
            make_request,
            max_retries=max_retries,
            on_retry=on_retry,
        )
    except (HTTPError, URLError) as e:
        # Audit log final failure
        if is_audit_enabled():
            log_api_request(
                endpoint="oauth/usage",
                method="GET",
                success=False,
                error=str(e),
                retry_count=retry_count,
            )
        # Convert any remaining errors to RuntimeError
        if isinstance(e, HTTPError):
            raise RuntimeError(f"API error: {e.code} {e.reason}") from e
        raise RuntimeError(f"Network error: {e.reason}") from e


def fetch_usage_cached(
    cache_ttl: int | None = None,
    silent: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    proxy: str | None = None,
    check_offline: bool = True,
) -> dict | None:
    """Fetch usage with caching support, offline detection, and retry.

    Args:
        cache_ttl: Override default cache TTL in seconds.
        silent: If True, return None on error instead of raising.
            If cache exists, return stale cache on error.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        proxy: Optional proxy URL (overrides environment variables).
        check_offline: If True, check network connectivity before fetch.

    Returns:
        Usage data dict, or None if silent mode and error occurred.
        If returning stale cache, includes '_stale' key set to True.

    Raises:
        RuntimeError: If not in silent mode and API/network error occurs.
    """
    try:
        # Try to load from cache first
        cached = load_cache()
        if cached is not None:
            return cached

        # Check network connectivity before attempting fetch
        if check_offline:
            is_online, offline_reason = check_network_connectivity()
            if not is_online:
                if silent:
                    stale = get_stale_cache()
                    if stale is not None:
                        stale["_stale"] = True
                        stale["_offline"] = True
                        return stale
                    return None
                raise RuntimeError(f"Offline: {offline_reason}")

        # Cache miss or stale, fetch fresh data
        data = fetch_usage(
            timeout=timeout,
            max_retries=max_retries,
            proxy=proxy,
        )
        save_cache(data)
        return data

    except Exception:
        if silent:
            # Try to return stale cache as fallback
            stale = get_stale_cache()
            if stale is not None:
                stale["_stale"] = True
                return stale
            return None
        raise


def fetch_admin_usage(
    admin_key: str,
    days: int = 180,
    timeout: int = 30,
    max_retries: int = DEFAULT_MAX_RETRIES,
    proxy: str | None = None,
) -> list:
    """Fetch historical usage from Admin API with pagination and retry.

    Args:
        admin_key: Admin API key for authentication.
        days: Number of days of history to fetch (default 180 / 6 months).
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts per page.
        proxy: Optional proxy URL (overrides environment variables).

    Returns:
        List of usage bucket dictionaries.

    Raises:
        RuntimeError: If authentication fails, access denied, or network error.
    """
    # Setup proxy
    if proxy:
        setup_proxy_handler(proxy)
    else:
        setup_proxy_handler()

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    all_data: list[dict] = []
    next_page: str | None = None

    def make_page_request(request: Request) -> dict:
        """Make a single page request with error handling."""
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            if e.code == 401:
                raise RuntimeError("Admin API authentication failed. Check your API key.") from None
            if e.code == 403:
                raise RuntimeError("Admin API access denied. Ensure you have admin role.") from None
            if not is_retryable_error(e):
                raise RuntimeError(f"Admin API error: {e.code} {e.reason}") from e
            raise
        except URLError as e:
            if not is_retryable_error(e):
                raise RuntimeError(f"Network error: {e.reason}") from e
            raise

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
            # Use lambda to capture current req value
            data = retry_request(lambda r=req: make_page_request(r), max_retries=max_retries)
            all_data.extend(data.get("data", []))

            # Check for more pages
            if data.get("has_more") and data.get("next_page"):
                next_page = data["next_page"]
            else:
                break
        except (HTTPError, URLError) as e:
            if isinstance(e, HTTPError):
                raise RuntimeError(f"Admin API error: {e.code} {e.reason}") from e
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
