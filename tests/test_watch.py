"""Tests for watch mode display functions."""

import pytest
from unittest.mock import patch
import platform

from claude_watch.display.watch import (
    clear_screen,
    format_duration,
    format_countdown,
    calculate_delta,
    format_delta,
    print_watch_header,
    print_watch_summary,
)


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds_only(self):
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        assert format_duration(3725) == "1h 2m 5s"

    def test_zero_seconds(self):
        assert format_duration(0) == "0s"

    def test_exact_hour(self):
        assert format_duration(3600) == "1h 0m 0s"


class TestFormatCountdown:
    """Tests for format_countdown function."""

    def test_positive_seconds(self):
        assert format_countdown(30) == "30s"

    def test_one_second(self):
        assert format_countdown(1) == "1s"

    def test_zero_seconds(self):
        assert format_countdown(0) == "refreshing..."

    def test_negative_seconds(self):
        assert format_countdown(-1) == "refreshing..."


class TestCalculateDelta:
    """Tests for calculate_delta function."""

    def test_positive_delta(self):
        initial = {"five_hour": {"utilization": 30}}
        current = {"five_hour": {"utilization": 45}}
        assert calculate_delta(initial, current) == 15

    def test_negative_delta(self):
        initial = {"five_hour": {"utilization": 50}}
        current = {"five_hour": {"utilization": 40}}
        assert calculate_delta(initial, current) == -10

    def test_zero_delta(self):
        initial = {"five_hour": {"utilization": 30}}
        current = {"five_hour": {"utilization": 30}}
        assert calculate_delta(initial, current) == 0

    def test_missing_initial_data(self):
        initial = {}
        current = {"five_hour": {"utilization": 45}}
        assert calculate_delta(initial, current) is None

    def test_missing_current_data(self):
        initial = {"five_hour": {"utilization": 30}}
        current = {}
        assert calculate_delta(initial, current) is None

    def test_none_five_hour(self):
        initial = {"five_hour": None}
        current = {"five_hour": {"utilization": 45}}
        assert calculate_delta(initial, current) is None


class TestFormatDelta:
    """Tests for format_delta function."""

    def test_positive_delta(self):
        result = format_delta(5.5)
        assert "+5.5%" in result

    def test_negative_delta(self):
        result = format_delta(-3.2)
        assert "-3.2%" in result

    def test_zero_delta(self):
        result = format_delta(0)
        assert "±0.0%" in result

    def test_none_delta(self):
        assert format_delta(None) == ""


class TestClearScreen:
    """Tests for clear_screen function."""

    @patch('os.system')
    @patch('platform.system')
    def test_windows_uses_cls(self, mock_platform, mock_system):
        mock_platform.return_value = "Windows"
        clear_screen()
        mock_system.assert_called_once_with("cls")

    @patch('sys.stdout')
    @patch('platform.system')
    def test_unix_uses_ansi(self, mock_platform, mock_stdout):
        mock_platform.return_value = "Linux"
        clear_screen()
        mock_stdout.write.assert_called()
        mock_stdout.flush.assert_called()


class TestPrintWatchHeader:
    """Tests for print_watch_header function."""

    def test_header_includes_interval(self, capsys):
        print_watch_header(30, 15, 120)
        captured = capsys.readouterr()
        assert "Interval: 30s" in captured.out

    def test_header_includes_countdown(self, capsys):
        print_watch_header(30, 15, 120)
        captured = capsys.readouterr()
        assert "Refresh: 15s" in captured.out

    def test_header_includes_session(self, capsys):
        print_watch_header(30, 15, 120)
        captured = capsys.readouterr()
        assert "Session:" in captured.out

    def test_header_includes_delta_when_provided(self, capsys):
        print_watch_header(30, 15, 120, delta=5.0)
        captured = capsys.readouterr()
        assert "Delta:" in captured.out
        assert "+5.0%" in captured.out


class TestPrintWatchSummary:
    """Tests for print_watch_summary function."""

    def test_summary_shows_duration(self, capsys):
        print_watch_summary(3600, 10, None, None)
        captured = capsys.readouterr()
        assert "Duration: 1h" in captured.out

    def test_summary_shows_refresh_count(self, capsys):
        print_watch_summary(100, 5, None, None)
        captured = capsys.readouterr()
        assert "Refreshes: 5" in captured.out

    def test_summary_shows_delta_when_data_provided(self, capsys):
        initial = {"five_hour": {"utilization": 30}}
        final = {"five_hour": {"utilization": 45}}
        print_watch_summary(100, 5, initial, final)
        captured = capsys.readouterr()
        assert "Usage change:" in captured.out
        assert "+15.0%" in captured.out

    def test_summary_without_data(self, capsys):
        print_watch_summary(100, 5, None, None)
        captured = capsys.readouterr()
        assert "Watch Session Summary" in captured.out
        assert "Usage change:" not in captured.out
