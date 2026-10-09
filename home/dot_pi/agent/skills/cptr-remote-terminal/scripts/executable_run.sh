#!/bin/bash
# Type a command into the active cptr terminal, press Enter, wait, and print the tail of the screen.
# Usage: run.sh '<command>' [sleep_seconds=2] [tail_lines=40]
# Pass an empty command to only re-read the screen (polling a long-running command).
set -u
BROWSER=$HOME/.pi/agent/skills/browser/scripts
S="role=textbox[name='Terminal input']"
if [ -n "$1" ]; then
  "$BROWSER/key.js" Control+u "$S" >/dev/null
  "$BROWSER/type.js" "$S" "$1" >/dev/null
  "$BROWSER/key.js" Enter "$S" >/dev/null
fi
sleep "${2:-2}"
"$BROWSER/text.js" "main" | tail -n "${3:-40}"
