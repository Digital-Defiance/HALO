#!/usr/bin/env bash
# Classify shapes the way the Epoch verifier does: isohedral check on, up to 12 coronas.
# Usage: scripts/check_shape.sh FILE   (one or more shapes in heesch-sat text format; a bare "GRID x y ..." line is fine)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAT="$ROOT/build/$(uname -s)/heesch-sat/src/sat"
[ -x "$SAT" ] || { echo "Run scripts/setup_heesch_sat.sh first" >&2; exit 1; }
"$SAT" -isohedral -show -maxlevel 12 "$@"
