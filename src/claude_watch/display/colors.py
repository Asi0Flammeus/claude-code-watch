"""Terminal color handling and detection.

Provides ANSI color codes for terminal output with automatic
detection of color support.
"""

import os
import platform
import sys


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    MAGENTA = "\033[95m"
    BAR_FILL = "\033[94m"
    BAR_EMPTY = "\033[90m"
    UP = "\033[91m"
    DOWN = "\033[92m"
    FLAT = "\033[90m"


def supports_color() -> bool:
    """Check if the terminal supports color output.

    Returns:
        True if colors should be displayed, False otherwise.
    """
    # Check for CLAUDE_WATCH_NO_COLOR env var (any non-empty value disables color)
    if os.environ.get("CLAUDE_WATCH_NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if platform.system() == "Windows":
        return bool(os.environ.get("TERM") or os.environ.get("WT_SESSION"))
    return True


def init_colors() -> None:
    """Initialize colors based on terminal support.

    Disables all color codes if the terminal doesn't support colors.
    """
    if not supports_color():
        for attr in dir(Colors):
            if not attr.startswith("_"):
                setattr(Colors, attr, "")


# Auto-initialize on import
init_colors()

__all__ = ["Colors", "supports_color", "init_colors"]
