#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

cleanup() {
  echo ""
  echo "Shutting down servers..."
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "========================================================="
echo "  Starting India Travel Safety Platform (Backend + Web)  "
echo "========================================================="

# Start backend in background
./start_backend.sh &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend on http://localhost:8000..."
until curl -s http://localhost:8000/v1/health >/dev/null 2>&1; do
  sleep 0.5
done
echo "Backend is ready!"

# Start frontend
./start_frontend.sh
