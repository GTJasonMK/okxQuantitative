#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

require_command() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    return
  fi

  echo "[ERROR] $command_name not found"
  exit 1
}

echo "================================================"
echo "       OKX Quantitative Trading System"
echo "================================================"
echo

require_command uv
require_command node

echo "[1/2] Checking backend..."
cd "$BACKEND_DIR"
if ! uv run python -c "import fastapi, uvicorn, annotated_doc" >/dev/null 2>&1; then
  echo "[ERROR] Backend runtime dependencies are incomplete"
  echo "        Fix: cd backend && uv sync"
  exit 1
fi

echo "[2/2] Checking frontend..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules/electron" ]; then
  echo "[ERROR] Frontend dependencies are missing"
  echo "        Fix: cd frontend && npm install"
  exit 1
fi

echo
echo "[START] Single-window dev runtime..."
cd "$PROJECT_ROOT"
node tools/startDevRuntime.cjs
