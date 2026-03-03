#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script supports macOS only."
  exit 1
fi

LABEL="${AUTO_SYNC_LABEL:-com.agi-cardio.autosync}"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [ ! -f "$PLIST_PATH" ]; then
  echo "Launch agent status: not installed"
  exit 0
fi

if launchctl print "gui/$(id -u)/${LABEL}" >/tmp/agi_autosync_launchd_status.$$ 2>/dev/null; then
  pid="$(awk '/pid =/{print $3; exit}' /tmp/agi_autosync_launchd_status.$$)"
  last_exit="$(awk '/last exit code =/{print $5; exit}' /tmp/agi_autosync_launchd_status.$$)"
  rm -f /tmp/agi_autosync_launchd_status.$$
  echo "Launch agent status: installed and loaded"
  echo "Label: $LABEL"
  echo "PID: ${pid:--}"
  echo "Last exit code: ${last_exit:--}"
else
  rm -f /tmp/agi_autosync_launchd_status.$$
  echo "Launch agent status: installed but not loaded"
  echo "Label: $LABEL"
fi
