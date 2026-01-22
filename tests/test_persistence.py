"""Tests for persistent token storage."""

import tempfile
from pathlib import Path

import pytest

from claude_watch.history.persistence import (
    TokenStore,
    _get_data_dir,
    _hash_entry,
)


class TestHashEntry:
    """Tests for _hash_entry function."""

    def test_returns_16_char_hex_string(self):
        """Test that hash is exactly 16 hex characters."""
        result = _hash_entry("session-123", "2025-01-15T10:30:00Z", 1000, 500)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_consistent_for_same_input(self):
        """Test that same inputs produce same hash."""
        hash1 = _hash_entry("session-123", "2025-01-15T10:30:00Z", 1000, 500)
        hash2 = _hash_entry("session-123", "2025-01-15T10:30:00Z", 1000, 500)
        assert hash1 == hash2

    def test_different_inputs_produce_different_hashes(self):
        """Test that different inputs produce different hashes."""
        base = _hash_entry("session-123", "2025-01-15T10:30:00Z", 1000, 500)

        # Different session
        diff_session = _hash_entry("session-456", "2025-01-15T10:30:00Z", 1000, 500)
        assert base != diff_session

        # Different timestamp
        diff_ts = _hash_entry("session-123", "2025-01-15T10:31:00Z", 1000, 500)
        assert base != diff_ts

        # Different input tokens
        diff_input = _hash_entry("session-123", "2025-01-15T10:30:00Z", 1001, 500)
        assert base != diff_input

        # Different output tokens
        diff_output = _hash_entry("session-123", "2025-01-15T10:30:00Z", 1000, 501)
        assert base != diff_output


class TestGetDataDir:
    """Tests for XDG data directory compliance."""

    def test_respects_xdg_data_home(self, monkeypatch):
        """Test that XDG_DATA_HOME environment variable is respected."""
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        result = _get_data_dir()
        assert result == Path("/custom/data/ccw")

    def test_falls_back_to_default(self, monkeypatch):
        """Test fallback to ~/.local/share/ccw when XDG_DATA_HOME is unset."""
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = _get_data_dir()
        assert result == Path.home() / ".local" / "share" / "ccw"

    def test_empty_xdg_data_home_uses_default(self, monkeypatch):
        """Test that empty XDG_DATA_HOME falls back to default."""
        monkeypatch.setenv("XDG_DATA_HOME", "")
        result = _get_data_dir()
        assert result == Path.home() / ".local" / "share" / "ccw"


class TestTokenStore:
    """Tests for TokenStore class."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary file for store testing."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        yield path
        # Cleanup
        if path.exists():
            path.unlink()

    def test_creates_file_on_save(self, temp_store_path):
        """Test that save creates the store file."""
        # Remove file first
        if temp_store_path.exists():
            temp_store_path.unlink()

        store = TokenStore(temp_store_path)
        store.save()

        assert temp_store_path.exists()

    def test_get_stats_returns_zeros_for_empty_store(self, temp_store_path):
        """Test that get_stats returns zeros when store is empty."""
        store = TokenStore(temp_store_path)
        stats = store.get_stats(days=7)

        assert stats["totals"]["input_tokens"] == 0
        assert stats["totals"]["output_tokens"] == 0
        assert stats["totals"]["cache_read_tokens"] == 0
        assert stats["totals"]["cache_creation_tokens"] == 0
        assert stats["totals"]["messages"] == 0
        assert stats["estimated_cost"]["opus"] == 0.0
        assert stats["estimated_cost"]["sonnet"] == 0.0

    def test_get_stats_for_display_returns_expected_structure(self, temp_store_path):
        """Test that get_stats_for_display returns display-ready structure."""
        store = TokenStore(temp_store_path)
        display_data = store.get_stats_for_display(days=7)

        assert "period" in display_data
        assert "days" in display_data["period"]
        assert "totals" in display_data
        assert "daily" in display_data
        assert isinstance(display_data["daily"], list)
        assert "by_model" in display_data
        assert "estimated_cost" in display_data

    def test_get_status_returns_metadata(self, temp_store_path):
        """Test that get_status returns store metadata."""
        store = TokenStore(temp_store_path)
        status = store.get_status()

        assert "store_path" in status
        assert "version" in status
        assert "total_entries" in status
        assert "scanned_files" in status
        assert status["total_entries"] == 0

    def test_reset_clears_data(self, temp_store_path):
        """Test that reset clears all stored data."""
        store = TokenStore(temp_store_path)

        # Manually add some data
        store._data["entries"].append({
            "hash": "test123456789abc",
            "timestamp": "2025-01-15T10:30:00Z",
            "session_id": "test-session",
            "project": "test-project",
            "model": "claude-opus-4-5-20251101",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 25,
            "cache_creation_tokens": 10,
            "source_file": "test.jsonl",
        })
        store.save()

        assert len(store._data["entries"]) == 1

        store.reset()

        assert len(store._data["entries"]) == 0

    def test_store_persists_across_instances(self, temp_store_path):
        """Test that data persists when creating new store instance."""
        # Create store and add data
        store1 = TokenStore(temp_store_path)
        store1._data["entries"].append({
            "hash": "test123456789abc",
            "timestamp": "2025-01-15T10:30:00Z",
            "session_id": "test-session",
            "project": "test-project",
            "model": "claude-opus-4-5-20251101",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 25,
            "cache_creation_tokens": 10,
            "source_file": "test.jsonl",
        })
        store1.save()

        # Create new instance and verify data
        store2 = TokenStore(temp_store_path)
        assert len(store2._data["entries"]) == 1
        assert store2._data["entries"][0]["input_tokens"] == 100
