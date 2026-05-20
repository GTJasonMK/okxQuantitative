#!/usr/bin/env bash
set -euo pipefail

FORCE=0
RESET_CONFIG=0
HAS_ERRORS=0

for arg in "$@"; do
  case "$arg" in
    --force|/force) FORCE=1 ;;
    --config|/config) RESET_CONFIG=1 ;;
    *)
      echo "[ERROR] Unknown argument: $arg"
      echo "Usage: ./reset.sh [--force] [--config]"
      exit 1
      ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DATA_DIR="$PROJECT_ROOT/data"
CONFIG_DIR="$PROJECT_ROOT/config"
LOGS_DIR="$PROJECT_ROOT/logs"
ENV_FILE="$CONFIG_DIR/.env"
FRONTEND_PACKAGE_FILE="$FRONTEND_DIR/package.json"
RUNTIME_CONFIG_FILES=(
  "$CONFIG_DIR/user_preferences.json"
  "$CONFIG_DIR/risk_control.json"
  "$CONFIG_DIR/market_alerts.json"
)
TREND_PATTERNS=(
  "$DATA_DIR/trend_research*.json"
  "$DATA_DIR/trend_research*.pt"
  "$DATA_DIR/*.tmp"
)
DATABASE_PATH=""
DATABASE_WAL=""
DATABASE_SHM=""
API_PORT=""
APP_PRODUCT_NAME=""
APP_PACKAGE_NAME=""
USER_DATA_DIR=""
USER_DATA_FALLBACK_DIR=""

strip_wrapping_quotes() {
  local value="$1"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then value="${value:1:${#value}-2}"; fi
  if [[ "$value" == \'*\' && "$value" == *\' ]]; then value="${value:1:${#value}-2}"; fi
  printf '%s' "$value"
}

read_env_value() {
  local target_key="$1"
  local line="" key="" value=""
  [ -f "$ENV_FILE" ] || return
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in ""|\#*) continue ;; esac
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    [ "$key" = "$target_key" ] && printf '%s' "$value" && return
  done < "$ENV_FILE"
}

resolve_database_path() {
  local database_path_raw=""
  database_path_raw="$(strip_wrapping_quotes "$(read_env_value DATABASE_PATH)")"
  API_PORT="$(strip_wrapping_quotes "$(read_env_value API_PORT)")"
  if [ -z "$database_path_raw" ]; then
    DATABASE_PATH="$DATA_DIR/market.db"
  elif [[ "$database_path_raw" = /* ]]; then
    DATABASE_PATH="$database_path_raw"
  else
    DATABASE_PATH="$PROJECT_ROOT/$database_path_raw"
  fi
  DATABASE_WAL="${DATABASE_PATH}-wal"
  DATABASE_SHM="${DATABASE_PATH}-shm"
}

load_app_names() {
  [ -f "$FRONTEND_PACKAGE_FILE" ] || return
  command -v node >/dev/null 2>&1 || return
  mapfile -t app_names < <(
    node -e "const pkg = require(process.argv[1]); console.log(pkg.productName || ''); console.log(pkg.name || '');" \
      "$FRONTEND_PACKAGE_FILE"
  )
  APP_PRODUCT_NAME="${app_names[0]:-}"
  APP_PACKAGE_NAME="${app_names[1]:-}"
}

resolve_user_data_dirs() {
  local config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
  [ -n "$APP_PRODUCT_NAME" ] && USER_DATA_DIR="$config_home/$APP_PRODUCT_NAME"
  if [ -n "$APP_PACKAGE_NAME" ] && [ "$APP_PACKAGE_NAME" != "$APP_PRODUCT_NAME" ]; then
    USER_DATA_FALLBACK_DIR="$config_home/$APP_PACKAGE_NAME"
  fi
}

preview_file() {
  local target="$1"
  [ -n "$target" ] || return
  if [ -f "$target" ]; then
    echo "     - $target [$(stat -c '%s' "$target") bytes]"
    return
  fi
  echo "     - $target [not found]"
}

preview_glob() {
  local pattern="$1" matched=0
  shopt -s nullglob
  for file in $pattern; do
    echo "     - $file"
    matched=1
  done
  shopt -u nullglob
  [ "$matched" -eq 1 ] || echo "     - $pattern [not found]"
}

preview_dir() {
  local target="$1"
  [ -n "$target" ] || return
  [ -d "$target" ] && echo "     - $target" && return
  echo "     - $target [not found]"
}

find_port_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null
    return
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser "${port}/tcp" 2>/dev/null | tr ' ' '\n' | sed '/^$/d'
    return
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null \
      | awk -F '[,= ]+' 'NR > 1 { for (i = 1; i <= NF; i += 1) if ($i == "pid") print $(i + 1) }'
  fi
}

kill_port() {
  local port="$1" pids="" pid=""
  pids="$(find_port_pids "$port" | sort -u || true)"
  [ -n "$pids" ] || return
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done <<< "$pids"
}

kill_repo_electron() {
  local pid=""
  command -v pgrep >/dev/null 2>&1 || return
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done < <(pgrep -f "$FRONTEND_DIR/node_modules/electron" || true)
}

mark_error() { HAS_ERRORS=1; }

delete_file() {
  local target="$1"
  [ -n "$target" ] || return
  if [ ! -e "$target" ]; then
    echo "    [SKIP] $target"
    return
  fi
  rm -f "$target" && echo "    [OK] Removed $target" && return
  echo "    [ERROR] Failed to remove $target"
  mark_error
}

delete_glob() {
  local pattern="$1" matched=0
  shopt -s nullglob
  for target in $pattern; do
    matched=1
    delete_file "$target"
  done
  shopt -u nullglob
  [ "$matched" -eq 1 ] || echo "    [SKIP] $pattern"
}

delete_dir() {
  local target="$1"
  [ -n "$target" ] || return
  if [ ! -d "$target" ]; then
    echo "    [SKIP] $target"
    return
  fi
  rm -rf "$target" && echo "    [OK] Cleared $target" && return
  echo "    [ERROR] Failed to clear $target"
  mark_error
}

resolve_database_path
load_app_names
resolve_user_data_dirs

echo
echo "================================================"
echo "       OKX Quantitative Trading System"
echo "        Reset Local Runtime State"
echo "================================================"
echo
echo " The following local runtime state will be removed:"
echo
echo "   [Database]"
for target in "$DATABASE_PATH" "$DATABASE_WAL" "$DATABASE_SHM"; do preview_file "$target"; done
echo
echo "   [Runtime Config]"
for target in "${RUNTIME_CONFIG_FILES[@]}"; do preview_file "$target"; done
echo
echo "   [Trend Research Artifacts]"
for pattern in "${TREND_PATTERNS[@]}"; do preview_glob "$pattern"; done
echo
echo "   [Logs]"
preview_dir "$LOGS_DIR"
echo
echo "   [Electron User Data]"
preview_dir "$USER_DATA_DIR"
preview_dir "$USER_DATA_FALLBACK_DIR"

if [ "$RESET_CONFIG" -eq 1 ]; then
  echo
  echo "   [Config]"
  preview_file "$ENV_FILE"
fi

if [ "$FORCE" -eq 0 ]; then
  echo
  read -r -p " Are you sure? [y/N]: " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo
    echo " [Cancelled] No data was deleted."
    exit 0
  fi
fi

echo
echo " [Resetting...]"
echo
echo "   Stopping services..."
kill_port "8000"
[ -n "$API_PORT" ] && kill_port "$API_PORT"
kill_port "5173"
kill_repo_electron

for target in "$DATABASE_PATH" "$DATABASE_WAL" "$DATABASE_SHM"; do delete_file "$target"; done
for target in "${RUNTIME_CONFIG_FILES[@]}"; do delete_file "$target"; done
for pattern in "${TREND_PATTERNS[@]}"; do delete_glob "$pattern"; done
delete_dir "$LOGS_DIR"
delete_dir "$USER_DATA_DIR"
delete_dir "$USER_DATA_FALLBACK_DIR"
[ "$RESET_CONFIG" -eq 1 ] && delete_file "$ENV_FILE"
mkdir -p "$DATA_DIR" "$CONFIG_DIR" "$LOGS_DIR"

echo
echo "================================================"
if [ "$HAS_ERRORS" -eq 0 ]; then echo "             Reset Complete!"; else echo "        Reset Completed With Errors"; fi
echo "================================================"
echo
if [ "$HAS_ERRORS" -eq 0 ]; then echo " The local runtime state has been cleared."; else echo " Some files or directories could not be removed."; fi
if [ "$RESET_CONFIG" -eq 1 ]; then
  echo
  echo " [NOTE] Remember to recreate config/.env before using API features."
fi
echo
echo " Run ./start.sh to start the system."
[ "$HAS_ERRORS" -eq 0 ] || exit 1
