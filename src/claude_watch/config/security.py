"""Security utilities for credential validation and protection."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

# Token format patterns
# OAuth access tokens from Claude Code
OAUTH_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,}$")

# Admin API keys (Anthropic API keys)
API_KEY_PATTERN = re.compile(r"^sk-ant-[a-zA-Z0-9_-]{20,}$")


def validate_oauth_token(token: str) -> tuple[bool, str | None]:
    """Validate OAuth access token format.

    Args:
        token: Token string to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not token:
        return False, "Token is empty"

    if len(token) < 20:
        return False, "Token is too short (minimum 20 characters)"

    if not OAUTH_TOKEN_PATTERN.match(token):
        return False, "Token contains invalid characters"

    return True, None


def validate_api_key(api_key: str) -> tuple[bool, str | None]:
    """Validate Anthropic API key format.

    Args:
        api_key: API key string to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not api_key:
        return False, "API key is empty"

    if not api_key.startswith("sk-ant-"):
        return False, "API key must start with 'sk-ant-'"

    if not API_KEY_PATTERN.match(api_key):
        return False, "API key format is invalid"

    return True, None


def mask_token(token: str, prefix_len: int = 8, suffix_len: int = 4) -> str:
    """Mask a token for safe logging/display.

    Args:
        token: Token to mask.
        prefix_len: Number of prefix characters to show.
        suffix_len: Number of suffix characters to show.

    Returns:
        Masked token string (e.g., "sk-ant-xx...yyyy").
    """
    if not token:
        return "<empty>"

    if len(token) <= prefix_len + suffix_len:
        return "*" * len(token)

    return f"{token[:prefix_len]}...{token[-suffix_len:]}"


def check_file_permissions(path: Path) -> tuple[bool, str | None]:
    """Check if file has secure permissions (0600 or stricter).

    Args:
        path: Path to the file.

    Returns:
        Tuple of (is_secure, warning_message).
    """
    if not path.exists():
        return True, None  # File doesn't exist yet, will be created securely

    try:
        mode = path.stat().st_mode
        # Check if group or other have any permissions
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            current_perms = oct(mode)[-3:]
            return False, f"File {path} has insecure permissions ({current_perms}), should be 600"
        return True, None
    except OSError as e:
        return False, f"Cannot check permissions for {path}: {e}"


def fix_file_permissions(path: Path) -> tuple[bool, str | None]:
    """Fix file permissions to 0600.

    Args:
        path: Path to the file.

    Returns:
        Tuple of (success, error_message).
    """
    if not path.exists():
        return True, None

    try:
        os.chmod(path, 0o600)
        return True, None
    except OSError as e:
        return False, f"Cannot fix permissions for {path}: {e}"


def check_credentials_security(
    credentials_path: Path,
    config_path: Path,
    auto_fix: bool = True,
) -> list[str]:
    """Check security of credential and config files.

    Args:
        credentials_path: Path to credentials file.
        config_path: Path to config file.
        auto_fix: If True, attempt to fix insecure permissions.

    Returns:
        List of warning messages. Empty if all secure.
    """
    warnings = []

    for path in [credentials_path, config_path]:
        is_secure, warning = check_file_permissions(path)
        if not is_secure:
            if auto_fix:
                success, fix_error = fix_file_permissions(path)
                if success:
                    warnings.append(f"Fixed insecure permissions on {path}")
                else:
                    warnings.append(f"{warning}. Auto-fix failed: {fix_error}")
            else:
                warnings.append(warning or "")

    return warnings


def validate_credentials_on_startup(
    credentials_path: Path,
    config_path: Path,
    check_permissions: bool = True,
    auto_fix_permissions: bool = True,
) -> tuple[bool, list[str]]:
    """Validate credentials and security on startup.

    Args:
        credentials_path: Path to credentials file.
        config_path: Path to config file.
        check_permissions: If True, check file permissions.
        auto_fix_permissions: If True, auto-fix insecure permissions.

    Returns:
        Tuple of (is_valid, list_of_warnings).
    """
    warnings = []
    is_valid = True

    # Check credentials file exists
    if not credentials_path.exists():
        warnings.append(
            f"Credentials file not found: {credentials_path}. "
            "Run 'claude' to authenticate with Claude Code first."
        )
        is_valid = False

    # Check file permissions
    if check_permissions:
        perm_warnings = check_credentials_security(
            credentials_path,
            config_path,
            auto_fix=auto_fix_permissions,
        )
        warnings.extend(perm_warnings)

    return is_valid, warnings


__all__ = [
    "OAUTH_TOKEN_PATTERN",
    "API_KEY_PATTERN",
    "validate_oauth_token",
    "validate_api_key",
    "mask_token",
    "check_file_permissions",
    "fix_file_permissions",
    "check_credentials_security",
    "validate_credentials_on_startup",
]
