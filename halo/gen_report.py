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
import hashlib
import json
import math
import os

from runner import evaluation_seconds


def latest_run(log):
    """Find the last started run, independent of later warning events."""
    found = None
    with open(str(log) + ".runs.jsonl") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if row.get("event") == "started":
                found = row.get("run_id")
    if not found:
        raise ValueError("no started run in the manifest")
    return found


def collect_stats(log, *, run_id="", since="", skip_lines=0, min_cells=0,
                  generator="", by_parent=False, snapshot_bytes=None):
    """Read a byte-bounded snapshot without writing to a potentially active log.

    Checks are completed records. Per-parent hit counts are unique canonical
    shapes within each group; repeated attempts still contribute checks/cost.
    Neither unfinished work nor neighbourhood exhaustion can be inferred here.
    """
    stats = {}
    malformed = partial = 0
    digest = hashlib.sha256()
    with open(log, "rb") as fh:
        size = os.fstat(fh.fileno()).st_size
        if snapshot_bytes is not None:
            size = min(size, snapshot_bytes)
        remaining = size
        i = 0
        while remaining:
            line = fh.readline(remaining)
            if not line:
                break
            digest.update(line)
            remaining -= len(line)
            if not line.endswith(b"\n"):
                partial += 1
                break
            i += 1
            if i <= skip_lines:
                continue
            try:
                r = json.loads(line)
                if not isinstance(r, dict):
                    raise ValueError("expected a record")
            except (ValueError, UnicodeError):
                malformed += 1
                continue
            if since and (r.get("ts") or "") < since:
                continue
            if run_id and r.get("run_id") != run_id:
                continue
            if (r.get("cells") or 0) < min_cells:
                continue
            g = r.get("generator") or "?"
            if generator and g != generator:
                continue
            parent = r.get("parent")
            key = (g, parent) if by_parent else g
            s = stats.setdefault(key, {"n": 0, "tile": 0, "hc": {}, "sec": 0.0,
                                      "cells": 0, "other": 0, "hits": {2: set(), 3: set(), 4: set(), 5: set()}})
            s["n"] += 1
            s["sec"] += evaluation_seconds(r)
            s["cells"] += int(r.get("cells") or 0)
            st = r.get("status")
            if st in ("isohedral", "periodic", "anisohedral", "aperiodic"):
                s["tile"] += 1
            elif st == "nontiler" and r.get("hc") is not None:
                hc = r["hc"]
                s["hc"][hc] = s["hc"].get(hc, 0) + 1
                if by_parent:
                    # Missing canons do not support a claim of unique discoveries.
                    canon = r.get("canon")
                    if canon:
                        for threshold in s["hits"]:
                            if hc >= threshold:
                                s["hits"][threshold].add(canon)
            else:
                s["other"] += 1
    return stats, {"snapshot_bytes": size, "snapshot_sha256": digest.hexdigest(),
                   "malformed_rows": malformed, "partial_rows": partial}


def parent_rows(stats):
    rows = []
    for (generator, parent), s in stats.items():
        n = s["n"]
        rows.append({"generator": generator, "parent": parent,
                     "parent_id": hashlib.sha256((parent or "?").encode()).hexdigest()[:12],
                     "parent_cells": (len(parent.split()) - 1) // 2 if parent else None,
                     "checks": n, "unsettled": s["other"], "tilers": s["tile"],
                     "unique_hc3plus": len(s["hits"][3]), "unique_hc4plus": len(s["hits"][4]),
                     "unique_hc5plus": len(s["hits"][5]), "worker_seconds": s["sec"],
                     "seconds_per_check": s["sec"] / n,
                     "hc3plus_per_1000": 1000 * len(s["hits"][3]) / n,
                     "hc3plus_per_worker_hour": 3600 * len(s["hits"][3]) / s["sec"] if s["sec"] else None})
    return sorted(rows, key=lambda r: (-r["checks"], r["generator"], r["parent_id"]))


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
    ap.add_argument("--latest-run", action="store_true", help="select the most recently started run in the manifest")
    ap.add_argument("--generator", default="", help="restrict to one generator; --by-parent defaults to search-sweep2")
    ap.add_argument("--by-parent", action="store_true", help="report per-parent discovery yield and recorded worker cost")
    ap.add_argument("--json", action="store_true", help="machine-readable per-parent report (requires --by-parent)")
    ap.add_argument("--top", type=int, default=20, help="maximum parent rows printed; JSON always includes all")
    ap.add_argument("--skip-lines", type=int, default=0, help="ignore the first N lines (e.g. an earlier run)")
    ap.add_argument("--min-cells", type=int, default=0,
                    help="only shapes with at least this many cells (18 for hexes = beyond Kaplan's enumeration)")
    args = ap.parse_args()
    if args.top < 1 or (args.latest_run and args.run_id) or (args.json and not args.by_parent):
        ap.error("need positive --top; choose --latest-run or --run-id; --json requires --by-parent")
    if args.latest_run:
        args.run_id = latest_run(args.log)
    if args.by_parent and not args.generator:
        args.generator = "search-sweep2"
    stats, snapshot = collect_stats(args.log, run_id=args.run_id, since=args.since,
        skip_lines=args.skip_lines, min_cells=args.min_cells, generator=args.generator, by_parent=args.by_parent)
    if args.by_parent:
        rows = parent_rows(stats)
        if args.json:
            print(json.dumps({"run_id": args.run_id, **snapshot, "parents": rows}, indent=2))
            return
        print(f"run {args.run_id or 'all'}; {sum(r['checks'] for r in rows):,} completed checks; "
              f"{len(rows)} parent groups; byte snapshot {snapshot['snapshot_bytes']:,}")
        print(f"{'generator':15s} {'parent ID':12s} {'cells':>5s} {'checks':>8s} {'H3+':>5s} {'H4+':>4s} "
              f"{'H5+':>4s} {'H3+/1k':>8s} {'unsettled':>9s} {'s/check':>8s}")
        for r in rows[:args.top]:
            cells = str(r['parent_cells']) if r['parent_cells'] is not None else '?'
            print(f"{r['generator']:15s} {r['parent_id']:12s} {cells:>5s} {r['checks']:8d} "
                  f"{r['unique_hc3plus']:5d} {r['unique_hc4plus']:4d} {r['unique_hc5plus']:4d} "
                  f"{r['hc3plus_per_1000']:8.2f} {r['unsettled']:9d} {r['seconds_per_check']:8.2f}")
        print("Hits are unique canonical shapes within each parent group; checks include repeated attempts. "
              "Neighbourhood exhaustion is not inferred.")
        if snapshot['malformed_rows'] or snapshot['partial_rows']:
            print(f"Skipped {snapshot['malformed_rows']} malformed and {snapshot['partial_rows']} partial rows.")
        return
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
