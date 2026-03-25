#!/usr/bin/env bash
set -euo pipefail

# Re-collect balanced baseline datasets with CSI_META + CSI_DATA lines.
# Usage:
#   bash recollect_balanced_data.sh [duration_seconds] [output_dir]
# Example:
#   bash recollect_balanced_data.sh 600 ../data2/myroom

DURATION="${1:-600}"
OUT_DIR="${2:-../data2/myroom}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
	PYTHON_BIN="python3"
fi

mkdir -p "$OUT_DIR"

echo "============================================================"
echo "Balanced Baseline Re-Collection"
echo "Duration per class: ${DURATION}s"
echo "Output directory: ${OUT_DIR}"
echo "============================================================"

echo
echo "Step 1/3: EMPTY room capture starts in 5s..."
sleep 5
"${PYTHON_BIN}" "${SCRIPT_DIR}/collect_raw_csi.py" "${OUT_DIR}/empty.txt" "$DURATION"

echo
echo "Step 2/3: OCCUPIED room (1 person) starts in 5s..."
sleep 5
"${PYTHON_BIN}" "${SCRIPT_DIR}/collect_raw_csi.py" "${OUT_DIR}/occupied.txt" "$DURATION"

echo
echo "Step 3/3: MULTIPLE people starts in 5s..."
sleep 5
"${PYTHON_BIN}" "${SCRIPT_DIR}/collect_raw_csi.py" "${OUT_DIR}/multiple_people.txt" "$DURATION"

echo
echo "Done. Collected:"
wc -l "${OUT_DIR}/empty.txt" "${OUT_DIR}/occupied.txt" "${OUT_DIR}/multiple_people.txt"
