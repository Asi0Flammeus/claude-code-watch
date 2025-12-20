# Fish completion for claude-watch
# Installation:
#   Copy to ~/.config/fish/completions/claude-watch.fish
#   Or: cp claude-watch.fish ~/.config/fish/completions/

# Disable file completions for claude-watch
complete -c claude-watch -f

# Options
complete -c claude-watch -s h -l help -d 'Show help message and exit'
complete -c claude-watch -s j -l json -d 'Output raw JSON instead of formatted view'
complete -c claude-watch -s a -l analytics -d 'Show detailed analytics with historical trends'
complete -c claude-watch -s s -l setup -d 'Run interactive setup wizard'
complete -c claude-watch -s c -l config -d 'Show current configuration'
complete -c claude-watch -l no-color -d 'Disable colored output'
complete -c claude-watch -l no-record -d 'Do not record this fetch to history'
complete -c claude-watch -l cache-ttl -d 'Cache TTL in seconds' -x -a '30 60 120 300'
complete -c claude-watch -s V -l version -d 'Show version and system information'
complete -c claude-watch -s v -l verbose -d 'Show detailed output including timing and cache info'
complete -c claude-watch -s q -l quiet -d 'Suppress all output except errors'
complete -c claude-watch -l dry-run -d 'Show what would be done without making API calls'
complete -c claude-watch -s U -l update -d 'Check for and install updates' -x -a 'check'

# Also complete for ccw alias
complete -c ccw -f
complete -c ccw -s h -l help -d 'Show help message and exit'
complete -c ccw -s j -l json -d 'Output raw JSON instead of formatted view'
complete -c ccw -s a -l analytics -d 'Show detailed analytics with historical trends'
complete -c ccw -s s -l setup -d 'Run interactive setup wizard'
complete -c ccw -s c -l config -d 'Show current configuration'
complete -c ccw -l no-color -d 'Disable colored output'
complete -c ccw -l no-record -d 'Do not record this fetch to history'
complete -c ccw -l cache-ttl -d 'Cache TTL in seconds' -x -a '30 60 120 300'
complete -c ccw -s V -l version -d 'Show version and system information'
complete -c ccw -s v -l verbose -d 'Show detailed output including timing and cache info'
complete -c ccw -s q -l quiet -d 'Suppress all output except errors'
complete -c ccw -l dry-run -d 'Show what would be done without making API calls'
complete -c ccw -s U -l update -d 'Check for and install updates' -x -a 'check'
