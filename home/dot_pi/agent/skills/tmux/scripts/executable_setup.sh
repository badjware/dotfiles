#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

require_tmux
if [[ -f "$STATE_FILE" ]]; then
  load_pane
  "$SCRIPT_DIR/status.sh"
  exit 0
fi

session="pi-tmux-${USER:-agent}-$$"
tmux new-session -d -s "$session" -n shell
target=$(tmux list-panes -t "$session" -F '#{session_name}:#{window_index}.#{pane_index}' | head -n 1)
[[ -n "$target" ]] || fail "could not determine the created pane"
write_state owned "$target" "$session"
"$SCRIPT_DIR/status.sh"
