"""Setup and installation utilities.

Modules:
    wizard: Interactive setup wizard
    completion: Shell completion installation
    systemd: Systemd timer configuration (TODO)
"""

from claude_watch.setup.completion import (
    SHELL_CONFIGS,
    detect_shell,
    get_completion_source_path,
    setup_shell_completion,
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
]
