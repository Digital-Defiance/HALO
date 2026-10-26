#!/usr/bin/env bash
# Sweep libaner's GPU tuning knobs on the HALO scorer and print one line per configuration.
# Run on the Mac after rebuilding ANER (make -C /Volumes/Code/ANER/lib), with nothing else heavy running.
#   ANER_GPU_PIPELINE=0|1   synchronous vs two-chunks-in-flight GPU worker
#   ANER_GPU_CHUNK=N        GPU chunk width in columns (default 2048)
#   ANER_GPU_OPT_LEVEL=0|1  MPSGraph optimization level (1 may move work onto the Neural Engine)
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${ANER_PYTHON:-/Volumes/Code/ANER/python}"
W=results/models/scorer_hex11_b8.npz
D=results/hex11.jsonl
run() {  # label, env..., then schedules
  local label="$1"; shift
  env "$@" python3 halo/aner_scorer.py "$W" "$D" --no-mlx --schedules "$SCHED" --label "$(printf '%-28s' "$label")" 2>&1 \
    | grep -E "ANER|Error|error|failed" || echo "$label: no output"
}
echo "== reference (CPU, once) =="
python3 halo/aner_scorer.py "$W" "$D" --schedules ane --label "" 2>&1 | grep -E "NumPy|MLX|ANER"
SCHED=gpu,split
echo "== sync worker (old behaviour apart from lighter lowering) =="
run "pipeline=0 chunk=2048" ANER_GPU_PIPELINE=0 ANER_GPU_CHUNK=2048
echo "== pipelined worker, chunk sweep =="
for c in 2048 4096 8192 16384; do
  run "pipeline=1 chunk=$c" ANER_GPU_PIPELINE=1 ANER_GPU_CHUNK=$c
done
echo "== optimization level 1 (experiment) =="
for c in 2048 8192; do
  run "opt=1 pipeline=1 chunk=$c" ANER_GPU_OPT_LEVEL=1 ANER_GPU_PIPELINE=1 ANER_GPU_CHUNK=$c
done
