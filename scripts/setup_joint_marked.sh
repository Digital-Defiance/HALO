#!/usr/bin/env bash
# Isolated joint-rule backend; v1 and production binaries are left alone.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OS="$(uname -s)"
SRC="$ROOT/build/$OS/heesch-sat/src"
DEST="$ROOT/build/$OS/heesch-sat-joint-marked-v1"
if [ ! -f "$SRC/heesch.h" ]; then echo "Build the pinned checker first" >&2; exit 1; fi
mkdir -p "$DEST"
STALE=0
if [ ! -x "$DEST/joint-marked" ]; then STALE=1; fi
for SOURCE in "$SRC"/*.h "$ROOT/third_party/heesch-sat/halo_marked_methods.h" \
    "$ROOT/third_party/heesch-sat/halo_joint_marked_methods.h" "$ROOT/third_party/heesch-sat/joint_marked.cpp" "$0"; do
  if [ "$SOURCE" -nt "$DEST/joint-marked" ]; then STALE=1; fi
done
if [ "$STALE" = 0 ]; then exit 0; fi
WORK="$(mktemp -d "${TMPDIR:-/tmp}/halo-joint-marked.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
cp "$SRC"/*.h "$WORK/"
cp "$ROOT/third_party/heesch-sat/joint_marked.cpp" "$ROOT/third_party/heesch-sat/halo_joint_marked_methods.h" "$WORK/"
python3 - "$ROOT" "$WORK" <<'PY'
from pathlib import Path
import sys
root,work=map(Path,sys.argv[1:])
methods=(root/'third_party/heesch-sat/halo_marked_methods.h').read_text()
anchors={'getClauses(solver,true);':'getClauses(solver,true);\n    addJointMarkedClauses(solver);',
         'const auto& model = solver.get_model();':'const auto& model = solver.get_model();\n        if (joint_rounds_ >= joint_limit_) return CMSat::l_Undef;\n        if (refineJointMarkedClauses(solver)) continue;',
         'getSolution(solver,patch,level_);':'getSolution(solver,patch,level_);\n            captureJointMarkedSolution(solver);'}
for before,after in anchors.items():
    if methods.count(before)!=1: raise SystemExit('joint integration anchor changed')
    methods=methods.replace(before,after)
methods+='\n'+(work/'halo_joint_marked_methods.h').read_text()
(work/'halo_marked_methods.h').write_text(methods)
p=work/'heesch.h';text=p.read_text();anchor='using patch_t = LabelledPatch<coord_t>;'
if text.count(anchor)!=1: raise SystemExit('pinned checker anchor changed')
p.write_text(text.replace(anchor,anchor+'\n#include "halo_marked_methods.h"'))
PY
case "$OS" in
  Darwin)
    BREW="$(brew --prefix)"
    clang++ -std=c++20 -O2 -DNDEBUG -I"$BREW/include/cryptominisat5" -I"$BREW/include" \
      "$WORK/joint_marked.cpp" -L"$BREW/lib" -Wl,-rpath,"$BREW/lib" -lcryptominisat5 -o "$WORK/joint-marked" ;;
  Linux) g++ -std=c++20 -O2 -DNDEBUG -I/usr/include/cryptominisat5 "$WORK/joint_marked.cpp" -lcryptominisat5 -o "$WORK/joint-marked" ;;
  *) echo "unsupported OS" >&2; exit 1 ;;
esac
mv "$WORK/joint-marked" "$DEST/joint-marked"
echo "Built $DEST/joint-marked"
