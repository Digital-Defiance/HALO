#!/usr/bin/env bash
# Clone Craig Kaplan's heesch-sat at the pinned commit and build it with HALO's Makefile.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="d12a527"
DEST="$ROOT/build/$(uname -s)/heesch-sat"
mkdir -p "$(dirname "$DEST")"
if [ ! -d "$DEST/.git" ]; then
  git clone https://github.com/isohedral/heesch-sat.git "$DEST"
fi
git -C "$DEST" checkout -q "$COMMIT"
case "$(uname -s)" in
  Darwin) MK="Makefile.macos"; JOBS="$(sysctl -n hw.ncpu)" ;;
  Linux)  MK="Makefile.linux"; JOBS="$(nproc)" ;;
  *) echo "unsupported OS" >&2; exit 1 ;;
esac
cp "$ROOT/third_party/heesch-sat/$MK" "$DEST/src/Makefile.halo"
make -C "$DEST/src" -f Makefile.halo -j"$JOBS" sat gen report
echo "Built $DEST/src/sat"
# HALO's fast periodic tiling detector (C++, no dependencies). Rebuilt only when the source is
# newer, so re-running this script never replaces a binary a running search is using.
PD="$(dirname "$DEST")/periodic_dlx"
if [ ! -x "$PD" ] || [ "$ROOT/halo/periodic_dlx.cpp" -nt "$PD" ]; then
  c++ -O2 -std=c++17 -o "$PD" "$ROOT/halo/periodic_dlx.cpp"
fi
echo "Built $PD"
# HALO's next-corona defect solver: heesch-sat with a relaxed outer corona
# (third_party/heesch-sat/halo_defect.patch + defect.cpp), built in a separate copy so the
# sat binary above is never touched.
DD="$(dirname "$DEST")/heesch-sat-defect"
STAMP="$ROOT/third_party/heesch-sat/halo_defect.patch"
if [ ! -x "$DD/defect" ] || [ "$STAMP" -nt "$DD/defect" ] || [ "$ROOT/third_party/heesch-sat/defect.cpp" -nt "$DD/defect" ]; then
  rm -rf "$DD" && mkdir -p "$DD"
  cp "$DEST"/src/*.h "$DEST"/src/*.cpp "$DD"/
  patch -s -d "$DD" -p2 < "$STAMP"
  cp "$ROOT/third_party/heesch-sat/defect.cpp" "$DD/"
  cp "$ROOT/third_party/heesch-sat/$MK" "$DD/Makefile.halo"
  make -C "$DD" -f Makefile.halo -j"$JOBS" defect
fi
echo "Built $DD/defect"
