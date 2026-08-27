#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 1 ]] || fail "usage: attach.sh session:window.pane"
require_tmux
[[ ! -f "$STATE_FILE" ]] || fail "a pane is already controlled; run cleanup.sh first"
pane_exists "$1" || fail "pane does not exist: $1"
write_state attached "$1"
"$SCRIPT_DIR/status.sh"
