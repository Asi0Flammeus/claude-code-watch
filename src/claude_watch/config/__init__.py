"""Configuration management.

Modules:
    settings: Config loading, saving, validation, and migration
    credentials: Credential storage and retrieval
"""

from claude_watch.config.settings import (
    CONFIG_FILE,
    CONFIG_SCHEMA,
    CONFIG_VERSION,
    DEFAULT_CONFIG,
    SUBSCRIPTION_PLANS,
    load_config,
    migrate_config,
    save_config,
    validate_config,
)

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
]
