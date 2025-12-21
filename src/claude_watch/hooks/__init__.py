"""Claude Code hook generation for usage monitoring."""

from claude_watch.hooks.generator import (
    CLAUDE_SETTINGS_PATH,
    HOOK_SCRIPT_PATH,
    HOOK_SCRIPT_TEMPLATE,
    generate_hook_script,
    install_hook,
    load_claude_settings,
    run_generate_hook,
    save_claude_settings,
    write_hook_script,
)

__all__ = [
    "CLAUDE_SETTINGS_PATH",
    "HOOK_SCRIPT_PATH",
    "HOOK_SCRIPT_TEMPLATE",
    "generate_hook_script",
    "install_hook",
    "load_claude_settings",
    "run_generate_hook",
    "save_claude_settings",
    "write_hook_script",
]
