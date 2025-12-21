"""Analytics display and visualization for terminal output.

Provides functions for displaying usage trends, sparklines, statistics,
and subscription cost analysis.
"""

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union

from claude_watch.display.colors import Colors

# Default constants (can be overridden by passing config)
HISTORY_FILE = Path.home() / ".claude" / ".usage_history.json"

SUBSCRIPTION_PLANS = {
    "pro": {
        "name": "Pro",
        "cost": 20.00,
        "messages_5h": 45,
        "weekly_sonnet_hours": 60,
        "weekly_opus_hours": 0,
    },
    "max_5x": {
        "name": "Max 5x",
        "cost": 100.00,
        "messages_5h": 225,
        "weekly_sonnet_hours": 210,
        "weekly_opus_hours": 25,
    },
    "max_20x": {
        "name": "Max 20x",
        "cost": 200.00,
        "messages_5h": 900,
        "weekly_sonnet_hours": 360,
        "weekly_opus_hours": 32,
    },
}

API_PRICING = {
    "claude-sonnet-4-5-20250929": (3.00, 15.00, 0.30),
    "claude-sonnet-4-20250514": (3.00, 15.00, 0.30),
    "claude-opus-4-5-20251101": (15.00, 75.00, 1.50),
    "claude-opus-4-20250514": (15.00, 75.00, 1.50),
    "claude-haiku-4-5-20251101": (1.00, 5.00, 0.10),
    "claude-3-5-sonnet-20241022": (3.00, 15.00, 0.30),
    "claude-3-5-haiku-20241022": (1.00, 5.00, 0.10),
    "claude-3-haiku-20240307": (0.25, 1.25, 0.03),
    "default": (3.00, 15.00, 0.30),
}


def make_sparkline(
    values: list,
    timestamps: Optional[list] = None,
    width: int = 20,
    period_hours: int = 24,
) -> Union[str, tuple]:
    """Generate sparkline with optional time axis labels.

    Args:
        values: Data values for sparkline.
        timestamps: Optional list of ISO timestamps for time axis.
        width: Max width of sparkline in characters.
        period_hours: The period this data represents (24=day, 168=week)
            - controls date vs time format.

    Returns:
        If timestamps provided: tuple of (sparkline_str, time_axis_str)
        Otherwise: just the sparkline string
    """
    if not values:
        empty = "─" * width
        return (
            (f"{Colors.CYAN}{empty}{Colors.RESET}", "")
            if timestamps
            else f"{Colors.CYAN}{empty}{Colors.RESET}"
        )

    chars = "▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val > min_val else 1

    # Downsample if needed, keeping track of bin timestamps
    bin_times = []
    if len(values) > width:
        step = len(values) / width
        sampled_values = []
        for i in range(width):
            idx = int(i * step)
            sampled_values.append(values[idx])
            if timestamps:
                bin_times.append(timestamps[idx])
        values = sampled_values
    elif timestamps:
        bin_times = timestamps[:]

    # Generate sparkline
    sparkline = ""
    for v in values:
        idx = int((v - min_val) / range_val * (len(chars) - 1))
        sparkline += chars[idx]

    if not timestamps:
        return f"{Colors.CYAN}{sparkline}{Colors.RESET}"

    # Generate time axis - show labels at start, middle, and end
    num_bins = len(values)
    time_axis = ""

    if bin_times and num_bins >= 2:
        try:
            first_dt = datetime.fromisoformat(bin_times[0].replace("Z", "+00:00")).astimezone()
            last_dt = datetime.fromisoformat(bin_times[-1].replace("Z", "+00:00")).astimezone()

            # Use format based on intended period (not actual data span)
            if period_hours <= 48:  # 24h or 48h view - show time
                first_label = first_dt.strftime("%-H:%M")
                last_label = last_dt.strftime("%-H:%M")
            else:  # 7d or longer view - show date
                first_label = first_dt.strftime("%d/%m")
                last_label = last_dt.strftime("%d/%m")

            # Build axis: first_label padded to sparkline width, then last_label
            padding = num_bins - len(first_label) - len(last_label)
            if padding > 0:
                time_axis = first_label + " " * padding + last_label
            else:
                time_axis = first_label + "→" + last_label

        except (ValueError, AttributeError):
            pass

    return (f"{Colors.CYAN}{sparkline}{Colors.RESET}", f"{Colors.DIM}{time_axis}{Colors.RESET}")


def format_trend(current: float, previous: Optional[float]) -> str:
    """Format a trend indicator comparing current to previous value.

    Args:
        current: Current value.
        previous: Previous value for comparison.

    Returns:
        Colored trend string with arrow and percentage change.
    """
    if previous is None or previous == 0:
        return ""

    change = current - previous
    pct_change = (change / previous) * 100 if previous != 0 else 0

    if change > 0:
        arrow, color = "↑", Colors.UP
    elif change < 0:
        arrow, color = "↓", Colors.DOWN
        pct_change = abs(pct_change)
    else:
        arrow, color = "→", Colors.FLAT

    return f"{color}{arrow} {pct_change:.1f}%{Colors.RESET}"


def get_period_stats(history: list, hours: int, field: str) -> dict:
    """Calculate statistics for a time period.

    Args:
        history: List of history records with 'timestamp' and field values.
        hours: Number of hours to look back.
        field: The field name to analyze (e.g., 'five_hour', 'seven_day').

    Returns:
        Dict with 'count', 'min', 'max', 'avg', 'current', 'values', 'timestamps'.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    filtered = [
        h for h in history if h.get("timestamp", "") > cutoff_str and h.get(field) is not None
    ]
    values = [h[field] for h in filtered]
    timestamps = [h["timestamp"] for h in filtered]

    if not values:
        return {"count": 0}

    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": statistics.mean(values),
        "current": values[-1] if values else None,
        "values": values,
        "timestamps": timestamps,
    }


def get_daily_peaks(history: list, field: str) -> dict:
    """Analyze history to find peak usage patterns.

    Args:
        history: List of history records.
        field: The field name to analyze.

    Returns:
        Dict with 'peak_day', 'peak_day_avg', 'peak_hour', 'peak_hour_avg'.
    """
    by_dow = defaultdict(list)
    by_hour = defaultdict(list)

    for h in history:
        if h.get(field) is None:
            continue
        try:
            dt = datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            by_dow[local_dt.strftime("%a")].append(h[field])
            by_hour[local_dt.hour].append(h[field])
        except (ValueError, KeyError):
            continue

    peak_day, peak_day_avg = None, 0
    for day, vals in by_dow.items():
        avg = statistics.mean(vals) if vals else 0
        if avg > peak_day_avg:
            peak_day, peak_day_avg = day, avg

    peak_hour, peak_hour_avg = None, 0
    for hour, vals in by_hour.items():
        avg = statistics.mean(vals) if vals else 0
        if avg > peak_hour_avg:
            peak_hour, peak_hour_avg = hour, avg

    return {
        "peak_day": peak_day,
        "peak_day_avg": peak_day_avg,
        "peak_hour": peak_hour,
        "peak_hour_avg": peak_hour_avg,
    }


def calculate_token_cost(
    input_tok: int,
    output_tok: int,
    cache_tok: int,
    model: str = "default",
    pricing: Optional[dict] = None,
) -> float:
    """Calculate API cost for given token counts.

    Args:
        input_tok: Number of input tokens.
        output_tok: Number of output tokens.
        cache_tok: Number of cache read tokens.
        model: Model identifier for pricing lookup.
        pricing: Optional custom pricing dict (defaults to API_PRICING).

    Returns:
        Total cost in dollars.
    """
    if pricing is None:
        pricing = API_PRICING
    model_pricing = pricing.get(model, pricing.get("default", (3.00, 15.00, 0.30)))
    input_cost = (input_tok / 1_000_000) * model_pricing[0]
    output_cost = (output_tok / 1_000_000) * model_pricing[1]
    cache_cost = (cache_tok / 1_000_000) * model_pricing[2]
    return input_cost + output_cost + cache_cost


def display_admin_usage(
    admin_data: list,
    config: dict,
    subscription_plans: Optional[dict] = None,
) -> None:
    """Display usage data from Admin API with cost analysis.

    Args:
        admin_data: List of usage buckets from Admin API.
        config: Configuration dict with 'subscription_plan' key.
        subscription_plans: Optional custom plans dict.
    """
    if subscription_plans is None:
        subscription_plans = SUBSCRIPTION_PLANS

    if not admin_data:
        print(f"{Colors.DIM}No usage data from Admin API{Colors.RESET}")
        return

    plan_key = config.get("subscription_plan", "pro")
    plan_info = subscription_plans.get(plan_key, subscription_plans["pro"])
    monthly_sub_cost = plan_info["cost"]
    daily_sub_cost = monthly_sub_cost / 30
    weekly_sub_cost = monthly_sub_cost / 4

    print()
    print(f"{Colors.BOLD}{Colors.MAGENTA}═══ Organization Usage (Admin API) ═══{Colors.RESET}")
    print(f"{Colors.DIM}Your plan: {plan_info['name']} (${monthly_sub_cost:.0f}/mo){Colors.RESET}")
    print()

    # Aggregate by day, week, month with model breakdown
    by_day = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0}))
    by_week = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0}))
    by_month = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0}))

    for bucket in admin_data:
        date_str = bucket.get("starting_at", "")[:10]
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            week_key = dt.strftime("%Y-W%W")
            month_key = dt.strftime("%Y-%m")
        except ValueError:
            week_key = "unknown"
            month_key = "unknown"

        for result in bucket.get("results", []):
            input_tok = result.get("uncached_input_tokens", 0)
            output_tok = result.get("output_tokens", 0)
            cache_tok = result.get("cache_read_input_tokens", 0)
            model = result.get("model", "default")

            by_day[date_str][model]["input"] += input_tok
            by_day[date_str][model]["output"] += output_tok
            by_day[date_str][model]["cache_read"] += cache_tok

            by_week[week_key][model]["input"] += input_tok
            by_week[week_key][model]["output"] += output_tok
            by_week[week_key][model]["cache_read"] += cache_tok

            by_month[month_key][model]["input"] += input_tok
            by_month[month_key][model]["output"] += output_tok
            by_month[month_key][model]["cache_read"] += cache_tok

    def calc_period_cost(period_data: dict) -> float:
        """Calculate total cost for a period across all models."""
        total = 0.0
        for model, usage in period_data.items():
            total += calculate_token_cost(
                usage["input"], usage["output"], usage["cache_read"], model
            )
        return total

    def calc_period_tokens(period_data: dict) -> tuple:
        """Calculate total tokens for a period."""
        inp, out, cache = 0, 0, 0
        for usage in period_data.values():
            inp += usage["input"]
            out += usage["output"]
            cache += usage["cache_read"]
        return inp, out, cache

    def cost_indicator(api_cost: float, sub_cost: float) -> str:
        """Return colored indicator comparing API vs subscription cost."""
        if api_cost <= 0:
            return f"{Colors.DIM}--{Colors.RESET}"
        if api_cost < sub_cost * 0.5:
            return f"{Colors.GREEN}${api_cost:>6.2f}{Colors.RESET}"
        elif api_cost < sub_cost:
            return f"{Colors.CYAN}${api_cost:>6.2f}{Colors.RESET}"
        elif api_cost < sub_cost * 1.5:
            return f"{Colors.YELLOW}${api_cost:>6.2f}{Colors.RESET}"
        else:
            return f"{Colors.RED}${api_cost:>6.2f}{Colors.RESET}"

    # Daily Usage
    print(f"{Colors.BOLD}Daily Token Usage (Last 7 Days){Colors.RESET}")
    print(f"{Colors.DIM}Pro-rated subscription: ${daily_sub_cost:.2f}/day{Colors.RESET}")
    print()
    print(f"  {'Date':<12} {'Input':>10} {'Output':>10} {'API Cost':>10} {'vs Sub':>8}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

    daily_costs = []
    for date in sorted(by_day.keys(), reverse=True)[:7]:
        inp, out, cache = calc_period_tokens(by_day[date])
        cost = calc_period_cost(by_day[date])
        daily_costs.append(cost)
        diff = cost - daily_sub_cost
        if diff > 0:
            vs_sub = f"{Colors.RED}+${diff:.2f}{Colors.RESET}"
        elif diff < 0:
            vs_sub = f"{Colors.GREEN}-${-diff:.2f}{Colors.RESET}"
        else:
            vs_sub = f"{Colors.DIM}=$0.00{Colors.RESET}"
        print(f"  {date:<12} {inp:>10,} {out:>10,} {cost_indicator(cost, daily_sub_cost)} {vs_sub}")

    print()

    # Weekly Usage
    if by_week:
        print(f"{Colors.BOLD}Weekly Token Usage (Last 4 Weeks){Colors.RESET}")
        print(f"{Colors.DIM}Pro-rated subscription: ${weekly_sub_cost:.2f}/week{Colors.RESET}")
        print()
        print(f"  {'Week':<12} {'Input':>10} {'Output':>10} {'API Cost':>10} {'vs Sub':>8}")
        print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

        for week in sorted(by_week.keys(), reverse=True)[:4]:
            inp, out, cache = calc_period_tokens(by_week[week])
            cost = calc_period_cost(by_week[week])
            diff = cost - weekly_sub_cost
            if diff > 0:
                vs_sub = f"{Colors.RED}+${diff:.2f}{Colors.RESET}"
            elif diff < 0:
                vs_sub = f"{Colors.GREEN}-${-diff:.2f}{Colors.RESET}"
            else:
                vs_sub = f"{Colors.DIM}=$0.00{Colors.RESET}"
            print(
                f"  {week:<12} {inp:>10,} {out:>10,} {cost_indicator(cost, weekly_sub_cost)} {vs_sub}"
            )

        print()

    # Monthly Usage
    monthly_costs = {}
    if by_month:
        print(f"{Colors.BOLD}Monthly Token Usage (Last 6 Months){Colors.RESET}")
        print(f"{Colors.DIM}Subscription: ${monthly_sub_cost:.2f}/month{Colors.RESET}")
        print()
        print(f"  {'Month':<12} {'Input':>10} {'Output':>10} {'API Cost':>10} {'vs Sub':>10}")
        print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10}")

        for month in sorted(by_month.keys(), reverse=True)[:6]:
            inp, out, cache = calc_period_tokens(by_month[month])
            cost = calc_period_cost(by_month[month])
            monthly_costs[month] = cost
            diff = cost - monthly_sub_cost
            if diff > 0:
                vs_sub = f"{Colors.RED}+${diff:.2f}{Colors.RESET}"
            elif diff < 0:
                vs_sub = f"{Colors.GREEN}-${-diff:.2f}{Colors.RESET}"
            else:
                vs_sub = f"{Colors.DIM}=$0.00{Colors.RESET}"
            print(
                f"  {month:<12} {inp:>10,} {out:>10,} {cost_indicator(cost, monthly_sub_cost)} {vs_sub}"
            )

        print()

    # Subscription Recommendation
    if monthly_costs:
        _display_subscription_recommendation(monthly_costs, monthly_sub_cost, subscription_plans)


def _display_subscription_recommendation(
    monthly_costs: dict,
    monthly_sub_cost: float,
    subscription_plans: dict,
) -> None:
    """Display subscription recommendation based on usage analysis.

    Args:
        monthly_costs: Dict of month -> cost.
        monthly_sub_cost: Current subscription monthly cost.
        subscription_plans: Available subscription plans.
    """
    avg_monthly_cost = sum(monthly_costs.values()) / len(monthly_costs)
    total_cost = sum(monthly_costs.values())
    months_count = len(monthly_costs)

    print(f"{Colors.BOLD}{Colors.CYAN}═══ Subscription Recommendation ═══{Colors.RESET}")
    print()
    print(f"  Based on {months_count} months of usage data:")
    print()
    print(
        f"  {'Average monthly API cost:':<28} {Colors.BOLD}${avg_monthly_cost:>8.2f}{Colors.RESET}"
    )
    print(f"  {'Total API cost ({} months):':<28} ${total_cost:>8.2f}".format(months_count))
    print()

    print(f"  {'Plan':<12} {'Monthly':>10} {'vs API':>12} {'Recommendation':<20}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 12} {'-' * 20}")

    for plan_id, plan_data in subscription_plans.items():
        plan_cost = plan_data["cost"]
        diff = avg_monthly_cost - plan_cost

        if diff > 0:
            vs_api = f"{Colors.GREEN}saves ${diff:.2f}{Colors.RESET}"
        else:
            vs_api = f"{Colors.YELLOW}costs ${-diff:.2f}{Colors.RESET}"

        # Determine recommendation
        if avg_monthly_cost < subscription_plans["pro"]["cost"] * 0.7:
            if plan_id == "pro":
                rec = f"{Colors.YELLOW}Consider API{Colors.RESET}"
            else:
                rec = ""
        else:
            rec = ""

        print(f"  {plan_data['name']:<12} ${plan_cost:>8.0f} {vs_api:>20} {rec}")

    print()

    # Final recommendation
    pro_cost = subscription_plans["pro"]["cost"]
    max5_cost = subscription_plans["max_5x"]["cost"]
    max20_cost = subscription_plans["max_20x"]["cost"]

    if avg_monthly_cost < pro_cost * 0.5:
        print(f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} Your usage is low enough that")
        print(f"     {Colors.YELLOW}pay-per-use API{Colors.RESET} might be more cost-effective.")
        print(f"     Average: ${avg_monthly_cost:.2f}/mo vs Pro: ${pro_cost:.0f}/mo")
    elif avg_monthly_cost < max5_cost:
        print(
            f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} {Colors.GREEN}Pro ($20/mo){Colors.RESET} is optimal for your usage."
        )
        print(f"     Your API equivalent: ${avg_monthly_cost:.2f}/mo")
        if avg_monthly_cost > pro_cost:
            savings = avg_monthly_cost - pro_cost
            print(
                f"     You save: {Colors.GREEN}${savings:.2f}/mo{Colors.RESET} with Pro subscription"
            )
    elif avg_monthly_cost < max20_cost:
        print(
            f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} {Colors.GREEN}Max 5x ($100/mo){Colors.RESET} offers best value."
        )
        print(f"     Your API equivalent: ${avg_monthly_cost:.2f}/mo")
        savings = avg_monthly_cost - max5_cost
        if savings > 0:
            print(f"     You save: {Colors.GREEN}${savings:.2f}/mo{Colors.RESET} with Max 5x")
    else:
        print(
            f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} {Colors.GREEN}Max 20x ($200/mo){Colors.RESET} for heavy usage."
        )
        print(f"     Your API equivalent: ${avg_monthly_cost:.2f}/mo")
        savings = avg_monthly_cost - max20_cost
        if savings > 0:
            print(f"     You save: {Colors.GREEN}${savings:.2f}/mo{Colors.RESET} with Max 20x")

    print()

    # Rate Limit Analysis
    _display_rate_limit_analysis(monthly_costs, monthly_sub_cost, subscription_plans)


def _display_rate_limit_analysis(
    monthly_costs: dict,
    monthly_sub_cost: float,
    subscription_plans: dict,
) -> None:
    """Display rate limit analysis based on usage patterns.

    Args:
        monthly_costs: Dict of month -> cost.
        monthly_sub_cost: Current subscription monthly cost.
        subscription_plans: Available subscription plans.
    """
    sum(monthly_costs.values()) / len(monthly_costs)
    daily_costs_list = list(monthly_costs.values())

    if not daily_costs_list:
        return

    peak_monthly = max(daily_costs_list)
    max5_cost = subscription_plans["max_5x"]["cost"]
    max20_cost = subscription_plans["max_20x"]["cost"]
    pro_cost = subscription_plans["pro"]["cost"]

    print(f"{Colors.BOLD}{Colors.CYAN}═══ Rate Limit Analysis ═══{Colors.RESET}")
    print()
    print(
        f"  {Colors.DIM}Subscriptions have usage limits that may throttle heavy sessions.{Colors.RESET}"
    )
    print(
        f"  {Colors.DIM}API pay-per-use has no usage limits, only rate limits (tokens/min).{Colors.RESET}"
    )
    print()

    print(f"  {'Usage Pattern':<24} {'Your Usage':>12} {'Impact':>20}")
    print(f"  {'-' * 24} {'-' * 12} {'-' * 20}")

    # Peak month analysis
    if peak_monthly > monthly_sub_cost * 2:
        impact = f"{Colors.RED}May hit limits{Colors.RESET}"
    elif peak_monthly > monthly_sub_cost:
        impact = f"{Colors.YELLOW}Near limits{Colors.RESET}"
    else:
        impact = f"{Colors.GREEN}Within limits{Colors.RESET}"
    print(f"  {'Peak month cost':<24} ${peak_monthly:>10.2f} {impact:>28}")

    # Burstiness check
    if len(daily_costs_list) > 1:
        variance = max(daily_costs_list) / (sum(daily_costs_list) / len(daily_costs_list))
        if variance > 3:
            burst_impact = f"{Colors.RED}Very bursty{Colors.RESET}"
        elif variance > 1.5:
            burst_impact = f"{Colors.YELLOW}Somewhat bursty{Colors.RESET}"
        else:
            burst_impact = f"{Colors.GREEN}Steady usage{Colors.RESET}"
        print(f"  {'Usage variance':<24} {variance:>11.1f}x {burst_impact:>28}")

    print()
    print(f"  {Colors.BOLD}Rate Limit Considerations:{Colors.RESET}")
    print()

    if peak_monthly > max20_cost:
        print(
            f"  {Colors.RED}⚠{Colors.RESET}  Your peak usage (${peak_monthly:.0f}/mo) exceeds Max 20x limits."
        )
        print("      You may experience throttling even on the highest plan.")
        print(f"      {Colors.CYAN}Consider:{Colors.RESET} API pay-per-use for unlimited capacity")
    elif peak_monthly > max5_cost:
        print(
            f"  {Colors.YELLOW}⚠{Colors.RESET}  Your peak usage suggests you might hit Max 5x limits."
        )
        print(
            f"      {Colors.CYAN}Consider:{Colors.RESET} Max 20x for headroom, or API for peak periods"
        )
    elif peak_monthly > pro_cost * 2:
        print(f"  {Colors.YELLOW}ℹ{Colors.RESET}  Your peak usage is 2x+ Pro limits.")
        print(f"      {Colors.CYAN}Consider:{Colors.RESET} Max 5x to avoid throttling on busy days")
    else:
        print(
            f"  {Colors.GREEN}✓{Colors.RESET}  Your usage patterns fit within subscription limits."
        )
        print("      Pro plan should provide sufficient capacity.")

    print()


def display_analytics(
    data: dict,
    history: list,
    config: dict,
    history_file: Optional[Path] = None,
) -> None:
    """Display detailed analytics.

    Args:
        data: Current usage data.
        history: List of historical usage records.
        config: Configuration dict.
        history_file: Optional path to history file for display.
    """
    if history_file is None:
        history_file = HISTORY_FILE

    print()
    print(f"{Colors.BOLD}{Colors.MAGENTA}═══ Usage Analytics ═══{Colors.RESET}")
    print()

    # Data source indicator
    if config.get("use_admin_api") and config.get("admin_api_key"):
        print(f"{Colors.DIM}Data source: Admin API + Local tracking{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Data source: Local tracking{Colors.RESET}")
    print()

    # Current usage summary
    print(f"{Colors.BOLD}{Colors.WHITE}Current Status{Colors.RESET}")
    print()

    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)

    session_remaining = 100 - five_hour
    weekly_remaining = 100 - seven_day

    print(f"  Session capacity remaining:  {Colors.GREEN}{session_remaining:.0f}%{Colors.RESET}")
    print(f"  Weekly capacity remaining:   {Colors.GREEN}{weekly_remaining:.0f}%{Colors.RESET}")

    if history:
        recent_1h = get_period_stats(history, 1, "five_hour")
        if recent_1h["count"] >= 2:
            rate = recent_1h["max"] - recent_1h["min"]
            if rate > 0:
                hours_to_limit = session_remaining / rate
                if hours_to_limit < 24:
                    print(
                        f"  Est. time to session limit:  {Colors.YELLOW}{hours_to_limit:.1f} hours{Colors.RESET} (at current rate)"
                    )

    print()

    # Historical trends
    if not history:
        print(
            f"{Colors.DIM}No historical data yet. Run periodically to collect analytics.{Colors.RESET}"
        )
        print(f"{Colors.DIM}Data is stored in: {history_file}{Colors.RESET}")
        print()
        return

    print(f"{Colors.BOLD}{Colors.WHITE}Session Usage Trends (5-hour window){Colors.RESET}")
    print()

    stats_24h = get_period_stats(history, 24, "five_hour")
    if stats_24h["count"] > 0:
        sparkline, time_axis = make_sparkline(
            stats_24h["values"], stats_24h.get("timestamps"), period_hours=24
        )
        print(f"  Last 24h: {sparkline}")
        if time_axis:
            print(f"            {time_axis}")
        print(
            f"            Min: {stats_24h['min']:.0f}%  Max: {stats_24h['max']:.0f}%  Avg: {stats_24h['avg']:.1f}%"
        )

        stats_prev = get_period_stats(
            [
                h
                for h in history
                if h["timestamp"] < (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            ],
            24,
            "five_hour",
        )
        if stats_prev["count"] > 0:
            trend = format_trend(stats_24h["avg"], stats_prev["avg"])
            print(f"            vs prev 24h: {trend}")
    print()

    stats_7d = get_period_stats(history, 168, "five_hour")
    if stats_7d["count"] > 0:
        sparkline, time_axis = make_sparkline(
            stats_7d["values"], stats_7d.get("timestamps"), period_hours=168
        )
        print(f"  Last 7d:  {sparkline}")
        if time_axis:
            print(f"            {time_axis}")
        print(
            f"            Min: {stats_7d['min']:.0f}%  Max: {stats_7d['max']:.0f}%  Avg: {stats_7d['avg']:.1f}%"
        )
    print()

    print(f"{Colors.BOLD}{Colors.WHITE}Weekly Usage Trends (7-day window){Colors.RESET}")
    print()

    stats_weekly = get_period_stats(history, 168, "seven_day")
    if stats_weekly["count"] > 0:
        sparkline, time_axis = make_sparkline(
            stats_weekly["values"], stats_weekly.get("timestamps"), period_hours=168
        )
        print(f"  Last 7d:  {sparkline}")
        if time_axis:
            print(f"            {time_axis}")
        print(
            f"            Min: {stats_weekly['min']:.0f}%  Max: {stats_weekly['max']:.0f}%  Avg: {stats_weekly['avg']:.1f}%"
        )
    print()

    peaks = get_daily_peaks(history, "five_hour")
    if peaks["peak_day"] or peaks["peak_hour"] is not None:
        print(f"{Colors.BOLD}{Colors.WHITE}Usage Patterns{Colors.RESET}")
        print()
        if peaks["peak_day"]:
            print(
                f"  Peak day:   {Colors.YELLOW}{peaks['peak_day']}{Colors.RESET} (avg {peaks['peak_day_avg']:.1f}%)"
            )
        if peaks["peak_hour"] is not None:
            hour_str = datetime.now().replace(hour=peaks["peak_hour"], minute=0).strftime("%-I %p")
            print(
                f"  Peak hour:  {Colors.YELLOW}{hour_str}{Colors.RESET} (avg {peaks['peak_hour_avg']:.1f}%)"
            )
        print()

    total_records = len(history)
    oldest = min(h["timestamp"] for h in history) if history else None
    if oldest:
        oldest_dt = datetime.fromisoformat(oldest.replace("Z", "+00:00")).astimezone()
        days_tracked = (datetime.now(timezone.utc) - oldest_dt.astimezone(timezone.utc)).days
        print(
            f"{Colors.DIM}Analytics based on {total_records} data points over {days_tracked} days{Colors.RESET}"
        )

    print(f"{Colors.DIM}History stored in: {history_file}{Colors.RESET}")
    print()


def display_analytics_json(data: dict, history: list, config: dict) -> None:
    """Output analytics as JSON.

    Args:
        data: Current usage data.
        history: List of historical usage records.
        config: Configuration dict.
    """
    stats_24h = get_period_stats(history, 24, "five_hour")
    stats_7d = get_period_stats(history, 168, "five_hour")
    stats_weekly = get_period_stats(history, 168, "seven_day")
    peaks = get_daily_peaks(history, "five_hour")

    analytics = {
        "current": data,
        "history_count": len(history),
        "data_source": "admin_api" if config.get("use_admin_api") else "local",
        "session_stats_24h": (
            {
                "min": stats_24h.get("min"),
                "max": stats_24h.get("max"),
                "avg": stats_24h.get("avg"),
                "count": stats_24h.get("count", 0),
            }
            if stats_24h["count"] > 0
            else None
        ),
        "session_stats_7d": (
            {
                "min": stats_7d.get("min"),
                "max": stats_7d.get("max"),
                "avg": stats_7d.get("avg"),
                "count": stats_7d.get("count", 0),
            }
            if stats_7d["count"] > 0
            else None
        ),
        "weekly_stats_7d": (
            {
                "min": stats_weekly.get("min"),
                "max": stats_weekly.get("max"),
                "avg": stats_weekly.get("avg"),
                "count": stats_weekly.get("count", 0),
            }
            if stats_weekly["count"] > 0
            else None
        ),
        "patterns": {
            "peak_day": peaks.get("peak_day"),
            "peak_day_avg": peaks.get("peak_day_avg"),
            "peak_hour": peaks.get("peak_hour"),
            "peak_hour_avg": peaks.get("peak_hour_avg"),
        },
    }

    print(json.dumps(analytics, indent=2))


def display_json(data: dict) -> None:
    """Output data as formatted JSON.

    Args:
        data: Data to output.
    """
    print(json.dumps(data, indent=2))


__all__ = [
    "make_sparkline",
    "format_trend",
    "get_period_stats",
    "get_daily_peaks",
    "calculate_token_cost",
    "display_admin_usage",
    "display_analytics",
    "display_analytics_json",
    "display_json",
    "SUBSCRIPTION_PLANS",
    "API_PRICING",
    "HISTORY_FILE",
]
