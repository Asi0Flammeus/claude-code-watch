"""Tests for the centralized pricing module."""

from __future__ import annotations

import pytest

from claude_watch.pricing import PRICING, ModelPricing, calculate_cost


class TestPricingConstants:
    """Tests for PRICING dict."""

    def test_pricing_has_required_models(self):
        """Test that all expected models are present."""
        expected_models = [
            "claude-opus-4-5-20251101",
            "claude-opus-4-20250514",
            "claude-sonnet-4-5-20250929",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-haiku-4-5-20251101",
            "claude-3-5-haiku-20241022",
            "claude-3-haiku-20240307",
            "default",
        ]
        for model in expected_models:
            assert model in PRICING, f"Missing model: {model}"

    def test_pricing_is_namedtuple_with_four_fields(self):
        """Test that each pricing entry is a ModelPricing with 4 fields."""
        for model, pricing in PRICING.items():
            assert isinstance(pricing, ModelPricing), f"{model} is not ModelPricing"
            assert len(pricing) == 4, f"{model} doesn't have 4 fields"
            assert hasattr(pricing, "input")
            assert hasattr(pricing, "output")
            assert hasattr(pricing, "cache_read")
            assert hasattr(pricing, "cache_creation")

    def test_pricing_values_are_positive(self):
        """Test that all pricing values are non-negative."""
        for model, pricing in PRICING.items():
            assert pricing.input >= 0, f"{model} input price is negative"
            assert pricing.output >= 0, f"{model} output price is negative"
            assert pricing.cache_read >= 0, f"{model} cache_read price is negative"
            assert pricing.cache_creation >= 0, f"{model} cache_creation price is negative"

    def test_opus_is_most_expensive(self):
        """Test that Opus models are priced higher than Sonnet."""
        opus_pricing = PRICING["claude-opus-4-5-20251101"]
        sonnet_pricing = PRICING["claude-sonnet-4-5-20250929"]

        assert opus_pricing.input > sonnet_pricing.input
        assert opus_pricing.output > sonnet_pricing.output


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_zero_tokens_returns_zero(self):
        """Test that zero tokens results in zero cost."""
        cost = calculate_cost(0, 0, 0, 0, "default")
        assert cost == 0.0

    def test_known_values_sonnet(self):
        """Test cost calculation with known Sonnet pricing."""
        # Sonnet: $3/MTok input, $15/MTok output, $0.30/MTok cache read
        # 1M input + 1M output + 1M cache = $3 + $15 + $0.30 = $18.30
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_creation_tokens=0,
            model="claude-sonnet-4-5-20250929",
        )
        assert cost == pytest.approx(18.30, rel=0.01)

    def test_known_values_opus(self):
        """Test cost calculation with known Opus pricing."""
        # Opus: $15/MTok input, $75/MTok output, $1.50/MTok cache read
        # 1M input + 1M output + 1M cache = $15 + $75 + $1.50 = $91.50
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_creation_tokens=0,
            model="claude-opus-4-5-20251101",
        )
        assert cost == pytest.approx(91.50, rel=0.01)

    def test_cache_creation_included(self):
        """Test that cache creation tokens are included in cost."""
        # With cache creation
        cost_with = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=1_000_000,
            model="claude-sonnet-4-5-20250929",
        )
        # Without cache creation
        cost_without = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            model="claude-sonnet-4-5-20250929",
        )
        assert cost_with > cost_without

    def test_unknown_model_uses_default(self):
        """Test that unknown models fall back to default pricing."""
        cost_unknown = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            model="unknown-model-xyz",
        )
        cost_default = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            model="default",
        )
        assert cost_unknown == cost_default

    def test_small_token_counts(self):
        """Test with small token counts (typical usage)."""
        # 10K input, 5K output - typical for a few messages
        cost = calculate_cost(
            input_tokens=10_000,
            output_tokens=5_000,
            cache_read_tokens=50_000,
            cache_creation_tokens=0,
            model="claude-sonnet-4-5-20250929",
        )
        # $3/MTok * 0.01M + $15/MTok * 0.005M + $0.30/MTok * 0.05M
        # = $0.03 + $0.075 + $0.015 = $0.12
        assert cost == pytest.approx(0.12, rel=0.01)
