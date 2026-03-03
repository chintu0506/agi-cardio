#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.autosync.pid"
LOG_FILE="$ROOT_DIR/.autosync.log"

if [ ! -f "$PID_FILE" ]; then
  echo "Auto sync status: stopped"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
  echo "Auto sync status: running (PID $pid)"
  echo "Log file: $LOG_FILE"
  exit 0
fi

echo "Auto sync status: stale pid file (cleaning up)"
rm -f "$PID_FILE"
