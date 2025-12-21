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


__all__ = [
    "create_parser",
    "print_version",
    "handle_config_command",
]
