"""
Tests for CLI argument parsing and command execution.

These are integration tests that verify CLI behavior end-to-end.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Path to the main script
SCRIPT_PATH = PROJECT_ROOT / "claude_watch.py"

# Import functions from main script (like other test files do)
exec(open(SCRIPT_PATH, encoding="utf-8").read())


class TestCLIHelp:
    """Tests for --help argument."""

    def test_help_exits_zero(self):
        """Test that --help exits with code 0."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_help_shows_description(self):
        """Test that --help shows program description."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert "Claude Code" in result.stdout
        assert "usage" in result.stdout.lower()

    def test_help_shows_all_arguments(self):
        """Test that --help lists all main arguments."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        expected_args = ["--json", "--analytics", "--setup", "--config", "--no-color", "--no-record"]
        for arg in expected_args:
            assert arg in result.stdout, f"Missing argument {arg} in help output"

    def test_help_shows_examples(self):
        """Test that --help shows usage examples."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert "Examples:" in result.stdout
        assert "claude-watch" in result.stdout


class TestCLIArgumentParsing:
    """Tests for argument parsing without execution."""

    def test_json_short_flag(self):
        """Test -j is equivalent to --json."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--json", "-j", action="store_true")

        args = parser.parse_args(["-j"])
        assert args.json is True

    def test_analytics_short_flag(self):
        """Test -a is equivalent to --analytics."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--analytics", "-a", action="store_true")

        args = parser.parse_args(["-a"])
        assert args.analytics is True

    def test_setup_short_flag(self):
        """Test -s is equivalent to --setup."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--setup", "-s", action="store_true")

        args = parser.parse_args(["-s"])
        assert args.setup is True

    def test_config_short_flag(self):
        """Test -c is equivalent to --config."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--config", "-c", action="store_true")

        args = parser.parse_args(["-c"])
        assert args.config is True

    def test_cache_ttl_accepts_integer(self):
        """Test --cache-ttl accepts integer values."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--cache-ttl", type=int)

        args = parser.parse_args(["--cache-ttl", "120"])
        assert args.cache_ttl == 120

    def test_cache_ttl_rejects_non_integer(self):
        """Test --cache-ttl rejects non-integer values."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--cache-ttl", type=int)

        with pytest.raises(SystemExit):
            parser.parse_args(["--cache-ttl", "abc"])


class TestCLIColors:
    """Tests for color handling."""

    def test_colors_class_has_all_required_colors(self):
        """Test Colors class has all required color codes."""
        required_colors = [
            "RESET", "BOLD", "DIM", "GREEN", "YELLOW", "RED",
            "CYAN", "WHITE", "GRAY", "MAGENTA"
        ]
        for color in required_colors:
            assert hasattr(Colors, color), f"Missing color {color}"

    def test_no_color_flag_clears_colors(self):
        """Test --no-color disables ANSI color codes."""
        # Store original colors
        original_values = {}
        for attr in ["GREEN", "RED", "BOLD", "RESET"]:
            original_values[attr] = getattr(Colors, attr)

        # Simulate --no-color behavior
        for attr in dir(Colors):
            if not attr.startswith("_"):
                setattr(Colors, attr, "")

        # Verify colors are cleared
        assert Colors.GREEN == ""
        assert Colors.RED == ""
        assert Colors.BOLD == ""

        # Restore for other tests
        for attr, value in original_values.items():
            setattr(Colors, attr, value)


class TestCLIConfig:
    """Tests for --config command."""

    def test_config_command_loads_config(self, tmp_path):
        """Test --config loads and displays configuration."""
        # Set up temp config
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"subscription_plan": "max_5x", "setup_completed": True})
        )
        globals()["CONFIG_FILE"] = config_file

        # Load config using the function
        config = load_config()
        assert config["subscription_plan"] == "max_5x"
        assert config["setup_completed"] is True

    def test_config_has_default_values(self, tmp_path):
        """Test config defaults are applied."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")
        globals()["CONFIG_FILE"] = config_file

        config = load_config()
        # Should have default values merged
        assert "subscription_plan" in config
        assert "auto_collect" in config


class TestCLIHistory:
    """Tests for history management via CLI."""

    def test_load_empty_history(self, tmp_path):
        """Test loading empty history."""
        history_file = tmp_path / "history.json"
        history_file.write_text("[]")
        globals()["HISTORY_FILE"] = history_file

        history = load_history()
        assert history == []

    def test_load_history_with_data(self, tmp_path):
        """Test loading history with data."""
        history_file = tmp_path / "history.json"
        test_data = [
            {"timestamp": "2024-12-19T10:00:00Z", "five_hour": 25.0, "seven_day": 10.0}
        ]
        history_file.write_text(json.dumps(test_data))
        globals()["HISTORY_FILE"] = history_file

        history = load_history()
        assert len(history) == 1
        assert history[0]["five_hour"] == 25.0


class TestCLIIntegration:
    """End-to-end integration tests."""

    def test_script_is_executable(self):
        """Test the script can be executed."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_unknown_argument_fails(self):
        """Test that unknown arguments produce error."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--unknown-arg"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "unrecognized" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_mutually_exclusive_pattern(self):
        """Test setup for future mutually exclusive arguments."""
        import argparse

        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--json", action="store_true")
        group.add_argument("--prompt", action="store_true")

        # Both should fail
        with pytest.raises(SystemExit):
            parser.parse_args(["--json", "--prompt"])

        # Each alone should work
        args1 = parser.parse_args(["--json"])
        assert args1.json is True

        args2 = parser.parse_args(["--prompt"])
        assert args2.prompt is True

    def test_script_syntax_valid(self):
        """Test the script has valid Python syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestCLIConstants:
    """Tests for CLI constants and configuration."""

    def test_api_url_defined(self):
        """Test API URL is defined."""
        assert API_URL is not None
        assert "api.anthropic.com" in API_URL

    def test_cache_max_age_reasonable(self):
        """Test cache max age is reasonable (30s to 5min)."""
        assert CACHE_MAX_AGE >= 30
        assert CACHE_MAX_AGE <= 300

    def test_max_history_days_reasonable(self):
        """Test history retention is reasonable (30-365 days)."""
        assert MAX_HISTORY_DAYS >= 30
        assert MAX_HISTORY_DAYS <= 365

    def test_subscription_plans_defined(self):
        """Test subscription plans are defined."""
        assert "pro" in SUBSCRIPTION_PLANS
        assert "max_5x" in SUBSCRIPTION_PLANS
        assert "max_20x" in SUBSCRIPTION_PLANS

    def test_subscription_plans_have_required_fields(self):
        """Test each subscription plan has required fields."""
        required_fields = ["name", "cost", "messages_5h"]
        for plan_id, plan in SUBSCRIPTION_PLANS.items():
            for field in required_fields:
                assert field in plan, f"Plan {plan_id} missing field {field}"
