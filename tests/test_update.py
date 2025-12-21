"""
Tests for update checking functions.

Tests cover:
- parse_version() - version string parsing
- compare_versions() - semantic version comparison
- detect_installation_method() - detecting uv/pipx/pip
- check_for_update() - update availability check
"""

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from claude_watch.update.checker import (
    GITHUB_RELEASES_URL,
    GITHUB_REPO,
    check_for_update,
    compare_versions,
    detect_installation_method,
    fetch_latest_version,
    parse_version,
    run_update,
    run_upgrade,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test parse_version()
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseVersion:
    """Tests for parse_version() function."""

    def test_simple_version(self):
        """Test parsing simple version."""
        result = parse_version("1.2.3")
        assert result == (1, 2, 3, "")

    def test_version_with_prerelease(self):
        """Test parsing version with prerelease."""
        result = parse_version("1.0.0-beta.1")
        assert result == (1, 0, 0, "beta.1")

    def test_version_with_alpha(self):
        """Test parsing version with alpha prerelease."""
        result = parse_version("2.0.0-alpha.2")
        assert result == (2, 0, 0, "alpha.2")

    def test_major_only_affects_first(self):
        """Test parsing major version."""
        result = parse_version("10.0.0")
        assert result == (10, 0, 0, "")

    def test_double_digit_minor(self):
        """Test parsing double digit minor version."""
        result = parse_version("0.10.0")
        assert result == (0, 10, 0, "")

    def test_double_digit_patch(self):
        """Test parsing double digit patch version."""
        result = parse_version("0.0.15")
        assert result == (0, 0, 15, "")

    def test_invalid_version_returns_fallback(self):
        """Test parsing invalid version returns fallback."""
        result = parse_version("invalid")
        assert result == (0, 0, 0, "invalid")

    def test_zero_version(self):
        """Test parsing zero version."""
        result = parse_version("0.0.0")
        assert result == (0, 0, 0, "")

    def test_large_numbers(self):
        """Test parsing large version numbers."""
        result = parse_version("100.200.300")
        assert result == (100, 200, 300, "")


# ═══════════════════════════════════════════════════════════════════════════════
# Test compare_versions()
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompareVersions:
    """Tests for compare_versions() function."""

    def test_equal_versions(self):
        """Test comparing equal versions."""
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_v1_less_than_v2_patch(self):
        """Test v1 < v2 (patch difference)."""
        assert compare_versions("1.0.0", "1.0.1") == -1

    def test_v1_greater_than_v2_patch(self):
        """Test v1 > v2 (patch difference)."""
        assert compare_versions("1.0.2", "1.0.1") == 1

    def test_v1_less_than_v2_minor(self):
        """Test v1 < v2 (minor difference)."""
        assert compare_versions("1.0.0", "1.1.0") == -1

    def test_v1_greater_than_v2_minor(self):
        """Test v1 > v2 (minor difference)."""
        assert compare_versions("1.2.0", "1.1.0") == 1

    def test_v1_less_than_v2_major(self):
        """Test v1 < v2 (major difference)."""
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_v1_greater_than_v2_major(self):
        """Test v1 > v2 (major difference)."""
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
        """Test same prerelease versions are equal."""
        assert compare_versions("1.0.0-beta.1", "1.0.0-beta.1") == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test detect_installation_method()
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectInstallationMethod:
    """Tests for detect_installation_method() function."""

    def test_detects_uv_installation(self):
        """Test detecting uv tool installation."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "claude-watch 0.1.0\n  python\n"

        with patch("claude_watch.update.checker.subprocess.run", return_value=mock_result):
            result = detect_installation_method()

        assert result == "uv"

    def test_detects_pipx_installation(self):
        """Test detecting pipx installation."""
        def side_effect(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "uv":
                result.returncode = 0
                result.stdout = "other-package 1.0.0"  # no claude-watch
            elif cmd[0] == "pipx":
                result.returncode = 0
                result.stdout = "claude-watch 0.1.0"
            return result

        with patch("claude_watch.update.checker.subprocess.run", side_effect=side_effect):
            result = detect_installation_method()

        assert result == "pipx"

    def test_returns_none_when_not_found(self):
        """Test returns None when not found in any method."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "other-package 1.0.0"

        with patch("claude_watch.update.checker.subprocess.run", return_value=mock_result):
            with patch("importlib.util.find_spec", return_value=None):
                result = detect_installation_method()

        assert result is None

    def test_pip_detection(self):
        """Test detecting pip installation."""
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""

        mock_spec = MagicMock()
        mock_spec.origin = "/usr/lib/python3.11/site-packages/claude_watch/__init__.py"

        with patch("claude_watch.update.checker.subprocess.run", return_value=fail_result):
            with patch("importlib.util.find_spec", return_value=mock_spec):
                result = detect_installation_method()

        assert result == "pip"

    def test_command_not_found(self):
        """Test when uv/pipx commands are not found."""
        with patch(
            "claude_watch.update.checker.subprocess.run",
            side_effect=FileNotFoundError("Command not found"),
        ):
            with patch("importlib.util.find_spec", return_value=None):
                result = detect_installation_method()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Test fetch_latest_version()
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchLatestVersion:
    """Tests for fetch_latest_version() function."""

    def test_github_url_is_correct(self):
        """Verify GitHub releases URL is properly formatted."""
        assert GITHUB_REPO == "Asi0Flammeus/claude-code-watch"
        assert "api.github.com" in GITHUB_RELEASES_URL
        assert GITHUB_REPO in GITHUB_RELEASES_URL

    def test_successful_fetch(self):
        """Test successful version fetch."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"tag_name": "v0.2.5"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claude_watch.update.checker.urlopen", return_value=mock_response):
            result = fetch_latest_version()

        assert result == "0.2.5"

    def test_strips_v_prefix(self):
        """Test that v prefix is stripped from tag."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"tag_name": "v1.0.0"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claude_watch.update.checker.urlopen", return_value=mock_response):
            result = fetch_latest_version()

        assert result == "1.0.0"

    def test_handles_no_prefix(self):
        """Test handling version without v prefix."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"tag_name": "1.0.0"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claude_watch.update.checker.urlopen", return_value=mock_response):
            result = fetch_latest_version()

        assert result == "1.0.0"

    def test_network_error(self):
        """Test network error returns None."""
        with patch("claude_watch.update.checker.urlopen", side_effect=URLError("Connection refused")):
            result = fetch_latest_version()

        assert result is None

    def test_invalid_json(self):
        """Test invalid JSON returns None."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("claude_watch.update.checker.urlopen", return_value=mock_response):
            result = fetch_latest_version()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Test run_upgrade()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunUpgrade:
    """Tests for run_upgrade() function."""

    def test_uv_upgrade_success(self):
        """Test uv upgrade success."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("claude_watch.update.checker.subprocess.run", return_value=mock_result):
            success, message = run_upgrade("uv")

        assert success is True
        assert "uv" in message

    def test_pipx_upgrade_success(self):
        """Test pipx upgrade success."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("claude_watch.update.checker.subprocess.run", return_value=mock_result):
            success, message = run_upgrade("pipx")

        assert success is True
        assert "pipx" in message

    def test_upgrade_failure(self):
        """Test upgrade failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Package not found"
        mock_result.stdout = ""

        with patch("claude_watch.update.checker.subprocess.run", return_value=mock_result):
            success, message = run_upgrade("uv")

        assert success is False
        assert "failed" in message.lower()

    def test_unknown_method(self):
        """Test unknown installation method."""
        success, message = run_upgrade("unknown")
        assert success is False
        assert "Unknown" in message


# ═══════════════════════════════════════════════════════════════════════════════
# Test check_for_update()
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckForUpdate:
    """Tests for check_for_update() function."""

    def test_no_update_when_current_is_latest(self):
        """Test no update when versions are equal."""
        current = "0.1.0"
        latest = "0.1.0"
        update_available = compare_versions(current, latest) < 0
        assert update_available is False

    def test_update_available_when_newer(self):
        """Test update available when newer version exists."""
        current = "0.1.0"
        latest = "0.2.0"
        update_available = compare_versions(current, latest) < 0
        assert update_available is True

    def test_no_update_when_current_is_newer(self):
        """Test no update when current is dev version ahead of release."""
        current = "0.3.0"
        latest = "0.2.0"
        update_available = compare_versions(current, latest) < 0
        assert update_available is False

    def test_returns_dict_or_none(self):
        """Test check_for_update returns dict or None."""
        with patch("claude_watch.update.checker.fetch_latest_version", return_value="0.2.0"):
            with patch("claude_watch.update.checker.detect_installation_method", return_value="pip"):
                result = check_for_update("0.1.0", quiet=True)

        assert result is not None
        assert isinstance(result, dict)
        assert "current" in result
        assert "latest" in result
        assert "update_available" in result

    def test_returns_none_on_fetch_failure(self):
        """Test returns None when fetch fails."""
        with patch("claude_watch.update.checker.fetch_latest_version", return_value=None):
            result = check_for_update("0.1.0", quiet=True)

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Test run_update()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunUpdate:
    """Tests for run_update() function."""

    def test_returns_exit_code(self):
        """Test that run_update returns an integer exit code."""
        with patch("claude_watch.update.checker.check_for_update", return_value=None):
            exit_code = run_update("0.1.0", check_only=True)

        assert isinstance(exit_code, int)
        assert exit_code == 1  # 1 for error (fetch failed)

    def test_returns_2_when_already_latest(self):
        """Test returns 2 when already on latest version."""
        with patch(
            "claude_watch.update.checker.check_for_update",
            return_value={
                "current": "0.2.0",
                "latest": "0.2.0",
                "update_available": False,
                "method": "pip",
            },
        ):
            exit_code = run_update("0.2.0", check_only=True)

        assert exit_code == 2
