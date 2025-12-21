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

- [x] [**Shell prompt**](docs/FEATURES.md#1-shell-prompt-integration---prompt) - Compact output for PS1/starship/oh-my-zsh
- [x] [**Tmux integration**](docs/FEATURES.md#4-tmux-integration---tmux) - Status bar with session % and reset time
- [ ] [**Watch mode**](docs/FEATURES.md#2-watch-mode---watch) - Live updating display
- [ ] [**Notifications**](docs/FEATURES.md#3-desktop-notifications---notify) - Desktop alerts at usage thresholds
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

# Install directly from GitHub
uv tool install git+https://github.com/Asi0Flammeus/claude-code-watch

# Run
claude-watch           # Current usage
claude-watch -a        # With analytics
ccw                    # Short alias (included)
```

Update later with: `uv tool upgrade claude-watch`

### Option 2: pipx

If you prefer [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/Asi0Flammeus/claude-code-watch
```

### Option 3: Direct Download

Single-file install without any package manager:

```bash
curl -o ~/.local/bin/claude-watch \
  https://raw.githubusercontent.com/Asi0Flammeus/claude-code-watch/main/claude_watch.py

chmod +x ~/.local/bin/claude-watch

# Optional: create short alias
ln -s ~/.local/bin/claude-watch ~/.local/bin/ccw
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
| `claude-watch --prompt` | Compact output for shell prompts |
| `claude-watch -p minimal` | Minimal prompt format |
| `claude-watch --tmux` | Output for tmux status bar |
| `claude-watch --no-color` | Disable colors (for piping) |
| `claude-watch --no-record` | Don't save to history |
| `ccw` | Short alias (configure in shell) |

### Shell Prompt Integration

Embed usage in your shell prompt with `--prompt`:

```bash
claude-watch --prompt              # S:45% 2h15m→ (default format)
claude-watch -p minimal            # 45%→
claude-watch -p full               # S:45% W:12%→
claude-watch -p icon               # 🟢45%→
claude-watch --prompt --prompt-color  # With ANSI colors
```

**Exit codes** for scripting:
- `0` - OK (usage < 75%)
- `1` - Warning (75-89%)
- `2` - Critical (≥90%)
- `3` - Error (no data)

**Trend indicators**: `↑` increasing, `↓` decreasing, `→` stable

#### Bash (PS1)

```bash
# Add to ~/.bashrc
claude_usage() {
    claude-watch -p minimal 2>/dev/null || echo "?"
}
PS1='[\u@\h \W $(claude_usage)] \$ '
```

#### Zsh

```zsh
# Add to ~/.zshrc
claude_usage() {
    claude-watch -p icon 2>/dev/null || echo "?"
}
RPROMPT='$(claude_usage)'
```

#### Starship

```toml
# Add to ~/.config/starship.toml
[custom.claude]
command = "claude-watch -p minimal"
when = true
format = "[$output]($style) "
style = "blue"
```

#### Oh-My-Zsh

```zsh
# Create ~/.oh-my-zsh/custom/themes/claude.zsh-theme
PROMPT='%{$fg[cyan]%}%c%{$reset_color%} $(claude-watch -p icon 2>/dev/null) %(!.#.$) '
```

### Tmux Integration

The `--tmux` flag outputs usage with tmux-specific color codes:

```bash
claude-watch --tmux    # #[fg=green]S:45% 2h15m #[fg=green]W:12%#[default]
```

**Exit codes** match `--prompt` for conditional coloring in tmux:
- `0` - OK (green)
- `1` - Warning (yellow, 75-89%)
- `2` - Critical (red, ≥90%)
- `3` - Error

#### Tmux Status Bar

```tmux
# Add to ~/.tmux.conf
set -g status-right '#(claude-watch --tmux 2>/dev/null)'
set -g status-interval 60  # Update every 60 seconds
```

For more control, use a script:

```bash
# ~/.local/bin/tmux-claude-usage
#!/bin/bash
claude-watch --tmux 2>/dev/null || echo "#[fg=yellow]?#[default]"
```

```tmux
# In ~/.tmux.conf
set -g status-right '#(~/.local/bin/tmux-claude-usage)'
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CLAUDE_WATCH_NO_COLOR` | Disable colors when set to any non-empty value |
| `CLAUDE_WATCH_CACHE_TTL` | Cache TTL in seconds (default: 60) |
| `CLAUDE_WATCH_HISTORY_DAYS` | History retention in days (default: 180) |

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
