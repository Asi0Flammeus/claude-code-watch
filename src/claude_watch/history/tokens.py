"""Token usage extraction from Claude Code conversation logs.

Parses JSONL files from ~/.claude/projects/ to extract and aggregate
token usage data from assistant messages.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class UsageEntry(TypedDict):
    """Token usage data from a single assistant message."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    model: str
    timestamp: str
    session_id: str


class DailyUsage(TypedDict):
    """Aggregated usage data for a single day."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    messages: int


class ModelUsage(TypedDict):
    """Aggregated usage data for a single model."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    messages: int


class EstimatedCost(TypedDict):
    """Estimated costs at different pricing tiers."""

    opus: float
    sonnet: float


class TokenUsageReport(TypedDict):
    """Complete token usage report structure."""

    period_days: int
    totals: dict[str, int]
    daily: dict[str, DailyUsage]
    by_model: dict[str, ModelUsage]
    by_session: dict[str, dict[str, int]]
    estimated_cost: EstimatedCost


def get_claude_projects_dir() -> Path:
    """Get the Claude projects directory path.

    Returns:
        Path to ~/.claude/projects directory.
    """
    return Path.home() / ".claude" / "projects"


def _extract_usage_from_message(entry: dict[str, Any]) -> UsageEntry | None:
    """Extract token usage from a single JSONL entry.

    Args:
        entry: Parsed JSON entry from conversation log.

    Returns:
        UsageEntry if this is an assistant message with usage data, else None.
    """
    # Only process assistant messages
    if entry.get("type") != "assistant":
        return None

    message = entry.get("message", {})
    usage = message.get("usage")

    if not usage:
        return None

    model = message.get("model", "unknown")
    session_id = entry.get("sessionId", "unknown")
    timestamp = entry.get("timestamp", "")

    return UsageEntry(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
        cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
        model=model,
        timestamp=timestamp,
        session_id=session_id,
    )


def parse_conversation_file(path: Path) -> list[UsageEntry]:
    """Parse a single JSONL conversation file.

    Args:
        path: Path to the .jsonl file.

    Returns:
        List of UsageEntry dicts extracted from assistant messages.
    """
    entries: list[UsageEntry] = []

    try:
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    usage = _extract_usage_from_message(entry)
                    if usage:
                        entries.append(usage)
                except json.JSONDecodeError as e:
                    logger.debug(
                        "Skipping malformed JSON at %s:%d: %s", path, line_num, e
                    )
                    continue

    except OSError as e:
        logger.warning("Could not read file %s: %s", path, e)

    return entries


def _parse_timestamp(timestamp: str) -> datetime | None:
    """Parse ISO timestamp to datetime.

    Args:
        timestamp: ISO 8601 timestamp string.

    Returns:
        Timezone-aware datetime or None if parsing fails.
    """
    if not timestamp:
        return None

    try:
        # Handle trailing Z
        ts = timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


__all__ = [
    "get_claude_projects_dir",
    "parse_conversation_file",
    "_parse_timestamp",
    "_extract_usage_from_message",
    "UsageEntry",
    "DailyUsage",
    "ModelUsage",
    "EstimatedCost",
    "TokenUsageReport",
]
