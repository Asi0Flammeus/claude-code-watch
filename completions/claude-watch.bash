# Bash completion for claude-watch
# Installation:
#   Add to ~/.bashrc:
#     source /path/to/completions/claude-watch.bash
#   Or copy to /etc/bash_completion.d/claude-watch

_claude_watch_completions() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # All available options
    opts="--help -h --json -j --analytics -a --setup -s --config -c --no-color --no-record --cache-ttl"

    # Handle options that require arguments
    case "${prev}" in
        --cache-ttl)
            # Suggest common TTL values in seconds
            COMPREPLY=($(compgen -W "30 60 120 300" -- "${cur}"))
            return 0
            ;;
    esac

    # Complete options
    if [[ "${cur}" == -* ]]; then
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
        return 0
    fi
}

complete -F _claude_watch_completions claude-watch
complete -F _claude_watch_completions ccw
