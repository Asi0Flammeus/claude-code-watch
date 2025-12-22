"""Systemd timer configuration for automatic data collection.

Provides functions for setting up, disabling, and checking the status
of systemd user timers for periodic usage data collection.
"""

import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

from claude_watch.display.colors import Colors

# Systemd paths
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "claude-watch-record"


def get_script_path() -> str:
    """Get the path to the claude-watch script.

    Returns:
        Full path to the executable script.
    """
    # Check if running from symlink
    script = Path(sys.argv[0]).resolve()
    if script.exists():
        return str(script)
    # Fallback to which
    result = subprocess.run(["which", "claude-watch"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return str(Path(__file__).resolve())


def setup_systemd_timer(
    interval_hours: int = 1,
    service_name: Optional[str] = None,
    script_path: Optional[str] = None,
) -> bool:
    """Set up systemd user timer for automatic collection.

    Args:
        interval_hours: Collection interval in hours (default: 1).
        service_name: Override service name (default: claude-watch-record).
        script_path: Override script path (default: auto-detect).

    Returns:
        True if setup succeeded, False otherwise.
    """
    if platform.system() != "Linux":
        print(
            f"{Colors.YELLOW}Automatic collection via systemd is only available on Linux.{Colors.RESET}"
        )
        print(
            f"{Colors.DIM}For macOS, you can use launchd. For Windows, use Task Scheduler.{Colors.RESET}"
        )
        return False

    if service_name is None:
        service_name = SERVICE_NAME
    if script_path is None:
        script_path = get_script_path()

    service_content = f"""[Unit]
Description=Record Claude Code usage to history
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={script_path} --no-color
StandardOutput=null
StandardError=journal

# Security hardening
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
NoNewPrivileges=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictSUIDSGID=true

[Install]
WantedBy=default.target
"""

    timer_content = f"""[Unit]
Description=Record Claude Code usage every {interval_hours} hour(s)

[Timer]
OnBootSec=5min
OnUnitActiveSec={interval_hours}h
Persistent=true

[Install]
WantedBy=timers.target
"""

    try:
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)

        service_file = SYSTEMD_USER_DIR / f"{service_name}.service"
        timer_file = SYSTEMD_USER_DIR / f"{service_name}.timer"

        with open(service_file, "w") as f:
            f.write(service_content)

        with open(timer_file, "w") as f:
            f.write(timer_content)

        # Reload and enable
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", f"{service_name}.timer"], check=True)
        subprocess.run(["systemctl", "--user", "start", f"{service_name}.timer"], check=True)

        return True
    except Exception as e:
        print(f"{Colors.RED}Failed to set up systemd timer: {e}{Colors.RESET}")
        return False


def disable_systemd_timer(service_name: Optional[str] = None) -> bool:
    """Disable and remove systemd timer.

    Args:
        service_name: Override service name (default: claude-watch-record).

    Returns:
        True if disabled successfully, False otherwise.
    """
    if platform.system() != "Linux":
        return False

    if service_name is None:
        service_name = SERVICE_NAME

    try:
        subprocess.run(
            ["systemctl", "--user", "stop", f"{service_name}.timer"], capture_output=True
        )
        subprocess.run(
            ["systemctl", "--user", "disable", f"{service_name}.timer"], capture_output=True
        )

        service_file = SYSTEMD_USER_DIR / f"{service_name}.service"
        timer_file = SYSTEMD_USER_DIR / f"{service_name}.timer"

        if service_file.exists():
            service_file.unlink()
        if timer_file.exists():
            timer_file.unlink()

        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        return True
    except Exception:
        return False


def check_timer_status(service_name: Optional[str] = None) -> Optional[dict]:
    """Check if systemd timer is active.

    Args:
        service_name: Override service name (default: claude-watch-record).

    Returns:
        Dictionary with 'active' bool and optional 'details' string,
        or None if systemd is not available.
    """
    if platform.system() != "Linux":
        return None

    if service_name is None:
        service_name = SERVICE_NAME

    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", f"{service_name}.timer"],
            capture_output=True,
            text=True,
        )
        is_active = result.stdout.strip() == "active"

        if is_active:
            result = subprocess.run(
                ["systemctl", "--user", "list-timers", f"{service_name}.timer", "--no-pager"],
                capture_output=True,
                text=True,
            )
            return {"active": True, "details": result.stdout}
        return {"active": False}
    except Exception:
        return None


__all__ = [
    "SYSTEMD_USER_DIR",
    "SERVICE_NAME",
    "get_script_path",
    "setup_systemd_timer",
    "disable_systemd_timer",
    "check_timer_status",
]
