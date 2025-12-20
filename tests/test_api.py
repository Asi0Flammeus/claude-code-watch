"""
Tests for API communication functions.

Tests cover:
- fetch_usage() - OAuth API communication
- get_credentials() - credential loading from file/keychain
- get_access_token() - token extraction
- Error handling (auth, network, parsing)
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

# Import from the executable script
sys.path.insert(0, str(Path(__file__).parent.parent))

# We need to import the module dynamically since it's an executable without .py extension
spec = importlib.util.spec_from_loader(
    "claude_watch",
    loader=None,
    origin=str(Path(__file__).parent.parent / "claude_watch.py"),
)
claude_watch = importlib.util.module_from_spec(spec)

# Execute the module to load its contents
with open(Path(__file__).parent.parent / "claude_watch.py", encoding="utf-8") as f:
    exec(f.read(), claude_watch.__dict__)


# ═══════════════════════════════════════════════════════════════════════════════
# Test fetch_usage()
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchUsage:
    """Tests for fetch_usage() API communication."""

    def test_successful_fetch(self, usage_normal, credentials_valid):
        """Test successful API response parsing."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(usage_normal).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(claude_watch, "get_access_token", return_value="test-token"):
            with patch.object(claude_watch, "urlopen", return_value=mock_response):
                result = claude_watch.fetch_usage()

        assert result["five_hour"]["utilization"] == 34.5
        assert result["seven_day"]["utilization"] == 12.3

    def test_auth_error_401(self, credentials_valid):
        """Test 401 authentication error handling."""
        http_error = HTTPError(
            url="https://api.anthropic.com/api/oauth/usage",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        with patch.object(claude_watch, "get_access_token", return_value="test-token"):
            with patch.object(claude_watch, "urlopen", side_effect=http_error):
                with pytest.raises(RuntimeError) as exc_info:
                    claude_watch.fetch_usage()

        assert "Authentication failed" in str(exc_info.value)
        assert "session may have expired" in str(exc_info.value)

    def test_api_error_500(self, credentials_valid):
        """Test 500 server error handling."""
        http_error = HTTPError(
            url="https://api.anthropic.com/api/oauth/usage",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with patch.object(claude_watch, "get_access_token", return_value="test-token"):
            with patch.object(claude_watch, "urlopen", side_effect=http_error):
                with pytest.raises(RuntimeError) as exc_info:
                    claude_watch.fetch_usage()

        assert "API error: 500" in str(exc_info.value)

    def test_network_error(self, credentials_valid):
        """Test network error handling."""
        url_error = URLError("Connection refused")

        with patch.object(claude_watch, "get_access_token", return_value="test-token"):
            with patch.object(claude_watch, "urlopen", side_effect=url_error):
                with pytest.raises(RuntimeError) as exc_info:
                    claude_watch.fetch_usage()

        assert "Network error" in str(exc_info.value)

    def test_timeout_error(self, credentials_valid):
        """Test request timeout handling."""
        url_error = URLError("timed out")

        with patch.object(claude_watch, "get_access_token", return_value="test-token"):
            with patch.object(claude_watch, "urlopen", side_effect=url_error):
                with pytest.raises(RuntimeError) as exc_info:
                    claude_watch.fetch_usage()

        assert "Network error" in str(exc_info.value)
        assert "timed out" in str(exc_info.value)

    def test_request_headers(self, usage_normal, credentials_valid):
        """Test that correct headers are sent with request."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(usage_normal).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        captured_request = None

        def capture_request(req, **kwargs):
            nonlocal captured_request
            captured_request = req
            return mock_response

        with patch.object(claude_watch, "get_access_token", return_value="test-token"):
            with patch.object(claude_watch, "urlopen", side_effect=capture_request):
                claude_watch.fetch_usage()

        assert captured_request is not None
        assert "Bearer test-token" in captured_request.get_header("Authorization")
        assert captured_request.get_header("Content-type") == "application/json"
        assert "claude-watch" in captured_request.get_header("User-agent")


# ═══════════════════════════════════════════════════════════════════════════════
# Test get_credentials()
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCredentials:
    """Tests for get_credentials() credential loading."""

    def test_load_from_file(self, tmp_path, credentials_valid):
        """Test loading credentials from file."""
        creds_file = tmp_path / ".credentials.json"
        creds_file.write_text(json.dumps(credentials_valid))

        with patch.object(claude_watch, "get_credentials_path", return_value=creds_file):
            with patch.object(claude_watch.platform, "system", return_value="Linux"):
                result = claude_watch.get_credentials()

        assert result["claudeAiOauth"]["accessToken"] == "test-access-token-12345"

    def test_file_not_found(self, tmp_path):
        """Test error when credentials file doesn't exist."""
        non_existent = tmp_path / "nonexistent" / ".credentials.json"

        with patch.object(claude_watch, "get_credentials_path", return_value=non_existent):
            with patch.object(claude_watch.platform, "system", return_value="Linux"):
                with pytest.raises(FileNotFoundError) as exc_info:
                    claude_watch.get_credentials()

        assert "Credentials not found" in str(exc_info.value)
        assert "Claude Code is installed" in str(exc_info.value)

    def test_macos_keychain_fallback(self, tmp_path, credentials_valid):
        """Test macOS keychain is tried first, then file fallback."""
        creds_file = tmp_path / ".credentials.json"
        creds_file.write_text(json.dumps(credentials_valid))

        # Simulate keychain returning None (not found)
        with patch.object(claude_watch.platform, "system", return_value="Darwin"):
            with patch.object(claude_watch, "get_macos_keychain_credentials", return_value=None):
                with patch.object(claude_watch, "get_credentials_path", return_value=creds_file):
                    result = claude_watch.get_credentials()

        assert result["claudeAiOauth"]["accessToken"] == "test-access-token-12345"

    def test_macos_keychain_success(self, credentials_valid):
        """Test macOS keychain returns credentials successfully."""
        with patch.object(claude_watch.platform, "system", return_value="Darwin"):
            with patch.object(
                claude_watch,
                "get_macos_keychain_credentials",
                return_value=credentials_valid,
            ):
                result = claude_watch.get_credentials()

        assert result["claudeAiOauth"]["accessToken"] == "test-access-token-12345"


# ═══════════════════════════════════════════════════════════════════════════════
# Test get_access_token()
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAccessToken:
    """Tests for get_access_token() token extraction."""

    def test_extract_token(self, credentials_valid):
        """Test extracting access token from credentials."""
        with patch.object(claude_watch, "get_credentials", return_value=credentials_valid):
            token = claude_watch.get_access_token()

        assert token == "test-access-token-12345"

    def test_missing_token(self, credentials_missing_token):
        """Test error when access token is missing."""
        with patch.object(claude_watch, "get_credentials", return_value=credentials_missing_token):
            with pytest.raises(ValueError) as exc_info:
                claude_watch.get_access_token()

        assert "No access token found" in str(exc_info.value)

    def test_missing_oauth_section(self):
        """Test error when claudeAiOauth section is missing."""
        creds_no_oauth = {"someOtherKey": "value"}

        with patch.object(claude_watch, "get_credentials", return_value=creds_no_oauth):
            with pytest.raises(ValueError) as exc_info:
                claude_watch.get_access_token()

        assert "No access token found" in str(exc_info.value)

    def test_empty_credentials(self):
        """Test error when credentials are empty."""
        with patch.object(claude_watch, "get_credentials", return_value={}):
            with pytest.raises(ValueError) as exc_info:
                claude_watch.get_access_token()

        assert "No access token found" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# Test load_history() and save_history()
# ═══════════════════════════════════════════════════════════════════════════════


class TestHistoryManagement:
    """Tests for history load/save functions."""

    def test_load_empty_history(self, tmp_path):
        """Test loading when history file doesn't exist."""
        history_file = tmp_path / ".usage_history.json"

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            result = claude_watch.load_history()

        assert result == []

    def test_load_existing_history(self, tmp_path, history_sample):
        """Test loading existing history file."""
        history_file = tmp_path / ".usage_history.json"
        history_file.write_text(json.dumps(history_sample))

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            result = claude_watch.load_history()

        assert len(result) == 5
        assert result[0]["five_hour"] == 25.0

    def test_load_corrupted_history(self, tmp_path):
        """Test loading corrupted history file returns empty list."""
        history_file = tmp_path / ".usage_history.json"
        history_file.write_text("not valid json {{{")

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            result = claude_watch.load_history()

        assert result == []

    def test_save_history(self, tmp_path):
        """Test saving history to file."""
        from datetime import datetime, timedelta, timezone

        history_file = tmp_path / ".usage_history.json"

        # Create recent history entries (within MAX_HISTORY_DAYS)
        recent_history = []
        for i in range(5):
            recent_history.append(
                {
                    "timestamp": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                    "five_hour": 25.0 + i * 2,
                    "seven_day": 10.0 + i * 0.5,
                }
            )

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            claude_watch.save_history(recent_history)

        assert history_file.exists()
        saved = json.loads(history_file.read_text())
        assert len(saved) == 5

    def test_save_history_prunes_old(self, tmp_path):
        """Test that save_history prunes entries older than MAX_HISTORY_DAYS."""
        from datetime import datetime, timedelta, timezone

        history_file = tmp_path / ".usage_history.json"

        # Create history with old and new entries
        old_entry = {
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
            "five_hour": 50.0,
            "seven_day": 20.0,
        }
        new_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "five_hour": 30.0,
            "seven_day": 10.0,
        }

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            with patch.object(claude_watch, "MAX_HISTORY_DAYS", 30):
                claude_watch.save_history([old_entry, new_entry])

        saved = json.loads(history_file.read_text())
        assert len(saved) == 1  # Old entry should be pruned
        assert saved[0]["five_hour"] == 30.0

    def test_save_creates_parent_dirs(self, tmp_path):
        """Test that save_history creates parent directories."""
        history_file = tmp_path / "subdir" / "nested" / ".usage_history.json"

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            claude_watch.save_history([{"timestamp": "2024-12-19T00:00:00Z"}])

        assert history_file.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Test record_usage()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordUsage:
    """Tests for record_usage() function."""

    def test_record_appends_entry(self, tmp_path, usage_normal):
        """Test that record_usage appends new entry to history."""
        history_file = tmp_path / ".usage_history.json"
        history_file.write_text("[]")

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            claude_watch.record_usage(usage_normal)

        saved = json.loads(history_file.read_text())
        assert len(saved) == 1
        assert saved[0]["five_hour"] == 34.5
        assert saved[0]["seven_day"] == 12.3
        assert "timestamp" in saved[0]

    def test_record_handles_missing_fields(self, tmp_path):
        """Test record_usage handles missing optional fields."""
        history_file = tmp_path / ".usage_history.json"
        history_file.write_text("[]")

        minimal_data = {
            "five_hour": {"utilization": 10.0},
            "seven_day": {"utilization": 5.0},
        }

        with patch.object(claude_watch, "HISTORY_FILE", history_file):
            claude_watch.record_usage(minimal_data)

        saved = json.loads(history_file.read_text())
        assert len(saved) == 1
        assert saved[0]["seven_day_sonnet"] is None
        assert saved[0]["seven_day_opus"] is None
