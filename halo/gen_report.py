#!/usr/bin/env python3
"""Compare candidate generators in a search log: how often each one's shapes come out Hc >= 2.

Usage:
  python3 halo/gen_report.py results/search_hex_01.jsonl [--since 2026-10-26T12:00:00] [--skip-lines 47157]

Per generator (search = random mutants, search-scored = scorer-picked mutants,
search-relax-<mode> = continuous relaxation): shapes checked, share that tile, the Hc
distribution of non-tilers, the Hc >= 2 rate with a 95% Wilson interval, Hc >= 3 count,
and worker seconds per shape, including ladder stages, retries and defect scoring.
Historical rows without total_seconds undercount earlier ladder stages.
"""
import argparse
import json
import math

from runner import evaluation_seconds


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--since", default="", help="only rows with ts >= this (ISO, as logged)")
    ap.add_argument("--run-id", default="", help="only this run (IDs and settings in LOG.runs.jsonl)")
    ap.add_argument("--skip-lines", type=int, default=0, help="ignore the first N lines (e.g. an earlier run)")
    ap.add_argument("--min-cells", type=int, default=0,
                    help="only shapes with at least this many cells (18 for hexes = beyond Kaplan's enumeration)")
    args = ap.parse_args()
    stats = {}
    with open(args.log) as fh:
        for i, ln in enumerate(fh):
            if i < args.skip_lines:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if args.since and (r.get("ts") or "") < args.since:
                continue
            if args.run_id and r.get("run_id") != args.run_id:
                continue
            if (r.get("cells") or 0) < args.min_cells:
                continue
            g = r.get("generator") or "?"
            s = stats.setdefault(g, {"n": 0, "tile": 0, "hc": {}, "sec": 0.0, "cells": 0, "other": 0})
            s["n"] += 1
            s["sec"] += evaluation_seconds(r)
            s["cells"] += int(r.get("cells") or 0)
            st = r.get("status")
            if st in ("isohedral", "periodic", "anisohedral", "aperiodic"):
                s["tile"] += 1
            elif st == "nontiler" and r.get("hc") is not None:
                s["hc"][r["hc"]] = s["hc"].get(r["hc"], 0) + 1
            else:
                s["other"] += 1
    if not stats:
        print("no rows")
        return
    print(f"{'generator':20s} {'checked':>7s} {'tilers':>7s} {'unsettled':>9s}  {'Hc>=2 rate (95% CI)':26s} "
          f"{'Hc>=3':>5s} {'s/check':>7s} {'3+/wkr-h':>9s} {'cells':>5s}  non-tilers by Hc")
    for g in sorted(stats):
        s = stats[g]
        n = s["n"]
        k2 = sum(v for h, v in s["hc"].items() if h >= 2)
        k3 = sum(v for h, v in s["hc"].items() if h >= 3)
        lo, hi = wilson(k2, n)
        hist = ", ".join(f"{h}:{v}" for h, v in sorted(s["hc"].items()))
        per_hour = 3600 * k3 / s["sec"] if s["sec"] else 0.0
        print(f"{g:20s} {n:7d} {100*s['tile']/n:6.1f}% {s['other']:9d}  {100*k2/n:5.2f}% ({100*lo:4.2f}-{100*hi:5.2f}%)      "
              f"{k3:5d} {s['sec']/n:7.2f} {per_hour:9.1f} {s['cells']/n:5.1f}  {hist}")


if __name__ == "__main__":
    main()
