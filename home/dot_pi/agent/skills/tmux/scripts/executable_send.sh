#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

newline=true
if [[ ${1:-} == "-n" ]]; then
  newline=false
  shift
fi
[[ $# -eq 1 ]] || fail "usage: send.sh [-n] text"
load_pane

tmux send-keys -t "$TARGET" -l -- "$1"
if "$newline"; then
  sleep 1
  tmux send-keys -t "$TARGET" Enter
fi
