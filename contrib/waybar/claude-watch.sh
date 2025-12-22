#!/bin/bash
# Claude Watch module for Waybar
#
# Add to ~/.config/waybar/config:
#
# "custom/claude": {
#     "exec": "/path/to/claude-watch.sh",
#     "interval": 60,
#     "return-type": "json",
#     "format": "{}",
# }
#
# Add styling in ~/.config/waybar/style.css:
#
# #custom-claude.warning {
#     color: #f1fa8c;
# }
# #custom-claude.critical {
#     color: #ff5555;
# }

# Get usage from claude-watch
data=$(claude-watch --json 2>/dev/null)
exit_code=$?

if [ $exit_code -ne 0 ] || [ -z "$data" ]; then
    # Error case
    echo '{"text": "Claude: ?", "class": "error", "tooltip": "Failed to fetch usage"}'
    exit 0
fi

# Parse JSON
session=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('five_hour',{}).get('utilization',0))" 2>/dev/null)
weekly=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('seven_day',{}).get('utilization',0))" 2>/dev/null)
resets_at=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('five_hour',{}).get('resets_at',''))" 2>/dev/null)

# Default values if parsing failed
session=${session:-0}
weekly=${weekly:-0}

# Determine class based on max usage
max_usage=$(echo "$session $weekly" | awk '{print ($1>$2)?$1:$2}')

if (( $(echo "$max_usage >= 90" | bc -l) )); then
    class="critical"
    icon="🔴"
elif (( $(echo "$max_usage >= 75" | bc -l) )); then
    class="warning"
    icon="⚠️"
else
    class="normal"
    icon="✓"
fi

# Format text
text=$(printf "%s S:%.0f%% W:%.0f%%" "$icon" "$session" "$weekly")

# Format tooltip
tooltip=$(printf "Session: %.1f%%\nWeekly: %.1f%%\nResets: %s" "$session" "$weekly" "$resets_at")

# Output Waybar JSON
printf '{"text": "%s", "class": "%s", "tooltip": "%s"}\n' "$text" "$class" "$tooltip"
