#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"

[[ $# -ge 1 && $# -le 2 ]] || fail "usage: wait.sh regex [timeout-seconds]"
pattern=$1
timeout=${2:-15}
[[ "$timeout" =~ ^[0-9]+$ ]] || fail "timeout must be a non-negative integer"
load_pane

for ((elapsed = 0; elapsed <= timeout; elapsed++)); do
  if tmux capture-pane -p -J -t "$TARGET" -S -1000 | rg -q -- "$pattern"; then
    exit 0
  fi
  (( elapsed == timeout )) && break
  sleep 1
done

printf 'tmux skill: timed out waiting for %q in %s\n' "$pattern" "$TARGET" >&2
tmux capture-pane -p -J -t "$TARGET" -S -200 >&2
exit 1
