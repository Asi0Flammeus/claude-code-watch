"""Shell prompt output formatters.

Provides compact output formats for shell prompt integration (PS1, etc.).
Each format outputs a single line suitable for embedding in prompts.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from claude_watch.utils.time import parse_reset_time


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


def calculate_trend(
    current: float,
    history: list[dict],
    lookback_minutes: int = 60,
    threshold: float = 2.0,
) -> str:
    """Calculate usage trend indicator from history.

    Compares current usage with historical value from lookback_minutes ago.

    Args:
        current: Current utilization percentage (0-100).
        history: List of history entries with 'timestamp' and 'five_hour' keys.
        lookback_minutes: How far back to look for comparison (default: 60).
        threshold: Minimum percentage point change to show trend (default: 2.0).

    Returns:
        Trend indicator: '↑' (increasing), '↓' (decreasing), or '→' (stable).
    """
    if not history:
        return "→"

    # Find entry closest to lookback_minutes ago
    now = datetime.now(timezone.utc)
    target_time = now - timedelta(minutes=lookback_minutes)

    best_entry = None
    best_diff = float("inf")

    for entry in history:
        try:
            ts = entry.get("timestamp", "")
            if not ts:
                continue
            entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            diff = abs((entry_time - target_time).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_entry = entry
        except (ValueError, TypeError):
            continue

    if best_entry is None:
        return "→"

    # Check if entry is within reasonable range (within 30 min of target)
    if best_diff > 30 * 60:
        return "→"

    historical = best_entry.get("five_hour")
    if historical is None:
        return "→"

    delta = current - historical
    if delta > threshold:
        return "↑"
    elif delta < -threshold:
        return "↓"
    return "→"


def get_trend_indicator(data: dict, history: Optional[list] = None) -> str:
    """Get trend indicator for current session usage.

    Args:
        data: Current usage data dict.
        history: Optional history list. If None, loads from storage.

    Returns:
        Trend indicator string.
    """
    if history is None:
        from claude_watch.history.storage import load_history
        history = load_history()

    five_hour = data.get("five_hour") or {}
    current = five_hour.get("utilization", 0)

    return calculate_trend(current, history)


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


def format_prompt(
    data: dict,
    fmt: str = "default",
    include_trend: bool = True,
    history: Optional[list] = None,
) -> str:
    """Format usage data for shell prompt output.

    Args:
        data: Usage data dict from API.
        fmt: Format type - 'default', 'minimal', 'full', or 'icon'.
        include_trend: Whether to include trend indicator (default: True).
        history: Optional history list for trend calculation.

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

    result = formatters[fmt](data)

    if include_trend:
        trend = get_trend_indicator(data, history)
        result = f"{result}{trend}"

    return result


__all__ = [
    "format_prompt",
    "format_prompt_default",
    "format_prompt_minimal",
    "format_prompt_full",
    "format_prompt_icon",
    "format_reset_compact",
    "calculate_trend",
    "get_trend_indicator",
]
