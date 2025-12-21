"""Platform detection and compatibility utilities.

Provides functions for detecting the current shell and script location.
"""

import os
import subprocess
import sys
from pathlib import Path


def get_script_path() -> str:
    """Get the path to the currently running script.

    Resolves symlinks and falls back to using `which` if needed.

    Returns:
        Absolute path to the script.
    """
    # Check if running from symlink
    script = Path(sys.argv[0]).resolve()
    if script.exists():
        return str(script)
    # Fallback to which
    result = subprocess.run(
        ["which", "claude-watch"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return str(Path(__file__).resolve())


def detect_shell() -> str:
    """Detect the user's default shell.

    Checks environment variables to determine the current shell.

    Returns:
        Shell name: "zsh", "fish", or "bash" (default).
    """
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "fish" in shell:
        return "fish"
    elif "bash" in shell:
        return "bash"
    # Fallback: check if running in a known shell
    if os.environ.get("ZSH_VERSION"):
        return "zsh"
    if os.environ.get("FISH_VERSION"):
        return "fish"
    if os.environ.get("BASH_VERSION"):
        return "bash"
    return "bash"  # Default to bash


__all__ = ["get_script_path", "detect_shell"]
