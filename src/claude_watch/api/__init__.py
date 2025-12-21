"""API client and caching.

Modules:
    client: Claude API client for fetching usage data
    cache: Response caching with TTL support
"""

from claude_watch.api.cache import (
    CACHE_FILE,
    CACHE_MAX_AGE,
    get_stale_cache,
    load_cache,
    save_cache,
)
from claude_watch.api.client import (
    ADMIN_API_URL,
    API_BETA_HEADER,
    API_URL,
    fetch_admin_usage,
    fetch_usage,
    fetch_usage_cached,
    get_mock_usage_data,
)

__all__ = [
    # Cache
    "CACHE_FILE",
    "CACHE_MAX_AGE",
    "load_cache",
    "save_cache",
    "get_stale_cache",
    # Client
    "API_URL",
    "ADMIN_API_URL",
    "API_BETA_HEADER",
    "fetch_usage",
    "fetch_usage_cached",
    "fetch_admin_usage",
    "get_mock_usage_data",
]
