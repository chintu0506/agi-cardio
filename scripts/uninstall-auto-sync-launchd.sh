#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script supports macOS only."
  exit 1
fi

LABEL="${AUTO_SYNC_LABEL:-com.agi-cardio.autosync}"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "Auto-sync launch agent removed."
echo "Label: $LABEL"
