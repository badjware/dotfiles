#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

lines=${1:-200}
[[ "$lines" =~ ^[0-9]+$ ]] || fail "line count must be a non-negative integer"
load_pane
tmux capture-pane -p -J -t "$TARGET" -S "-$lines"
