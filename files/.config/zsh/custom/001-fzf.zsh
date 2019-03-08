# show file preview on CTRL+T
export FZF_DEFAULT_OPTS="--height 90% --preview '([[ -d {} ]] && lsd --color always --icon always --tree --depth 3 {} || highlight -O ansi -l {} || (file {} | grep -q text && cat {} || od -A x -t xz -v {})) 2>/dev/null | head -200'"

# Use tmux pane if available
export FZF_TMUX=1
export FZF_TMUX_HEIGHT=90%

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
