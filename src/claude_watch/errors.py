"""Categorized error handling with actionable messages.

Provides structured error types with exit codes and recovery suggestions
for better user experience and scripting integration.
"""

from __future__ import annotations

from enum import IntEnum
from typing import ClassVar


class ExitCode(IntEnum):
    """Exit codes for scripting integration.

    Standard categories:
    - 0: Success
    - 1-9: Usage/config errors (user can fix)
    - 10-19: Authentication errors
    - 20-29: Network errors
    - 30-39: API errors
    - 40-49: System errors
    - 50-59: Data errors
    """

    SUCCESS = 0

    # Usage/config errors (1-9)
    USAGE_ERROR = 1
    CONFIG_ERROR = 2
    SETUP_REQUIRED = 3
    INVALID_ARGUMENT = 4

    # Authentication errors (10-19)
    AUTH_EXPIRED = 10
    AUTH_INVALID = 11
    AUTH_MISSING = 12
    AUTH_PERMISSION = 13

    # Network errors (20-29)
    NETWORK_OFFLINE = 20
    NETWORK_TIMEOUT = 21
    NETWORK_DNS = 22
    NETWORK_PROXY = 23

    # API errors (30-39)
    API_ERROR = 30
    API_RATE_LIMIT = 31
    API_SERVER_ERROR = 32
    API_MAINTENANCE = 33

    # System errors (40-49)
    FILE_NOT_FOUND = 40
    FILE_PERMISSION = 41
    DISK_FULL = 42
    SYSTEM_ERROR = 49

    # Data errors (50-59)
    DATA_CORRUPT = 50
    DATA_INVALID = 51


class ClaudeWatchError(Exception):
    """Base exception for claude-watch with structured error info.

    Attributes:
        message: Human-readable error message.
        code: Exit code for scripting.
        suggestion: Actionable recovery suggestion.
        details: Optional additional context.
    """

    code: ClassVar[ExitCode] = ExitCode.USAGE_ERROR
    suggestion: ClassVar[str] = ""

    def __init__(
        self,
        message: str,
        suggestion: str | None = None,
        details: str | None = None,
    ):
        self.message = message
        self._suggestion = suggestion
        self.details = details
        super().__init__(message)

    def get_suggestion(self) -> str:
        """Get the recovery suggestion."""
        return self._suggestion or self.suggestion

    def format_full(self) -> str:
        """Format the complete error message with suggestion."""
        parts = [f"Error: {self.message}"]
        if self.details:
            parts.append(f"Details: {self.details}")
        suggestion = self.get_suggestion()
        if suggestion:
            parts.append(f"Suggestion: {suggestion}")
        return "\n".join(parts)


# Authentication Errors


class AuthenticationExpiredError(ClaudeWatchError):
    """OAuth token has expired and needs renewal."""

    code = ExitCode.AUTH_EXPIRED
    suggestion = (
        "Re-authenticate with Claude Code by running 'claude' and signing in again."
    )


class AuthenticationInvalidError(ClaudeWatchError):
    """OAuth token format is invalid."""

    code = ExitCode.AUTH_INVALID
    suggestion = (
        "Your credentials appear corrupted. "
        "Try running 'claude' to re-authenticate."
    )


class AuthenticationMissingError(ClaudeWatchError):
    """No credentials found."""

    code = ExitCode.AUTH_MISSING
    suggestion = (
        "Run 'claude' to install and authenticate with Claude Code first."
    )


class PermissionDeniedError(ClaudeWatchError):
    """API access denied (wrong role or permissions)."""

    code = ExitCode.AUTH_PERMISSION
    suggestion = (
        "Ensure your account has the required permissions. "
        "Admin API requires admin role in your organization."
    )


# Network Errors


class NetworkOfflineError(ClaudeWatchError):
    """Device appears to be offline."""

    code = ExitCode.NETWORK_OFFLINE
    suggestion = "Check your internet connection and try again."


class NetworkTimeoutError(ClaudeWatchError):
    """Request timed out."""

    code = ExitCode.NETWORK_TIMEOUT
    suggestion = (
        "The request timed out. Try again, or increase timeout with --timeout flag."
    )


class NetworkDNSError(ClaudeWatchError):
    """DNS resolution failed."""

    code = ExitCode.NETWORK_DNS
    suggestion = (
        "DNS lookup failed. Check your network configuration or try a different DNS server."
    )


class NetworkProxyError(ClaudeWatchError):
    """Proxy connection failed."""

    code = ExitCode.NETWORK_PROXY
    suggestion = (
        "Proxy connection failed. Check your proxy settings "
        "(HTTP_PROXY, HTTPS_PROXY environment variables or --proxy flag)."
    )


# API Errors


class APIError(ClaudeWatchError):
    """Generic API error."""

    code = ExitCode.API_ERROR
    suggestion = "Try again later. If the problem persists, check Anthropic's status page."


class RateLimitError(ClaudeWatchError):
    """API rate limit exceeded."""

    code = ExitCode.API_RATE_LIMIT
    suggestion = (
        "You've hit the API rate limit. Wait a few minutes before trying again."
    )


class ServerError(ClaudeWatchError):
    """API server error (5xx)."""

    code = ExitCode.API_SERVER_ERROR
    suggestion = (
        "The Anthropic API is experiencing issues. "
        "Check status.anthropic.com and try again later."
    )


class MaintenanceError(ClaudeWatchError):
    """API is under maintenance."""

    code = ExitCode.API_MAINTENANCE
    suggestion = (
        "The API is currently under maintenance. Try again in a few minutes."
    )


# Config/Setup Errors


class ConfigError(ClaudeWatchError):
    """Configuration file error."""

    code = ExitCode.CONFIG_ERROR
    suggestion = "Run 'claude-watch --config reset' to reset configuration to defaults."


class SetupRequiredError(ClaudeWatchError):
    """Initial setup has not been completed."""

    code = ExitCode.SETUP_REQUIRED
    suggestion = "Run 'claude-watch --setup' to complete initial configuration."


# File/System Errors


class FileNotFoundError_(ClaudeWatchError):
    """Required file not found."""

    code = ExitCode.FILE_NOT_FOUND
    suggestion = "Ensure the file exists and the path is correct."


class FilePermissionError(ClaudeWatchError):
    """Insufficient permissions for file operation."""

    code = ExitCode.FILE_PERMISSION
    suggestion = (
        "Check file permissions. "
        "Credentials should have 600 permissions (owner read/write only)."
    )


class DataCorruptError(ClaudeWatchError):
    """Data file is corrupted."""

    code = ExitCode.DATA_CORRUPT
    suggestion = (
        "The data file appears corrupted. "
        "Try deleting it and letting it regenerate."
    )


def categorize_http_error(status_code: int, reason: str = "") -> ClaudeWatchError:
    """Convert HTTP status code to appropriate error type.

    Args:
        status_code: HTTP status code.
        reason: Optional reason phrase.

    Returns:
        Appropriate ClaudeWatchError subclass instance.
    """
    message = f"API error: {status_code}"
    if reason:
        message += f" {reason}"

    if status_code == 401:
        return AuthenticationExpiredError(
            "Authentication failed. Your session may have expired."
        )
    elif status_code == 403:
        return PermissionDeniedError(
            "Access denied. You may not have permission for this operation."
        )
    elif status_code == 429:
        return RateLimitError(
            "Rate limit exceeded. Too many requests."
        )
    elif status_code == 503:
        return MaintenanceError(
            "Service temporarily unavailable."
        )
    elif status_code >= 500:
        return ServerError(
            f"Server error: {status_code} {reason}"
        )
    else:
        return APIError(message)


def categorize_network_error(error_reason: str) -> ClaudeWatchError:
    """Convert network error reason to appropriate error type.

    Args:
        error_reason: Error reason string from URLError.

    Returns:
        Appropriate ClaudeWatchError subclass instance.
    """
    reason_lower = error_reason.lower()

    if "timed out" in reason_lower or "timeout" in reason_lower:
        return NetworkTimeoutError(f"Connection timed out: {error_reason}")
    elif "name or service not known" in reason_lower or "getaddrinfo" in reason_lower:
        return NetworkDNSError(f"DNS resolution failed: {error_reason}")
    elif "proxy" in reason_lower or "tunnel" in reason_lower:
        return NetworkProxyError(f"Proxy error: {error_reason}")
    elif "connection refused" in reason_lower or "no route" in reason_lower:
        return NetworkOfflineError(f"Connection failed: {error_reason}")
    else:
        return NetworkOfflineError(f"Network error: {error_reason}")


def format_error_for_user(error: Exception, verbose: bool = False) -> str:
    """Format any exception for user display.

    Args:
        error: Exception to format.
        verbose: If True, include details and suggestions.

    Returns:
        Formatted error message string.
    """
    if isinstance(error, ClaudeWatchError):
        if verbose:
            return error.format_full()
        return f"Error: {error.message}"
    else:
        return f"Error: {error}"


def get_exit_code(error: Exception) -> int:
    """Get the exit code for an exception.

    Args:
        error: Exception to get code for.

    Returns:
        Integer exit code.
    """
    if isinstance(error, ClaudeWatchError):
        return error.code
    elif isinstance(error, FileNotFoundError):
        return ExitCode.FILE_NOT_FOUND
    elif isinstance(error, PermissionError):
        return ExitCode.FILE_PERMISSION
    elif isinstance(error, ValueError):
        return ExitCode.INVALID_ARGUMENT
    else:
        return ExitCode.SYSTEM_ERROR


__all__ = [
    # Exit codes
    "ExitCode",
    # Base error
    "ClaudeWatchError",
    # Authentication errors
    "AuthenticationExpiredError",
    "AuthenticationInvalidError",
    "AuthenticationMissingError",
    "PermissionDeniedError",
    # Network errors
    "NetworkOfflineError",
    "NetworkTimeoutError",
    "NetworkDNSError",
    "NetworkProxyError",
    # API errors
    "APIError",
    "RateLimitError",
    "ServerError",
    "MaintenanceError",
    # Config errors
    "ConfigError",
    "SetupRequiredError",
    # File errors
    "FileNotFoundError_",
    "FilePermissionError",
    "DataCorruptError",
    # Utilities
    "categorize_http_error",
    "categorize_network_error",
    "format_error_for_user",
    "get_exit_code",
]
