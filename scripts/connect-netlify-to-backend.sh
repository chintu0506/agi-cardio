#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

NETLIFY_SITE_ID="${NETLIFY_SITE_ID:-2dbb0bfa-4f54-42c6-85f9-fc657ab8d6c9}"
BACKEND_URL="${1:-${VITE_API_BASE:-}}"

if [ -z "$BACKEND_URL" ]; then
  echo "Usage: $0 https://<backend-domain>"
  exit 1
fi

BACKEND_URL="${BACKEND_URL%/}"

echo "Setting Netlify VITE_API_BASE=$BACKEND_URL"
npx --yes netlify-cli env:set VITE_API_BASE "$BACKEND_URL" --context production --force >/dev/null

echo "Triggering Netlify production build..."
npx --yes netlify-cli api createSiteBuild --data "{\"site_id\":\"${NETLIFY_SITE_ID}\"}" >/dev/null

echo "Done."
echo "Netlify frontend now points to: $BACKEND_URL"
