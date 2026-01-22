"""Centralized pricing data for Claude models.

This module provides a single source of truth for model pricing,
used across all cost calculation functions in the codebase.
"""

from __future__ import annotations

from typing import NamedTuple


class ModelPricing(NamedTuple):
    input: float
    output: float
    cache_read: float
    cache_creation: float


# Pricing per 1M tokens (as of 2025)
# Format: (input, output, cache_read, cache_creation)
PRICING: dict[str, ModelPricing] = {
    # Opus models
    "claude-opus-4-5-20251101": ModelPricing(15.0, 75.0, 1.50, 18.75),
    "claude-opus-4-20250514": ModelPricing(15.0, 75.0, 1.50, 18.75),
    # Sonnet models
    "claude-sonnet-4-5-20250929": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-3-5-sonnet-20241022": ModelPricing(3.0, 15.0, 0.30, 3.75),
    # Haiku models
    "claude-haiku-4-5-20251101": ModelPricing(1.0, 5.0, 0.10, 1.25),
    "claude-3-5-haiku-20241022": ModelPricing(1.0, 5.0, 0.10, 1.25),
    "claude-3-haiku-20240307": ModelPricing(0.25, 1.25, 0.03, 0.3125),
    # Default fallback (Sonnet pricing)
    "default": ModelPricing(3.0, 15.0, 0.30, 3.75),
}


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int = 0,
    model: str = "default",
) -> float:
    """Calculate cost based on token counts and model pricing.

    Args:
        input_tokens: Non-cached input tokens.
        output_tokens: Output tokens.
        cache_read_tokens: Cached input tokens read.
        cache_creation_tokens: Tokens written to cache.
        model: Model identifier for pricing lookup.

    Returns:
        Estimated cost in dollars.
    """
    pricing = PRICING.get(model, PRICING["default"])

    return (
        (input_tokens / 1_000_000) * pricing.input
        + (output_tokens / 1_000_000) * pricing.output
        + (cache_read_tokens / 1_000_000) * pricing.cache_read
        + (cache_creation_tokens / 1_000_000) * pricing.cache_creation
    )


__all__ = [
    "ModelPricing",
    "PRICING",
    "calculate_cost",
]
