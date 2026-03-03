#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.autosync.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "Auto sync is not running."
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [ -z "$pid" ]; then
  rm -f "$PID_FILE"
  echo "Auto sync pid file was empty. Cleaned up."
  exit 0
fi

if kill -0 "$pid" >/dev/null 2>&1; then
  kill "$pid"
  echo "Stopped auto sync (PID $pid)."
else
  echo "No running process for PID $pid. Cleaned up pid file."
fi

rm -f "$PID_FILE"
