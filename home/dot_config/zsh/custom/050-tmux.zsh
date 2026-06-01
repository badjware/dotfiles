# Smart `tmux`: bare invocation attaches by cwd, or creates a session named
# after the cwd basename (`~` for $HOME). Anything with args passes through.
tmux() {
    if [[ $# -gt 0 || -n "$TMUX" ]]; then
        command tmux "$@"
        return
    fi

    local existing
    existing=$(command tmux list-sessions -F '#{session_path}:#{session_name}' 2>/dev/null \
        | awk -F: -v pwd="$PWD" '$1 == pwd {print $2; exit}')

    if [[ -n "$existing" ]]; then
        command tmux attach-session -t "=$existing"
        return
    fi

    local display_name internal_name
    if [[ "$PWD" == "$HOME" ]]; then
        display_name="~"
        internal_name="home"
    else
        display_name="${PWD:t}"
        internal_name="$display_name"
    fi

    local base_internal="$internal_name" base_display="$display_name" i=2
    while command tmux has-session -t="$internal_name" 2>/dev/null \
        || command tmux has-session -t="$display_name" 2>/dev/null; do
        internal_name="${base_internal}-${i}"
        display_name="${base_display}-${i}"
        ((i++))
    done

    command tmux new-session -s "$internal_name" -c "$PWD" \; rename-session "$display_name"
}

# Auto-launch on interactive shell, except from $HOME
if [[ -z "$TMUX" && $- == *i* && $- != *c* && -z "$NO_TMUX" && -z "$ZED_FILE" && "$PWD" != "$HOME" ]] \
    && command -v tmux >/dev/null; then
    tmux && exit
fi
