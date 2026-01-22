"""Tests for tmux status bar output formatting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from claude_watch.display.tmux import (
    format_tmux,
    format_tmux_minimal,
    get_tmux_color,
)


class TestGetTmuxColor:
    """Tests for get_tmux_color function."""

    # Dracula theme colors
    GREEN = "#50fa7b"
    YELLOW = "#f1fa8c"
    RED = "#ff5555"

    def test_low_usage_returns_green(self):
        assert get_tmux_color(0) == self.GREEN
        assert get_tmux_color(50) == self.GREEN
        assert get_tmux_color(74) == self.GREEN

    def test_medium_usage_returns_yellow(self):
        assert get_tmux_color(75) == self.YELLOW
        assert get_tmux_color(80) == self.YELLOW
        assert get_tmux_color(89) == self.YELLOW

    def test_high_usage_returns_red(self):
        assert get_tmux_color(90) == self.RED
        assert get_tmux_color(95) == self.RED
        assert get_tmux_color(100) == self.RED


class TestFormatTmux:
    """Tests for format_tmux function."""

    def test_basic_format_includes_session_and_weekly(self):
        data = {
            "five_hour": {"utilization": 45, "resets_at": ""},
            "seven_day": {"utilization": 12},
        }
        result = format_tmux(data)
        assert "S:45%" in result
        assert "W:12%" in result

    def test_includes_tmux_color_codes(self):
        data = {
            "five_hour": {"utilization": 45, "resets_at": ""},
            "seven_day": {"utilization": 12},
        }
        result = format_tmux(data)
        # Uses Dracula theme hex colors
        assert "#[fg=#50fa7b]" in result  # Green
        assert "#[default]" in result

    def test_color_reflects_session_usage(self):
        # Green session (Dracula: #50fa7b)
        data_low = {
            "five_hour": {"utilization": 30, "resets_at": ""},
            "seven_day": {"utilization": 10},
        }
        assert "#[fg=#50fa7b]S:30%" in format_tmux(data_low)

        # Yellow session (Dracula: #f1fa8c)
        data_mid = {
            "five_hour": {"utilization": 80, "resets_at": ""},
            "seven_day": {"utilization": 10},
        }
        assert "#[fg=#f1fa8c]S:80%" in format_tmux(data_mid)

        # Red session (Dracula: #ff5555)
        data_high = {
            "five_hour": {"utilization": 95, "resets_at": ""},
            "seven_day": {"utilization": 10},
        }
        assert "#[fg=#ff5555]S:95%" in format_tmux(data_high)

    def test_color_reflects_weekly_usage(self):
        # Green weekly (Dracula: #50fa7b)
        data = {
            "five_hour": {"utilization": 50, "resets_at": ""},
            "seven_day": {"utilization": 30},
        }
        assert "#[fg=#50fa7b]W:30%" in format_tmux(data)

        # Red weekly (Dracula: #ff5555)
        data_high = {
            "five_hour": {"utilization": 50, "resets_at": ""},
            "seven_day": {"utilization": 95},
        }
        assert "#[fg=#ff5555]W:95%" in format_tmux(data_high)

    def test_includes_reset_time_when_present(self):
        # Create a reset time 2 hours from now
        reset_time = datetime.now(timezone.utc) + timedelta(hours=2, minutes=15)
        data = {
            "five_hour": {
                "utilization": 45,
                "resets_at": reset_time.isoformat().replace("+00:00", "Z"),
            },
            "seven_day": {"utilization": 12},
        }
        result = format_tmux(data)
        # Should include compact reset time like "2h15m"
        assert "2h" in result or "1h" in result  # Allow for timing variance

    def test_ends_with_default_reset(self):
        data = {
            "five_hour": {"utilization": 45, "resets_at": ""},
            "seven_day": {"utilization": 12},
        }
        result = format_tmux(data)
        assert result.endswith("#[default]")

    def test_handles_empty_data(self):
        data = {}
        result = format_tmux(data)
        assert "S:0%" in result
        assert "W:0%" in result

    def test_handles_none_values(self):
        data = {
            "five_hour": None,
            "seven_day": None,
        }
        result = format_tmux(data)
        assert "S:0%" in result
        assert "W:0%" in result


class TestFormatTmuxMinimal:
    """Tests for format_tmux_minimal function."""

    def test_shows_only_percentage(self):
        data = {
            "five_hour": {"utilization": 45},
        }
        result = format_tmux_minimal(data)
        # Should be like "#[fg=green]45%#[default]"
        assert "45%" in result
        assert "#[default]" in result

    def test_includes_color(self):
        # Dracula theme hex colors
        data = {"five_hour": {"utilization": 45}}
        assert "#[fg=#50fa7b]" in format_tmux_minimal(data)  # Green

        data = {"five_hour": {"utilization": 85}}
        assert "#[fg=#f1fa8c]" in format_tmux_minimal(data)  # Yellow

        data = {"five_hour": {"utilization": 95}}
        assert "#[fg=#ff5555]" in format_tmux_minimal(data)  # Red

    def test_handles_empty_data(self):
        result = format_tmux_minimal({})
        assert "0%" in result
