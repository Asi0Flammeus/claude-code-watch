"""Display components for terminal output.

Modules:
    colors: Terminal color handling and detection
    spinner: Animated loading spinner
    progress: Progress bar rendering
    usage: Usage display formatting
    analytics: Analytics visualization
"""

from claude_watch.display.colors import Colors, init_colors, supports_color
from claude_watch.display.spinner import Spinner

__all__ = ["Colors", "supports_color", "init_colors", "Spinner"]
