#!/usr/bin/env python3
"""Generator bake-off: same parents, same number of new shapes per generator, same checker.

Each generator proposes up to --n new shapes (not in the archive, valid, within limits) from the
same parent set:
  random      one random mutation step (as search.py's unscored mutants)
  scored      best --pick of --candidates random mutants by the scorer (as search.py's refill)
  relax-cell  continuous relaxation, one logit per cell (relax.py)
  relax-splat continuous relaxation, Gaussian blobs (relax.py)
Then every proposed shape goes through the same checker ladder in parallel, in shuffled order,
and the results are written as a search-style JSONL log (generator field set), so
`gen_report.py` summarises it (add --min-cells 18 for yield beyond Kaplan's enumeration).
Generation time per shape is reported too: a generator that is better per check but much
slower to propose may still lose on a real run.

Usage:
  python3 halo/bakeoff.py --archive results/search_hex_01.jsonl --parents results/seeds_kaplan_hex_3up.jsonl \
      --parent-min-hc 3 --scorer results/models/scorer_v3_hex.npz --n 1000 --out results/bakeoff_01.jsonl
"""
import argparse
import json
import os
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner  # noqa: E402
import shape as shp  # noqa: E402
from search import mutate  # noqa: E402

GENERATORS = ("random", "scored", "relax-cell", "relax-splat")


def load_rows(paths):
    rows = {}
    for path in paths.split(","):
        if not path:
            continue
        with open(path) as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                key = r.get("canon") or shp.canonical(*shp.parse(r["shape"]))
                rows[key] = r
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive", default="", help="JSONL logs of already-checked shapes (excluded), comma-separated")
    ap.add_argument("--parents", required=True, help="JSONL file(s) with parent shapes, comma-separated")
    ap.add_argument("--parent-min-hc", type=int, default=3)
    ap.add_argument("--parent-min-cells", type=int, default=0)
    ap.add_argument("--scorer", required=True)
    ap.add_argument("--generators", default=",".join(GENERATORS))
    ap.add_argument("--n", type=int, default=1000, help="shapes per generator (fewer if a generator runs dry)")
    ap.add_argument("--gen-seconds", type=float, default=900.0, help="time limit per generator")
    ap.add_argument("--candidates", type=int, default=2048)
    ap.add_argument("--pick", type=int, default=32)
    ap.add_argument("--relax-parents", type=int, default=16)
    ap.add_argument("--relax-tile-weight", type=float, default=1.0)
    ap.add_argument("--relax-grow", type=int, default=4)
    ap.add_argument("--min-cells", type=int, default=4)
    ap.add_argument("--max-cells", type=int, default=30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--seed", type=int, default=0)
    # checker settings (as search.py)
    ap.add_argument("--sat", default=runner.DEFAULT_SAT)
    ap.add_argument("--maxlevel", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--timeout-long", type=float, default=300.0)
    ap.add_argument("--mem-mb", type=float, default=3000.0)
    ap.add_argument("--periodic-budget", type=float, default=30.0)
    ap.add_argument("--periodic-quick", type=float, default=3.0)
    ap.add_argument("--periodic-max-t", type=int, default=24)
    ap.add_argument("--escalate-maxlevel", type=int, default=9)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    nrng = np.random.default_rng(args.seed)
    archive = load_rows(args.archive)
    parents = [r for r in load_rows(args.parents).values()
               if r.get("status") == "nontiler" and (r.get("hc") or 0) >= args.parent_min_hc
               and (r.get("cells") or len(shp.parse(r["shape"])[1])) >= args.parent_min_cells]
    if not parents:
        sys.exit("no parents")
    grid = shp.parse(parents[0]["shape"])[0]
    print(f"archive {len(archive)} shapes; {len(parents)} parents (hc >= {args.parent_min_hc}), cells "
          f"{min(len(shp.parse(p['shape'])[1]) for p in parents)}-{max(len(shp.parse(p['shape'])[1]) for p in parents)}",
          flush=True)
    taken = set(archive)
    for p in parents:
        taken.add(shp.canonical(*shp.parse(p["shape"])))

    def valid_new(cells):
        if not (args.min_cells <= len(cells) <= args.max_cells):
            return None
        ok, problems, _ = shp.check(shp.fmt(grid, cells))
        if not ok or any("stricter" in q for q in problems):
            return None
        canon = shp.canonical(grid, cells)
        return None if canon in taken else canon

    def mutant():
        p = rng.choice(parents)
        g, cells = shp.parse(p["shape"])
        steps = 1 + int(rng.random() < 0.3) + int(rng.random() < 0.1)
        new, op = mutate(g, cells, rng, steps)
        return valid_new(new), p, op

    import aner_scorer
    sc = aner_scorer.Scorer(args.scorer, "numpy")

    def predict(canons):
        feats, owner = [], []
        for c in canons:
            for v in sc.featurize(c):
                feats.append(v)
                owner.append(c)
        if not feats:
            return {}
        out = sc.score(np.stack(feats))
        tot, cnt = {}, {}
        for (_, h), c in zip(out, owner):
            tot[c] = tot.get(c, 0.0) + float(h)
            cnt[c] = cnt.get(c, 0) + 1
        return {c: tot[c] / cnt[c] for c in tot}

    proposals = []  # (canon, parent, op, generator)
    gen_time = {}
    for gen in args.generators.split(","):
        t0 = time.time()
        got = []
        if gen == "random":
            tries = 0
            while len(got) < args.n and tries < args.n * 200 and time.time() - t0 < args.gen_seconds:
                tries += 1
                canon, p, op = mutant()
                if canon:
                    taken.add(canon)
                    got.append((canon, p["shape"], op, gen))
        elif gen == "scored":
            while len(got) < args.n and time.time() - t0 < args.gen_seconds:
                cands = {}
                for _ in range(args.candidates * 20):
                    if len(cands) >= args.candidates:
                        break
                    canon, p, op = mutant()
                    if canon and canon not in cands:
                        cands[canon] = (p["shape"], op)
                if not cands:
                    break
                pr = predict(cands)
                for _, canon in sorted(((v, c) for c, v in pr.items()), reverse=True)[: args.pick]:
                    if canon not in taken and len(got) < args.n:
                        taken.add(canon)
                        got.append((canon, cands[canon][0], cands[canon][1], gen))
        elif gen.startswith("relax-"):
            import relax
            rx = relax.Relaxer(args.scorer, gen.split("-", 1)[1], "auto", min_cells=args.min_cells,
                               max_cells=args.max_cells, grow=args.relax_grow, tile_weight=args.relax_tile_weight)
            dry = 0
            while len(got) < args.n and time.time() - t0 < args.gen_seconds and dry < 20:
                batch = [rng.choice(parents) for _ in range(args.relax_parents)]
                before = len(got)
                for p, res in zip(batch, rx.relax_many([p["shape"] for p in batch], nrng, exclude=taken)):
                    for canon, info in res:
                        if canon not in taken and len(got) < args.n:
                            taken.add(canon)
                            got.append((canon, p["shape"], f"{gen}:r{info['round']}+{info['dist']}", gen))
                dry = dry + 1 if len(got) == before else 0
        else:
            sys.exit(f"unknown generator {gen}")
        dt = time.time() - t0
        gen_time[gen] = (len(got), dt)
        print(f"{gen:12s}: {len(got)} new shapes in {dt:.0f}s ({1000*dt/max(1,len(got)):.0f} ms per shape)", flush=True)
        proposals += got

    rng.shuffle(proposals)
    done = set()
    if os.path.exists(args.out):  # resume
        with open(args.out) as fh:
            for ln in fh:
                try:
                    done.add(json.loads(ln)["canon"])
                except Exception:
                    pass
    todo = [p for p in proposals if p[0] not in done]
    print(f"checking {len(todo)} shapes with {args.jobs} jobs ({len(done)} already in {args.out})", flush=True)
    workdir = tempfile.mkdtemp(prefix="halo_bakeoff_")
    t0 = time.time()
    with open(args.out, "a") as fh, ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(runner.classify, c, args, workdir): (c, par, op, g) for c, par, op, g in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            canon, parent, op, gen = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:
                rec = {"status": "error", "hc": None, "hh": None, "stderr": repr(exc)}
            record = rec.pop("record", None)
            row = {"canon": canon, "shape": canon, "grid": grid, "cells": (len(canon.split()) - 1) // 2,
                   "parent": parent, "op": op, "generator": gen, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            row.update(rec)
            if row["status"] == "nontiler" and (row["hc"] or 0) >= 3:
                row["witness"] = record
                print(f"  Hc={row['hc']} ({gen}, {row['cells']} cells): {canon}", flush=True)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if k % 500 == 0:
                print(f"  {k}/{len(todo)} checked, {k/(time.time()-t0):.1f}/s", flush=True)
    print("generation time: " + ", ".join(f"{g} {n} shapes in {t:.0f}s" for g, (n, t) in gen_time.items()))


if __name__ == "__main__":
    main()
