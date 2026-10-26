#!/usr/bin/env python3
"""HALO Track C: guided local search for polyforms with high Heesch numbers.

Starts from seed shapes (e.g. the Hc=3 shapes from a runner JSONL), repeatedly mutates
the best ones (add / remove / move a cell, keeping the shape connected, hole-free and
within the Epoch limits), checks every new shape with the full runner ladder
(heesch-sat + periodic tiling detector), and keeps an elite archive.

Every checked shape is appended to --log (JSONL, same fields as runner.py plus parent and
op), so a run can be stopped and resumed: on restart the archive is rebuilt from the log.

Usage (native macOS run, all cores):
  python3 halo/search.py --seeds results/hex11.jsonl --seed-min-hc 3 --log results/search_hex.jsonl \
      --max-cells 40 --maxlevel 7 --hours 8

With the learned scorer as a prefilter (ANER on Neural Engine + GPU):
  PYTHONPATH=/Volumes/Code/ANER/python python3 halo/search.py --seeds results/hex11.jsonl --seed-min-hc 3 \
      --log results/search_hex.jsonl --scorer results/models/scorer_hex11_b8.npz --hours 8

Optional continuous-relaxation generator (halo/relax.py, off by default): --relax-frac 0.25 gives
a quarter of the checks to shapes made by relaxing an elite parent to soft occupancies and following
the scorer's gradient ("cell" or Gaussian "splat" mode; several modes take turns). Logged as
generator search-relax-<mode>, so a run doubles as a bake-off against search / search-scored.

Square and hex grids only (mutation needs grid adjacency).
"""
import argparse
import collections
import heapq
import json
import math
import os
import random
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner  # noqa: E402
import shape as shp  # noqa: E402


def line_of(grid, cells):
    return shp.fmt(grid, cells)


def mutate(grid, cells, rng, steps):
    s = set(cells)
    nb = shp.NEIGHBOURS[grid]
    ops = []
    for _ in range(steps):
        r = rng.random()
        frontier = list({(x + dx, y + dy) for x, y in s for dx, dy in nb} - s)
        if r < 0.45 or len(s) <= 3:
            s.add(rng.choice(frontier))
            ops.append("add")
        elif r < 0.7:
            s.discard(rng.choice(sorted(s)))
            ops.append("remove")
        else:
            c = rng.choice(sorted(s))
            s.discard(c)
            frontier = list({(x + dx, y + dy) for x, y in s for dx, dy in nb} - s - {c})
            if not frontier:
                s.add(c)
                continue
            s.add(rng.choice(frontier))
            ops.append("move")
    return sorted(s), "+".join(ops)


PREFER_MIN_CELLS = 0  # set from --prefer-min-cells


def fitness(rec):
    """Sort key: higher is better. Non-tilers by hc, then (optionally) size in unexplored territory,
    then hh, then closeness to the next corona (defect), then (with a size target) closeness to it,
    then checker time at the deciding level."""
    if rec.get("status") != "nontiler" or rec.get("hc") is None:
        return (-1, 0, -1, -1.0, 0, 0.0)
    cells = rec.get("cells") or 0
    big = 1 if PREFER_MIN_CELLS and cells >= PREFER_MIN_CELLS else 0
    # with a size target, larger parents win ties (fewer cells to grow, closer to the target)
    near = min(cells, PREFER_MIN_CELLS) if PREFER_MIN_CELLS else 0
    return (rec["hc"], big, rec.get("hh") or rec["hc"], -defect_frac(rec), near, min(rec.get("seconds", 0.0), 600.0))


def defect_frac(rec):
    """Share of the cells next to an hc-patch that the best (hc+1)-corona found leaves
    uncovered (lower is closer to Heesch number hc+1); 1.0 when not measured."""
    d, r = rec.get("defect"), rec.get("ring")
    return d / r if d is not None and r else 1.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", required=True, help="runner JSONL or text file(s) of shape lines, comma-separated")
    ap.add_argument("--seed-min-hc", type=int, default=3)
    ap.add_argument("--log", required=True)
    ap.add_argument("--grid", default="", help="restrict to one grid (O or H); default: from seeds")
    ap.add_argument("--max-cells", type=int, default=40)
    ap.add_argument("--min-cells", type=int, default=4,
                    help="smallest shape to check. Parents below it are first grown (random frontier cells) up to "
                         "it, so e.g. --min-cells 18 with 15-17-cell parents explores 18+ cells, the sizes beyond "
                         "Kaplan's exhaustive polyhex enumeration")
    ap.add_argument("--parent-min-cells", type=int, default=0,
                    help="parents (elite and explore) only from shapes with at least this many cells")
    ap.add_argument("--elite", type=int, default=64, help="parents are drawn from the top-N archive")
    ap.add_argument("--prefer-min-cells", type=int, default=0,
                    help="among equal hc, prefer shapes with at least this many cells (e.g. 18 for hexes: "
                         "Kaplan enumerated all polyhexes up to 17 cells, max Hc 4)")
    ap.add_argument("--explore", type=float, default=0.1, help="chance to pick a random archived parent")
    ap.add_argument("--explore-min-hc", type=int, default=1,
                    help="random (explore) parents come from non-tilers with at least this hc. Run 2 filled the "
                         "archive with ~70k large Hc=0 shapes; exploring from those mostly breeds more of them")
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--max-evals", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--seed", type=int, default=0)
    # checker settings (same meaning as runner.py)
    ap.add_argument("--sat", default=runner.DEFAULT_SAT)
    ap.add_argument("--maxlevel", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--timeout-long", type=float, default=300.0)
    ap.add_argument("--mem-mb", type=float, default=3000.0)
    ap.add_argument("--periodic-budget", type=float, default=30.0)
    ap.add_argument("--periodic-quick", type=float, default=3.0)
    ap.add_argument("--periodic-max-t", type=int, default=24)
    ap.add_argument("--escalate-maxlevel", type=int, default=9,
                    help="re-check inconclusive shapes with no periodic tiling at this maxlevel")
    ap.add_argument("--retry-jobs", type=int, default=2,
                    help="shapes that hit the memory or time cap are re-checked, this many at a time, with "
                         "--retry-mem-mb and --retry-timeout (0 = log them as memout/timeout). High-Hc shapes "
                         "need more memory: runs 1-2 lost two Hc=4 and three Hc=3 shapes to the 3 GB cap")
    ap.add_argument("--retry-mem-mb", type=float, default=12000.0)
    ap.add_argument("--retry-timeout", type=float, default=1200.0)
    ap.add_argument("--defect-min-hc", type=int, default=3,
                    help="for non-tilers with at least this hc, also measure how close they come to the next "
                         "corona: the fewest uncovered cells next to an hc-patch (third_party/heesch-sat/"
                         "defect.cpp). Used as a fitness tie-breaker after hc and hh; 0 = off")
    ap.add_argument("--defect-timeout", type=float, default=120.0)
    ap.add_argument("--defect-confl", type=int, default=500000,
                    help="SAT conflict budget per defect solve; when it runs out the defect is an upper bound")
    ap.add_argument("--defect-mem-mb", type=float, default=6000.0)
    ap.add_argument("--retry-archived", action="store_true",
                    help="also re-check memout/timeout shapes already in the log (within --min/--max-cells)")
    # learned scorer prefilter (Track D)
    ap.add_argument("--scorer", default="", help="scorer weights (.npz from scorer.py); enables the prefilter")
    ap.add_argument("--scorer-schedule", default="ane", choices=["ane", "split", "gpu", "mlx", "numpy"],
                    help="where to run the scorer. Default ane: the Neural Engine alone is ~8x more than the "
                         "search needs and leaves the GPU free for retraining (mlx = GPU via MLX fp16)")
    ap.add_argument("--candidates", type=int, default=2048, help="mutants generated and scored per refill")
    ap.add_argument("--pick", type=int, default=32, help="best-scoring mutants queued for checking per refill")
    ap.add_argument("--score-formula", default="hc", choices=["hc", "hc_tile"],
                    help="rank candidates by predicted hc ('hc', default) or hc*(1-p_tile). High-Heesch shapes "
                         "look like near-tilers, so penalizing tiler-likeness also throws away the best shapes "
                         "(held-out search data: top 5%% hc>=2 yield 3.6%% with 'hc' vs 2.6%% with 'hc_tile')")
    ap.add_argument("--random-frac", type=float, default=0.1,
                    help="fraction of checks given to unscored random mutants (keeps the scorer honest)")
    ap.add_argument("--guard-checks", type=int, default=2000,
                    help="switch off a guided generator (scored or relaxation) when, over its last N checks, its "
                         "Hc>=2 rate is below --guard-ratio times the random mutants' rate over their last N "
                         "(needs >= 500 random checks; 0 = no guard). Run 2's scorer ran away to big shapes it "
                         "overrated and fell to 0.3%% vs 1.1%% for random mutants")
    ap.add_argument("--guard-ratio", type=float, default=0.5)
    # continuous relaxation generator (relax.py); off unless --relax-frac > 0
    ap.add_argument("--relax-frac", type=float, default=0.0,
                    help="fraction of checks given to relaxation-generated shapes (needs --scorer); 0 = off. "
                         "--random-frac then applies to the remaining checks")
    ap.add_argument("--relax-mode", default="splat",
                    help="relaxation mode(s), comma-separated, taking turns: cell, splat")
    ap.add_argument("--relax-backend", default="auto", choices=["auto", "mlx", "numpy"],
                    help="gradient backend (auto: MLX on the GPU if installed, else NumPy on the CPU)")
    ap.add_argument("--relax-parents", type=int, default=16,
                    help="elite parents relaxed together (one batched scorer call per step) per refill")
    ap.add_argument("--relax-rounds", type=int, default=6)
    ap.add_argument("--relax-steps", type=int, default=30)
    ap.add_argument("--relax-max-flips", type=int, default=4, help="cells changed per relaxation round, at most")
    ap.add_argument("--relax-grow", type=int, default=4, help="cells a relaxed shape may gain vs its parent")
    ap.add_argument("--relax-tile-weight", type=float, default=1.0,
                    help="relaxation objective = hc_hat - w * softplus(tile logit). The hc head ignores tilers, "
                         "so with w = 0 relaxation drifts into tilers")
    ap.add_argument("--relax-shrink", type=int, default=0,
                    help="cells a relaxed shape may lose vs its parent (unconstrained, relaxation shrinks "
                         "shapes into sizes the scorer never saw)")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    global PREFER_MIN_CELLS
    PREFER_MIN_CELLS = args.prefer_min_cells

    archive = {}  # canonical line -> record
    if os.path.exists(args.log):
        with open(args.log) as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                    archive[r["canon"]] = r
                except Exception:
                    pass
    print(f"resumed {len(archive)} shapes from {args.log}" if archive else "fresh run", flush=True)

    seeds = []
    for seed_path in args.seeds.split(","):
      with open(seed_path) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            if seed_path.endswith(".jsonl"):
                r = json.loads(ln)
                if r.get("status") == "nontiler" and (r.get("hc") or 0) >= args.seed_min_hc:
                    seeds.append(r)
            else:
                seeds.append({"shape": ln, "status": "unknown"})
    grids = {s["shape"].split()[0].rstrip("?") for s in seeds}
    grid = args.grid or (grids.pop() if len(grids) == 1 else "")
    if grid not in ("O", "H"):
        sys.exit(f"need seeds from one square or hex grid (got {grids}); use --grid")
    for s in seeds:
        g, cells = shp.parse(s["shape"])
        canon = shp.canonical(g, cells)
        old = archive.get(canon)
        if old is None or (old.get("status") not in ("nontiler", "isohedral", "periodic")
                           and s.get("status") == "nontiler"):
            rec = dict(s)
            rec.update({"canon": canon, "shape": canon, "parent": None, "op": "seed", "cells": len(cells)})
            archive[canon] = rec
    print(f"{len(seeds)} seeds on grid {grid}; archive {len(archive)}", flush=True)

    workdir = tempfile.mkdtemp(prefix="halo_search_")
    lock = threading.Lock()
    deadline = time.monotonic() + args.hours * 3600
    evals = 0
    best_seen = max((fitness(r) for r in archive.values()), default=(-1, -1, 0))
    print(f"best so far: hc={best_seen[0]}", flush=True)

    # Parents: all non-tilers (`live`) and the top-N of them (`elite`). Both are kept up to date
    # incrementally; re-sorting the whole archive per candidate made the first overnight run
    # spend >95% of its time in Python with the checker cores idle.
    def ncells(r):
        return r.get("cells") or (len(r["canon"].split()) - 1) // 2

    live = [r for r in archive.values() if r.get("status") == "nontiler"]  # all non-tilers (stats)
    parent_pool = [r for r in live if ncells(r) >= args.parent_min_cells]
    explore_pool = [r for r in parent_pool if (r.get("hc") or 0) >= args.explore_min_hc]
    elite_state = {"elite": [], "dirty": True}

    def note_result(row):
        if row.get("status") != "nontiler":
            return
        live.append(row)
        if ncells(row) < args.parent_min_cells:
            return
        parent_pool.append(row)
        if (row.get("hc") or 0) >= args.explore_min_hc:
            explore_pool.append(row)
        el = elite_state["elite"]
        if len(el) < args.elite or fitness(row) > fitness(el[-1]):
            elite_state["dirty"] = True

    def pick_parent():
        if not parent_pool:
            return None
        if rng.random() < args.explore and explore_pool:
            return rng.choice(explore_pool)
        if elite_state["dirty"]:
            elite_state["elite"] = heapq.nlargest(args.elite, parent_pool, key=fitness)
            elite_state["dirty"] = False
        return rng.choice(elite_state["elite"])

    def gen_candidate(exclude=()):
        """A new valid mutant (canon, parent canon, op), not yet in the archive; None if stuck."""
        for _ in range(200):
            parent = pick_parent()
            if parent is None:
                return None
            g, cells = shp.parse(parent["canon"])
            grown = 0
            if len(cells) < args.min_cells:  # grow small parents up to the size floor first
                s = set(cells)
                nb = shp.NEIGHBOURS[g]
                while len(s) < args.min_cells:
                    s.add(rng.choice(sorted({(x + dx, y + dy) for x, y in s for dx, dy in nb} - s)))
                    grown += 1
                cells = sorted(s)
            steps = 1 + int(rng.random() < 0.3) + int(rng.random() < 0.1)
            new, op = mutate(g, cells, rng, steps)
            if grown:
                op = f"grow{grown}+{op}"
            if not (args.min_cells <= len(new) <= args.max_cells):
                continue
            ok, problems, info = shp.check(line_of(g, new))
            if not ok or any("stricter" in p for p in problems):
                continue
            canon = shp.canonical(g, new)
            if canon in archive or canon in exclude:
                continue
            return canon, parent["canon"], op
        return None

    def propose():
        """An unscored random mutant, marked pending."""
        c = gen_candidate()
        if c is None:
            return None
        with lock:
            archive[c[0]] = {"canon": c[0], "status": "pending"}
        return c + (None,)

    sc = None
    if args.scorer:
        import aner_scorer
        sc = aner_scorer.Scorer(args.scorer, args.scorer_schedule)
        print(f"scorer: {args.scorer} on {sc.backend}; {args.candidates} candidates -> best {args.pick} "
              f"per refill, {args.random_frac:.0%} random checks", flush=True)
    queue = []  # list of (pred, canon, parent, op), best first

    def predict(canons):
        """Scorer prediction per shape (mean over its symmetric images); shapes that fit no
        orientation of the window are left out."""
        feats, owner = [], []
        for canon in canons:
            for v in sc.featurize(canon):
                feats.append(v)
                owner.append(canon)
        if not feats:
            return {}
        out = sc.score(np.stack(feats))
        tot, cnt = {}, {}
        for (tile, hc_hat), canon in zip(out, owner):
            v = float(hc_hat)
            if args.score_formula == "hc_tile":
                v *= 1.0 - 1.0 / (1.0 + math.exp(-float(tile)))
            tot[canon] = tot.get(canon, 0.0) + v
            cnt[canon] = cnt.get(canon, 0) + 1
        return {c: tot[c] / cnt[c] for c in tot}

    def refill():
        cands = {}
        for _ in range(args.candidates * 3):
            if len(cands) >= args.candidates:
                break
            c = gen_candidate(exclude=cands)
            if c is None:
                break
            cands[c[0]] = c
        preds = predict(cands)
        ranked = sorted(((v, c) for c, v in preds.items()), reverse=True)[: args.pick]
        with lock:
            for pred, canon in ranked:
                if canon in archive:
                    continue
                archive[canon] = {"canon": canon, "status": "pending"}
                _, parent, op = cands[canon]
                queue.append((pred, canon, parent, op))
        queue.sort(key=lambda q: -q[0])

    relaxers, rqueue = [], []
    if args.relax_frac > 0:
        if sc is None:
            sys.exit("--relax-frac needs --scorer")
        import relax as relax_mod
        for mode in args.relax_mode.split(","):
            relaxers.append(relax_mod.Relaxer(
                args.scorer, mode.strip(), args.relax_backend, rounds=args.relax_rounds, steps=args.relax_steps,
                max_flips=args.relax_max_flips, min_cells=args.min_cells, max_cells=args.max_cells,
                shrink=args.relax_shrink, grow=args.relax_grow, tile_weight=args.relax_tile_weight))
        print(f"relaxation: {args.relax_frac:.0%} of checks, modes {args.relax_mode}, "
              f"gradients on {relaxers[0].backend}", flush=True)
    nrng = np.random.default_rng(args.seed)
    relax_turn = [0]

    def refill_relax():
        rx = relaxers[relax_turn[0] % len(relaxers)]
        relax_turn[0] += 1
        made = []
        parents = [p for p in (pick_parent() for _ in range(args.relax_parents)) if p is not None]
        for parent, res in zip(parents, rx.relax_many([p["canon"] for p in parents], nrng, exclude=archive)):
            for canon, info in res:
                op = f"relax-{rx.mode}:r{info['round']}+{info['dist']}"
                made.append((canon, parent["canon"], op))
        preds = predict([m[0] for m in made])
        with lock:
            for canon, parent, op in made:
                if canon in archive:
                    continue
                archive[canon] = {"canon": canon, "status": "pending"}
                rqueue.append((canon, parent, op, preds.get(canon)))

    disabled = set()  # guided generators switched off by the guard

    def next_job():
        if relaxers and rng.random() < args.relax_frac:
            if not rqueue:
                refill_relax()
            if rqueue:
                return rqueue.pop(0)
        if sc is None or "search-scored" in disabled or rng.random() < args.random_frac:
            return propose()
        if not queue:
            refill()
        if not queue:
            return propose()
        pred, canon, parent, op = queue.pop(0)
        return canon, parent, op, pred

    gen_stats = {}
    recent = {}  # generator -> deque of recent outcomes (1 = Hc>=2) for the guard

    def guard():
        n_r = len(recent.get("search", ()))
        if not args.guard_checks or n_r < min(500, args.guard_checks):
            return
        rate_r = sum(recent["search"]) / n_r
        if rate_r == 0:
            return
        for gen, dq in recent.items():
            if gen == "search" or gen in disabled or len(dq) < args.guard_checks:
                continue
            k = sum(dq)
            if k / len(dq) < args.guard_ratio * rate_r:
                disabled.add(gen)
                print(f"  GUARD: switching off {gen}: Hc>=2 in {k}/{len(dq)} of its last checks "
                      f"({100*k/len(dq):.2f}%) vs random mutants {100*rate_r:.2f}% (last {n_r})", flush=True)
                if gen == "search-scored":
                    queue.clear()
                elif gen.startswith("search-relax-"):
                    mode = gen[len("search-relax-"):]
                    relaxers[:] = [r for r in relaxers if r.mode != mode]
                    rqueue[:] = [q for q in rqueue if not q[2].startswith(f"relax-{mode}:")]

    def generator_of(op, pred):
        if op.startswith("relax-"):
            return "search-" + op.split(":")[0]
        return "search-scored" if pred is not None else "search"

    def check(canon, opts):
        """Checker ladder, plus the next-corona defect for high-hc non-tilers."""
        rec = runner.classify(canon, opts, workdir)
        if (args.defect_min_hc and rec.get("status") == "nontiler"
                and (rec.get("hc") or 0) >= args.defect_min_hc):
            rec.update(runner.run_defect(canon, rec["hc"], rec.get("hh") or rec["hc"], args.defect_timeout,
                                         args.defect_mem_mb, args.defect_confl))
        return rec

    closest = {}  # hc -> best defect fraction seen this run at the size target

    # Shapes that hit the memory/time cap go to a retry queue with a bigger budget (few at a time).
    retry_opts = argparse.Namespace(**vars(args))
    retry_opts.mem_mb = args.retry_mem_mb
    retry_opts.timeout = args.timeout_long
    retry_opts.timeout_long = args.retry_timeout
    retry_q = collections.deque()
    if args.retry_jobs and args.retry_archived:
        for r in list(archive.values()):
            if r.get("status") in ("memout", "timeout") and args.min_cells <= ncells(r) <= args.max_cells:
                first = {k: r.get(k) for k in ("status", "seconds", "peak_rss_mb")}
                retry_q.append((r["canon"], r.get("parent"), r.get("op") or "", r.get("pred"), first))
        print(f"re-checking {len(retry_q)} archived memout/timeout shapes with {args.retry_mem_mb:.0f} MB", flush=True)

    with open(args.log, "a") as logfh, ThreadPoolExecutor(max_workers=args.jobs + args.retry_jobs) as pool:
        running = {}  # future -> (canon, parent, op, pred, first result if this is a retry else None)
        n_retry = 0
        t0 = time.monotonic()
        while True:
            stop = time.monotonic() > deadline or (args.max_evals and evals >= args.max_evals)
            while not stop and retry_q and n_retry < args.retry_jobs:
                item = retry_q.popleft()
                running[pool.submit(check, item[0], retry_opts)] = item
                n_retry += 1
            while not stop and len(running) - n_retry < args.jobs:
                prop = next_job()
                if prop is None:
                    break
                canon, parent, op, pred = prop
                running[pool.submit(check, canon, args)] = (canon, parent, op, pred, None)
            if not running:
                break
            done, _ = wait(list(running), return_when=FIRST_COMPLETED)
            for fut in done:
                canon, parent, op, pred, first = running.pop(fut)
                if first is not None:
                    n_retry -= 1
                try:
                    rec = fut.result()
                except Exception as exc:
                    rec = {"status": "error", "hc": None, "hh": None, "stderr": repr(exc)}
                if first is None and args.retry_jobs and rec.get("status") in ("memout", "timeout"):
                    retry_q.append((canon, parent, op, pred,
                                    {k: rec.get(k) for k in ("status", "seconds", "peak_rss_mb")}))
                    print(f"  {rec['status']} at {args.mem_mb:.0f} MB / {args.timeout_long:.0f} s, queued for a "
                          f"{args.retry_mem_mb:.0f} MB re-check ({len(retry_q)} waiting): {canon}", flush=True)
                    continue
                record = rec.pop("record", None)
                row = {"canon": canon, "shape": canon, "grid": grid, "cells": (len(canon.split()) - 1) // 2,
                       "parent": parent, "op": op, "generator": generator_of(op, pred),
                       "pred": None if pred is None else round(pred, 4), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
                row.update(rec)
                if first is not None:
                    row["retried_from"] = first
                    print(f"  re-check done: {row['status']} hc={row.get('hc')} ({row['cells']} cells, "
                          f"{row.get('seconds', 0):.0f} s, {row.get('peak_rss_mb') or 0:.0f} MB): {canon}", flush=True)
                if row["status"] == "nontiler" and (row["hc"] or 0) >= 3:
                    row["witness"] = record
                with lock:
                    archive[canon] = row
                    note_result(row)
                    logfh.write(json.dumps(row) + "\n")
                    logfh.flush()
                evals += 1
                ga, gg, gt = gen_stats.get(row["generator"], (0, 0, 0))
                good = int(row["status"] == "nontiler" and (row["hc"] or 0) >= 2)
                gen_stats[row["generator"]] = (ga + 1, gg + good, gt + int(row["status"] in ("isohedral", "periodic")))
                if args.guard_checks:
                    if row["generator"] not in recent:
                        recent[row["generator"]] = collections.deque(maxlen=args.guard_checks)
                    recent[row["generator"]].append(good)
                f = fitness(row)
                if (row.get("defect") is not None and row.get("ring")
                        and row["cells"] >= (PREFER_MIN_CELLS or 0)):
                    frac = row["defect"] / row["ring"]
                    if frac < closest.get(row["hc"], 2.0):
                        closest[row["hc"]] = frac
                        print(f"  closest yet to hc={row['hc'] + 1} ({row['cells']} cells): {row['defect']} of "
                              f"{row['ring']} cells uncovered (score {row['hc'] + 1 - frac:.4f}"
                              f"{'' if row.get('defect_exact') else ', upper bound'}): {canon}", flush=True)
                if f[0] > best_seen[0]:
                    best_seen = f
                    print(f"  NEW BEST hc={row['hc']} hh={row['hh']} cells={row['cells']}: {canon}", flush=True)
                if evals % 100 == 0:
                    guard()
                    hist = {}
                    for r in live:
                        hist[r["hc"]] = hist.get(r["hc"], 0) + 1
                    rate = evals / (time.monotonic() - t0)
                    print(f"  {evals} evals, {rate:.1f}/s, archive {len(archive)}, non-tilers by hc: "
                          + ", ".join(f"{k}:{v}" for k, v in sorted(hist.items())), flush=True)
                    if sc is not None:
                        for gen in sorted(gen_stats):
                            n_all, n_good, n_tile = gen_stats[gen]
                            if n_all:
                                print(f"     {gen:19s}: {n_all} checked, hc>=2 {n_good} ({100*n_good/n_all:.1f}%), "
                                      f"tilers {100*n_tile/n_all:.0f}%" + ("  [switched off]" if gen in disabled else ""),
                                      flush=True)
        for canon, parent, op, pred, first in retry_q:  # not re-checked before the stop: keep them findable
            row = {"canon": canon, "shape": canon, "grid": grid, "cells": (len(canon.split()) - 1) // 2,
                   "parent": parent, "op": op, "generator": generator_of(op, pred), "hc": None, "hh": None,
                   "pred": None if pred is None else round(pred, 4), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            row.update(first)
            logfh.write(json.dumps(row) + "\n")
        if retry_q:
            print(f"{len(retry_q)} shapes still waiting for a re-check were logged as {first['status']}; "
                  f"rerun with --retry-archived to check them", flush=True)
    print(f"done: {evals} evaluations; best hc={best_seen[0]}")
    top = sorted((r for r in archive.values() if r.get("status") == "nontiler"), key=fitness, reverse=True)[:10]
    for r in top:
        print(f"  hc={r['hc']} hh={r.get('hh')} cells={r.get('cells')} {r['canon']}")


if __name__ == "__main__":
    main()
