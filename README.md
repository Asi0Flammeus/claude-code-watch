# Claude Code Usage CLI

A clean command-line tool to display your Claude Code subscription usage limits, similar to [claude.ai/settings/usage](https://claude.ai/settings/usage).

![Example output](https://img.shields.io/badge/Python-3.8+-blue.svg)

## Features

- Displays current session (5-hour) and weekly usage limits
- Visual progress bars with color-coded usage levels
- Cross-platform support (Linux, macOS, Windows)
- JSON output mode for scripting
- No external dependencies (uses Python stdlib only)

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

Last updated: just now
```

## Installation

### Quick Install (Linux/macOS)

```bash
# Download and install
curl -o ~/.local/bin/claude-usage https://raw.githubusercontent.com/YOUR_REPO/claude-code-usage-cli/main/claude-usage
chmod +x ~/.local/bin/claude-usage

# Or clone and symlink
git clone https://github.com/YOUR_REPO/claude-code-usage-cli.git
ln -s $(pwd)/claude-code-usage-cli/claude-usage ~/.local/bin/claude-usage
```

### Manual Install

1. Download `claude-usage` to a directory in your PATH
2. Make it executable: `chmod +x claude-usage`
3. Run: `claude-usage`

## Prerequisites

- **Python 3.8+** (no external packages needed)
- **Claude Code** installed and authenticated
  - The tool reads credentials from `~/.claude/.credentials.json` (Linux/Windows)
  - On macOS, it can also read from the macOS Keychain

## Usage

```bash
# Display formatted usage
claude-usage

# Output raw JSON (for scripting)
claude-usage --json

# Disable colors (for piping)
claude-usage --no-color
```

### Shell Integration

Add to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
# Alias for quick access
alias cu='claude-usage'

# Show usage on terminal startup (optional)
claude-usage 2>/dev/null || true
```

### Statusline Integration

For tmux statusline:

```bash
# In ~/.tmux.conf
set -g status-right "#(claude-usage --json 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print(f\\\"CC: {int(d.get('five_hour',{}).get('utilization',0))}%\\\")\" 2>/dev/null || echo 'CC: --')"
```

## API Details

The tool uses the Anthropic OAuth API:

- **Endpoint**: `https://api.anthropic.com/api/oauth/usage`
- **Authentication**: Bearer token from Claude Code credentials
- **Required Header**: `anthropic-beta: oauth-2025-04-20`

### Response Structure

```json
{
  "five_hour": {
    "utilization": 34.0,
    "resets_at": "2025-12-18T16:00:00+00:00"
  },
  "seven_day": {
    "utilization": 9.0,
    "resets_at": "2025-12-23T09:00:00+00:00"
  },
  "seven_day_sonnet": {
    "utilization": 1.0,
    "resets_at": "2025-12-22T18:00:00+00:00"
  },
  "seven_day_opus": null,
  "extra_usage": {
    "is_enabled": false,
    "monthly_limit": null,
    "used_credits": null,
    "utilization": null
  }
}
```

### Usage Limits Explained

| Limit | Description |
|-------|-------------|
| `five_hour` | Current session - rolling 5-hour window usage |
| `seven_day` | Weekly limit - all models combined |
| `seven_day_sonnet` | Weekly Sonnet-only usage |
| `seven_day_opus` | Weekly Opus-only usage (if applicable) |
| `extra_usage` | Additional credits (Max plan feature) |

## Troubleshooting

### "Credentials not found"

Ensure Claude Code is installed and you've logged in:
```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Login
claude login
```

### "Authentication failed"

Your session may have expired. Re-authenticate:
```bash
claude logout
claude login
```

### No color output

Colors require a TTY. When piping output, colors are automatically disabled.
Use `--no-color` to force disable colors.

## Contributing

Issues and PRs welcome! This tool is intentionally minimal with no external dependencies.

## License

MIT

## References

- [Claude Code Documentation](https://claude.ai/docs/code)
- [Usage Limits Article](https://codelynx.dev/posts/claude-code-usage-limits-statusline)
- [Anthropic API Rate Limits](https://platform.claude.com/docs/en/api/rate-limits)
