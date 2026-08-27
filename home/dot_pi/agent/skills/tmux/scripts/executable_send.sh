#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

newline=true
stdin=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n)
      newline=false
      shift
      ;;
    --stdin)
      stdin=true
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      fail "usage: send.sh [-n] [--stdin] [text]"
      ;;
    *)
      break
      ;;
  esac
done

if "$stdin"; then
  [[ $# -eq 0 ]] || fail "usage: send.sh [-n] --stdin"
else
  [[ $# -eq 1 ]] || fail "usage: send.sh [-n] [--stdin] text"
fi

load_pane
if "$stdin"; then
  buffer="pi-tmux-send-$$"
  tmux load-buffer -b "$buffer" -
  tmux paste-buffer -d -b "$buffer" -t "$TARGET"
else
  tmux send-keys -t "$TARGET" -l -- "$1"
fi

if "$newline"; then
  sleep 1
  tmux send-keys -t "$TARGET" Enter
  sleep 1
fi
