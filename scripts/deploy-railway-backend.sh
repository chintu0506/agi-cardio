#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RAILWAY_CMD=(npx --yes @railway/cli)
SERVICE_NAME="${RAILWAY_SERVICE_NAME:-agi-cardio-backend}"
VOLUME_PATH="${RAILWAY_VOLUME_PATH:-/data}"
OTP_PREVIEW="${OTP_ALLOW_PREVIEW:-true}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required."
  exit 1
fi

if ! "${RAILWAY_CMD[@]}" whoami >/dev/null 2>&1; then
  echo "Railway login required."
  echo "Run: npx --yes @railway/cli login --browserless"
  exit 1
fi

if ! "${RAILWAY_CMD[@]}" status --json >/dev/null 2>&1; then
  echo "No Railway project linked in this folder."
  echo "Run one of:"
  echo "  npx --yes @railway/cli init -n agi-cardio"
  echo "  npx --yes @railway/cli link --project <project-id>"
  exit 1
fi

services_json="$("${RAILWAY_CMD[@]}" service status --all --json 2>/dev/null || echo '[]')"
has_service="$(printf '%s' "$services_json" | jq -r --arg svc "$SERVICE_NAME" 'if type=="array" then any(.[]; ((.name // .service // .serviceName // .id // "") == $svc)) else false end')"
if [ "$has_service" != "true" ]; then
  echo "Creating Railway service: $SERVICE_NAME"
  "${RAILWAY_CMD[@]}" add --service "$SERVICE_NAME" >/dev/null
fi

"${RAILWAY_CMD[@]}" service link "$SERVICE_NAME" >/dev/null 2>&1 || true

echo "Setting backend variables..."
"${RAILWAY_CMD[@]}" variable set --service "$SERVICE_NAME" --skip-deploys \
  "AGI_DATA_DIR=$VOLUME_PATH" \
  "AGI_BACKEND_HOST=0.0.0.0" \
  "AGI_BACKEND_PORT=5000" \
  "OTP_ALLOW_PREVIEW=$OTP_PREVIEW" >/dev/null

volumes_json="$("${RAILWAY_CMD[@]}" volume --service "$SERVICE_NAME" list --json 2>/dev/null || echo '[]')"
volume_id="$(printf '%s' "$volumes_json" | jq -r --arg p "$VOLUME_PATH" 'if type=="array" then (map(select((.mountPath // .mount_path // "") == $p))[0].id // "") else "" end')"
if [ -z "$volume_id" ]; then
  echo "Creating Railway volume at mount path: $VOLUME_PATH"
  new_volume="$("${RAILWAY_CMD[@]}" volume --service "$SERVICE_NAME" add --mount-path "$VOLUME_PATH" --json)"
  volume_id="$(printf '%s' "$new_volume" | jq -r '.id // empty')"
fi
if [ -n "$volume_id" ]; then
  "${RAILWAY_CMD[@]}" volume --service "$SERVICE_NAME" attach --volume "$volume_id" -y >/dev/null 2>&1 || true
fi

echo "Deploying backend service from ./backend ..."
"${RAILWAY_CMD[@]}" up backend --service "$SERVICE_NAME" --path-as-root -d

domain_json="$("${RAILWAY_CMD[@]}" domain --service "$SERVICE_NAME" --port 5000 --json 2>/dev/null || echo '{}')"
backend_domain="$(printf '%s' "$domain_json" | jq -r 'if type=="array" then (.[0].domain // .[0].url // "") else (.domain // .url // "") end')"

if [ -n "$backend_domain" ]; then
  if [[ "$backend_domain" =~ ^https?:// ]]; then
    backend_url="$backend_domain"
  else
    backend_url="https://$backend_domain"
  fi
  echo "Backend deployed."
  echo "BACKEND_URL=$backend_url"
  echo "Next: ./scripts/connect-netlify-to-backend.sh \"$backend_url\""
else
  echo "Backend deployed. Could not auto-read public domain."
  echo "Generate one with:"
  echo "  npx --yes @railway/cli domain --service \"$SERVICE_NAME\" --port 5000"
fi
