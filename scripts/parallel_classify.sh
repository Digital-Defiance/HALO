#!/usr/bin/env bash
# Classify a file of unclassified shapes (one shape per line, as written by `gen`) across all cores.
# Usage: scripts/parallel_classify.sh INPUT OUTPUT [JOBS] [MAXLEVEL]
#   JOBS defaults to the number of CPU cores; MAXLEVEL defaults to 7.
# Output is heesch-sat's classified format (no witness patches); a summary report is printed at the end.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/$(uname -s)/heesch-sat/src"
[ -x "$BIN/sat" ] || { echo "Run scripts/setup_heesch_sat.sh first" >&2; exit 1; }
IN="$1"; OUT="$2"
JOBS="${3:-$( (sysctl -n hw.ncpu 2>/dev/null || nproc) )}"
ML="${4:-7}"
TMP="$(mktemp -d)"
awk -v n="$JOBS" -v d="$TMP" '{ print > (d "/in." (NR % n)) }' "$IN"
START=$(date +%s)
for f in "$TMP"/in.*; do
  "$BIN/sat" -isohedral -maxlevel "$ML" "$f" -o "${f/in./out.}" &
done
wait
cat "$TMP"/out.* > "$OUT"
echo "Classified $(wc -l < "$IN" | tr -d ' ') shapes with $JOBS jobs in $(( $(date +%s) - START )) s"
"$BIN/report" "$OUT"
rm -rf "$TMP" 2>/dev/null || true
