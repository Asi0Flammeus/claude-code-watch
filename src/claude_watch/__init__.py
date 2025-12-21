"""Claude Watch - CLI tool to monitor Claude Code subscription usage limits.

This package provides utilities for monitoring and analyzing Claude Code usage,
including API integration, configuration management, and display formatting.
"""

from claude_watch._version import __version__
from claude_watch.cli import create_parser, handle_config_command, print_version

__all__ = [
    "__version__",
    "create_parser",
    "print_version",
    "handle_config_command",
]
