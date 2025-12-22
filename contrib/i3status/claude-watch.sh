#!/bin/bash
# Claude Watch module for i3status-rs or i3blocks
#
# For i3blocks, add to ~/.config/i3blocks/config:
#
# [claude-watch]
# command=/path/to/claude-watch.sh
# interval=60
# markup=pango
#
# For i3status-rs, use custom block:
#
# [[block]]
# block = "custom"
# command = "/path/to/claude-watch.sh"
# interval = 60
# json = true

# Get usage from claude-watch (uses cache for speed)
data=$(claude-watch --json 2>/dev/null)
exit_code=$?

if [ $exit_code -ne 0 ] || [ -z "$data" ]; then
    # Error case
    echo '{"full_text": "Claude: ?", "color": "#888888"}'
    exit 0
fi

# Parse JSON
session=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('five_hour',{}).get('utilization',0))" 2>/dev/null)
weekly=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('seven_day',{}).get('utilization',0))" 2>/dev/null)

# Default values if parsing failed
session=${session:-0}
weekly=${weekly:-0}

# Determine color based on max usage
max_usage=$(echo "$session $weekly" | awk '{print ($1>$2)?$1:$2}')

if (( $(echo "$max_usage >= 90" | bc -l) )); then
    color="#FF5555"  # Red
    icon="🔴"
elif (( $(echo "$max_usage >= 75" | bc -l) )); then
    color="#F1FA8C"  # Yellow
    icon="⚠️"
else
    color="#50FA7B"  # Green
    icon="✓"
fi

# Format output (i3blocks JSON protocol)
printf '{"full_text": "%s S:%.0f%% W:%.0f%%", "color": "%s"}\n' "$icon" "$session" "$weekly" "$color"
