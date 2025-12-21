"""
Tests for display formatting functions.
"""

from claude_watch.display.analytics import format_trend, make_sparkline
from claude_watch.display.colors import Colors
from claude_watch.display.progress import (
    format_percentage,
    get_usage_color,
    make_progress_bar,
)


class TestProgressBar:
    """Tests for make_progress_bar function."""

    def test_zero_percent(self):
        """Test progress bar at 0%."""
        bar = make_progress_bar(0)
        # Should have no filled blocks
        assert "█" not in bar or bar.count("█") == 0

    def test_full_percent(self):
        """Test progress bar at 100%."""
        bar = make_progress_bar(100)
        # Should have all filled blocks
        assert "░" not in bar or bar.count("░") == 0

    def test_half_percent(self):
        """Test progress bar at 50%."""
        bar = make_progress_bar(50, width=20)
        # Should have approximately half filled
        filled = bar.count("█")
        assert 8 <= filled <= 12  # Allow some variance

    def test_custom_width(self):
        """Test progress bar with custom width."""
        bar = make_progress_bar(50, width=10)
        # Total blocks should be 10
        total_blocks = bar.count("█") + bar.count("░")
        assert total_blocks == 10


class TestUsageColor:
    """Tests for get_usage_color function."""

    def test_low_usage_green(self):
        """Test low usage returns green color."""
        color = get_usage_color(25)
        assert color == Colors.GREEN

    def test_medium_usage_yellow(self):
        """Test medium usage returns yellow color."""
        color = get_usage_color(60)
        assert color == Colors.YELLOW

    def test_high_usage_red(self):
        """Test high usage returns red color."""
        color = get_usage_color(85)
        assert color == Colors.RED

    def test_boundary_50(self):
        """Test boundary at 50%."""
        assert get_usage_color(49) == Colors.GREEN
        assert get_usage_color(50) == Colors.YELLOW

    def test_boundary_80(self):
        """Test boundary at 80%."""
        assert get_usage_color(79) == Colors.YELLOW
        assert get_usage_color(80) == Colors.RED


class TestFormatPercentage:
    """Tests for format_percentage function."""

    def test_format_integer(self):
        """Test percentage formats as integer."""
        result = format_percentage(45.7)
        assert "45%" in result

    def test_includes_used_suffix(self):
        """Test percentage includes 'used' suffix."""
        result = format_percentage(30)
        assert "used" in result


class TestSparkline:
    """Tests for make_sparkline function."""

    def test_empty_values(self):
        """Test sparkline with empty values."""
        result = make_sparkline([])
        if isinstance(result, tuple):
            sparkline, _ = result
        else:
            sparkline = result
        assert "─" in sparkline

    def test_single_value(self):
        """Test sparkline with single value."""
        result = make_sparkline([50])
        if isinstance(result, tuple):
            sparkline, _ = result
        else:
            sparkline = result
        # Should have at least one character
        assert len(sparkline.replace(Colors.CYAN, "").replace(Colors.RESET, "")) >= 1

    def test_increasing_values(self):
        """Test sparkline with increasing values."""
        values = [10, 20, 30, 40, 50]
        result = make_sparkline(values)
        if isinstance(result, tuple):
            sparkline, _ = result
        else:
            sparkline = result
        # Should show increasing pattern
        chars = sparkline.replace(Colors.CYAN, "").replace(Colors.RESET, "")
        assert len(chars) == len(values)

    def test_with_timestamps(self):
        """Test sparkline with timestamps."""
        values = [10, 20, 30]
        timestamps = [
            "2024-12-19T10:00:00+00:00",
            "2024-12-19T11:00:00+00:00",
            "2024-12-19T12:00:00+00:00",
        ]
        sparkline, time_axis = make_sparkline(values, timestamps, period_hours=24)
        assert isinstance(sparkline, str)
        assert isinstance(time_axis, str)


class TestFormatTrend:
    """Tests for format_trend function."""

    def test_increase(self):
        """Test upward trend."""
        result = format_trend(50, 40)
        assert "↑" in result

    def test_decrease(self):
        """Test downward trend."""
        result = format_trend(40, 50)
        assert "↓" in result

    def test_stable(self):
        """Test stable trend."""
        result = format_trend(50, 50)
        assert "→" in result

    def test_no_previous(self):
        """Test with no previous value."""
        result = format_trend(50, None)
        assert result == ""

    def test_zero_previous(self):
        """Test with zero previous value."""
        result = format_trend(50, 0)
        assert result == ""
