"""Usage display formatting for terminal output.

Provides functions for displaying API usage information with
progress bars, percentages, and reset time formatting.
"""

from typing import Optional

from claude_watch.display.colors import Colors
from claude_watch.display.progress import format_percentage, make_progress_bar
from claude_watch.utils.time import format_absolute_time, format_relative_time


def print_usage_row(label: str, data: Optional[dict], use_relative_time: bool = False) -> None:
    """Print a single usage row with progress bar and percentage.

    Args:
        label: The label for this usage row (e.g., "Current session").
        data: Dict with 'utilization' (float) and 'resets_at' (str) keys.
        use_relative_time: If True, show relative time (e.g., "2 hr 30 min"),
            otherwise show absolute time (e.g., "Mon 9:30 AM").
    """
    if data is None:
        return

    utilization = data.get("utilization", 0)
    resets_at = data.get("resets_at", "")

    bar = make_progress_bar(utilization)
    pct = format_percentage(utilization)

    if resets_at:
        if use_relative_time:
            reset_str = f"Resets in {format_relative_time(resets_at)}"
        else:
            reset_str = f"Resets {format_absolute_time(resets_at)}"
    else:
        reset_str = ""

    print(f"{Colors.WHITE}{label:<20}{Colors.RESET} {bar}  {pct}")
    if reset_str:
        print(f"{Colors.DIM}{reset_str}{Colors.RESET}")
    print()


def display_usage(data: dict) -> None:
    """Display complete usage information for all models.

    Args:
        data: Usage data dict containing 'five_hour', 'seven_day',
            'seven_day_sonnet', 'seven_day_opus', and 'extra_usage' keys.
    """
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Plan usage limits{Colors.RESET}")
    print()

    if data.get("five_hour"):
        print_usage_row("Current session", data["five_hour"], use_relative_time=True)

    print(f"{Colors.BOLD}{Colors.WHITE}Weekly limits{Colors.RESET}")
    print()

    if data.get("seven_day"):
        print_usage_row("All models", data["seven_day"])

    if data.get("seven_day_sonnet"):
        print_usage_row("Sonnet only", data["seven_day_sonnet"])

    if data.get("seven_day_opus"):
        print_usage_row("Opus only", data["seven_day_opus"])

    extra = data.get("extra_usage", {})
    if extra.get("is_enabled"):
        print(f"{Colors.BOLD}{Colors.WHITE}Extra usage{Colors.RESET}")
        print()
        if extra.get("utilization") is not None:
            print_usage_row(
                "Extra credits", {"utilization": extra["utilization"], "resets_at": None}
            )

    print(f"{Colors.DIM}Last updated: just now{Colors.RESET}")
    print()


__all__ = ["print_usage_row", "display_usage"]
