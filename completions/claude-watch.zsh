#compdef claude-watch
# Zsh completion for claude-watch
# Installation:
#   Add to ~/.zshrc before compinit:
#     fpath=(/path/to/completions $fpath)
#   Or copy to a directory in your $fpath (e.g., /usr/local/share/zsh/site-functions/)
#   Then run: autoload -Uz compinit && compinit

_claude_watch() {
    local -a opts

    opts=(
        '(-h --help)'{-h,--help}'[Show help message and exit]'
        '(-j --json)'{-j,--json}'[Output raw JSON instead of formatted view]'
        '(-a --analytics)'{-a,--analytics}'[Show detailed analytics with historical trends]'
        '(-s --setup)'{-s,--setup}'[Run interactive setup wizard]'
        '(-c --config)'{-c,--config}'[Show current configuration]'
        '--no-color[Disable colored output]'
        '--no-record[Do not record this fetch to history]'
        '--cache-ttl[Cache TTL in seconds]:seconds:(30 60 120 300)'
    )

    _arguments -s -S $opts
}

_claude_watch "$@"

# Also complete for ccw alias
compdef _claude_watch ccw
