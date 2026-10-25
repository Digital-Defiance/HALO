#!/usr/bin/env python3
"""HALO Track B, cheap route: scaled polyominoes with bumps and nicks on their edges.

Takes base polyominoes, scales each cell to an s x s block (s odd), and marks every base
boundary edge as flat, bump (a small protrusion outside the middle of the edge) or nick
(the same shape cut inside). Writes unique, connected, hole-free unmarked polyominoes,
one per line, ready for halo/runner.py.

This mirrors Mann–Thomas marked polyforms (bumps and nicks, Heesch numbers up to 5)
but realizes the markings as cells, so the result is an ordinary polyomino that
heesch-sat (and Epoch's verifier) can check.

Usage:
  python3 halo/gen_marked.py --base-size 4 --scale 3 [--bump-depth 1] [--max-marked 99]
                             [--sample N --seed S] -o results/marked_b4_s3.txt
Base shapes come from Kaplan's `gen` (built by scripts/setup_heesch_sat.sh).
"""
import argparse
import itertools
import os
import platform
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape as shp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "build", platform.system(), "heesch-sat", "src", "gen")
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def base_polyominoes(size):
    out = subprocess.run([GEN, "-omino", "-size", str(size), "-free"], capture_output=True, text=True,
                         check=True).stdout
    return [shp.parse(ln)[1] for ln in out.splitlines() if ln.strip()]


def boundary_edges(cells):
    s = set(cells)
    return [(c, d) for c in sorted(cells) for d in DIRS if (c[0] + d[0], c[1] + d[1]) not in s]


def realize(cells, edges, marks, s, depth):
    """Fine cells for a marked, scaled base polyomino. marks[i] in {0, 1 (bump), -1 (nick)}."""
    fine = set()
    for x, y in cells:
        for i in range(s):
            for j in range(s):
                fine.add((x * s + i, y * s + j))
    mid = s // 2
    for ((x, y), (dx, dy)), m in zip(edges, marks):
        if m == 0:
            continue
        for k in range(depth):
            # cell just outside (bump) or just inside (nick) the middle of this edge, k deep
            if dx == 1:
                out_c, in_c = (x * s + s + k, y * s + mid), (x * s + s - 1 - k, y * s + mid)
            elif dx == -1:
                out_c, in_c = (x * s - 1 - k, y * s + mid), (x * s + k, y * s + mid)
            elif dy == 1:
                out_c, in_c = (x * s + mid, y * s + s + k), (x * s + mid, y * s + s - 1 - k)
            else:
                out_c, in_c = (x * s + mid, y * s - 1 - k), (x * s + mid, y * s + k)
            if m == 1:
                fine.add(out_c)
            else:
                fine.discard(in_c)
    return sorted(fine)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-size", type=int, required=True)
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--bump-depth", type=int, default=1)
    ap.add_argument("--max-marked", type=int, default=99, help="at most this many non-flat edges")
    ap.add_argument("--sample", type=int, default=0, help="random sample of markings per base (0 = all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    if args.scale % 2 == 0 or args.scale < 3:
        sys.exit("--scale must be odd and >= 3")
    rng = random.Random(args.seed)

    seen = set()
    kept = rejected = 0
    with open(args.out, "w") as fh:
        for base in base_polyominoes(args.base_size):
            edges = boundary_edges(base)
            if args.sample:
                marks_iter = (tuple(rng.choice((0, 1, -1)) for _ in edges) for _ in range(args.sample))
            else:
                marks_iter = itertools.product((0, 1, -1), repeat=len(edges))
            for marks in marks_iter:
                if sum(1 for m in marks if m) > args.max_marked:
                    continue
                fine = realize(base, edges, marks, args.scale, args.bump_depth)
                key = shp.canonical("O", fine)
                if key in seen:
                    continue
                seen.add(key)
                ok, problems, info = shp.check("O " + " ".join(f"{x} {y}" for x, y in fine))
                if not ok:
                    rejected += 1
                    continue
                fh.write(key + "\n")
                kept += 1
    print(f"wrote {kept} unique shapes to {args.out} ({rejected} rejected by constraint checks)")


if __name__ == "__main__":
    main()
