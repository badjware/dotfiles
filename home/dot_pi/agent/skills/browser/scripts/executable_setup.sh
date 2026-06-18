#!/usr/bin/env bash
# Launches Chrome with remote debugging on port 9222.
# Safe to re-run: kills any existing instance first.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "ERROR: WAYLAND_DISPLAY is unset." >&2
  exit 1
fi

PORT=9222
BASE_DIR="/tmp/browser-skill"
PROFILE_DIR="${BASE_DIR}/profile"

# Kill any existing instance bound to this port
if pkill -f -- "--remote-debugging-port=${PORT}" &>/dev/null 2>&1; then
  echo "killing existing Chrome on port ${PORT}"
  sleep 1
fi

mkdir -p "${PROFILE_DIR}"

google-chrome \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  --disable-features=PasswordManager,Geolocation \
  --disable-notifications \
  &>"${BASE_DIR}/chrome.log" &

echo "waiting for Chrome to be ready..."
for i in $(seq 1 20); do
  if curl -sf "http://localhost:${PORT}/json/version" &>/dev/null; then
    echo "Chrome is ready on port ${PORT}"
    node "${SKILL_DIR}/scripts/dialog-handler.js" >>${BASE_DIR}/chrome.log 2>&1 &
    exit 0
  fi
  sleep 0.5
done

echo "ERROR: Chrome did not start in time. Check ${BASE_DIR}/chrome.log" >&2
exit 1
