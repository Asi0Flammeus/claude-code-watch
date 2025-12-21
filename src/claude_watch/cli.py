"""Command-line interface for claude-watch.

This module provides the main entry point and argument parsing for the
claude-watch CLI tool.
"""

import argparse
import platform
import sys
from typing import Optional

from claude_watch._version import __version__
from claude_watch.display.colors import Colors


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
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
  claude-watch --prompt     Output for shell prompt (default format)
  claude-watch -p minimal   Shell prompt in minimal format
  claude-watch --verbose    Show timing and cache info
  claude-watch --quiet      Silent mode for scripts
  claude-watch --dry-run    Test without API calls (uses mock data)
  claude-watch --version    Show version and system info
  claude-watch --update     Check for and install updates
  claude-watch -U check     Check for updates without installing
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
        help="Cache TTL in seconds (default: 60)",
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
        "--prompt",
        "-p",
        nargs="?",
        const="default",
        choices=["default", "minimal", "full", "icon"],
        metavar="FORMAT",
        help="Output for shell prompt integration. Formats: default, minimal, full, icon.",
    )

    return parser


def print_version() -> None:
    """Print version and system information."""
    print(
        f"claude-watch {__version__} "
        f"(Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}, "
        f"{platform.system()} {platform.machine()})"
    )


def handle_config_command(
    config_args: list,
    show_config_func,
    reset_config_func,
    set_config_func,
    default_config: dict,
) -> None:
    """Handle configuration subcommands.

    Args:
        config_args: List of config command arguments.
        show_config_func: Function to display current configuration.
        reset_config_func: Function to reset configuration.
        set_config_func: Function to set a configuration value.
        default_config: Dictionary of default configuration values.
    """
    # Handle empty list (just --config with no args) as "show"
    if len(config_args) == 0:
        show_config_func()
    elif config_args[0] == "show":
        show_config_func()
    elif config_args[0] == "reset":
        reset_config_func()
    elif config_args[0] == "set":
        if len(config_args) != 3:
            print(f"{Colors.RED}Error: 'set' requires KEY and VALUE arguments{Colors.RESET}")
            print("Usage: claude-watch --config set KEY VALUE")
            print(f"\nValid keys: {', '.join(sorted(default_config.keys()))}")
            sys.exit(1)
        set_config_func(config_args[1], config_args[2])
    else:
        print(f"{Colors.RED}Error: Unknown config command '{config_args[0]}'{Colors.RESET}")
        print("Available commands: show, reset, set KEY VALUE")
        sys.exit(1)


def main() -> None:
    """Main entry point for claude-watch CLI.

    This function is the primary entry point when installed via pip/pipx/uv.
    It parses arguments and dispatches to the appropriate handler.
    """
    import json
    import time

    from claude_watch.api.cache import CACHE_MAX_AGE
    from claude_watch.api.client import fetch_usage_cached, get_mock_usage_data
    from claude_watch.config.settings import (
        DEFAULT_CONFIG,
        load_config,
        reset_config,
        save_config,
    )
    from claude_watch.display.analytics import display_analytics
    from claude_watch.display.usage import display_usage
    from claude_watch.history.storage import load_history, record_usage
    from claude_watch.setup.wizard import run_setup
    from claude_watch.update.checker import run_update

    parser = create_parser()
    args = parser.parse_args()

    # Handle --no-color flag
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith("_"):
                setattr(Colors, attr, "")

    # Handle --version flag
    if args.version:
        print_version()
        return

    # Handle --update flag
    if args.update is not None:
        check_only = args.update == "check"
        exit_code = run_update(__version__, check_only=check_only)
        sys.exit(exit_code)

    # Load configuration
    config = load_config()

    # Handle --setup flag
    if args.setup:
        run_setup()
        return

    # Handle --config flag
    if args.config is not None:
        def _show_config():
            """Display current configuration."""
            from datetime import datetime

            from claude_watch.config.settings import CONFIG_FILE
            from claude_watch.display.analytics import SUBSCRIPTION_PLANS
            from claude_watch.history.storage import HISTORY_FILE

            history = load_history()

            print()
            print(f"{Colors.BOLD}{Colors.CYAN}Current Configuration{Colors.RESET}")
            print()

            # Subscription Plan
            plan_key = config.get("subscription_plan", "pro")
            plan_info = SUBSCRIPTION_PLANS.get(plan_key, SUBSCRIPTION_PLANS["pro"])
            print(
                f"  Subscription:     {Colors.CYAN}{plan_info['name']}{Colors.RESET} "
                f"(${plan_info['cost']:.0f}/mo)"
            )
            print()

            # Admin API
            if config.get("admin_api_key"):
                key = config["admin_api_key"]
                masked = key[:15] + "..." + key[-4:] if len(key) > 20 else "***"
                print(f"  Admin API Key:    {Colors.GREEN}Configured{Colors.RESET} ({masked})")
                use_api = config.get("use_admin_api")
                color = Colors.GREEN if use_api else Colors.YELLOW
                print(f"  Use Admin API:    {color}{'Yes' if use_api else 'No'}{Colors.RESET}")
            else:
                print(f"  Admin API Key:    {Colors.DIM}Not configured{Colors.RESET}")
                print(f"  Data Source:      {Colors.CYAN}Local tracking{Colors.RESET}")

            print()

            # Auto collection
            interval = config.get("collect_interval_hours", 1)
            if config.get("auto_collect"):
                print(f"  Auto Collection:  {Colors.GREEN}Active{Colors.RESET} (every {interval}h)")
            else:
                print(f"  Auto Collection:  {Colors.YELLOW}Inactive{Colors.RESET}")

            # History stats
            print()
            print(f"  History Records:  {len(history)}")
            if history:
                oldest = min(h["timestamp"] for h in history)
                newest = max(h["timestamp"] for h in history)
                oldest_dt = datetime.fromisoformat(oldest.replace("Z", "+00:00")).astimezone()
                newest_dt = datetime.fromisoformat(newest.replace("Z", "+00:00")).astimezone()
                print(
                    f"  Date Range:       {oldest_dt.strftime('%Y-%m-%d')} to "
                    f"{newest_dt.strftime('%Y-%m-%d')}"
                )

            print()
            print(f"  Config File:      {CONFIG_FILE}")
            print(f"  History File:     {HISTORY_FILE}")
            print()

        def _reset_config():
            reset_config()
            print(f"{Colors.GREEN}Configuration reset to defaults.{Colors.RESET}")

        def _set_config(key: str, value: str):
            if key not in DEFAULT_CONFIG:
                print(f"{Colors.RED}Error: Unknown config key '{key}'{Colors.RESET}")
                print(f"Valid keys: {', '.join(sorted(DEFAULT_CONFIG.keys()))}")
                sys.exit(1)

            # Type conversion based on expected type
            expected_type = type(DEFAULT_CONFIG[key])
            if expected_type == bool:
                converted = value.lower() in ("true", "1", "yes", "on")
            elif expected_type == int:
                try:
                    converted = int(value)
                except ValueError:
                    print(f"{Colors.RED}Error: '{key}' must be an integer{Colors.RESET}")
                    sys.exit(1)
            elif expected_type == float:
                try:
                    converted = float(value)
                except ValueError:
                    print(f"{Colors.RED}Error: '{key}' must be a number{Colors.RESET}")
                    sys.exit(1)
            else:
                converted = value if value.lower() != "null" else None

            config[key] = converted
            save_config(config)
            print(f"{Colors.GREEN}Set {key} = {converted}{Colors.RESET}")

        handle_config_command(args.config, _show_config, _reset_config, _set_config, DEFAULT_CONFIG)
        return

    # Handle --dry-run flag
    if args.dry_run:
        print("[DRY-RUN] Using mock data (no API calls)")
        data = get_mock_usage_data()
        if args.json:
            print()
            print(json.dumps(data, indent=2))
        else:
            display_usage(data)
        return

    # Fetch usage data
    start_time = time.time()
    try:
        cache_ttl = args.cache_ttl if args.cache_ttl else CACHE_MAX_AGE
        data, cache_status = fetch_usage_cached(cache_ttl=cache_ttl)
    except Exception as e:
        if not args.quiet:
            print(f"{Colors.RED}Error fetching usage data: {e}{Colors.RESET}")
        sys.exit(1)
    elapsed = time.time() - start_time

    # Record to history (unless --no-record)
    if not args.no_record and data:
        record_usage(data)

    # Handle --analytics flag
    if args.analytics:
        history = load_history()
        if args.json:
            from claude_watch.display.analytics import display_analytics_json
            display_analytics_json(data, history, config)
        else:
            display_usage(data)
            display_analytics(data, history, config)
        return

    # Handle --json output
    if args.json:
        print(json.dumps(data, indent=2))
        return

    # Default: show usage
    if not args.quiet:
        display_usage(data)


__all__ = [
    "create_parser",
    "main",
    "print_version",
    "handle_config_command",
]
