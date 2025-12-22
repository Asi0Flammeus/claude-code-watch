"""Audit logging for security-relevant operations.

Provides structured logging for credential access, configuration changes,
and API operations with rotation and retention policies.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Audit log configuration
AUDIT_DIR = Path.home() / ".claude" / "audit"
AUDIT_LOG_FILE = AUDIT_DIR / "audit.log"
AUDIT_MAX_SIZE_MB = 10
AUDIT_MAX_FILES = 5

# Audit event types
class AuditEvent:
    """Audit event type constants."""

    # Credential events
    CREDENTIAL_READ = "credential.read"
    CREDENTIAL_VALIDATE = "credential.validate"
    CREDENTIAL_VALIDATE_FAILED = "credential.validate.failed"

    # Configuration events
    CONFIG_READ = "config.read"
    CONFIG_WRITE = "config.write"
    CONFIG_RESET = "config.reset"

    # API events
    API_REQUEST = "api.request"
    API_SUCCESS = "api.success"
    API_ERROR = "api.error"
    API_RETRY = "api.retry"

    # Permission events
    PERMISSION_CHECK = "permission.check"
    PERMISSION_FIX = "permission.fix"
    PERMISSION_DENIED = "permission.denied"

    # Session events
    SESSION_START = "session.start"
    SESSION_END = "session.end"

    # Notification events
    NOTIFICATION_SENT = "notification.sent"
    HOOK_INSTALLED = "hook.installed"


# Global audit state
_audit_enabled = False
_audit_log_path: Path | None = None


def enable_audit_logging(log_path: Path | None = None) -> None:
    """Enable audit logging.

    Args:
        log_path: Optional custom path for audit log. Defaults to ~/.claude/audit/audit.log.
    """
    global _audit_enabled, _audit_log_path

    _audit_enabled = True
    _audit_log_path = log_path or AUDIT_LOG_FILE

    # Create audit directory with secure permissions
    audit_dir = _audit_log_path.parent
    if not audit_dir.exists():
        audit_dir.mkdir(parents=True, mode=0o700)

    # Log that audit logging was enabled
    log_audit_event(
        event_type=AuditEvent.SESSION_START,
        message="Audit logging enabled",
        details={"log_path": str(_audit_log_path)},
    )


def disable_audit_logging() -> None:
    """Disable audit logging."""
    global _audit_enabled

    if _audit_enabled:
        log_audit_event(
            event_type=AuditEvent.SESSION_END,
            message="Audit logging disabled",
        )
    _audit_enabled = False


def is_audit_enabled() -> bool:
    """Check if audit logging is enabled.

    Returns:
        True if audit logging is enabled.
    """
    return _audit_enabled


def _rotate_logs() -> None:
    """Rotate audit logs if they exceed size limit."""
    if _audit_log_path is None or not _audit_log_path.exists():
        return

    try:
        size_mb = _audit_log_path.stat().st_size / (1024 * 1024)
        if size_mb < AUDIT_MAX_SIZE_MB:
            return

        # Rotate existing logs
        for i in range(AUDIT_MAX_FILES - 1, 0, -1):
            old_path = _audit_log_path.with_suffix(f".log.{i}")
            new_path = _audit_log_path.with_suffix(f".log.{i + 1}")
            if old_path.exists():
                if i + 1 >= AUDIT_MAX_FILES:
                    old_path.unlink()  # Delete oldest
                else:
                    old_path.rename(new_path)

        # Move current log to .1
        _audit_log_path.rename(_audit_log_path.with_suffix(".log.1"))

    except OSError:
        pass  # Best effort rotation


def log_audit_event(
    event_type: str,
    message: str,
    details: dict | None = None,
    success: bool = True,
) -> None:
    """Log an audit event.

    Args:
        event_type: Type of audit event (use AuditEvent constants).
        message: Human-readable description of the event.
        details: Optional additional structured data.
        success: Whether the operation was successful.
    """
    if not _audit_enabled or _audit_log_path is None:
        return

    # Build audit record
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "message": message,
        "success": success,
        "pid": os.getpid(),
    }

    if details:
        # Sanitize details to remove sensitive data
        sanitized = _sanitize_details(details)
        record["details"] = sanitized

    # Rotate if needed
    _rotate_logs()

    # Write log entry
    try:
        with open(_audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        # Ensure secure permissions on log file
        os.chmod(_audit_log_path, 0o600)
    except OSError:
        pass  # Best effort logging


def _sanitize_details(details: dict) -> dict:
    """Sanitize details dict to remove sensitive information.

    Args:
        details: Raw details dictionary.

    Returns:
        Sanitized details with tokens/keys masked.
    """
    sensitive_keys = {
        "token",
        "key",
        "password",
        "secret",
        "api_key",
        "access_token",
        "oauth_token",
    }

    sanitized = {}
    for key, value in details.items():
        lower_key = key.lower()
        if any(s in lower_key for s in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                sanitized[key] = f"{value[:4]}...{value[-4:]}"
            else:
                sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_details(value)
        else:
            sanitized[key] = value

    return sanitized


def log_credential_access(
    credential_type: str,
    path: Path | None = None,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Log credential access event.

    Args:
        credential_type: Type of credential (e.g., 'oauth', 'api_key').
        path: Path to credential file if applicable.
        success: Whether access was successful.
        error: Error message if access failed.
    """
    event = AuditEvent.CREDENTIAL_READ if success else AuditEvent.CREDENTIAL_VALIDATE_FAILED
    details = {"credential_type": credential_type}
    if path:
        details["path"] = str(path)
    if error:
        details["error"] = error

    log_audit_event(
        event_type=event,
        message=f"Credential access: {credential_type}",
        details=details,
        success=success,
    )


def log_api_request(
    endpoint: str,
    method: str = "GET",
    success: bool = True,
    status_code: int | None = None,
    error: str | None = None,
    retry_count: int = 0,
) -> None:
    """Log API request event.

    Args:
        endpoint: API endpoint (sanitized, no tokens).
        method: HTTP method.
        success: Whether request was successful.
        status_code: HTTP status code if available.
        error: Error message if request failed.
        retry_count: Number of retries performed.
    """
    if retry_count > 0:
        event = AuditEvent.API_RETRY
    elif success:
        event = AuditEvent.API_SUCCESS
    else:
        event = AuditEvent.API_ERROR

    details = {
        "endpoint": endpoint,
        "method": method,
    }
    if status_code:
        details["status_code"] = status_code
    if error:
        details["error"] = error
    if retry_count > 0:
        details["retry_count"] = retry_count

    log_audit_event(
        event_type=event,
        message=f"API {method} {endpoint}",
        details=details,
        success=success,
    )


def log_config_change(
    action: str,
    key: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    """Log configuration change event.

    Args:
        action: Type of change ('read', 'write', 'reset').
        key: Configuration key if applicable.
        old_value: Previous value (will be sanitized).
        new_value: New value (will be sanitized).
    """
    event_map = {
        "read": AuditEvent.CONFIG_READ,
        "write": AuditEvent.CONFIG_WRITE,
        "reset": AuditEvent.CONFIG_RESET,
    }
    event = event_map.get(action, AuditEvent.CONFIG_WRITE)

    details = {"action": action}
    if key:
        details["key"] = key
    if old_value is not None:
        details["old_value"] = old_value
    if new_value is not None:
        details["new_value"] = new_value

    log_audit_event(
        event_type=event,
        message=f"Config {action}" + (f": {key}" if key else ""),
        details=details,
    )


def log_permission_event(
    path: Path,
    action: str,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Log permission-related event.

    Args:
        path: File path affected.
        action: Action taken ('check', 'fix', 'denied').
        success: Whether the action was successful.
        error: Error message if action failed.
    """
    event_map = {
        "check": AuditEvent.PERMISSION_CHECK,
        "fix": AuditEvent.PERMISSION_FIX,
        "denied": AuditEvent.PERMISSION_DENIED,
    }
    event = event_map.get(action, AuditEvent.PERMISSION_CHECK)

    details = {
        "path": str(path),
        "action": action,
    }
    if error:
        details["error"] = error

    log_audit_event(
        event_type=event,
        message=f"Permission {action}: {path.name}",
        details=details,
        success=success,
    )


def get_audit_log_path() -> Path | None:
    """Get the current audit log path.

    Returns:
        Path to audit log file, or None if not enabled.
    """
    return _audit_log_path if _audit_enabled else None


def read_audit_log(
    limit: int = 100,
    event_filter: str | None = None,
) -> list[dict]:
    """Read recent audit log entries.

    Args:
        limit: Maximum number of entries to return.
        event_filter: Optional event type prefix to filter by.

    Returns:
        List of audit log entries (most recent first).
    """
    if not _audit_enabled or _audit_log_path is None:
        return []

    if not _audit_log_path.exists():
        return []

    entries = []
    try:
        with open(_audit_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if event_filter is None or entry.get("event", "").startswith(event_filter):
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []

    # Return most recent first, limited
    return entries[-limit:][::-1]


__all__ = [
    "AuditEvent",
    "enable_audit_logging",
    "disable_audit_logging",
    "is_audit_enabled",
    "log_audit_event",
    "log_credential_access",
    "log_api_request",
    "log_config_change",
    "log_permission_event",
    "get_audit_log_path",
    "read_audit_log",
    "AUDIT_DIR",
    "AUDIT_LOG_FILE",
]
