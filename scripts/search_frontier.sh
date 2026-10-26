#!/usr/bin/env bash
# Next frontier run. Start after the existing run has finished; extra CLI args override defaults.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ANER_PYTHON:-/Volumes/Code/ANER/python}${PYTHONPATH:+:$PYTHONPATH}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
PYTHON="${HALO_PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="${HALO_PYTHON:-python3}"
fi
exec "$PYTHON" halo/search.py \
  --seeds results/seeds_kaplan_hex_3up.jsonl --seed-min-hc 3 \
  --log results/search_hex_01.jsonl \
  --min-cells 18 --max-cells 30 --parent-min-cells 15 --prefer-min-cells 18 \
  --scorer results/models/scorer_v4_hex.npz --scorer-schedule mlx-fp32 \
  --scorer-spatial 256 \
  --sweep-min-hc 3 --sweep-frac 0.75 --random-frac 0.5 \
  --maxlevel 7 --escalate-maxlevel 9 --mem-mb 3000 \
  --retry-mem-mb 10000 --retry-jobs 2 --retry-archived \
  --jobs 14 --hours 8 "$@"
