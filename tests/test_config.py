"""
Tests for configuration management functions.
"""

import json
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions from main script
exec(open(Path(__file__).parent.parent / "claude_watch.py", encoding="utf-8").read())


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_default_when_no_file(self, tmp_path):
        """Test returns default config when file doesn't exist."""
        # Point CONFIG_FILE to a nonexistent path
        nonexistent = tmp_path / "nonexistent.json"
        globals()["CONFIG_FILE"] = nonexistent

        result = load_config()
        assert result == DEFAULT_CONFIG

    def test_loads_existing_config(self, tmp_path):
        """Test loading existing config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"subscription_plan": "max_5x", "setup_completed": True}))
        globals()["CONFIG_FILE"] = config_file

        result = load_config()
        assert result["subscription_plan"] == "max_5x"

    def test_merges_with_defaults(self, tmp_path):
        """Test that loaded config is merged with defaults."""
        # Create partial config
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"subscription_plan": "max_5x"}))
        globals()["CONFIG_FILE"] = config_file

        result = load_config()
        # Should have the custom value
        assert result["subscription_plan"] == "max_5x"
        # Should have default values for missing keys
        assert "admin_api_key" in result
        assert "auto_collect" in result
        assert result["admin_api_key"] is None  # Default value


class TestSaveConfig:
    """Tests for save_config function."""

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created."""
        config_file = tmp_path / "subdir" / "config.json"
        globals()["CONFIG_FILE"] = config_file

        save_config({"test": "value"})

        assert config_file.exists()

    def test_saves_json(self, tmp_path):
        """Test that config is saved as valid JSON."""
        config_file = tmp_path / "config.json"
        globals()["CONFIG_FILE"] = config_file

        save_config({"subscription_plan": "pro", "auto_collect": True})

        # Read and parse
        loaded = json.loads(config_file.read_text())
        assert loaded["subscription_plan"] == "pro"
        assert loaded["auto_collect"] is True

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Unix permissions not applicable on Windows"
    )
    def test_sets_file_permissions(self, tmp_path):
        """Test that config file has secure permissions."""
        config_file = tmp_path / "config.json"
        globals()["CONFIG_FILE"] = config_file

        save_config({"admin_api_key": "secret"})

        # Check file permissions (0o600 = owner read/write only)
        mode = config_file.stat().st_mode
        assert mode & 0o777 == 0o600


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
            "subscription_plan",
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


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config_returns_empty_list(self):
        """Test that valid config returns no errors."""
        valid_config = {
            "admin_api_key": "sk-ant-test",
            "use_admin_api": True,
            "auto_collect": False,
            "collect_interval_hours": 1,
            "setup_completed": True,
            "subscription_plan": "pro",
            "shell_completion_installed": False,
        }
        errors = validate_config(valid_config)
        assert errors == []

    def test_valid_config_with_null_api_key(self):
        """Test that null api_key is valid."""
        config = {"admin_api_key": None}
        errors = validate_config(config)
        assert errors == []

    def test_empty_config_is_valid(self):
        """Test that empty config (all defaults) is valid."""
        errors = validate_config({})
        assert errors == []

    def test_unknown_key_reports_error(self):
        """Test that unknown keys are reported."""
        config = {"unknown_key": "value"}
        errors = validate_config(config)
        assert len(errors) == 1
        assert "Unknown config key: 'unknown_key'" in errors[0]

    def test_invalid_type_reports_error(self):
        """Test that wrong types are reported."""
        config = {"use_admin_api": "not a bool"}
        errors = validate_config(config)
        assert len(errors) == 1
        assert "'use_admin_api' has invalid type" in errors[0]

    def test_invalid_subscription_plan(self):
        """Test that invalid subscription plan is reported."""
        config = {"subscription_plan": "invalid_plan"}
        errors = validate_config(config)
        assert len(errors) == 1
        assert "'subscription_plan'" in errors[0]
        assert "must be one of" in errors[0]

    def test_invalid_collect_interval(self):
        """Test that out-of-range interval is reported."""
        config = {"collect_interval_hours": 48}
        errors = validate_config(config)
        assert len(errors) == 1
        assert "'collect_interval_hours'" in errors[0]
        assert "must be between 0 and 24" in errors[0]

    def test_zero_collect_interval_invalid(self):
        """Test that zero interval is invalid."""
        config = {"collect_interval_hours": 0}
        errors = validate_config(config)
        assert len(errors) == 1

    def test_multiple_errors(self):
        """Test that multiple errors are collected."""
        config = {
            "unknown_key": "value",
            "use_admin_api": "not a bool",
            "subscription_plan": "invalid",
        }
        errors = validate_config(config)
        assert len(errors) == 3

    def test_float_interval_is_valid(self):
        """Test that float interval values are accepted."""
        config = {"collect_interval_hours": 0.5}
        errors = validate_config(config)
        assert errors == []

    def test_empty_string_api_key_invalid(self):
        """Test that empty string api_key is invalid."""
        config = {"admin_api_key": ""}
        errors = validate_config(config)
        assert len(errors) == 1
        assert "'admin_api_key'" in errors[0]


class TestLoadConfigValidation:
    """Tests for load_config with validation."""

    def test_load_config_validates_by_default(self, tmp_path, capsys):
        """Test that load_config validates and warns on errors."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"unknown_key": "value"}))
        globals()["CONFIG_FILE"] = config_file

        load_config()

        captured = capsys.readouterr()
        assert "Warning: Config validation errors" in captured.err
        assert "Unknown config key" in captured.err

    def test_load_config_can_skip_validation(self, tmp_path, capsys):
        """Test that validation can be disabled."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"unknown_key": "value"}))
        globals()["CONFIG_FILE"] = config_file

        load_config(validate=False)

        captured = capsys.readouterr()
        assert captured.err == ""
