"""Setup and installation utilities.

Modules:
    wizard: Interactive setup wizard
    completion: Shell completion installation (TODO)
    systemd: Systemd timer configuration (TODO)
"""

from claude_watch.setup.wizard import (
    SUBSCRIPTION_PLAN_DETAILS,
    prompt_input,
    prompt_yes_no,
    run_setup,
)

__all__ = [
    "prompt_yes_no",
    "prompt_input",
    "run_setup",
    "SUBSCRIPTION_PLAN_DETAILS",
]
