"""
Tests for time parsing and formatting functions.
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions from main script
exec(open(Path(__file__).parent.parent / "claude-watch").read())


class TestParseResetTime:
    """Tests for parse_reset_time function."""

    def test_zulu_format(self):
        """Test parsing ISO format with Z suffix."""
        result = parse_reset_time("2024-12-19T14:30:00Z")
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 19
        assert result.hour == 14
        assert result.minute == 30

    def test_offset_format(self):
        """Test parsing ISO format with timezone offset."""
        result = parse_reset_time("2024-12-19T14:30:00+00:00")
        assert result.tzinfo is not None

    def test_with_milliseconds(self):
        """Test parsing with milliseconds."""
        result = parse_reset_time("2024-12-19T14:30:00.123Z")
        assert result.hour == 14
        assert result.minute == 30


class TestFormatRelativeTime:
    """Tests for format_relative_time function."""

    def test_hours_and_minutes(self):
        """Test formatting hours and minutes."""
        # Create a reset time 2 hours 30 minutes in the future
        future = datetime.now(timezone.utc) + timedelta(hours=2, minutes=30)
        result = format_relative_time(future.isoformat())
        assert "hr" in result or "min" in result

    def test_minutes_only(self):
        """Test formatting minutes only."""
        future = datetime.now(timezone.utc) + timedelta(minutes=45)
        result = format_relative_time(future.isoformat())
        assert "min" in result

    def test_past_time(self):
        """Test handling past time (should show < 1 min)."""
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = format_relative_time(past.isoformat())
        assert "< 1 min" in result or "0" in result


class TestFormatAbsoluteTime:
    """Tests for format_absolute_time function."""

    def test_contains_day(self):
        """Test that result contains day of week."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        result = format_absolute_time(future.isoformat())
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert any(day in result for day in days)

    def test_contains_time(self):
        """Test that result contains time."""
        future = datetime.now(timezone.utc) + timedelta(hours=5)
        result = format_absolute_time(future.isoformat())
        # Should contain AM or PM
        assert "AM" in result or "PM" in result
