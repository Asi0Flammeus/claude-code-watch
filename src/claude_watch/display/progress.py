"""Progress bar rendering and percentage formatting.

Provides utilities for displaying usage progress with color coding.
"""

from claude_watch.display.colors import Colors


def make_progress_bar(percentage: float, width: int = 25) -> str:
    """Create a visual progress bar with block characters.

    Args:
        percentage: Usage percentage (0-100).
        width: Width of the progress bar in characters.

    Returns:
        Colored string representation of the progress bar.
    """
    filled = int(width * percentage / 100)
    empty = width - filled
    return f"{Colors.BAR_FILL}{'█' * filled}{Colors.BAR_EMPTY}{'░' * empty}{Colors.RESET}"


def get_usage_color(percentage: float) -> str:
    """Get the appropriate color code for a usage percentage.

    Args:
        percentage: Usage percentage (0-100).

    Returns:
        ANSI color code string.
    """
    if percentage >= 80:
        return Colors.RED
    elif percentage >= 50:
        return Colors.YELLOW
    return Colors.GREEN


def format_percentage(percentage: float) -> str:
    """Format a percentage with appropriate color coding.

    Args:
        percentage: Usage percentage (0-100).

    Returns:
        Colored string like "75% used".
    """
    color = get_usage_color(percentage)
    return f"{color}{int(percentage)}% used{Colors.RESET}"


__all__ = ["make_progress_bar", "get_usage_color", "format_percentage"]
