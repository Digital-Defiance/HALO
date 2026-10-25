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
# HALO's fast periodic tiling detector (C++, no dependencies)
c++ -O2 -std=c++17 -o "$(dirname "$DEST")/periodic_dlx" "$ROOT/halo/periodic_dlx.cpp"
echo "Built $(dirname "$DEST")/periodic_dlx"
