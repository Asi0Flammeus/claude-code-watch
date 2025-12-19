# Implementation TODO

Development roadmap for `claude-usage` CLI features.
Reference: [docs/FEATURES.md](../docs/FEATURES.md)

---

## Phase 0: Quality Foundation ⚡ NEW

### 0.1 Testing Infrastructure
**Priority:** Critical - Required before major feature development

- [ ] Create `tests/` directory structure
- [ ] Set up pytest with `pytest.ini` or `pyproject.toml`
- [ ] Add coverage tracking (`pytest-cov`)
- [ ] Create mock fixtures for API responses
- [ ] Unit tests for core functions:
  - [ ] `fetch_usage()` - API communication
  - [ ] `parse_reset_time()` - Time parsing
  - [ ] `format_relative_time()` - Display formatting
  - [ ] `get_period_stats()` - Analytics calculations
  - [ ] `load_history()` / `save_history()` - Data persistence
- [ ] Integration tests for CLI arguments
- [ ] Add `make test` target

```bash
# Target structure
tests/
├── conftest.py           # Fixtures, mocks
├── test_api.py           # API communication tests
├── test_analytics.py     # Analytics function tests
├── test_cli.py           # CLI argument parsing tests
├── test_formatting.py    # Display formatting tests
└── fixtures/
    └── api_responses.json # Mock API data
```

---

### 0.2 CI/CD Pipeline
**Priority:** High - Enables automated quality gates

- [ ] Create `.github/workflows/test.yml`
- [ ] Configure test matrix (Python 3.8, 3.9, 3.10, 3.11, 3.12)
- [ ] Configure OS matrix (ubuntu-latest, macos-latest, windows-latest)
- [ ] Add linting step (ruff or flake8)
- [ ] Add type checking step (mypy)
- [ ] Create `.github/workflows/release.yml` for automated releases
- [ ] Add branch protection rules documentation

```yaml
# Target: .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.8', '3.10', '3.12']
```

---

### 0.3 Pre-commit Hooks
**Priority:** Medium - Ensures code quality on commit

- [ ] Create `.pre-commit-config.yaml`
- [ ] Configure hooks: ruff, mypy, trailing-whitespace
- [ ] Add `make lint` target
- [ ] Document pre-commit setup in CONTRIBUTING.md

---

## Phase 1: Foundation

### 1.1 Cache System (Prerequisite)
**Required by:** `--prompt`, `--tmux`

- [ ] Create `fetch_usage_cached()` function
- [ ] Cache file: `~/.claude/.usage_cache.json`
- [ ] Max age: 60 seconds (configurable)
- [ ] Silent fallback on error (return `None` or last cached)
- [ ] Add `--cache-ttl` argument (optional)

```python
# Target location: after fetch_usage() function
CACHE_FILE = Path.home() / ".claude" / ".usage_cache.json"
CACHE_MAX_AGE = 60
```

---

## Phase 1.5: Developer Experience ⚡ NEW

### 1.5.1 Shell Completions
**Priority:** High - Users expect tab completion

- [ ] Create `completions/` directory
- [ ] Generate bash completion script
- [ ] Generate zsh completion script
- [ ] Generate fish completion script
- [ ] Add installation instructions to README
- [ ] Include in setup wizard (`--setup`)

```bash
# Target: completions/claude-usage.bash
_claude_usage_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=($(compgen -W "--help --json --analytics --prompt --tmux --watch --notify --forecast --export --report --setup --config --no-color --no-record --version --verbose --quiet" -- "$cur"))
}
complete -F _claude_usage_completions claude-usage
```

---

### 1.5.2 Essential CLI Flags
**Priority:** High - Standard CLI expectations

- [ ] Add `--version` / `-V` flag
  - Display version, Python version, platform
  - Check for updates (optional, non-blocking)
- [ ] Add `--verbose` / `-v` flag
  - Show API request/response details
  - Show timing information
  - Show cache status
- [ ] Add `--quiet` / `-q` flag
  - Suppress all non-error output
  - For cron jobs and scripts
  - Only output on threshold breach
- [ ] Add `--dry-run` flag (for testing)
  - Show what would be done without API calls
  - Use cached/mock data

**Test:** `claude-usage --version` should output `claude-usage 1.0.0 (Python 3.11, Linux)`

---

### 1.5.3 Configuration Improvements
**Priority:** Medium - Better config management

- [ ] Add config schema validation
- [ ] Add config migration for old formats
- [ ] Add `--config show` to display current config
- [ ] Add `--config reset` to reset to defaults
- [ ] Add `--config set KEY VALUE` for quick edits
- [ ] Support `CLAUDE_USAGE_*` environment variables
  - `CLAUDE_USAGE_NO_COLOR` - Disable colors
  - `CLAUDE_USAGE_CACHE_TTL` - Cache timeout
  - `CLAUDE_USAGE_HISTORY_DAYS` - History retention

---

## Phase 2: Quick Wins (Low Effort, High Value)

### 2.1 Shell Prompt (`--prompt`)
**Spec:** [docs/FEATURES.md#1-shell-prompt-integration](../docs/FEATURES.md#1-shell-prompt-integration---prompt)

- [ ] Add `--prompt [FORMAT]` argument
- [ ] Implement formats: `default`, `minimal`, `full`, `icon`
- [ ] Add trend indicator (`↑`, `↓`, `→`)
- [ ] Use cached fetch (from 1.1)
- [ ] Set exit codes (0=ok, 1=warning, 2=critical, 3=error)
- [ ] Add `--prompt-color` flag
- [ ] Document shell integration examples in README

**Test:** `claude-usage --prompt` should output `45↑/12` instantly

---

### 2.2 Tmux Integration (`--tmux`)
**Spec:** [docs/FEATURES.md#4-tmux-integration](../docs/FEATURES.md#4-tmux-integration---tmux)

- [ ] Add `--tmux` argument
- [ ] Output format: `S:45% 2h15m W:12%`
- [ ] Tmux color codes: `#[fg=green]`, `#[fg=yellow]`, `#[fg=red]`
- [ ] Implement `format_reset_compact()` for `2h15m` format
- [ ] Use cached fetch (from 1.1)
- [ ] Add tmux config example to README

**Test:** `claude-usage --tmux` should output colored tmux-formatted string

---

### 2.3 Watch Mode (`--watch`)
**Spec:** [docs/FEATURES.md#2-watch-mode](../docs/FEATURES.md#2-watch-mode---watch)

- [ ] Add `--watch [INTERVAL]` argument (default: 30s, range: 10-300)
- [ ] Implement `clear_screen()` function
- [ ] Add watch header with refresh countdown
- [ ] Track delta from session start
- [ ] Handle Ctrl+C gracefully with summary
- [ ] Support `--watch -a` for analytics mode

**Test:** `claude-usage --watch 10` should refresh every 10 seconds

---

### 2.4 CSV Export (`--export`)
**Spec:** [docs/FEATURES.md#8-csv-export](../docs/FEATURES.md#8-csv-export---export)

- [ ] Add `--export csv|json` argument
- [ ] Add `--days N` filter argument
- [ ] Add `-o FILE` output argument
- [ ] Add `--excel` flag for BOM prefix
- [ ] CSV columns: `timestamp,session_usage,weekly_usage,sonnet_usage,opus_usage`
- [ ] Sort by timestamp descending

**Test:** `claude-usage --export csv --days 7` should output last week's data

---

## Phase 3: Predictions & Analysis

### 3.1 Enhanced Forecast (`--forecast`)
**Spec:** [docs/FEATURES.md#6-enhanced-forecast](../docs/FEATURES.md#6-enhanced-forecast---forecast)

- [ ] Add `--forecast` argument
- [ ] Implement `calculate_forecast()` function
- [ ] Calculate hourly rate from recent history
- [ ] Add confidence intervals (conservative/optimistic)
- [ ] Weekly projection based on daily rate
- [ ] Display recommendations
- [ ] Integrate with `-a` analytics mode

**Test:** `claude-usage --forecast` should show time-to-limit predictions

---

## Phase 4: Notifications & Hooks

### 4.1 Desktop Notifications (`--notify`)
**Spec:** [docs/FEATURES.md#3-desktop-notifications](../docs/FEATURES.md#3-desktop-notifications---notify)

- [ ] Add `--notify` argument
- [ ] Add `--notify-at THRESHOLDS` argument (default: `80,90,95`)
- [ ] Implement `send_notification()` cross-platform:
  - Linux: `notify-send`
  - macOS: `osascript`
  - Windows: PowerShell toast
- [ ] Add notification state file to avoid duplicates
- [ ] Reset state when usage drops below 50%
- [ ] Add `--notify-daemon` for background mode

**Test:** `claude-usage --notify` should send notification if above threshold

---

### 4.2 Hook Generator (`--generate-hook`)
**Spec:** [docs/FEATURES.md#5-hook-generator](../docs/FEATURES.md#5-hook-generator---generate-hook)

- [ ] Add `--generate-hook` argument
- [ ] Create hook script template
- [ ] Add `--install-hook` to auto-install
- [ ] Update `~/.claude/settings.json` with hook path
- [ ] Support `CLAUDE_USAGE_THRESHOLD` env var
- [ ] Document hook usage in README

**Test:** `claude-usage --generate-hook` should output valid bash script

---

## Phase 5: Reporting

### 5.1 HTML Reports (`--report`)
**Spec:** [docs/FEATURES.md#7-html-report](../docs/FEATURES.md#7-html-report---report)

- [ ] Add `--report weekly|monthly` argument
- [ ] Create HTML template with dark theme
- [ ] Implement `generate_svg_chart()` for usage graphs
- [ ] Implement `generate_heatmap()` for day/hour patterns
- [ ] Add cost comparison table
- [ ] Generate recommendations section
- [ ] Add `--open` flag to open in browser
- [ ] Save to `~/.claude/report-{period}-{date}.html`

**Test:** `claude-usage --report weekly --open` should generate and open HTML report

---

## Phase 6: Resilience & Security ⚡ NEW

### 6.1 Network Resilience
**Priority:** High - Critical for reliability

- [ ] Implement retry with exponential backoff
  - Max 3 retries
  - Backoff: 1s, 2s, 4s
  - Jitter to prevent thundering herd
- [ ] Add configurable timeout (`--timeout`)
  - Default: 10 seconds
  - Range: 5-60 seconds
- [ ] Implement offline mode
  - Detect network unavailability
  - Fallback to cached data with staleness indicator
  - Show "Offline mode - data from X minutes ago"
- [ ] Add proxy support
  - Respect `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`
  - Add `--proxy` argument for explicit proxy

```python
# Target implementation
def fetch_with_retry(url, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return fetch_usage()
        except (URLError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
```

---

### 6.2 Security Hardening
**Priority:** High - Protect user credentials

- [ ] Validate credentials on startup
  - Check token format
  - Warn if token near expiration
- [ ] Secure credential handling
  - Never log access tokens
  - Mask tokens in verbose output (`sk-ant-...xxxx`)
- [ ] Audit logging (optional)
  - Log API calls to `~/.claude/.usage_audit.log`
  - Include timestamp, action, success/failure
  - Add `--audit` flag to enable
- [ ] Permission checks
  - Warn if config files world-readable
  - Auto-fix permissions on write (`chmod 600`)
- [ ] Secure systemd service
  - Add `ProtectSystem=strict`
  - Add `NoNewPrivileges=true`
  - Document in setup wizard

---

### 6.3 Error Handling Improvements
**Priority:** Medium - Better user experience

- [ ] Categorize errors with actionable messages
  - Network errors → "Check internet connection"
  - Auth errors → "Run `claude logout && claude login`"
  - Rate limit → "Wait X minutes or check usage"
- [ ] Add error codes for scripting
  - 0: Success
  - 1: Warning threshold
  - 2: Critical threshold
  - 10: Network error
  - 11: Authentication error
  - 12: API error
  - 20: Configuration error
- [ ] Add `--health-check` command
  - Verify credentials
  - Test API connectivity
  - Check config file integrity
  - Return structured status

**Test:** `claude-usage --health-check` should output structured health status

---

## Phase 7: Integrations ⚡ NEW

### 7.1 Webhook Notifications
**Priority:** Medium - Team/automation use cases

- [ ] Add `--webhook URL` argument
  - POST JSON payload on threshold breach
  - Support Slack incoming webhooks
  - Support Discord webhooks
  - Support generic HTTP webhooks
- [ ] Webhook payload schema:
```json
{
  "event": "threshold_breach",
  "level": "warning",
  "session_usage": 85.2,
  "weekly_usage": 45.1,
  "reset_in": "2h 15m",
  "timestamp": "2024-12-19T14:30:00Z"
}
```
- [ ] Add `--webhook-secret` for HMAC signing
- [ ] Add webhook configuration to `--setup`

---

### 7.2 Metrics Export
**Priority:** Medium - Monitoring/observability

- [ ] Prometheus metrics endpoint
  - Add `--metrics-server PORT` for metrics HTTP server
  - Expose `claude_usage_session_percent` gauge
  - Expose `claude_usage_weekly_percent` gauge
  - Expose `claude_usage_api_calls_total` counter
- [ ] Add Grafana dashboard template
  - Save as `contrib/grafana-dashboard.json`
  - Document import instructions
- [ ] InfluxDB line protocol export
  - Add `--export influx` format
  - Support direct push to InfluxDB

```bash
# Example: Prometheus scrape output
claude_usage_session_percent 45.2
claude_usage_weekly_percent 12.1
claude_usage_reset_seconds 7500
```

---

### 7.3 Desktop Integrations
**Priority:** Low - Power user features

- [ ] Raycast extension template
  - Quick view usage
  - Notification integration
  - Save as `contrib/raycast/`
- [ ] Alfred workflow
  - Keyword trigger
  - Visual output
  - Save as `contrib/alfred/`
- [ ] Polybar module
  - Script for usage display
  - Color theming
  - Save as `contrib/polybar/`
- [ ] i3status/waybar module
  - Usage block
  - Click to refresh
  - Save as `contrib/i3status/`

---

## Phase 8: Distribution ⚡ NEW

### 8.1 Python Packaging
**Priority:** High - Standard installation method

- [ ] Create `pyproject.toml`
  - Define metadata, dependencies, entry points
  - Configure build system (hatchling or setuptools)
- [ ] Create `setup.py` (legacy compatibility)
- [ ] Add `__version__` to module
- [ ] Create `requirements-dev.txt` for development
- [ ] Publish to PyPI
  - Configure trusted publisher
  - Create release workflow
- [ ] Add `pip install claude-usage` to README

```toml
# Target: pyproject.toml
[project]
name = "claude-usage"
version = "1.0.0"
description = "CLI tool to monitor Claude Code subscription usage"
requires-python = ">=3.8"
license = {text = "MIT"}
dependencies = []  # Zero deps!

[project.scripts]
claude-usage = "claude_usage:main"
```

---

### 8.2 Platform Packages
**Priority:** Medium - Easier installation

- [ ] **Homebrew formula** (macOS/Linux)
  - Create `Formula/claude-usage.rb`
  - Submit to homebrew-core or create tap
  - Test: `brew install claude-usage`
- [ ] **AUR package** (Arch Linux)
  - Create `PKGBUILD`
  - Submit to AUR
  - Test: `yay -S claude-usage`
- [ ] **Debian/Ubuntu** (.deb)
  - Create debian packaging
  - Host on GitHub releases or PPA
  - Test: `sudo dpkg -i claude-usage.deb`
- [ ] **Nix package**
  - Create `flake.nix` or `default.nix`
  - Submit to nixpkgs
  - Test: `nix run github:user/claude-usage`

---

### 8.3 Container Distribution
**Priority:** Low - Edge cases

- [ ] Create `Dockerfile`
  - Multi-stage build
  - Minimal image (alpine-based)
  - Credential mounting documentation
- [ ] Publish to Docker Hub / GHCR
- [ ] Create `docker-compose.yml` example
  - Daemon mode with notifications
  - Volume mounts for config/history

```dockerfile
# Target: Dockerfile
FROM python:3.12-alpine AS runtime
COPY claude-usage /usr/local/bin/
ENTRYPOINT ["claude-usage"]
```

---

### 8.4 Documentation & Community
**Priority:** High - Project sustainability

- [ ] Create man page (`man/claude-usage.1`)
  - Full command documentation
  - Install via package managers
- [ ] Create `CONTRIBUTING.md`
  - Development setup
  - Testing instructions
  - PR guidelines
  - Code style guide
- [ ] Create `CHANGELOG.md`
  - Keep a Changelog format
  - Automate with release-please or similar
- [ ] GitHub issue templates
  - Bug report template
  - Feature request template
  - Question template
- [ ] GitHub discussions setup
  - Q&A category
  - Ideas category
  - Show and tell

---

## Implementation Notes

### File Structure After Implementation
```
claude-usage (main script)
├── Configuration section
├── Cache system (new)
├── Credential management
├── History management
├── API communication
├── Time formatting
├── Display formatting
├── Forecast functions (new)
├── Notification functions (new)
├── Export functions (new)
├── Report generation (new)
├── Hook generation (new)
└── Main entry point (extended argparse)
```

### Argument Groups
```python
# Display modes (mutually exclusive)
display_group = parser.add_mutually_exclusive_group()
display_group.add_argument("--json", "-j", ...)
display_group.add_argument("--prompt", ...)
display_group.add_argument("--tmux", ...)
display_group.add_argument("--watch", "-w", ...)
display_group.add_argument("--report", ...)
display_group.add_argument("--export", ...)
```

### Testing Checklist
- [ ] All new flags work with `--no-color`
- [ ] All new flags work with `--no-record`
- [ ] Cache respects `--no-record` (still caches)
- [ ] Errors don't break shell prompts (silent fail)
- [ ] Cross-platform notification testing

---

## Progress Tracking

### Phase 0: Quality Foundation ⚡ NEW
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 0.1 | Testing infrastructure | Not started | |
| 0.2 | CI/CD pipeline | Not started | |
| 0.3 | Pre-commit hooks | Not started | |

### Phase 1: Foundation
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 1.1 | Cache system | Not started | |

### Phase 1.5: Developer Experience ⚡ NEW
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 1.5.1 | Shell completions | Not started | |
| 1.5.2 | Essential CLI flags | Not started | |
| 1.5.3 | Config improvements | Not started | |

### Phase 2: Quick Wins
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 2.1 | `--prompt` | Not started | |
| 2.2 | `--tmux` | Not started | |
| 2.3 | `--watch` | Not started | |
| 2.4 | `--export` | Not started | |

### Phase 3: Predictions
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 3.1 | `--forecast` | Not started | |

### Phase 4: Notifications & Hooks
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 4.1 | `--notify` | Not started | |
| 4.2 | `--generate-hook` | Not started | |

### Phase 5: Reporting
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 5.1 | `--report` | Not started | |

### Phase 6: Resilience & Security ⚡ NEW
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 6.1 | Network resilience | Not started | |
| 6.2 | Security hardening | Not started | |
| 6.3 | Error handling | Not started | |

### Phase 7: Integrations ⚡ NEW
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 7.1 | Webhook notifications | Not started | |
| 7.2 | Metrics export | Not started | |
| 7.3 | Desktop integrations | Not started | |

### Phase 8: Distribution ⚡ NEW
| # | Feature | Status | PR |
|---|---------|--------|-----|
| 8.1 | Python packaging | Not started | |
| 8.2 | Platform packages | Not started | |
| 8.3 | Container distribution | Not started | |
| 8.4 | Documentation & community | Not started | |

---

## Priority Matrix

| Priority | Phase | Rationale |
|----------|-------|-----------|
| 🔴 Critical | 0 (Quality) | Foundation for maintainability |
| 🔴 Critical | 1 (Cache) | Prerequisite for shell integrations |
| 🟡 High | 1.5 (DX) | User expectations |
| 🟡 High | 2 (Quick Wins) | High value, low effort |
| 🟡 High | 8.1, 8.4 (PyPI, Docs) | Distribution & sustainability |
| 🟢 Medium | 3-5 | Core features |
| 🟢 Medium | 6 (Resilience) | Production readiness |
| 🟢 Medium | 7.1-7.2 | Enterprise/team use |
| 🔵 Low | 7.3, 8.2-8.3 | Nice-to-have |

---

*Update this file as features are implemented.*
*Last updated: 2024-12-19 | Added phases 0, 1.5, 6, 7, 8*
