"""Tests for update system functionality."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import URLError

import pytest

# Load the script as a module
script_path = Path(__file__).parent.parent / "claude_watch.py"
exec(compile(script_path.read_text(), script_path, "exec"))

# Save reference to module functions for patching
_module_globals = globals()


class TestParseVersion:
    """Test semantic version parsing."""

    def test_simple_version(self):
        result = parse_version("1.2.3")
        assert result == (1, 2, 3, "")

    def test_version_with_prerelease(self):
        result = parse_version("1.0.0-beta.1")
        assert result == (1, 0, 0, "beta.1")

    def test_version_with_alpha(self):
        result = parse_version("2.0.0-alpha.2")
        assert result == (2, 0, 0, "alpha.2")

    def test_major_only_affects_first(self):
        result = parse_version("10.0.0")
        assert result == (10, 0, 0, "")

    def test_double_digit_minor(self):
        result = parse_version("0.10.0")
        assert result == (0, 10, 0, "")

    def test_double_digit_patch(self):
        result = parse_version("0.0.15")
        assert result == (0, 0, 15, "")

    def test_invalid_version_returns_fallback(self):
        result = parse_version("invalid")
        assert result == (0, 0, 0, "invalid")


class TestCompareVersions:
    """Test version comparison logic."""

    def test_equal_versions(self):
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_v1_less_than_v2_patch(self):
        assert compare_versions("1.0.0", "1.0.1") == -1

    def test_v1_greater_than_v2_patch(self):
        assert compare_versions("1.0.2", "1.0.1") == 1

    def test_v1_less_than_v2_minor(self):
        assert compare_versions("1.0.0", "1.1.0") == -1

    def test_v1_greater_than_v2_minor(self):
        assert compare_versions("1.2.0", "1.1.0") == 1

    def test_v1_less_than_v2_major(self):
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_v1_greater_than_v2_major(self):
        assert compare_versions("3.0.0", "2.0.0") == 1

    def test_double_digit_minor_comparison(self):
        """0.10.0 should be greater than 0.9.0"""
        assert compare_versions("0.9.0", "0.10.0") == -1

    def test_stable_greater_than_prerelease(self):
        """Stable 1.0.0 should be greater than 1.0.0-beta.1"""
        assert compare_versions("1.0.0", "1.0.0-beta.1") == 1

    def test_prerelease_less_than_stable(self):
        """Prerelease 1.0.0-beta.1 should be less than stable 1.0.0"""
        assert compare_versions("1.0.0-beta.1", "1.0.0") == -1

    def test_prerelease_comparison(self):
        """alpha.1 < beta.1 (string comparison)"""
        assert compare_versions("1.0.0-alpha.1", "1.0.0-beta.1") == -1

    def test_same_prerelease(self):
        assert compare_versions("1.0.0-beta.1", "1.0.0-beta.1") == 0


class TestDetectInstallationMethod:
    """Test installation method detection."""

    @patch("subprocess.run")
    def test_detects_uv_installation(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "claude-watch 0.1.0\n  python\n"
        mock_run.return_value = mock_result

        result = detect_installation_method()
        assert result == "uv"

    @patch("subprocess.run")
    def test_detects_pipx_installation(self, mock_run):
        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "uv":
                result.returncode = 0
                result.stdout = "other-package 1.0.0"  # no claude-watch
            elif cmd[0] == "pipx":
                result.returncode = 0
                result.stdout = "claude-watch 0.1.0"
            return result

        mock_run.side_effect = side_effect

        result = detect_installation_method()
        assert result == "pipx"

    @patch("subprocess.run")
    def test_returns_none_when_not_found(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "other-package 1.0.0"
        mock_run.return_value = mock_result

        # Patch importlib to not find the module
        with patch("importlib.util.find_spec", return_value=None):
            result = detect_installation_method()
            assert result is None


class TestFetchLatestVersion:
    """Test PyPI version fetching - integration-style tests."""

    def test_pypi_url_is_correct(self):
        """Verify PyPI URL is properly formatted."""
        assert PYPI_URL == "https://pypi.org/pypi/claude-watch/json"

    def test_function_handles_network_failure_gracefully(self):
        """Test that network failures return None, not raise."""
        # This will fail because package isn't on PyPI - that's expected
        result = fetch_latest_version()
        # Should return None on any failure, not raise
        assert result is None or isinstance(result, str)

    def test_function_returns_string_or_none(self):
        """Test return type is correct."""
        result = fetch_latest_version()
        assert result is None or isinstance(result, str)


class TestRunUpgrade:
    """Test upgrade command execution."""

    @patch("subprocess.run")
    def test_uv_upgrade_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        success, message = run_upgrade("uv")
        assert success is True
        assert "uv" in message

    @patch("subprocess.run")
    def test_pipx_upgrade_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        success, message = run_upgrade("pipx")
        assert success is True
        assert "pipx" in message

    @patch("subprocess.run")
    def test_upgrade_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Package not found"
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        success, message = run_upgrade("uv")
        assert success is False
        assert "failed" in message.lower()

    def test_unknown_method(self):
        success, message = run_upgrade("unknown")
        assert success is False
        assert "Unknown" in message


class TestCheckForUpdate:
    """Test update check functionality - logic tests."""

    def test_returns_none_when_pypi_unreachable(self):
        """Test that check_for_update returns None when PyPI is unreachable."""
        # Package isn't on PyPI so fetch_latest_version will return None
        result = check_for_update(quiet=True)
        assert result is None

    def test_no_update_when_current_is_latest(self):
        """Test update logic with same version."""
        current = "0.1.0"
        latest = "0.1.0"
        update_available = compare_versions(current, latest) < 0
        assert update_available is False

    def test_update_available_when_newer(self):
        """Test update logic with newer version."""
        current = "0.1.0"
        latest = "0.2.0"
        update_available = compare_versions(current, latest) < 0
        assert update_available is True

    def test_no_update_when_current_is_newer(self):
        """Test update logic when current is dev version ahead of release."""
        current = "0.3.0"
        latest = "0.2.0"
        update_available = compare_versions(current, latest) < 0
        assert update_available is False


class TestRunUpdate:
    """Test run_update function behavior."""

    def test_returns_exit_code(self):
        """Test that run_update returns an integer exit code."""
        # Will return 1 because PyPI is unreachable
        exit_code = run_update(check_only=True)
        assert isinstance(exit_code, int)
        # Should be 1 (error) since package isn't on PyPI
        assert exit_code == 1
