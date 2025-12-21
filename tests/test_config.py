"""
Tests for configuration management functions.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import claude_watch.config.settings as settings_module
from claude_watch.config.settings import (
    CONFIG_FILE,
    CONFIG_VERSION,
    DEFAULT_CONFIG,
    load_config,
    migrate_config,
    save_config,
    validate_config,
)
from claude_watch.setup.wizard import prompt_input, prompt_yes_no


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_default_when_no_file(self, tmp_path):
        """Test returns default config when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.json"

        result = load_config(config_file=nonexistent)
        assert result == DEFAULT_CONFIG

    def test_loads_existing_config(self, tmp_path):
        """Test loading existing config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"subscription_plan": "max_5x", "setup_completed": True}))

        result = load_config(config_file=config_file, silent=True)
        assert result["subscription_plan"] == "max_5x"

    def test_merges_with_defaults(self, tmp_path):
        """Test that loaded config is merged with defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"subscription_plan": "max_5x"}))

        result = load_config(config_file=config_file, silent=True)
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

        save_config({"test": "value"}, config_file=config_file)

        assert config_file.exists()

    def test_saves_json(self, tmp_path):
        """Test that config is saved as valid JSON."""
        config_file = tmp_path / "config.json"

        save_config({"subscription_plan": "pro", "auto_collect": True}, config_file=config_file)

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

        save_config({"admin_api_key": "secret"}, config_file=config_file)

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

        load_config(config_file=config_file)

        captured = capsys.readouterr()
        assert "Warning: Config validation errors" in captured.err
        assert "Unknown config key" in captured.err

    def test_load_config_can_skip_validation(self, tmp_path, capsys):
        """Test that validation can be disabled."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"unknown_key": "value"}))

        load_config(config_file=config_file, validate=False, auto_migrate=False)

        captured = capsys.readouterr()
        assert captured.err == ""


class TestMigrateConfig:
    """Tests for config migration functionality."""

    def test_v1_config_migrated_to_v2(self):
        """Test that v1 config (missing shell_completion_installed) is migrated."""
        v1_config = {
            "admin_api_key": "test-key",
            "use_admin_api": True,
            "auto_collect": False,
            "collect_interval_hours": 2,
            "setup_completed": True,
            "subscription_plan": "pro",
        }

        migrated, was_migrated = migrate_config(v1_config)

        assert was_migrated is True
        assert "shell_completion_installed" in migrated
        assert migrated["shell_completion_installed"] is False
        assert migrated["_config_version"] == CONFIG_VERSION
        # Original values preserved
        assert migrated["admin_api_key"] == "test-key"
        assert migrated["use_admin_api"] is True
        assert migrated["subscription_plan"] == "pro"

    def test_current_config_not_migrated(self):
        """Test that current version config is not migrated."""
        current_config = {
            "admin_api_key": "test-key",
            "use_admin_api": True,
            "auto_collect": False,
            "collect_interval_hours": 2,
            "setup_completed": True,
            "subscription_plan": "pro",
            "shell_completion_installed": True,
            "_config_version": CONFIG_VERSION,
        }

        migrated, was_migrated = migrate_config(current_config)

        assert was_migrated is False
        assert migrated == current_config

    def test_partial_v1_config_migrated(self):
        """Test migration of minimal v1 config."""
        minimal_config = {"subscription_plan": "max_5x"}

        migrated, was_migrated = migrate_config(minimal_config)

        assert was_migrated is True
        assert "shell_completion_installed" in migrated
        assert migrated["_config_version"] == CONFIG_VERSION

    def test_already_has_shell_completion_not_migrated(self):
        """Test config with shell_completion but no version marker."""
        config_with_field = {
            "subscription_plan": "pro",
            "shell_completion_installed": True,
        }

        migrated, was_migrated = migrate_config(config_with_field)

        # No migration needed since field already exists
        assert was_migrated is False

    def test_load_config_auto_migrates(self, tmp_path, capsys):
        """Test that load_config automatically migrates old configs."""
        config_file = tmp_path / "config.json"
        v1_config = {
            "admin_api_key": "test-key",
            "use_admin_api": True,
            "subscription_plan": "pro",
        }
        config_file.write_text(json.dumps(v1_config))

        result = load_config(config_file=config_file)

        # Check migration message printed
        captured = capsys.readouterr()
        assert "Config migrated to version" in captured.err

        # Check config was updated
        assert result["shell_completion_installed"] is False

        # Check file was saved with migration
        saved_config = json.loads(config_file.read_text())
        assert saved_config["_config_version"] == CONFIG_VERSION

    def test_load_config_can_skip_migration(self, tmp_path, capsys):
        """Test that auto_migrate=False skips migration."""
        config_file = tmp_path / "config.json"
        v1_config = {"subscription_plan": "pro"}
        config_file.write_text(json.dumps(v1_config))

        load_config(config_file=config_file, auto_migrate=False, validate=False)

        # No migration message
        captured = capsys.readouterr()
        assert captured.err == ""

        # Config not modified on disk
        saved_config = json.loads(config_file.read_text())
        assert "_config_version" not in saved_config
