"""Webhook sender with support for Slack, Discord, and generic HTTP webhooks."""

import hashlib
import hmac
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Literal, Optional

WebhookType = Literal["slack", "discord", "generic"]


class WebhookError(Exception):
    """Exception raised when webhook sending fails."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def detect_webhook_type(url: str) -> WebhookType:
    """Auto-detect webhook type from URL.

    Args:
        url: Webhook URL.

    Returns:
        Detected webhook type: 'slack', 'discord', or 'generic'.
    """
    url_lower = url.lower()
    if "hooks.slack.com" in url_lower:
        return "slack"
    if "discord.com/api/webhooks" in url_lower or "discordapp.com/api/webhooks" in url_lower:
        return "discord"
    return "generic"


def format_generic_payload(
    data: dict,
    threshold: int,
    event: str = "threshold_breach",
) -> dict[str, Any]:
    """Format payload for generic HTTP webhooks.

    Args:
        data: Current usage data.
        threshold: Threshold that was breached.
        event: Event type identifier.

    Returns:
        Generic JSON payload.
    """
    five_hour = data.get("five_hour") or {}
    seven_day = data.get("seven_day") or {}

    return {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threshold_breached": threshold,
        "usage": {
            "session": {
                "utilization": five_hour.get("utilization", 0),
                "resets_at": five_hour.get("resets_at"),
            },
            "weekly": {
                "utilization": seven_day.get("utilization", 0),
                "resets_at": seven_day.get("resets_at"),
            },
        },
        "source": "claude-watch",
    }


def format_slack_payload(
    data: dict,
    threshold: int,
) -> dict[str, Any]:
    """Format payload for Slack incoming webhooks.

    Args:
        data: Current usage data.
        threshold: Threshold that was breached.

    Returns:
        Slack Block Kit message payload.
    """
    five_hour = data.get("five_hour") or {}
    seven_day = data.get("seven_day") or {}

    session_pct = five_hour.get("utilization", 0)
    weekly_pct = seven_day.get("utilization", 0)

    # Determine severity
    if threshold >= 95:
        color = "#FF0000"
        emoji = ":rotating_light:"
        severity = "CRITICAL"
    elif threshold >= 90:
        color = "#FF6600"
        emoji = ":warning:"
        severity = "HIGH"
    else:
        color = "#FFCC00"
        emoji = ":bell:"
        severity = "WARNING"

    return {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} Claude Usage {severity}: {threshold}% threshold breached",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Session Usage:*\n{session_pct:.1f}%",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Weekly Usage:*\n{weekly_pct:.1f}%",
                            },
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Sent by claude-watch at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                            },
                        ],
                    },
                ],
            },
        ],
    }


def format_discord_payload(
    data: dict,
    threshold: int,
) -> dict[str, Any]:
    """Format payload for Discord webhooks.

    Args:
        data: Current usage data.
        threshold: Threshold that was breached.

    Returns:
        Discord embed message payload.
    """
    five_hour = data.get("five_hour") or {}
    seven_day = data.get("seven_day") or {}

    session_pct = five_hour.get("utilization", 0)
    weekly_pct = seven_day.get("utilization", 0)

    # Determine severity and color
    if threshold >= 95:
        color = 0xFF0000  # Red
        severity = "CRITICAL"
    elif threshold >= 90:
        color = 0xFF6600  # Orange
        severity = "HIGH"
    else:
        color = 0xFFCC00  # Yellow
        severity = "WARNING"

    return {
        "embeds": [
            {
                "title": f"Claude Usage {severity}",
                "description": f"**{threshold}%** threshold breached",
                "color": color,
                "fields": [
                    {
                        "name": "Session Usage",
                        "value": f"{session_pct:.1f}%",
                        "inline": True,
                    },
                    {
                        "name": "Weekly Usage",
                        "value": f"{weekly_pct:.1f}%",
                        "inline": True,
                    },
                ],
                "footer": {
                    "text": "claude-watch",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ],
    }


def compute_hmac_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload.

    Args:
        payload: JSON payload as bytes.
        secret: Webhook secret key.

    Returns:
        HMAC signature as hex string.
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def send_webhook(
    url: str,
    data: dict,
    threshold: int,
    webhook_type: Optional[WebhookType] = None,
    secret: Optional[str] = None,
    timeout: int = 10,
) -> bool:
    """Send webhook notification.

    Args:
        url: Webhook URL.
        data: Current usage data.
        threshold: Threshold that was breached.
        webhook_type: Override auto-detected webhook type.
        secret: Optional secret for HMAC signing (generic webhooks only).
        timeout: Request timeout in seconds.

    Returns:
        True if webhook was sent successfully.

    Raises:
        WebhookError: If the webhook request fails.
    """
    if webhook_type is None:
        webhook_type = detect_webhook_type(url)

    # Format payload based on webhook type
    if webhook_type == "slack":
        payload = format_slack_payload(data, threshold)
    elif webhook_type == "discord":
        payload = format_discord_payload(data, threshold)
    else:
        payload = format_generic_payload(data, threshold)

    payload_bytes = json.dumps(payload).encode("utf-8")

    # Build headers
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "claude-watch",
    }

    # Add HMAC signature for generic webhooks if secret provided
    if secret and webhook_type == "generic":
        signature = compute_hmac_signature(payload_bytes, secret)
        headers["X-Claude-Watch-Signature"] = f"sha256={signature}"
        headers["X-Claude-Watch-Timestamp"] = str(int(time.time()))

    # Send request
    req = urllib.request.Request(
        url,
        data=payload_bytes,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            if status < 200 or status >= 300:
                raise WebhookError(f"Webhook returned status {status}", status)
            return True
    except urllib.error.HTTPError as e:
        raise WebhookError(f"Webhook request failed: {e.code} {e.reason}", e.code) from e
    except urllib.error.URLError as e:
        raise WebhookError(f"Webhook connection failed: {e.reason}") from e
    except Exception as e:
        raise WebhookError(f"Webhook error: {e}") from e
