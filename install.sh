#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOCAL_BIN_DIR="${HOME}/.local/bin"

add_local_bin_to_path() {
  if [ -d "$LOCAL_BIN_DIR" ] && [[ ":$PATH:" != *":$LOCAL_BIN_DIR:"* ]]; then
    export PATH="$LOCAL_BIN_DIR:$PATH"
  fi
}

install_uv() {
  echo "    Installing uv..."

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "    [ERROR] curl or wget is required to install uv automatically"
    return 1
  fi

  add_local_bin_to_path
  command -v uv >/dev/null 2>&1
}

check_uv() {
  echo "  uv:"
  if command -v uv >/dev/null 2>&1; then
    uv --version | sed 's/^/    /'
    return
  fi

  echo "    [NOT INSTALLED]"
  if ! install_uv; then
    echo "    [ERROR] Failed to install uv automatically"
    echo "    Please install it manually and rerun ./install.sh"
    exit 1
  fi

  echo "    [OK] uv installed"
}

check_node() {
  echo "  Node.js:"
  if command -v node >/dev/null 2>&1; then
    node --version | sed 's/^/    /'
    return
  fi

  echo "    [NOT INSTALLED] Please install Node.js 18+ and rerun ./install.sh"
  exit 1
}

install_backend() {
  echo
  echo "================================================"
  echo "        Installing Backend Dependencies"
  echo "================================================"
  echo

  cd "$BACKEND_DIR"
  echo "[INSTALL] Syncing Python packages with uv..."
  uv sync

  echo "[CHECK] Verifying backend runtime dependencies..."
  if ! uv run python -c "import fastapi, uvicorn, annotated_doc" >/dev/null 2>&1; then
    echo "[ERROR] Backend runtime dependency verification failed"
    echo "[TIP] Retry: cd backend && uv sync"
    exit 1
  fi
}

install_frontend() {
  local reinstall_choice="n"

  echo
  echo "================================================"
  echo "       Installing Frontend Dependencies"
  echo "================================================"
  echo

  cd "$FRONTEND_DIR"
  if [ -d "node_modules" ]; then
    read -r -p "node_modules exists. Reinstall? [y/N]: " reinstall_choice
    if [[ "$reinstall_choice" =~ ^[Yy]$ ]]; then
      echo "[CLEAN] Removing old node_modules..."
      rm -rf node_modules
    else
      echo "[SKIP] Keeping existing dependencies"
      return
    fi
  fi

  echo "[INSTALL] npm packages (this may take a few minutes)..."
  npm install
}

add_local_bin_to_path

echo "================================================"
echo "       OKX Quantitative Trading System"
echo "            Install Dependencies"
echo "================================================"
echo

echo "[CHECK] System environment..."
echo
check_uv
check_node
install_backend
install_frontend

echo
echo "================================================"
echo "           Installation Complete"
echo "================================================"
echo
echo "  All dependencies installed successfully."
echo
echo "  Next steps:"
echo "    1. Configure config/.env if needed"
echo "    2. Run ./start.sh to start the system"
