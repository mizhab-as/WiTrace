#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-/dev/cu.usbserial-0001}"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
IDF_EXPORT="$HOME/esp/esp-idf/export.sh"

printf "\n[1/4] Stopping existing monitor/app processes...\n"
pkill -f "idf.py.*monitor|idf_monitor.py|python.*collect_raw_csi.py|python.*app.py" || true

printf "[2/4] Freeing serial port %s...\n" "$PORT"
if lsof -t "$PORT" >/dev/null 2>&1; then
  lsof -t "$PORT" | xargs kill -9 || true
fi
sleep 1

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python venv not found at $PYTHON_BIN"
  echo "Create it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "$IDF_EXPORT" ]; then
  echo "ESP-IDF export script not found at $IDF_EXPORT"
  exit 1
fi

printf "[3/4] Building and flashing firmware to %s...\n" "$PORT"
source "$IDF_EXPORT" >/tmp/idf_export.log 2>&1
idf.py -C "$ROOT_DIR/firmware/csi_receiver" -p "$PORT" build flash

printf "[4/4] Starting Python web app...\n"
printf "Open: http://localhost:8080\n\n"
cd "$ROOT_DIR/python"
exec "$PYTHON_BIN" app.py
