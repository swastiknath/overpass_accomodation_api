#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  India Travel Safety & Hotel Intelligence Test Runner  "
echo "========================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Detect Python venv
VENV_PYTEST="$SCRIPT_DIR/india-travel-safety/.venv/bin/pytest"
if [ ! -f "$VENV_PYTEST" ]; then
  VENV_PYTEST="pytest"
fi

echo ""
echo ">>> [1/2] Running Backend Pytest Suite..."
PYTHONPATH=backend "$VENV_PYTEST" backend/tests/ -v

echo ""
echo ">>> [2/2] Running Frontend Vitest Suite..."
npm --prefix frontend run test

echo ""
echo "========================================================"
echo "  ALL TESTS PASSED SUCCESSFULLY!                        "
echo "========================================================"
