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
        '(-c --config)'{-c,--config}'[Configuration commands: show, reset, set KEY VALUE]:command:->config'
        '--no-color[Disable colored output]'
        '--no-record[Do not record this fetch to history]'
        '--cache-ttl[Cache TTL in seconds]:seconds:(30 60 120 300)'
        '(-V --version)'{-V,--version}'[Show version and system information]'
        '(-v --verbose)'{-v,--verbose}'[Show detailed output including timing and cache info]'
        '(-q --quiet)'{-q,--quiet}'[Suppress all output except errors]'
        '--dry-run[Show what would be done without making API calls]'
        '(-U --update)'{-U,--update}'[Check for and install updates]:mode:(check)'
    )

    _arguments -s -S $opts

    case "$state" in
        config)
            local -a config_cmds config_keys
            config_cmds=(
                'show:Display current configuration'
                'reset:Reset configuration to defaults'
                'set:Set a configuration value (KEY VALUE)'
            )
            config_keys=(
                'admin_api_key:Admin API key for organization usage'
                'auto_collect:Enable automatic data collection'
                'collect_interval_hours:Collection interval in hours'
                'setup_completed:Whether setup wizard has been run'
                'shell_completion_installed:Whether shell completion is installed'
                'subscription_plan:Subscription plan (pro, max_5x, max_20x)'
                'use_admin_api:Whether to use Admin API'
            )

            if (( CURRENT == 2 )); then
                _describe -t commands 'config command' config_cmds
            elif (( CURRENT == 3 )) && [[ ${words[2]} == "set" ]]; then
                _describe -t keys 'config key' config_keys
            elif (( CURRENT == 4 )) && [[ ${words[2]} == "set" ]]; then
                case "${words[3]}" in
                    subscription_plan)
                        _values 'plan' 'pro' 'max_5x' 'max_20x'
                        ;;
                    auto_collect|use_admin_api|setup_completed|shell_completion_installed)
                        _values 'boolean' 'true' 'false'
                        ;;
                    *)
                        _message 'value'
                        ;;
                esac
            fi
            ;;
    esac
}

_claude_watch "$@"

# Also complete for ccw alias
compdef _claude_watch ccw
