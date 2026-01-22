"""Integration modules for external tools."""

from claude_watch.integrations.statusline import (
    generate_statusline_script,
    install_statusline,
)

__all__ = [
    "install_statusline",
    "generate_statusline_script",
]
