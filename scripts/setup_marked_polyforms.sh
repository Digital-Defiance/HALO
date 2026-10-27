#!/usr/bin/env bash
# Build experimental marked solver without touching the production checkout.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OS="$(uname -s)"
SRC="$ROOT/build/$OS/heesch-sat/src"
DEST="$ROOT/build/$OS/heesch-sat-marked-v1"
if [ ! -f "$SRC/heesch.h" ]; then
  echo "First run scripts/setup_heesch_sat.sh" >&2
  exit 1
fi
mkdir -p "$DEST"
STALE=0
if [ ! -x "$DEST/marked" ]; then STALE=1; fi
for SOURCE in "$SRC"/*.h "$ROOT/third_party/heesch-sat/halo_marked_methods.h" "$ROOT/third_party/heesch-sat/marked.cpp" "$0"; do
  if [ "$SOURCE" -nt "$DEST/marked" ]; then STALE=1; fi
done
if [ "$STALE" = 0 ]; then exit 0; fi
WORK="$(mktemp -d "${TMPDIR:-/tmp}/halo-marked.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
cp "$SRC"/*.h "$WORK/"
cp "$ROOT/third_party/heesch-sat/halo_marked_methods.h" "$ROOT/third_party/heesch-sat/marked.cpp" "$WORK/"
python3 - "$WORK/heesch.h" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
text=p.read_text()
anchor='using patch_t = LabelledPatch<coord_t>;'
if text.count(anchor)!=1:
    raise SystemExit('pinned checker integration anchor changed')
p.write_text(text.replace(anchor,anchor+'\n#include "halo_marked_methods.h"'))
PY
case "$OS" in
  Darwin)
    BREW="$(brew --prefix)"
    clang++ -std=c++20 -O2 -DNDEBUG -I"$BREW/include/cryptominisat5" -I"$BREW/include" \
      "$WORK/marked.cpp" -L"$BREW/lib" -Wl,-rpath,"$BREW/lib" -lcryptominisat5 -o "$WORK/marked"
    ;;
  Linux)
    g++ -std=c++20 -O2 -DNDEBUG -I/usr/include/cryptominisat5 \
      "$WORK/marked.cpp" -lcryptominisat5 -o "$WORK/marked"
    ;;
  *) echo "unsupported OS $OS" >&2; exit 1 ;;
esac
mv "$WORK/marked" "$DEST/marked"
echo "Built $DEST/marked"
