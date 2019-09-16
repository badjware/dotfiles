# show file preview on CTRL+T
export FZF_DEFAULT_OPTS="--height 90%"
export FZF_CTRL_T_OPTS="--preview '([[ -d {} ]] && lsd --color always --icon always --tree --depth 3 {} || highlight -O ansi -l {} || (file {} | grep -q text && cat {} || od -A x -t xz -v {})) 2>/dev/null | head -200'"
export FZF_ALT_C_OPTS="$FZF_CTRL_T_OPTS"

# Use tmux pane if available
export FZF_TMUX=1
export FZF_TMUX_HEIGHT=90%

# attach some extra options to path and dir completion
eval "_$(declare -f _fzf_path_completion)"
_fzf_path_completion() {
    FZF_DEFAULT_OPTS="$FZF_DEFAULT_OPTS $FZF_CTRL_T_OPTS" __fzf_path_completion "$1" "$2"
}

eval "_$(declare -f _fzf_dir_completion)"
_fzf_dir_completion() {
    FZF_DEFAULT_OPTS="$FZF_DEFAULT_OPTS $FZF_CTRL_T_OPTS" __fzf_dir_completion "$1" "$2"
}

# Remove duplicate when using Ctrl+R
# https://github.com/junegunn/fzf/issues/626
__fzf_history__() (
    local line
    shopt -u nocaseglob nocasematch
    line=$(
    HISTTIMEFORMAT= history | tac | sort --key=2.1 -bus | sort -n |
    FZF_DEFAULT_OPTS="--height ${FZF_TMUX_HEIGHT:-40%} $FZF_DEFAULT_OPTS --tac -n2..,.. --tiebreak=index --bind=ctrl-r:toggle-sort $FZF_CTRL_R_OPTS +m" $(__fzfcmd) |
    command grep '^ *[0-9]') &&
    if [[ $- =~ H ]]; then
        sed 's/^ *\([0-9]*\)\** .*/!\1/' <<< "$line"
    else
        sed 's/^ *\([0-9]*\)\** *//' <<< "$line"
    fi
)
