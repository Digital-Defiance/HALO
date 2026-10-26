#!/usr/bin/env python3
"""Add next-corona defects to a JSONL of classified shapes (e.g. the Kaplan seeds).

For each non-tiler with hc >= --min-hc and cells >= --min-cells, runs the defect solver
(runner.run_defect) and writes the row with defect, ring, defect_exact, defect_seconds added.
Rows that already have a defect are copied unchanged, so an interrupted run can be resumed by
pointing --out at the same file (rows already in --out are skipped).

Usage:
  python3 halo/add_defects.py results/seeds_kaplan_hex_3up.jsonl --out results/seeds_kaplan_hex_3up_defect.jsonl \
      --min-hc 3 --min-cells 15 --jobs 8
"""
import argparse
import json
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
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--mem-mb", type=float, default=6000.0)
    ap.add_argument("--confl", type=int, default=500000)
    ap.add_argument("--max-d", type=int, default=64)
    args = ap.parse_args()

    rows = [json.loads(ln) for ln in open(args.input) if ln.strip()]
    done = set()
    if os.path.exists(args.out):
        for ln in open(args.out):
            try:
                done.add(json.loads(ln)["canon"])
            except Exception:
                pass
    todo, keep = [], []
    for r in rows:
        if r["canon"] in done:
            continue
        cells = r.get("cells") or (len(r["canon"].split()) - 1) // 2
        if (r.get("status") == "nontiler" and (r.get("hc") or 0) >= args.min_hc and cells >= args.min_cells
                and r.get("defect") is None):
            todo.append(r)
        else:
            keep.append(r)
    print(f"{len(rows)} rows, {len(done)} already in {args.out}; measuring {len(todo)}", flush=True)
    with open(args.out, "a") as fh:
        for r in keep:
            fh.write(json.dumps(r) + "\n")
        fh.flush()
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(runner.run_defect, r["canon"], r["hc"], r.get("hh") or r["hc"], args.timeout,
                                args.mem_mb, args.confl, args.max_d): r for r in todo}
            for k, fut in enumerate(as_completed(futs), 1):
                r = dict(futs[fut])
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
