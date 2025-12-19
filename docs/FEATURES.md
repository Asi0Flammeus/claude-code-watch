# Feature Specifications

Design specifications for upcoming `claude-usage` CLI features.

---

## 1. Shell Prompt Integration (`--prompt`)

### Purpose
Compact output for embedding in shell prompts (PS1, starship, oh-my-zsh, powerlevel10k).

### Usage
```bash
claude-usage --prompt [FORMAT]
```

### Output Formats

| Format | Output | Description |
|--------|--------|-------------|
| `default` | `45↑/12` | session%trend/weekly% |
| `minimal` | `45` | session% only |
| `full` | `S:45↑ W:12` | labeled |
| `icon` | `◐ 45↑` | unicode indicator |

### Trend Indicators
- `↑` - Usage increased >5% in last hour
- `↓` - Usage decreased (reset occurred)
- `→` - Stable (±5%)

### Color Codes (optional `--prompt-color`)
```
< 50%  → green  (normal)
50-79% → yellow (caution)
80-94% → red    (warning)
≥ 95%  → red+bold (critical)
```

### Exit Codes
- `0` - Success, under 80%
- `1` - Warning, 80-94%
- `2` - Critical, ≥95%
- `3` - Error (auth, network)

### Implementation

```python
def cmd_prompt(format: str = "default", color: bool = False) -> str:
    """Generate prompt-friendly output."""
    data = fetch_usage_cached(max_age=60)  # Cache 60s to avoid API spam

    session = data.get("five_hour", {}).get("utilization", 0)
    weekly = data.get("seven_day", {}).get("utilization", 0)
    trend = get_trend_indicator(session)  # Compare with last recorded

    if format == "minimal":
        return f"{int(session)}"
    elif format == "full":
        return f"S:{int(session)}{trend} W:{int(weekly)}"
    elif format == "icon":
        icon = get_usage_icon(session)  # ○◔◑◕●
        return f"{icon} {int(session)}{trend}"
    else:  # default
        return f"{int(session)}{trend}/{int(weekly)}"
```

### Cache Strategy
- Cache file: `~/.claude/.usage_cache.json`
- Max age: 60 seconds (configurable)
- Fallback: Return `--` on error (don't break prompt)

### Shell Integration Examples

**Bash (.bashrc):**
```bash
claude_usage() {
    claude-usage --prompt 2>/dev/null || echo "--"
}
PS1='[\u@\h \W $(claude_usage)]$ '
```

**Starship (starship.toml):**
```toml
[custom.claude]
command = "claude-usage --prompt"
when = "command -v claude-usage"
format = "[$output]($style) "
style = "bold cyan"
```

**Oh-My-Zsh (.zshrc):**
```zsh
PROMPT='%n@%m %~ $(claude-usage --prompt 2>/dev/null) %# '
```

---

## 2. Watch Mode (`--watch`)

### Purpose
Live-updating display for monitoring usage during heavy sessions.

### Usage
```bash
claude-usage --watch [INTERVAL]
claude-usage -w 30              # Refresh every 30 seconds
claude-usage --watch 60 -a      # With analytics, every 60s
```

### Parameters
| Param | Default | Range | Description |
|-------|---------|-------|-------------|
| `INTERVAL` | 30 | 10-300 | Seconds between refreshes |

### Display
```
╭─────────────────────────────────────────────────╮
│  Claude Usage Monitor          [Refresh: 30s]  │
│  Last update: 14:32:05                         │
╰─────────────────────────────────────────────────╯

Plan usage limits

Current session      ████████░░░░░░░░░░░░░░░░░  34% used
Resets in 3 hr 25 min                           ↑ +2% since start

Weekly limits

All models           ██░░░░░░░░░░░░░░░░░░░░░░░  9% used
Resets Tue 9:59 AM

───────────────────────────────────────────────────
Session started: 14:30:00 | Changes: +5% session
Press Ctrl+C to exit
```

### Implementation

```python
import signal

def cmd_watch(interval: int = 30, with_analytics: bool = False):
    """Live-updating usage display."""
    initial_data = fetch_usage()
    start_time = datetime.now()

    def handle_sigint(sig, frame):
        print("\n\nMonitoring stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    while True:
        clear_screen()
        print_watch_header(interval, start_time)

        try:
            data = fetch_usage()
            display_usage(data)
            display_delta(data, initial_data)

            if with_analytics:
                display_mini_analytics(data, load_history())

        except Exception as e:
            print(f"Error: {e} - retrying...")

        print_watch_footer(start_time, initial_data)
        time.sleep(interval)

def clear_screen():
    """Clear terminal screen."""
    print("\033[2J\033[H", end="")

def display_delta(current: dict, initial: dict):
    """Show change since monitoring started."""
    curr_session = current.get("five_hour", {}).get("utilization", 0)
    init_session = initial.get("five_hour", {}).get("utilization", 0)
    delta = curr_session - init_session

    if delta > 0:
        print(f"  {Colors.UP}↑ +{delta:.1f}% since start{Colors.RESET}")
    elif delta < 0:
        print(f"  {Colors.DOWN}↓ {delta:.1f}% (reset occurred){Colors.RESET}")
```

### Features
- Delta tracking from session start
- Countdown to next refresh
- Graceful Ctrl+C handling
- Optional analytics mode (`-a`)
- Error recovery with retry

---

## 3. Desktop Notifications (`--notify`)

### Purpose
Proactive alerts when approaching usage limits.

### Usage
```bash
claude-usage --notify                    # Check and notify if threshold hit
claude-usage --notify-at 80,90,95        # Custom thresholds
claude-usage --notify-daemon             # Background daemon mode
```

### Thresholds
| Level | Default | Icon | Urgency |
|-------|---------|------|---------|
| Warning | 80% | ⚠️ | normal |
| Critical | 90% | 🔴 | critical |
| Limit | 95% | 🛑 | critical |

### Notification Content
```
Title: Claude Usage Warning
Body:  Session usage at 85% - Resets in 2h 15m
       Consider pausing for rate limit recovery.
```

### Implementation

```python
import subprocess
import platform

NOTIFY_STATE_FILE = Path.home() / ".claude" / ".notify_state.json"

def send_notification(title: str, body: str, urgency: str = "normal"):
    """Send desktop notification cross-platform."""
    system = platform.system()

    if system == "Linux":
        subprocess.run([
            "notify-send",
            f"--urgency={urgency}",
            "--app-name=Claude Usage",
            "--icon=dialog-warning",
            title, body
        ], check=False)

    elif system == "Darwin":  # macOS
        script = f'''
        display notification "{body}" with title "{title}" sound name "Ping"
        '''
        subprocess.run(["osascript", "-e", script], check=False)

    elif system == "Windows":
        # PowerShell toast notification
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
        $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
        $xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{title}"))
        $xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{body}"))
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Usage").Show($toast)
        '''
        subprocess.run(["powershell", "-Command", ps_script], check=False)

def check_and_notify(thresholds: list = [80, 90, 95]):
    """Check usage and send notification if threshold crossed."""
    data = fetch_usage()
    session = data.get("five_hour", {}).get("utilization", 0)

    # Load state to avoid duplicate notifications
    state = load_notify_state()
    last_notified = state.get("last_threshold", 0)

    for threshold in sorted(thresholds):
        if session >= threshold and threshold > last_notified:
            urgency = "critical" if threshold >= 90 else "normal"
            reset_time = format_relative_time(data["five_hour"]["resets_at"])

            send_notification(
                title=f"Claude Usage: {int(session)}%",
                body=f"Session at {int(session)}% - Resets in {reset_time}",
                urgency=urgency
            )

            state["last_threshold"] = threshold
            state["last_notified"] = datetime.now().isoformat()
            save_notify_state(state)
            break

    # Reset state if usage dropped (new session)
    if session < 50 and last_notified > 0:
        state["last_threshold"] = 0
        save_notify_state(state)

def cmd_notify_daemon(interval: int = 300):
    """Background daemon for periodic notification checks."""
    print(f"Starting notification daemon (checking every {interval}s)")
    print("Press Ctrl+C to stop")

    while True:
        try:
            check_and_notify()
        except Exception as e:
            print(f"Check failed: {e}")
        time.sleep(interval)
```

### Daemon Mode
For continuous monitoring, integrate with systemd:

```ini
# ~/.config/systemd/user/claude-usage-notify.service
[Unit]
Description=Claude Usage Notification Daemon

[Service]
ExecStart=/path/to/claude-usage --notify-daemon
Restart=always

[Install]
WantedBy=default.target
```

---

## 4. Tmux Integration (`--tmux`)

### Purpose
Optimized output for tmux status bar with session %, reset time, and colors.

### Usage
```bash
claude-usage --tmux              # Compact colored output
claude-usage --tmux --no-color   # For non-256color terminals
```

### Output Format
```
S:45% 2h15m W:12%
```

With colors (tmux format):
```
#[fg=yellow]S:45%#[fg=default] 2h15m #[fg=green]W:12%#[fg=default]
```

### Color Mapping (tmux)
| Usage | Color Code |
|-------|------------|
| 0-49% | `#[fg=green]` |
| 50-79% | `#[fg=yellow]` |
| 80-94% | `#[fg=red]` |
| ≥95% | `#[fg=red,bold]` |

### Implementation

```python
def cmd_tmux(no_color: bool = False) -> str:
    """Generate tmux status bar output."""
    try:
        data = fetch_usage_cached(max_age=60)
    except Exception:
        return "#[fg=red]CC:ERR#[fg=default]" if not no_color else "CC:ERR"

    session = data.get("five_hour", {}).get("utilization", 0)
    weekly = data.get("seven_day", {}).get("utilization", 0)
    reset_at = data.get("five_hour", {}).get("resets_at", "")

    # Format reset time compactly
    reset_str = format_reset_compact(reset_at)  # "2h15m" or "45m"

    if no_color:
        return f"S:{int(session)}% {reset_str} W:{int(weekly)}%"

    session_color = get_tmux_color(session)
    weekly_color = get_tmux_color(weekly)

    return (
        f"{session_color}S:{int(session)}%#[fg=default] "
        f"{reset_str} "
        f"{weekly_color}W:{int(weekly)}%#[fg=default]"
    )

def get_tmux_color(pct: float) -> str:
    """Return tmux color code for percentage."""
    if pct >= 95:
        return "#[fg=red,bold]"
    elif pct >= 80:
        return "#[fg=red]"
    elif pct >= 50:
        return "#[fg=yellow]"
    return "#[fg=green]"

def format_reset_compact(reset_at: str) -> str:
    """Format reset time as compact string: '2h15m' or '45m'."""
    if not reset_at:
        return ""

    reset_dt = parse_reset_time(reset_at)
    now = datetime.now(timezone.utc)
    delta = reset_dt - now
    total_seconds = max(0, int(delta.total_seconds()))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"
```

### Tmux Configuration

**~/.tmux.conf:**
```bash
# Update every 60 seconds
set -g status-interval 60

# Right status with Claude usage
set -g status-right '#(claude-usage --tmux 2>/dev/null) | %H:%M'

# Or with fallback
set -g status-right '#(claude-usage --tmux 2>/dev/null || echo "CC:--") | %H:%M'
```

### Cache Requirement
- Must use cache to avoid API calls every `status-interval`
- Cache file: `~/.claude/.usage_cache.json`
- Max age: 60 seconds
- Silent fallback on error

---

## 5. Hook Generator (`--generate-hook`)

### Purpose
Generate Claude Code hook scripts for pre-session usage warnings.

### Usage
```bash
claude-usage --generate-hook              # Output to stdout
claude-usage --generate-hook --install    # Install to ~/.claude/hooks/
```

### Hook Types

| Hook | Trigger | Purpose |
|------|---------|---------|
| `PreToolUse` | Before any tool | Check before heavy operations |
| `PostToolUse` | After tool completes | Update usage after calls |
| `Stop` | Session end | Record final usage |

### Generated Hook Script

```bash
#!/bin/bash
# Claude Code Usage Check Hook
# Generated by: claude-usage --generate-hook
# Install to: ~/.claude/hooks/pre-session-check.sh

THRESHOLD=${CLAUDE_USAGE_THRESHOLD:-80}
USAGE_CMD="claude-usage"

# Only check at session start (first tool call)
STATE_FILE="/tmp/.claude-usage-session-$$"
if [[ -f "$STATE_FILE" ]]; then
    exit 0  # Already checked this session
fi
touch "$STATE_FILE"

# Get current usage
USAGE_JSON=$($USAGE_CMD --json 2>/dev/null)
if [[ $? -ne 0 ]]; then
    exit 0  # Don't block on errors
fi

SESSION_PCT=$(echo "$USAGE_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(int(data.get('five_hour', {}).get('utilization', 0)))
" 2>/dev/null)

if [[ -z "$SESSION_PCT" ]]; then
    exit 0
fi

# Check threshold
if [[ $SESSION_PCT -ge $THRESHOLD ]]; then
    RESET_TIME=$($USAGE_CMD --json 2>/dev/null | python3 -c "
import sys, json
from datetime import datetime, timezone
data = json.load(sys.stdin)
reset = data.get('five_hour', {}).get('resets_at', '')
if reset:
    dt = datetime.fromisoformat(reset.replace('Z', '+00:00'))
    delta = dt - datetime.now(timezone.utc)
    hours = int(delta.total_seconds() // 3600)
    mins = int((delta.total_seconds() % 3600) // 60)
    print(f'{hours}h {mins}m')
" 2>/dev/null)

    echo "⚠️  Claude Usage Warning: Session at ${SESSION_PCT}%"
    echo "   Resets in: ${RESET_TIME}"
    echo "   Consider waiting for rate limit recovery."
    echo ""
fi

exit 0
```

### Implementation

```python
HOOK_TEMPLATE = '''#!/bin/bash
# Claude Code Usage Check Hook
# Generated by: claude-usage --generate-hook
# Installed: {timestamp}

THRESHOLD=${{CLAUDE_USAGE_THRESHOLD:-{threshold}}}

# ... (full script as above)
'''

def cmd_generate_hook(threshold: int = 80, install: bool = False):
    """Generate Claude Code hook script."""
    script = HOOK_TEMPLATE.format(
        timestamp=datetime.now().isoformat(),
        threshold=threshold
    )

    if install:
        hooks_dir = Path.home() / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        hook_file = hooks_dir / "pre-session-check.sh"
        hook_file.write_text(script)
        hook_file.chmod(0o755)

        # Update settings.json to register hook
        settings_file = Path.home() / ".claude" / "settings.json"
        settings = json.loads(settings_file.read_text()) if settings_file.exists() else {}

        if "hooks" not in settings:
            settings["hooks"] = {}
        settings["hooks"]["PreToolUse"] = str(hook_file)

        settings_file.write_text(json.dumps(settings, indent=2))

        print(f"✓ Hook installed: {hook_file}")
        print(f"✓ Settings updated: {settings_file}")
        print(f"\nUsage threshold: {threshold}%")
        print("Set CLAUDE_USAGE_THRESHOLD env var to customize.")
    else:
        print(script)
```

### Configuration
Environment variables:
- `CLAUDE_USAGE_THRESHOLD` - Warning threshold (default: 80)
- `CLAUDE_USAGE_SILENT` - Suppress warnings if set

---

## 6. Enhanced Forecast (`--forecast`)

### Purpose
Predict when limits will be hit based on usage patterns.

### Usage
```bash
claude-usage --forecast           # Show predictions
claude-usage -a --forecast        # With analytics
```

### Output
```
Usage Forecast

Current session: 45% used
  └─ At current rate: limit in ~2.3 hours
  └─ Conservative estimate: ~1.8 hours
  └─ Optimistic estimate: ~3.1 hours

Weekly usage: 12% used
  └─ Daily average: 2.4%/day
  └─ Projected week-end: 28%
  └─ Days until limit: N/A (on track)

Recommendations:
  • You can sustain current pace for 2+ hours
  • Heavy usage sessions best before 3 PM (your pattern)
  • Weekly capacity sufficient for normal usage
```

### Implementation

```python
def calculate_forecast(data: dict, history: list) -> dict:
    """Calculate usage forecasts based on patterns."""
    session = data.get("five_hour", {}).get("utilization", 0)
    weekly = data.get("seven_day", {}).get("utilization", 0)
    session_reset = data.get("five_hour", {}).get("resets_at", "")

    # Get recent usage rate (last hour)
    recent = get_period_stats(history, 1, "five_hour")

    if recent["count"] >= 2:
        hourly_rate = recent["max"] - recent["min"]
        hourly_rate = max(hourly_rate, 0.1)  # Avoid division by zero
    else:
        # Estimate from current usage and reset time
        hourly_rate = estimate_hourly_rate(session, session_reset)

    # Calculate time to limit
    remaining = 100 - session
    hours_to_limit = remaining / hourly_rate if hourly_rate > 0 else float('inf')

    # Confidence intervals based on variance
    if recent["count"] >= 5:
        variance = statistics.stdev([h["five_hour"] for h in history[-10:] if h.get("five_hour")])
        conservative = remaining / (hourly_rate + variance)
        optimistic = remaining / max(hourly_rate - variance, 0.1)
    else:
        conservative = hours_to_limit * 0.7
        optimistic = hours_to_limit * 1.5

    # Weekly projection
    daily_stats = get_period_stats(history, 24, "seven_day")
    if daily_stats["count"] >= 2:
        daily_rate = daily_stats["max"] - daily_stats["min"]
    else:
        daily_rate = weekly / 7 if weekly > 0 else 2  # Estimate

    days_remaining = 7 - get_days_into_week()
    projected_weekly = weekly + (daily_rate * days_remaining)

    return {
        "session": {
            "current": session,
            "hourly_rate": hourly_rate,
            "hours_to_limit": hours_to_limit,
            "conservative_hours": conservative,
            "optimistic_hours": optimistic,
        },
        "weekly": {
            "current": weekly,
            "daily_rate": daily_rate,
            "projected_end": min(projected_weekly, 100),
            "days_to_limit": (100 - weekly) / daily_rate if daily_rate > 0 else None,
        }
    }

def display_forecast(forecast: dict):
    """Display usage forecast."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Usage Forecast{Colors.RESET}")
    print()

    s = forecast["session"]
    print(f"{Colors.WHITE}Current session: {s['current']:.0f}% used{Colors.RESET}")

    if s["hours_to_limit"] < 24:
        print(f"  └─ At current rate: limit in ~{s['hours_to_limit']:.1f} hours")
        print(f"  └─ Conservative: ~{s['conservative_hours']:.1f} hours")
        print(f"  └─ Optimistic: ~{s['optimistic_hours']:.1f} hours")
    else:
        print(f"  └─ Limit unlikely at current pace")

    print()

    w = forecast["weekly"]
    print(f"{Colors.WHITE}Weekly usage: {w['current']:.0f}% used{Colors.RESET}")
    print(f"  └─ Daily average: {w['daily_rate']:.1f}%/day")
    print(f"  └─ Projected week-end: {w['projected_end']:.0f}%")

    if w["days_to_limit"] and w["days_to_limit"] < 7:
        print(f"  └─ {Colors.YELLOW}Days until limit: {w['days_to_limit']:.1f}{Colors.RESET}")
    else:
        print(f"  └─ {Colors.GREEN}On track for week{Colors.RESET}")

    print()
```

---

## 7. HTML Report (`--report`)

### Purpose
Generate comprehensive usage reports in HTML format.

### Usage
```bash
claude-usage --report weekly              # Generate weekly report
claude-usage --report monthly             # Generate monthly report
claude-usage --report weekly -o report.html  # Custom output file
claude-usage --report weekly --open       # Generate and open in browser
```

### Report Contents
1. **Summary Card** - Current usage, period stats
2. **Usage Chart** - SVG line chart of usage over time
3. **Peak Analysis** - Busiest days/hours heatmap
4. **Cost Analysis** - API equivalent, subscription comparison
5. **Recommendations** - Personalized suggestions

### HTML Template Structure

```html
<!DOCTYPE html>
<html>
<head>
    <title>Claude Usage Report - {period}</title>
    <style>
        :root {
            --bg: #0d1117;
            --card-bg: #161b22;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --green: #3fb950;
            --yellow: #d29922;
            --red: #f85149;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }
        .card {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
        }
        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: var(--accent);
        }
        .chart { width: 100%; height: 200px; }
        .heatmap { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
        .heatmap-cell {
            aspect-ratio: 1;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
        }
    </style>
</head>
<body>
    <h1>Claude Usage Report</h1>
    <p class="subtitle">{start_date} - {end_date}</p>

    <!-- Summary Card -->
    <div class="card">
        <h2>Summary</h2>
        <div class="stat-grid">
            <div class="stat">
                <div class="stat-value">{avg_session}%</div>
                <div class="stat-label">Avg Session Usage</div>
            </div>
            <div class="stat">
                <div class="stat-value">{peak_session}%</div>
                <div class="stat-label">Peak Session</div>
            </div>
            <div class="stat">
                <div class="stat-value">{avg_weekly}%</div>
                <div class="stat-label">Avg Weekly Usage</div>
            </div>
            <div class="stat">
                <div class="stat-value">${api_cost}</div>
                <div class="stat-label">API Equivalent</div>
            </div>
        </div>
    </div>

    <!-- Usage Chart -->
    <div class="card">
        <h2>Usage Over Time</h2>
        <svg class="chart" viewBox="0 0 800 200">
            {svg_chart}
        </svg>
    </div>

    <!-- Heatmap -->
    <div class="card">
        <h2>Usage Patterns</h2>
        <div class="heatmap">
            {heatmap_cells}
        </div>
    </div>

    <!-- Cost Analysis -->
    <div class="card">
        <h2>Cost Analysis</h2>
        {cost_comparison_table}
    </div>

    <!-- Recommendations -->
    <div class="card">
        <h2>Recommendations</h2>
        <ul>
            {recommendations}
        </ul>
    </div>

    <footer>
        Generated by claude-usage on {generated_at}
    </footer>
</body>
</html>
```

### Implementation

```python
import webbrowser
from string import Template

HTML_TEMPLATE = """..."""  # Full template above

def generate_svg_chart(data_points: list, width: int = 800, height: int = 200) -> str:
    """Generate SVG line chart from data points."""
    if not data_points:
        return ""

    # Normalize values to chart dimensions
    max_val = max(d["value"] for d in data_points) or 100
    points = []

    for i, d in enumerate(data_points):
        x = (i / (len(data_points) - 1)) * (width - 40) + 20
        y = height - 20 - (d["value"] / max_val * (height - 40))
        points.append(f"{x},{y}")

    path = f'<path d="M {" L ".join(points)}" fill="none" stroke="#58a6ff" stroke-width="2"/>'

    # Add gradient fill
    gradient = f'''
    <defs>
        <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#58a6ff" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#58a6ff" stop-opacity="0"/>
        </linearGradient>
    </defs>
    <path d="M 20,{height-20} L {" L ".join(points)} L {width-20},{height-20} Z" fill="url(#fill)"/>
    '''

    return gradient + path

def generate_heatmap(history: list) -> str:
    """Generate day/hour usage heatmap."""
    # Aggregate by day-of-week and hour
    by_dow_hour = defaultdict(list)

    for h in history:
        if h.get("five_hour") is None:
            continue
        try:
            dt = datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00")).astimezone()
            key = (dt.weekday(), dt.hour // 4)  # 4-hour blocks
            by_dow_hour[key].append(h["five_hour"])
        except:
            continue

    cells = []
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for dow in range(7):
        for block in range(6):  # 6 4-hour blocks
            key = (dow, block)
            values = by_dow_hour.get(key, [])
            avg = statistics.mean(values) if values else 0
            color = get_heatmap_color(avg)
            cells.append(f'<div class="heatmap-cell" style="background:{color}" title="{days[dow]} {block*4}:00">{int(avg)}</div>')

    return "\n".join(cells)

def cmd_report(period: str = "weekly", output: str = None, open_browser: bool = False):
    """Generate HTML usage report."""
    history = load_history()
    config = load_config()

    # Determine date range
    if period == "weekly":
        hours = 168
    elif period == "monthly":
        hours = 720
    else:
        hours = 168

    stats = get_period_stats(history, hours, "five_hour")
    weekly_stats = get_period_stats(history, hours, "seven_day")

    # Generate report data
    report_data = {
        "period": period.title(),
        "start_date": (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "avg_session": f"{stats.get('avg', 0):.1f}",
        "peak_session": f"{stats.get('max', 0):.0f}",
        "avg_weekly": f"{weekly_stats.get('avg', 0):.1f}",
        "api_cost": calculate_estimated_api_cost(history, hours),
        "svg_chart": generate_svg_chart(prepare_chart_data(history, hours)),
        "heatmap_cells": generate_heatmap(history),
        "cost_comparison_table": generate_cost_table(history, hours, config),
        "recommendations": generate_recommendations(stats, weekly_stats, config),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    html = Template(HTML_TEMPLATE).substitute(report_data)

    # Output
    if output:
        output_path = Path(output)
    else:
        output_path = Path.home() / ".claude" / f"report-{period}-{datetime.now().strftime('%Y%m%d')}.html"

    output_path.write_text(html)
    print(f"Report generated: {output_path}")

    if open_browser:
        webbrowser.open(f"file://{output_path}")
```

---

## 8. CSV Export (`--export`)

### Purpose
Export usage history to CSV for external analysis tools.

### Usage
```bash
claude-usage --export csv                  # Export to stdout
claude-usage --export csv -o usage.csv     # Export to file
claude-usage --export csv --days 30        # Last 30 days only
claude-usage --export csv --format excel   # Excel-compatible (with BOM)
```

### CSV Format

```csv
timestamp,session_usage,weekly_usage,sonnet_usage,opus_usage
2024-12-18T14:30:00+00:00,45.2,12.1,8.5,
2024-12-18T13:30:00+00:00,42.1,11.8,8.2,
2024-12-18T12:30:00+00:00,38.5,11.5,7.9,
```

### Implementation

```python
import csv
import io

def cmd_export(format: str = "csv", output: str = None, days: int = None, excel: bool = False):
    """Export usage history to CSV."""
    history = load_history()

    # Filter by days if specified
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        history = [h for h in history if h.get("timestamp", "") > cutoff_str]

    # Sort by timestamp descending
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Prepare output
    if output:
        file_handle = open(output, "w", newline="", encoding="utf-8-sig" if excel else "utf-8")
    else:
        file_handle = io.StringIO()

    writer = csv.writer(file_handle)

    # Header
    writer.writerow([
        "timestamp",
        "session_usage",
        "weekly_usage",
        "sonnet_usage",
        "opus_usage"
    ])

    # Data rows
    for h in history:
        writer.writerow([
            h.get("timestamp", ""),
            h.get("five_hour", ""),
            h.get("seven_day", ""),
            h.get("seven_day_sonnet", ""),
            h.get("seven_day_opus", ""),
        ])

    if output:
        file_handle.close()
        print(f"Exported {len(history)} records to {output}")
    else:
        print(file_handle.getvalue())

def cmd_export_json(output: str = None, days: int = None):
    """Export usage history to JSON."""
    history = load_history()

    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        history = [h for h in history if h.get("timestamp", "") > cutoff_str]

    if output:
        with open(output, "w") as f:
            json.dump(history, f, indent=2)
        print(f"Exported {len(history)} records to {output}")
    else:
        print(json.dumps(history, indent=2))
```

### Extended Export Options

```bash
# Export with aggregation
claude-usage --export csv --aggregate hourly    # Hourly averages
claude-usage --export csv --aggregate daily     # Daily summaries

# Include computed fields
claude-usage --export csv --include-rate        # Add rate-of-change column
claude-usage --export csv --include-forecast    # Add forecast column
```

---

## Implementation Priority

| # | Feature | Complexity | Dependencies |
|---|---------|------------|--------------|
| 1 | `--prompt` | Low | Cache system |
| 2 | `--tmux` | Low | Cache system |
| 3 | `--watch` | Low | None |
| 4 | `--export csv` | Low | None |
| 5 | `--forecast` | Medium | History analysis |
| 6 | `--notify` | Medium | Platform detection |
| 7 | `--generate-hook` | Medium | Hook template |
| 8 | `--report html` | High | SVG generation |

## Shared Components

### Cache System
Required by: `--prompt`, `--tmux`

```python
CACHE_FILE = Path.home() / ".claude" / ".usage_cache.json"
CACHE_MAX_AGE = 60  # seconds

def fetch_usage_cached(max_age: int = CACHE_MAX_AGE) -> dict:
    """Fetch usage with caching to reduce API calls."""
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
            cached_at = datetime.fromisoformat(cache["cached_at"])
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()

            if age < max_age:
                return cache["data"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # Fetch fresh data
    data = fetch_usage()

    # Update cache
    cache = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "data": data
    }
    CACHE_FILE.write_text(json.dumps(cache))

    return data
```

### Argument Parser Updates

```python
# Add new arguments to existing parser
parser.add_argument("--prompt", nargs="?", const="default", metavar="FORMAT",
                   help="Compact output for shell prompts (default|minimal|full|icon)")
parser.add_argument("--tmux", action="store_true",
                   help="Output optimized for tmux status bar")
parser.add_argument("--watch", "-w", nargs="?", const=30, type=int, metavar="SEC",
                   help="Live updating display (default: 30s)")
parser.add_argument("--notify", action="store_true",
                   help="Send desktop notification if threshold reached")
parser.add_argument("--notify-at", type=str, default="80,90,95",
                   help="Notification thresholds (default: 80,90,95)")
parser.add_argument("--forecast", "-f", action="store_true",
                   help="Show usage predictions")
parser.add_argument("--generate-hook", action="store_true",
                   help="Generate Claude Code hook script")
parser.add_argument("--install-hook", action="store_true",
                   help="Install hook to ~/.claude/hooks/")
parser.add_argument("--report", choices=["weekly", "monthly"],
                   help="Generate HTML usage report")
parser.add_argument("--export", choices=["csv", "json"],
                   help="Export usage history")
parser.add_argument("--days", type=int,
                   help="Limit export to last N days")
parser.add_argument("-o", "--output", type=str,
                   help="Output file path")
parser.add_argument("--open", action="store_true",
                   help="Open report in browser")
```

---

*Specification v1.0 - Ready for implementation*
