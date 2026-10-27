#!/usr/bin/env python3
"""Add next-corona defects to a JSONL of classified shapes (e.g. the Kaplan seeds).

For each non-tiler with hc >= --min-hc and cells >= --min-cells, runs the defect solver
(runner.run_defect) and writes the row with defect, ring, defect_exact, defect_seconds added.
Rows with a version-2 defect are copied unchanged. Older metrics are remeasured,
because version 1 did not exclude holes in inner coronas. Output is append only;
an interrupted run can resume with --out pointing at the same file.

Usage:
  python3 halo/add_defects.py results/seeds_kaplan_hex_3up.jsonl --out results/seeds_kaplan_hex_3up_defect.jsonl \
      --min-hc 3 --min-cells 15 --jobs 8
"""
import argparse
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-hc", type=int, default=3)
    ap.add_argument("--min-cells", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel defect solvers; default 1 because high-Hc layouts can use several GB")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--mem-mb", type=float, default=6000.0)
    ap.add_argument("--confl", type=int, default=500000)
    ap.add_argument("--max-d", type=int, default=64)
    ap.add_argument("--include-patch", action="store_true", help="export best partial layout and gap coordinates")
    ap.add_argument("--memory-budget-mb", type=float, default=48000)
    ap.add_argument("--memory-reserve-mb", type=float, default=8000)
    args = ap.parse_args()
    if (args.jobs < 1 or args.confl < 1 or args.max_d < 0
            or any(not math.isfinite(x) or x <= 0 for x in
                   (args.timeout, args.mem_mb, args.memory_budget_mb))
            or not math.isfinite(args.memory_reserve_mb) or args.memory_reserve_mb < 0):
        ap.error("invalid worker, conflict or resource limits")

    with open(args.input) as source:
        rows = [json.loads(ln) for ln in source if ln.strip()]
    done = set()
    if os.path.exists(args.out):
        with open(args.out) as previous:
            for ln in previous:
                try:
                    old = json.loads(ln)
                    complete = old.get("defect") is None or old.get("defect_version", 1) >= 2
                    if args.include_patch and old.get("defect") is not None and not old.get("defect_patch"):
                        complete = False
                    if complete:
                        done.add(old["canon"])
                except Exception:
                    pass
    todo, keep = [], []
    for r in rows:
        if r["canon"] in done:
            continue
        cells = r.get("cells") or (len(r["canon"].split()) - 1) // 2
        if (r.get("status") == "nontiler" and (r.get("hc") or 0) >= args.min_hc and cells >= args.min_cells
                and (r.get("defect") is None or r.get("defect_version", 1) < 2
                     or (args.include_patch and not r.get("defect_patch")))):
            todo.append(r)
        else:
            keep.append(r)
    print(f"{len(rows)} rows, {len(done)} already in {args.out}; measuring {len(todo)}", flush=True)
    runner.ensure_jsonl_boundary(args.out)
    with runner.use_memory_budget(runner.MemoryBudget(args.memory_budget_mb, args.memory_reserve_mb)), \
            open(args.out, "a") as fh:
        for r in keep:
            fh.write(json.dumps(r) + "\n")
        fh.flush()
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(runner.run_defect, r["canon"], r["hc"], r.get("hh") or r["hc"], args.timeout,
                                args.mem_mb, args.confl, args.max_d,
                                include_patch=args.include_patch): r for r in todo}
            for k, fut in enumerate(as_completed(futs), 1):
                # A failed remeasurement must not retain a stale partial patch
                # or version tag from a previous metric.
                r = {key: value for key, value in futs[fut].items()
                     if key not in ("defect", "ring") and not key.startswith("defect_")}
                r.update(fut.result())
                fh.write(json.dumps(r) + "\n")
                fh.flush()
                d = r.get("defect")
                print(f"  [{k}/{len(todo)}] hc={r['hc']} cells={r.get('cells')}: "
                      + (f"{d}/{r['ring']} ({r['hc'] + 1 - d / r['ring']:.4f}"
                         f"{'' if r.get('defect_exact') else ', bound'})" if d is not None else r.get("defect_stop")),
                      flush=True)


if __name__ == "__main__":
    main()
