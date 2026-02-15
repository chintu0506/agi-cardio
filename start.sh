#!/bin/bash
# ================================================================
# AGI-Driven Intelligent Cardiovascular Diagnostic System v2.0
# ================================================================
set -e
cd "$(dirname "$0")"

# Load local environment overrides for OTP/email/SMS providers.
if [ -f ".env" ]; then
  set -a
  . ".env"
  set +a
fi
if [ -f "backend/.env" ]; then
  set -a
  . "backend/.env"
  set +a
fi

echo ""
echo "  ♥  AGI CardioSense — Intelligent Cardiovascular Diagnostics v2.0"
echo "  ──────────────────────────────────────────────────────────────────"
echo "  Ensemble AI · Explainable Reasoning · Conversational Assistant"
echo ""

if ! command -v python3 &>/dev/null; then echo "❌ Python 3 required"; exit 1; fi
if ! command -v npm &>/dev/null; then echo "❌ npm (Node.js) required for frontend"; exit 1; fi

is_port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

pick_free_port() {
  local port="$1"
  local max_tries="${2:-20}"
  local i=0
  while [ "$i" -lt "$max_tries" ]; do
    if ! is_port_in_use "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
    i=$((i + 1))
  done
  return 1
}

# Clear stale backend from prior crashed runs
pkill -f "python3 app.py" 2>/dev/null || true

# Train models if not present
if [ ! -f "backend/models/master_model.pkl" ]; then
  echo "  🧬  Training 5-model AGI ensemble (first run, ~30s)..."
  (cd backend && python3 train_model.py)
  echo ""
fi

# Start backend
BACKEND_PORT="$(pick_free_port 5000 40)" || { echo "❌ Could not find a free backend port"; exit 1; }
echo "  🚀  Starting AGI API on http://localhost:${BACKEND_PORT}"
(cd backend && AGI_BACKEND_HOST=127.0.0.1 AGI_BACKEND_PORT="$BACKEND_PORT" python3 app.py > /tmp/agi_backend.log 2>&1) & BPID=$!
sleep 3

if kill -0 $BPID 2>/dev/null; then
  echo "  ✅  Backend running (PID $BPID)"
else
  echo "  ❌  Backend failed. Check: /tmp/agi_backend.log"
  cat /tmp/agi_backend.log; exit 1
fi

echo ""
echo "  📡  API Endpoints:"
echo "      GET  /api/health        — System status"
echo "      GET  /api/model-info    — Model metadata"
echo "      POST /api/predict       — Full AGI diagnosis (21 features)"
echo "      POST /api/chat          — Medical AI assistant"
echo "      GET  /api/sample-cases  — 4 pre-built patient profiles"
echo "      GET  /api/ecg-realtime  — ECG signal generation"
echo ""

# Ensure frontend deps exist
if [ ! -d "frontend/node_modules" ]; then
  echo "  📦  Installing frontend dependencies..."
  (cd frontend && npm ci)
fi

# Start frontend dev server (Vite)
FRONTEND_PORT="$(pick_free_port 8080 40)" || { echo "❌ Could not find a free frontend port"; kill $BPID 2>/dev/null||true; exit 1; }
API_BASE="http://127.0.0.1:${BACKEND_PORT}"
echo "  🚀  Starting frontend (Vite) on http://localhost:${FRONTEND_PORT}"
(cd frontend && VITE_API_BASE="$API_BASE" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" > /tmp/agi_frontend.log 2>&1) & FPID=$!
sleep 3

if kill -0 $FPID 2>/dev/null; then
  echo "  ✅  Frontend running (PID $FPID)"
else
  echo "  ❌  Frontend failed. Check: /tmp/agi_frontend.log"
  cat /tmp/agi_frontend.log; kill $BPID 2>/dev/null||true; exit 1
fi

echo "  🌐  Frontend: http://localhost:${FRONTEND_PORT}"
echo "  🔗  API Base: ${API_BASE}"
echo ""
echo "  Pages: Home | Diagnose | Results (6 tabs) | AI Assistant | About"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

cleanup(){
  echo ""
  echo "  🛑  Stopping..."
  kill $BPID $FPID 2>/dev/null || true
  pkill -P $FPID 2>/dev/null || true
  echo "  👋  Done."
}
trap cleanup EXIT INT TERM
wait
