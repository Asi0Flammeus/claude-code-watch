"""Display components for terminal output.

Modules:
    colors: Terminal color handling and detection
    spinner: Animated loading spinner
    progress: Progress bar rendering
    usage: Usage display formatting
    analytics: Analytics visualization
"""

from claude_watch.display.colors import Colors, init_colors, supports_color
from claude_watch.display.progress import format_percentage, get_usage_color, make_progress_bar
from claude_watch.display.spinner import Spinner
from claude_watch.display.usage import display_usage, print_usage_row

__all__ = [
    "Colors",
    "supports_color",
    "init_colors",
    "Spinner",
    "make_progress_bar",
    "get_usage_color",
    "format_percentage",
    "display_usage",
    "print_usage_row",
]
