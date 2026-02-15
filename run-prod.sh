#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker is required."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "❌ Docker Compose (v2) is required."
  exit 1
fi

echo "🚀 Starting AGI CardioSense in production mode (Docker Compose)..."
docker compose up -d --build

echo ""
echo "✅ Services started:"
echo "   Frontend: http://localhost:8080"
echo "   Backend:  http://localhost:5000/api/health"
echo "   Ready:    http://localhost:5000/api/ready"
echo ""
echo "Useful commands:"
echo "   docker compose ps"
echo "   docker compose logs -f"
echo "   docker compose down"
