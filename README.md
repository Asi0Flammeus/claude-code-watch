# Claude Code Usage CLI

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
git clone https://github.com/YOUR_REPO/claude-code-usage-cli.git
ln -s $(pwd)/claude-code-usage-cli/claude-usage ~/.local/bin/

# Run
claude-usage           # Current usage
claude-usage -a        # With analytics
claude-usage --setup   # Configure auto-collection
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
| `claude-usage` | Show current usage |
| `claude-usage -a` | Show analytics with trends |
| `claude-usage -j` | Output raw JSON |
| `claude-usage --setup` | Run setup wizard |
| `claude-usage --config` | Show configuration |
| `claude-usage --no-color` | Disable colors (for piping) |
| `claude-usage --no-record` | Don't save to history |

## Setup Wizard

First run prompts for optional configuration:

1. **Admin API Key** - For organization usage data (requires admin role)
2. **Auto-collection** - Hourly systemd timer for analytics
3. **Subscription plan** - Pro ($20), Max 5x ($100), or Max 20x ($200)

Re-run anytime with `claude-usage --setup`.

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
