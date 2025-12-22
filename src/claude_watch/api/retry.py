"""Network resilience with retry logic and proxy support."""

from __future__ import annotations

import os
import random
import socket
import time
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener, install_opener

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 30.0  # seconds
DEFAULT_TIMEOUT = 10  # seconds

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

T = TypeVar("T")


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> float:
    """Calculate exponential backoff delay with jitter.

    Uses exponential backoff (2^attempt * base_delay) with random jitter
    to prevent thundering herd problems.

    Args:
        attempt: Current attempt number (0-indexed).
        base_delay: Base delay in seconds.
        max_delay: Maximum delay cap in seconds.

    Returns:
        Delay in seconds with jitter applied.
    """
    # Exponential backoff: 2^attempt * base_delay
    delay = min(base_delay * (2**attempt), max_delay)

    # Add jitter: random value between 0 and delay
    jitter = random.random() * delay * 0.5  # Up to 50% jitter

    return delay + jitter


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry.

    Args:
        error: The exception that occurred.

    Returns:
        True if the request should be retried.
    """
    if isinstance(error, HTTPError):
        return error.code in RETRYABLE_STATUS_CODES

    if isinstance(error, URLError):
        # Network errors are generally retryable
        reason = str(error.reason).lower()
        retryable_reasons = [
            "connection refused",
            "connection reset",
            "connection timed out",
            "name or service not known",
            "temporary failure",
            "try again",
        ]
        return any(r in reason for r in retryable_reasons)

    if isinstance(error, (socket.timeout, TimeoutError)):
        return True

    return False


def check_network_connectivity() -> tuple[bool, str | None]:
    """Check if network is available.

    Attempts to connect to well-known hosts to verify network connectivity.

    Returns:
        Tuple of (is_online, error_message).
    """
    # Try multiple hosts to avoid false negatives
    test_hosts = [
        ("api.anthropic.com", 443),
        ("1.1.1.1", 53),  # Cloudflare DNS
        ("8.8.8.8", 53),  # Google DNS
    ]

    for host, port in test_hosts:
        try:
            socket.create_connection((host, port), timeout=3)
            return True, None
        except (socket.timeout, OSError):
            continue

    return False, "No network connectivity detected"


def setup_proxy_handler(proxy_url: str | None = None) -> None:
    """Configure urllib to use proxy settings.

    Respects HTTP_PROXY, HTTPS_PROXY, and NO_PROXY environment variables.
    An explicit proxy_url takes precedence over environment variables.

    Args:
        proxy_url: Optional explicit proxy URL (overrides env vars).
    """
    proxies = {}

    # Check for explicit proxy first
    if proxy_url:
        proxies["http"] = proxy_url
        proxies["https"] = proxy_url
    else:
        # Use environment variables
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy

    if proxies:
        # Install proxy handler globally
        proxy_handler = ProxyHandler(proxies)
        opener = build_opener(proxy_handler)
        install_opener(opener)


def get_no_proxy_hosts() -> set[str]:
    """Get list of hosts that should bypass proxy.

    Returns:
        Set of hostnames that should not use proxy.
    """
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    return {h.strip().lower() for h in no_proxy.split(",") if h.strip()}


def should_bypass_proxy(host: str) -> bool:
    """Check if a host should bypass the proxy.

    Args:
        host: Hostname to check.

    Returns:
        True if proxy should be bypassed for this host.
    """
    no_proxy_hosts = get_no_proxy_hosts()
    host_lower = host.lower()

    for pattern in no_proxy_hosts:
        if pattern.startswith("."):
            # Suffix match (e.g., .example.com matches sub.example.com)
            if host_lower.endswith(pattern) or host_lower == pattern[1:]:
                return True
        elif pattern == "*":
            return True
        elif host_lower == pattern:
            return True

    return False


def retry_request(
    request_func: Callable[[], T],
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Execute a request with automatic retry on transient failures.

    Args:
        request_func: Function to execute (should make the HTTP request).
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay between retries in seconds.
        max_delay: Maximum delay cap in seconds.
        on_retry: Optional callback called before each retry with
                  (attempt_number, error, delay).

    Returns:
        Result of the request function.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return request_func()
        except Exception as e:
            last_error = e

            # Check if we should retry
            if attempt >= max_retries or not is_retryable_error(e):
                raise

            # Calculate delay with exponential backoff and jitter
            delay = calculate_backoff_delay(attempt, base_delay, max_delay)

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e, delay)

            # Wait before retry
            time.sleep(delay)

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected retry loop exit")


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_BASE_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_TIMEOUT",
    "RETRYABLE_STATUS_CODES",
    "calculate_backoff_delay",
    "is_retryable_error",
    "check_network_connectivity",
    "setup_proxy_handler",
    "get_no_proxy_hosts",
    "should_bypass_proxy",
    "retry_request",
]
