#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INTERVAL_SECONDS="${AUTO_SYNC_INTERVAL:-30}"
REMOTE_NAME="${AUTO_SYNC_REMOTE:-origin}"
BRANCH_NAME="${AUTO_SYNC_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
COMMIT_PREFIX="${AUTO_SYNC_COMMIT_PREFIX:-chore(auto-sync): laptop update}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required for auto sync."
  exit 1
fi

if ! [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [ "$INTERVAL_SECONDS" -lt 5 ]; then
  echo "AUTO_SYNC_INTERVAL must be an integer >= 5."
  exit 1
fi

if [ "$BRANCH_NAME" = "HEAD" ]; then
  echo "Detached HEAD is not supported. Checkout a branch first."
  exit 1
fi

if ! git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  echo "Remote '$REMOTE_NAME' not found."
  exit 1
fi

echo "Auto sync started on branch '$BRANCH_NAME' to remote '$REMOTE_NAME' every ${INTERVAL_SECONDS}s."
echo "Create .autosync.pause in repo root to temporarily pause syncing."

while true; do
  if [ -f "$ROOT_DIR/.autosync.pause" ]; then
    sleep "$INTERVAL_SECONDS"
    continue
  fi

  if [ -f "$ROOT_DIR/.git/MERGE_HEAD" ] || [ -d "$ROOT_DIR/.git/rebase-apply" ] || [ -d "$ROOT_DIR/.git/rebase-merge" ]; then
    sleep "$INTERVAL_SECONDS"
    continue
  fi

  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    if ! git diff --cached --quiet; then
      ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
      git commit -m "${COMMIT_PREFIX} ${ts}" >/dev/null 2>&1 || true
    fi

    if git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
      git push "$REMOTE_NAME" "$BRANCH_NAME" || true
    else
      git push -u "$REMOTE_NAME" "$BRANCH_NAME" || true
    fi
  fi

  sleep "$INTERVAL_SECONDS"
done
