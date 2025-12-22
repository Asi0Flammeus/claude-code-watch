"""HTML report generator with charts and visualizations."""

from __future__ import annotations

import statistics
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from claude_watch.display.analytics import (
    SUBSCRIPTION_PLANS,
    get_daily_peaks,
    get_period_stats,
)
from claude_watch.display.colors import Colors
from claude_watch.history.storage import load_history

# Report output directory
REPORT_DIR = Path.home() / ".claude"


def generate_svg_chart(
    values: list,
    timestamps: list,
    width: int = 600,
    height: int = 200,
    color: str = "#8b5cf6",
    title: str = "",
) -> str:
    """Generate an SVG line chart for usage data.

    Args:
        values: List of numeric values.
        timestamps: List of ISO timestamp strings.
        width: Chart width in pixels.
        height: Chart height in pixels.
        color: Line color (hex).
        title: Optional chart title.

    Returns:
        SVG markup string.
    """
    if not values:
        return f'<svg width="{width}" height="{height}"><text x="50%" y="50%" text-anchor="middle" fill="#6b7280">No data</text></svg>'

    padding = 40
    chart_width = width - padding * 2
    chart_height = height - padding * 2

    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val if max_val > min_val else 1

    # Generate path points
    points = []
    for i, v in enumerate(values):
        x = padding + (i / max(1, len(values) - 1)) * chart_width
        y = padding + chart_height - ((v - min_val) / val_range) * chart_height
        points.append(f"{x:.1f},{y:.1f}")

    path = f"M {' L '.join(points)}"

    # Generate area fill path
    area_points = points + [f"{padding + chart_width:.1f},{padding + chart_height:.1f}", f"{padding:.1f},{padding + chart_height:.1f}"]
    area_path = f"M {' L '.join(area_points)} Z"

    # X-axis labels
    x_labels = ""
    if timestamps:
        try:
            first_dt = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00")).astimezone()
            last_dt = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00")).astimezone()

            # Check span to determine format
            span_hours = (last_dt - first_dt).total_seconds() / 3600
            if span_hours <= 48:
                first_label = first_dt.strftime("%H:%M")
                last_label = last_dt.strftime("%H:%M")
            else:
                first_label = first_dt.strftime("%b %d")
                last_label = last_dt.strftime("%b %d")

            x_labels = f'''
                <text x="{padding}" y="{height - 10}" fill="#9ca3af" font-size="12">{first_label}</text>
                <text x="{width - padding}" y="{height - 10}" fill="#9ca3af" font-size="12" text-anchor="end">{last_label}</text>
            '''
        except (ValueError, IndexError):
            pass

    # Y-axis labels
    y_labels = f'''
        <text x="{padding - 5}" y="{padding + 5}" fill="#9ca3af" font-size="12" text-anchor="end">{max_val:.0f}%</text>
        <text x="{padding - 5}" y="{padding + chart_height}" fill="#9ca3af" font-size="12" text-anchor="end">{min_val:.0f}%</text>
    '''

    # Title
    title_svg = ""
    if title:
        title_svg = f'<text x="{width / 2}" y="20" fill="#f3f4f6" font-size="14" font-weight="bold" text-anchor="middle">{title}</text>'

    return f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:{color};stop-opacity:0.3"/>
                <stop offset="100%" style="stop-color:{color};stop-opacity:0.05"/>
            </linearGradient>
        </defs>
        {title_svg}
        <path d="{area_path}" fill="url(#areaGradient)"/>
        <path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>
        {x_labels}
        {y_labels}
    </svg>'''


def generate_heatmap(
    history: list,
    field: str = "five_hour",
    width: int = 500,
    height: int = 180,
) -> str:
    """Generate an SVG heatmap showing usage by day and hour.

    Args:
        history: List of history entries.
        field: Field to analyze.
        width: Chart width in pixels.
        height: Chart height in pixels.

    Returns:
        SVG markup string.
    """
    # Aggregate by day of week and hour
    by_day_hour: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for h in history:
        if h.get(field) is None:
            continue
        try:
            dt = datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            dow = local_dt.weekday()  # 0=Mon, 6=Sun
            hour = local_dt.hour
            by_day_hour[dow][hour].append(h[field])
        except (ValueError, KeyError):
            continue

    if not by_day_hour:
        return f'<svg width="{width}" height="{height}"><text x="50%" y="50%" text-anchor="middle" fill="#6b7280">No data</text></svg>'

    # Calculate averages
    heatmap_data: dict[tuple[int, int], float | None] = {}
    max_avg = 0.0
    for dow in range(7):
        for hour in range(24):
            vals = by_day_hour[dow][hour]
            if vals:
                avg = statistics.mean(vals)
                heatmap_data[(dow, hour)] = avg
                max_avg = max(max_avg, avg)
            else:
                heatmap_data[(dow, hour)] = None

    # Generate SVG
    cell_width = (width - 60) / 24
    cell_height = (height - 40) / 7
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    cells = ""
    for dow in range(7):
        for hour in range(24):
            x = 40 + hour * cell_width
            y = 20 + dow * cell_height
            val = heatmap_data[(dow, hour)]

            if val is not None:
                # Color intensity based on value
                intensity = val / max_avg if max_avg > 0 else 0
                if val >= 90:
                    color = f"rgba(239, 68, 68, {0.3 + intensity * 0.7})"  # Red
                elif val >= 75:
                    color = f"rgba(234, 179, 8, {0.3 + intensity * 0.7})"  # Yellow
                else:
                    color = f"rgba(139, 92, 246, {0.3 + intensity * 0.7})"  # Purple
            else:
                color = "rgba(55, 65, 81, 0.3)"

            cells += f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_width - 1:.1f}" height="{cell_height - 1:.1f}" fill="{color}" rx="2"/>'

    # Day labels
    day_labels = ""
    for i, day in enumerate(days):
        y = 20 + i * cell_height + cell_height / 2 + 4
        day_labels += f'<text x="35" y="{y:.1f}" fill="#9ca3af" font-size="10" text-anchor="end">{day}</text>'

    # Hour labels (every 6 hours)
    hour_labels = ""
    for hour in [0, 6, 12, 18]:
        x = 40 + hour * cell_width + cell_width / 2
        hour_labels += f'<text x="{x:.1f}" y="{height - 5}" fill="#9ca3af" font-size="10" text-anchor="middle">{hour}:00</text>'

    return f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        {cells}
        {day_labels}
        {hour_labels}
    </svg>'''


def generate_cost_table(history: list, config: dict) -> str:
    """Generate HTML table comparing subscription costs.

    Args:
        history: List of history entries.
        config: User configuration.

    Returns:
        HTML table markup.
    """
    plan_key = config.get("subscription_plan", "pro")

    rows = ""
    for plan_id, plan_info in SUBSCRIPTION_PLANS.items():
        is_current = plan_id == plan_key
        highlight = "background: rgba(139, 92, 246, 0.2);" if is_current else ""
        badge = '<span style="background: #8b5cf6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 8px;">Current</span>' if is_current else ""

        rows += f'''
            <tr style="{highlight}">
                <td style="padding: 12px; border-bottom: 1px solid #374151;">{plan_info["name"]}{badge}</td>
                <td style="padding: 12px; border-bottom: 1px solid #374151; text-align: right;">${plan_info["cost"]:.0f}/mo</td>
                <td style="padding: 12px; border-bottom: 1px solid #374151; text-align: right;">{plan_info["messages_5h"]} msg/5h</td>
                <td style="padding: 12px; border-bottom: 1px solid #374151; text-align: right;">{plan_info["weekly_sonnet_hours"]}h Sonnet</td>
                <td style="padding: 12px; border-bottom: 1px solid #374151; text-align: right;">{plan_info["weekly_opus_hours"]}h Opus</td>
            </tr>
        '''

    return f'''
        <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
            <thead>
                <tr style="background: #1f2937;">
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #4b5563;">Plan</th>
                    <th style="padding: 12px; text-align: right; border-bottom: 2px solid #4b5563;">Cost</th>
                    <th style="padding: 12px; text-align: right; border-bottom: 2px solid #4b5563;">Session Limit</th>
                    <th style="padding: 12px; text-align: right; border-bottom: 2px solid #4b5563;">Weekly Sonnet</th>
                    <th style="padding: 12px; text-align: right; border-bottom: 2px solid #4b5563;">Weekly Opus</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    '''


def generate_recommendations(data: dict, history: list, config: dict) -> str:
    """Generate HTML recommendations section.

    Args:
        data: Current usage data.
        history: Historical usage data.
        config: User configuration.

    Returns:
        HTML markup for recommendations.
    """
    recommendations = []

    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)

    # Session recommendations
    if five_hour >= 90:
        recommendations.append({
            "severity": "critical",
            "icon": "!",
            "message": "Session limit nearly reached - wait for reset or reduce request intensity",
            "color": "#ef4444"
        })
    elif five_hour >= 75:
        recommendations.append({
            "severity": "warning",
            "icon": "*",
            "message": "High session usage - consider pacing your requests",
            "color": "#eab308"
        })

    # Weekly recommendations
    if seven_day >= 85:
        recommendations.append({
            "severity": "warning",
            "icon": "*",
            "message": "Weekly limit approaching - prioritize critical tasks",
            "color": "#eab308"
        })

    # Pattern-based recommendations
    peaks = get_daily_peaks(history, "five_hour")
    if peaks["peak_hour"] is not None:
        hour_str = datetime.now().replace(hour=peaks["peak_hour"], minute=0).strftime("%-I %p")
        recommendations.append({
            "severity": "info",
            "icon": "i",
            "message": f"Peak usage hour: {hour_str} - schedule intensive work outside this time",
            "color": "#8b5cf6"
        })

    if peaks["peak_day"]:
        recommendations.append({
            "severity": "info",
            "icon": "i",
            "message": f"Peak usage day: {peaks['peak_day']} - distribute work more evenly",
            "color": "#8b5cf6"
        })

    # Efficiency recommendation
    stats_7d = get_period_stats(history, 168, "five_hour")
    if stats_7d["count"] > 0 and stats_7d["avg"] < 30:
        recommendations.append({
            "severity": "success",
            "icon": "+",
            "message": "Usage is efficient - plenty of capacity available",
            "color": "#22c55e"
        })

    if not recommendations:
        recommendations.append({
            "severity": "success",
            "icon": "+",
            "message": "Usage is within healthy limits",
            "color": "#22c55e"
        })

    items = ""
    for rec in recommendations:
        items += f'''
            <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: rgba({_hex_to_rgb(rec["color"])}, 0.1); border-radius: 8px; margin-bottom: 8px;">
                <span style="display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: {rec["color"]}; color: white; border-radius: 50%; font-weight: bold; font-size: 14px;">{rec["icon"]}</span>
                <span style="color: #f3f4f6;">{rec["message"]}</span>
            </div>
        '''

    return items


def _hex_to_rgb(hex_color: str) -> str:
    """Convert hex color to RGB string."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"{r}, {g}, {b}"


def generate_report(
    period: str,
    data: dict,
    history: list,
    config: dict,
) -> str:
    """Generate a complete HTML report.

    Args:
        period: Report period ("weekly" or "monthly").
        data: Current usage data.
        history: Historical usage data.
        config: User configuration.

    Returns:
        Complete HTML document as string.
    """
    now = datetime.now(timezone.utc).astimezone()

    # Determine date range
    if period == "weekly":
        hours = 168  # 7 days
        title = "Weekly Usage Report"
        date_range = f"{(now - timedelta(days=7)).strftime('%b %d')} - {now.strftime('%b %d, %Y')}"
    else:
        hours = 720  # ~30 days
        title = "Monthly Usage Report"
        date_range = f"{(now - timedelta(days=30)).strftime('%b %d')} - {now.strftime('%b %d, %Y')}"

    # Get period-specific stats
    stats_session = get_period_stats(history, hours, "five_hour")
    stats_weekly = get_period_stats(history, hours, "seven_day")

    # Current usage
    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)
    resets_at = data.get("five_hour", {}).get("resets_at", "")

    # Format reset time
    reset_str = ""
    if resets_at:
        try:
            reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00")).astimezone()
            reset_str = reset_dt.strftime("%H:%M")
        except ValueError:
            pass

    # Generate charts
    session_chart = generate_svg_chart(
        stats_session.get("values", []),
        stats_session.get("timestamps", []),
        width=600,
        height=200,
        color="#8b5cf6",
        title="Session Usage (5-hour window)"
    )

    weekly_chart = generate_svg_chart(
        stats_weekly.get("values", []),
        stats_weekly.get("timestamps", []),
        width=600,
        height=200,
        color="#06b6d4",
        title="Weekly Usage (7-day window)"
    )

    heatmap = generate_heatmap(history, "five_hour")
    cost_table = generate_cost_table(history, config)
    recommendations = generate_recommendations(data, history, config)

    # Plan info
    plan_key = config.get("subscription_plan", "pro")
    plan_info = SUBSCRIPTION_PLANS.get(plan_key, SUBSCRIPTION_PLANS["pro"])

    # Stats cards
    stats_html = ""
    if stats_session["count"] > 0:
        stats_html = f'''
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 24px;">
                <div style="background: #1f2937; padding: 16px; border-radius: 12px; text-align: center;">
                    <div style="color: #9ca3af; font-size: 14px;">Min Session</div>
                    <div style="color: #f3f4f6; font-size: 24px; font-weight: bold;">{stats_session["min"]:.0f}%</div>
                </div>
                <div style="background: #1f2937; padding: 16px; border-radius: 12px; text-align: center;">
                    <div style="color: #9ca3af; font-size: 14px;">Max Session</div>
                    <div style="color: #f3f4f6; font-size: 24px; font-weight: bold;">{stats_session["max"]:.0f}%</div>
                </div>
                <div style="background: #1f2937; padding: 16px; border-radius: 12px; text-align: center;">
                    <div style="color: #9ca3af; font-size: 14px;">Avg Session</div>
                    <div style="color: #f3f4f6; font-size: 24px; font-weight: bold;">{stats_session["avg"]:.1f}%</div>
                </div>
                <div style="background: #1f2937; padding: 16px; border-radius: 12px; text-align: center;">
                    <div style="color: #9ca3af; font-size: 14px;">Data Points</div>
                    <div style="color: #f3f4f6; font-size: 24px; font-weight: bold;">{stats_session["count"]}</div>
                </div>
            </div>
        '''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Claude Watch</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #111827;
            color: #f3f4f6;
            line-height: 1.6;
            padding: 24px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid #374151;
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 8px;
            color: #f3f4f6;
        }}
        .header .subtitle {{
            color: #9ca3af;
            font-size: 16px;
        }}
        .section {{
            margin-bottom: 32px;
        }}
        .section h2 {{
            font-size: 20px;
            margin-bottom: 16px;
            color: #f3f4f6;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section h2::before {{
            content: '';
            display: inline-block;
            width: 4px;
            height: 20px;
            background: #8b5cf6;
            border-radius: 2px;
        }}
        .card {{
            background: #1f2937;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .current-usage {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }}
        .usage-item {{
            text-align: center;
        }}
        .usage-item .label {{
            color: #9ca3af;
            font-size: 14px;
            margin-bottom: 4px;
        }}
        .usage-item .value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .usage-item .value.green {{ color: #22c55e; }}
        .usage-item .value.yellow {{ color: #eab308; }}
        .usage-item .value.red {{ color: #ef4444; }}
        .chart-container {{
            background: #1f2937;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            overflow-x: auto;
        }}
        .footer {{
            text-align: center;
            color: #6b7280;
            font-size: 14px;
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid #374151;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="subtitle">{date_range}</div>
            <div class="subtitle" style="margin-top: 4px;">Plan: {plan_info["name"]} (${plan_info["cost"]:.0f}/mo)</div>
        </div>

        <div class="section">
            <h2>Current Status</h2>
            <div class="card">
                <div class="current-usage">
                    <div class="usage-item">
                        <div class="label">Session Usage</div>
                        <div class="value {'red' if five_hour >= 90 else 'yellow' if five_hour >= 75 else 'green'}">{five_hour:.0f}%</div>
                        <div class="label">{f"Resets at {reset_str}" if reset_str else ""}</div>
                    </div>
                    <div class="usage-item">
                        <div class="label">Weekly Usage</div>
                        <div class="value {'red' if seven_day >= 85 else 'yellow' if seven_day >= 70 else 'green'}">{seven_day:.0f}%</div>
                    </div>
                    <div class="usage-item">
                        <div class="label">Session Remaining</div>
                        <div class="value green">{100 - five_hour:.0f}%</div>
                    </div>
                    <div class="usage-item">
                        <div class="label">Weekly Remaining</div>
                        <div class="value green">{100 - seven_day:.0f}%</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Usage Statistics</h2>
            {stats_html}
        </div>

        <div class="section">
            <h2>Session Usage Trend</h2>
            <div class="chart-container">
                {session_chart}
            </div>
        </div>

        <div class="section">
            <h2>Weekly Usage Trend</h2>
            <div class="chart-container">
                {weekly_chart}
            </div>
        </div>

        <div class="section">
            <h2>Usage Heatmap (Day/Hour)</h2>
            <div class="chart-container">
                {heatmap}
            </div>
        </div>

        <div class="section">
            <h2>Subscription Plans</h2>
            <div class="card">
                {cost_table}
            </div>
        </div>

        <div class="section">
            <h2>Recommendations</h2>
            <div class="card">
                {recommendations}
            </div>
        </div>

        <div class="footer">
            Generated by claude-watch on {now.strftime("%Y-%m-%d %H:%M:%S %Z")}
        </div>
    </div>
</body>
</html>'''

    return html


def run_report(
    period: str,
    data: dict,
    config: dict,
    open_browser: bool = False,
) -> int:
    """Generate and save an HTML report.

    Args:
        period: Report period ("weekly" or "monthly").
        data: Current usage data.
        config: User configuration.
        open_browser: If True, open the report in default browser.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    history = load_history()

    if not history:
        print(f"{Colors.YELLOW}Warning: No history data available for report{Colors.RESET}")
        print(f"{Colors.DIM}Run 'claude-watch' periodically to collect data{Colors.RESET}")
        return 1

    # Generate report
    html = generate_report(period, data, history, config)

    # Save to file
    now = datetime.now(timezone.utc).astimezone()
    filename = f"report-{period}-{now.strftime('%Y%m%d')}.html"
    filepath = REPORT_DIR / filename

    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"{Colors.GREEN}Report saved to: {filepath}{Colors.RESET}")
    except OSError as e:
        print(f"{Colors.RED}Error writing report: {e}{Colors.RESET}")
        return 1

    # Open in browser if requested
    if open_browser:
        try:
            webbrowser.open(f"file://{filepath}")
            print(f"{Colors.DIM}Opened in default browser{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}Could not open browser: {e}{Colors.RESET}")
            print(f"{Colors.DIM}Open manually: file://{filepath}{Colors.RESET}")

    return 0


__all__ = [
    "generate_svg_chart",
    "generate_heatmap",
    "generate_cost_table",
    "generate_recommendations",
    "generate_report",
    "run_report",
    "REPORT_DIR",
]
