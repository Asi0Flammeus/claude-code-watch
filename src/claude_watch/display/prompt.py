"""Shell prompt output formatters.

Provides compact output formats for shell prompt integration (PS1, etc.).
Each format outputs a single line suitable for embedding in prompts.
"""

from claude_watch.utils.time import parse_reset_time
from datetime import datetime, timezone


def format_reset_compact(reset_at: str) -> str:
    """Format reset time as compact duration (e.g., '2h15m').

    Args:
        reset_at: ISO 8601 timestamp string.

    Returns:
        Compact duration like '2h15m', '45m', or '<1m'.
    """
    reset_dt = parse_reset_time(reset_at)
    now = datetime.now(timezone.utc)
    delta = reset_dt - now
    total_seconds = max(0, int(delta.total_seconds()))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    elif minutes > 0:
        return f"{minutes}m"
    return "<1m"


def format_prompt_default(data: dict) -> str:
    """Format usage for shell prompt - default format.

    Shows session percentage with reset time.
    Example: 'S:45% 2h15m'

    Args:
        data: Usage data dict with 'five_hour' key.

    Returns:
        Formatted string for shell prompt.
    """
    five_hour = data.get("five_hour") or {}
    utilization = five_hour.get("utilization", 0)
    resets_at = five_hour.get("resets_at", "")

    pct = int(utilization)
    reset_str = format_reset_compact(resets_at) if resets_at else ""

    if reset_str:
        return f"S:{pct}% {reset_str}"
    return f"S:{pct}%"


def format_prompt_minimal(data: dict) -> str:
    """Format usage for shell prompt - minimal format.

    Shows just the session percentage.
    Example: '45%'

    Args:
        data: Usage data dict with 'five_hour' key.

    Returns:
        Formatted percentage string.
    """
    five_hour = data.get("five_hour") or {}
    utilization = five_hour.get("utilization", 0)
    return f"{int(utilization)}%"


def format_prompt_full(data: dict) -> str:
    """Format usage for shell prompt - full format.

    Shows session and weekly percentages.
    Example: 'S:45% W:12%'

    Args:
        data: Usage data dict with 'five_hour' and 'seven_day' keys.

    Returns:
        Formatted string with session and weekly usage.
    """
    five_hour = data.get("five_hour") or {}
    seven_day = data.get("seven_day") or {}

    session_pct = int(five_hour.get("utilization", 0))
    weekly_pct = int(seven_day.get("utilization", 0))

    return f"S:{session_pct}% W:{weekly_pct}%"


def format_prompt_icon(data: dict) -> str:
    """Format usage for shell prompt - icon format.

    Shows usage with emoji indicator based on level.
    Example: '🟢45%' or '🟡75%' or '🔴95%'

    Args:
        data: Usage data dict with 'five_hour' key.

    Returns:
        Formatted string with emoji and percentage.
    """
    five_hour = data.get("five_hour") or {}
    utilization = five_hour.get("utilization", 0)
    pct = int(utilization)

    if utilization >= 90:
        icon = "🔴"
    elif utilization >= 75:
        icon = "🟡"
    else:
        icon = "🟢"

    return f"{icon}{pct}%"


def format_prompt(data: dict, fmt: str = "default") -> str:
    """Format usage data for shell prompt output.

    Args:
        data: Usage data dict from API.
        fmt: Format type - 'default', 'minimal', 'full', or 'icon'.

    Returns:
        Formatted string for shell prompt.

    Raises:
        ValueError: If format is not recognized.
    """
    formatters = {
        "default": format_prompt_default,
        "minimal": format_prompt_minimal,
        "full": format_prompt_full,
        "icon": format_prompt_icon,
    }

    if fmt not in formatters:
        raise ValueError(f"Unknown prompt format: {fmt}")

    return formatters[fmt](data)


__all__ = [
    "format_prompt",
    "format_prompt_default",
    "format_prompt_minimal",
    "format_prompt_full",
    "format_prompt_icon",
    "format_reset_compact",
]
