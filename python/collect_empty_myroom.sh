#!/usr/bin/env bash
set -euo pipefail

# Collect an "empty room" baseline into data2/myroom/empty.txt
# Usage:
#   ./python/collect_empty_myroom.sh [duration_seconds]
# Example:
#   ./python/collect_empty_myroom.sh 600

DURATION_SECONDS="${1:-600}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_FILE="${PROJECT_ROOT}/data2/myroom/empty.txt"

PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
	PYTHON_BIN="python3"
fi

mkdir -p "$(dirname "${OUT_FILE}")"

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/collect_raw_csi.py" "${OUT_FILE}" "${DURATION_SECONDS}"
