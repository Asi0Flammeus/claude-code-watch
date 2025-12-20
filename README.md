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

## Installation

### Option 1: uv (Recommended)

[uv](https://docs.astral.sh/uv/) is the fastest way to install Python CLI tools:

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install claude-watch
uv tool install claude-watch

# Run
claude-watch           # Current usage
claude-watch -a        # With analytics
ccw                    # Short alias (included)
```

Update later with: `uv tool upgrade claude-watch`

### Option 2: pipx

If you prefer [pipx](https://pipx.pypa.io/):

```bash
pipx install claude-watch
```

### Option 3: Direct Download

For a single-file install without package managers:

```bash
# Download to ~/.local/bin (or any directory in your PATH)
curl -o ~/.local/bin/claude-watch \
  https://raw.githubusercontent.com/YOUR_REPO/claude-watch/main/claude_watch.py

chmod +x ~/.local/bin/claude-watch

# Optional: create short alias
ln -s ~/.local/bin/claude-watch ~/.local/bin/ccw
```

### Option 4: From Source

```bash
git clone https://github.com/YOUR_REPO/claude-watch.git
cd claude-watch
uv tool install .
# or: pip install --user .
```

## Quick Start

```bash
claude-watch           # Show current usage
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

## Shell Completions

Tab completion is available for Bash, Zsh, and Fish shells.

### Bash

Add to `~/.bashrc`:

```bash
source /path/to/claude-watch/completions/claude-watch.bash
```

Or copy to system completions:

```bash
sudo cp completions/claude-watch.bash /etc/bash_completion.d/claude-watch
```

### Zsh

Add to `~/.zshrc` (before `compinit`):

```zsh
fpath=(/path/to/claude-watch/completions $fpath)
autoload -Uz compinit && compinit
```

Or copy to a directory in your `$fpath`:

```bash
cp completions/claude-watch.zsh /usr/local/share/zsh/site-functions/_claude-watch
```

### Fish

Copy to Fish completions directory:

```bash
cp completions/claude-watch.fish ~/.config/fish/completions/
```

Completions also work for the `ccw` alias.

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
