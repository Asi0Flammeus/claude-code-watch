"""
Tests for cache system functions.

Tests cover:
- load_cache() - loading cached usage data
- save_cache() - saving usage data to cache
- get_stale_cache() - retrieving stale cache for fallback
- fetch_usage_cached() - fetching with caching and error handling
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

# Import from the executable script
sys.path.insert(0, str(Path(__file__).parent.parent))

# We need to import the module dynamically since it's an executable without .py extension
spec = importlib.util.spec_from_loader(
    "claude_watch",
    loader=None,
    origin=str(Path(__file__).parent.parent / "claude-watch"),
)
claude_watch = importlib.util.module_from_spec(spec)

# Execute the module to load its contents
with open(Path(__file__).parent.parent / "claude-watch", encoding="utf-8") as f:
    exec(f.read(), claude_watch.__dict__)


# ═══════════════════════════════════════════════════════════════════════════════
# Test load_cache()
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadCache:
    """Tests for load_cache() function."""

    def test_load_nonexistent_cache(self, tmp_path):
        """Test loading when cache file doesn't exist."""
        cache_file = tmp_path / ".usage_cache.json"

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            result = claude_watch.load_cache()

        assert result is None

    def test_load_valid_fresh_cache(self, tmp_path, usage_normal):
        """Test loading valid cache that is still fresh."""
        cache_file = tmp_path / ".usage_cache.json"
        cache_data = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "CACHE_MAX_AGE", 60):
                result = claude_watch.load_cache()

        assert result is not None
        assert result["five_hour"]["utilization"] == 34.5

    def test_load_stale_cache_returns_none(self, tmp_path, usage_normal):
        """Test that stale cache returns None."""
        cache_file = tmp_path / ".usage_cache.json"
        # Create cache from 2 minutes ago (120 seconds > 60 second TTL)
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        cache_data = {
            "cached_at": stale_time.isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "CACHE_MAX_AGE", 60):
                result = claude_watch.load_cache()

        assert result is None

    def test_load_cache_missing_timestamp(self, tmp_path, usage_normal):
        """Test cache without cached_at returns None."""
        cache_file = tmp_path / ".usage_cache.json"
        cache_data = {"data": usage_normal}  # Missing cached_at
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            result = claude_watch.load_cache()

        assert result is None

    def test_load_corrupted_cache(self, tmp_path):
        """Test loading corrupted cache returns None."""
        cache_file = tmp_path / ".usage_cache.json"
        cache_file.write_text("not valid json {{{", encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            result = claude_watch.load_cache()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Test save_cache()
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveCache:
    """Tests for save_cache() function."""

    def test_save_cache(self, tmp_path, usage_normal):
        """Test saving cache to file."""
        cache_file = tmp_path / ".usage_cache.json"

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            claude_watch.save_cache(usage_normal)

        assert cache_file.exists()
        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        assert "cached_at" in saved
        assert saved["data"]["five_hour"]["utilization"] == 34.5

    def test_save_cache_creates_parent_dirs(self, tmp_path, usage_normal):
        """Test that save_cache creates parent directories."""
        cache_file = tmp_path / "subdir" / "nested" / ".usage_cache.json"

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            claude_watch.save_cache(usage_normal)

        assert cache_file.exists()

    def test_save_cache_silent_fail(self, tmp_path, usage_normal):
        """Test that save_cache fails silently on IOError."""
        # Use a path that will fail (directory as file)
        cache_file = tmp_path / "readonly_dir" / ".usage_cache.json"
        readonly_dir = tmp_path / "readonly_dir"
        readonly_dir.mkdir()
        # Create a directory where the file should be (causes IOError)
        cache_file_as_dir = cache_file
        cache_file_as_dir.mkdir()

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            # Should not raise, just silently fail
            claude_watch.save_cache(usage_normal)


# ═══════════════════════════════════════════════════════════════════════════════
# Test get_stale_cache()
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetStaleCache:
    """Tests for get_stale_cache() function."""

    def test_get_stale_cache_nonexistent(self, tmp_path):
        """Test getting stale cache when file doesn't exist."""
        cache_file = tmp_path / ".usage_cache.json"

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            result = claude_watch.get_stale_cache()

        assert result is None

    def test_get_stale_cache_returns_old_data(self, tmp_path, usage_normal):
        """Test that get_stale_cache returns data regardless of age."""
        cache_file = tmp_path / ".usage_cache.json"
        # Create very old cache
        old_time = datetime.now(timezone.utc) - timedelta(hours=24)
        cache_data = {
            "cached_at": old_time.isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            result = claude_watch.get_stale_cache()

        assert result is not None
        assert result["five_hour"]["utilization"] == 34.5

    def test_get_stale_cache_corrupted(self, tmp_path):
        """Test getting stale cache from corrupted file returns None."""
        cache_file = tmp_path / ".usage_cache.json"
        cache_file.write_text("not valid json", encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            result = claude_watch.get_stale_cache()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Test fetch_usage_cached()
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchUsageCached:
    """Tests for fetch_usage_cached() function."""

    def test_returns_fresh_cache(self, tmp_path, usage_normal):
        """Test that fresh cache is returned without API call."""
        cache_file = tmp_path / ".usage_cache.json"
        cache_data = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "CACHE_MAX_AGE", 60):
                with patch.object(claude_watch, "fetch_usage") as mock_fetch:
                    result = claude_watch.fetch_usage_cached()

        # fetch_usage should not be called when cache is fresh
        mock_fetch.assert_not_called()
        assert result["five_hour"]["utilization"] == 34.5

    def test_fetches_when_cache_stale(self, tmp_path, usage_normal, usage_high):
        """Test that API is called when cache is stale."""
        cache_file = tmp_path / ".usage_cache.json"
        # Create stale cache
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        cache_data = {
            "cached_at": stale_time.isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "CACHE_MAX_AGE", 60):
                with patch.object(claude_watch, "fetch_usage", return_value=usage_high) as mock_fetch:
                    result = claude_watch.fetch_usage_cached()

        mock_fetch.assert_called_once()
        assert result["five_hour"]["utilization"] == 85.2  # From usage_high

    def test_fetches_when_no_cache(self, tmp_path, usage_normal):
        """Test that API is called when no cache exists."""
        cache_file = tmp_path / ".usage_cache.json"
        # No cache file exists

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "fetch_usage", return_value=usage_normal) as mock_fetch:
                result = claude_watch.fetch_usage_cached()

        mock_fetch.assert_called_once()
        assert result["five_hour"]["utilization"] == 34.5

    def test_saves_cache_after_fetch(self, tmp_path, usage_normal):
        """Test that cache is saved after successful fetch."""
        cache_file = tmp_path / ".usage_cache.json"

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "fetch_usage", return_value=usage_normal):
                claude_watch.fetch_usage_cached()

        assert cache_file.exists()
        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        assert saved["data"]["five_hour"]["utilization"] == 34.5

    def test_custom_cache_ttl(self, tmp_path, usage_normal, usage_high):
        """Test that custom cache_ttl overrides default."""
        cache_file = tmp_path / ".usage_cache.json"
        # Create cache from 30 seconds ago
        cache_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        cache_data = {
            "cached_at": cache_time.isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "CACHE_MAX_AGE", 60):
                # With default TTL (60s), cache should be fresh
                with patch.object(claude_watch, "fetch_usage", return_value=usage_high) as mock_fetch:
                    result1 = claude_watch.fetch_usage_cached()
                    mock_fetch.assert_not_called()
                    assert result1["five_hour"]["utilization"] == 34.5

                # With custom TTL (10s), cache should be stale
                with patch.object(claude_watch, "fetch_usage", return_value=usage_high) as mock_fetch:
                    result2 = claude_watch.fetch_usage_cached(cache_ttl=10)
                    mock_fetch.assert_called_once()
                    assert result2["five_hour"]["utilization"] == 85.2

    def test_silent_mode_returns_none_on_error(self, tmp_path):
        """Test that silent mode returns None on error with no cache."""
        cache_file = tmp_path / ".usage_cache.json"
        # No cache file exists

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "fetch_usage", side_effect=RuntimeError("Network error")):
                result = claude_watch.fetch_usage_cached(silent=True)

        assert result is None

    def test_silent_mode_returns_stale_cache_on_error(self, tmp_path, usage_normal):
        """Test that silent mode returns stale cache on error."""
        cache_file = tmp_path / ".usage_cache.json"
        # Create stale cache
        stale_time = datetime.now(timezone.utc) - timedelta(hours=1)
        cache_data = {
            "cached_at": stale_time.isoformat(),
            "data": usage_normal,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "CACHE_MAX_AGE", 60):
                with patch.object(claude_watch, "fetch_usage", side_effect=RuntimeError("Network error")):
                    result = claude_watch.fetch_usage_cached(silent=True)

        # Should return stale cache as fallback
        assert result is not None
        assert result["five_hour"]["utilization"] == 34.5

    def test_non_silent_mode_raises_on_error(self, tmp_path):
        """Test that non-silent mode raises exception on error."""
        cache_file = tmp_path / ".usage_cache.json"

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "fetch_usage", side_effect=RuntimeError("Network error")):
                with pytest.raises(RuntimeError) as exc_info:
                    claude_watch.fetch_usage_cached(silent=False)

        assert "Network error" in str(exc_info.value)

    def test_cache_ttl_restored_after_call(self, tmp_path, usage_normal):
        """Test that CACHE_MAX_AGE is restored after call with custom TTL."""
        cache_file = tmp_path / ".usage_cache.json"
        original_ttl = claude_watch.CACHE_MAX_AGE

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "fetch_usage", return_value=usage_normal):
                claude_watch.fetch_usage_cached(cache_ttl=999)

        # TTL should be restored to original value
        assert claude_watch.CACHE_MAX_AGE == original_ttl

    def test_cache_ttl_restored_on_exception(self, tmp_path):
        """Test that CACHE_MAX_AGE is restored even on exception."""
        cache_file = tmp_path / ".usage_cache.json"
        original_ttl = claude_watch.CACHE_MAX_AGE

        with patch.object(claude_watch, "CACHE_FILE", cache_file):
            with patch.object(claude_watch, "fetch_usage", side_effect=RuntimeError("Error")):
                try:
                    claude_watch.fetch_usage_cached(cache_ttl=999)
                except RuntimeError:
                    pass

        # TTL should be restored to original value
        assert claude_watch.CACHE_MAX_AGE == original_ttl
