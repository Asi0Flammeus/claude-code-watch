"""Usage forecasting with projections and recommendations."""

import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from claude_watch.display.analytics import get_period_stats
from claude_watch.display.colors import Colors


def calculate_hourly_rate(history: list, hours: int = 4) -> Optional[dict]:
    """Calculate usage rate per hour from recent history.

    Args:
        history: List of history entries.
        hours: Number of hours to analyze (default: 4).

    Returns:
        Dict with rate info or None if insufficient data.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    filtered = [
        h
        for h in history
        if h.get("timestamp", "") > cutoff_str and h.get("five_hour") is not None
    ]

    if len(filtered) < 2:
        return None

    filtered.sort(key=lambda x: x["timestamp"])

    first_ts = datetime.fromisoformat(filtered[0]["timestamp"].replace("Z", "+00:00"))
    last_ts = datetime.fromisoformat(filtered[-1]["timestamp"].replace("Z", "+00:00"))
    hours_elapsed = (last_ts - first_ts).total_seconds() / 3600

    if hours_elapsed < 0.1:
        return None

    first_val = filtered[0]["five_hour"]
    last_val = filtered[-1]["five_hour"]
    change = last_val - first_val

    rate_per_hour = change / hours_elapsed if hours_elapsed > 0 else 0

    rates = []
    for i in range(1, len(filtered)):
        prev_ts = datetime.fromisoformat(
            filtered[i - 1]["timestamp"].replace("Z", "+00:00")
        )
        curr_ts = datetime.fromisoformat(filtered[i]["timestamp"].replace("Z", "+00:00"))
        h_diff = (curr_ts - prev_ts).total_seconds() / 3600
        if h_diff > 0.05:
            val_diff = filtered[i]["five_hour"] - filtered[i - 1]["five_hour"]
            rates.append(val_diff / h_diff)

    if rates:
        rate_std = statistics.stdev(rates) if len(rates) > 1 else 0
    else:
        rate_std = 0

    return {
        "rate_per_hour": rate_per_hour,
        "rate_std": rate_std,
        "hours_analyzed": hours_elapsed,
        "data_points": len(filtered),
    }


def calculate_forecast(data: dict, history: list, config: dict) -> dict:
    """Calculate usage forecast with projections.

    Args:
        data: Current usage data.
        history: Historical usage data.
        config: User configuration.

    Returns:
        Dict with forecast data.
    """
    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)

    session_remaining = 100 - five_hour
    weekly_remaining = 100 - seven_day

    forecast = {
        "current": {
            "session_used": five_hour,
            "session_remaining": session_remaining,
            "weekly_used": seven_day,
            "weekly_remaining": weekly_remaining,
        },
        "session": {},
        "weekly": {},
        "recommendations": [],
    }

    rate_info = calculate_hourly_rate(history, hours=4)
    if rate_info and rate_info["rate_per_hour"] > 0:
        rate = rate_info["rate_per_hour"]
        rate_std = rate_info["rate_std"]

        hours_to_limit = session_remaining / rate if rate > 0 else float("inf")

        conservative_rate = rate + rate_std
        hours_conservative = (
            session_remaining / conservative_rate if conservative_rate > 0 else float("inf")
        )

        optimistic_rate = max(0.1, rate - rate_std)
        hours_optimistic = (
            session_remaining / optimistic_rate if optimistic_rate > 0 else float("inf")
        )

        forecast["session"] = {
            "rate_per_hour": round(rate, 2),
            "hours_to_limit": round(hours_to_limit, 1) if hours_to_limit < 100 else None,
            "hours_conservative": (
                round(hours_conservative, 1) if hours_conservative < 100 else None
            ),
            "hours_optimistic": (
                round(hours_optimistic, 1) if hours_optimistic < 100 else None
            ),
            "data_quality": "good" if rate_info["data_points"] >= 5 else "limited",
        }

        if hours_to_limit < 1:
            forecast["recommendations"].append(
                {
                    "severity": "critical",
                    "message": "Session limit imminent - consider pausing or reducing usage",
                }
            )
        elif hours_to_limit < 2:
            forecast["recommendations"].append(
                {
                    "severity": "warning",
                    "message": f"Session limit approaching in ~{hours_to_limit:.0f}h - plan accordingly",
                }
            )

    stats_24h = get_period_stats(history, 24, "seven_day")
    if stats_24h["count"] >= 2:
        daily_change = stats_24h["max"] - stats_24h["min"]
        if daily_change > 0:
            days_to_limit = weekly_remaining / daily_change
            weekly_projection = seven_day + (daily_change * 7)

            forecast["weekly"] = {
                "daily_rate": round(daily_change, 1),
                "days_to_limit": round(days_to_limit, 1) if days_to_limit < 30 else None,
                "weekly_projection": round(min(100, weekly_projection), 1),
                "on_track": weekly_projection <= 85,
            }

            if weekly_projection > 95:
                forecast["recommendations"].append(
                    {
                        "severity": "warning",
                        "message": f"Weekly usage trending high - projected to hit {weekly_projection:.0f}%",
                    }
                )
            elif weekly_projection <= 60:
                forecast["recommendations"].append(
                    {
                        "severity": "info",
                        "message": "Weekly usage is efficient - plenty of capacity remaining",
                    }
                )

    if five_hour >= 90:
        forecast["recommendations"].append(
            {
                "severity": "critical",
                "message": "Session limit nearly reached - wait for reset or reduce intensity",
            }
        )
    elif five_hour >= 75:
        forecast["recommendations"].append(
            {
                "severity": "warning",
                "message": "High session usage - consider pacing your requests",
            }
        )

    if seven_day >= 85:
        forecast["recommendations"].append(
            {
                "severity": "warning",
                "message": "Weekly limit approaching - prioritize critical tasks",
            }
        )

    if not forecast["recommendations"]:
        forecast["recommendations"].append(
            {"severity": "info", "message": "Usage is within healthy limits"}
        )

    return forecast


def display_forecast(data: dict, history: list, config: dict) -> None:
    """Display usage forecast with projections and recommendations."""
    forecast = calculate_forecast(data, history, config)

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}═══ Usage Forecast ═══{Colors.RESET}")
    print()

    current = forecast["current"]
    print(f"{Colors.BOLD}{Colors.WHITE}Current Status{Colors.RESET}")
    print()
    print(
        f"  Session:  {current['session_used']:.0f}% used, "
        f"{Colors.GREEN}{current['session_remaining']:.0f}%{Colors.RESET} remaining"
    )
    print(
        f"  Weekly:   {current['weekly_used']:.0f}% used, "
        f"{Colors.GREEN}{current['weekly_remaining']:.0f}%{Colors.RESET} remaining"
    )
    print()

    session = forecast.get("session", {})
    if session:
        print(f"{Colors.BOLD}{Colors.WHITE}Session Projections{Colors.RESET}")
        print()
        rate = session.get("rate_per_hour", 0)
        if rate > 0:
            print(f"  Current rate:    {Colors.YELLOW}{rate:.1f}%/hour{Colors.RESET}")

            hours_to_limit = session.get("hours_to_limit")
            if hours_to_limit:
                hours_conservative = session.get("hours_conservative")
                hours_optimistic = session.get("hours_optimistic")

                if hours_to_limit < 1:
                    color = Colors.RED
                elif hours_to_limit < 3:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN

                print(
                    f"  Time to limit:   {color}{hours_to_limit:.1f}h{Colors.RESET}",
                    end="",
                )
                if hours_conservative and hours_optimistic:
                    print(f" (range: {hours_conservative:.1f}h - {hours_optimistic:.1f}h)")
                else:
                    print()
            else:
                print(
                    f"  Time to limit:   {Colors.GREEN}Not projected to hit limit{Colors.RESET}"
                )

            quality = session.get("data_quality", "unknown")
            quality_icon = "+" if quality == "good" else "o"
            print(f"  Data quality:    {quality_icon} {quality}")
        print()

    weekly = forecast.get("weekly", {})
    if weekly:
        print(f"{Colors.BOLD}{Colors.WHITE}Weekly Projections{Colors.RESET}")
        print()
        daily_rate = weekly.get("daily_rate", 0)
        if daily_rate > 0:
            print(f"  Daily rate:      {Colors.YELLOW}{daily_rate:.1f}%/day{Colors.RESET}")

            projection = weekly.get("weekly_projection", 0)
            on_track = weekly.get("on_track", True)
            proj_color = Colors.GREEN if on_track else Colors.YELLOW
            print(f"  7-day projection: {proj_color}{projection:.0f}%{Colors.RESET}")

            days_to_limit = weekly.get("days_to_limit")
            if days_to_limit:
                print(
                    f"  Days to limit:   {Colors.YELLOW}{days_to_limit:.1f} days{Colors.RESET}"
                )
        print()

    recommendations = forecast.get("recommendations", [])
    if recommendations:
        print(f"{Colors.BOLD}{Colors.WHITE}Recommendations{Colors.RESET}")
        print()
        for rec in recommendations:
            severity = rec.get("severity", "info")
            message = rec.get("message", "")

            if severity == "critical":
                icon = f"{Colors.RED}!{Colors.RESET}"
            elif severity == "warning":
                icon = f"{Colors.YELLOW}*{Colors.RESET}"
            else:
                icon = f"{Colors.GREEN}+{Colors.RESET}"

            print(f"  {icon} {message}")
        print()


def display_forecast_json(data: dict, history: list, config: dict) -> None:
    """Output forecast as JSON."""
    forecast = calculate_forecast(data, history, config)
    print(json.dumps(forecast, indent=2))
