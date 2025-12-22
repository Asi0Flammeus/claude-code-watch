#!/bin/bash
# Claude Watch Status Line for Claude Code
#
# This script outputs usage information in Claude Code status line format.
# Add to your Claude Code settings.json:
#
# {
#   "statusLine": {
#     "command": "/path/to/status-line.sh"
#   }
# }
#
# Or use: claude-watch --install-statusline

# Get usage from claude-watch (uses cache for speed)
output=$(claude-watch --prompt minimal 2>/dev/null)
exit_code=$?

# Format based on exit code
case $exit_code in
    0)  # OK (< 75%)
        echo "[$output]"
        ;;
    1)  # Warning (75-90%)
        echo "[⚠ $output]"
        ;;
    2)  # Critical (> 90%)
        echo "[🔴 $output]"
        ;;
    *)  # Error
        echo "[Usage: ?]"
        ;;
esac
