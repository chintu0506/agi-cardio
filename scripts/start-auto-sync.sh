#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.autosync.pid"
LOG_FILE="$ROOT_DIR/.autosync.log"
SYNC_SCRIPT="$ROOT_DIR/scripts/auto-sync.sh"

if [ ! -x "$SYNC_SCRIPT" ]; then
  echo "Auto sync script not executable: $SYNC_SCRIPT"
  exit 1
fi

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" >/dev/null 2>&1; then
    echo "Auto sync already running (PID $old_pid)."
    exit 0
  fi
fi

nohup "$SYNC_SCRIPT" >>"$LOG_FILE" 2>&1 &
new_pid="$!"
echo "$new_pid" > "$PID_FILE"

echo "Auto sync started (PID $new_pid)."
echo "Logs: $LOG_FILE"
