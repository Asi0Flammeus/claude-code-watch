"""Export history data to CSV, JSON, and InfluxDB formats."""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional

from claude_watch.display.colors import Colors
from claude_watch.history.storage import load_history

CSV_COLUMNS = [
    "timestamp",
    "five_hour_pct",
    "seven_day_pct",
    "seven_day_sonnet_pct",
    "seven_day_opus_pct",
]


def filter_history_by_days(history: list, days: Optional[int] = None) -> list:
    """Filter history to entries within the last N days.

    Args:
        history: List of history entries.
        days: Number of days to keep (None for all).

    Returns:
        Filtered list of history entries.
    """
    if days is None:
        return history[:]

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    return [h for h in history if h.get("timestamp", "") >= cutoff_str]


def export_csv(
    history: list, days: Optional[int] = None, excel_bom: bool = False
) -> str:
    """Export history to CSV format.

    Args:
        history: List of history entries.
        days: Filter to last N days (None for all).
        excel_bom: Add UTF-8 BOM for Excel compatibility.

    Returns:
        CSV formatted string.
    """
    filtered = filter_history_by_days(history, days)
    filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    lines = []

    if excel_bom:
        lines.append("\ufeff")

    lines.append(",".join(CSV_COLUMNS))

    for entry in filtered:
        row = [
            entry.get("timestamp", ""),
            str(entry.get("five_hour", "") if entry.get("five_hour") is not None else ""),
            str(entry.get("seven_day", "") if entry.get("seven_day") is not None else ""),
            str(
                entry.get("seven_day_sonnet", "")
                if entry.get("seven_day_sonnet") is not None
                else ""
            ),
            str(
                entry.get("seven_day_opus", "")
                if entry.get("seven_day_opus") is not None
                else ""
            ),
        ]
        lines.append(",".join(row))

    return "\n".join(lines)


def export_json(history: list, days: Optional[int] = None) -> str:
    """Export history to JSON format.

    Args:
        history: List of history entries.
        days: Filter to last N days (None for all).

    Returns:
        JSON formatted string.
    """
    filtered = filter_history_by_days(history, days)
    filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return json.dumps(filtered, indent=2)


def export_influx(history: list, days: Optional[int] = None) -> str:
    """Export history to InfluxDB line protocol format.

    Args:
        history: List of history entries.
        days: Filter to last N days (None for all).

    Returns:
        InfluxDB line protocol formatted string.
    """
    filtered = filter_history_by_days(history, days)
    filtered.sort(key=lambda x: x.get("timestamp", ""))

    lines = []

    for entry in filtered:
        ts = entry.get("timestamp", "")
        if not ts:
            continue

        # Parse timestamp and convert to nanoseconds
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ns = int(dt.timestamp() * 1_000_000_000)
        except (ValueError, TypeError):
            continue

        # Build field set
        fields = []
        if entry.get("five_hour") is not None:
            fields.append(f"session_pct={entry['five_hour']}")
        if entry.get("seven_day") is not None:
            fields.append(f"weekly_pct={entry['seven_day']}")
        if entry.get("seven_day_sonnet") is not None:
            fields.append(f"sonnet_pct={entry['seven_day_sonnet']}")
        if entry.get("seven_day_opus") is not None:
            fields.append(f"opus_pct={entry['seven_day_opus']}")

        if fields:
            line = f"claude_usage {','.join(fields)} {ns}"
            lines.append(line)

    return "\n".join(lines)


def push_to_influxdb(
    url: str,
    data: str,
    token: Optional[str] = None,
    org: Optional[str] = None,
    bucket: Optional[str] = None,
    timeout: int = 10,
) -> bool:
    """Push data to InfluxDB v2 API.

    Args:
        url: InfluxDB base URL (e.g., http://localhost:8086).
        data: InfluxDB line protocol data.
        token: InfluxDB API token.
        org: InfluxDB organization.
        bucket: InfluxDB bucket.
        timeout: Request timeout in seconds.

    Returns:
        True if push was successful.

    Raises:
        Exception: If the request fails.
    """
    # Build write URL
    write_url = f"{url.rstrip('/')}/api/v2/write"
    if org:
        write_url += f"?org={org}"
        if bucket:
            write_url += f"&bucket={bucket}"

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
    }
    if token:
        headers["Authorization"] = f"Token {token}"

    req = urllib.request.Request(
        write_url,
        data=data.encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status in (200, 204)
    except urllib.error.HTTPError as e:
        raise Exception(f"InfluxDB error: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise Exception(f"Connection error: {e.reason}") from e


def run_export(
    format_type: str,
    days: Optional[int],
    output_file: Optional[str],
    excel_bom: bool,
) -> int:
    """Run the export command.

    Args:
        format_type: Export format ('csv' or 'json').
        days: Filter to last N days (None for all).
        output_file: Output file path (None for stdout).
        excel_bom: Add UTF-8 BOM for Excel compatibility.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    history = load_history()

    if not history:
        print(
            f"{Colors.YELLOW}Warning: No history data available{Colors.RESET}",
            file=sys.stderr,
        )
        return 0

    if format_type == "csv":
        output = export_csv(history, days, excel_bom)
    elif format_type == "influx":
        output = export_influx(history, days)
    else:
        output = export_json(history, days)

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
            print(
                f"{Colors.GREEN}Exported to {output_file}{Colors.RESET}",
                file=sys.stderr,
            )
        except IOError as e:
            print(
                f"{Colors.RED}Error writing to {output_file}: {e}{Colors.RESET}",
                file=sys.stderr,
            )
            return 1
    else:
        print(output)

    return 0
