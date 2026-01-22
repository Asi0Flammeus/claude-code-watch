"""Tests for token extraction from Claude Code conversation logs."""

from claude_watch.history.tokens import _extract_usage_from_message, _parse_timestamp


class TestParseTimestamp:
    """Tests for _parse_timestamp function."""

    def test_valid_iso_timestamp(self):
        """Test parsing valid ISO timestamp."""
        ts = "2025-01-15T10:30:00+00:00"
        result = _parse_timestamp(ts)
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_timestamp_with_z_suffix(self):
        """Test parsing timestamp with Z suffix."""
        ts = "2025-01-15T10:30:00Z"
        result = _parse_timestamp(ts)
        assert result is not None
        assert result.year == 2025

    def test_timestamp_with_milliseconds(self):
        """Test parsing timestamp with milliseconds."""
        ts = "2025-01-15T10:30:00.123456+00:00"
        result = _parse_timestamp(ts)
        assert result is not None

    def test_empty_string_returns_none(self):
        """Test that empty string returns None."""
        result = _parse_timestamp("")
        assert result is None

    def test_none_input_returns_none(self):
        """Test that None-like empty input returns None."""
        result = _parse_timestamp("")
        assert result is None

    def test_invalid_format_returns_none(self):
        """Test that invalid format returns None."""
        result = _parse_timestamp("not-a-timestamp")
        assert result is None

    def test_partial_timestamp_accepted(self):
        """Test that date-only string is accepted (time defaults to midnight)."""
        result = _parse_timestamp("2025-01-15")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15


class TestExtractUsageFromMessage:
    """Tests for _extract_usage_from_message function."""

    def test_extracts_from_assistant_message(self):
        """Test extraction from valid assistant message."""
        entry = {
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-5-20251101",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_input_tokens": 200,
                    "cache_creation_input_tokens": 100,
                },
            },
            "sessionId": "test-session-123",
            "timestamp": "2025-01-15T10:30:00Z",
        }

        result = _extract_usage_from_message(entry)

        assert result is not None
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["cache_read_input_tokens"] == 200
        assert result["cache_creation_input_tokens"] == 100
        assert result["model"] == "claude-opus-4-5-20251101"
        assert result["session_id"] == "test-session-123"

    def test_returns_none_for_user_message(self):
        """Test that user messages return None."""
        entry = {
            "type": "user",
            "message": {"content": "Hello"},
        }
        result = _extract_usage_from_message(entry)
        assert result is None

    def test_returns_none_for_system_message(self):
        """Test that system messages return None."""
        entry = {
            "type": "system",
            "message": {"content": "System prompt"},
        }
        result = _extract_usage_from_message(entry)
        assert result is None

    def test_returns_none_for_missing_type(self):
        """Test that entries without type return None."""
        entry = {
            "message": {"usage": {"input_tokens": 100}},
        }
        result = _extract_usage_from_message(entry)
        assert result is None

    def test_returns_none_for_missing_usage(self):
        """Test that assistant messages without usage return None."""
        entry = {
            "type": "assistant",
            "message": {"model": "claude-opus-4-5-20251101"},
        }
        result = _extract_usage_from_message(entry)
        assert result is None

    def test_defaults_for_missing_fields(self):
        """Test that missing optional fields get defaults."""
        entry = {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    # cache fields missing
                },
            },
            # sessionId missing
            # timestamp missing
        }

        result = _extract_usage_from_message(entry)

        assert result is not None
        assert result["cache_read_input_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0
        assert result["model"] == "unknown"
        assert result["session_id"] == "unknown"
        assert result["timestamp"] == ""

    def test_handles_empty_message(self):
        """Test handling of empty message dict."""
        entry = {
            "type": "assistant",
            "message": {},
        }
        result = _extract_usage_from_message(entry)
        assert result is None
