# Claude Code Usage CLI

A command-line tool to monitor your Claude Code subscription usage, similar to [claude.ai/settings/usage](https://claude.ai/settings/usage).

## Features

- **Real-time usage** - Session (5h) and weekly limits with progress bars
- **Analytics** - Historical trends, sparklines, peak usage patterns
- **Cost analysis** - Compare API costs vs subscription value (Pro/Max)
- **Auto-collection** - Systemd timer for hourly usage tracking
- **Admin API support** - Organization-level usage data (optional)
- **Cross-platform** - Linux, macOS, Windows
- **Zero dependencies** - Python stdlib only

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
