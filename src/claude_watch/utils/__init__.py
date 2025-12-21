"""Utility functions.

Modules:
    time: Time formatting and parsing utilities
    platform: Platform detection and compatibility
"""

from claude_watch.utils.platform import detect_shell, get_script_path
from claude_watch.utils.time import (
    format_absolute_time,
    format_relative_time,
    parse_reset_time,
)

__all__ = [
    "parse_reset_time",
    "format_relative_time",
    "format_absolute_time",
    "get_script_path",
    "detect_shell",
]
