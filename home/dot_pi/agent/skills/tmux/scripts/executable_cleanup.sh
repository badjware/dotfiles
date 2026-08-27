#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

source "$STATE_FILE"
rm -f "$STATE_FILE"
rmdir "$STATE_DIR" 2>/dev/null || true

if [[ ${MODE:-} == owned && -n ${SESSION:-} ]] && command -v tmux >/dev/null 2>&1; then
  tmux kill-session -t "$SESSION" 2>/dev/null || true
fi
