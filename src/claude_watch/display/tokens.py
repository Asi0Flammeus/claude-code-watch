"""Token usage display formatting for terminal output.

Provides functions for displaying Claude Code token usage with
period summaries, daily breakdowns, model breakdowns, and cost estimates.

Expected data structure from token parser:
{
    "period": {
        "days": int,
        "start_date": str,  # ISO date string
        "end_date": str,    # ISO date string
    },
    "totals": {
        "input_tokens": int,
        "output_tokens": int,
        "cache_read_tokens": int,
        "cache_write_tokens": int,  # optional
        "messages": int,
    },
    "daily": [
        {
            "date": str,  # ISO date string
            "input_tokens": int,
            "output_tokens": int,
            "cache_read_tokens": int,
            "cache_write_tokens": int,  # optional
            "messages": int,
        },
        ...
    ],
    "by_model": {
        "model-id": {
            "input_tokens": int,
            "output_tokens": int,
            "cache_read_tokens": int,
            "cache_write_tokens": int,  # optional
            "messages": int,
        },
        ...
    },
}
"""

import json

from claude_watch.display.colors import Colors
from claude_watch.pricing import calculate_cost


def _format_number(n: int) -> str:
    """Format a number with thousands separators.

    Args:
        n: The number to format.

    Returns:
        Formatted string with commas.
    """
    return f"{n:,}"


def _get_model_display_name(model_id: str) -> str:
    """Get a shorter display name for a model ID.

    Args:
        model_id: Full model identifier (e.g., 'claude-opus-4-5-20251101').

    Returns:
        Shortened display name.
    """
    return model_id


def display_token_usage(data: dict) -> None:
    """Display token usage with formatted terminal output.

    Args:
        data: Token usage data dict containing 'period', 'totals',
            'daily', and 'by_model' keys.
    """
    period = data.get("period", {})
    totals = data.get("totals", {})
    daily = data.get("daily", [])
    by_model = data.get("by_model", {})

    days = period.get("days", 7)

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}=== Claude Code Token Usage (Last {days} Days) ==={Colors.RESET}")
    print()

    # Totals section
    print(f"{Colors.BOLD}{Colors.WHITE}Totals{Colors.RESET}")
    print()

    input_tok = totals.get("input_tokens", 0)
    output_tok = totals.get("output_tokens", 0)
    cache_read_tok = totals.get("cache_read_tokens", 0)
    cache_write_tok = totals.get("cache_write_tokens", 0)
    messages = totals.get("messages", 0)

    print(f"  {'Input tokens:':<24} {Colors.GREEN}{_format_number(input_tok):>14}{Colors.RESET}")
    print(f"  {'Output tokens:':<24} {Colors.GREEN}{_format_number(output_tok):>14}{Colors.RESET}")
    print(f"  {'Cache read tokens:':<24} {Colors.CYAN}{_format_number(cache_read_tok):>14}{Colors.RESET}")
    if cache_write_tok > 0:
        print(f"  {'Cache write tokens:':<24} {Colors.CYAN}{_format_number(cache_write_tok):>14}{Colors.RESET}")
    print(f"  {'Messages:':<24} {Colors.WHITE}{_format_number(messages):>14}{Colors.RESET}")
    print()

    # Daily breakdown
    if daily:
        print(f"{Colors.BOLD}{Colors.WHITE}Daily Breakdown{Colors.RESET}")
        print()

        # Header
        header = f"  {'Date':<12} {'Input':>12} {'Output':>12} {'Cache Read':>14} {'Messages':>10}"
        print(f"{Colors.DIM}{header}{Colors.RESET}")
        print(f"  {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 14} {'-' * 10}")

        # Sort daily by date descending
        sorted_daily = sorted(daily, key=lambda x: x.get("date", ""), reverse=True)

        for day_data in sorted_daily:
            date_str = day_data.get("date", "")[:10]
            day_input = day_data.get("input_tokens", 0)
            day_output = day_data.get("output_tokens", 0)
            day_cache = day_data.get("cache_read_tokens", 0)
            day_messages = day_data.get("messages", 0)

            print(
                f"  {date_str:<12} "
                f"{_format_number(day_input):>12} "
                f"{_format_number(day_output):>12} "
                f"{_format_number(day_cache):>14} "
                f"{_format_number(day_messages):>10}"
            )
        print()

    # Model breakdown
    if by_model:
        print(f"{Colors.BOLD}{Colors.WHITE}By Model{Colors.RESET}")
        print()

        # Sort models by total tokens (input + output) descending
        sorted_models = sorted(
            by_model.items(),
            key=lambda x: x[1].get("input_tokens", 0) + x[1].get("output_tokens", 0),
            reverse=True,
        )

        for model_id, model_data in sorted_models:
            model_input = model_data.get("input_tokens", 0)
            model_output = model_data.get("output_tokens", 0)
            model_cache = model_data.get("cache_read_tokens", 0)

            # Color code by model type
            if "opus" in model_id.lower():
                model_color = Colors.MAGENTA
            elif "sonnet" in model_id.lower():
                model_color = Colors.CYAN
            elif "haiku" in model_id.lower():
                model_color = Colors.GREEN
            else:
                model_color = Colors.WHITE

            display_name = _get_model_display_name(model_id)
            print(
                f"  {model_color}{display_name}{Colors.RESET}:"
            )
            print(
                f"    {_format_number(model_input)} in / {_format_number(model_output)} out"
                f" / {_format_number(model_cache)} cache"
            )
        print()

    # Cost estimates
    print(f"{Colors.BOLD}{Colors.WHITE}Estimated API Cost (if pay-per-use){Colors.RESET}")
    print()

    # If we have model breakdown, calculate actual cost per model
    actual_cost = 0.0
    if by_model:
        for model_id, model_data in by_model.items():
            actual_cost += calculate_cost(
                model_data.get("input_tokens", 0),
                model_data.get("output_tokens", 0),
                model_data.get("cache_read_tokens", 0),
                model_data.get("cache_creation_tokens", 0),
                model_id,
            )
        print(f"  {'Actual model mix:':<24} {Colors.BOLD}${actual_cost:>10,.2f}{Colors.RESET}")

    # Calculate hypothetical costs at each pricing tier
    opus_cost = calculate_cost(input_tok, output_tok, cache_read_tok, 0, "claude-opus-4-5-20251101")
    sonnet_cost = calculate_cost(input_tok, output_tok, cache_read_tok, 0, "claude-sonnet-4-5-20250929")
    haiku_cost = calculate_cost(input_tok, output_tok, cache_read_tok, 0, "claude-haiku-4-5-20251101")

    print(f"  {'At Opus pricing:':<24} {Colors.MAGENTA}${opus_cost:>10,.2f}{Colors.RESET}")
    print(f"  {'At Sonnet pricing:':<24} {Colors.CYAN}${sonnet_cost:>10,.2f}{Colors.RESET}")
    print(f"  {'At Haiku pricing:':<24} {Colors.GREEN}${haiku_cost:>10,.2f}{Colors.RESET}")
    print()

    # Subscription comparison
    _display_subscription_comparison(actual_cost if actual_cost > 0 else sonnet_cost)


def _display_subscription_comparison(api_cost: float) -> None:
    """Display subscription comparison message.

    Args:
        api_cost: The calculated API cost for comparison.
    """
    # Approximate monthly extrapolation (assuming 7 days of data)
    monthly_estimate = api_cost * (30 / 7)

    print(f"{Colors.DIM}Subscription Value Comparison (extrapolated monthly):{Colors.RESET}")
    print()

    subscriptions = [
        ("Pro", 20, "$20/mo"),
        ("Max 5x", 100, "$100/mo"),
        ("Max 20x", 200, "$200/mo"),
    ]

    for name, cost, price in subscriptions:
        if monthly_estimate > cost:
            savings = monthly_estimate - cost
            savings_pct = (savings / monthly_estimate) * 100
            print(
                f"  {name} ({price}): "
                f"{Colors.GREEN}saves ~${savings:,.0f}/mo ({savings_pct:.0f}%){Colors.RESET}"
            )
        else:
            overpay = cost - monthly_estimate
            print(
                f"  {name} ({price}): "
                f"{Colors.YELLOW}~${overpay:,.0f}/mo over API cost{Colors.RESET}"
            )
    print()


def display_token_usage_json(data: dict) -> None:
    """Output token usage data as formatted JSON.

    Args:
        data: Token usage data dict to output.
    """
    # Add calculated costs to the output
    totals = data.get("totals", {})
    by_model = data.get("by_model", {})

    input_tok = totals.get("input_tokens", 0)
    output_tok = totals.get("output_tokens", 0)
    cache_read_tok = totals.get("cache_read_tokens", 0)

    # Calculate costs
    opus_cost = calculate_cost(input_tok, output_tok, cache_read_tok, 0, "claude-opus-4-5-20251101")
    sonnet_cost = calculate_cost(input_tok, output_tok, cache_read_tok, 0, "claude-sonnet-4-5-20250929")

    # Calculate actual cost if model breakdown available
    actual_cost = 0.0
    if by_model:
        for model_id, model_data in by_model.items():
            actual_cost += calculate_cost(
                model_data.get("input_tokens", 0),
                model_data.get("output_tokens", 0),
                model_data.get("cache_read_tokens", 0),
                model_data.get("cache_creation_tokens", 0),
                model_id,
            )

    output = {
        **data,
        "estimated_costs": {
            "actual_model_mix": round(actual_cost, 2) if actual_cost > 0 else None,
            "at_opus_pricing": round(opus_cost, 2),
            "at_sonnet_pricing": round(sonnet_cost, 2),
            "currency": "USD",
        },
    }

    print(json.dumps(output, indent=2))


def _calc_stats(values: list[int | float]) -> tuple[float, float]:
    """Calculate mean and standard deviation.

    Args:
        values: List of numeric values.

    Returns:
        Tuple of (mean, std_dev). Returns (0, 0) if not enough values.
    """
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, variance ** 0.5


def _fmt_compact(n: float) -> str:
    """Format number in compact form (K, M).

    Args:
        n: Number to format.

    Returns:
        Formatted string.
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return f"{n:.0f}"


def display_token_stats(data: dict) -> None:
    """Display token usage statistics with period breakdown and averages.

    Shows usage by period (7d, 14d, 30d, 6mo, all time) and
    daily/weekly/monthly statistics with averages and std deviations.

    Args:
        data: Token usage data dict with 'daily' entries.
    """
    from collections import defaultdict
    from datetime import datetime, timedelta

    daily = data.get("daily", [])

    if not daily:
        print(f"{Colors.YELLOW}No data available for statistics.{Colors.RESET}")
        return

    # Parse and sort entries
    entries = []
    for d in daily:
        try:
            date = datetime.strptime(d["date"], "%Y-%m-%d")
            entries.append((date, d))
        except (KeyError, ValueError):
            continue

    if not entries:
        print(f"{Colors.YELLOW}No valid date entries found.{Colors.RESET}")
        return

    entries.sort(key=lambda x: x[0])
    oldest = entries[0][0]
    newest = entries[-1][0]
    total_days = (newest - oldest).days + 1

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}=== Token Usage Statistics ==={Colors.RESET}")
    print()
    print(f"  Date range: {oldest.date()} to {newest.date()} ({total_days} days)")
    print()

    # Period breakdown
    def calc_period(days_back: int) -> dict | None:
        cutoff = newest - timedelta(days=days_back)
        filtered = [(d, e) for d, e in entries if d > cutoff]
        if not filtered:
            return None
        return {
            "days": len(filtered),
            "input": sum(e["input_tokens"] for _, e in filtered),
            "output": sum(e["output_tokens"] for _, e in filtered),
            "cache_read": sum(e["cache_read_tokens"] for _, e in filtered),
            "messages": sum(e["messages"] for _, e in filtered),
        }

    periods = [
        ("Last 7 days", 7),
        ("Last 14 days", 14),
        ("Last 30 days", 30),
        ("Last 6 months", 180),
        ("All time", 9999),
    ]

    print(f"{Colors.BOLD}{Colors.WHITE}Usage by Period{Colors.RESET}")
    print()
    header = f"  {'Period':<16} {'Days':>6} {'Input':>10} {'Output':>10} {'Cache Read':>12} {'Messages':>10}"
    print(f"{Colors.DIM}{header}{Colors.RESET}")
    print(f"  {'-' * 70}")

    for name, days in periods:
        p = calc_period(days)
        if p:
            print(
                f"  {name:<16} {p['days']:>6} "
                f"{_fmt_compact(p['input']):>10} "
                f"{_fmt_compact(p['output']):>10} "
                f"{_fmt_compact(p['cache_read']):>12} "
                f"{p['messages']:>10,}"
            )
    print()

    # Daily statistics
    daily_input = [e["input_tokens"] for _, e in entries]
    daily_output = [e["output_tokens"] for _, e in entries]
    daily_cache = [e["cache_read_tokens"] for _, e in entries]
    daily_msgs = [e["messages"] for _, e in entries]

    print(f"{Colors.BOLD}{Colors.WHITE}Daily Statistics ({len(entries)} days){Colors.RESET}")
    print()

    def print_stat_row(label: str, values: list, color: str = Colors.WHITE) -> None:
        mean, std = _calc_stats(values)
        print(
            f"  {label:<16} "
            f"avg {color}{_fmt_compact(mean):>10}{Colors.RESET}  "
            f"std {Colors.DIM}{_fmt_compact(std):>10}{Colors.RESET}"
        )

    print_stat_row("Input tokens:", daily_input, Colors.GREEN)
    print_stat_row("Output tokens:", daily_output, Colors.GREEN)
    print_stat_row("Cache read:", daily_cache, Colors.CYAN)
    print_stat_row("Messages:", daily_msgs, Colors.WHITE)
    print()

    # Weekly statistics
    weekly: dict = defaultdict(lambda: {"input": 0, "output": 0, "cache": 0, "msgs": 0})
    for d, e in entries:
        week = d.isocalendar()[:2]  # (year, week)
        weekly[week]["input"] += e["input_tokens"]
        weekly[week]["output"] += e["output_tokens"]
        weekly[week]["cache"] += e["cache_read_tokens"]
        weekly[week]["msgs"] += e["messages"]

    if len(weekly) > 1:
        w_input = [w["input"] for w in weekly.values()]
        w_output = [w["output"] for w in weekly.values()]
        w_cache = [w["cache"] for w in weekly.values()]
        w_msgs = [w["msgs"] for w in weekly.values()]

        print(f"{Colors.BOLD}{Colors.WHITE}Weekly Statistics ({len(weekly)} weeks){Colors.RESET}")
        print()
        print_stat_row("Input tokens:", w_input, Colors.GREEN)
        print_stat_row("Output tokens:", w_output, Colors.GREEN)
        print_stat_row("Cache read:", w_cache, Colors.CYAN)
        print_stat_row("Messages:", w_msgs, Colors.WHITE)
        print()

    # Monthly statistics
    monthly: dict = defaultdict(lambda: {"input": 0, "output": 0, "cache": 0, "msgs": 0})
    for d, e in entries:
        month = (d.year, d.month)
        monthly[month]["input"] += e["input_tokens"]
        monthly[month]["output"] += e["output_tokens"]
        monthly[month]["cache"] += e["cache_read_tokens"]
        monthly[month]["msgs"] += e["messages"]

    if len(monthly) > 1:
        m_input = [m["input"] for m in monthly.values()]
        m_output = [m["output"] for m in monthly.values()]
        m_cache = [m["cache"] for m in monthly.values()]
        m_msgs = [m["msgs"] for m in monthly.values()]

        print(f"{Colors.BOLD}{Colors.WHITE}Monthly Statistics ({len(monthly)} months){Colors.RESET}")
        print()
        print_stat_row("Input tokens:", m_input, Colors.GREEN)
        print_stat_row("Output tokens:", m_output, Colors.GREEN)
        print_stat_row("Cache read:", m_cache, Colors.CYAN)
        print_stat_row("Messages:", m_msgs, Colors.WHITE)
        print()

    # Variance indicator
    _, daily_std = _calc_stats(daily_msgs)
    daily_mean = sum(daily_msgs) / len(daily_msgs) if daily_msgs else 0
    if daily_mean > 0 and daily_std / daily_mean > 0.5:
        print(
            f"{Colors.DIM}Note: High variance in daily usage "
            f"(std/mean = {daily_std / daily_mean:.1%}){Colors.RESET}"
        )
        print()


def display_token_stats_json(data: dict) -> None:
    """Output token statistics as JSON.

    Args:
        data: Token usage data dict with 'daily' entries.
    """
    from collections import defaultdict
    from datetime import datetime, timedelta

    daily = data.get("daily", [])

    # Parse entries
    entries = []
    for d in daily:
        try:
            date = datetime.strptime(d["date"], "%Y-%m-%d")
            entries.append((date, d))
        except (KeyError, ValueError):
            continue

    if not entries:
        print(json.dumps({"error": "No valid data"}))
        return

    entries.sort(key=lambda x: x[0])
    oldest = entries[0][0]
    newest = entries[-1][0]

    # Period breakdown
    def calc_period(days_back: int) -> dict | None:
        cutoff = newest - timedelta(days=days_back)
        filtered = [(d, e) for d, e in entries if d > cutoff]
        if not filtered:
            return None
        return {
            "days": len(filtered),
            "input_tokens": sum(e["input_tokens"] for _, e in filtered),
            "output_tokens": sum(e["output_tokens"] for _, e in filtered),
            "cache_read_tokens": sum(e["cache_read_tokens"] for _, e in filtered),
            "messages": sum(e["messages"] for _, e in filtered),
        }

    periods_data = {}
    for name, days in [("7d", 7), ("14d", 14), ("30d", 30), ("6mo", 180), ("all", 9999)]:
        p = calc_period(days)
        if p:
            periods_data[name] = p

    # Statistics
    def calc_group_stats(groups: dict) -> dict:
        return {
            "count": len(groups),
            "input_tokens": {
                "mean": _calc_stats([g["input"] for g in groups.values()])[0],
                "std": _calc_stats([g["input"] for g in groups.values()])[1],
            },
            "output_tokens": {
                "mean": _calc_stats([g["output"] for g in groups.values()])[0],
                "std": _calc_stats([g["output"] for g in groups.values()])[1],
            },
            "cache_read_tokens": {
                "mean": _calc_stats([g["cache"] for g in groups.values()])[0],
                "std": _calc_stats([g["cache"] for g in groups.values()])[1],
            },
            "messages": {
                "mean": _calc_stats([g["msgs"] for g in groups.values()])[0],
                "std": _calc_stats([g["msgs"] for g in groups.values()])[1],
            },
        }

    # Daily
    daily_groups = {
        d.strftime("%Y-%m-%d"): {
            "input": e["input_tokens"],
            "output": e["output_tokens"],
            "cache": e["cache_read_tokens"],
            "msgs": e["messages"],
        }
        for d, e in entries
    }

    # Weekly
    weekly: dict = defaultdict(lambda: {"input": 0, "output": 0, "cache": 0, "msgs": 0})
    for d, e in entries:
        week = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        weekly[week]["input"] += e["input_tokens"]
        weekly[week]["output"] += e["output_tokens"]
        weekly[week]["cache"] += e["cache_read_tokens"]
        weekly[week]["msgs"] += e["messages"]

    # Monthly
    monthly: dict = defaultdict(lambda: {"input": 0, "output": 0, "cache": 0, "msgs": 0})
    for d, e in entries:
        month = d.strftime("%Y-%m")
        monthly[month]["input"] += e["input_tokens"]
        monthly[month]["output"] += e["output_tokens"]
        monthly[month]["cache"] += e["cache_read_tokens"]
        monthly[month]["msgs"] += e["messages"]

    output = {
        "date_range": {
            "oldest": oldest.strftime("%Y-%m-%d"),
            "newest": newest.strftime("%Y-%m-%d"),
            "total_days": (newest - oldest).days + 1,
        },
        "by_period": periods_data,
        "statistics": {
            "daily": calc_group_stats(daily_groups),
            "weekly": calc_group_stats(dict(weekly)) if len(weekly) > 1 else None,
            "monthly": calc_group_stats(dict(monthly)) if len(monthly) > 1 else None,
        },
    }

    print(json.dumps(output, indent=2))


__all__ = [
    "display_token_usage",
    "display_token_usage_json",
    "display_token_stats",
    "display_token_stats_json",
]
