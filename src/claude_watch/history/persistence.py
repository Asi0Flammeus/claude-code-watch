"""Persistent token storage for Claude Code usage tracking.

Provides durable storage of token usage data extracted from conversation logs.
The ephemeral JSONL files in ~/.claude/projects/ can be cleaned up at any time;
this module ensures historical usage data is preserved.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict

from claude_watch.history.tokens import (
    EstimatedCost,
    TokenUsageReport,
    _parse_timestamp,
    get_claude_projects_dir,
    parse_conversation_file,
)
from claude_watch.pricing import calculate_cost

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    """Get XDG-compliant data directory.

    Respects XDG_DATA_HOME environment variable if set,
    otherwise falls back to ~/.local/share/ccw.

    Returns:
        Path to the ccw data directory.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "ccw"
    return Path.home() / ".local" / "share" / "ccw"


# XDG-compliant storage location
STORE_DIR = _get_data_dir()
STORE_FILE = STORE_DIR / "token-usage.json"
STORE_VERSION = 1


class StoredEntry(TypedDict):
    """A single token usage entry in the persistent store."""

    hash: str
    timestamp: str
    session_id: str
    project: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    source_file: str


class ScannedFileInfo(TypedDict):
    """Metadata about a scanned JSONL file."""

    last_modified: str
    entries_count: int


class StoreData(TypedDict):
    """Complete persistent store structure."""

    version: int
    last_scan: str
    scanned_files: dict[str, ScannedFileInfo]
    entries: list[StoredEntry]


@dataclass
class SyncResult:
    """Result of a sync operation."""

    files_scanned: int
    new_entries: int
    skipped_files: int
    total_entries: int


def _hash_entry(
    session_id: str,
    timestamp: str,
    input_tokens: int,
    output_tokens: int,
) -> str:
    """Generate unique hash for entry deduplication.

    Uses SHA-256 truncated to 16 hex chars (64 bits).
    Birthday paradox: 50% collision probability at ~4B entries.
    Acceptable: timestamps provide uniqueness, collisions only skip duplicates.

    Args:
        session_id: Session identifier.
        timestamp: ISO 8601 timestamp.
        input_tokens: Input token count.
        output_tokens: Output token count.

    Returns:
        16-character hex hash.
    """
    hash_input = f"{session_id}:{timestamp}:{input_tokens}:{output_tokens}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _extract_project_name(file_path: Path) -> str:
    """Extract project name from JSONL file path.

    The path structure is typically:
    ~/.claude/projects/<project-hash>/<conversation>.jsonl

    Args:
        file_path: Path to the JSONL file.

    Returns:
        Project identifier (directory name containing the file).
    """
    # Get parent directory name as project identifier
    return file_path.parent.name


class TokenStore:
    """Manages persistent token usage storage.

    Provides methods to sync from ephemeral JSONL files, query historical
    data, and generate usage reports.
    """

    def __init__(self, store_path: Path | None = None):
        """Initialize the token store.

        Args:
            store_path: Optional custom path for the store file.
                       Defaults to ~/.local/share/ccw/token-usage.json
        """
        self._store_path = store_path or STORE_FILE
        self._ensure_directory()
        self._data = self._load()

    def _ensure_directory(self) -> None:
        """Create store directory with proper permissions if needed."""
        store_dir = self._store_path.parent
        if not store_dir.exists():
            store_dir.mkdir(parents=True, mode=0o700)
            logger.info("Created token store directory: %s", store_dir)

    def _load(self) -> StoreData:
        """Load existing store or return empty structure.

        Returns:
            Store data dictionary.
        """
        if not self._store_path.exists():
            logger.info("No existing token store found, starting fresh")
            return StoreData(
                version=STORE_VERSION,
                last_scan="",
                scanned_files={},
                entries=[],
            )

        try:
            with open(self._store_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate version
            if data.get("version", 0) != STORE_VERSION:
                logger.warning(
                    "Store version mismatch (got %s, expected %s), starting fresh",
                    data.get("version"),
                    STORE_VERSION,
                )
                return StoreData(
                    version=STORE_VERSION,
                    last_scan="",
                    scanned_files={},
                    entries=[],
                )

            return data

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load token store: %s, starting fresh", e)
            return StoreData(
                version=STORE_VERSION,
                last_scan="",
                scanned_files={},
                entries=[],
            )

    def save(self) -> None:
        """Atomic write to store file.

        Writes to a temporary file first, then renames to ensure
        the store file is never left in a corrupted state.
        """
        self._ensure_directory()

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=self._store_path.parent,
            prefix=".token-usage-",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)

            # Set permissions before rename
            os.chmod(temp_path, 0o600)

            # Atomic rename
            os.replace(temp_path, self._store_path)
            logger.debug("Saved token store to %s", self._store_path)

        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _is_file_changed(self, path: Path) -> bool:
        """Check if JSONL file needs re-scanning.

        Compares file modification time against stored metadata.

        Args:
            path: Path to the JSONL file.

        Returns:
            True if file should be scanned (new or modified).
        """
        path_str = str(path)

        if path_str not in self._data["scanned_files"]:
            return True

        try:
            current_mtime = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            stored_mtime = self._data["scanned_files"][path_str]["last_modified"]
            return current_mtime > stored_mtime
        except OSError:
            return True

    def sync(self, force: bool = False) -> SyncResult:
        """Scan JSONL files, extract new entries, update store.

        Args:
            force: If True, rescan all files regardless of mtime.

        Returns:
            SyncResult with counts of operations performed.
        """
        projects_dir = get_claude_projects_dir()

        if not projects_dir.exists():
            logger.info("Claude projects directory not found: %s", projects_dir)
            return SyncResult(
                files_scanned=0,
                new_entries=0,
                skipped_files=0,
                total_entries=len(self._data["entries"]),
            )

        # Build set of existing hashes for deduplication
        existing_hashes = {e["hash"] for e in self._data["entries"]}

        # Find all JSONL files
        jsonl_files = list(projects_dir.rglob("*.jsonl"))

        files_scanned = 0
        skipped_files = 0
        new_entries = 0

        for jsonl_path in jsonl_files:
            # Check if file needs scanning
            if not force and not self._is_file_changed(jsonl_path):
                skipped_files += 1
                continue

            files_scanned += 1
            project = _extract_project_name(jsonl_path)
            source_file = jsonl_path.name

            # Parse file using existing extraction logic
            entries = parse_conversation_file(jsonl_path)
            entries_added = 0

            for entry in entries:
                # Generate hash for deduplication
                entry_hash = _hash_entry(
                    entry["session_id"],
                    entry["timestamp"],
                    entry["input_tokens"],
                    entry["output_tokens"],
                )

                if entry_hash in existing_hashes:
                    continue

                # Add new entry
                stored_entry = StoredEntry(
                    hash=entry_hash,
                    timestamp=entry["timestamp"],
                    session_id=entry["session_id"],
                    project=project,
                    model=entry["model"],
                    input_tokens=entry["input_tokens"],
                    output_tokens=entry["output_tokens"],
                    cache_read_tokens=entry["cache_read_input_tokens"],
                    cache_creation_tokens=entry["cache_creation_input_tokens"],
                    source_file=source_file,
                )

                self._data["entries"].append(stored_entry)
                existing_hashes.add(entry_hash)
                entries_added += 1

            new_entries += entries_added

            # Update scanned file metadata
            try:
                mtime = datetime.fromtimestamp(
                    jsonl_path.stat().st_mtime, tz=timezone.utc
                ).isoformat()
            except OSError:
                mtime = datetime.now(timezone.utc).isoformat()

            self._data["scanned_files"][str(jsonl_path)] = ScannedFileInfo(
                last_modified=mtime,
                entries_count=len(entries),
            )

        # Update last scan timestamp
        self._data["last_scan"] = datetime.now(timezone.utc).isoformat()

        # Save if we made any changes
        if new_entries > 0 or files_scanned > 0:
            self.save()

        return SyncResult(
            files_scanned=files_scanned,
            new_entries=new_entries,
            skipped_files=skipped_files,
            total_entries=len(self._data["entries"]),
        )

    def needs_sync(self) -> bool:
        """Check if any JSONL files have been modified since last scan.

        Returns:
            True if sync is needed.
        """
        projects_dir = get_claude_projects_dir()
        if not projects_dir.exists():
            return False

        for jsonl_path in projects_dir.rglob("*.jsonl"):
            if self._is_file_changed(jsonl_path):
                return True

        return False

    def get_entries(
        self,
        days: int | None = None,
        project: str | None = None,
        model: str | None = None,
    ) -> list[StoredEntry]:
        """Get entries, optionally filtered.

        Args:
            days: Only include entries from the last N days.
            project: Filter by project name.
            model: Filter by model name.

        Returns:
            List of matching entries.
        """
        entries = self._data["entries"]

        # Filter by date (parse timestamp once to avoid redundant parsing)
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            filtered = []
            for e in entries:
                ts = _parse_timestamp(e["timestamp"])
                if ts and ts >= cutoff:
                    filtered.append(e)
            entries = filtered

        # Filter by project
        if project is not None:
            entries = [e for e in entries if e["project"] == project]

        # Filter by model
        if model is not None:
            entries = [e for e in entries if e["model"] == model]

        return entries

    def get_stats(self, days: int = 7) -> TokenUsageReport:
        """Aggregate entries into usage report.

        Produces the same report format as the original get_token_usage()
        function for compatibility with existing display code.

        Args:
            days: Number of days to include.

        Returns:
            TokenUsageReport matching the existing format.
        """
        entries = self.get_entries(days=days)

        # Aggregation containers
        totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "messages": 0,
        }
        sessions: set[str] = set()
        daily: dict[str, dict[str, int]] = {}
        by_model: dict[str, dict[str, int]] = {}
        by_session: dict[str, dict[str, int]] = {}

        for entry in entries:
            # Update totals
            totals["input_tokens"] += entry["input_tokens"]
            totals["output_tokens"] += entry["output_tokens"]
            totals["cache_read_tokens"] += entry["cache_read_tokens"]
            totals["cache_creation_tokens"] += entry["cache_creation_tokens"]
            totals["messages"] += 1
            sessions.add(entry["session_id"])

            # Parse timestamp for daily grouping
            ts = _parse_timestamp(entry["timestamp"])
            if ts:
                date_key = ts.strftime("%Y-%m-%d")

                # Initialize daily bucket if needed
                if date_key not in daily:
                    daily[date_key] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_read_tokens": 0,
                        "cache_creation_tokens": 0,
                        "messages": 0,
                    }

                daily[date_key]["input_tokens"] += entry["input_tokens"]
                daily[date_key]["output_tokens"] += entry["output_tokens"]
                daily[date_key]["cache_read_tokens"] += entry["cache_read_tokens"]
                daily[date_key]["cache_creation_tokens"] += entry["cache_creation_tokens"]
                daily[date_key]["messages"] += 1

            # Update model breakdown
            model = entry["model"]
            if model not in by_model:
                by_model[model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_creation_tokens": 0,
                    "messages": 0,
                }

            by_model[model]["input_tokens"] += entry["input_tokens"]
            by_model[model]["output_tokens"] += entry["output_tokens"]
            by_model[model]["cache_read_tokens"] += entry["cache_read_tokens"]
            by_model[model]["cache_creation_tokens"] += entry["cache_creation_tokens"]
            by_model[model]["messages"] += 1

            # Update session breakdown
            session = entry["session_id"]
            if session not in by_session:
                by_session[session] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_creation_tokens": 0,
                    "messages": 0,
                }

            by_session[session]["input_tokens"] += entry["input_tokens"]
            by_session[session]["output_tokens"] += entry["output_tokens"]
            by_session[session]["cache_read_tokens"] += entry["cache_read_tokens"]
            by_session[session]["cache_creation_tokens"] += entry["cache_creation_tokens"]
            by_session[session]["messages"] += 1

        # Add session count to totals
        totals["sessions"] = len(sessions)

        # Sort daily by date
        sorted_daily = dict(sorted(daily.items()))

        # Calculate estimated costs using centralized pricing
        cost_opus = calculate_cost(
            totals["input_tokens"],
            totals["output_tokens"],
            totals["cache_read_tokens"],
            totals["cache_creation_tokens"],
            "claude-opus-4-5-20251101",
        )

        cost_sonnet = calculate_cost(
            totals["input_tokens"],
            totals["output_tokens"],
            totals["cache_read_tokens"],
            totals["cache_creation_tokens"],
            "claude-sonnet-4-5-20250929",
        )

        return TokenUsageReport(
            period_days=days,
            totals=totals,
            daily=sorted_daily,
            by_model=by_model,
            by_session=by_session,
            estimated_cost=EstimatedCost(
                opus=round(cost_opus, 2),
                sonnet=round(cost_sonnet, 2),
            ),
        )

    def get_stats_for_display(self, days: int = 7) -> dict:
        """Get stats transformed for display module consumption.

        Converts the internal TokenUsageReport format to the display-friendly
        format expected by display/tokens.py. This ensures data transformation
        happens once at the source rather than in each consumer.

        Args:
            days: Number of days to include.

        Returns:
            Dict with keys: period, totals, daily (list), by_model, estimated_cost.
        """
        stats = self.get_stats(days)
        return {
            "period": {"days": stats["period_days"]},
            "totals": stats["totals"],
            "daily": [{"date": date, **usage} for date, usage in stats["daily"].items()],
            "by_model": stats["by_model"],
            "estimated_cost": stats["estimated_cost"],
        }

    def get_status(self) -> dict[str, Any]:
        """Get store metadata and status.

        Returns:
            Dictionary with store statistics.
        """
        entries = self._data["entries"]

        # Calculate date range
        timestamps = [
            _parse_timestamp(e["timestamp"]) for e in entries if _parse_timestamp(e["timestamp"])
        ]

        oldest = min(timestamps).isoformat() if timestamps else None
        newest = max(timestamps).isoformat() if timestamps else None

        # Count by project
        projects: dict[str, int] = {}
        for entry in entries:
            proj = entry["project"]
            projects[proj] = projects.get(proj, 0) + 1

        # File size
        try:
            file_size = self._store_path.stat().st_size
        except OSError:
            file_size = 0

        return {
            "store_path": str(self._store_path),
            "version": self._data["version"],
            "last_scan": self._data["last_scan"],
            "total_entries": len(entries),
            "scanned_files": len(self._data["scanned_files"]),
            "date_range": {
                "oldest": oldest,
                "newest": newest,
            },
            "by_project": projects,
            "file_size_bytes": file_size,
        }

    def reset(self) -> None:
        """Clear all stored data and rescan from scratch."""
        self._data = StoreData(
            version=STORE_VERSION,
            last_scan="",
            scanned_files={},
            entries=[],
        )
        self.save()
        logger.info("Token store reset")


# Module-level convenience functions


def get_token_store(store_path: Path | None = None) -> TokenStore:
    """Get a TokenStore instance.

    Args:
        store_path: Optional custom store path.

    Returns:
        TokenStore instance.
    """
    return TokenStore(store_path)


def sync_and_get_usage(days: int = 7, force_sync: bool = False) -> TokenUsageReport:
    """Sync token store and return usage report.

    This is the main entry point for the --tokens flag. It automatically
    syncs if any JSONL files have been modified, then returns the report.

    Args:
        days: Number of days to include in the report.
        force_sync: If True, rescan all files regardless of mtime.

    Returns:
        TokenUsageReport from the persistent store.
    """
    store = get_token_store()

    # Auto-sync if needed
    if force_sync or store.needs_sync():
        store.sync(force=force_sync)

    return store.get_stats(days=days)


def sync_and_get_display_data(days: int = 7, force_sync: bool = False) -> dict:
    """Sync token store and return data in display-ready format.

    Same as sync_and_get_usage but returns data transformed for
    the display module (daily as list, period as dict).

    Args:
        days: Number of days to include in the report.
        force_sync: If True, rescan all files regardless of mtime.

    Returns:
        Dict ready for display/tokens.py functions.
    """
    store = get_token_store()

    # Auto-sync if needed
    if force_sync or store.needs_sync():
        store.sync(force=force_sync)

    return store.get_stats_for_display(days=days)


__all__ = [
    "TokenStore",
    "StoredEntry",
    "SyncResult",
    "get_token_store",
    "sync_and_get_usage",
    "sync_and_get_display_data",
    "STORE_FILE",
    "STORE_DIR",
]
