"""Webhook notification functionality for claude-watch."""

from claude_watch.webhook.sender import (
    WebhookError,
    detect_webhook_type,
    format_discord_payload,
    format_generic_payload,
    format_slack_payload,
    send_webhook,
)

__all__ = [
    "WebhookError",
    "detect_webhook_type",
    "format_discord_payload",
    "format_generic_payload",
    "format_slack_payload",
    "send_webhook",
]
