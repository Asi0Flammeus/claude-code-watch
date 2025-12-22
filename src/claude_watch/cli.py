"""Command-line interface for claude-watch.

This module provides the main entry point and argument parsing for the
claude-watch CLI tool.
"""

import argparse
import platform
import sys

from claude_watch._version import __version__
from claude_watch.display.colors import Colors
from claude_watch.errors import ClaudeWatchError, format_error_for_user, get_exit_code


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
  claude-watch --current    Show only current session (compact)
  claude-watch --watch --current  Live compact monitoring
  claude-watch --analytics  Show detailed analytics and trends
  claude-watch --forecast   Show usage forecast and recommendations
  claude-watch --setup      Run interactive setup wizard
  claude-watch --config     Show current configuration
  claude-watch --json       Output raw JSON data
  claude-watch --export csv Export history to CSV
  claude-watch --export json -d 7  Export last 7 days as JSON
  claude-watch --notify     Send notification if usage high
  claude-watch --notify-daemon  Run notification daemon
  claude-watch --webhook URL    Send webhook on threshold breach
  claude-watch --install-hook   Install Claude Code hook
  claude-watch --prompt     Output for shell prompt
  claude-watch --tmux       Output for tmux status bar
  claude-watch --watch      Live updating display
  claude-watch --report weekly  Generate weekly HTML report
  claude-watch --report monthly --open  Generate and open monthly report
  claude-watch --metrics-server 9100  Start Prometheus metrics server
  claude-watch --update     Check for and install updates
  claude-watch --audit      Enable audit logging for operations
  claude-watch --show-audit Show recent audit log entries
  claude-watch --health-check Run system diagnostics
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
    parser.add_argument(
        "--prompt-color",
        action="store_true",
        help="Include ANSI color codes in prompt output (for color-capable shells).",
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
        "--current",
        action="store_true",
        help="Show only current session (compact view). Use with --watch for minimal monitoring.",
    )

    # Export arguments
    parser.add_argument(
        "--export",
        choices=["csv", "json", "influx"],
        metavar="FORMAT",
        help="Export history data. FORMAT: csv, json, or influx (InfluxDB line protocol).",
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
        "--influxdb-url",
        metavar="URL",
        help="Push data directly to InfluxDB (e.g., http://localhost:8086).",
    )
    parser.add_argument(
        "--influxdb-token",
        metavar="TOKEN",
        help="InfluxDB API token for authentication.",
    )
    parser.add_argument(
        "--influxdb-org",
        metavar="ORG",
        help="InfluxDB organization name.",
    )
    parser.add_argument(
        "--influxdb-bucket",
        metavar="BUCKET",
        help="InfluxDB bucket name.",
    )

    # Forecast arguments
    parser.add_argument(
        "--forecast",
        "-f",
        action="store_true",
        help="Show usage forecast with projections and recommendations.",
    )

    # Notification arguments
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

    # Webhook arguments
    parser.add_argument(
        "--webhook",
        metavar="URL",
        help="Send webhook notification on threshold breach (Slack, Discord, or generic HTTP).",
    )
    parser.add_argument(
        "--webhook-secret",
        metavar="SECRET",
        help="HMAC secret for signing webhook payloads (generic webhooks only).",
    )

    # Hook arguments
    parser.add_argument(
        "--generate-hook",
        action="store_true",
        help="Generate Claude Code hook script for usage monitoring.",
    )
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help="Generate and install hook to ~/.claude/settings.json.",
    )

    # Report arguments
    parser.add_argument(
        "--report",
        "-r",
        choices=["weekly", "monthly"],
        metavar="PERIOD",
        help="Generate HTML usage report. PERIOD: weekly or monthly.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated report in default browser.",
    )

    # Metrics arguments
    parser.add_argument(
        "--metrics-server",
        type=int,
        metavar="PORT",
        help="Start Prometheus metrics server on specified port.",
    )
    parser.add_argument(
        "--metrics-interval",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Metrics fetch interval in seconds (default: 60).",
    )

    # Network arguments
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        metavar="SECONDS",
        help="Request timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--proxy",
        metavar="URL",
        help="Proxy URL (overrides HTTP_PROXY/HTTPS_PROXY env vars).",
    )

    # Security arguments
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Enable audit logging for security-relevant operations.",
    )
    parser.add_argument(
        "--audit-log",
        metavar="PATH",
        help="Custom path for audit log file (default: ~/.claude/audit/audit.log).",
    )
    parser.add_argument(
        "--show-audit",
        nargs="?",
        const=50,
        type=int,
        metavar="N",
        help="Show last N audit log entries (default: 50).",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run system health checks (credentials, API, config).",
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

    # Handle audit logging flags
    if args.audit or args.audit_log:
        from pathlib import Path

        from claude_watch.config.audit import enable_audit_logging

        log_path = Path(args.audit_log) if args.audit_log else None
        enable_audit_logging(log_path)

    # Handle --show-audit flag
    if args.show_audit is not None:
        from pathlib import Path

        # Temporarily enable to read, even if --audit wasn't passed
        from claude_watch.config.audit import (
            AUDIT_LOG_FILE,
        )

        log_path = Path(args.audit_log) if args.audit_log else AUDIT_LOG_FILE

        if not log_path.exists():
            print(f"{Colors.YELLOW}No audit log found at {log_path}{Colors.RESET}")
            print("Use --audit flag to enable audit logging.")
            sys.exit(0)

        entries = []
        try:
            import json as json_module

            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json_module.loads(line))
                        except json_module.JSONDecodeError:
                            continue
        except OSError as e:
            print(f"{Colors.RED}Error reading audit log: {e}{Colors.RESET}")
            sys.exit(1)

        # Get last N entries
        limit = args.show_audit
        entries = entries[-limit:][::-1]

        if not entries:
            print(f"{Colors.DIM}No audit log entries found.{Colors.RESET}")
            sys.exit(0)

        print()
        print(f"{Colors.BOLD}{Colors.CYAN}Audit Log{Colors.RESET} ({len(entries)} entries)")
        print(f"{Colors.DIM}{'─' * 70}{Colors.RESET}")

        for entry in entries:
            timestamp = entry.get("timestamp", "")[:19]  # Trim to seconds
            event = entry.get("event", "unknown")
            message = entry.get("message", "")
            success = entry.get("success", True)

            # Color code by event type and success
            if not success:
                color = Colors.RED
                icon = "✗"
            elif event.startswith("credential") or event.startswith("permission"):
                color = Colors.YELLOW
                icon = "⚡"
            elif event.startswith("api"):
                color = Colors.CYAN
                icon = "→"
            elif event.startswith("config"):
                color = Colors.MAGENTA
                icon = "⚙"
            elif event.startswith("session"):
                color = Colors.GREEN
                icon = "●"
            else:
                color = Colors.WHITE
                icon = "•"

            print(f"{Colors.DIM}{timestamp}{Colors.RESET} {color}{icon} {event}{Colors.RESET}")
            if message:
                print(f"  {message}")

            # Show details if present
            details = entry.get("details", {})
            if details and args.verbose:
                for k, v in details.items():
                    print(f"    {Colors.DIM}{k}: {v}{Colors.RESET}")

        print()
        print(f"{Colors.DIM}Log file: {log_path}{Colors.RESET}")
        sys.exit(0)

    # Handle --health-check flag
    if args.health_check:
        from claude_watch.health import run_health_check

        exit_code = run_health_check(
            verbose=args.verbose,
            timeout=args.timeout,
        )
        sys.exit(exit_code)

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
        elif args.prompt:
            from claude_watch.display.prompt import format_prompt
            print(format_prompt(data, args.prompt, color=args.prompt_color))
        elif args.tmux:
            from claude_watch.display.tmux import format_tmux
            print(format_tmux(data))
        elif args.current:
            from claude_watch.display.watch import display_current_compact
            print()
            display_current_compact(data)
            print()
        else:
            display_usage(data)
        return

    # Handle --prompt with cached-first strategy (fast for shell prompts)
    if args.prompt:
        from claude_watch.api.cache import get_stale_cache, load_cache
        from claude_watch.display.prompt import format_prompt

        # Try cache first (prefer speed over freshness for prompts)
        data = load_cache()
        if data is None:
            data = get_stale_cache()
        if data is None:
            # No cache at all, fetch silently
            data = fetch_usage_cached(silent=True)
        if data is None:
            # Still nothing, show empty prompt with error exit code
            print("")
            sys.exit(3)

        print(format_prompt(data, args.prompt, color=args.prompt_color))

        # Set exit code based on usage level
        five_hour = data.get("five_hour") or {}
        utilization = five_hour.get("utilization", 0)
        if utilization >= 90:
            sys.exit(2)  # Critical
        elif utilization >= 75:
            sys.exit(1)  # Warning
        sys.exit(0)  # OK

    # Handle --tmux with cached-first strategy (fast for tmux status bar)
    if args.tmux:
        from claude_watch.api.cache import get_stale_cache, load_cache
        from claude_watch.display.tmux import format_tmux

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
        from claude_watch.display.watch import run_watch_mode

        def fetch_for_watch():
            return fetch_usage_cached(cache_ttl=0)  # Always fetch fresh data

        run_watch_mode(
            fetch_func=fetch_for_watch,
            display_func=display_usage,
            interval=args.watch,
            analytics_mode=args.analytics,
            history_func=load_history if args.analytics else None,
            config=config if args.analytics else None,
            current_only=args.current,
        )
        return

    # Handle standalone --current (without --watch)
    if args.current:
        from claude_watch.display.watch import display_current_compact

        try:
            data = fetch_usage_cached(
                cache_ttl=args.cache_ttl if args.cache_ttl else CACHE_MAX_AGE,
                timeout=args.timeout,
                proxy=args.proxy,
            )
        except Exception as e:
            if not args.quiet:
                error_msg = format_error_for_user(e, verbose=args.verbose)
                print(f"{Colors.RED}{error_msg}{Colors.RESET}")
                if isinstance(e, ClaudeWatchError) and e.get_suggestion():
                    print(f"{Colors.YELLOW}Suggestion: {e.get_suggestion()}{Colors.RESET}")
            sys.exit(get_exit_code(e))

        if not args.no_record and data:
            record_usage(data)

        if not args.quiet:
            print()
            display_current_compact(data)
            print()
        return

    # Handle --influxdb-url flag (push to InfluxDB)
    if args.influxdb_url:
        from claude_watch.export.exporter import export_influx, push_to_influxdb
        from claude_watch.history.storage import load_history as load_history_func

        history = load_history_func()
        if not history:
            print(f"{Colors.YELLOW}No history data to push{Colors.RESET}")
            sys.exit(0)

        influx_data = export_influx(history, args.days)
        if not influx_data:
            print(f"{Colors.YELLOW}No data to push after filtering{Colors.RESET}")
            sys.exit(0)

        if not args.quiet:
            print(f"Pushing {len(history)} records to InfluxDB...")

        try:
            push_to_influxdb(
                url=args.influxdb_url,
                data=influx_data,
                token=args.influxdb_token,
                org=args.influxdb_org,
                bucket=args.influxdb_bucket,
                timeout=args.timeout,
            )
            if not args.quiet:
                print(f"{Colors.GREEN}Successfully pushed to InfluxDB{Colors.RESET}")
            sys.exit(0)
        except Exception as e:
            print(f"{Colors.RED}InfluxDB push failed: {e}{Colors.RESET}")
            sys.exit(1)

    # Handle --export flag
    if args.export:
        from claude_watch.export import run_export

        exit_code = run_export(args.export, args.days, args.output, args.excel)
        sys.exit(exit_code)

    # Handle --generate-hook and --install-hook flags
    if args.generate_hook or args.install_hook:
        from claude_watch.hooks import run_generate_hook

        exit_code = run_generate_hook(install=args.install_hook)
        sys.exit(exit_code)

    # Handle --notify-daemon flag
    if args.notify_daemon:
        from claude_watch.notify import run_notify_daemon

        thresholds = [int(t.strip()) for t in args.notify_at.split(",")]

        def fetch_for_notify():
            return fetch_usage_cached(cache_ttl=0, silent=True)

        run_notify_daemon(thresholds, fetch_func=fetch_for_notify)
        return

    # Handle --metrics-server flag
    if args.metrics_server:
        from claude_watch.metrics import run_metrics_server

        def fetch_for_metrics():
            return fetch_usage_cached(cache_ttl=0, silent=True)

        run_metrics_server(
            port=args.metrics_server,
            fetch_func=fetch_for_metrics,
            fetch_interval=args.metrics_interval,
            verbose=not args.quiet,
        )
        return

    # Fetch usage data
    start_time = time.time()
    try:
        cache_ttl = args.cache_ttl if args.cache_ttl else CACHE_MAX_AGE
        data = fetch_usage_cached(
            cache_ttl=cache_ttl,
            timeout=args.timeout,
            proxy=args.proxy,
        )
    except Exception as e:
        if not args.quiet:
            error_msg = format_error_for_user(e, verbose=args.verbose)
            print(f"{Colors.RED}{error_msg}{Colors.RESET}")
            if isinstance(e, ClaudeWatchError) and e.get_suggestion():
                print(f"{Colors.YELLOW}Suggestion: {e.get_suggestion()}{Colors.RESET}")
        sys.exit(get_exit_code(e))
    _ = time.time() - start_time  # Track elapsed time for verbose mode

    # Record to history (unless --no-record)
    if not args.no_record and data:
        record_usage(data)

    # Handle --notify flag (single check)
    if args.notify:
        from claude_watch.notify import check_and_notify

        thresholds = [int(t.strip()) for t in args.notify_at.split(",")]
        exit_code = check_and_notify(data, thresholds, verbose=not args.quiet)
        sys.exit(exit_code)

    # Handle --webhook flag
    if args.webhook:
        from claude_watch.webhook import WebhookError, send_webhook

        thresholds = [int(t.strip()) for t in args.notify_at.split(",")]
        five_hour = data.get("five_hour", {}).get("utilization", 0)
        seven_day = data.get("seven_day", {}).get("utilization", 0)
        current_usage = max(five_hour, seven_day)

        # Find highest breached threshold
        breached = [t for t in sorted(thresholds, reverse=True) if current_usage >= t]

        if not breached:
            if not args.quiet:
                print(
                    f"{Colors.GREEN}Usage at {current_usage:.0f}% "
                    f"(below all thresholds){Colors.RESET}"
                )
            sys.exit(0)

        highest_threshold = breached[0]

        if not args.quiet:
            print(
                f"{Colors.YELLOW}Threshold {highest_threshold}% breached "
                f"(usage: {current_usage:.0f}%){Colors.RESET}"
            )
            print(f"Sending webhook to {args.webhook[:50]}...")

        try:
            send_webhook(
                url=args.webhook,
                data=data,
                threshold=highest_threshold,
                secret=args.webhook_secret,
                timeout=args.timeout,
            )
            if not args.quiet:
                print(f"{Colors.GREEN}Webhook sent successfully{Colors.RESET}")
            sys.exit(0)
        except WebhookError as e:
            print(f"{Colors.RED}Webhook failed: {e}{Colors.RESET}")
            sys.exit(1)

    # Handle --forecast flag
    if args.forecast:
        from claude_watch.forecast import display_forecast, display_forecast_json

        history = load_history()
        if args.json:
            display_forecast_json(data, history, config)
        else:
            display_usage(data)
            display_forecast(data, history, config)
        return

    # Handle --report flag
    if args.report:
        from claude_watch.reports import run_report

        exit_code = run_report(
            period=args.report,
            data=data,
            config=config,
            open_browser=args.open,
        )
        sys.exit(exit_code)

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
