#!/usr/bin/env bash
# Kills Chrome and deletes the persistent profile (cookies, cache, login sessions).
set -euo pipefail

PROFILE_DIR="${HOME}/.cache/browser-skill/profile"

if pkill -9 -f 'chrome' &>/dev/null 2>&1; then
  echo "killed Chrome"
fi

if [[ -d "${PROFILE_DIR}" ]]; then
  rm -rf "${PROFILE_DIR}"
  echo "deleted profile at ${PROFILE_DIR}"
else
  echo "no profile found at ${PROFILE_DIR}"
fi
