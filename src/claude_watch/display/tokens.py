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
from typing import Optional

from claude_watch.display.analytics import API_PRICING
from claude_watch.display.colors import Colors


def _format_number(n: int) -> str:
    """Format a number with thousands separators.

    Args:
        n: The number to format.

    Returns:
        Formatted string with commas.
    """
    return f"{n:,}"


def _calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    model: str = "default",
    pricing: Optional[dict] = None,
) -> float:
    """Calculate API cost for given token counts.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cache_read_tokens: Number of cache read tokens.
        model: Model identifier for pricing lookup.
        pricing: Optional custom pricing dict (defaults to API_PRICING).

    Returns:
        Total cost in dollars.
    """
    if pricing is None:
        pricing = API_PRICING
    model_pricing = pricing.get(model, pricing.get("default", (3.00, 15.00, 0.30)))
    input_cost = (input_tokens / 1_000_000) * model_pricing[0]
    output_cost = (output_tokens / 1_000_000) * model_pricing[1]
    cache_cost = (cache_read_tokens / 1_000_000) * model_pricing[2]
    return input_cost + output_cost + cache_cost


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

    # Calculate cost at different pricing tiers
    opus_pricing = API_PRICING.get("claude-opus-4-5-20251101", (15.00, 75.00, 1.50))
    sonnet_pricing = API_PRICING.get("claude-sonnet-4-5-20250929", (3.00, 15.00, 0.30))
    haiku_pricing = API_PRICING.get("claude-haiku-4-5-20251101", (1.00, 5.00, 0.10))

    # If we have model breakdown, calculate actual cost per model
    actual_cost = 0.0
    if by_model:
        for model_id, model_data in by_model.items():
            actual_cost += _calculate_cost(
                model_data.get("input_tokens", 0),
                model_data.get("output_tokens", 0),
                model_data.get("cache_read_tokens", 0),
                model_id,
            )
        print(f"  {'Actual model mix:':<24} {Colors.BOLD}${actual_cost:>10,.2f}{Colors.RESET}")

    # Calculate hypothetical costs at each pricing tier
    opus_cost = (
        (input_tok / 1_000_000) * opus_pricing[0]
        + (output_tok / 1_000_000) * opus_pricing[1]
        + (cache_read_tok / 1_000_000) * opus_pricing[2]
    )
    sonnet_cost = (
        (input_tok / 1_000_000) * sonnet_pricing[0]
        + (output_tok / 1_000_000) * sonnet_pricing[1]
        + (cache_read_tok / 1_000_000) * sonnet_pricing[2]
    )
    haiku_cost = (
        (input_tok / 1_000_000) * haiku_pricing[0]
        + (output_tok / 1_000_000) * haiku_pricing[1]
        + (cache_read_tok / 1_000_000) * haiku_pricing[2]
    )

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
    opus_pricing = API_PRICING.get("claude-opus-4-5-20251101", (15.00, 75.00, 1.50))
    sonnet_pricing = API_PRICING.get("claude-sonnet-4-5-20250929", (3.00, 15.00, 0.30))

    opus_cost = (
        (input_tok / 1_000_000) * opus_pricing[0]
        + (output_tok / 1_000_000) * opus_pricing[1]
        + (cache_read_tok / 1_000_000) * opus_pricing[2]
    )
    sonnet_cost = (
        (input_tok / 1_000_000) * sonnet_pricing[0]
        + (output_tok / 1_000_000) * sonnet_pricing[1]
        + (cache_read_tok / 1_000_000) * sonnet_pricing[2]
    )

    # Calculate actual cost if model breakdown available
    actual_cost = 0.0
    if by_model:
        for model_id, model_data in by_model.items():
            actual_cost += _calculate_cost(
                model_data.get("input_tokens", 0),
                model_data.get("output_tokens", 0),
                model_data.get("cache_read_tokens", 0),
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


__all__ = ["display_token_usage", "display_token_usage_json"]
