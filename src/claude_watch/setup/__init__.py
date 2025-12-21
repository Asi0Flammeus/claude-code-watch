"""Setup and installation utilities.

Modules:
    wizard: Interactive setup wizard
    completion: Shell completion installation
    systemd: Systemd timer configuration
"""

from claude_watch.setup.completion import (
    SHELL_CONFIGS,
    detect_shell,
    get_completion_source_path,
    setup_shell_completion,
)
from claude_watch.setup.systemd import (
    SERVICE_NAME,
    SYSTEMD_USER_DIR,
    check_timer_status,
    disable_systemd_timer,
    get_script_path,
    setup_systemd_timer,
)
from claude_watch.setup.wizard import (
    SUBSCRIPTION_PLAN_DETAILS,
    prompt_input,
    prompt_yes_no,
    run_setup,
)

__all__ = [
    # Wizard
    "prompt_yes_no",
    "prompt_input",
    "run_setup",
    "SUBSCRIPTION_PLAN_DETAILS",
    # Completion
    "detect_shell",
    "get_completion_source_path",
    "setup_shell_completion",
    "SHELL_CONFIGS",
    # Systemd
    "SYSTEMD_USER_DIR",
    "SERVICE_NAME",
    "get_script_path",
    "setup_systemd_timer",
    "disable_systemd_timer",
    "check_timer_status",
]
