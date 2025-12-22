"""Integration modules for external tools."""

from claude_watch.integrations.statusline import (
    install_statusline,
    generate_statusline_script,
)

__all__ = [
    "install_statusline",
    "generate_statusline_script",
]
