"""Time formatting and parsing utilities.

Provides functions for handling ISO timestamps and formatting
relative/absolute time displays.
"""

from datetime import datetime, timezone


def parse_reset_time(iso_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string to datetime.

    Handles various formats including trailing Z and microseconds.

    Args:
        iso_str: ISO 8601 timestamp string (e.g., "2024-01-15T10:30:00Z").

    Returns:
        Timezone-aware datetime object.
    """
    iso_str = iso_str.replace("Z", "+00:00")
    if "." in iso_str:
        parts = iso_str.split("+")
        if len(parts) == 2:
            iso_str = parts[0].split(".")[0] + "+" + parts[1]
    return datetime.fromisoformat(iso_str)


def format_relative_time(reset_at: str) -> str:
    """Format a reset time as relative duration from now.

    Args:
        reset_at: ISO 8601 timestamp string.

    Returns:
        Human-readable string like "2 hr 30 min" or "< 1 min".
    """
    reset_dt = parse_reset_time(reset_at)
    now = datetime.now(timezone.utc)
    delta = reset_dt - now
    total_seconds = max(0, int(delta.total_seconds()))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours} hr {minutes} min"
    elif minutes > 0:
        return f"{minutes} min"
    return "< 1 min"


def format_absolute_time(reset_at: str) -> str:
    """Format a reset time as local absolute time.

    Args:
        reset_at: ISO 8601 timestamp string.

    Returns:
        Local time string like "Mon 9:30 AM".
    """
    reset_dt = parse_reset_time(reset_at)
    local_dt = reset_dt.astimezone()
    # Use %I (with padding) and strip leading zero manually for cross-platform compatibility
    # Windows doesn't support %-I, and %#I is Windows-only
    formatted = local_dt.strftime("%a %I:%M %p")
    # Remove leading zero from hour (e.g., "Mon 09:30 AM" -> "Mon 9:30 AM")
    parts = formatted.split(" ")
    if len(parts) >= 2 and parts[1].startswith("0"):
        parts[1] = parts[1][1:]
    return " ".join(parts)


__all__ = ["parse_reset_time", "format_relative_time", "format_absolute_time"]
