#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${TMPDIR:-/tmp}/pi-tmux-skill"
STATE_FILE="$STATE_DIR/pane"

fail() {
  printf 'tmux skill: %s\n' "$*" >&2
  exit 1
}

require_tmux() {
  command -v tmux >/dev/null 2>&1 || fail "tmux is not installed or not on PATH"
}

pane_exists() {
  tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index}' 2>/dev/null | rg -Fx -- "$1" >/dev/null
}

load_pane() {
  require_tmux
  [[ -f "$STATE_FILE" ]] || fail "no controlled pane; run setup.sh or attach.sh"
  # State is written only by this skill after tmux validates the target.
  source "$STATE_FILE"
  [[ -n "${TARGET:-}" && -n "${MODE:-}" ]] || fail "invalid pane state"
  pane_exists "$TARGET" || fail "controlled pane no longer exists; run cleanup.sh"
}

write_state() {
  local mode=$1
  local target=$2
  local session=${3:-}
  umask 077
  mkdir -p "$STATE_DIR"
  printf 'MODE=%q\nTARGET=%q\nSESSION=%q\n' "$mode" "$target" "$session" > "$STATE_FILE"
}
