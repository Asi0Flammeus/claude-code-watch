"""Credential management for claude-watch.

Provides functions for retrieving Claude Code OAuth credentials from
platform-specific locations (macOS Keychain, Windows APPDATA, Linux home).
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional


def get_credentials_path() -> Path:
    """Get the path to the credentials file based on the current platform.

    Returns:
        Path to the credentials file.

    Note:
        - Windows: %APPDATA%/.claude/.credentials.json
        - macOS/Linux: ~/.claude/.credentials.json
    """
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", "~"))
    else:
        base = Path.home()
    return base / ".claude" / ".credentials.json"


def get_macos_keychain_credentials() -> Optional[dict]:
    """Retrieve credentials from macOS Keychain.

    Returns:
        Credentials dict if found in Keychain, None otherwise.

    Note:
        This only works on macOS systems with the 'security' command.
    """
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout.strip())
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None


def get_credentials() -> dict:
    """Get Claude Code credentials from the appropriate source.

    First tries macOS Keychain on Darwin systems, then falls back to
    the credentials file.

    Returns:
        Credentials dictionary containing OAuth tokens.

    Raises:
        FileNotFoundError: If credentials file doesn't exist.
        json.JSONDecodeError: If credentials file is invalid JSON.
    """
    if platform.system() == "Darwin":
        creds = get_macos_keychain_credentials()
        if creds:
            return creds

    creds_path = get_credentials_path()
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Credentials not found at {creds_path}\n"
            "Please ensure Claude Code is installed and you've logged in."
        )

    with open(creds_path) as f:
        return json.load(f)


def get_access_token() -> str:
    """Get the OAuth access token from credentials.

    Returns:
        The access token string.

    Raises:
        FileNotFoundError: If credentials file doesn't exist.
        ValueError: If no access token found in credentials.
    """
    creds = get_credentials()
    oauth = creds.get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    if not token:
        raise ValueError("No access token found in credentials")
    return token


__all__ = [
    "get_credentials_path",
    "get_macos_keychain_credentials",
    "get_credentials",
    "get_access_token",
]
