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
    opts="--help -h --json -j --analytics -a --setup -s --config -c --no-color --no-record --cache-ttl --version -V --verbose -v --quiet -q --dry-run --update -U"

    # Handle options that require arguments
    case "${prev}" in
        --cache-ttl)
            # Suggest common TTL values in seconds
            COMPREPLY=($(compgen -W "30 60 120 300" -- "${cur}"))
            return 0
            ;;
        --update|-U)
            # Suggest check option
            COMPREPLY=($(compgen -W "check" -- "${cur}"))
            return 0
            ;;
        --config|-c)
            # Suggest config subcommands
            COMPREPLY=($(compgen -W "show reset set" -- "${cur}"))
            return 0
            ;;
        set)
            # Check if we're in a --config context
            for ((i=1; i < COMP_CWORD; i++)); do
                if [[ "${COMP_WORDS[i]}" == "--config" || "${COMP_WORDS[i]}" == "-c" ]]; then
                    # Suggest config keys
                    COMPREPLY=($(compgen -W "admin_api_key auto_collect collect_interval_hours setup_completed shell_completion_installed subscription_plan use_admin_api" -- "${cur}"))
                    return 0
                fi
            done
            ;;
        subscription_plan)
            # Suggest subscription plan values
            COMPREPLY=($(compgen -W "pro max_5x max_20x" -- "${cur}"))
            return 0
            ;;
        auto_collect|use_admin_api|setup_completed|shell_completion_installed)
            # Suggest boolean values
            COMPREPLY=($(compgen -W "true false" -- "${cur}"))
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
