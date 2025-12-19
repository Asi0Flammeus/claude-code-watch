"""
Tests for analytics calculation functions.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions from main script
exec(open(Path(__file__).parent.parent / "claude-watch", encoding="utf-8").read())


class TestGetPeriodStats:
    """Tests for get_period_stats function."""

    def test_empty_history(self):
        """Test with empty history."""
        result = get_period_stats([], 24, "five_hour")
        assert result["count"] == 0

    def test_with_data(self):
        """Test with sample history data."""
        # Use fresh timestamps within the last 24 hours
        now = datetime.now(timezone.utc)
        history = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "five_hour": 25.0},
            {"timestamp": (now - timedelta(hours=2)).isoformat(), "five_hour": 30.0},
            {"timestamp": (now - timedelta(hours=3)).isoformat(), "five_hour": 35.0},
        ]
        result = get_period_stats(history, 24, "five_hour")
        assert result["count"] > 0
        assert "min" in result
        assert "max" in result
        assert "avg" in result

    def test_min_max_avg(self):
        """Test min, max, avg calculations."""
        now = datetime.now(timezone.utc)
        history = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "five_hour": 10},
            {"timestamp": (now - timedelta(hours=2)).isoformat(), "five_hour": 20},
            {"timestamp": (now - timedelta(hours=3)).isoformat(), "five_hour": 30},
        ]
        result = get_period_stats(history, 24, "five_hour")

        assert result["min"] == 10
        assert result["max"] == 30
        assert result["avg"] == 20

    def test_filters_old_data(self):
        """Test that old data is filtered out."""
        now = datetime.now(timezone.utc)
        history = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "five_hour": 50},
            {"timestamp": (now - timedelta(hours=25)).isoformat(), "five_hour": 100},
        ]
        result = get_period_stats(history, 24, "five_hour")

        assert result["count"] == 1
        assert result["max"] == 50

    def test_handles_none_values(self):
        """Test handling of None values."""
        now = datetime.now(timezone.utc)
        history = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "five_hour": 50},
            {"timestamp": (now - timedelta(hours=2)).isoformat(), "five_hour": None},
            {"timestamp": (now - timedelta(hours=3)).isoformat(), "five_hour": 30},
        ]
        result = get_period_stats(history, 24, "five_hour")

        assert result["count"] == 2


class TestGetDailyPeaks:
    """Tests for get_daily_peaks function."""

    def test_empty_history(self):
        """Test with empty history."""
        result = get_daily_peaks([], "five_hour")
        assert result["peak_day"] is None
        assert result["peak_hour"] is None

    def test_finds_peak_day(self, history_large):
        """Test finding peak day."""
        result = get_daily_peaks(history_large, "five_hour")
        # Should have a peak day
        if result["peak_day"]:
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            assert result["peak_day"] in days

    def test_finds_peak_hour(self, history_large):
        """Test finding peak hour."""
        result = get_daily_peaks(history_large, "five_hour")
        # Should have a peak hour (0-23)
        if result["peak_hour"] is not None:
            assert 0 <= result["peak_hour"] <= 23


class TestCalculateTokenCost:
    """Tests for calculate_token_cost function."""

    def test_zero_tokens(self):
        """Test with zero tokens."""
        cost = calculate_token_cost(0, 0, 0)
        assert cost == 0

    def test_input_only(self):
        """Test input tokens only."""
        cost = calculate_token_cost(1_000_000, 0, 0, "default")
        assert cost == 3.0  # $3 per 1M input tokens

    def test_output_only(self):
        """Test output tokens only."""
        cost = calculate_token_cost(0, 1_000_000, 0, "default")
        assert cost == 15.0  # $15 per 1M output tokens

    def test_cache_tokens(self):
        """Test cache read tokens."""
        cost = calculate_token_cost(0, 0, 1_000_000, "default")
        assert cost == 0.30  # $0.30 per 1M cache tokens

    def test_combined(self):
        """Test combined token costs."""
        cost = calculate_token_cost(1_000_000, 500_000, 2_000_000, "default")
        expected = 3.0 + 7.5 + 0.60  # input + output + cache
        assert abs(cost - expected) < 0.01

    def test_specific_model(self):
        """Test with specific model pricing."""
        # Opus is more expensive
        cost_default = calculate_token_cost(1_000_000, 0, 0, "default")
        cost_opus = calculate_token_cost(1_000_000, 0, 0, "claude-opus-4-5-20251101")
        assert cost_opus > cost_default


class TestSubscriptionPlans:
    """Tests for subscription plan configuration."""

    def test_all_plans_exist(self):
        """Test all expected plans exist."""
        assert "pro" in SUBSCRIPTION_PLANS
        assert "max_5x" in SUBSCRIPTION_PLANS
        assert "max_20x" in SUBSCRIPTION_PLANS

    def test_plan_costs_increasing(self):
        """Test plan costs are in order."""
        assert SUBSCRIPTION_PLANS["pro"]["cost"] < SUBSCRIPTION_PLANS["max_5x"]["cost"]
        assert SUBSCRIPTION_PLANS["max_5x"]["cost"] < SUBSCRIPTION_PLANS["max_20x"]["cost"]

    def test_plan_has_required_fields(self):
        """Test plans have required fields."""
        for _plan_id, plan in SUBSCRIPTION_PLANS.items():
            assert "name" in plan
            assert "cost" in plan
            assert "messages_5h" in plan
