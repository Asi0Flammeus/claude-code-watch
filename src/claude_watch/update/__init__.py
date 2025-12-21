"""Update checking and installation.

Modules:
    checker: Version comparison and update detection
"""

from claude_watch.update.checker import (
    GITHUB_RELEASES_URL,
    GITHUB_REPO,
    check_for_update,
    compare_versions,
    detect_installation_method,
    fetch_latest_version,
    parse_version,
    run_update,
    run_upgrade,
)

__all__ = [
    "GITHUB_REPO",
    "GITHUB_RELEASES_URL",
    "parse_version",
    "compare_versions",
    "detect_installation_method",
    "fetch_latest_version",
    "run_upgrade",
    "check_for_update",
    "run_update",
]
