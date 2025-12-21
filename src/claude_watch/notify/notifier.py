"""Desktop notifications with cross-platform support."""

import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from claude_watch.display.colors import Colors

NOTIFY_STATE_FILE = Path.home() / ".claude" / ".notify_state.json"


def load_notify_state() -> dict:
    """Load notification state from file."""
    if not NOTIFY_STATE_FILE.exists():
        return {"last_thresholds": [], "last_notified_at": None}
    try:
        with open(NOTIFY_STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"last_thresholds": [], "last_notified_at": None}


def save_notify_state(state: dict) -> None:
    """Save notification state to file."""
    NOTIFY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIFY_STATE_FILE, "w") as f:
        json.dump(state, f)


def send_notification_linux(title: str, message: str, urgency: str = "normal") -> bool:
    """Send notification on Linux using notify-send."""
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "claude-watch", title, message],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def send_notification_macos(title: str, message: str, urgency: str = "normal") -> bool:
    """Send notification on macOS using osascript."""
    title_escaped = title.replace('"', '\\"')
    message_escaped = message.replace('"', '\\"')

    script = f'display notification "{message_escaped}" with title "{title_escaped}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def send_notification_windows(title: str, message: str, urgency: str = "normal") -> bool:
    """Send notification on Windows using PowerShell toast."""
    script = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

    $template = @"
    <toast>
        <visual>
            <binding template="ToastText02">
                <text id="1">{title}</text>
                <text id="2">{message}</text>
            </binding>
        </visual>
    </toast>
"@

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("claude-watch").Show($toast)
    '''
    try:
        subprocess.run(
            ["powershell", "-Command", script],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def send_notification(title: str, message: str, urgency: str = "normal") -> bool:
    """Send a desktop notification using the appropriate method for the platform.

    Args:
        title: Notification title.
        message: Notification body.
        urgency: Notification urgency (low, normal, critical).

    Returns:
        True if notification was sent successfully.
    """
    system = platform.system()
    if system == "Linux":
        return send_notification_linux(title, message, urgency)
    elif system == "Darwin":
        return send_notification_macos(title, message, urgency)
    elif system == "Windows":
        return send_notification_windows(title, message, urgency)
    else:
        return False


def check_and_notify(data: dict, thresholds: List[int], verbose: bool = False) -> int:
    """Check usage against thresholds and send notifications if needed.

    Args:
        data: Current usage data.
        thresholds: List of threshold percentages to check.
        verbose: Whether to print verbose output.

    Returns:
        Exit code (0 = ok, 1 = warning sent, 2 = critical sent).
    """
    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)

    current_usage = max(five_hour, seven_day)

    state = load_notify_state()
    last_thresholds = set(state.get("last_thresholds", []))

    thresholds_sorted = sorted(thresholds, reverse=True)

    exceeded = [t for t in thresholds_sorted if current_usage >= t]

    min_threshold = min(thresholds) if thresholds else 80
    reset_threshold = min(50, min_threshold)
    if current_usage < reset_threshold:
        if last_thresholds:
            if verbose:
                print(
                    f"{Colors.GREEN}Usage dropped below {reset_threshold}%, "
                    f"resetting notification state{Colors.RESET}"
                )
            state["last_thresholds"] = []
            save_notify_state(state)
        if not exceeded:
            if verbose:
                print(
                    f"{Colors.GREEN}Usage at {current_usage:.0f}% "
                    f"(below all thresholds){Colors.RESET}"
                )
            return 0

    new_exceeded = [t for t in exceeded if t not in last_thresholds]

    if not new_exceeded:
        if verbose:
            if exceeded:
                print(
                    f"{Colors.DIM}Usage at {current_usage:.0f}% "
                    f"(already notified for {exceeded[0]}%){Colors.RESET}"
                )
            else:
                print(
                    f"{Colors.GREEN}Usage at {current_usage:.0f}% "
                    f"(below all thresholds){Colors.RESET}"
                )
        return 0

    highest_new = max(new_exceeded)

    if highest_new >= 95:
        urgency = "critical"
        severity_text = "CRITICAL"
    elif highest_new >= 90:
        urgency = "critical"
        severity_text = "HIGH"
    else:
        urgency = "normal"
        severity_text = "WARNING"

    title = f"Claude Usage {severity_text}: {current_usage:.0f}%"
    message = f"Session: {five_hour:.0f}% | Weekly: {seven_day:.0f}%"

    if verbose:
        print(f"{Colors.YELLOW}Sending notification: {title}{Colors.RESET}")

    success = send_notification(title, message, urgency)

    if success:
        state["last_thresholds"] = exceeded
        state["last_notified_at"] = datetime.now(timezone.utc).isoformat()
        save_notify_state(state)

        if verbose:
            print(f"{Colors.GREEN}Notification sent successfully{Colors.RESET}")

        return 2 if urgency == "critical" else 1
    else:
        if verbose:
            print(
                f"{Colors.RED}Failed to send notification "
                f"(notify-send not available?){Colors.RESET}"
            )
        return 0


def run_notify_daemon(
    thresholds: List[int],
    interval: int = 300,
    fetch_func=None,
) -> None:
    """Run notification daemon in the background.

    Args:
        thresholds: List of threshold percentages to check.
        interval: Check interval in seconds (default: 300 = 5 minutes).
        fetch_func: Function to fetch usage data.
    """
    print(f"{Colors.CYAN}Starting notification daemon...{Colors.RESET}")
    print(f"  Thresholds: {', '.join(str(t) + '%' for t in sorted(thresholds))}")
    print(f"  Interval: {interval}s")
    print(f"  Press Ctrl+C to stop")
    print()

    try:
        while True:
            try:
                if fetch_func:
                    data = fetch_func()
                    if data:
                        check_and_notify(data, thresholds, verbose=True)
            except Exception as e:
                print(
                    f"{Colors.RED}Error checking usage: {e}{Colors.RESET}",
                    file=__import__("sys").stderr,
                )

            time.sleep(interval)
    except KeyboardInterrupt:
        print()
        print(f"{Colors.CYAN}Notification daemon stopped{Colors.RESET}")
