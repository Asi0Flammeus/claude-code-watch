#!/usr/bin/env python3
"""
Claude Code Watch - Monitor your Claude Code subscription usage limits.

Fetches usage data from the Anthropic OAuth API and displays it in a clean
terminal interface similar to claude.ai/settings/usage.

Cross-platform support: Linux, macOS, Windows

Commands:
  claude-watch     Primary command
  ccw              Short alias (configure via shell alias)
"""

import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from collections import defaultdict
import statistics
import shutil

# ═══════════════════════════════════════════════════════════════════════════════
# Version
# ═══════════════════════════════════════════════════════════════════════════════

__version__ = "0.5.1"

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

API_URL = "https://api.anthropic.com/api/oauth/usage"
ADMIN_API_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
API_BETA_HEADER = "oauth-2025-04-20"
CONFIG_FILE = Path.home() / ".claude" / ".usage_config.json"
HISTORY_FILE = Path.home() / ".claude" / ".usage_history.json"
CACHE_FILE = Path.home() / ".claude" / ".usage_cache.json"
MAX_HISTORY_DAYS = 180  # 6 months (override with CLAUDE_WATCH_HISTORY_DAYS)
CACHE_MAX_AGE = 60  # seconds (override with CLAUDE_WATCH_CACHE_TTL)

# Apply environment variable overrides
if os.environ.get("CLAUDE_WATCH_CACHE_TTL"):
    try:
        CACHE_MAX_AGE = int(os.environ["CLAUDE_WATCH_CACHE_TTL"])
    except ValueError:
        pass  # Keep default if invalid

if os.environ.get("CLAUDE_WATCH_HISTORY_DAYS"):
    try:
        MAX_HISTORY_DAYS = int(os.environ["CLAUDE_WATCH_HISTORY_DAYS"])
    except ValueError:
        pass  # Keep default if invalid

# Systemd paths
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "claude-watch-record"


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    MAGENTA = "\033[95m"
    BAR_FILL = "\033[94m"
    BAR_EMPTY = "\033[90m"
    UP = "\033[91m"
    DOWN = "\033[92m"
    FLAT = "\033[90m"


def supports_color():
    # Check for CLAUDE_WATCH_NO_COLOR env var (any non-empty value disables color)
    if os.environ.get("CLAUDE_WATCH_NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if platform.system() == "Windows":
        return os.environ.get("TERM") or os.environ.get("WT_SESSION")
    return True


if not supports_color():
    for attr in dir(Colors):
        if not attr.startswith("_"):
            setattr(Colors, attr, "")

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Spinner
# ═══════════════════════════════════════════════════════════════════════════════

import threading
import time
import itertools


class Spinner:
    """Simple CLI spinner for loading states."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Loading"):
        self.message = message
        self.running = False
        self.thread = None
        self.frame_cycle = itertools.cycle(self.FRAMES)

    def _spin(self):
        while self.running:
            frame = next(self.frame_cycle)
            sys.stdout.write(f"\r{Colors.CYAN}{frame}{Colors.RESET} {self.message}...")
            sys.stdout.flush()
            time.sleep(0.08)

    def start(self):
        if not sys.stdout.isatty():
            return self
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self

    def stop(self, clear: bool = True):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        if sys.stdout.isatty():
            if clear:
                sys.stdout.write(f"\r{' ' * (len(self.message) + 10)}\r")
            sys.stdout.flush()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Config Management
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "admin_api_key": None,
    "use_admin_api": False,
    "auto_collect": False,
    "collect_interval_hours": 1,
    "setup_completed": False,
    "subscription_plan": "pro",  # pro, max_5x, max_20x
    "shell_completion_installed": False,
}

# Subscription plans with monthly costs and rate limits
SUBSCRIPTION_PLANS = {
    "pro": {
        "name": "Pro",
        "cost": 20.00,
        "messages_5h": 45,  # ~45 messages per 5 hours
        "weekly_sonnet_hours": 60,  # ~40-80 hours Sonnet 4
        "weekly_opus_hours": 0,  # No dedicated Opus allocation
    },
    "max_5x": {
        "name": "Max 5x",
        "cost": 100.00,
        "messages_5h": 225,  # ~225 messages per 5 hours (5x Pro)
        "weekly_sonnet_hours": 210,  # ~140-280 hours Sonnet 4
        "weekly_opus_hours": 25,  # ~15-35 hours Opus 4
    },
    "max_20x": {
        "name": "Max 20x",
        "cost": 200.00,
        "messages_5h": 900,  # ~900 messages per 5 hours (20x Pro)
        "weekly_sonnet_hours": 360,  # ~240-480 hours Sonnet 4
        "weekly_opus_hours": 32,  # ~24-40 hours Opus 4
    },
}

# API Pricing per 1M tokens
API_PRICING = {
    "claude-sonnet-4-5-20250929": (3.00, 15.00, 0.30),
    "claude-sonnet-4-20250514": (3.00, 15.00, 0.30),
    "claude-opus-4-5-20251101": (15.00, 75.00, 1.50),
    "claude-opus-4-20250514": (15.00, 75.00, 1.50),
    "claude-haiku-4-5-20251101": (1.00, 5.00, 0.10),
    "claude-3-5-sonnet-20241022": (3.00, 15.00, 0.30),
    "claude-3-5-haiku-20241022": (1.00, 5.00, 0.10),
    "claude-3-haiku-20240307": (0.25, 1.25, 0.03),
    "default": (3.00, 15.00, 0.30),
}


# Config schema for validation
# Format: key -> (type, required, validator_func or None)
# validator_func takes value and returns (is_valid, error_message)
CONFIG_SCHEMA = {
    "admin_api_key": (
        (str, type(None)),
        False,
        lambda v: (True, "") if v is None or (isinstance(v, str) and len(v) > 0) else (False, "must be a non-empty string or null"),
    ),
    "use_admin_api": ((bool,), False, None),
    "auto_collect": ((bool,), False, None),
    "collect_interval_hours": (
        (int, float),
        False,
        lambda v: (True, "") if 0 < v <= 24 else (False, "must be between 0 and 24"),
    ),
    "setup_completed": ((bool,), False, None),
    "subscription_plan": (
        (str,),
        False,
        lambda v: (True, "") if v in SUBSCRIPTION_PLANS else (False, f"must be one of: {', '.join(SUBSCRIPTION_PLANS.keys())}"),
    ),
    "shell_completion_installed": ((bool,), False, None),
    "_config_version": ((int,), False, None),  # Internal version tracking for migrations
}


def validate_config(config: dict) -> List[str]:
    """Validate configuration against schema.

    Args:
        config: Configuration dictionary to validate.

    Returns:
        List of validation error messages. Empty list if valid.
    """
    errors = []

    # Check for unknown keys
    for key in config:
        if key not in CONFIG_SCHEMA:
            errors.append(f"Unknown config key: '{key}'")

    # Validate each known key
    for key, (expected_types, required, validator) in CONFIG_SCHEMA.items():
        # Check required keys
        if required and key not in config:
            errors.append(f"Missing required key: '{key}'")
            continue

        # Skip if key not present and not required
        if key not in config:
            continue

        value = config[key]

        # Type checking (allow None for optional fields)
        if not isinstance(value, expected_types):
            type_names = " or ".join(t.__name__ for t in expected_types)
            errors.append(f"'{key}' has invalid type: expected {type_names}, got {type(value).__name__}")
            continue

        # Custom validation
        if validator and value is not None:
            is_valid, error_msg = validator(value)
            if not is_valid:
                errors.append(f"'{key}' {error_msg}")

    return errors


# Config version for migration tracking
# Increment this when adding new config fields or changing schema
CONFIG_VERSION = 2

# Migration history:
# v1: Original config (admin_api_key, use_admin_api, auto_collect, collect_interval_hours, setup_completed, subscription_plan)
# v2: Added shell_completion_installed


def migrate_config(config: dict) -> Tuple[dict, bool]:
    """Migrate old config formats to the current schema.

    Args:
        config: Configuration dictionary to migrate.

    Returns:
        Tuple of (migrated_config, was_migrated).
    """
    was_migrated = False
    migrated = config.copy()

    # Detect version by checking for known fields
    # If _config_version is missing, infer from field presence
    current_version = migrated.get("_config_version", 1)

    # Migration from v1 to v2: Add shell_completion_installed
    if current_version < 2:
        if "shell_completion_installed" not in migrated:
            migrated["shell_completion_installed"] = DEFAULT_CONFIG["shell_completion_installed"]
            was_migrated = True
        current_version = 2

    # Remove any deprecated keys (none currently, but ready for future)
    deprecated_keys = []  # Add deprecated key names here in future
    for key in deprecated_keys:
        if key in migrated:
            del migrated[key]
            was_migrated = True

    # Update version marker
    if was_migrated:
        migrated["_config_version"] = CONFIG_VERSION

    return migrated, was_migrated


def load_config(validate: bool = True, auto_migrate: bool = True) -> dict:
    """Load configuration from file.

    Args:
        validate: Whether to validate config and warn on errors. Default True.
        auto_migrate: Whether to automatically migrate old config formats. Default True.

    Returns:
        Configuration dictionary merged with defaults.
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)

            # Migrate old config formats if needed
            if auto_migrate:
                config, was_migrated = migrate_config(config)
                if was_migrated:
                    # Save the migrated config
                    save_config(config)
                    print(f"{Colors.CYAN}Config migrated to version {CONFIG_VERSION}{Colors.RESET}", file=sys.stderr)

            # Validate if requested
            if validate:
                errors = validate_config(config)
                if errors:
                    print(f"{Colors.YELLOW}Warning: Config validation errors:{Colors.RESET}", file=sys.stderr)
                    for error in errors:
                        print(f"  - {error}", file=sys.stderr)

            # Merge with defaults for any missing keys
            return {**DEFAULT_CONFIG, **config}
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save configuration to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    # Secure the file (contains API key)
    os.chmod(CONFIG_FILE, 0o600)


# ═══════════════════════════════════════════════════════════════════════════════
# Update System
# ═══════════════════════════════════════════════════════════════════════════════

# GitHub releases API (no PyPI dependency)
GITHUB_REPO = "Asi0Flammeus/claude-code-watch"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(version_str: str) -> Tuple[int, int, int, str]:
    """Parse semantic version string into comparable tuple.

    Returns (major, minor, patch, prerelease) where prerelease is empty string
    for stable releases or the prerelease suffix (e.g., 'alpha.1', 'beta.2').
    """
    # Match semantic version with optional prerelease
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version_str.strip())
    if not match:
        return (0, 0, 0, version_str)  # Fallback for unparseable versions

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    prerelease = match.group(4) or ""
    return (major, minor, patch, prerelease)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.

    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    p1 = parse_version(v1)
    p2 = parse_version(v2)

    # Compare major, minor, patch
    for i in range(3):
        if p1[i] < p2[i]:
            return -1
        if p1[i] > p2[i]:
            return 1

    # If same major.minor.patch, compare prerelease
    # No prerelease (stable) > any prerelease
    if not p1[3] and p2[3]:
        return 1  # v1 is stable, v2 is prerelease
    if p1[3] and not p2[3]:
        return -1  # v1 is prerelease, v2 is stable
    if p1[3] < p2[3]:
        return -1
    if p1[3] > p2[3]:
        return 1

    return 0


def detect_installation_method() -> Optional[str]:
    """Detect how claude-watch was installed.

    Returns:
        'uv' - installed via uv tool
        'pipx' - installed via pipx
        'pip' - installed via pip
        None - unknown/development installation
    """
    # Check for uv tool installation
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "claude-watch" in result.stdout:
            return "uv"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # Check for pipx installation
    try:
        result = subprocess.run(
            ["pipx", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "claude-watch" in result.stdout:
            return "pipx"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # Check if installed via pip (in site-packages)
    try:
        import importlib.util
        spec = importlib.util.find_spec("claude_watch")
        if spec and spec.origin:
            origin = str(spec.origin)
            if "site-packages" in origin:
                return "pip"
    except (ImportError, AttributeError):
        pass

    return None


def fetch_latest_version() -> Optional[str]:
    """Fetch the latest version from GitHub releases.

    Returns:
        Latest version string (without 'v' prefix), or None if fetch failed.
    """
    req = Request(
        GITHUB_RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"claude-watch/{__version__}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            tag_name = data.get("tag_name", "")
            # Remove 'v' prefix if present (e.g., 'v0.1.0' -> '0.1.0')
            if tag_name.startswith("v"):
                tag_name = tag_name[1:]
            return tag_name if tag_name else None
    except (HTTPError, URLError, json.JSONDecodeError, KeyError):
        return None


def run_upgrade(method: str) -> Tuple[bool, str]:
    """Run the upgrade command for the detected installation method.

    Args:
        method: Installation method ('uv', 'pipx', or 'pip')

    Returns:
        (success, message) tuple
    """
    github_url = f"git+https://github.com/{GITHUB_REPO}.git"
    commands = {
        # uv/pipx remember install source, so upgrade pulls from original git URL
        "uv": ["uv", "tool", "upgrade", "claude-watch"],
        "pipx": ["pipx", "upgrade", "claude-watch"],
        # pip needs explicit URL since it doesn't track source
        "pip": [sys.executable, "-m", "pip", "install", "--upgrade", github_url],
    }

    cmd = commands.get(method)
    if not cmd:
        return False, f"Unknown installation method: {method}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, f"Successfully upgraded via {method}"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return False, f"Upgrade failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "Upgrade timed out after 120 seconds"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except subprocess.SubprocessError as e:
        return False, f"Upgrade failed: {e}"


def check_for_update(quiet: bool = False) -> Optional[dict]:
    """Check if an update is available.

    Args:
        quiet: If True, suppress output messages

    Returns:
        Dict with 'current', 'latest', 'update_available', 'method' keys,
        or None if check failed.
    """
    if not quiet:
        print("Checking for updates...")

    latest = fetch_latest_version()
    if latest is None:
        if not quiet:
            print(f"{Colors.YELLOW}Could not check for updates (GitHub unreachable or no releases){Colors.RESET}")
        return None

    current = __version__
    update_available = compare_versions(current, latest) < 0
    method = detect_installation_method()

    return {
        "current": current,
        "latest": latest,
        "update_available": update_available,
        "method": method,
    }


def run_update(check_only: bool = False) -> int:
    """Run the update process.

    Args:
        check_only: If True, only check for updates without installing

    Returns:
        Exit code (0 for success, 1 for error, 2 for no update available)
    """
    result = check_for_update(quiet=False)
    if result is None:
        return 1

    current = result["current"]
    latest = result["latest"]
    update_available = result["update_available"]
    method = result["method"]

    print()
    print(f"  Current version: {Colors.CYAN}{current}{Colors.RESET}")
    print(f"  Latest version:  {Colors.CYAN}{latest}{Colors.RESET}")
    print()

    if not update_available:
        print(f"{Colors.GREEN}✓ You are running the latest version{Colors.RESET}")
        return 2

    print(f"{Colors.YELLOW}Update available: {current} → {latest}{Colors.RESET}")
    print()

    if check_only:
        if method:
            print(f"Run {Colors.CYAN}claude-watch --update{Colors.RESET} to update via {method}")
        else:
            print("Installation method not detected. Manual update may be required.")
        return 0

    # Proceed with upgrade
    if method is None:
        print(f"{Colors.YELLOW}Could not detect installation method.{Colors.RESET}")
        print()
        print("Please update manually using one of:")
        print(f"  {Colors.CYAN}uv tool upgrade claude-watch{Colors.RESET}")
        print(f"  {Colors.CYAN}pipx upgrade claude-watch{Colors.RESET}")
        print(f"  {Colors.CYAN}pip install --upgrade claude-watch{Colors.RESET}")
        return 1

    print(f"Updating via {Colors.CYAN}{method}{Colors.RESET}...")
    print()

    success, message = run_upgrade(method)

    if success:
        print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")
        print()
        print(f"Restart your shell or run {Colors.CYAN}claude-watch --version{Colors.RESET} to verify.")
        return 0
    else:
        print(f"{Colors.RED}✗ {message}{Colors.RESET}")
        return 1


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Wizard
# ═══════════════════════════════════════════════════════════════════════════════


def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt user for yes/no answer."""
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        response = input(f"{question}{suffix}").strip().lower()
        if not response:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'")


def prompt_input(question: str, default: str = "") -> str:
    """Prompt user for text input."""
    suffix = f" [{default}] " if default else " "
    response = input(f"{question}{suffix}").strip()
    return response if response else default


def get_script_path() -> str:
    """Get the path to this script."""
    # Check if running from symlink
    script = Path(sys.argv[0]).resolve()
    if script.exists():
        return str(script)
    # Fallback to which
    result = subprocess.run(["which", "claude-watch"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return str(Path(__file__).resolve())


def detect_shell() -> str:
    """Detect the user's default shell."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "fish" in shell:
        return "fish"
    elif "bash" in shell:
        return "bash"
    # Fallback: check if running in a known shell
    if os.environ.get("ZSH_VERSION"):
        return "zsh"
    if os.environ.get("FISH_VERSION"):
        return "fish"
    if os.environ.get("BASH_VERSION"):
        return "bash"
    return "bash"  # Default to bash


def get_completion_source_path() -> Optional[Path]:
    """Find the completions directory from the package installation."""
    # Try to find completions relative to this module
    module_dir = Path(__file__).parent
    completions_dir = module_dir / "completions"
    if completions_dir.exists():
        return completions_dir

    # Try sibling directory (for development)
    completions_dir = module_dir.parent / "completions"
    if completions_dir.exists():
        return completions_dir

    # Try site-packages location
    for path in sys.path:
        completions_dir = Path(path) / "claude_watch" / "completions"
        if completions_dir.exists():
            return completions_dir

    return None


def setup_shell_completion() -> bool:
    """Set up shell completion for the user's shell."""
    shell = detect_shell()
    completions_source = get_completion_source_path()

    if not completions_source:
        print(f"{Colors.YELLOW}Could not find completion scripts.{Colors.RESET}")
        print(f"{Colors.DIM}You can manually install from the project's completions/ directory.{Colors.RESET}")
        return False

    shell_configs = {
        "bash": {
            "completion_file": "claude-watch.bash",
            "rc_files": [Path.home() / ".bashrc", Path.home() / ".bash_profile"],
            "completion_dir": Path.home() / ".local" / "share" / "bash-completion" / "completions",
            "source_line": lambda path: f'\n# Claude Watch completion\n[ -f "{path}" ] && source "{path}"\n',
        },
        "zsh": {
            "completion_file": "claude-watch.zsh",
            "rc_files": [Path.home() / ".zshrc"],
            "completion_dir": Path.home() / ".zsh" / "completions",
            "source_line": lambda path: f'\n# Claude Watch completion\n[ -f "{path}" ] && source "{path}"\n',
        },
        "fish": {
            "completion_file": "claude-watch.fish",
            "rc_files": [],  # Fish auto-loads from completions dir
            "completion_dir": Path.home() / ".config" / "fish" / "completions",
            "source_line": None,  # Fish doesn't need sourcing
        },
    }

    config = shell_configs.get(shell)
    if not config:
        print(f"{Colors.YELLOW}Unknown shell: {shell}{Colors.RESET}")
        return False

    source_file = completions_source / config["completion_file"]
    if not source_file.exists():
        print(f"{Colors.YELLOW}Completion file not found: {source_file}{Colors.RESET}")
        return False

    # Strategy: copy to completion directory
    dest_dir = config["completion_dir"]
    dest_file = dest_dir / config["completion_file"]

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest_file)
        print(f"{Colors.GREEN}✓ Copied completion to {dest_file}{Colors.RESET}")

        # For bash/zsh, add source line to rc file if not using XDG completion
        if shell in ("bash", "zsh") and config["source_line"]:
            # Check if bash-completion is available (auto-loads from dir)
            bash_completion_dir = Path("/usr/share/bash-completion/completions")
            if shell == "bash" and bash_completion_dir.exists():
                # User might have bash-completion installed, which auto-loads
                alt_dest = bash_completion_dir / "claude-watch"
                if os.access(str(bash_completion_dir), os.W_OK):
                    shutil.copy2(source_file, alt_dest)
                    print(f"{Colors.DIM}Also copied to system completions: {alt_dest}{Colors.RESET}")
                    return True

            # Add source line to rc file
            for rc_file in config["rc_files"]:
                if rc_file.exists():
                    content = rc_file.read_text()
                    if "claude-watch" not in content.lower() and "Claude Watch" not in content:
                        source_line = config["source_line"](dest_file)
                        with open(rc_file, "a") as f:
                            f.write(source_line)
                        print(f"{Colors.GREEN}✓ Added source line to {rc_file}{Colors.RESET}")
                    else:
                        print(f"{Colors.DIM}Completion already configured in {rc_file}{Colors.RESET}")
                    break

        print(f"{Colors.DIM}Restart your shell or run: source {dest_file}{Colors.RESET}")
        return True

    except PermissionError:
        print(f"{Colors.YELLOW}Permission denied writing to {dest_dir}{Colors.RESET}")
        print(f"{Colors.DIM}You can manually copy {source_file} to your completions directory.{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Error setting up completion: {e}{Colors.RESET}")
        return False


def setup_systemd_timer(interval_hours: int = 1) -> bool:
    """Set up systemd user timer for automatic collection."""
    if platform.system() != "Linux":
        print(
            f"{Colors.YELLOW}Automatic collection via systemd is only available on Linux.{Colors.RESET}"
        )
        print(
            f"{Colors.DIM}For macOS, you can use launchd. For Windows, use Task Scheduler.{Colors.RESET}"
        )
        return False

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

        service_file = SYSTEMD_USER_DIR / f"{SERVICE_NAME}.service"
        timer_file = SYSTEMD_USER_DIR / f"{SERVICE_NAME}.timer"

        with open(service_file, "w") as f:
            f.write(service_content)

        with open(timer_file, "w") as f:
            f.write(timer_content)

        # Reload and enable
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", f"{SERVICE_NAME}.timer"], check=True)
        subprocess.run(["systemctl", "--user", "start", f"{SERVICE_NAME}.timer"], check=True)

        return True
    except Exception as e:
        print(f"{Colors.RED}Failed to set up systemd timer: {e}{Colors.RESET}")
        return False


def disable_systemd_timer() -> bool:
    """Disable and remove systemd timer."""
    if platform.system() != "Linux":
        return False

    try:
        subprocess.run(
            ["systemctl", "--user", "stop", f"{SERVICE_NAME}.timer"], capture_output=True
        )
        subprocess.run(
            ["systemctl", "--user", "disable", f"{SERVICE_NAME}.timer"], capture_output=True
        )

        service_file = SYSTEMD_USER_DIR / f"{SERVICE_NAME}.service"
        timer_file = SYSTEMD_USER_DIR / f"{SERVICE_NAME}.timer"

        if service_file.exists():
            service_file.unlink()
        if timer_file.exists():
            timer_file.unlink()

        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        return True
    except Exception:
        return False

def check_timer_status() -> Optional[dict]:
    """Check if systemd timer is active."""
    if platform.system() != "Linux":
        return None

    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", f"{SERVICE_NAME}.timer"],
            capture_output=True,
            text=True,
        )
        is_active = result.stdout.strip() == "active"

        if is_active:
            result = subprocess.run(
                ["systemctl", "--user", "list-timers", f"{SERVICE_NAME}.timer", "--no-pager"],
                capture_output=True,
                text=True,
            )
            return {"active": True, "details": result.stdout}
        return {"active": False}
    except Exception:
        return None


def run_setup():
    """Run interactive setup wizard."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}═══ Claude Code Watch Setup ═══{Colors.RESET}")
    print()

    config = load_config()

    # Step 1: Admin API Key
    print(f"{Colors.BOLD}Step 1: Admin API Key (Optional){Colors.RESET}")
    print()
    print("The Admin API provides historical usage data but requires:")
    print(f"  {Colors.DIM}• An organization account (not individual Pro/Max){Colors.RESET}")
    print(f"  {Colors.DIM}• Admin role in the organization{Colors.RESET}")
    print(f"  {Colors.DIM}• Admin API key (sk-ant-admin-...){Colors.RESET}")
    print()
    print(
        f"Get your Admin API key at: {Colors.CYAN}https://console.anthropic.com/settings/admin-keys{Colors.RESET}"
    )
    print()

    has_admin_key = prompt_yes_no("Do you have an Admin API key?", default=False)

    if has_admin_key:
        while True:
            admin_key = prompt_input("Enter your Admin API key (sk-ant-admin-...):")
            if admin_key.startswith("sk-ant-admin"):
                config["admin_api_key"] = admin_key
                config["use_admin_api"] = True
                print(f"{Colors.GREEN}✓ Admin API key saved{Colors.RESET}")
                break
            elif not admin_key:
                print("Skipping Admin API setup.")
                break
            else:
                print(
                    f"{Colors.RED}Invalid key format. Admin keys start with 'sk-ant-admin-'{Colors.RESET}"
                )
    else:
        print()
        print(f"{Colors.DIM}No problem! We'll use local tracking instead.{Colors.RESET}")
        print(
            f"{Colors.DIM}Your usage will be recorded each time you run the command.{Colors.RESET}"
        )
        config["use_admin_api"] = False

    print()

    # Step 2: Automatic Collection
    print(f"{Colors.BOLD}Step 2: Automatic Data Collection{Colors.RESET}")
    print()

    if not config["use_admin_api"]:
        print("Since you're using local tracking, we recommend automatic collection")
        print("to build historical data for analytics.")
        print()
    else:
        print("Even with Admin API, local collection provides faster access to recent data.")
        print()

    setup_auto = prompt_yes_no("Set up automatic hourly data collection?", default=True)

    if setup_auto:
        interval = prompt_input("Collection interval in hours", default="1")
        try:
            interval_hours = int(interval)
            if interval_hours < 1:
                interval_hours = 1
        except ValueError:
            interval_hours = 1

        print()
        print(f"Setting up collection every {interval_hours} hour(s)...")

        if setup_systemd_timer(interval_hours):
            config["auto_collect"] = True
            config["collect_interval_hours"] = interval_hours
            print(f"{Colors.GREEN}✓ Automatic collection enabled{Colors.RESET}")
            print()
            print(f"{Colors.DIM}Manage with:{Colors.RESET}")
            print(f"  systemctl --user status {SERVICE_NAME}.timer")
            print(f"  systemctl --user stop {SERVICE_NAME}.timer")
        else:
            config["auto_collect"] = False
    else:
        config["auto_collect"] = False
        # Disable existing timer if any
        disable_systemd_timer()

    print()

    # Step 3: Subscription Plan
    print(f"{Colors.BOLD}Step 3: Your Subscription Plan{Colors.RESET}")
    print()
    print("Select your Claude subscription for cost comparison:")
    print()
    print(f"  {Colors.CYAN}1{Colors.RESET}) Pro       - $20/month")
    print(f"  {Colors.CYAN}2{Colors.RESET}) Max 5x    - $100/month")
    print(f"  {Colors.CYAN}3{Colors.RESET}) Max 20x   - $200/month")
    print()

    plan_choice = prompt_input("Enter choice (1-3)", default="1")
    plan_map = {"1": "pro", "2": "max_5x", "3": "max_20x"}
    config["subscription_plan"] = plan_map.get(plan_choice, "pro")
    plan_info = SUBSCRIPTION_PLANS[config["subscription_plan"]]
    print(
        f"{Colors.GREEN}✓ Subscription set to {plan_info['name']} (${plan_info['cost']:.0f}/mo){Colors.RESET}"
    )

    print()

    # Step 4: Shell Completion
    print(f"{Colors.BOLD}Step 4: Shell Tab Completion (Optional){Colors.RESET}")
    print()
    shell = detect_shell()
    print(f"Detected shell: {Colors.CYAN}{shell}{Colors.RESET}")
    print()
    print("Tab completion allows you to press TAB to auto-complete options like:")
    print(f"  {Colors.DIM}claude-watch --<TAB>{Colors.RESET}  → shows all available flags")
    print()

    setup_completion = prompt_yes_no("Install shell tab completion?", default=True)

    if setup_completion:
        if setup_shell_completion():
            config["shell_completion_installed"] = True
        else:
            config["shell_completion_installed"] = False
    else:
        print(f"{Colors.DIM}Skipping shell completion setup.{Colors.RESET}")
        config["shell_completion_installed"] = False

    print()

    # Save config
    config["setup_completed"] = True
    save_config(config)

    print(f"{Colors.GREEN}{Colors.BOLD}✓ Setup complete!{Colors.RESET}")
    print()
    print(f"Configuration saved to: {Colors.DIM}{CONFIG_FILE}{Colors.RESET}")
    print()
    print("Run again to see your usage:")
    print(f"  {Colors.CYAN}claude-watch{Colors.RESET}           - Current usage")
    print(f"  {Colors.CYAN}claude-watch -a{Colors.RESET}        - With analytics")
    print(f"  {Colors.CYAN}claude-watch --setup{Colors.RESET}   - Re-run setup")
    print(
        f"  {Colors.CYAN}ccw{Colors.RESET}                    - Short alias (add to shell config)"
    )
    print()


def reset_config():
    """Reset configuration to defaults."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    save_config(DEFAULT_CONFIG.copy())
    print(f"{Colors.GREEN}✓ Configuration reset to defaults{Colors.RESET}")
    print()
    show_config()


def set_config(key: str, value: str):
    """Set a configuration key to a value.

    Handles type conversion based on the default config type.
    """
    if key not in DEFAULT_CONFIG:
        valid_keys = ", ".join(sorted(DEFAULT_CONFIG.keys()))
        print(f"{Colors.RED}Error: Unknown configuration key '{key}'{Colors.RESET}")
        print(f"Valid keys: {valid_keys}")
        sys.exit(1)

    config = load_config()
    default_value = DEFAULT_CONFIG[key]

    # Type conversion based on default type
    try:
        if default_value is None:
            # None defaults accept strings or can be set to null/none
            if value.lower() in ("null", "none", ""):
                converted = None
            else:
                converted = value
        elif isinstance(default_value, bool):
            # Boolean: accept various truthy/falsy values
            if value.lower() in ("true", "1", "yes", "on"):
                converted = True
            elif value.lower() in ("false", "0", "no", "off"):
                converted = False
            else:
                raise ValueError(f"Expected boolean value (true/false), got '{value}'")
        elif isinstance(default_value, int):
            converted = int(value)
        elif isinstance(default_value, float):
            converted = float(value)
        else:
            # String type
            converted = value
    except ValueError as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)

    # Special validation for specific keys
    if key == "subscription_plan" and converted not in SUBSCRIPTION_PLANS:
        valid_plans = ", ".join(SUBSCRIPTION_PLANS.keys())
        print(f"{Colors.RED}Error: Invalid subscription plan '{converted}'{Colors.RESET}")
        print(f"Valid plans: {valid_plans}")
        sys.exit(1)

    if key == "admin_api_key" and converted and not converted.startswith("sk-ant-admin"):
        print(f"{Colors.YELLOW}Warning: Admin API keys typically start with 'sk-ant-admin-'{Colors.RESET}")

    if key == "collect_interval_hours" and converted < 1:
        print(f"{Colors.RED}Error: collect_interval_hours must be at least 1{Colors.RESET}")
        sys.exit(1)

    old_value = config.get(key)
    config[key] = converted
    save_config(config)

    # Display result
    if converted is None:
        display_value = "null"
    elif isinstance(converted, bool):
        display_value = "true" if converted else "false"
    else:
        display_value = str(converted)

    print(f"{Colors.GREEN}✓ Set {key} = {display_value}{Colors.RESET}")

    if old_value != converted:
        if old_value is None:
            old_display = "null"
        elif isinstance(old_value, bool):
            old_display = "true" if old_value else "false"
        else:
            old_display = str(old_value)
        print(f"{Colors.DIM}  (was: {old_display}){Colors.RESET}")


def show_config():
    """Display current configuration."""
    config = load_config()
    timer_status = check_timer_status()

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Current Configuration{Colors.RESET}")
    print()

    # Subscription Plan
    plan_key = config.get("subscription_plan", "pro")
    plan_info = SUBSCRIPTION_PLANS.get(plan_key, SUBSCRIPTION_PLANS["pro"])
    print(
        f"  Subscription:     {Colors.CYAN}{plan_info['name']}{Colors.RESET} (${plan_info['cost']:.0f}/mo)"
    )

    print()

    # Admin API
    if config.get("admin_api_key"):
        key = config["admin_api_key"]
        masked = key[:15] + "..." + key[-4:] if len(key) > 20 else "***"
        print(f"  Admin API Key:    {Colors.GREEN}Configured{Colors.RESET} ({masked})")
        print(
            f"  Use Admin API:    {Colors.GREEN if config.get('use_admin_api') else Colors.YELLOW}{'Yes' if config.get('use_admin_api') else 'No'}{Colors.RESET}"
        )
    else:
        print(f"  Admin API Key:    {Colors.DIM}Not configured{Colors.RESET}")
        print(f"  Data Source:      {Colors.CYAN}Local tracking{Colors.RESET}")

    print()

    # Auto collection
    if timer_status:
        if timer_status.get("active"):
            print(
                f"  Auto Collection:  {Colors.GREEN}Active{Colors.RESET} (every {config.get('collect_interval_hours', 1)}h)"
            )
        else:
            print(f"  Auto Collection:  {Colors.YELLOW}Inactive{Colors.RESET}")
    else:
        print(f"  Auto Collection:  {Colors.DIM}N/A (Linux only){Colors.RESET}")

    # History stats
    history = load_history()
    print()
    print(f"  History Records:  {len(history)}")
    if history:
        oldest = min(h["timestamp"] for h in history)
        newest = max(h["timestamp"] for h in history)
        oldest_dt = datetime.fromisoformat(oldest.replace("Z", "+00:00")).astimezone()
        newest_dt = datetime.fromisoformat(newest.replace("Z", "+00:00")).astimezone()
        print(
            f"  Date Range:       {oldest_dt.strftime('%Y-%m-%d')} to {newest_dt.strftime('%Y-%m-%d')}"
        )

    print()
    print(f"  Config File:      {CONFIG_FILE}")
    print(f"  History File:     {HISTORY_FILE}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# Credential Management
# ═══════════════════════════════════════════════════════════════════════════════


def get_credentials_path() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", "~"))
    else:
        base = Path.home()
    return base / ".claude" / ".credentials.json"

def get_macos_keychain_credentials() -> Optional[dict]:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout.strip())
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None


def get_credentials() -> dict:
    if platform.system() == "Darwin":
        creds = get_macos_keychain_credentials()
        if creds:
            return creds

    creds_path = get_credentials_path()
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Credentials not found at {creds_path}\n"
            "Please ensure Claude Code is installed and you've logged in."
        )

    with open(creds_path) as f:
        return json.load(f)


def get_access_token() -> str:
    creds = get_credentials()
    oauth = creds.get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    if not token:
        raise ValueError("No access token found in credentials")
    return token


# ═══════════════════════════════════════════════════════════════════════════════
# History Management
# ═══════════════════════════════════════════════════════════════════════════════


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_history(history: list):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_HISTORY_DAYS)
    cutoff_str = cutoff.isoformat()
    history = [h for h in history if h.get("timestamp", "") > cutoff_str]

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_usage(data: dict):
    history = load_history()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "five_hour": data.get("five_hour", {}).get("utilization"),
        "seven_day": data.get("seven_day", {}).get("utilization"),
        "seven_day_sonnet": data.get("seven_day_sonnet", {}).get("utilization")
        if data.get("seven_day_sonnet")
        else None,
        "seven_day_opus": data.get("seven_day_opus", {}).get("utilization")
        if data.get("seven_day_opus")
        else None,
    }
    history.append(entry)
    save_history(history)


# ═══════════════════════════════════════════════════════════════════════════════
# Export Functions
# ═══════════════════════════════════════════════════════════════════════════════

# CSV columns schema:
# timestamp, five_hour_pct, seven_day_pct, seven_day_sonnet_pct, seven_day_opus_pct

CSV_COLUMNS = ["timestamp", "five_hour_pct", "seven_day_pct", "seven_day_sonnet_pct", "seven_day_opus_pct"]


def filter_history_by_days(history: list, days: Optional[int]) -> list:
    """Filter history entries to the last N days.

    Args:
        history: List of history entries.
        days: Number of days to include (None for all).

    Returns:
        Filtered list of history entries.
    """
    if days is None:
        return history

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    return [h for h in history if h.get("timestamp", "") >= cutoff_str]


def export_csv(history: list, days: Optional[int] = None, excel_bom: bool = False) -> str:
    """Export history to CSV format.

    Args:
        history: List of history entries.
        days: Filter to last N days (None for all).
        excel_bom: Add UTF-8 BOM for Excel compatibility.

    Returns:
        CSV formatted string.
    """
    filtered = filter_history_by_days(history, days)
    # Sort by timestamp descending (most recent first)
    filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    lines = []

    # Add BOM for Excel compatibility
    if excel_bom:
        lines.append("\ufeff")

    # Header row
    lines.append(",".join(CSV_COLUMNS))

    # Data rows
    for entry in filtered:
        row = [
            entry.get("timestamp", ""),
            str(entry.get("five_hour", "") if entry.get("five_hour") is not None else ""),
            str(entry.get("seven_day", "") if entry.get("seven_day") is not None else ""),
            str(entry.get("seven_day_sonnet", "") if entry.get("seven_day_sonnet") is not None else ""),
            str(entry.get("seven_day_opus", "") if entry.get("seven_day_opus") is not None else ""),
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
    # Sort by timestamp descending (most recent first)
    filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return json.dumps(filtered, indent=2)


def run_export(format_type: str, days: Optional[int], output_file: Optional[str], excel_bom: bool) -> int:
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
        print(f"{Colors.YELLOW}Warning: No history data available{Colors.RESET}", file=sys.stderr)
        return 0

    if format_type == "csv":
        output = export_csv(history, days, excel_bom)
    else:
        output = export_json(history, days)

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"{Colors.GREEN}Exported to {output_file}{Colors.RESET}", file=sys.stderr)
        except IOError as e:
            print(f"{Colors.RED}Error writing to {output_file}: {e}{Colors.RESET}", file=sys.stderr)
            return 1
    else:
        print(output)

    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# API Communication
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_usage() -> dict:
    """Fetch current usage from OAuth API."""
    token = get_access_token()

    req = Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": API_BETA_HEADER,
            "Content-Type": "application/json",
            "User-Agent": f"claude-watch/{__version__}",
        },
    )

    try:
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        if e.code == 401:
            raise RuntimeError(
                "Authentication failed. Your session may have expired.\n"
                "Please re-authenticate with Claude Code."
            )
        raise RuntimeError(f"API error: {e.code} {e.reason}")
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def load_cache() -> Optional[dict]:
    """Load cached usage data if valid."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        # Check cache age
        cached_at = cache.get("cached_at")
        if not cached_at:
            return None
        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - cached_dt).total_seconds()
        if age > CACHE_MAX_AGE:
            return None
        return cache.get("data")
    except (json.JSONDecodeError, IOError, ValueError):
        return None


def save_cache(data: dict):
    """Save usage data to cache."""
    cache = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except IOError:
        pass  # Silent fail for cache write errors


def get_stale_cache() -> Optional[dict]:
    """Get cached data even if stale (for fallback)."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        return cache.get("data")
    except (json.JSONDecodeError, IOError):
        return None


def fetch_usage_cached(cache_ttl: Optional[int] = None, silent: bool = False) -> Optional[dict]:
    """Fetch usage with caching support.

    Args:
        cache_ttl: Override default cache TTL in seconds.
        silent: If True, return None on error instead of raising.
                If cache exists, return stale cache on error.

    Returns:
        Usage data dict, or None if silent mode and error occurred.
    """
    global CACHE_MAX_AGE
    original_max_age = CACHE_MAX_AGE

    try:
        # Apply custom TTL if provided
        if cache_ttl is not None:
            CACHE_MAX_AGE = cache_ttl

        # Try to load from cache first
        cached = load_cache()
        if cached is not None:
            return cached

        # Cache miss or stale, fetch fresh data
        data = fetch_usage()
        save_cache(data)
        return data

    except Exception as e:
        if silent:
            # Try to return stale cache as fallback
            stale = get_stale_cache()
            if stale is not None:
                return stale
            return None
        raise
    finally:
        # Restore original TTL
        CACHE_MAX_AGE = original_max_age


def get_mock_usage_data() -> dict:
    """Generate mock usage data for dry-run mode.

    Returns realistic mock data that matches the API response format.
    Useful for testing and development without making API calls.
    """
    now = datetime.now(timezone.utc)

    return {
        "five_hour": {
            "utilization": 34.5,
            "resets_at": (now + timedelta(hours=3, minutes=15)).isoformat().replace("+00:00", "Z"),
        },
        "seven_day": {
            "utilization": 12.3,
            "resets_at": (now + timedelta(days=4, hours=9)).isoformat().replace("+00:00", "Z"),
        },
        "seven_day_sonnet": {
            "utilization": 8.1,
            "resets_at": (now + timedelta(days=3, hours=15)).isoformat().replace("+00:00", "Z"),
        },
        "seven_day_opus": None,
        "extra_usage": {
            "is_enabled": False,
        },
    }


def fetch_admin_usage(admin_key: str, days: int = 180) -> list:
    """Fetch historical usage from Admin API with pagination (default 180 days / 6 months)."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    all_data = []
    next_page = None

    while True:
        # Build URL with pagination
        url = (
            f"{ADMIN_API_URL}?"
            f"starting_at={start_date.strftime('%Y-%m-%dT00:00:00Z')}&"
            f"ending_at={end_date.strftime('%Y-%m-%dT23:59:59Z')}&"
            f"bucket_width=1d&"
            f"limit=31&"
            f"group_by[]=model"
        )
        if next_page:
            url += f"&page={next_page}"

        req = Request(
            url,
            headers={
                "x-api-key": admin_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": f"claude-watch/{__version__}",
            },
        )

        try:
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                all_data.extend(data.get("data", []))

                # Check for more pages
                if data.get("has_more") and data.get("next_page"):
                    next_page = data["next_page"]
                else:
                    break
        except HTTPError as e:
            if e.code == 401:
                raise RuntimeError("Admin API authentication failed. Check your API key.")
            if e.code == 403:
                raise RuntimeError("Admin API access denied. Ensure you have admin role.")
            raise RuntimeError(f"Admin API error: {e.code} {e.reason}")
        except URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

    return all_data


# ═══════════════════════════════════════════════════════════════════════════════
# Time Formatting
# ═══════════════════════════════════════════════════════════════════════════════


def parse_reset_time(iso_str: str) -> datetime:
    iso_str = iso_str.replace("Z", "+00:00")
    if "." in iso_str:
        parts = iso_str.split("+")
        if len(parts) == 2:
            iso_str = parts[0].split(".")[0] + "+" + parts[1]
    return datetime.fromisoformat(iso_str)


def format_relative_time(reset_at: str) -> str:
    reset_dt = parse_reset_time(reset_at)
    now = datetime.now(timezone.utc)
    delta = reset_dt - now
    total_seconds = max(0, int(delta.total_seconds()))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours} hr {minutes} min"
    elif minutes > 0:
        return f"{minutes} min"
    return "< 1 min"


def format_reset_compact(reset_at: str) -> str:
    """Format reset time as compact duration (e.g., '2h15m')."""
    reset_dt = parse_reset_time(reset_at)
    now = datetime.now(timezone.utc)
    delta = reset_dt - now
    total_seconds = max(0, int(delta.total_seconds()))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    elif minutes > 0:
        return f"{minutes}m"
    return "<1m"


def format_absolute_time(reset_at: str) -> str:
    reset_dt = parse_reset_time(reset_at)
    local_dt = reset_dt.astimezone()
    # Use %I (with padding) and strip leading zero manually for cross-platform compatibility
    # Windows doesn't support %-I, and %#I is Windows-only
    formatted = local_dt.strftime("%a %I:%M %p")
    # Remove leading zero from hour (e.g., "Mon 09:30 AM" -> "Mon 9:30 AM")
    parts = formatted.split(" ")
    if len(parts) >= 2 and parts[1].startswith("0"):
        parts[1] = parts[1][1:]
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Display Formatting
# ═══════════════════════════════════════════════════════════════════════════════


def make_progress_bar(percentage: float, width: int = 25) -> str:
    filled = int(width * percentage / 100)
    empty = width - filled
    return f"{Colors.BAR_FILL}{'█' * filled}{Colors.BAR_EMPTY}{'░' * empty}{Colors.RESET}"


def get_usage_color(percentage: float) -> str:
    if percentage >= 80:
        return Colors.RED
    elif percentage >= 50:
        return Colors.YELLOW
    return Colors.GREEN


def format_percentage(percentage: float) -> str:
    color = get_usage_color(percentage)
    return f"{color}{int(percentage)}% used{Colors.RESET}"

def print_usage_row(label: str, data: Optional[dict], use_relative_time: bool = False):
    if data is None:
        return

    utilization = data.get("utilization", 0)
    resets_at = data.get("resets_at", "")

    bar = make_progress_bar(utilization)
    pct = format_percentage(utilization)

    if resets_at:
        if use_relative_time:
            reset_str = f"Resets in {format_relative_time(resets_at)}"
        else:
            reset_str = f"Resets {format_absolute_time(resets_at)}"
    else:
        reset_str = ""

    print(f"{Colors.WHITE}{label:<20}{Colors.RESET} {bar}  {pct}")
    if reset_str:
        print(f"{Colors.DIM}{reset_str}{Colors.RESET}")
    print()


def display_usage(data: dict):
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Plan usage limits{Colors.RESET}")
    print()

    if data.get("five_hour"):
        print_usage_row("Current session", data["five_hour"], use_relative_time=True)

    print(f"{Colors.BOLD}{Colors.WHITE}Weekly limits{Colors.RESET}")
    print()

    if data.get("seven_day"):
        print_usage_row("All models", data["seven_day"])

    if data.get("seven_day_sonnet"):
        print_usage_row("Sonnet only", data["seven_day_sonnet"])

    if data.get("seven_day_opus"):
        print_usage_row("Opus only", data["seven_day_opus"])

    extra = data.get("extra_usage", {})
    if extra.get("is_enabled"):
        print(f"{Colors.BOLD}{Colors.WHITE}Extra usage{Colors.RESET}")
        print()
        if extra.get("utilization") is not None:
            print_usage_row(
                "Extra credits", {"utilization": extra["utilization"], "resets_at": None}
            )

    print(f"{Colors.DIM}Last updated: just now{Colors.RESET}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# Tmux Status Bar Formatting
# ═══════════════════════════════════════════════════════════════════════════════


def get_tmux_color(utilization: float) -> str:
    """Get tmux color name based on usage level."""
    if utilization >= 90:
        return "red"
    elif utilization >= 75:
        return "yellow"
    return "green"


def format_tmux(data: dict) -> str:
    """Format usage data for tmux status bar.

    Output format: 'S:45% 2h15m W:12%' with tmux color codes.
    """
    five_hour = data.get("five_hour") or {}
    seven_day = data.get("seven_day") or {}

    session_pct = int(five_hour.get("utilization", 0))
    weekly_pct = int(seven_day.get("utilization", 0))
    resets_at = five_hour.get("resets_at", "")

    # Get colors based on usage levels
    session_color = get_tmux_color(session_pct)
    weekly_color = get_tmux_color(weekly_pct)

    # Build session part with reset time
    reset_str = format_reset_compact(resets_at) if resets_at else ""

    # Build output with tmux color codes
    parts = []

    # Session usage with color
    session_part = f"#[fg={session_color}]S:{session_pct}%"
    if reset_str:
        session_part += f" {reset_str}"
    parts.append(session_part)

    # Weekly usage with color
    weekly_part = f"#[fg={weekly_color}]W:{weekly_pct}%"
    parts.append(weekly_part)

    # Reset color at end
    return " ".join(parts) + "#[default]"


# ═══════════════════════════════════════════════════════════════════════════════
# Watch Mode
# ═══════════════════════════════════════════════════════════════════════════════


def clear_screen() -> None:
    """Clear the terminal screen in a cross-platform way."""
    if platform.system() == "Windows":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def format_duration(seconds: int) -> str:
    """Format duration in seconds as human-readable string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def format_countdown(seconds_left: int) -> str:
    """Format countdown timer."""
    if seconds_left <= 0:
        return "refreshing..."
    return f"{seconds_left}s"


def calculate_delta(initial_data: dict, current_data: dict) -> Optional[float]:
    """Calculate usage delta from initial to current."""
    initial_five_hour = initial_data.get("five_hour") or {}
    current_five_hour = current_data.get("five_hour") or {}

    initial_util = initial_five_hour.get("utilization")
    current_util = current_five_hour.get("utilization")

    if initial_util is not None and current_util is not None:
        return current_util - initial_util
    return None


def format_delta(delta: Optional[float]) -> str:
    """Format delta value with sign and color."""
    if delta is None:
        return ""

    if delta > 0:
        return f"{Colors.RED}+{delta:.1f}%{Colors.RESET}"
    elif delta < 0:
        return f"{Colors.GREEN}{delta:.1f}%{Colors.RESET}"
    else:
        return f"{Colors.DIM}±0.0%{Colors.RESET}"


def print_watch_header(
    interval: int,
    countdown: int,
    session_duration: int,
    delta: Optional[float] = None,
) -> None:
    """Print the watch mode header with status information."""
    now = datetime.now(timezone.utc).astimezone()
    time_str = now.strftime("%H:%M:%S")

    header_parts = [
        f"{Colors.BOLD}{Colors.CYAN}Claude Watch{Colors.RESET}",
        f"{Colors.DIM}|{Colors.RESET}",
        f"Refresh: {format_countdown(countdown)}",
        f"{Colors.DIM}|{Colors.RESET}",
        f"Interval: {interval}s",
        f"{Colors.DIM}|{Colors.RESET}",
        f"Session: {format_duration(session_duration)}",
    ]

    if delta is not None:
        header_parts.extend([
            f"{Colors.DIM}|{Colors.RESET}",
            f"Delta: {format_delta(delta)}",
        ])

    header_parts.extend([
        f"{Colors.DIM}|{Colors.RESET}",
        f"{Colors.DIM}{time_str}{Colors.RESET}",
    ])

    print(" ".join(header_parts))
    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")


def print_watch_summary(
    session_duration: int,
    refresh_count: int,
    initial_data: Optional[dict],
    final_data: Optional[dict],
) -> None:
    """Print summary when exiting watch mode."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Watch Session Summary{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
    print(f"Duration: {format_duration(session_duration)}")
    print(f"Refreshes: {refresh_count}")

    if initial_data and final_data:
        delta = calculate_delta(initial_data, final_data)
        if delta is not None:
            print(f"Usage change: {format_delta(delta)}")

    print()


def run_watch_mode(
    fetch_func,
    display_func,
    interval: int = 30,
    analytics_mode: bool = False,
    history_func=None,
    config: Optional[dict] = None,
) -> None:
    """Run the watch mode loop."""
    import time as _time

    # Validate interval
    interval = max(10, min(300, interval))

    start_time = _time.time()
    refresh_count = 0
    initial_data = None
    current_data = None

    try:
        while True:
            loop_start = _time.time()
            session_duration = int(loop_start - start_time)

            # Fetch data
            try:
                current_data = fetch_func()
                if initial_data is None:
                    initial_data = current_data
                refresh_count += 1
            except Exception as e:
                clear_screen()
                print(f"{Colors.RED}Error fetching data: {e}{Colors.RESET}")
                _time.sleep(interval)
                continue

            # Calculate delta
            delta = None
            if initial_data and current_data:
                delta = calculate_delta(initial_data, current_data)

            # Display
            for countdown in range(interval, -1, -1):
                clear_screen()
                print_watch_header(interval, countdown, session_duration + (interval - countdown), delta)
                print()

                if analytics_mode and history_func:
                    display_func(current_data)
                    history = history_func()
                    display_analytics(current_data, history, config or {})
                else:
                    display_func(current_data)

                if countdown > 0:
                    _time.sleep(1)

    except KeyboardInterrupt:
        session_duration = int(_time.time() - start_time)
        clear_screen()
        print_watch_summary(session_duration, refresh_count, initial_data, current_data)


# ═══════════════════════════════════════════════════════════════════════════════
# Analytics Display
# ═══════════════════════════════════════════════════════════════════════════════


def make_sparkline(
    values: list, timestamps: list = None, width: int = 20, period_hours: int = 24
) -> tuple:
    """Generate sparkline with optional time axis labels.

    Args:
        values: Data values for sparkline
        timestamps: Optional list of ISO timestamps for time axis
        width: Max width of sparkline in characters
        period_hours: The period this data represents (24=day, 168=week) - controls date vs time format

    Returns: (sparkline_str, time_axis_str) or just sparkline_str if no timestamps
    """
    if not values:
        empty = "─" * width
        return (
            (f"{Colors.CYAN}{empty}{Colors.RESET}", "")
            if timestamps
            else f"{Colors.CYAN}{empty}{Colors.RESET}"
        )

    chars = "▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val > min_val else 1

    # Downsample if needed, keeping track of bin timestamps
    bin_times = []
    if len(values) > width:
        step = len(values) / width
        sampled_values = []
        for i in range(width):
            idx = int(i * step)
            sampled_values.append(values[idx])
            if timestamps:
                bin_times.append(timestamps[idx])
        values = sampled_values
    elif timestamps:
        bin_times = timestamps[:]

    # Generate sparkline
    sparkline = ""
    for v in values:
        idx = int((v - min_val) / range_val * (len(chars) - 1))
        sparkline += chars[idx]

    if not timestamps:
        return f"{Colors.CYAN}{sparkline}{Colors.RESET}"

    # Generate time axis - show labels at start, middle, and end
    num_bins = len(values)
    time_axis = ""

    if bin_times and num_bins >= 2:
        # Get first and last timestamps
        try:
            first_dt = datetime.fromisoformat(bin_times[0].replace("Z", "+00:00")).astimezone()
            last_dt = datetime.fromisoformat(bin_times[-1].replace("Z", "+00:00")).astimezone()

            # Use format based on intended period (not actual data span)
            if period_hours <= 48:  # 24h or 48h view - show time
                first_label = first_dt.strftime("%-H:%M")
                last_label = last_dt.strftime("%-H:%M")
            else:  # 7d or longer view - show date
                first_label = first_dt.strftime("%d/%m")
                last_label = last_dt.strftime("%d/%m")

            # Build axis: first_label padded to sparkline width, then last_label
            # First label left-aligned, last label right-aligned
            padding = num_bins - len(first_label) - len(last_label)
            if padding > 0:
                time_axis = first_label + " " * padding + last_label
            else:
                time_axis = first_label + "→" + last_label

        except (ValueError, AttributeError):
            pass

    return (f"{Colors.CYAN}{sparkline}{Colors.RESET}", f"{Colors.DIM}{time_axis}{Colors.RESET}")


def format_trend(current: float, previous: float) -> str:
    if previous is None or previous == 0:
        return ""

    change = current - previous
    pct_change = (change / previous) * 100 if previous != 0 else 0

    if change > 0:
        arrow, color = "↑", Colors.UP
    elif change < 0:
        arrow, color = "↓", Colors.DOWN
        pct_change = abs(pct_change)
    else:
        arrow, color = "→", Colors.FLAT

    return f"{color}{arrow} {pct_change:.1f}%{Colors.RESET}"


def get_period_stats(history: list, hours: int, field: str) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    # Filter and keep timestamps for time range
    filtered = [
        h for h in history if h.get("timestamp", "") > cutoff_str and h.get(field) is not None
    ]
    values = [h[field] for h in filtered]
    timestamps = [h["timestamp"] for h in filtered]

    if not values:
        return {"count": 0}

    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": statistics.mean(values),
        "current": values[-1] if values else None,
        "values": values,
        "timestamps": timestamps,  # Raw timestamps for sparkline axis
    }


def get_daily_peaks(history: list, field: str) -> dict:
    by_dow = defaultdict(list)
    by_hour = defaultdict(list)

    for h in history:
        if h.get(field) is None:
            continue
        try:
            dt = datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            by_dow[local_dt.strftime("%a")].append(h[field])
            by_hour[local_dt.hour].append(h[field])
        except (ValueError, KeyError):
            continue

    peak_day, peak_day_avg = None, 0
    for day, vals in by_dow.items():
        avg = statistics.mean(vals) if vals else 0
        if avg > peak_day_avg:
            peak_day, peak_day_avg = day, avg

    peak_hour, peak_hour_avg = None, 0
    for hour, vals in by_hour.items():
        avg = statistics.mean(vals) if vals else 0
        if avg > peak_hour_avg:
            peak_hour, peak_hour_avg = hour, avg

    return {
        "peak_day": peak_day,
        "peak_day_avg": peak_day_avg,
        "peak_hour": peak_hour,
        "peak_hour_avg": peak_hour_avg,
    }


def calculate_token_cost(
    input_tok: int, output_tok: int, cache_tok: int, model: str = "default"
) -> float:
    """Calculate API cost for given token counts."""
    pricing = API_PRICING.get(model, API_PRICING["default"])
    input_cost = (input_tok / 1_000_000) * pricing[0]
    output_cost = (output_tok / 1_000_000) * pricing[1]
    cache_cost = (cache_tok / 1_000_000) * pricing[2]
    return input_cost + output_cost + cache_cost


def display_admin_usage(admin_data: list, config: dict):
    """Display usage data from Admin API with cost analysis."""
    if not admin_data:
        print(f"{Colors.DIM}No usage data from Admin API{Colors.RESET}")
        return

    # Get user's subscription plan
    plan_key = config.get("subscription_plan", "pro")
    plan_info = SUBSCRIPTION_PLANS.get(plan_key, SUBSCRIPTION_PLANS["pro"])
    monthly_sub_cost = plan_info["cost"]
    daily_sub_cost = monthly_sub_cost / 30
    weekly_sub_cost = monthly_sub_cost / 4

    print()
    print(f"{Colors.BOLD}{Colors.MAGENTA}═══ Organization Usage (Admin API) ═══{Colors.RESET}")
    print(f"{Colors.DIM}Your plan: {plan_info['name']} (${monthly_sub_cost:.0f}/mo){Colors.RESET}")
    print()

    # Aggregate by day, week, month with model breakdown for cost calculation
    by_day = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0}))
    by_week = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0}))
    by_month = defaultdict(lambda: defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0}))

    for bucket in admin_data:
        date_str = bucket.get("starting_at", "")[:10]
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            week_key = dt.strftime("%Y-W%W")
            month_key = dt.strftime("%Y-%m")
        except ValueError:
            week_key = "unknown"
            month_key = "unknown"

        for result in bucket.get("results", []):
            input_tok = result.get("uncached_input_tokens", 0)
            output_tok = result.get("output_tokens", 0)
            cache_tok = result.get("cache_read_input_tokens", 0)
            model = result.get("model", "default")

            by_day[date_str][model]["input"] += input_tok
            by_day[date_str][model]["output"] += output_tok
            by_day[date_str][model]["cache_read"] += cache_tok

            by_week[week_key][model]["input"] += input_tok
            by_week[week_key][model]["output"] += output_tok
            by_week[week_key][model]["cache_read"] += cache_tok

            by_month[month_key][model]["input"] += input_tok
            by_month[month_key][model]["output"] += output_tok
            by_month[month_key][model]["cache_read"] += cache_tok

    def calc_period_cost(period_data: dict) -> float:
        """Calculate total cost for a period across all models."""
        total = 0.0
        for model, usage in period_data.items():
            total += calculate_token_cost(
                usage["input"], usage["output"], usage["cache_read"], model
            )
        return total

    def calc_period_tokens(period_data: dict) -> tuple:
        """Calculate total tokens for a period."""
        inp, out, cache = 0, 0, 0
        for usage in period_data.values():
            inp += usage["input"]
            out += usage["output"]
            cache += usage["cache_read"]
        return inp, out, cache

    def cost_indicator(api_cost: float, sub_cost: float) -> str:
        """Return colored indicator comparing API vs subscription cost."""
        if api_cost <= 0:
            return f"{Colors.DIM}--{Colors.RESET}"
        if api_cost < sub_cost * 0.5:
            return f"{Colors.GREEN}${api_cost:>6.2f}{Colors.RESET}"  # Much cheaper
        elif api_cost < sub_cost:
            return f"{Colors.CYAN}${api_cost:>6.2f}{Colors.RESET}"  # Cheaper
        elif api_cost < sub_cost * 1.5:
            return f"{Colors.YELLOW}${api_cost:>6.2f}{Colors.RESET}"  # Similar/slightly more
        else:
            return f"{Colors.RED}${api_cost:>6.2f}{Colors.RESET}"  # Much more expensive

    # ─── Daily Usage ───
    print(f"{Colors.BOLD}Daily Token Usage (Last 7 Days){Colors.RESET}")
    print(f"{Colors.DIM}Pro-rated subscription: ${daily_sub_cost:.2f}/day{Colors.RESET}")
    print()
    print(f"  {'Date':<12} {'Input':>10} {'Output':>10} {'API Cost':>10} {'vs Sub':>8}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

    daily_costs = []
    for date in sorted(by_day.keys(), reverse=True)[:7]:
        inp, out, cache = calc_period_tokens(by_day[date])
        cost = calc_period_cost(by_day[date])
        daily_costs.append(cost)
        diff = cost - daily_sub_cost
        if diff > 0:
            vs_sub = f"{Colors.RED}+${diff:.2f}{Colors.RESET}"
        elif diff < 0:
            vs_sub = f"{Colors.GREEN}-${-diff:.2f}{Colors.RESET}"
        else:
            vs_sub = f"{Colors.DIM}=$0.00{Colors.RESET}"
        print(f"  {date:<12} {inp:>10,} {out:>10,} {cost_indicator(cost, daily_sub_cost)} {vs_sub}")

    print()

    # ─── Weekly Usage ───
    if by_week:
        print(f"{Colors.BOLD}Weekly Token Usage (Last 4 Weeks){Colors.RESET}")
        print(f"{Colors.DIM}Pro-rated subscription: ${weekly_sub_cost:.2f}/week{Colors.RESET}")
        print()
        print(f"  {'Week':<12} {'Input':>10} {'Output':>10} {'API Cost':>10} {'vs Sub':>8}")
        print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

        weekly_costs = []
        for week in sorted(by_week.keys(), reverse=True)[:4]:
            inp, out, cache = calc_period_tokens(by_week[week])
            cost = calc_period_cost(by_week[week])
            weekly_costs.append(cost)
            diff = cost - weekly_sub_cost
            if diff > 0:
                vs_sub = f"{Colors.RED}+${diff:.2f}{Colors.RESET}"
            elif diff < 0:
                vs_sub = f"{Colors.GREEN}-${-diff:.2f}{Colors.RESET}"
            else:
                vs_sub = f"{Colors.DIM}=$0.00{Colors.RESET}"
            print(
                f"  {week:<12} {inp:>10,} {out:>10,} {cost_indicator(cost, weekly_sub_cost)} {vs_sub}"
            )

        print()

    # ─── Monthly Usage ───
    monthly_costs = {}
    if by_month:
        print(f"{Colors.BOLD}Monthly Token Usage (Last 6 Months){Colors.RESET}")
        print(f"{Colors.DIM}Subscription: ${monthly_sub_cost:.2f}/month{Colors.RESET}")
        print()
        print(f"  {'Month':<12} {'Input':>10} {'Output':>10} {'API Cost':>10} {'vs Sub':>10}")
        print(f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10}")

        for month in sorted(by_month.keys(), reverse=True)[:6]:
            inp, out, cache = calc_period_tokens(by_month[month])
            cost = calc_period_cost(by_month[month])
            monthly_costs[month] = cost
            diff = cost - monthly_sub_cost
            if diff > 0:
                vs_sub = f"{Colors.RED}+${diff:.2f}{Colors.RESET}"
            elif diff < 0:
                vs_sub = f"{Colors.GREEN}-${-diff:.2f}{Colors.RESET}"
            else:
                vs_sub = f"{Colors.DIM}=$0.00{Colors.RESET}"
            print(
                f"  {month:<12} {inp:>10,} {out:>10,} {cost_indicator(cost, monthly_sub_cost)} {vs_sub}"
            )

        print()

    # ─── Subscription Recommendation ───
    if monthly_costs:
        avg_monthly_cost = sum(monthly_costs.values()) / len(monthly_costs)
        total_cost = sum(monthly_costs.values())
        months_count = len(monthly_costs)

        print(f"{Colors.BOLD}{Colors.CYAN}═══ Subscription Recommendation ═══{Colors.RESET}")
        print()
        print(f"  Based on {months_count} months of usage data:")
        print()
        print(
            f"  {'Average monthly API cost:':<28} {Colors.BOLD}${avg_monthly_cost:>8.2f}{Colors.RESET}"
        )
        print(f"  {'Total API cost ({} months):':<28} ${total_cost:>8.2f}".format(months_count))
        print()

        # Calculate savings/cost for each plan
        print(f"  {'Plan':<12} {'Monthly':>10} {'vs API':>12} {'Recommendation':<20}")
        print(f"  {'-' * 12} {'-' * 10} {'-' * 12} {'-' * 20}")

        best_plan = None
        best_savings = float("-inf")

        for plan_id, plan_data in SUBSCRIPTION_PLANS.items():
            plan_cost = plan_data["cost"]
            diff = avg_monthly_cost - plan_cost

            if diff > 0:
                # API costs more - subscription saves money
                vs_api = f"{Colors.GREEN}saves ${diff:.2f}{Colors.RESET}"
                savings = diff
            else:
                # API costs less - subscription costs more
                vs_api = f"{Colors.YELLOW}costs ${-diff:.2f}{Colors.RESET}"
                savings = diff

            # Determine recommendation
            if avg_monthly_cost < SUBSCRIPTION_PLANS["pro"]["cost"] * 0.7:
                if plan_id == "pro":
                    rec = f"{Colors.YELLOW}Consider API{Colors.RESET}"
                else:
                    rec = ""
            elif plan_cost <= avg_monthly_cost * 1.1 and plan_cost >= avg_monthly_cost * 0.5:
                if savings > best_savings:
                    best_savings = savings
                    best_plan = plan_id
                rec = ""
            else:
                rec = ""

            print(f"  {plan_data['name']:<12} ${plan_cost:>8.0f} {vs_api:>20} {rec}")

        print()

        # Final recommendation based on API cost vs subscription tiers
        pro_cost = SUBSCRIPTION_PLANS["pro"]["cost"]
        max5_cost = SUBSCRIPTION_PLANS["max_5x"]["cost"]
        max20_cost = SUBSCRIPTION_PLANS["max_20x"]["cost"]

        if avg_monthly_cost < pro_cost * 0.5:
            # Very low usage - API might be better
            print(f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} Your usage is low enough that")
            print(
                f"     {Colors.YELLOW}pay-per-use API{Colors.RESET} might be more cost-effective."
            )
            print(f"     Average: ${avg_monthly_cost:.2f}/mo vs Pro: ${pro_cost:.0f}/mo")
        elif avg_monthly_cost < max5_cost:
            # API cost under $100 - Pro is best value
            print(
                f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} {Colors.GREEN}Pro ($20/mo){Colors.RESET} is optimal for your usage."
            )
            print(f"     Your API equivalent: ${avg_monthly_cost:.2f}/mo")
            if avg_monthly_cost > pro_cost:
                savings = avg_monthly_cost - pro_cost
                print(
                    f"     You save: {Colors.GREEN}${savings:.2f}/mo{Colors.RESET} with Pro subscription"
                )
        elif avg_monthly_cost < max20_cost:
            # API cost $100-$200 - Max 5x is best value
            print(
                f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} {Colors.GREEN}Max 5x ($100/mo){Colors.RESET} offers best value."
            )
            print(f"     Your API equivalent: ${avg_monthly_cost:.2f}/mo")
            savings = avg_monthly_cost - max5_cost
            if savings > 0:
                print(f"     You save: {Colors.GREEN}${savings:.2f}/mo{Colors.RESET} with Max 5x")
        else:
            # Heavy usage - Max 20x
            print(
                f"  {Colors.BOLD}💡 Recommendation:{Colors.RESET} {Colors.GREEN}Max 20x ($200/mo){Colors.RESET} for heavy usage."
            )
            print(f"     Your API equivalent: ${avg_monthly_cost:.2f}/mo")
            savings = avg_monthly_cost - max20_cost
            if savings > 0:
                print(f"     You save: {Colors.GREEN}${savings:.2f}/mo{Colors.RESET} with Max 20x")

        print()

        # ─── Rate Limit Analysis ───
        # Analyze usage patterns to determine if rate limits would be hit
        daily_costs_list = list(monthly_costs.values())
        if daily_costs_list:
            peak_monthly = max(daily_costs_list)
            avg_daily = avg_monthly_cost / 30

            print(f"{Colors.BOLD}{Colors.CYAN}═══ Rate Limit Analysis ═══{Colors.RESET}")
            print()
            print(
                f"  {Colors.DIM}Subscriptions have usage limits that may throttle heavy sessions.{Colors.RESET}"
            )
            print(
                f"  {Colors.DIM}API pay-per-use has no usage limits, only rate limits (tokens/min).{Colors.RESET}"
            )
            print()

            # Estimate sessions based on token usage patterns
            # Rough estimate: $1 of API cost ≈ 1 Claude Code session hour at average usage
            peak_daily_sessions = peak_monthly / 30  # Peak day estimate
            avg_daily_sessions = avg_monthly_cost / 30

            print(f"  {'Usage Pattern':<24} {'Your Usage':>12} {'Impact':>20}")
            print(f"  {'-' * 24} {'-' * 12} {'-' * 20}")

            # Peak month analysis
            if peak_monthly > monthly_sub_cost * 2:
                impact = f"{Colors.RED}May hit limits{Colors.RESET}"
            elif peak_monthly > monthly_sub_cost:
                impact = f"{Colors.YELLOW}Near limits{Colors.RESET}"
            else:
                impact = f"{Colors.GREEN}Within limits{Colors.RESET}"
            print(f"  {'Peak month cost':<24} ${peak_monthly:>10.2f} {impact:>28}")

            # Burstiness check (variance in monthly usage)
            if len(daily_costs_list) > 1:
                variance = max(daily_costs_list) / (sum(daily_costs_list) / len(daily_costs_list))
                if variance > 3:
                    burst_impact = f"{Colors.RED}Very bursty{Colors.RESET}"
                elif variance > 1.5:
                    burst_impact = f"{Colors.YELLOW}Somewhat bursty{Colors.RESET}"
                else:
                    burst_impact = f"{Colors.GREEN}Steady usage{Colors.RESET}"
                print(f"  {'Usage variance':<24} {variance:>11.1f}x {burst_impact:>28}")

            print()

            # Rate limit recommendations
            print(f"  {Colors.BOLD}Rate Limit Considerations:{Colors.RESET}")
            print()

            if peak_monthly > max20_cost:
                print(
                    f"  {Colors.RED}⚠{Colors.RESET}  Your peak usage (${peak_monthly:.0f}/mo) exceeds Max 20x limits."
                )
                print(f"      You may experience throttling even on the highest plan.")
                print(
                    f"      {Colors.CYAN}Consider:{Colors.RESET} API pay-per-use for unlimited capacity"
                )
            elif peak_monthly > max5_cost:
                print(
                    f"  {Colors.YELLOW}⚠{Colors.RESET}  Your peak usage suggests you might hit Max 5x limits."
                )
                print(
                    f"      {Colors.CYAN}Consider:{Colors.RESET} Max 20x for headroom, or API for peak periods"
                )
            elif peak_monthly > pro_cost * 2:
                print(f"  {Colors.YELLOW}ℹ{Colors.RESET}  Your peak usage is 2x+ Pro limits.")
                print(
                    f"      {Colors.CYAN}Consider:{Colors.RESET} Max 5x to avoid throttling on busy days"
                )
            else:
                print(
                    f"  {Colors.GREEN}✓{Colors.RESET}  Your usage patterns fit within subscription limits."
                )
                print(f"      Pro plan should provide sufficient capacity.")

            print()


def display_analytics(data: dict, history: list, config: dict):
    """Display detailed analytics."""
    print()
    print(f"{Colors.BOLD}{Colors.MAGENTA}═══ Usage Analytics ═══{Colors.RESET}")
    print()

    # Data source indicator
    if config.get("use_admin_api") and config.get("admin_api_key"):
        print(f"{Colors.DIM}Data source: Admin API + Local tracking{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Data source: Local tracking{Colors.RESET}")
    print()

    # Current usage summary
    print(f"{Colors.BOLD}{Colors.WHITE}Current Status{Colors.RESET}")
    print()

    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)

    session_remaining = 100 - five_hour
    weekly_remaining = 100 - seven_day

    print(f"  Session capacity remaining:  {Colors.GREEN}{session_remaining:.0f}%{Colors.RESET}")
    print(f"  Weekly capacity remaining:   {Colors.GREEN}{weekly_remaining:.0f}%{Colors.RESET}")

    if history:
        recent_1h = get_period_stats(history, 1, "five_hour")
        if recent_1h["count"] >= 2:
            rate = recent_1h["max"] - recent_1h["min"]
            if rate > 0:
                hours_to_limit = session_remaining / rate
                if hours_to_limit < 24:
                    print(
                        f"  Est. time to session limit:  {Colors.YELLOW}{hours_to_limit:.1f} hours{Colors.RESET} (at current rate)"
                    )

    print()

    # Historical trends from local data
    if not history:
        print(
            f"{Colors.DIM}No historical data yet. Run periodically to collect analytics.{Colors.RESET}"
        )
        print(f"{Colors.DIM}Data is stored in: {HISTORY_FILE}{Colors.RESET}")
        print()
        return

    print(f"{Colors.BOLD}{Colors.WHITE}Session Usage Trends (5-hour window){Colors.RESET}")
    print()

    stats_24h = get_period_stats(history, 24, "five_hour")
    if stats_24h["count"] > 0:
        sparkline, time_axis = make_sparkline(
            stats_24h["values"], stats_24h.get("timestamps"), period_hours=24
        )
        print(f"  Last 24h: {sparkline}")
        if time_axis:
            print(f"            {time_axis}")
        print(
            f"            Min: {stats_24h['min']:.0f}%  Max: {stats_24h['max']:.0f}%  Avg: {stats_24h['avg']:.1f}%"
        )

        stats_prev = get_period_stats(
            [
                h
                for h in history
                if h["timestamp"] < (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            ],
            24,
            "five_hour",
        )
        if stats_prev["count"] > 0:
            trend = format_trend(stats_24h["avg"], stats_prev["avg"])
            print(f"            vs prev 24h: {trend}")
    print()

    stats_7d = get_period_stats(history, 168, "five_hour")
    if stats_7d["count"] > 0:
        sparkline, time_axis = make_sparkline(
            stats_7d["values"], stats_7d.get("timestamps"), period_hours=168
        )
        print(f"  Last 7d:  {sparkline}")
        if time_axis:
            print(f"            {time_axis}")
        print(
            f"            Min: {stats_7d['min']:.0f}%  Max: {stats_7d['max']:.0f}%  Avg: {stats_7d['avg']:.1f}%"
        )
    print()

    print(f"{Colors.BOLD}{Colors.WHITE}Weekly Usage Trends (7-day window){Colors.RESET}")
    print()

    stats_weekly = get_period_stats(history, 168, "seven_day")
    if stats_weekly["count"] > 0:
        sparkline, time_axis = make_sparkline(
            stats_weekly["values"], stats_weekly.get("timestamps"), period_hours=168
        )
        print(f"  Last 7d:  {sparkline}")
        if time_axis:
            print(f"            {time_axis}")
        print(
            f"            Min: {stats_weekly['min']:.0f}%  Max: {stats_weekly['max']:.0f}%  Avg: {stats_weekly['avg']:.1f}%"
        )
    print()

    peaks = get_daily_peaks(history, "five_hour")
    if peaks["peak_day"] or peaks["peak_hour"] is not None:
        print(f"{Colors.BOLD}{Colors.WHITE}Usage Patterns{Colors.RESET}")
        print()
        if peaks["peak_day"]:
            print(
                f"  Peak day:   {Colors.YELLOW}{peaks['peak_day']}{Colors.RESET} (avg {peaks['peak_day_avg']:.1f}%)"
            )
        if peaks["peak_hour"] is not None:
            hour_str = datetime.now().replace(hour=peaks["peak_hour"], minute=0).strftime("%-I %p")
            print(
                f"  Peak hour:  {Colors.YELLOW}{hour_str}{Colors.RESET} (avg {peaks['peak_hour_avg']:.1f}%)"
            )
        print()

    total_records = len(history)
    oldest = min(h["timestamp"] for h in history) if history else None
    if oldest:
        oldest_dt = datetime.fromisoformat(oldest.replace("Z", "+00:00")).astimezone()
        days_tracked = (datetime.now(timezone.utc) - oldest_dt.astimezone(timezone.utc)).days
        print(
            f"{Colors.DIM}Analytics based on {total_records} data points over {days_tracked} days{Colors.RESET}"
        )

    print(f"{Colors.DIM}History stored in: {HISTORY_FILE}{Colors.RESET}")
    print()


def display_analytics_json(data: dict, history: list, config: dict):
    """Output analytics as JSON."""
    stats_24h = get_period_stats(history, 24, "five_hour")
    stats_7d = get_period_stats(history, 168, "five_hour")
    stats_weekly = get_period_stats(history, 168, "seven_day")
    peaks = get_daily_peaks(history, "five_hour")

    analytics = {
        "current": data,
        "history_count": len(history),
        "data_source": "admin_api" if config.get("use_admin_api") else "local",
        "session_stats_24h": {
            "min": stats_24h.get("min"),
            "max": stats_24h.get("max"),
            "avg": stats_24h.get("avg"),
            "count": stats_24h.get("count", 0),
        }
        if stats_24h["count"] > 0
        else None,
        "session_stats_7d": {
            "min": stats_7d.get("min"),
            "max": stats_7d.get("max"),
            "avg": stats_7d.get("avg"),
            "count": stats_7d.get("count", 0),
        }
        if stats_7d["count"] > 0
        else None,
        "weekly_stats_7d": {
            "min": stats_weekly.get("min"),
            "max": stats_weekly.get("max"),
            "avg": stats_weekly.get("avg"),
            "count": stats_weekly.get("count", 0),
        }
        if stats_weekly["count"] > 0
        else None,
        "patterns": {
            "peak_day": peaks.get("peak_day"),
            "peak_day_avg": peaks.get("peak_day_avg"),
            "peak_hour": peaks.get("peak_hour"),
            "peak_hour_avg": peaks.get("peak_hour_avg"),
        },
    }

    print(json.dumps(analytics, indent=2))


def display_json(data: dict):
    print(json.dumps(data, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# Forecast Functions
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_hourly_rate(history: list, hours: int = 4) -> Optional[dict]:
    """Calculate usage rate per hour from recent history.

    Args:
        history: List of history entries.
        hours: Number of hours to analyze (default: 4).

    Returns:
        Dict with rate info or None if insufficient data.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    # Get entries from the period
    filtered = [
        h for h in history if h.get("timestamp", "") > cutoff_str and h.get("five_hour") is not None
    ]

    if len(filtered) < 2:
        return None

    # Sort by timestamp
    filtered.sort(key=lambda x: x["timestamp"])

    # Calculate rate from first to last
    first_ts = datetime.fromisoformat(filtered[0]["timestamp"].replace("Z", "+00:00"))
    last_ts = datetime.fromisoformat(filtered[-1]["timestamp"].replace("Z", "+00:00"))
    hours_elapsed = (last_ts - first_ts).total_seconds() / 3600

    if hours_elapsed < 0.1:  # Less than 6 minutes
        return None

    first_val = filtered[0]["five_hour"]
    last_val = filtered[-1]["five_hour"]
    change = last_val - first_val

    rate_per_hour = change / hours_elapsed if hours_elapsed > 0 else 0

    # Calculate variance for confidence intervals
    rates = []
    for i in range(1, len(filtered)):
        prev_ts = datetime.fromisoformat(filtered[i - 1]["timestamp"].replace("Z", "+00:00"))
        curr_ts = datetime.fromisoformat(filtered[i]["timestamp"].replace("Z", "+00:00"))
        h_diff = (curr_ts - prev_ts).total_seconds() / 3600
        if h_diff > 0.05:  # At least 3 minutes
            val_diff = filtered[i]["five_hour"] - filtered[i - 1]["five_hour"]
            rates.append(val_diff / h_diff)

    if rates:
        rate_std = statistics.stdev(rates) if len(rates) > 1 else 0
    else:
        rate_std = 0

    return {
        "rate_per_hour": rate_per_hour,
        "rate_std": rate_std,
        "hours_analyzed": hours_elapsed,
        "data_points": len(filtered),
    }


def calculate_forecast(data: dict, history: list, config: dict) -> dict:
    """Calculate usage forecast with projections.

    Args:
        data: Current usage data.
        history: Historical usage data.
        config: User configuration.

    Returns:
        Dict with forecast data.
    """
    five_hour = data.get("five_hour", {}).get("utilization", 0)
    seven_day = data.get("seven_day", {}).get("utilization", 0)

    session_remaining = 100 - five_hour
    weekly_remaining = 100 - seven_day

    forecast = {
        "current": {
            "session_used": five_hour,
            "session_remaining": session_remaining,
            "weekly_used": seven_day,
            "weekly_remaining": weekly_remaining,
        },
        "session": {},
        "weekly": {},
        "recommendations": [],
    }

    # Calculate session forecast from recent data
    rate_info = calculate_hourly_rate(history, hours=4)
    if rate_info and rate_info["rate_per_hour"] > 0:
        rate = rate_info["rate_per_hour"]
        rate_std = rate_info["rate_std"]

        # Time to limit estimates
        hours_to_limit = session_remaining / rate if rate > 0 else float("inf")

        # Conservative estimate (higher rate)
        conservative_rate = rate + rate_std
        hours_conservative = session_remaining / conservative_rate if conservative_rate > 0 else float("inf")

        # Optimistic estimate (lower rate)
        optimistic_rate = max(0.1, rate - rate_std)
        hours_optimistic = session_remaining / optimistic_rate if optimistic_rate > 0 else float("inf")

        forecast["session"] = {
            "rate_per_hour": round(rate, 2),
            "hours_to_limit": round(hours_to_limit, 1) if hours_to_limit < 100 else None,
            "hours_conservative": round(hours_conservative, 1) if hours_conservative < 100 else None,
            "hours_optimistic": round(hours_optimistic, 1) if hours_optimistic < 100 else None,
            "data_quality": "good" if rate_info["data_points"] >= 5 else "limited",
        }

        # Add recommendations based on forecast
        if hours_to_limit < 1:
            forecast["recommendations"].append({
                "severity": "critical",
                "message": "Session limit imminent - consider pausing or reducing usage",
            })
        elif hours_to_limit < 2:
            forecast["recommendations"].append({
                "severity": "warning",
                "message": "Session limit approaching in ~{:.0f}h - plan accordingly".format(hours_to_limit),
            })

    # Calculate weekly forecast
    # Use 24h average to project weekly trajectory
    stats_24h = get_period_stats(history, 24, "seven_day")
    if stats_24h["count"] >= 2:
        daily_change = stats_24h["max"] - stats_24h["min"]
        if daily_change > 0:
            days_to_limit = weekly_remaining / daily_change
            weekly_projection = seven_day + (daily_change * 7)

            forecast["weekly"] = {
                "daily_rate": round(daily_change, 1),
                "days_to_limit": round(days_to_limit, 1) if days_to_limit < 30 else None,
                "weekly_projection": round(min(100, weekly_projection), 1),
                "on_track": weekly_projection <= 85,
            }

            if weekly_projection > 95:
                forecast["recommendations"].append({
                    "severity": "warning",
                    "message": "Weekly usage trending high - projected to hit {:.0f}%".format(weekly_projection),
                })
            elif weekly_projection <= 60:
                forecast["recommendations"].append({
                    "severity": "info",
                    "message": "Weekly usage is efficient - plenty of capacity remaining",
                })

    # General recommendations based on current state
    if five_hour >= 90:
        forecast["recommendations"].append({
            "severity": "critical",
            "message": "Session limit nearly reached - wait for reset or reduce intensity",
        })
    elif five_hour >= 75:
        forecast["recommendations"].append({
            "severity": "warning",
            "message": "High session usage - consider pacing your requests",
        })

    if seven_day >= 85:
        forecast["recommendations"].append({
            "severity": "warning",
            "message": "Weekly limit approaching - prioritize critical tasks",
        })

    if not forecast["recommendations"]:
        forecast["recommendations"].append({
            "severity": "info",
            "message": "Usage is within healthy limits",
        })

    return forecast


def display_forecast(data: dict, history: list, config: dict):
    """Display usage forecast with projections and recommendations."""
    forecast = calculate_forecast(data, history, config)

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}═══ Usage Forecast ═══{Colors.RESET}")
    print()

    # Current status
    current = forecast["current"]
    print(f"{Colors.BOLD}{Colors.WHITE}Current Status{Colors.RESET}")
    print()
    print(f"  Session:  {current['session_used']:.0f}% used, {Colors.GREEN}{current['session_remaining']:.0f}%{Colors.RESET} remaining")
    print(f"  Weekly:   {current['weekly_used']:.0f}% used, {Colors.GREEN}{current['weekly_remaining']:.0f}%{Colors.RESET} remaining")
    print()

    # Session projections
    session = forecast.get("session", {})
    if session:
        print(f"{Colors.BOLD}{Colors.WHITE}Session Projections{Colors.RESET}")
        print()
        rate = session.get("rate_per_hour", 0)
        if rate > 0:
            print(f"  Current rate:    {Colors.YELLOW}{rate:.1f}%/hour{Colors.RESET}")

            hours_to_limit = session.get("hours_to_limit")
            if hours_to_limit:
                hours_conservative = session.get("hours_conservative")
                hours_optimistic = session.get("hours_optimistic")

                # Color based on urgency
                if hours_to_limit < 1:
                    color = Colors.RED
                elif hours_to_limit < 3:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN

                print(f"  Time to limit:   {color}{hours_to_limit:.1f}h{Colors.RESET}", end="")
                if hours_conservative and hours_optimistic:
                    print(f" (range: {hours_conservative:.1f}h - {hours_optimistic:.1f}h)")
                else:
                    print()
            else:
                print(f"  Time to limit:   {Colors.GREEN}Not projected to hit limit{Colors.RESET}")

            quality = session.get("data_quality", "unknown")
            quality_icon = "✓" if quality == "good" else "○"
            print(f"  Data quality:    {quality_icon} {quality}")
        print()

    # Weekly projections
    weekly = forecast.get("weekly", {})
    if weekly:
        print(f"{Colors.BOLD}{Colors.WHITE}Weekly Projections{Colors.RESET}")
        print()
        daily_rate = weekly.get("daily_rate", 0)
        if daily_rate > 0:
            print(f"  Daily rate:      {Colors.YELLOW}{daily_rate:.1f}%/day{Colors.RESET}")

            projection = weekly.get("weekly_projection", 0)
            on_track = weekly.get("on_track", True)
            proj_color = Colors.GREEN if on_track else Colors.YELLOW
            print(f"  7-day projection: {proj_color}{projection:.0f}%{Colors.RESET}")

            days_to_limit = weekly.get("days_to_limit")
            if days_to_limit:
                print(f"  Days to limit:   {Colors.YELLOW}{days_to_limit:.1f} days{Colors.RESET}")
        print()

    # Recommendations
    recommendations = forecast.get("recommendations", [])
    if recommendations:
        print(f"{Colors.BOLD}{Colors.WHITE}Recommendations{Colors.RESET}")
        print()
        for rec in recommendations:
            severity = rec.get("severity", "info")
            message = rec.get("message", "")

            if severity == "critical":
                icon = f"{Colors.RED}🚨{Colors.RESET}"
            elif severity == "warning":
                icon = f"{Colors.YELLOW}⚠️ {Colors.RESET}"
            else:
                icon = f"{Colors.GREEN}✓{Colors.RESET}"

            print(f"  {icon} {message}")
        print()


def display_forecast_json(data: dict, history: list, config: dict):
    """Output forecast as JSON."""
    forecast = calculate_forecast(data, history, config)
    print(json.dumps(forecast, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# Desktop Notifications
# ═══════════════════════════════════════════════════════════════════════════════

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


def save_notify_state(state: dict):
    """Save notification state to file."""
    NOTIFY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIFY_STATE_FILE, "w") as f:
        json.dump(state, f)


def send_notification_linux(title: str, message: str, urgency: str = "normal") -> bool:
    """Send notification on Linux using notify-send.

    Args:
        title: Notification title.
        message: Notification body.
        urgency: Notification urgency (low, normal, critical).

    Returns:
        True if notification was sent successfully.
    """
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
    """Send notification on macOS using osascript.

    Args:
        title: Notification title.
        message: Notification body.
        urgency: Notification urgency (unused on macOS).

    Returns:
        True if notification was sent successfully.
    """
    # Escape quotes for AppleScript
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
    """Send notification on Windows using PowerShell toast.

    Args:
        title: Notification title.
        message: Notification body.
        urgency: Notification urgency (unused on Windows).

    Returns:
        True if notification was sent successfully.
    """
    # PowerShell toast notification
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

    # Use max of session and weekly for threshold comparison
    current_usage = max(five_hour, seven_day)

    # Load state
    state = load_notify_state()
    last_thresholds = set(state.get("last_thresholds", []))

    # Sort thresholds descending to check highest first
    thresholds_sorted = sorted(thresholds, reverse=True)

    # Find exceeded thresholds
    exceeded = [t for t in thresholds_sorted if current_usage >= t]

    # Check if we should reset state (usage dropped below 50%)
    # Only reset if we previously had thresholds AND the lowest threshold is >= 50
    min_threshold = min(thresholds) if thresholds else 80
    reset_threshold = min(50, min_threshold)
    if current_usage < reset_threshold:
        if last_thresholds:
            if verbose:
                print(f"{Colors.GREEN}Usage dropped below {reset_threshold}%, resetting notification state{Colors.RESET}")
            state["last_thresholds"] = []
            save_notify_state(state)
        if not exceeded:
            if verbose:
                print(f"{Colors.GREEN}Usage at {current_usage:.0f}% (below all thresholds){Colors.RESET}")
            return 0

    # Find new thresholds that haven't been notified
    new_exceeded = [t for t in exceeded if t not in last_thresholds]

    if not new_exceeded:
        if verbose:
            if exceeded:
                print(f"{Colors.DIM}Usage at {current_usage:.0f}% (already notified for {exceeded[0]}%){Colors.RESET}")
            else:
                print(f"{Colors.GREEN}Usage at {current_usage:.0f}% (below all thresholds){Colors.RESET}")
        return 0

    # Send notification for highest new threshold
    highest_new = max(new_exceeded)

    # Determine urgency
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
        # Update state with all exceeded thresholds
        state["last_thresholds"] = exceeded
        state["last_notified_at"] = datetime.now(timezone.utc).isoformat()
        save_notify_state(state)

        if verbose:
            print(f"{Colors.GREEN}Notification sent successfully{Colors.RESET}")

        return 2 if urgency == "critical" else 1
    else:
        if verbose:
            print(f"{Colors.RED}Failed to send notification (notify-send not available?){Colors.RESET}")
        return 0


def run_notify_daemon(thresholds: List[int], interval: int = 300):
    """Run notification daemon in the background.

    Args:
        thresholds: List of threshold percentages to check.
        interval: Check interval in seconds (default: 300 = 5 minutes).
    """
    print(f"{Colors.CYAN}Starting notification daemon...{Colors.RESET}")
    print(f"  Thresholds: {', '.join(str(t) + '%' for t in sorted(thresholds))}")
    print(f"  Interval: {interval}s")
    print(f"  Press Ctrl+C to stop")
    print()

    try:
        while True:
            try:
                data = fetch_usage_cached(cache_ttl=0, silent=True)
                if data:
                    check_and_notify(data, thresholds, verbose=True)
            except Exception as e:
                print(f"{Colors.RED}Error checking usage: {e}{Colors.RESET}", file=sys.stderr)

            time.sleep(interval)
    except KeyboardInterrupt:
        print()
        print(f"{Colors.CYAN}Notification daemon stopped{Colors.RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Monitor Claude Code subscription usage limits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-watch              Show usage in formatted view
  claude-watch --analytics  Show detailed analytics and trends
  claude-watch --setup      Run interactive setup wizard
  claude-watch --config     Show current configuration (default: show)
  claude-watch --config show  Explicitly show current configuration
  claude-watch --config reset Reset configuration to defaults
  claude-watch --config set subscription_plan max_5x  Set a config value
  claude-watch --json       Output raw JSON data
  claude-watch --tmux       Output for tmux status bar
  claude-watch --watch      Live updating display (30s interval)
  claude-watch -w 60        Live display with 60s interval
  claude-watch --verbose    Show timing and cache info
  claude-watch --quiet      Silent mode for scripts
  claude-watch --dry-run    Test without API calls (uses mock data)
  claude-watch --version    Show version and system info
  claude-watch --update     Check for and install updates
  claude-watch -U check     Check for updates without installing
  claude-watch --export csv Export history to CSV
  claude-watch --export json -d 7 -o usage.json  Export last 7 days to JSON file
  claude-watch --export csv --excel -o data.csv  Export CSV with Excel BOM
  claude-watch --forecast   Show usage projections and recommendations
  claude-watch -f --json    Output forecast as JSON
  claude-watch --notify     Send desktop notification if usage exceeds thresholds
  claude-watch --notify --notify-at 70,85,95  Custom thresholds
  claude-watch --notify-daemon  Run as background notification service
  ccw                       Short alias (add to shell config)

Setup:
  On first run, you'll be prompted to configure:
  - Admin API key (optional, for organizations)
  - Automatic hourly data collection
""",
    )

    parser.add_argument(
        "--json", "-j", action="store_true", help="Output raw JSON instead of formatted view"
    )
    parser.add_argument(
        "--analytics",
        "-a",
        action="store_true",
        help="Show detailed analytics with historical trends",
    )
    parser.add_argument("--setup", "-s", action="store_true", help="Run interactive setup wizard")
    parser.add_argument(
        "--config",
        "-c",
        nargs="*",
        metavar="COMMAND",
        help="Configuration commands: show (default), reset, set KEY VALUE",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument(
        "--no-record", action="store_true", help="Don't record this fetch to history"
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        metavar="SECONDS",
        help=f"Cache TTL in seconds (default: {CACHE_MAX_AGE})",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        help="Show version and system information",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including timing and cache info",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress all output except errors",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making API calls (uses mock data)",
    )
    parser.add_argument(
        "--update",
        "-U",
        nargs="?",
        const="update",
        metavar="check",
        help="Check for and install updates. Use --update check to only check without installing.",
    )
    parser.add_argument(
        "--tmux",
        action="store_true",
        help="Output optimized for tmux status bar with tmux color codes.",
    )
    parser.add_argument(
        "--watch",
        "-w",
        nargs="?",
        const=30,
        type=int,
        metavar="SEC",
        help="Live updating display. Interval: 10-300 seconds (default: 30).",
    )
    parser.add_argument(
        "--export",
        choices=["csv", "json"],
        metavar="FORMAT",
        help="Export history data. FORMAT: csv or json.",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        metavar="N",
        help="Filter export to last N days (default: all history).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output file for export (default: stdout).",
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Add UTF-8 BOM for Excel compatibility (CSV only).",
    )
    parser.add_argument(
        "--forecast",
        "-f",
        action="store_true",
        help="Show usage forecast with projections and recommendations.",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Show desktop notification if usage exceeds thresholds.",
    )
    parser.add_argument(
        "--notify-at",
        metavar="THRESHOLDS",
        default="80,90,95",
        help="Comma-separated thresholds for notifications (default: 80,90,95).",
    )
    parser.add_argument(
        "--notify-daemon",
        action="store_true",
        help="Run as background daemon checking usage periodically.",
    )

    args = parser.parse_args()

    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith("_"):
                setattr(Colors, attr, "")

    # Handle version flag
    if args.version:
        print(f"claude-watch {__version__} (Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}, {platform.system()} {platform.machine()})")
        return

    # Handle update flag
    if args.update is not None:
        check_only = args.update == "check"
        exit_code = run_update(check_only=check_only)
        sys.exit(exit_code)

    # Handle --tmux with cached-first strategy (fast for tmux status bar)
    if args.tmux:
        # Handle dry-run mode for tmux
        if args.dry_run:
            data = get_mock_usage_data()
        else:
            # Try cache first (prefer speed over freshness for status bar)
            data = load_cache()
            if data is None:
                data = get_stale_cache()
            if data is None:
                # No cache at all, fetch silently
                data = fetch_usage_cached(silent=True)
            if data is None:
                # Still nothing, show empty output with error exit code
                print("")
                sys.exit(3)

        print(format_tmux(data))

        # Set exit code based on usage level
        five_hour = data.get("five_hour") or {}
        utilization = five_hour.get("utilization", 0)
        if utilization >= 90:
            sys.exit(2)  # Critical
        elif utilization >= 75:
            sys.exit(1)  # Warning
        sys.exit(0)  # OK

    # Handle --watch mode
    if args.watch is not None:
        config = load_config()

        def fetch_for_watch():
            return fetch_usage_cached(cache_ttl=0)  # Always fetch fresh data

        run_watch_mode(
            fetch_func=fetch_for_watch,
            display_func=display_usage,
            interval=args.watch,
            analytics_mode=args.analytics,
            history_func=load_history if args.analytics else None,
            config=config if args.analytics else None,
        )
        return

    # Handle --export mode
    if args.export:
        exit_code = run_export(args.export, args.days, args.output, args.excel)
        sys.exit(exit_code)

    # Handle --notify-daemon mode
    if args.notify_daemon:
        thresholds = [int(t.strip()) for t in args.notify_at.split(",")]
        run_notify_daemon(thresholds)
        return

    # Handle --notify mode
    if args.notify:
        # Parse thresholds
        try:
            thresholds = [int(t.strip()) for t in args.notify_at.split(",")]
        except ValueError:
            print(f"{Colors.RED}Error: Invalid threshold format. Use comma-separated numbers (e.g., 80,90,95){Colors.RESET}")
            sys.exit(1)

        # Fetch data
        data = fetch_usage_cached(cache_ttl=0, silent=True)
        if data is None:
            print(f"{Colors.RED}Error: Failed to fetch usage data{Colors.RESET}")
            sys.exit(3)

        exit_code = check_and_notify(data, thresholds, verbose=args.verbose)
        sys.exit(exit_code)

    # Handle setup and config commands
    if args.setup:
        run_setup()
        return

    if args.config is not None:
        # Handle empty list (just --config with no args) as "show"
        if len(args.config) == 0:
            show_config()
        elif args.config[0] == "show":
            show_config()
        elif args.config[0] == "reset":
            reset_config()
        elif args.config[0] == "set":
            if len(args.config) != 3:
                print(f"{Colors.RED}Error: 'set' requires KEY and VALUE arguments{Colors.RESET}")
                print(f"Usage: claude-watch --config set KEY VALUE")
                print(f"\nValid keys: {', '.join(sorted(DEFAULT_CONFIG.keys()))}")
                sys.exit(1)
            set_config(args.config[1], args.config[2])
        else:
            print(f"{Colors.RED}Error: Unknown config command '{args.config[0]}'{Colors.RESET}")
            print(f"Available commands: show, reset, set KEY VALUE")
            sys.exit(1)
        return

    # Load config
    config = load_config()

    # First run check
    if not config.get("setup_completed") and sys.stdin.isatty():
        print()
        print(f"{Colors.BOLD}{Colors.CYAN}Welcome to Claude Code Watch!{Colors.RESET}")
        print()
        if prompt_yes_no("Would you like to run the setup wizard?", default=True):
            run_setup()
            return
        else:
            config["setup_completed"] = True
            save_config(config)

    try:
        import time as _time

        start_time = _time.time()

        # Handle dry-run mode
        if args.dry_run:
            if not args.quiet:
                print(f"{Colors.YELLOW}[DRY-RUN]{Colors.RESET} Using mock data (no API calls)")
                print()
            data = get_mock_usage_data()
            cache_hit = False
            fetch_time = 0.0
        else:
            # Fetch current usage
            cache_ttl = args.cache_ttl if args.cache_ttl is not None else CACHE_MAX_AGE
            cached_data = load_cache()
            cache_hit = cached_data is not None

            if args.quiet:
                # Quiet mode: no spinner, use cached fetch
                data = fetch_usage_cached(cache_ttl=cache_ttl, silent=True)
                if data is None:
                    sys.exit(1)  # Silent failure
            else:
                if not args.verbose:
                    with Spinner("Fetching usage data"):
                        data = fetch_usage_cached(cache_ttl=cache_ttl, silent=False)
                else:
                    print(f"Fetching usage data (cache TTL: {cache_ttl}s)...")
                    data = fetch_usage_cached(cache_ttl=cache_ttl, silent=False)

            fetch_time = _time.time() - start_time

        # Show verbose info
        if args.verbose:
            cache_status = "DRY-RUN" if args.dry_run else ("HIT" if cache_hit else "MISS")
            print(f"  Cache: {cache_status}")
            print(f"  Time: {fetch_time:.2f}s")
            print()

        # Record to history (skip in dry-run mode)
        if not args.no_record and not args.dry_run:
            record_usage(data)

        history = load_history()

        # Quiet mode: only output if there's a problem (future threshold support)
        if args.quiet:
            return

        # Display output
        if args.forecast:
            # Standalone forecast mode
            if args.json:
                display_forecast_json(data, history, config)
            else:
                display_usage(data)
                display_forecast(data, history, config)
        elif args.analytics:
            # Only fetch admin data for analytics view (slower but more detailed)
            admin_data = None
            if config.get("use_admin_api") and config.get("admin_api_key"):
                try:
                    with Spinner("Fetching organization data"):
                        admin_data = fetch_admin_usage(config["admin_api_key"])
                except Exception as e:
                    print(
                        f"{Colors.YELLOW}Warning: Admin API fetch failed: {e}{Colors.RESET}",
                        file=sys.stderr,
                    )

            if args.json:
                display_analytics_json(data, history, config)
            else:
                display_usage(data)
                if admin_data:
                    display_admin_usage(admin_data, config)
                display_analytics(data, history, config)
                # Also show forecast in analytics mode
                display_forecast(data, history, config)
        elif args.json:
            display_json(data)
        else:
            display_usage(data)

    except FileNotFoundError as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, ValueError) as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)


if __name__ == "__main__":
    main()
