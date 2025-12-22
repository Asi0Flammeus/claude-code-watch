"""Interactive setup wizard for claude-watch.

Provides the interactive setup experience for configuring:
- Admin API key
- Automatic data collection
- Subscription plan
- Shell completion
"""

from claude_watch.config.settings import (
    CONFIG_FILE,
    load_config,
    save_config,
)
from claude_watch.display.colors import Colors

# Subscription plan details for display
SUBSCRIPTION_PLAN_DETAILS = {
    "pro": {
        "name": "Pro",
        "cost": 20.00,
    },
    "max_5x": {
        "name": "Max 5x",
        "cost": 100.00,
    },
    "max_20x": {
        "name": "Max 20x",
        "cost": 200.00,
    },
}


def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt user for yes/no answer.

    Args:
        question: The question to ask.
        default: Default value if user presses Enter.

    Returns:
        True for yes, False for no.
    """
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
    """Prompt user for text input.

    Args:
        question: The question to ask.
        default: Default value shown in brackets.

    Returns:
        User input or default value.
    """
    suffix = f" [{default}] " if default else " "
    response = input(f"{question}{suffix}").strip()
    return response if response else default


def run_setup(
    setup_systemd_timer_func=None,
    disable_systemd_timer_func=None,
    setup_shell_completion_func=None,
    detect_shell_func=None,
    service_name: str = "claude-watch-record",
) -> None:
    """Run interactive setup wizard.

    Args:
        setup_systemd_timer_func: Function to set up systemd timer (optional).
        disable_systemd_timer_func: Function to disable systemd timer (optional).
        setup_shell_completion_func: Function to set up shell completion (optional).
        detect_shell_func: Function to detect user's shell (optional).
        service_name: Name of the systemd service.
    """
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

        if setup_systemd_timer_func and setup_systemd_timer_func(interval_hours):
            config["auto_collect"] = True
            config["collect_interval_hours"] = interval_hours
            print(f"{Colors.GREEN}✓ Automatic collection enabled{Colors.RESET}")
            print()
            print(f"{Colors.DIM}Manage with:{Colors.RESET}")
            print(f"  systemctl --user status {service_name}.timer")
            print(f"  systemctl --user stop {service_name}.timer")
        else:
            config["auto_collect"] = False
            if not setup_systemd_timer_func:
                print(f"{Colors.YELLOW}Automatic collection not available (function not provided){Colors.RESET}")
    else:
        config["auto_collect"] = False
        # Disable existing timer if any
        if disable_systemd_timer_func:
            disable_systemd_timer_func()

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
    plan_info = SUBSCRIPTION_PLAN_DETAILS[config["subscription_plan"]]
    print(
        f"{Colors.GREEN}✓ Subscription set to {plan_info['name']} (${plan_info['cost']:.0f}/mo){Colors.RESET}"
    )

    print()

    # Step 4: Webhook Notifications
    print(f"{Colors.BOLD}Step 4: Webhook Notifications (Optional){Colors.RESET}")
    print()
    print("Get notified when usage exceeds thresholds via:")
    print(f"  {Colors.DIM}• Slack incoming webhooks{Colors.RESET}")
    print(f"  {Colors.DIM}• Discord webhooks{Colors.RESET}")
    print(f"  {Colors.DIM}• Generic HTTP endpoints{Colors.RESET}")
    print()

    setup_webhook = prompt_yes_no("Configure webhook notifications?", default=False)

    if setup_webhook:
        webhook_url = prompt_input("Webhook URL (Slack/Discord/HTTP):")
        if webhook_url:
            # Auto-detect type for display
            from claude_watch.webhook import detect_webhook_type

            webhook_type = detect_webhook_type(webhook_url)
            type_display = {"slack": "Slack", "discord": "Discord", "generic": "HTTP"}

            config["webhook_url"] = webhook_url
            print(f"{Colors.GREEN}✓ {type_display[webhook_type]} webhook configured{Colors.RESET}")

            # Only offer secret for generic webhooks
            if webhook_type == "generic":
                print()
                print("For generic HTTP webhooks, you can add HMAC signing for security.")
                add_secret = prompt_yes_no("Add webhook secret for HMAC signing?", default=False)
                if add_secret:
                    webhook_secret = prompt_input("Webhook secret:")
                    if webhook_secret:
                        config["webhook_secret"] = webhook_secret
                        print(
                            f"{Colors.GREEN}✓ Webhook secret saved (HMAC-SHA256 signing enabled){Colors.RESET}"
                        )

            # Configure thresholds
            print()
            thresholds = prompt_input("Notification thresholds (%)", default="80,90,95")
            config["webhook_thresholds"] = thresholds
            print(f"{Colors.GREEN}✓ Thresholds: {thresholds}{Colors.RESET}")
        else:
            print(f"{Colors.DIM}Skipping webhook setup.{Colors.RESET}")
    else:
        print(f"{Colors.DIM}Skipping webhook setup.{Colors.RESET}")

    print()

    # Step 5: Shell Completion
    print(f"{Colors.BOLD}Step 5: Shell Tab Completion (Optional){Colors.RESET}")
    print()

    if detect_shell_func:
        shell = detect_shell_func()
        print(f"Detected shell: {Colors.CYAN}{shell}{Colors.RESET}")
    else:
        print(f"Shell detection: {Colors.DIM}not available{Colors.RESET}")

    print()
    print("Tab completion allows you to press TAB to auto-complete options like:")
    print(f"  {Colors.DIM}claude-watch --<TAB>{Colors.RESET}  → shows all available flags")
    print()

    setup_completion = prompt_yes_no("Install shell tab completion?", default=True)

    if setup_completion:
        if setup_shell_completion_func and setup_shell_completion_func():
            config["shell_completion_installed"] = True
        else:
            config["shell_completion_installed"] = False
            if not setup_shell_completion_func:
                print(f"{Colors.YELLOW}Shell completion not available (function not provided){Colors.RESET}")
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


__all__ = [
    "prompt_yes_no",
    "prompt_input",
    "run_setup",
    "SUBSCRIPTION_PLAN_DETAILS",
]
