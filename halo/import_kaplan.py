#!/usr/bin/env python3
"""Import Kaplan's published Heesch data (heesch-sat `sat -show` output) as HALO seed JSONL.

Source: C. S. Kaplan, "Heesch numbers of unmarked polyforms", Contributions to Discrete
Mathematics 17(2), 2022; data at https://cs.uwaterloo.ca/~csk/heesch/ (e.g. hex/17hex_3up.txt,
every free polyhex of that size with Hc >= 3 or Hh >= 3). Download into refs/kaplan/ (git-ignored).

Usage:
  python3 halo/import_kaplan.py refs/kaplan/*hex_3up.txt --out results/seeds_kaplan_hex_3up.jsonl

Writes one JSONL row per shape: canonical form, grid, cells, status, hc, hh, generator
"kaplan2022", source file. search.py --seeds reads it directly (--seed-min-hc picks the level).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape as shp  # noqa: E402
from runner import STATUS_CODES  # noqa: E402


def records(path, grid="H"):
    """(shape line, status, hc, hh) for each shape line in a `sat -show` file that is followed
    by a status line. Witness and status lines are skipped. A status line like `I 1 0` looks
    like a 1-cell shape, so only lines of the requested grid count as shapes."""
    with open(path) as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    for i, ln in enumerate(lines[:-1]):
        toks = ln.split()
        if toks[0].rstrip("?") != grid or len(toks) < 3 or len(toks) % 2 == 0:
            continue
        if not all(t.lstrip("-").isdigit() for t in toks[1:]):
            continue
        st = lines[i + 1].split()
        code = st[0][0]
        if code not in STATUS_CODES:
            continue
        status = STATUS_CODES[code]
        hc = hh = None
        if status == "nontiler" and len(st) >= 3:
            hc, hh = int(st[1]), int(st[2])
        yield ln, status, hc, hh


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--grid", default="H")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows, seen = [], set()
    tally = {}
    for path in args.files:
        for line, status, hc, hh in records(path, args.grid):
            g, cells = shp.parse(line)
            canon = shp.canonical(g, cells)
            if canon in seen:
                continue
            seen.add(canon)
            rows.append({"canon": canon, "shape": canon, "grid": g, "cells": len(cells), "status": status,
                         "hc": hc, "hh": hh, "generator": "kaplan2022", "source": os.path.basename(path)})
            key = (len(cells), status if status != "nontiler" else f"Hc={hc}")
            tally[key] = tally.get(key, 0) + 1
    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"{len(rows)} shapes -> {args.out}")
    for (n, k), v in sorted(tally.items()):
        print(f"  {n:2d} cells  {k:14s} {v}")


if __name__ == "__main__":
    main()
