"""Tmux status bar output formatters.

Provides output formats optimized for tmux status bar integration.
Uses tmux-style color codes (#[fg=color]) instead of ANSI escape sequences.
"""

from typing import Optional

from claude_watch.display.prompt import format_reset_compact, get_trend_indicator


def get_tmux_color(utilization: float) -> str:
    """Get tmux color code based on usage level.

    Args:
        utilization: Usage percentage (0-100).

    Returns:
        Tmux hex color code (Dracula theme compatible).
    """
    if utilization >= 90:
        return "#ff5555"  # Dracula red
    elif utilization >= 75:
        return "#f1fa8c"  # Dracula yellow
    return "#50fa7b"  # Dracula green


def format_tmux(
    data: dict,
    include_weekly: bool = True,
    include_trend: bool = True,
    history: Optional[list] = None,
) -> str:
    """Format usage data for tmux status bar.

    Output format: 'S:45% 2h15m W:12%' with tmux color codes.

    Args:
        data: Usage data dict from API.
        include_weekly: Whether to include weekly usage (default: True).
        include_trend: Whether to include trend indicator (default: True).
        history: Optional history list for trend calculation.

    Returns:
        Formatted string with tmux color codes.
    """
    five_hour = data.get("five_hour") or {}
    seven_day = data.get("seven_day") or {}

    session_pct = int(five_hour.get("utilization", 0))
    weekly_pct = int(seven_day.get("utilization", 0))
    resets_at = five_hour.get("resets_at", "")

    # Get color based on session usage
    session_color = get_tmux_color(session_pct)
    weekly_color = get_tmux_color(weekly_pct)

    # Build session part with reset time
    reset_str = format_reset_compact(resets_at) if resets_at else ""

    # Add trend indicator if requested
    trend = ""
    if include_trend:
        trend = get_trend_indicator(data, history)

    # Build output with tmux color codes
    parts = []

    # Session usage with color
    session_part = f"#[fg={session_color}]S:{session_pct}%"
    if reset_str:
        session_part += f" {reset_str}"
    if trend:
        session_part += trend
    parts.append(session_part)

    # Weekly usage with color
    if include_weekly:
        weekly_part = f"#[fg={weekly_color}]W:{weekly_pct}%"
        parts.append(weekly_part)

    # Reset color at end
    return " ".join(parts) + "#[default]"


def format_tmux_minimal(data: dict) -> str:
    """Format usage for tmux - minimal format.

    Output format: '45%' with tmux color codes.

    Args:
        data: Usage data dict with 'five_hour' key.

    Returns:
        Formatted string with tmux color codes.
    """
    five_hour = data.get("five_hour") or {}
    utilization = five_hour.get("utilization", 0)
    pct = int(utilization)
    color = get_tmux_color(utilization)

    return f"#[fg={color}]{pct}%#[default]"


__all__ = [
    "format_tmux",
    "format_tmux_minimal",
    "get_tmux_color",
]
