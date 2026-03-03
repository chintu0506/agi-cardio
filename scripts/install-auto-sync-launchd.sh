#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer supports macOS only."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYNC_SCRIPT="$ROOT_DIR/scripts/auto-sync.sh"
LABEL="${AUTO_SYNC_LABEL:-com.agi-cardio.autosync}"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_FILE="$ROOT_DIR/.autosync.log"
INTERVAL_SECONDS="${AUTO_SYNC_INTERVAL:-30}"
REMOTE_NAME="${AUTO_SYNC_REMOTE:-origin}"
BRANCH_NAME="${AUTO_SYNC_BRANCH:-$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD)}"

if [ ! -x "$SYNC_SCRIPT" ]; then
  echo "Auto sync script not executable: $SYNC_SCRIPT"
  exit 1
fi

if ! [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [ "$INTERVAL_SECONDS" -lt 5 ]; then
  echo "AUTO_SYNC_INTERVAL must be an integer >= 5."
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd '${ROOT_DIR}' &amp;&amp; AUTO_SYNC_INTERVAL='${INTERVAL_SECONDS}' AUTO_SYNC_REMOTE='${REMOTE_NAME}' AUTO_SYNC_BRANCH='${BRANCH_NAME}' '${SYNC_SCRIPT}' &gt;&gt; '${LOG_FILE}' 2&gt;&amp;1</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true

echo "Installed and started auto-sync launch agent."
echo "Label: $LABEL"
echo "Plist: $PLIST_PATH"
echo "Log: $LOG_FILE"
