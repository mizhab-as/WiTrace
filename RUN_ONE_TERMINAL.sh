#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${ESP_PORT:-/dev/cu.usbserial-0001}"
FLASH_FIRST="${1:-}"

cd "${PROJECT_ROOT}"

echo "[1/4] Freeing serial port: ${PORT}"
PID="$(lsof -t "${PORT}" 2>/dev/null | head -n 1 || true)"
if [[ -n "${PID}" ]]; then
  echo "Killing process ${PID} using ${PORT}"
  kill "${PID}" || true
  sleep 1
fi

if [[ "${FLASH_FIRST}" == "--flash" ]]; then
  echo "[2/4] Flashing firmware first"
  if [[ -f "$HOME/esp/esp-idf/export.sh" ]]; then
    # shellcheck source=/dev/null
    source "$HOME/esp/esp-idf/export.sh"
  else
    echo "ESP-IDF export script not found at $HOME/esp/esp-idf/export.sh"
    echo "Skipping flash environment setup."
  fi

  cd "${PROJECT_ROOT}/firmware/csi_receiver"
  idf.py -p "${PORT}" -b 460800 flash
  cd "${PROJECT_ROOT}"
else
  echo "[2/4] Skipping flash (use --flash to flash firmware first)"
fi

echo "[3/4] Activating Python environment"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/.venv/bin/activate"

echo "[4/4] Starting dashboard backend (Ctrl+C to stop)"
cd "${PROJECT_ROOT}/python"
python app.py
