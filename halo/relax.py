#!/usr/bin/env python3
"""HALO Track D option: continuous-relaxation ("Gaussian splat") candidate generator.

Starts from a real shape, makes its occupancy soft, follows the learned scorer's gradient
uphill (higher predicted hc), snaps back to cells, repairs the result (largest connected
piece, holes filled, Epoch limits) and returns the distinct shapes it passes through.
It is a generator only: search.py sends every output through the checker like any other
candidate, so a misleading scorer costs checks, never correctness.

Modes
  cell   every cell near the shape has its own occupancy logit
  splat  the shape is a set of Gaussian blobs (one per starting cell) whose centres, widths
         and strengths move; occupancy is the blobs drawn onto the grid. Moves whole lobes
         together instead of single cells.

The scorer averages over the symmetric images of a shape, so the objective does too: each
step builds the soft image in every orientation where the current shape fits the window,
anchored the way scorer.images() anchors the discrete shape. Each round snaps at most
--max-flips cells (the most confident changes), so a round is a coordinated multi-cell move
rather than a jump to whatever the scorer likes most.

Gradient backends: MLX (GPU on Apple silicon) when importable, else NumPy with a hand-written
backward pass. `--selftest` checks both against finite differences.

Standalone use (what relaxation produces from each seed; no checker):
  python3 halo/relax.py results/models/scorer_v2_hex.npz --seeds results/seeds_hex11_hc3plus.jsonl --mode splat
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape as shp  # noqa: E402
from aner_scorer import S as ACT_S, load_weights  # noqa: E402

SQ3_2 = math.sqrt(3.0) / 2.0
MODES = ("cell", "splat")


def centre(grid, x, y):
    """Cartesian centre of a cell (hex: Kaplan's axial coordinates, y axis at 60 degrees)."""
    return (x + 0.5 * y, SQ3_2 * y) if grid == "H" else (float(x), float(y))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class HcGrad:
    """Objective per scorer input, hc_hat - tile_weight * softplus(tile_logit), and its gradient.

    The tiler term matters: the scorer's hc head is trained on non-tilers only, so its maximum
    lies among tilers, and pure hc ascent ends there (smoke test: 100% of relaxed shapes were
    tilers). softplus(t) = -log(1 - p_tile) barely touches near-tilers and grows for confident
    tilers."""

    def __init__(self, weights, backend="auto", tile_weight=1.0):
        self.tile_weight = float(tile_weight)
        self.W, self.blocks, self.window = load_weights(weights)
        self.inputs = self.W["inp.weight"].shape[1]
        self.backend = "numpy"
        self._vg = None
        if backend in ("auto", "mlx"):
            try:
                import mlx.core as mx
                Wm = {k: mx.array(v) for k, v in self.W.items()}
                blocks = self.blocks
                tw = self.tile_weight

                def f(x):
                    a = lambda z: z * mx.sigmoid(ACT_S * z)  # noqa: E731
                    h = a(x @ Wm["inp.weight"].T + Wm["inp.bias"])
                    for i in range(blocks):
                        t = a(h @ Wm[f"blocks.{i}.l1.weight"].T + Wm[f"blocks.{i}.l1.bias"])
                        h = h + t @ Wm[f"blocks.{i}.l2.weight"].T + Wm[f"blocks.{i}.l2.bias"]
                    hc = h @ Wm["head.weight"][1] + Wm["head.bias"][1]
                    t = h @ Wm["head.weight"][0] + Wm["head.bias"][0]
                    obj = hc - tw * mx.logaddexp(t, mx.zeros_like(t))
                    return obj.sum(), obj

                # auto: MLX only with a Metal GPU. MLX's CPU backend is ~7x slower than NumPy here.
                if backend == "auto" and not mx.metal.is_available():
                    raise RuntimeError("no Metal GPU")
                self._mx = mx
                self._vg = mx.compile(mx.value_and_grad(f))
                self.backend = "mlx-gpu" if mx.metal.is_available() else "mlx-cpu"
            except Exception:
                if backend == "mlx":
                    raise

    def __call__(self, X):
        X = np.ascontiguousarray(X, dtype=np.float32)
        if self._vg is not None:
            (_, hc), g = self._vg(self._mx.array(X))
            return np.array(hc, dtype=np.float64), np.array(g, dtype=np.float64)
        return self.numpy(X)

    def numpy(self, X):
        W, s = self.W, ACT_S
        z0 = X @ W["inp.weight"].T + W["inp.bias"]
        s0 = sigmoid(s * z0)
        h = z0 * s0
        cache = []
        for i in range(self.blocks):
            u = h @ W[f"blocks.{i}.l1.weight"].T + W[f"blocks.{i}.l1.bias"]
            su = sigmoid(s * u)
            h = h + (u * su) @ W[f"blocks.{i}.l2.weight"].T + W[f"blocks.{i}.l2.bias"]
            cache.append((u, su))
        hc = h @ W["head.weight"][1] + W["head.bias"][1]
        t = h @ W["head.weight"][0] + W["head.bias"][0]
        obj = hc - self.tile_weight * np.logaddexp(t, 0.0)
        g = (W["head.weight"][1][None, :] - self.tile_weight * sigmoid(t)[:, None] * W["head.weight"][0][None, :]
             ).astype(np.float32)
        for i in reversed(range(self.blocks)):
            u, su = cache[i]
            gu = (g @ W[f"blocks.{i}.l2.weight"]) * (su + s * u * su * (1.0 - su))
            g = g + gu @ W[f"blocks.{i}.l1.weight"]
        g = g * (s0 + s * z0 * s0 * (1.0 - s0))
        return obj.astype(np.float64), (g @ W["inp.weight"]).astype(np.float64)


def grow(grid, cells, r):
    """Cells within graph distance r of the shape (the shape included), sorted."""
    nb = shp.NEIGHBOURS[grid]
    out = set(cells)
    front = set(cells)
    for _ in range(r):
        front = {(x + dx, y + dy) for x, y in front for dx, dy in nb} - out
        out |= front
    return sorted(out)


def repair(grid, cells):
    """Largest connected piece of `cells` with its holes filled; None if empty."""
    s = set(cells)
    if not s:
        return None
    nb = shp.NEIGHBOURS[grid]
    best, seen = [], set()
    for c in sorted(s):
        if c in seen:
            continue
        comp, stack = [c], [c]
        seen.add(c)
        while stack:
            x, y = stack.pop()
            for dx, dy in nb:
                d = (x + dx, y + dy)
                if d in s and d not in seen:
                    seen.add(d)
                    comp.append(d)
                    stack.append(d)
        if len(comp) > len(best):
            best = comp
    s = set(best)
    xs = [x for x, _ in s]
    ys = [y for _, y in s]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    outside, stack = {(x0, y0)}, [(x0, y0)]
    while stack:
        x, y = stack.pop()
        for dx, dy in nb:
            d = (x + dx, y + dy)
            if x0 <= d[0] <= x1 and y0 <= d[1] <= y1 and d not in s and d not in outside:
                outside.add(d)
                stack.append(d)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if (x, y) not in s and (x, y) not in outside:
                s.add((x, y))
    return sorted(s)


class Adam:
    def __init__(self, shape, lr, b1=0.9, b2=0.999, eps=1e-8):
        self.m = np.zeros(shape)
        self.v = np.zeros(shape)
        self.t = 0
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps

    def step(self, g):
        """Ascent step for gradient g; returns the parameter change."""
        self.t += 1
        self.m = self.b1 * self.m + (1 - self.b1) * g
        self.v = self.b2 * self.v + (1 - self.b2) * g * g
        mh = self.m / (1 - self.b1 ** self.t)
        vh = self.v / (1 - self.b2 ** self.t)
        return self.lr * mh / (np.sqrt(vh) + self.eps)


class Relaxer:
    def __init__(self, weights, mode="splat", backend="auto", rounds=6, steps=30, max_flips=4,
                 ring=2, bin_weight=0.02, size_weight=0.5, min_cells=4, max_cells=40, shrink=0, grow=4,
                 lr_cell=0.15, lr_mu=0.05, lr_sigma=0.02, lr_amp=0.1, sigma0=0.55, amp0=0.9, tile_weight=1.0):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.g = HcGrad(weights, backend, tile_weight)
        self.window = self.g.window
        self.mode = mode
        self.rounds, self.steps, self.max_flips, self.ring = rounds, steps, max_flips, ring
        self.bin_weight, self.size_weight = bin_weight, size_weight
        self.min_cells, self.max_cells = min_cells, max_cells
        self.shrink, self.grow = shrink, grow
        self.lr_cell, self.lr_mu, self.lr_sigma, self.lr_amp = lr_cell, lr_mu, lr_sigma, lr_amp
        self.sigma0, self.amp0 = sigma0, amp0

    @property
    def backend(self):
        return self.g.backend

    # --- scorer images -------------------------------------------------------------------
    def maps(self, grid, shape_cells, C):
        """For each orientation in which the discrete shape fits the window: (image positions,
        indices into C) of the canvas cells that land inside the window."""
        out = []
        Wn = self.window
        for a, b, d, e in shp.SYMMETRIES[grid]:
            ts = [(a * x + b * y, d * x + e * y) for x, y in shape_cells]
            mx_ = min(x for x, _ in ts)
            my_ = min(y for _, y in ts)
            if max(x for x, _ in ts) - mx_ >= Wn or max(y for _, y in ts) - my_ >= Wn:
                continue
            pos, src = [], []
            for j, (x, y) in enumerate(C):
                X_ = a * x + b * y - mx_
                Y_ = d * x + e * y - my_
                if 0 <= X_ < Wn and 0 <= Y_ < Wn:
                    pos.append(Y_ * Wn + X_)
                    src.append(j)
            out.append((np.array(pos, np.int64), np.array(src, np.int64)))
        return out

    def score_shape(self, grid, cells):
        """Relaxation objective of a discrete shape (mean over its images)."""
        C = sorted(cells)
        m = self.maps(grid, C, C)
        if not m:
            return None
        hc, _ = self.objective(np.ones(len(C)), m)
        return hc

    def objective(self, p, maps):
        """Mean objective over the images of soft occupancy p (over canvas C), and d/dp."""
        return self.objectives([p], [maps])[0]

    def objectives(self, ps, maps_list):
        """objective() for several soft shapes with one scorer call."""
        X = np.zeros((sum(len(m) for m in maps_list), self.g.inputs), np.float32)
        k = 0
        for p, maps in zip(ps, maps_list):
            for pos, src in maps:
                X[k, pos] = p[src]
                k += 1
        val, gX = self.g(X)
        out, k = [], 0
        for p, maps in zip(ps, maps_list):
            gp = np.zeros(len(p))
            for i, (pos, src) in enumerate(maps):
                gp[src] += gX[k + i, pos]
            n = len(maps)
            out.append((float(val[k:k + n].mean()), gp / n))
            k += n
        return out

    def penalties(self, p, lo, hi):
        """Gradient of the regularisers (to add to the objective gradient): push occupancies
        towards 0/1 and keep the soft cell count inside [lo, hi]."""
        g = -self.bin_weight * (1.0 - 2.0 * p)
        n = p.sum()
        if n > hi:
            g -= 2.0 * self.size_weight * (n - hi)
        elif n < lo:
            g += 2.0 * self.size_weight * (lo - n)
        return g

    # --- the two parameterisations -------------------------------------------------------
    @staticmethod
    def splat_field(R, mu, ls, al):
        """Occupancy of canvas cells (centres R) from blobs; returns p and pieces for backward."""
        D = R[None, :, :] - mu[:, None, :]
        d2 = (D * D).sum(-1)
        sig2 = np.exp(2.0 * ls)[:, None]
        e = np.exp(-d2 / (2.0 * sig2))
        a = sigmoid(al)[:, None]
        q = np.minimum(a * e, 1.0 - 1e-9)
        L = np.log1p(-q).sum(0)
        p = 1.0 - np.exp(L)
        return p, (D, d2, sig2, e, a, q, L)

    @staticmethod
    def splat_backward(gp, parts):
        D, d2, sig2, e, a, q, L = parts
        gq = gp[None, :] * np.exp(L)[None, :] / (1.0 - q)
        w = gq * q / sig2
        gmu = (w[:, :, None] * D).sum(1)
        gls = (w * d2).sum(1)
        gal = (gq * e * a * (1.0 - a)).sum(1)
        return gmu, gls, gal

    # --- main loop: several shapes relax in lockstep, one batched scorer call per step ------
    def relax(self, line, rng, exclude=()):
        """Relax one shape. Returns [(canonical line, info)], distinct, new, valid, in order found."""
        return self.relax_many([line], rng, exclude)[0]

    def relax_many(self, lines, rng, exclude=()):
        """Relax several shapes together. One scorer call per step covers all their images, which
        costs about the same as one shape's (small batches are latency-bound). Returns one list
        per input line of [(canonical line, info)]."""
        jobs = [self._start(line, rng) for line in lines]
        alive = list(jobs)
        for rnd in range(self.rounds):
            alive = [j for j in alive if self._setup_round(j, rng)]
            if not alive:
                break
            Js = [None] * len(alive)
            for _ in range(self.steps):
                ps = [self._field(j) for j in alive]
                res = self.objectives(ps, [j["maps"] for j in alive])
                for i, (j, p, (J, gp)) in enumerate(zip(alive, ps, res)):
                    Js[i] = J
                    self._step(j, p, gp)
            for j, J in zip(alive, Js):
                self._finish_round(j, rnd, J, exclude)
        return [j["out"] for j in jobs]

    def _start(self, line, rng):
        grid, cells = shp.parse(line)
        j = {"grid": grid, "cur": set(cells), "start": set(cells), "seen": {shp.canonical(grid, cells)}, "out": [],
             # Size band around the starting shape. Unconstrained, relaxation shrinks shapes into
             # sizes the scorer never saw (4-9 cells), where it predicts hc ~3 with confidence.
             "lo": max(self.min_cells, len(cells) - self.shrink),
             "hi": min(self.max_cells, len(cells) + self.grow)}
        if self.mode == "cell":
            j["z"] = {}
        else:
            K = len(cells)
            j["mu"] = np.array([centre(grid, x, y) for x, y in cells]) + rng.normal(0.0, 0.05, (K, 2))
            j["ls"] = np.full(K, math.log(self.sigma0))
            j["al"] = np.full(K, math.log(self.amp0 / (1.0 - self.amp0)))
            j["opt"] = (Adam((K, 2), self.lr_mu), Adam(K, self.lr_sigma), Adam(K, self.lr_amp))
        return j

    def _setup_round(self, j, rng):
        """Canvas and image maps for this round; False if the shape fits no orientation."""
        grid, cur = j["grid"], j["cur"]
        C = grow(grid, cur, self.ring)
        maps = self.maps(grid, sorted(cur), C)
        if not maps:
            return False
        j["C"], j["maps"] = C, maps
        if self.mode == "cell":
            z = j["z"]
            for c in C:
                if c not in z:
                    z[c] = (2.0 if c in cur else -2.0) + rng.normal(0.0, 0.3)
            j["zc"] = np.array([z[c] for c in C])
            j["opt_c"] = Adam(len(C), self.lr_cell)
        else:
            j["R"] = np.array([centre(grid, x, y) for x, y in C])
        return True

    def _field(self, j):
        if self.mode == "cell":
            j["parts"] = None
            return sigmoid(j["zc"])
        p, j["parts"] = self.splat_field(j["R"], j["mu"], j["ls"], j["al"])
        return p

    def _step(self, j, p, gp):
        gp = gp + self.penalties(p, j["lo"], j["hi"])
        if self.mode == "cell":
            j["zc"] += j["opt_c"].step(gp * p * (1.0 - p))
        else:
            gmu, gls, gal = self.splat_backward(gp, j["parts"])
            opt = j["opt"]
            j["mu"] += opt[0].step(gmu)
            j["ls"] = np.clip(j["ls"] + opt[1].step(gls), math.log(0.3), math.log(1.5))
            j["al"] = np.clip(j["al"] + opt[2].step(gal), -6.0, 6.0)

    def _finish_round(self, j, rnd, J, exclude):
        """Snap (at most max_flips changes), repair, validate; record the shape if it is new."""
        grid, cur, C = j["grid"], j["cur"], j["C"]
        if self.mode == "cell":
            for c, v in zip(C, j["zc"]):
                j["z"][c] = v
        p = self._field(j)
        inside = np.array([c in cur for c in C])
        want = p > 0.5
        changed = np.where(want != inside)[0]
        if len(changed) == 0:
            return
        flips = changed[np.argsort(-np.abs(p[changed] - 0.5))][: self.max_flips]
        new = set(cur)
        for i in flips:
            if want[i]:
                new.add(C[i])
            else:
                new.discard(C[i])
        rep = repair(grid, new)
        # reject snaps outside the size band, or where repair threw away a detached piece
        if rep is None or not (j["lo"] <= len(rep) <= j["hi"]) or len(rep) < len(new) - 1:
            return
        ok, problems, _ = shp.check(shp.fmt(grid, rep))
        if not ok or any("stricter" in q for q in problems):
            return
        if self.mode == "cell":  # keep the logits consistent with what repair kept or filled
            for c in set(rep) ^ new:
                j["z"][c] = 1.0 if c in rep else -1.0
        j["cur"] = set(rep)
        canon = shp.canonical(grid, rep)
        if canon in j["seen"] or canon in exclude:
            return
        j["seen"].add(canon)
        j["out"].append((canon, {"round": rnd + 1, "flips": int(len(flips)), "soft_hc": round(J, 4),
                                 "dist": len(j["cur"] ^ j["start"]), "cells": len(j["cur"])}))


def selftest(weights):
    rng = np.random.default_rng(0)
    g = HcGrad(weights, "numpy", tile_weight=1.0)
    X = rng.random((3, g.inputs)).astype(np.float32)
    hc, gX = g(X)
    eps, worst = 1e-2, 0.0
    for _ in range(12):
        k, i = rng.integers(3), rng.integers(g.inputs)
        Xp, Xm = X.copy(), X.copy()
        Xp[k, i] += eps
        Xm[k, i] -= eps
        fd = (g(Xp)[0][k] - g(Xm)[0][k]) / (2 * eps)
        worst = max(worst, abs(fd - gX[k, i]) / (abs(fd) + 1e-3))
    print(f"numpy gradient vs finite differences: worst relative error {worst:.3g}")
    try:
        gm = HcGrad(weights, "mlx", tile_weight=1.0)
        hm, gmX = gm(X)
        print(f"mlx vs numpy: hc max diff {np.abs(hm - hc).max():.2g}, grad max diff {np.abs(gmX - gX).max():.2g} "
              f"(grad scale {np.abs(gX).max():.2g})")
    except Exception as exc:
        print(f"mlx unavailable: {exc}")
    # splat backward vs finite differences on a toy objective sum(w * p)
    R = rng.normal(0, 2, (20, 2))
    mu, ls, al = rng.normal(0, 1.5, (5, 2)), np.log(rng.uniform(0.4, 1.0, 5)), rng.normal(1, 1, 5)
    wv = rng.normal(0, 1, 20)
    f = lambda m, s, a: float((wv * Relaxer.splat_field(R, m, s, a)[0]).sum())  # noqa: E731
    p, parts = Relaxer.splat_field(R, mu, ls, al)
    gmu, gls, gal = Relaxer.splat_backward(wv, parts)
    e = 1e-6
    errs = []
    for k in range(5):
        for j in range(2):
            d = np.zeros_like(mu)
            d[k, j] = e
            errs.append(abs((f(mu + d, ls, al) - f(mu - d, ls, al)) / (2 * e) - gmu[k, j]))
        d = np.zeros(5)
        d[k] = e
        errs.append(abs((f(mu, ls + d, al) - f(mu, ls - d, al)) / (2 * e) - gls[k]))
        errs.append(abs((f(mu, ls, al + d) - f(mu, ls, al - d)) / (2 * e) - gal[k]))
    print(f"splat gradient vs finite differences: max abs error {max(errs):.2g}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weights")
    ap.add_argument("--seeds", default="", help="runner/search JSONL or text file of shape lines")
    ap.add_argument("--seed-min-hc", type=int, default=3)
    ap.add_argument("--mode", default="splat", choices=MODES)
    ap.add_argument("--backend", default="auto", choices=["auto", "mlx", "numpy"])
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--max-flips", type=int, default=4)
    ap.add_argument("--max-cells", type=int, default=30)
    ap.add_argument("--shrink", type=int, default=0, help="cells a relaxed shape may lose vs its start")
    ap.add_argument("--grow", type=int, default=4, help="cells a relaxed shape may gain vs its start")
    ap.add_argument("--tile-weight", type=float, default=1.0,
                    help="objective = hc_hat - w * softplus(tile logit); 0 = pure hc (drifts into tilers)")
    ap.add_argument("--check", action="store_true",
                    help="also run every relaxed shape through the checker (runner ladder) and tally results")
    ap.add_argument("--limit", type=int, default=20, help="seeds to relax")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest(args.weights)
        return
    rx = Relaxer(args.weights, args.mode, args.backend, args.rounds, args.steps, args.max_flips,
                 max_cells=args.max_cells, shrink=args.shrink, grow=args.grow, tile_weight=args.tile_weight)
    rng = np.random.default_rng(args.seed)
    seeds = []
    with open(args.seeds) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            if args.seeds.endswith(".jsonl"):
                r = json.loads(ln)
                if r.get("status") == "nontiler" and (r.get("hc") or 0) >= args.seed_min_hc:
                    seeds.append(r["shape"])
            else:
                seeds.append(ln)
    print(f"mode {args.mode}, backend {rx.backend}, {len(seeds)} seeds (relaxing {min(len(seeds), args.limit)})")
    if args.check:
        import tempfile
        import runner
        copts = argparse.Namespace(sat=runner.DEFAULT_SAT, maxlevel=7, timeout=10.0, timeout_long=60.0, mem_mb=2500.0,
                                   periodic_budget=30.0, periodic_quick=3.0, periodic_max_t=24, escalate_maxlevel=9)
        workdir = tempfile.mkdtemp(prefix="halo_relax_")
    n_out, ups, t0, tally, seen = 0, [], time.time(), {}, set()
    for line in seeds[: args.limit]:
        grid, cells = shp.parse(line)
        base = rx.score_shape(grid, cells)
        res = rx.relax(line, rng, exclude=seen)
        n_out += len(res)
        for canon, info in res:
            seen.add(canon)
            g2, c2 = shp.parse(canon)
            after = rx.score_shape(g2, c2)
            ups.append(after - base)
            verdict = ""
            if args.check:
                r = runner.classify(canon, copts, workdir)
                verdict = r["status"] if r["status"] != "nontiler" else f"Hc={r['hc']}"
                tally[verdict] = tally.get(verdict, 0) + 1
            print(f"  {len(cells):2d} cells objective {base:.3f} -> {after:.3f} (soft {info['soft_hc']:.3f}) "
                  f"round {info['round']} flips {info['flips']} dist {info['dist']} cells {info['cells']} {verdict}")
    dt = time.time() - t0
    if ups:
        print(f"{n_out} new shapes from {min(len(seeds), args.limit)} seeds in {dt:.1f}s; objective rose for "
              f"{100*np.mean(np.array(ups) > 0):.0f}% (mean change {np.mean(ups):+.3f})")
        if tally:
            print("checker: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    else:
        print(f"no new shapes ({dt:.1f}s)")


if __name__ == "__main__":
    main()
