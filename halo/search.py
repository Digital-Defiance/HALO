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

Neighbourhood sweep (on by default, --sweep-min-hc 3): every one-cell edit of each parent with
hc >= 3 is checked, best parents first, and each new hc >= 3 find is swept in turn. Logged as
generator search-sweep.

Square and hex grids only (mutation needs grid adjacency).
"""
import argparse
import collections
import contextlib
import functools
import hashlib
import heapq
import json
import math
import os
import random
import sys
import tempfile
import threading
import time
import uuid
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


def fmt_dur(seconds):
    seconds = max(0, int(seconds))
    h, m = divmod(seconds // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{seconds % 60:02d}s"


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
    ap.add_argument("--sweep-min-hc", type=int, default=3,
                    help="systematically check every one-cell edit (add, remove, move) of each parent with at "
                         "least this hc, best parents first; new finds at that level are swept too. 0 = off")
    ap.add_argument("--sweep-frac", type=float, default=0.5,
                    help="fraction of checks given to the sweep while it has work")
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
    ap.add_argument("--scorer-schedule", default="ane", choices=["ane", "split", "gpu", "mlx", "mlx-fp32", "numpy"],
                    help="where to run the scorer. Default ane: the Neural Engine alone is ~8x more than the "
                         "search needs and leaves the GPU free for retraining (mlx = GPU via MLX fp16; "
                         "mlx-fp32 = MLX with FP32 weights and arithmetic)")
    ap.add_argument("--scorer-spatial", type=int, choices=[64, 128, 256, 512], default=256,
                    help="ANER tile width; 256 reduced v4's 24,576-image ANE batch latency from 85 to 47 ms "
                         "on the M4 Max. The GPU's chunk width is controlled separately by ANER_GPU_CHUNK")
    ap.add_argument("--candidates", type=int, default=2048, help="mutants generated and scored per refill")
    ap.add_argument("--pick", type=int, default=32, help="best-scoring mutants queued for checking per refill")
    ap.add_argument("--score-formula", default="hc", choices=["hc", "hc_tile"],
                    help="rank candidates by predicted hc ('hc', default) or hc*(1-p_tile). High-Heesch shapes "
                         "look like near-tilers, so penalizing tiler-likeness also throws away the best shapes "
                         "(held-out search data: top 5%% hc>=2 yield 3.6%% with 'hc' vs 2.6%% with 'hc_tile')")
    ap.add_argument("--random-frac", type=float, default=0.1,
                    help="chance of random mutants on non-sweep/non-relaxation checks when scored picks "
                         "are ready; random mutants also fill background-refill gaps")
    ap.add_argument("--guard-checks", type=int, default=2000,
                    help="compare a guided generator (scored or relaxation) when, over its last N checks, its "
                         "Hc>=2 rate is below --guard-ratio times the random mutants' rate over their last N "
                         "(needs >= 500 random checks; 0 = no guard). This is a heuristic, not a significance test")
    ap.add_argument("--guard-ratio", type=float, default=0.5)
    ap.add_argument("--guard-mode", choices=["warn", "disable", "off"], default="warn",
                    help="warn (default) keeps guided generators running and reports low recent yield; "
                         "disable restores permanent shutoff for the run; off skips monitoring. Sparse "
                         "0-vs-1 windows are insufficient evidence to disable a scorer automatically")
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
    if args.jobs < 1 or args.retry_jobs < 0 or args.elite < 1:
        ap.error("--jobs and --elite must be positive; --retry-jobs must be nonnegative")
    if args.min_cells < 1 or args.max_cells < args.min_cells:
        ap.error("need 1 <= --min-cells <= --max-cells")
    if args.hours <= 0 or args.max_evals < 0 or args.candidates < 1 or args.pick < 1:
        ap.error("--hours, --candidates and --pick must be positive; --max-evals must be nonnegative")
    if args.guard_checks < 0 or not math.isfinite(args.guard_ratio) or args.guard_ratio < 0:
        ap.error("--guard-checks and --guard-ratio must be nonnegative, with a finite ratio")
    if any(not 0 <= x <= 1 for x in (args.explore, args.sweep_frac, args.random_frac, args.relax_frac)):
        ap.error("generator fractions and --explore must be between 0 and 1")
    rng = random.Random(args.seed)
    global PREFER_MIN_CELLS
    PREFER_MIN_CELLS = args.prefer_min_cells

    runner.ensure_jsonl_boundary(args.log)
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

    run_id = uuid.uuid4().hex
    def run_event(event, **info):
        # A separate append-only file keeps old shape-only JSONL readers compatible.
        with open(args.log + ".runs.jsonl", "a") as fh:
            fh.write(json.dumps({"run_id": run_id, "event": event,
                                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **info}) + "\n")

    hashes = {}
    for path in [__file__, runner.__file__, shp.__file__,
                 os.path.join(os.path.dirname(__file__), "aner_scorer.py"),
                 os.path.join(os.path.dirname(__file__), "scorer.py"), args.scorer]:
        if path and os.path.isfile(path):
            digest = hashlib.sha256()
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(1024 * 1024), b""):
                    digest.update(block)
            hashes[os.path.abspath(path)] = digest.hexdigest()
    run_event("started", options=vars(args), sha256=hashes, python=sys.version, platform=sys.platform)
    print(f"run {run_id}; settings and source/model hashes: {args.log}.runs.jsonl", flush=True)

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
    hc_hist = collections.Counter(r["hc"] for r in live)
    parent_pool = [r for r in live if ncells(r) >= args.parent_min_cells]
    explore_pool = [r for r in parent_pool if (r.get("hc") or 0) >= args.explore_min_hc]
    elite_state = {"elite": [], "dirty": True}

    sweep_heap = []  # (-fitness, tiebreak, canon) of parents whose neighbourhood is still to be swept
    swept = set()

    def want_sweep(row):
        if args.sweep_min_hc and (row.get("hc") or 0) >= args.sweep_min_hc and row["canon"] not in swept:
            swept.add(row["canon"])
            heapq.heappush(sweep_heap, (tuple(-x for x in fitness(row)), len(swept), row["canon"]))

    def note_result(row):
        if row.get("status") != "nontiler":
            return
        live.append(row)
        hc_hist[row["hc"]] += 1
        if ncells(row) < args.parent_min_cells:
            return
        want_sweep(row)
        parent_pool.append(row)
        if (row.get("hc") or 0) >= args.explore_min_hc:
            explore_pool.append(row)
        el = elite_state["elite"]
        if len(el) < args.elite or fitness(row) > fitness(el[-1]):
            elite_state["dirty"] = True

    def elite_parents():
        if elite_state["dirty"]:
            elite_state["elite"] = heapq.nlargest(args.elite, parent_pool, key=fitness)
            elite_state["dirty"] = False
        return elite_state["elite"]

    def pick_parent():
        if not parent_pool:
            return None
        if rng.random() < args.explore and explore_pool:
            return rng.choice(explore_pool)
        return rng.choice(elite_parents())

    @functools.lru_cache(maxsize=4096)
    def parent_cells(canon):
        g, cells = shp.parse(canon)
        return g, tuple(cells)

    def gen_candidate(exclude=(), source=rng, parents=None):
        """A new valid mutant (canon, parent canon, op), not yet in the archive; None if stuck."""
        for _ in range(200):
            if parents is None:
                parent = pick_parent()
            else:
                el, ex = parents
                choices = ex if ex and source.random() < args.explore else el
                parent = source.choice(choices) if choices else None
            if parent is None:
                return None
            g, cells = parent_cells(parent["canon"])
            grown = 0
            if len(cells) < args.min_cells:  # grow small parents up to the size floor first
                s = set(cells)
                nb = shp.NEIGHBOURS[g]
                while len(s) < args.min_cells:
                    s.add(source.choice(sorted({(x + dx, y + dy) for x, y in s for dx, dy in nb} - s)))
                    grown += 1
                cells = sorted(s)
            steps = 1 + int(source.random() < 0.3) + int(source.random() < 0.1)
            new, op = mutate(g, cells, source, steps)
            if grown:
                op = f"grow{grown}+{op}"
            if not (args.min_cells <= len(new) <= args.max_cells):
                continue
            ok, problems, info = shp.check_cells(g, new)
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
        sc = aner_scorer.Scorer(args.scorer, args.scorer_schedule, args.scorer_spatial)
        print(f"scorer: {args.scorer} on {sc.backend}; {args.candidates} candidates -> best {args.pick} "
              f"per refill, {args.random_frac:.0%} random checks; "
              f"guard={args.guard_mode if args.guard_checks else 'off'}", flush=True)
    queue = []  # list of (pred, canon, parent, op), best first
    scorer_lock = threading.Lock()
    scored_rng = random.Random(args.seed + 1)
    scored_future = None
    producer_stop = threading.Event()
    generation_seconds = 0.0

    def predict(canons):
        """Scorer prediction per shape (mean over its symmetric images); shapes that fit no
        orientation of the window are left out."""
        canons = list(canons)
        if hasattr(sc, "featurize_many"):
            feats, owner = sc.featurize_many(canons)
            if not len(feats):
                return {}
            with scorer_lock:
                out = sc.score(feats)
            values = out[:, 1].astype(np.float64)
            if args.score_formula == "hc_tile":
                values /= 1.0 + np.exp(np.clip(out[:, 0].astype(np.float64), -700, 700))
            if len(set(canons)) != len(canons):
                unique = list(dict.fromkeys(canons))
                indices = {canon: i for i, canon in enumerate(unique)}
                owner = np.array([indices[c] for c in canons], dtype=np.intp)[owner]
                canons = unique
            totals = np.bincount(owner, weights=values, minlength=len(canons))
            counts = np.bincount(owner, minlength=len(canons))
            return {canons[i]: float(totals[i] / counts[i]) for i in np.flatnonzero(counts)}
        feats, owner = [], []
        for canon in canons:
            for v in sc.featurize(canon):
                feats.append(v)
                owner.append(canon)
        if not feats:
            return {}
        with scorer_lock:  # relaxation may also use this scorer
            out = sc.score(np.stack(feats))
        tot, cnt = {}, {}
        for (tile, hc_hat), canon in zip(out, owner):
            v = float(hc_hat)
            if args.score_formula == "hc_tile":
                v *= 1.0 - 1.0 / (1.0 + math.exp(-float(tile)))
            tot[canon] = tot.get(canon, 0.0) + v
            cnt[canon] = cnt.get(canon, 0) + 1
        return {c: tot[c] / cnt[c] for c in tot}

    def refill(parents):
        """Build a batch off the dispatcher thread; publish results on that thread only."""
        start = time.monotonic()
        cands = {}
        for _ in range(args.candidates * 3):
            if producer_stop.is_set() or len(cands) >= args.candidates:
                break
            c = gen_candidate(exclude=cands, source=scored_rng, parents=parents)
            if c is None:
                break
            cands[c[0]] = c
        preds = predict(cands)
        ranked = sorted(((v, c) for c, v in preds.items()), reverse=True)[: args.pick]
        return [(pred, *cands[canon]) for pred, canon in ranked], time.monotonic() - start

    def start_refill():
        nonlocal scored_future
        if (scored_future is None and sc is not None and args.random_frac < 1
                and "search-scored" not in disabled):
            parents = (tuple(elite_parents()), tuple(explore_pool))
            scored_future = proposal_pool.submit(refill, parents)

    def collect_refill():
        nonlocal scored_future, generation_seconds
        if scored_future is None or not scored_future.done():
            return
        ranked, seconds = scored_future.result()
        scored_future = None
        generation_seconds += seconds
        if "search-scored" in disabled:
            return
        with lock:
            for pred, canon, parent, op in ranked:
                if canon in archive:
                    continue
                archive[canon] = {"canon": canon, "status": "pending"}
                queue.append((pred, canon, parent, op))
        queue.sort(key=lambda q: -q[0])

    for r in parent_pool:
        want_sweep(r)
    sweep_q = collections.deque()

    def neighbours(canon):
        """Every valid, unchecked one-cell edit (add, remove, move) of a shape."""
        g, cells = shp.parse(canon)
        s = set(cells)
        nb = shp.NEIGHBOURS[g]
        frontier = sorted({(x + dx, y + dy) for x, y in s for dx, dy in nb} - s)
        edits = [(sorted(s | {f}), "add") for f in frontier]
        for c in sorted(s):
            rest = s - {c}
            edits.append((sorted(rest), "remove"))
            for f in sorted({(x + dx, y + dy) for x, y in rest for dx, dy in nb} - rest - {c}):
                edits.append((sorted(rest | {f}), "move"))
        out, seen = [], set()
        for new, op in edits:
            if not (args.min_cells <= len(new) <= args.max_cells):
                continue
            ok, problems, _ = shp.check_cells(g, new)
            if not ok or any("stricter" in q for q in problems):
                continue
            k = shp.canonical(g, new)
            if k in archive or k in seen:
                continue
            seen.add(k)
            out.append((k, "sweep:" + op))
        return out

    sweep_stats = {"parents": 0, "edits": 0}  # for the sweep ETA

    def next_sweep():
        while sweep_q or sweep_heap:
            if not sweep_q:
                _, _, parent = heapq.heappop(sweep_heap)
                found = neighbours(parent)
                sweep_stats["parents"] += 1
                sweep_stats["edits"] += len(found)
                sweep_q.extend((k, parent, op) for k, op in found)
            while sweep_q:
                k, parent, op = sweep_q.popleft()
                if k in archive:
                    continue
                with lock:
                    archive[k] = {"canon": k, "status": "pending"}
                return k, parent, op, None
        return None

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
        collect_refill()
        if len(queue) <= max(1, args.pick // 2):
            start_refill()
        if args.sweep_min_hc and rng.random() < args.sweep_frac:
            job = next_sweep()
            if job is not None:
                return job
        if relaxers and rng.random() < args.relax_frac:
            if not rqueue:
                refill_relax()
            if rqueue:
                return rqueue.pop(0)
        if sc is None or "search-scored" in disabled or rng.random() < args.random_frac:
            return propose()
        if not queue:
            # Keep checkers fed while the next scored batch is generated.
            return propose()
        pred, canon, parent, op = queue.pop(0)
        return canon, parent, op, pred

    gen_stats = {}
    recent = {}  # generator -> deque of recent outcomes (1 = Hc>=2) for the guard
    last_guard_warning = {}  # generator -> completed checks at its last warning

    def guard():
        n_r = len(recent.get("search", ()))
        if args.guard_mode == "off" or not args.guard_checks or n_r < min(500, args.guard_checks):
            return
        rate_r = sum(recent["search"]) / n_r
        if rate_r == 0:
            return
        for gen, dq in recent.items():
            guided = gen == "search-scored" or gen.startswith("search-relax-")
            if not guided or gen in disabled or len(dq) < args.guard_checks:
                continue
            k = sum(dq)
            if k / len(dq) < args.guard_ratio * rate_r:
                info = {"generator": gen, "guided_hits": k, "guided_checks": len(dq),
                        "random_hits": sum(recent["search"]), "random_checks": n_r,
                        "completed_evaluations": evals, "mode": args.guard_mode}
                if args.guard_mode == "warn":
                    completed = gen_stats[gen][0]
                    info["guided_completed"] = completed
                    previous = last_guard_warning.get(gen)
                    if previous is None or completed - previous >= args.guard_checks:
                        last_guard_warning[gen] = completed
                        print(f"  GUARD warning: {gen} stays enabled: recent Hc>=2 {k}/{len(dq)} "
                              f"vs random {info['random_hits']}/{n_r}; heuristic comparison, "
                              "monitoring only", flush=True)
                        run_event("generator_guard_warning", **info)
                    continue
                disabled.add(gen)
                run_event("generator_guard_disabled", **info)
                print(f"  GUARD: switching off {gen}: Hc>=2 in {k}/{len(dq)} of its last checks "
                      f"({100*k/len(dq):.2f}%) vs random mutants {100*rate_r:.2f}% (last {n_r})", flush=True)
                if gen == "search-scored":
                    for _, canon, _, _ in queue:
                        if archive.get(canon, {}).get("status") == "pending":
                            archive.pop(canon)
                    queue.clear()
                elif gen.startswith("search-relax-"):
                    mode = gen[len("search-relax-"):]
                    relaxers[:] = [r for r in relaxers if r.mode != mode]
                    for canon, _, op, _ in rqueue:
                        if op.startswith(f"relax-{mode}:") and archive.get(canon, {}).get("status") == "pending":
                            archive.pop(canon)
                    rqueue[:] = [q for q in rqueue if not q[2].startswith(f"relax-{mode}:")]

    def generator_of(op, pred):
        if op.startswith("relax-"):
            return "search-" + op.split(":")[0]
        if op.startswith("sweep:"):
            return "search-sweep"
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
                first = {k: r.get(k) for k in ("status", "seconds", "total_seconds", "peak_rss_mb") if k in r}
                retry_q.append((r["canon"], r.get("parent"), r.get("op") or "", r.get("pred"), first))
        print(f"re-checking {len(retry_q)} archived memout/timeout shapes with {args.retry_mem_mb:.0f} MB", flush=True)

    with open(args.log, "a") as logfh, \
            ThreadPoolExecutor(max_workers=1) as proposal_pool, \
            ThreadPoolExecutor(max_workers=args.jobs + args.retry_jobs) as pool, \
            contextlib.ExitStack() as cleanup:
        cleanup.callback(producer_stop.set)
        running = {}  # future -> (canon, parent, op, pred, first result if this is a retry else None)
        n_retry = 0
        t0 = time.monotonic()
        while True:
            stop = time.monotonic() > deadline or (args.max_evals and evals >= args.max_evals)
            while (not stop and retry_q and n_retry < args.retry_jobs
                   and (not args.max_evals or evals + len(running) < args.max_evals)):
                item = retry_q.popleft()
                running[pool.submit(check, item[0], retry_opts)] = item
                n_retry += 1
            while (not stop and time.monotonic() <= deadline and len(running) - n_retry < args.jobs
                   and (not args.max_evals or evals + len(running) + len(retry_q) < args.max_evals)):
                prop = next_job()
                if prop is None:
                    break
                canon, parent, op, pred = prop
                running[pool.submit(check, canon, args)] = (canon, parent, op, pred, None)
            if not running:
                if not stop and scored_future is not None and not scored_future.done():
                    wait([scored_future], timeout=0.1)
                    continue
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
                                    {k: rec.get(k) for k in ("status", "seconds", "total_seconds", "peak_rss_mb") if k in rec}))
                    print(f"  {rec['status']} at {args.mem_mb:.0f} MB / {args.timeout_long:.0f} s, queued for a "
                          f"{args.retry_mem_mb:.0f} MB re-check ({len(retry_q)} waiting): {canon}", flush=True)
                    continue
                record = rec.pop("record", None)
                row = {"canon": canon, "shape": canon, "grid": grid, "cells": (len(canon.split()) - 1) // 2,
                       "parent": parent, "op": op, "generator": generator_of(op, pred),
                       "pred": None if pred is None else round(pred, 4), "run_id": run_id,
                       "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
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
                if args.guard_checks and args.guard_mode != "off":
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
                    now = time.monotonic()
                    rate = evals / (now - t0)
                    left = deadline - now
                    if args.max_evals:
                        left = min(left, (args.max_evals - evals) / max(rate, 1e-9))
                    eta = time.strftime("%H:%M", time.localtime(time.time() + left))
                    print(f"  {evals} evals, {rate:.1f}/s, archive {len(archive)}, non-tilers by hc: "
                          + ", ".join(f"{k}:{v}" for k, v in sorted(hc_hist.items()))
                          + f" | {fmt_dur(now - t0)} elapsed, ends ~{eta} (in {fmt_dur(left)})", flush=True)
                    if args.sweep_min_hc and (sweep_q or sweep_heap):
                        per = sweep_stats["edits"] / max(1, sweep_stats["parents"])
                        todo = len(sweep_q) + per * len(sweep_heap)
                        n_sw = gen_stats.get("search-sweep", (0, 0, 0))[0]
                        sw_rate = n_sw / (now - t0)
                        sw_eta = f", ~{fmt_dur(todo / sw_rate)} at the current pace" if sw_rate > 0 else ""
                        print(f"     sweep: {len(sweep_heap)} parents waiting + {len(sweep_q)} edits queued, "
                              f"~{todo:,.0f} checks to go{sw_eta} (new hc>=3 finds add more)", flush=True)
                    if sc is not None:
                        print(f"     scored batches: {generation_seconds:.1f}s generation/inference, "
                              f"{len(queue)} queued, refill {'running' if scored_future is not None else 'idle'}", flush=True)
                        for gen in sorted(gen_stats):
                            n_all, n_good, n_tile = gen_stats[gen]
                            if n_all:
                                print(f"     {gen:19s}: {n_all} checked, hc>=2 {n_good} ({100*n_good/n_all:.1f}%), "
                                      f"tilers {100*n_tile/n_all:.0f}%" + ("  [switched off]" if gen in disabled else ""),
                                      flush=True)
        producer_stop.set()
        if scored_future is not None:
            scored_future.cancel()
        for canon, parent, op, pred, first in retry_q:  # not re-checked before the stop: keep them findable
            row = {"canon": canon, "shape": canon, "grid": grid, "cells": (len(canon.split()) - 1) // 2,
                   "parent": parent, "op": op, "generator": generator_of(op, pred), "hc": None, "hh": None,
                   "pred": None if pred is None else round(pred, 4), "run_id": run_id,
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            row.update(first)
            logfh.write(json.dumps(row) + "\n")
        if retry_q:
            print(f"{len(retry_q)} shapes still waiting for a re-check were logged as {first['status']}; "
                  f"rerun with --retry-archived to check them", flush=True)
    run_event("finished", evaluations=evals, best_hc=best_seen[0],
              seconds=round(time.monotonic() - t0, 3), generators=gen_stats)
    print(f"done: {evals} evaluations; best hc={best_seen[0]}")
    top = sorted((r for r in archive.values() if r.get("status") == "nontiler"), key=fitness, reverse=True)[:10]
    for r in top:
        print(f"  hc={r['hc']} hh={r.get('hh')} cells={r.get('cells')} {r['canon']}")


if __name__ == "__main__":
    main()
