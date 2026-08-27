#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
source "$SCRIPT_DIR/common.sh"
load_pane

printf 'Controlled pane: %s\n' "$TARGET"
printf 'Mode: %s\n' "$MODE"
printf 'To monitor: tmux attach -t %s\n' "${TARGET%%:*}"
