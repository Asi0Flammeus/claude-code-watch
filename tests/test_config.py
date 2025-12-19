"""
Tests for configuration management functions.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions from main script
exec(open(Path(__file__).parent.parent / "claude-usage").read())


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_default_when_no_file(self, tmp_path):
        """Test returns default config when file doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            with patch("claude_usage.CONFIG_FILE", tmp_path / "nonexistent.json"):
                # Load should return defaults
                result = load_config()
                assert result == DEFAULT_CONFIG

    def test_loads_existing_config(self, tmp_config_file):
        """Test loading existing config file."""
        with patch("claude_usage.CONFIG_FILE", tmp_config_file):
            result = load_config()
            assert "subscription_plan" in result

    def test_merges_with_defaults(self, tmp_path):
        """Test that loaded config is merged with defaults."""
        # Create partial config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"subscription_plan": "max_5x"}))

        with patch("claude_usage.CONFIG_FILE", config_file):
            result = load_config()
            # Should have the custom value
            assert result["subscription_plan"] == "max_5x"
            # Should have default values for missing keys
            assert "admin_api_key" in result
            assert "auto_collect" in result


class TestSaveConfig:
    """Tests for save_config function."""

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created."""
        config_file = tmp_path / "subdir" / "config.json"

        with patch("claude_usage.CONFIG_FILE", config_file):
            save_config({"test": "value"})

        assert config_file.exists()

    def test_saves_json(self, tmp_path):
        """Test that config is saved as valid JSON."""
        config_file = tmp_path / "config.json"

        with patch("claude_usage.CONFIG_FILE", config_file):
            save_config({"subscription_plan": "pro", "auto_collect": True})

        # Read and parse
        loaded = json.loads(config_file.read_text())
        assert loaded["subscription_plan"] == "pro"
        assert loaded["auto_collect"] is True


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG."""

    def test_has_required_keys(self):
        """Test default config has all required keys."""
        required_keys = [
            "admin_api_key",
            "use_admin_api",
            "auto_collect",
            "collect_interval_hours",
            "setup_completed",
            "subscription_plan"
        ]
        for key in required_keys:
            assert key in DEFAULT_CONFIG

    def test_default_values(self):
        """Test default values are sensible."""
        assert DEFAULT_CONFIG["admin_api_key"] is None
        assert DEFAULT_CONFIG["use_admin_api"] is False
        assert DEFAULT_CONFIG["subscription_plan"] == "pro"
        assert DEFAULT_CONFIG["collect_interval_hours"] == 1


class TestPromptHelpers:
    """Tests for prompt helper functions."""

    def test_prompt_yes_no_default_true(self, monkeypatch):
        """Test yes/no prompt with default True."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = prompt_yes_no("Test?", default=True)
        assert result is True

    def test_prompt_yes_no_default_false(self, monkeypatch):
        """Test yes/no prompt with default False."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = prompt_yes_no("Test?", default=False)
        assert result is False

    def test_prompt_yes_no_explicit_yes(self, monkeypatch):
        """Test yes/no prompt with explicit yes."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        result = prompt_yes_no("Test?")
        assert result is True

    def test_prompt_yes_no_explicit_no(self, monkeypatch):
        """Test yes/no prompt with explicit no."""
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = prompt_yes_no("Test?")
        assert result is False

    def test_prompt_input_with_default(self, monkeypatch):
        """Test input prompt uses default on empty."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = prompt_input("Test?", default="default_value")
        assert result == "default_value"

    def test_prompt_input_with_value(self, monkeypatch):
        """Test input prompt returns entered value."""
        monkeypatch.setattr("builtins.input", lambda _: "custom_value")
        result = prompt_input("Test?", default="default")
        assert result == "custom_value"
