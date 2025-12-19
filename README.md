# Claude Code Watch

A command-line tool to monitor your Claude Code subscription usage, similar to [claude.ai/settings/usage](https://claude.ai/settings/usage).

## Features

### Implemented

- [x] **Real-time usage** - Session (5h) and weekly limits with progress bars
- [x] **Analytics mode** - Historical trends, sparklines, peak usage patterns
- [x] **Cost analysis** - Compare API costs vs subscription value (Pro/Max)
- [x] **Auto-collection** - Systemd timer for hourly usage tracking
- [x] **Admin API** - Organization-level usage data (optional)
- [x] **JSON output** - Machine-readable output for scripting
- [x] **Setup wizard** - Interactive configuration
- [x] **Cross-platform** - Linux, macOS, Windows
- [x] **Zero dependencies** - Python stdlib only

### Roadmap

- [ ] [**Shell prompt**](docs/FEATURES.md#1-shell-prompt-integration---prompt) - Compact output for PS1/starship/oh-my-zsh
- [ ] [**Watch mode**](docs/FEATURES.md#2-watch-mode---watch) - Live updating display
- [ ] [**Notifications**](docs/FEATURES.md#3-desktop-notifications---notify) - Desktop alerts at usage thresholds
- [ ] [**Tmux integration**](docs/FEATURES.md#4-tmux-integration---tmux) - Status bar with session % and reset time
- [ ] [**Hook generator**](docs/FEATURES.md#5-hook-generator---generate-hook) - Claude Code pre-session warnings
- [ ] [**Forecast**](docs/FEATURES.md#6-enhanced-forecast---forecast) - Predict when limits will be hit
- [ ] [**HTML reports**](docs/FEATURES.md#7-html-report---report) - Weekly/monthly usage reports
- [ ] [**CSV export**](docs/FEATURES.md#8-csv-export---export) - Export history for external tools

See [docs/FEATURES.md](docs/FEATURES.md) for detailed specifications.

## Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_REPO/claude-watch.git
cd claude-watch

# Option 1: Symlink to PATH
ln -s $(pwd)/claude-watch ~/.local/bin/claude-watch

# Option 2: Add alias for ccw (add to ~/.bashrc or ~/.zshrc)
alias ccw='/path/to/claude-watch/claude-watch'

# Run
claude-watch           # Current usage
claude-watch -a        # With analytics
claude-watch --setup   # Configure auto-collection
ccw                    # Short alias
```

## Example Output

```
Plan usage limits

Current session      ████████░░░░░░░░░░░░░░░░░  34% used
Resets in 3 hr 25 min

Weekly limits

All models           ██░░░░░░░░░░░░░░░░░░░░░░░  9% used
Resets Tue 9:59 AM

Sonnet only          ░░░░░░░░░░░░░░░░░░░░░░░░░  1% used
Resets Mon 6:59 PM
```

## Usage

| Command | Description |
|---------|-------------|
| `claude-watch` | Show current usage |
| `claude-watch -a` | Show analytics with trends |
| `claude-watch -j` | Output raw JSON |
| `claude-watch --setup` | Run setup wizard |
| `claude-watch --config` | Show configuration |
| `claude-watch --no-color` | Disable colors (for piping) |
| `claude-watch --no-record` | Don't save to history |
| `ccw` | Short alias (configure in shell) |

## Setup Wizard

First run prompts for optional configuration:

1. **Admin API Key** - For organization usage data (requires admin role)
2. **Auto-collection** - Hourly systemd timer for analytics
3. **Subscription plan** - Pro ($20), Max 5x ($100), or Max 20x ($200)

Re-run anytime with `claude-watch --setup`.

## Analytics Mode

With `-a` flag, shows:

- **Sparkline trends** - 24h and 7d usage patterns
- **Peak analysis** - Busiest days/hours
- **Usage prediction** - Estimated time to limits
- **Cost comparison** - API equivalent vs subscription value
- **Recommendations** - Optimal plan based on usage

## Requirements

- **Python 3.8+**
- **Claude Code** authenticated (`claude login`)

Credentials read from:
- `~/.claude/.credentials.json` (Linux/Windows)
- macOS Keychain (macOS)

## Data Storage

| File | Purpose |
|------|---------|
| `~/.claude/.usage_config.json` | Configuration |
| `~/.claude/.usage_history.json` | Usage history (180 days) |

## API Reference

### OAuth API (default)
- **Endpoint**: `https://api.anthropic.com/api/oauth/usage`
- **Auth**: Bearer token from Claude Code credentials
- **Data**: Current session and weekly utilization

### Admin API (optional)
- **Endpoint**: `https://api.anthropic.com/v1/organizations/usage_report/messages`
- **Auth**: Admin API key (`sk-ant-admin-...`)
- **Data**: Historical token usage with model breakdown

## Troubleshooting

**"Credentials not found"** - Run `claude login`

**"Authentication failed"** - Run `claude logout && claude login`

**Colors not showing** - Terminal must support ANSI; use `--no-color` for pipes

## License

MIT
