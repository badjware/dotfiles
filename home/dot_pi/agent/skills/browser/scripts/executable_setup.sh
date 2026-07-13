#!/usr/bin/env bash
# Launches Chrome with remote debugging on port 9222.
# Idempotent: if Chrome is already running on this port, this is a no-op.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "ERROR: WAYLAND_DISPLAY is unset." >&2
  exit 1
fi

PORT=9222
BASE_DIR="/tmp/browser-skill"
PROFILE_DIR="${HOME}/.cache/browser-skill/profile"
mkdir -p "${BASE_DIR}" "${PROFILE_DIR}"

if curl -sf "http://localhost:${PORT}/json/version" &>/dev/null; then
  echo "Chrome is already running on port ${PORT}, doing nothing"
  exit 0
fi

# Remove stale profile lock files left by a previous run or container
rm -f "${PROFILE_DIR}"/Singleton*

LANDING_URL="${BROWSER_LANDING_URL:-https://duckduckgo.com}"

chrome_args=(
  --remote-debugging-port="${PORT}"
  --user-data-dir="${PROFILE_DIR}"
  --no-first-run
  --no-default-browser-check
  --disable-features=PasswordManager,Geolocation
  --disable-notifications
  --disable-blink-features=AutomationControlled
)
google-chrome "${chrome_args[@]}" &>"${BASE_DIR}/chrome.log" &

echo "waiting for Chrome to be ready..."
for i in $(seq 1 20); do
  if curl -sf "http://localhost:${PORT}/json/version" &>/dev/null; then
    echo "Chrome is ready on port ${PORT}"
    node "${SKILL_DIR}/scripts/dialog-handler.js" >>${BASE_DIR}/chrome.log 2>&1 &
    node "${SKILL_DIR}/scripts/humanizer.js" >>${BASE_DIR}/chrome.log 2>&1 &
    exec "${SKILL_DIR}/scripts/navigate.js" "${LANDING_URL}"
  fi
  sleep 0.5
done

echo "ERROR: Chrome did not start in time. Check ${BASE_DIR}/chrome.log" >&2
exit 1
