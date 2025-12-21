"""
Pytest fixtures for claude-watch tests.

Test imports use the src/claude_watch/ package via --import-mode=importlib (see pyproject.toml).
The standalone claude_watch.py script is tested separately via subprocess.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Path Constants
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# Load fixtures data
FIXTURES_DIR = Path(__file__).parent / "fixtures"
with open(FIXTURES_DIR / "api_responses.json") as f:
    FIXTURES = json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# API Response Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def usage_normal():
    """Normal usage response (34.5% session, 12.3% weekly)."""
    return FIXTURES["usage_normal"].copy()


@pytest.fixture
def usage_high():
    """High usage response (85.2% session, 67.8% weekly)."""
    return FIXTURES["usage_high"].copy()


@pytest.fixture
def usage_critical():
    """Critical usage response (98.7% session, 95.1% weekly)."""
    return FIXTURES["usage_critical"].copy()


@pytest.fixture
def usage_empty():
    """Empty usage response (0% usage)."""
    return FIXTURES["usage_empty"].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# History Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def history_sample():
    """Sample history with 5 data points."""
    return FIXTURES["history_sample"].copy()


@pytest.fixture
def history_empty():
    """Empty history list."""
    return []


@pytest.fixture
def history_large():
    """Large history with 100 data points over 7 days."""
    history = []
    base_time = datetime.now(timezone.utc) - timedelta(days=7)

    for i in range(100):
        timestamp = base_time + timedelta(hours=i * 1.68)  # ~100 points over 7 days
        # Simulate varying usage patterns
        five_hour = 20 + (i % 30) + (i % 7) * 3  # 20-80% range
        seven_day = 5 + (i // 10) * 2  # Slowly increasing

        history.append(
            {
                "timestamp": timestamp.isoformat(),
                "five_hour": min(five_hour, 100),
                "seven_day": min(seven_day, 100),
                "seven_day_sonnet": five_hour * 0.3,
                "seven_day_opus": None,
            }
        )

    return history


# ═══════════════════════════════════════════════════════════════════════════════
# Credentials Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def credentials_valid():
    """Valid credentials with access token."""
    return FIXTURES["credentials_valid"].copy()


@pytest.fixture
def credentials_missing_token():
    """Credentials without access token."""
    return FIXTURES["credentials_missing_token"].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# Config Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def config_default():
    """Default configuration."""
    return FIXTURES["config_default"].copy()


@pytest.fixture
def config_max():
    """Max plan configuration with admin API."""
    return FIXTURES["config_max"].copy()


# ═══════════════════════════════════════════════════════════════════════════════
# Mock Fixtures (updated for new module structure)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_fetch_usage(usage_normal):
    """Mock fetch_usage to return normal usage data."""
    with patch("claude_watch.api.client.fetch_usage", return_value=usage_normal) as mock:
        yield mock


@pytest.fixture
def mock_credentials(credentials_valid):
    """Mock get_credentials to return valid credentials."""
    with patch("claude_watch.config.credentials.get_credentials", return_value=credentials_valid) as mock:
        yield mock


@pytest.fixture
def mock_urlopen():
    """Mock urlopen for API testing."""
    with patch("claude_watch.api.client.urlopen") as mock:
        yield mock


# ═══════════════════════════════════════════════════════════════════════════════
# Temporary File Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_config_file(tmp_path, config_default):
    """Create temporary config file."""
    config_file = tmp_path / ".usage_config.json"
    config_file.write_text(json.dumps(config_default))
    return config_file


@pytest.fixture
def tmp_history_file(tmp_path, history_sample):
    """Create temporary history file."""
    history_file = tmp_path / ".usage_history.json"
    history_file.write_text(json.dumps(history_sample))
    return history_file


@pytest.fixture
def tmp_credentials_file(tmp_path, credentials_valid):
    """Create temporary credentials file."""
    creds_file = tmp_path / ".credentials.json"
    creds_file.write_text(json.dumps(credentials_valid))
    return creds_file


# ═══════════════════════════════════════════════════════════════════════════════
# Time Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def fixed_now():
    """Fixed datetime for reproducible tests."""
    return datetime(2024, 12, 19, 14, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_now(fixed_now):
    """Mock datetime.now to return fixed time."""
    with patch("claude_watch.utils.time.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.strptime = datetime.strptime
        yield mock_dt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cli_args_default():
    """Default CLI arguments."""
    return type(
        "Args",
        (),
        {
            "json": False,
            "analytics": False,
            "setup": False,
            "config": False,
            "no_color": False,
            "no_record": False,
        },
    )()


@pytest.fixture
def cli_args_json():
    """CLI arguments with JSON output."""
    return type(
        "Args",
        (),
        {
            "json": True,
            "analytics": False,
            "setup": False,
            "config": False,
            "no_color": False,
            "no_record": False,
        },
    )()


@pytest.fixture
def cli_args_analytics():
    """CLI arguments with analytics mode."""
    return type(
        "Args",
        (),
        {
            "json": False,
            "analytics": True,
            "setup": False,
            "config": False,
            "no_color": False,
            "no_record": False,
        },
    )()
