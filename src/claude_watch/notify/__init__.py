"""Desktop notification functionality for claude-watch."""

from claude_watch.notify.notifier import (
    NOTIFY_STATE_FILE,
    check_and_notify,
    load_notify_state,
    run_notify_daemon,
    save_notify_state,
    send_notification,
)

__all__ = [
    "NOTIFY_STATE_FILE",
    "check_and_notify",
    "load_notify_state",
    "run_notify_daemon",
    "save_notify_state",
    "send_notification",
]
