#!/usr/bin/env bash
# Build the diagnostic exporter separately; leave the production checker alone.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OS="$(uname -s)"
SRC="$ROOT/build/$OS/heesch-sat/src"
DEST="${HALO_REPAIR_BUILD:-$ROOT/build/$OS/heesch-sat-defect-v2}"
if [ ! -f "$SRC/heesch.h" ]; then
  echo "First build the pinned checker with scripts/setup_heesch_sat.sh" >&2
  exit 1
fi
case "$OS" in
  Darwin) MK="Makefile.macos" ;;
  Linux) MK="Makefile.linux" ;;
  *) echo "unsupported OS: $OS" >&2; exit 1 ;;
esac
mkdir -p "$DEST"
STALE=0
if [ ! -x "$DEST/defect" ]; then STALE=1; fi
for SOURCE in "$SRC"/*.h "$SRC/isohedral.cpp" "$ROOT/third_party/heesch-sat/halo_defect.patch" \
              "$ROOT/third_party/heesch-sat/defect.cpp" "$ROOT/third_party/heesch-sat/$MK"; do
  if [ "$SOURCE" -nt "$DEST/defect" ]; then STALE=1; fi
done
if [ "$STALE" = 0 ]; then exit 0; fi
# Publish with rename; a process using the previous binary keeps its mapping.
WORK="$(mktemp -d "$DEST/build.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
cp "$SRC"/*.h "$WORK/"
cp "$SRC/isohedral.cpp" "$WORK/"
patch -s -d "$WORK" -p2 < "$ROOT/third_party/heesch-sat/halo_defect.patch"
cp "$ROOT/third_party/heesch-sat/defect.cpp" "$WORK/"
cp "$ROOT/third_party/heesch-sat/$MK" "$WORK/Makefile.halo"
make -C "$WORK" -f Makefile.halo -j2 defect
mv "$WORK/defect" "$DEST/defect"
echo "Built $DEST/defect"
