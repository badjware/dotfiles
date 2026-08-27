#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 1 ]] || fail "usage: key.sh key"
load_pane
tmux send-keys -t "$TARGET" "$1"
