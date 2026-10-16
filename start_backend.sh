#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Locate python/uvicorn across possible venv locations or system
if [ -f "$SCRIPT_DIR/.venv/bin/uvicorn" ]; then
  UVICORN_BIN="$SCRIPT_DIR/.venv/bin/uvicorn"
elif [ -f "$SCRIPT_DIR/india-travel-safety/.venv/bin/uvicorn" ]; then
  UVICORN_BIN="$SCRIPT_DIR/india-travel-safety/.venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  UVICORN_BIN="uvicorn"
elif [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
  UVICORN_BIN="$SCRIPT_DIR/.venv/bin/python3 -m uvicorn"
elif [ -f "$SCRIPT_DIR/india-travel-safety/.venv/bin/python3" ]; then
  UVICORN_BIN="$SCRIPT_DIR/india-travel-safety/.venv/bin/python3 -m uvicorn"
else
  UVICORN_BIN="python3 -m uvicorn"
fi

echo "Starting India Travel Safety Backend on http://localhost:8000..."
PYTHONPATH=backend $UVICORN_BIN api.main:app --host 0.0.0.0 --port 8000 --reload
