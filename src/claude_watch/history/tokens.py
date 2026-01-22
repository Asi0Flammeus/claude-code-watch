"""Token usage extraction from Claude Code conversation logs.

Parses JSONL files from ~/.claude/projects/ to extract and aggregate
token usage data from assistant messages.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (as of 2025)
PRICING_OPUS_INPUT = 15.0
PRICING_OPUS_OUTPUT = 75.0
PRICING_OPUS_CACHE_READ = 1.50
PRICING_OPUS_CACHE_CREATION = 18.75  # 1.25x input price

PRICING_SONNET_INPUT = 3.0
PRICING_SONNET_OUTPUT = 15.0
PRICING_SONNET_CACHE_READ = 0.30
PRICING_SONNET_CACHE_CREATION = 3.75  # 1.25x input price


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


def _calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    input_price: float,
    output_price: float,
    cache_read_price: float,
    cache_creation_price: float,
) -> float:
    """Calculate cost based on token counts and pricing.

    Args:
        input_tokens: Non-cached input tokens.
        output_tokens: Output tokens.
        cache_read_tokens: Cached input tokens read.
        cache_creation_tokens: Tokens written to cache.
        input_price: Price per 1M input tokens.
        output_price: Price per 1M output tokens.
        cache_read_price: Price per 1M cache read tokens.
        cache_creation_price: Price per 1M cache creation tokens.

    Returns:
        Estimated cost in dollars.
    """
    return (
        (input_tokens / 1_000_000) * input_price
        + (output_tokens / 1_000_000) * output_price
        + (cache_read_tokens / 1_000_000) * cache_read_price
        + (cache_creation_tokens / 1_000_000) * cache_creation_price
    )


def get_token_usage(days: int = 7) -> TokenUsageReport:
    """Get aggregated token usage for the specified period.

    Recursively scans ~/.claude/projects/ for JSONL files and aggregates
    token usage from assistant messages.

    Args:
        days: Number of days to look back (default: 7).

    Returns:
        TokenUsageReport with totals, daily breakdown, model breakdown,
        session breakdown, and estimated costs.
    """
    projects_dir = get_claude_projects_dir()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Aggregation containers
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "messages": 0,
    }
    sessions: set[str] = set()
    daily: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "messages": 0,
        }
    )
    by_model: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "messages": 0,
        }
    )
    by_session: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "messages": 0,
        }
    )

    if not projects_dir.exists():
        logger.info("Claude projects directory not found: %s", projects_dir)
        return TokenUsageReport(
            period_days=days,
            totals=totals,
            daily={},
            by_model={},
            by_session={},
            estimated_cost=EstimatedCost(opus=0.0, sonnet=0.0),
        )

    # Find all JSONL files
    jsonl_files = list(projects_dir.rglob("*.jsonl"))
    logger.info("Found %d JSONL files to process", len(jsonl_files))

    for jsonl_path in jsonl_files:
        entries = parse_conversation_file(jsonl_path)

        for entry in entries:
            ts = _parse_timestamp(entry["timestamp"])
            if ts is None or ts < cutoff:
                continue

            # Update totals
            totals["input_tokens"] += entry["input_tokens"]
            totals["output_tokens"] += entry["output_tokens"]
            totals["cache_read_tokens"] += entry["cache_read_input_tokens"]
            totals["cache_creation_tokens"] += entry["cache_creation_input_tokens"]
            totals["messages"] += 1
            sessions.add(entry["session_id"])

            # Update daily breakdown
            date_key = ts.strftime("%Y-%m-%d")
            daily[date_key]["input_tokens"] += entry["input_tokens"]
            daily[date_key]["output_tokens"] += entry["output_tokens"]
            daily[date_key]["cache_read_tokens"] += entry["cache_read_input_tokens"]
            daily[date_key]["cache_creation_tokens"] += entry[
                "cache_creation_input_tokens"
            ]
            daily[date_key]["messages"] += 1

            # Update model breakdown
            model = entry["model"]
            by_model[model]["input_tokens"] += entry["input_tokens"]
            by_model[model]["output_tokens"] += entry["output_tokens"]
            by_model[model]["cache_read_tokens"] += entry["cache_read_input_tokens"]
            by_model[model]["cache_creation_tokens"] += entry[
                "cache_creation_input_tokens"
            ]
            by_model[model]["messages"] += 1

            # Update session breakdown
            session = entry["session_id"]
            by_session[session]["input_tokens"] += entry["input_tokens"]
            by_session[session]["output_tokens"] += entry["output_tokens"]
            by_session[session]["cache_read_tokens"] += entry["cache_read_input_tokens"]
            by_session[session]["cache_creation_tokens"] += entry[
                "cache_creation_input_tokens"
            ]
            by_session[session]["messages"] += 1

    # Add session count to totals
    totals["sessions"] = len(sessions)

    # Sort daily by date
    sorted_daily = dict(sorted(daily.items()))

    # Calculate estimated costs
    cost_opus = _calculate_cost(
        totals["input_tokens"],
        totals["output_tokens"],
        totals["cache_read_tokens"],
        totals["cache_creation_tokens"],
        PRICING_OPUS_INPUT,
        PRICING_OPUS_OUTPUT,
        PRICING_OPUS_CACHE_READ,
        PRICING_OPUS_CACHE_CREATION,
    )

    cost_sonnet = _calculate_cost(
        totals["input_tokens"],
        totals["output_tokens"],
        totals["cache_read_tokens"],
        totals["cache_creation_tokens"],
        PRICING_SONNET_INPUT,
        PRICING_SONNET_OUTPUT,
        PRICING_SONNET_CACHE_READ,
        PRICING_SONNET_CACHE_CREATION,
    )

    return TokenUsageReport(
        period_days=days,
        totals=totals,
        daily=sorted_daily,
        by_model=dict(by_model),
        by_session=dict(by_session),
        estimated_cost=EstimatedCost(opus=round(cost_opus, 2), sonnet=round(cost_sonnet, 2)),
    )


__all__ = [
    "get_claude_projects_dir",
    "parse_conversation_file",
    "get_token_usage",
    "UsageEntry",
    "DailyUsage",
    "ModelUsage",
    "EstimatedCost",
    "TokenUsageReport",
    "PRICING_OPUS_INPUT",
    "PRICING_OPUS_OUTPUT",
    "PRICING_OPUS_CACHE_READ",
    "PRICING_OPUS_CACHE_CREATION",
    "PRICING_SONNET_INPUT",
    "PRICING_SONNET_OUTPUT",
    "PRICING_SONNET_CACHE_READ",
    "PRICING_SONNET_CACHE_CREATION",
]
