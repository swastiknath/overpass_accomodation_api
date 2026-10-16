#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_UVICORN="$SCRIPT_DIR/india-travel-safety/.venv/bin/uvicorn"

if [ ! -f "$VENV_UVICORN" ]; then
  echo "Error: Virtual environment not found at $VENV_UVICORN"
  exit 1
fi

echo "Starting India Travel Safety Backend on http://localhost:8000..."
PYTHONPATH=backend "$VENV_UVICORN" api.main:app --host 0.0.0.0 --port 8000 --reload
