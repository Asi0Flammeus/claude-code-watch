"""Configuration management for claude-watch.

Provides functions for loading, saving, validating, and migrating
configuration files.
"""

import json
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

# File paths
CONFIG_FILE = Path.home() / ".claude" / ".usage_config.json"

# Default configuration values
DEFAULT_CONFIG = {
    "admin_api_key": None,
    "use_admin_api": False,
    "auto_collect": False,
    "collect_interval_hours": 1,
    "setup_completed": False,
    "subscription_plan": "pro",  # pro, max_5x, max_20x
    "shell_completion_installed": False,
    "webhook_url": None,
    "webhook_secret": None,
    "webhook_thresholds": "80,90,95",
}

# Subscription plans for validation
SUBSCRIPTION_PLANS = {"pro", "max_5x", "max_20x"}

# Config version for migration tracking
# Increment this when adding new config fields or changing schema
CONFIG_VERSION = 3

# Migration history:
# v1: Original config (admin_api_key, use_admin_api, auto_collect,
#     collect_interval_hours, setup_completed, subscription_plan)
# v2: Added shell_completion_installed
# v3: Added webhook_url, webhook_secret, webhook_thresholds

# Config schema for validation
# Format: key -> (expected_types, required, validator_func or None)
# validator_func takes value and returns (is_valid, error_message)
ValidatorFunc = Callable[[Union[str, int, float, bool, None]], Tuple[bool, str]]

CONFIG_SCHEMA: dict[str, tuple[tuple, bool, Optional[ValidatorFunc]]] = {
    "admin_api_key": (
        (str, type(None)),
        False,
        lambda v: (True, "")
        if v is None or (isinstance(v, str) and len(v) > 0)
        else (False, "must be a non-empty string or null"),
    ),
    "use_admin_api": ((bool,), False, None),
    "auto_collect": ((bool,), False, None),
    "collect_interval_hours": (
        (int, float),
        False,
        lambda v: (True, "") if 0 < v <= 24 else (False, "must be between 0 and 24"),
    ),
    "setup_completed": ((bool,), False, None),
    "subscription_plan": (
        (str,),
        False,
        lambda v: (True, "")
        if v in SUBSCRIPTION_PLANS
        else (False, f"must be one of: {', '.join(sorted(SUBSCRIPTION_PLANS))}"),
    ),
    "shell_completion_installed": ((bool,), False, None),
    "webhook_url": (
        (str, type(None)),
        False,
        lambda v: (True, "")
        if v is None or (isinstance(v, str) and v.startswith("http"))
        else (False, "must be a valid HTTP/HTTPS URL"),
    ),
    "webhook_secret": ((str, type(None)), False, None),
    "webhook_thresholds": (
        (str,),
        False,
        lambda v: (True, "")
        if all(t.strip().isdigit() for t in v.split(","))
        else (False, "must be comma-separated integers (e.g., '80,90,95')"),
    ),
    "_config_version": ((int,), False, None),  # Internal version tracking for migrations
}


def validate_config(config: dict) -> List[str]:
    """Validate configuration against schema.

    Args:
        config: Configuration dictionary to validate.

    Returns:
        List of validation error messages. Empty list if valid.
    """
    errors = []

    # Check for unknown keys
    for key in config:
        if key not in CONFIG_SCHEMA:
            errors.append(f"Unknown config key: '{key}'")

    # Validate each known key
    for key, (expected_types, required, validator) in CONFIG_SCHEMA.items():
        # Check required keys
        if required and key not in config:
            errors.append(f"Missing required key: '{key}'")
            continue

        # Skip if key not present and not required
        if key not in config:
            continue

        value = config[key]

        # Type checking (allow None for optional fields)
        if not isinstance(value, expected_types):
            type_names = " or ".join(t.__name__ for t in expected_types)
            errors.append(
                f"'{key}' has invalid type: expected {type_names}, got {type(value).__name__}"
            )
            continue

        # Custom validation
        if validator and value is not None:
            is_valid, error_msg = validator(value)
            if not is_valid:
                errors.append(f"'{key}' {error_msg}")

    return errors


def migrate_config(config: dict) -> Tuple[dict, bool]:
    """Migrate old config formats to the current schema.

    Args:
        config: Configuration dictionary to migrate.

    Returns:
        Tuple of (migrated_config, was_migrated).
    """
    was_migrated = False
    migrated = config.copy()

    # Detect version by checking for known fields
    # If _config_version is missing, infer from field presence
    current_version = migrated.get("_config_version", 1)

    # Migration from v1 to v2: Add shell_completion_installed
    if current_version < 2:
        if "shell_completion_installed" not in migrated:
            migrated["shell_completion_installed"] = DEFAULT_CONFIG["shell_completion_installed"]
            was_migrated = True
        current_version = 2

    # Migration from v2 to v3: Add webhook settings
    if current_version < 3:
        if "webhook_url" not in migrated:
            migrated["webhook_url"] = DEFAULT_CONFIG["webhook_url"]
            was_migrated = True
        if "webhook_secret" not in migrated:
            migrated["webhook_secret"] = DEFAULT_CONFIG["webhook_secret"]
            was_migrated = True
        if "webhook_thresholds" not in migrated:
            migrated["webhook_thresholds"] = DEFAULT_CONFIG["webhook_thresholds"]
            was_migrated = True
        current_version = 3

    # Remove any deprecated keys (none currently, but ready for future)
    deprecated_keys: list[str] = []  # Add deprecated key names here in future
    for key in deprecated_keys:
        if key in migrated:
            del migrated[key]
            was_migrated = True

    # Update version marker
    if was_migrated:
        migrated["_config_version"] = CONFIG_VERSION

    return migrated, was_migrated


def load_config(
    validate: bool = True,
    auto_migrate: bool = True,
    config_file: Optional[Path] = None,
    silent: bool = False,
) -> dict:
    """Load configuration from file.

    Args:
        validate: Whether to validate config and warn on errors. Default True.
        auto_migrate: Whether to automatically migrate old config formats. Default True.
        config_file: Optional path to config file. Defaults to CONFIG_FILE.
        silent: If True, suppress warning output. Default False.

    Returns:
        Configuration dictionary merged with defaults.
    """
    if config_file is None:
        config_file = CONFIG_FILE

    if not config_file.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_file) as f:
            config = json.load(f)

            # Migrate old config formats if needed
            if auto_migrate:
                config, was_migrated = migrate_config(config)
                if was_migrated:
                    # Save the migrated config
                    save_config(config, config_file=config_file)
                    if not silent:
                        print(
                            f"Config migrated to version {CONFIG_VERSION}",
                            file=sys.stderr,
                        )

            # Validate if requested
            if validate and not silent:
                errors = validate_config(config)
                if errors:
                    print("Warning: Config validation errors:", file=sys.stderr)
                    for error in errors:
                        print(f"  - {error}", file=sys.stderr)

            # Merge with defaults for any missing keys
            return {**DEFAULT_CONFIG, **config}
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict, config_file: Optional[Path] = None) -> None:
    """Save configuration to file.

    Args:
        config: Configuration dictionary to save.
        config_file: Optional path to config file. Defaults to CONFIG_FILE.
    """
    if config_file is None:
        config_file = CONFIG_FILE

    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    # Secure the file (contains API key)
    os.chmod(config_file, 0o600)


def reset_config(config_file: Optional[Path] = None) -> None:
    """Reset configuration to default values.

    Args:
        config_file: Optional path to config file. Defaults to CONFIG_FILE.
    """
    save_config(DEFAULT_CONFIG.copy(), config_file=config_file)


__all__ = [
    "CONFIG_FILE",
    "DEFAULT_CONFIG",
    "SUBSCRIPTION_PLANS",
    "CONFIG_VERSION",
    "CONFIG_SCHEMA",
    "validate_config",
    "migrate_config",
    "load_config",
    "save_config",
    "reset_config",
]
