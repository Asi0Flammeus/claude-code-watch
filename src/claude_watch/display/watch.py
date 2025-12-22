"""Watch mode for live updating display.

Provides continuous monitoring with automatic refresh and delta tracking.
"""

import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from claude_watch.display.colors import Colors
from claude_watch.display.progress import format_percentage, make_progress_bar
from claude_watch.display.usage import display_usage
from claude_watch.utils.time import format_relative_time


def clear_screen() -> None:
    """Clear the terminal screen in a cross-platform way."""
    if platform.system() == "Windows":
        os.system("cls")
    else:
        # Use ANSI escape code for Unix-like systems
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def format_duration(seconds: int) -> str:
    """Format duration in seconds as human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like '1h 30m 45s' or '45s'.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def format_countdown(seconds_left: int) -> str:
    """Format countdown timer.

    Args:
        seconds_left: Seconds until next refresh.

    Returns:
        Formatted countdown string.
    """
    if seconds_left <= 0:
        return "refreshing..."
    return f"{seconds_left}s"


def calculate_delta(initial_data: dict, current_data: dict) -> Optional[float]:
    """Calculate usage delta from initial to current.

    Args:
        initial_data: Initial usage data snapshot.
        current_data: Current usage data.

    Returns:
        Delta in percentage points, or None if data is missing.
    """
    initial_five_hour = initial_data.get("five_hour") or {}
    current_five_hour = current_data.get("five_hour") or {}

    initial_util = initial_five_hour.get("utilization")
    current_util = current_five_hour.get("utilization")

    if initial_util is not None and current_util is not None:
        return current_util - initial_util
    return None


def format_delta(delta: Optional[float]) -> str:
    """Format delta value with sign and color.

    Args:
        delta: Usage change in percentage points.

    Returns:
        Formatted delta string with color.
    """
    if delta is None:
        return ""

    if delta > 0:
        return f"{Colors.RED}+{delta:.1f}%{Colors.RESET}"
    elif delta < 0:
        return f"{Colors.GREEN}{delta:.1f}%{Colors.RESET}"
    else:
        return f"{Colors.DIM}±0.0%{Colors.RESET}"


def display_current_compact(data: dict, delta: Optional[float] = None) -> None:
    """Display compact view with only current session info.

    Args:
        data: Usage data dict containing 'five_hour' key.
        delta: Optional usage delta since watch start.
    """
    five_hour = data.get("five_hour") or {}
    utilization = five_hour.get("utilization", 0)
    resets_at = five_hour.get("resets_at", "")

    bar = make_progress_bar(utilization, width=25)
    pct = format_percentage(utilization)

    reset_str = ""
    if resets_at:
        reset_str = f"Resets in {format_relative_time(resets_at)}"

    # Delta display
    delta_str = ""
    if delta is not None:
        delta_str = f" {format_delta(delta)}"

    print(f"{Colors.WHITE}Current session{Colors.RESET}  {bar}  {pct}{delta_str}")
    if reset_str:
        print(f"{Colors.DIM}{reset_str}{Colors.RESET}")


def print_watch_header_compact(
    interval: int,
    countdown: int,
) -> None:
    """Print compact watch header (single line).

    Args:
        interval: Refresh interval in seconds.
        countdown: Seconds until next refresh.
    """
    now = datetime.now(timezone.utc).astimezone()
    time_str = now.strftime("%H:%M:%S")

    print(
        f"{Colors.DIM}[{time_str}] "
        f"Refresh: {format_countdown(countdown)} | "
        f"Interval: {interval}s{Colors.RESET}"
    )


def print_watch_header(
    interval: int,
    countdown: int,
    session_duration: int,
    delta: Optional[float] = None,
) -> None:
    """Print the watch mode header with status information.

    Args:
        interval: Refresh interval in seconds.
        countdown: Seconds until next refresh.
        session_duration: Total watch session duration in seconds.
        delta: Optional usage delta since watch start.
    """
    now = datetime.now(timezone.utc).astimezone()
    time_str = now.strftime("%H:%M:%S")

    header_parts = [
        f"{Colors.BOLD}{Colors.CYAN}Claude Watch{Colors.RESET}",
        f"{Colors.DIM}|{Colors.RESET}",
        f"Refresh: {format_countdown(countdown)}",
        f"{Colors.DIM}|{Colors.RESET}",
        f"Interval: {interval}s",
        f"{Colors.DIM}|{Colors.RESET}",
        f"Session: {format_duration(session_duration)}",
    ]

    if delta is not None:
        header_parts.extend([
            f"{Colors.DIM}|{Colors.RESET}",
            f"Delta: {format_delta(delta)}",
        ])

    header_parts.extend([
        f"{Colors.DIM}|{Colors.RESET}",
        f"{Colors.DIM}{time_str}{Colors.RESET}",
    ])

    print(" ".join(header_parts))
    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")


def print_watch_summary(
    session_duration: int,
    refresh_count: int,
    initial_data: Optional[dict],
    final_data: Optional[dict],
) -> None:
    """Print summary when exiting watch mode.

    Args:
        session_duration: Total session duration in seconds.
        refresh_count: Number of refreshes performed.
        initial_data: Initial usage data at watch start.
        final_data: Final usage data at watch end.
    """
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Watch Session Summary{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
    print(f"Duration: {format_duration(session_duration)}")
    print(f"Refreshes: {refresh_count}")

    if initial_data and final_data:
        delta = calculate_delta(initial_data, final_data)
        if delta is not None:
            print(f"Usage change: {format_delta(delta)}")

    print()


def run_watch_mode(
    fetch_func,
    display_func,
    interval: int = 30,
    analytics_mode: bool = False,
    history_func=None,
    config: Optional[dict] = None,
    current_only: bool = False,
) -> None:
    """Run the watch mode loop.

    Args:
        fetch_func: Function to fetch usage data.
        display_func: Function to display usage data.
        interval: Refresh interval in seconds (10-300).
        analytics_mode: If True, show analytics view.
        history_func: Optional function to load history (for analytics).
        config: Optional config dict (for analytics).
        current_only: If True, show compact current-session-only view.
    """
    # Validate interval
    interval = max(10, min(300, interval))

    start_time = time.time()
    refresh_count = 0
    initial_data = None
    current_data = None

    try:
        while True:
            loop_start = time.time()
            session_duration = int(loop_start - start_time)

            # Fetch data
            try:
                current_data = fetch_func()
                if initial_data is None:
                    initial_data = current_data
                refresh_count += 1
            except Exception as e:
                clear_screen()
                print(f"{Colors.RED}Error fetching data: {e}{Colors.RESET}")
                time.sleep(interval)
                continue

            # Calculate delta
            delta = None
            if initial_data and current_data:
                delta = calculate_delta(initial_data, current_data)

            # Display
            for countdown in range(interval, -1, -1):
                clear_screen()

                if current_only:
                    # Compact mode: minimal header + current session only
                    print_watch_header_compact(interval, countdown)
                    display_current_compact(current_data, delta)
                elif analytics_mode and history_func:
                    # Full analytics mode
                    print_watch_header(interval, countdown, session_duration + (interval - countdown), delta)
                    print()
                    from claude_watch.display.analytics import display_analytics
                    display_func(current_data)
                    history = history_func()
                    display_analytics(current_data, history, config or {})
                else:
                    # Normal mode
                    print_watch_header(interval, countdown, session_duration + (interval - countdown), delta)
                    print()
                    display_func(current_data)

                if countdown > 0:
                    time.sleep(1)

    except KeyboardInterrupt:
        session_duration = int(time.time() - start_time)
        clear_screen()
        print_watch_summary(session_duration, refresh_count, initial_data, current_data)


__all__ = [
    "clear_screen",
    "format_duration",
    "format_countdown",
    "calculate_delta",
    "format_delta",
    "display_current_compact",
    "print_watch_header_compact",
    "print_watch_header",
    "print_watch_summary",
    "run_watch_mode",
]
