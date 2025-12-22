"""Health check implementation for system diagnostics.

Provides comprehensive system health verification including:
- Credential validation
- API connectivity testing
- Configuration file integrity
- Network connectivity
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from claude_watch.config.credentials import get_access_token, get_credentials_path
from claude_watch.config.security import (
    check_file_permissions,
    validate_oauth_token,
)
from claude_watch.config.settings import CONFIG_FILE
from claude_watch.display.colors import Colors
from claude_watch.errors import ExitCode
from claude_watch.history.storage import HISTORY_FILE


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    passed: bool
    message: str
    details: str | None = None
    suggestion: str | None = None


@dataclass
class HealthReport:
    """Complete health check report."""

    checks: list[HealthCheckResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    warnings: int = 0

    def add_check(self, result: HealthCheckResult) -> None:
        """Add a check result to the report."""
        self.checks.append(result)
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1

    @property
    def all_passed(self) -> bool:
        """Return True if all checks passed."""
        return self.failed == 0


def check_credentials_exist() -> HealthCheckResult:
    """Check if credentials file exists."""
    creds_path = get_credentials_path()

    if not creds_path.exists():
        return HealthCheckResult(
            name="Credentials File",
            passed=False,
            message="Credentials file not found",
            details=f"Expected at: {creds_path}",
            suggestion="Run 'claude' to authenticate with Claude Code first.",
        )

    return HealthCheckResult(
        name="Credentials File",
        passed=True,
        message="Credentials file exists",
        details=str(creds_path),
    )


def check_credentials_valid() -> HealthCheckResult:
    """Check if credentials are valid and properly formatted."""
    try:
        token = get_access_token(validate=False)

        if not token:
            return HealthCheckResult(
                name="Access Token",
                passed=False,
                message="No access token found in credentials",
                suggestion="Re-authenticate with 'claude' command.",
            )

        is_valid, error = validate_oauth_token(token)
        if not is_valid:
            return HealthCheckResult(
                name="Access Token",
                passed=False,
                message=f"Token format invalid: {error}",
                suggestion="Re-authenticate with 'claude' command.",
            )

        return HealthCheckResult(
            name="Access Token",
            passed=True,
            message="Access token is valid",
            details=f"Token: {token[:8]}...{token[-4:]}",
        )

    except FileNotFoundError as e:
        return HealthCheckResult(
            name="Access Token",
            passed=False,
            message="Cannot read credentials",
            details=str(e),
            suggestion="Run 'claude' to authenticate.",
        )
    except Exception as e:
        return HealthCheckResult(
            name="Access Token",
            passed=False,
            message=f"Error reading credentials: {e}",
            suggestion="Check credentials file format.",
        )


def check_credentials_permissions() -> HealthCheckResult:
    """Check credentials file permissions are secure."""
    creds_path = get_credentials_path()

    if not creds_path.exists():
        return HealthCheckResult(
            name="Credentials Permissions",
            passed=True,
            message="Skipped (file not found)",
        )

    is_secure, warning = check_file_permissions(creds_path)
    if not is_secure:
        return HealthCheckResult(
            name="Credentials Permissions",
            passed=False,
            message="Insecure file permissions",
            details=warning,
            suggestion="Run 'chmod 600' on the credentials file.",
        )

    return HealthCheckResult(
        name="Credentials Permissions",
        passed=True,
        message="File permissions are secure (600)",
    )


def check_api_connectivity(timeout: int = 5) -> HealthCheckResult:
    """Check API connectivity with a lightweight request."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    from claude_watch._version import __version__
    from claude_watch.api.client import API_BETA_HEADER, API_URL

    try:
        token = get_access_token(validate=False)
    except Exception:
        return HealthCheckResult(
            name="API Connectivity",
            passed=False,
            message="Cannot test API (no credentials)",
            suggestion="Fix credentials first.",
        )

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
        with urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            if status == 200:
                return HealthCheckResult(
                    name="API Connectivity",
                    passed=True,
                    message="API is reachable and responding",
                    details=f"Status: {status} OK",
                )
            return HealthCheckResult(
                name="API Connectivity",
                passed=False,
                message=f"Unexpected status: {status}",
            )
    except HTTPError as e:
        if e.code == 401:
            return HealthCheckResult(
                name="API Connectivity",
                passed=False,
                message="Authentication failed (401)",
                details="Your session may have expired.",
                suggestion="Re-authenticate with 'claude' command.",
            )
        elif e.code == 403:
            return HealthCheckResult(
                name="API Connectivity",
                passed=False,
                message="Access denied (403)",
                suggestion="Check your account permissions.",
            )
        elif e.code >= 500:
            return HealthCheckResult(
                name="API Connectivity",
                passed=False,
                message=f"Server error ({e.code})",
                suggestion="The API may be experiencing issues. Try again later.",
            )
        else:
            return HealthCheckResult(
                name="API Connectivity",
                passed=False,
                message=f"HTTP error: {e.code} {e.reason}",
            )
    except URLError as e:
        reason = str(e.reason)
        if "timed out" in reason.lower():
            return HealthCheckResult(
                name="API Connectivity",
                passed=False,
                message="Connection timed out",
                suggestion="Check your network connection or increase --timeout.",
            )
        return HealthCheckResult(
            name="API Connectivity",
            passed=False,
            message=f"Network error: {reason}",
            suggestion="Check your internet connection.",
        )
    except Exception as e:
        return HealthCheckResult(
            name="API Connectivity",
            passed=False,
            message=f"Unexpected error: {e}",
        )


def check_config_file() -> HealthCheckResult:
    """Check configuration file integrity."""
    if not CONFIG_FILE.exists():
        return HealthCheckResult(
            name="Configuration File",
            passed=True,
            message="No config file (using defaults)",
            details="This is normal for first-time setup.",
        )

    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return HealthCheckResult(
                name="Configuration File",
                passed=False,
                message="Invalid config format (not a dictionary)",
                suggestion="Run 'claude-watch --config reset' to reset.",
            )

        return HealthCheckResult(
            name="Configuration File",
            passed=True,
            message="Configuration file is valid",
            details=f"Keys: {', '.join(data.keys())}",
        )

    except json.JSONDecodeError as e:
        return HealthCheckResult(
            name="Configuration File",
            passed=False,
            message="Invalid JSON in config file",
            details=str(e),
            suggestion="Run 'claude-watch --config reset' to reset.",
        )
    except Exception as e:
        return HealthCheckResult(
            name="Configuration File",
            passed=False,
            message=f"Error reading config: {e}",
        )


def check_config_permissions() -> HealthCheckResult:
    """Check configuration file permissions."""
    if not CONFIG_FILE.exists():
        return HealthCheckResult(
            name="Config Permissions",
            passed=True,
            message="Skipped (file not found)",
        )

    is_secure, warning = check_file_permissions(CONFIG_FILE)
    if not is_secure:
        return HealthCheckResult(
            name="Config Permissions",
            passed=False,
            message="Insecure permissions",
            details=warning,
            suggestion="Run 'chmod 600' on the config file.",
        )

    return HealthCheckResult(
        name="Config Permissions",
        passed=True,
        message="File permissions are secure",
    )


def check_history_file() -> HealthCheckResult:
    """Check history file integrity."""
    if not HISTORY_FILE.exists():
        return HealthCheckResult(
            name="History File",
            passed=True,
            message="No history file (will be created on first use)",
        )

    try:
        with open(HISTORY_FILE) as f:
            data = json.load(f)

        if not isinstance(data, list):
            return HealthCheckResult(
                name="History File",
                passed=False,
                message="Invalid history format (not a list)",
                suggestion="Delete the history file to reset.",
            )

        return HealthCheckResult(
            name="History File",
            passed=True,
            message=f"History file valid ({len(data)} records)",
            details=str(HISTORY_FILE),
        )

    except json.JSONDecodeError as e:
        return HealthCheckResult(
            name="History File",
            passed=False,
            message="Invalid JSON in history file",
            details=str(e),
            suggestion=f"Delete {HISTORY_FILE} to reset.",
        )
    except Exception as e:
        return HealthCheckResult(
            name="History File",
            passed=False,
            message=f"Error reading history: {e}",
        )


def check_network_connectivity() -> HealthCheckResult:
    """Check basic network connectivity."""
    from claude_watch.api.retry import check_network_connectivity as check_net

    is_online, reason = check_net()

    if is_online:
        return HealthCheckResult(
            name="Network Connectivity",
            passed=True,
            message="Network is available",
        )

    return HealthCheckResult(
        name="Network Connectivity",
        passed=False,
        message="Network appears offline",
        details=reason,
        suggestion="Check your internet connection.",
    )


def run_health_check(
    verbose: bool = False,
    skip_api: bool = False,
    timeout: int = 5,
) -> int:
    """Run all health checks and display results.

    Args:
        verbose: Show detailed output for all checks.
        skip_api: Skip API connectivity check.
        timeout: Timeout for API check in seconds.

    Returns:
        Exit code (0 = all passed, 1 = failures).
    """
    report = HealthReport()

    # Define checks to run
    checks: list[Callable[[], HealthCheckResult]] = [
        check_credentials_exist,
        check_credentials_valid,
        check_credentials_permissions,
        check_config_file,
        check_config_permissions,
        check_history_file,
        check_network_connectivity,
    ]

    # Add API check unless skipped
    if not skip_api:
        checks.append(lambda: check_api_connectivity(timeout))

    # Print header
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Claude Watch Health Check{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print()

    # Run checks with progress
    for check_func in checks:
        try:
            result = check_func()
        except Exception as e:
            result = HealthCheckResult(
                name=check_func.__name__.replace("check_", "").replace("_", " ").title(),
                passed=False,
                message=f"Check failed: {e}",
            )

        report.add_check(result)

        # Display result
        if result.passed:
            icon = f"{Colors.GREEN}✓{Colors.RESET}"
        else:
            icon = f"{Colors.RED}✗{Colors.RESET}"

        print(f"  {icon} {result.name}: {result.message}")

        if verbose or not result.passed:
            if result.details:
                print(f"      {Colors.DIM}Details: {result.details}{Colors.RESET}")
            if result.suggestion and not result.passed:
                print(f"      {Colors.YELLOW}→ {result.suggestion}{Colors.RESET}")

    # Print summary
    print()
    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")

    if report.all_passed:
        print(
            f"{Colors.GREEN}✓ All {report.passed} checks passed{Colors.RESET}"
        )
        return ExitCode.SUCCESS
    else:
        print(
            f"{Colors.RED}✗ {report.failed} check(s) failed{Colors.RESET}, "
            f"{Colors.GREEN}{report.passed} passed{Colors.RESET}"
        )
        return ExitCode.USAGE_ERROR


__all__ = [
    "HealthCheckResult",
    "HealthReport",
    "run_health_check",
    "check_credentials_exist",
    "check_credentials_valid",
    "check_credentials_permissions",
    "check_api_connectivity",
    "check_config_file",
    "check_config_permissions",
    "check_history_file",
    "check_network_connectivity",
]
