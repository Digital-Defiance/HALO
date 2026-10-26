#!/usr/bin/env python3
"""HALO learned scorer (Track D), step 1: can a network predict Heesch numbers?

Trains a deep residual MLP on runner JSONL results and reports how well it ranks shapes,
including an extrapolation test: shapes with the top Heesch number in the data are held
out of training entirely, and we measure where the model ranks them.

The network uses only operations ANER supports (linear maps, per-channel bias via
const+add, x*sigmoid(1.702x) activation, residual adds), so trained weights can be loaded
into an ANER graph unchanged (see halo/aner_scorer.py).

Usage:
  python3 halo/scorer.py results/hex11.jsonl [--blocks 8] [--width 512] [--epochs 8]
                         [--holdout-top] [--save results/scorer_hex11.npz]
  python3 halo/scorer.py results/hex11.jsonl,results/hex11_pass2.jsonl,results/hex11_ml7.jsonl,results/search_hex_01.jsonl \
                         --window 22 --eval-source 3 --save results/models/scorer_v2.npz
Requires: numpy, torch (CPU is fine).
"""
import argparse
import json
import math
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape as shp  # noqa: E402

# Proven tilers only. "inconclusive" is NOT a tiler (heesch-sat's inconclusive allows holed
# coronas, SPEC §6), so inconclusive / memout / timeout rows are left out of training.
TILER = ("isohedral", "periodic", "anisohedral", "aperiodic")
WINDOW = 16  # default window: 16 x 16 = 256 inputs (a multiple of 64, as ANER requires)


def input_size(window):
    """Input vector length for a window: window^2 rounded up to a multiple of 64 (ANER)."""
    return ((window * window + 63) // 64) * 64


def load(paths):
    """Rows (shape, is_tiler, hc, source_index) from one or more runner/search JSONL files
    (comma-separated). Later files override earlier ones for the same shape, so re-check
    passes replace the first pass's unsettled results."""
    merged = {}
    for src, path in enumerate(p for p in paths.split(",") if p):
        with open(path) as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                st = r.get("status")
                g, cells = shp.parse(r["shape"])
                key = shp.canonical(g, cells) if g in shp.SYMMETRIES else r["shape"]
                if st == "nontiler" and r.get("hc") is not None:
                    merged[key] = (r["shape"], 0, r["hc"], src)
                elif st in TILER:
                    merged[key] = (r["shape"], 1, -1, src)
                # inconclusive / memout / timeout / error: unsettled, never overrides a settled label
    return list(merged.values())


def images(line, window=WINDOW, size=None):
    """All symmetric images of a shape that fit the window, as occupancy vectors of length
    `size` (default: input_size(window); positions past window^2 are zero padding)."""
    size = size or input_size(window)
    grid, cells = shp.parse(line)
    out = []
    for a, b, d, e in shp.SYMMETRIES[grid]:
        pts = [(a * x + b * y, d * x + e * y) for x, y in cells]
        mx = min(x for x, _ in pts)
        my = min(y for _, y in pts)
        v = np.zeros(size, np.float32)
        ok = True
        for x, y in pts:
            x, y = x - mx, y - my
            if x >= window or y >= window:
                ok = False
                break
            v[y * window + x] = 1.0
        if ok:
            out.append(v)
    return out


def featurize(rows, window=WINDOW):
    """Returns X (list of image stacks), tile, hc, source, kept-row indices. Shapes that do not
    fit the window in any orientation are skipped."""
    X, tile, hc, src = [], [], [], []
    for line, t, h, s in rows:
        ims = images(line, window)
        if not ims:
            continue
        X.append(np.stack(ims).astype(np.uint8))  # occupancy is 0/1; float32 only per batch
        tile.append(t)
        hc.append(h)
        src.append(s)
    return X, np.array(tile, np.float32), np.array(hc, np.float32), np.array(src, np.int32)


def build_model(width, blocks, inp=WINDOW * WINDOW):
    import torch
    import torch.nn as nn

    class Act(nn.Module):
        def forward(self, x):
            return x * torch.sigmoid(1.702 * x)

    class Block(nn.Module):
        def __init__(self, w, scale):
            super().__init__()
            self.l1 = nn.Linear(w, w)
            self.l2 = nn.Linear(w, w)
            self.act = Act()
            with torch.no_grad():
                self.l2.weight.mul_(scale)
                self.l2.bias.zero_()

        def forward(self, x):
            return x + self.l2(self.act(self.l1(x)))

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Linear(inp, width)
            self.act = Act()
            self.blocks = nn.ModuleList([Block(width, 1.0 / math.sqrt(2 * blocks)) for _ in range(blocks)])
            self.head = nn.Linear(width, 2)  # [tile logit, hc estimate]

        def forward(self, x):
            h = self.act(self.inp(x))
            for b in self.blocks:
                h = b(h)
            return self.head(h)

    return Net()


def auc(scores, labels):
    """ROC AUC via ranks (labels in {0,1})."""
    order = np.argsort(scores)
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    pos = labels == 1
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jsonl", help="runner/search JSONL file(s), comma-separated; later files override earlier")
    ap.add_argument("--window", type=int, default=WINDOW, help="occupancy window side (inputs padded to x64)")
    ap.add_argument("--tiler-hc", type=float, default=-1.0,
                    help="hc regression target for tilers (pushes tilers down the ranking); nan = ignore tilers")
    ap.add_argument("--eval-source", type=int, default=-1,
                    help="index of the input file whose held-out shapes get a search-style report")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--blocks", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--holdout-top", action="store_true",
                    help="exclude all shapes with the highest hc from training (extrapolation test)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save", default="")
    args = ap.parse_args()

    import torch
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    t0 = time.time()
    rows = load(args.jsonl)
    X, tile, hc, src = featurize(rows, args.window)
    inp = input_size(args.window)
    top = int(hc.max())
    print(f"{len(rows)} shapes loaded, {len(X)} fit a {args.window}x{args.window} window ({inp} inputs); "
          f"{int(tile.sum())} tilers, hc max {top}, featurized in {time.time()-t0:.0f}s")
    rows = None

    idx = np.arange(len(X))
    np.random.shuffle(idx)
    n_test = len(X) // 5
    test, train = idx[:n_test], idx[n_test:]
    if args.holdout_top:
        top_idx = np.where(hc == top)[0]
        train = np.array([i for i in train if hc[i] != top])
        test = np.array(sorted(set(test.tolist()) | set(top_idx.tolist())))
        print(f"holding out all {len(top_idx)} shapes with hc={top} from training")

    # sample weights: emphasize rare high-hc non-tilers
    counts = {h: max(1, int(((hc == h) & (tile == 0))[train].sum())) for h in range(top + 1)}
    def weight(i):
        return 1.0 if tile[i] else (counts[0] / counts[int(hc[i])]) ** 0.5

    model = build_model(args.width, args.blocks, inp)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * math.ceil(len(train) / args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps)
    bce = torch.nn.BCEWithLogitsLoss(reduction="none")
    w_all = np.array([weight(i) for i in range(len(X))], np.float32)
    use_tiler_hc = not math.isnan(args.tiler_hc)

    for ep in range(args.epochs):
        model.train()
        np.random.shuffle(train)
        tot, nb = 0.0, 0
        for s in range(0, len(train), args.batch):
            b = train[s:s + args.batch]
            xb = torch.from_numpy(np.stack([X[i][random.randrange(len(X[i]))] for i in b]).astype(np.float32))  # random symmetry
            tb = torch.from_numpy(tile[b])
            hb = torch.from_numpy(hc[b])
            wb = torch.from_numpy(w_all[b])
            out = model(xb)
            l_tile = bce(out[:, 0], tb)
            nt = tb == 0
            l_hc = torch.zeros_like(l_tile)
            l_hc[nt] = (out[nt, 1] - hb[nt]) ** 2
            if use_tiler_hc:
                l_hc[~nt] = 0.5 * (out[~nt, 1] - args.tiler_hc) ** 2
            loss = ((l_tile + l_hc) * wb).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item()
            nb += 1
        print(f"epoch {ep+1}/{args.epochs} loss {tot/nb:.4f}  ({time.time()-t0:.0f}s)", flush=True)

    # evaluation: average over all symmetric images
    model.eval()
    with torch.no_grad():
        pt, ph = [], []
        for i in test:
            o = model(torch.from_numpy(X[i].astype(np.float32))).mean(0)
            pt.append(o[0].item())
            ph.append(o[1].item())
    pt, ph = np.array(pt), np.array(ph)
    tt, ht = tile[test], hc[test]
    print("\n== held-out evaluation ==")
    print(f"tiler vs non-tiler AUC: {auc(pt, tt):.4f}")
    nt = tt == 0
    for k in range(1, top + 1):
        print(f"non-tilers, hc>={k} vs rest AUC: {auc(ph[nt], (ht[nt] >= k).astype(int)):.4f}"
              f"  (positives {(ht[nt] >= k).sum()})")
    # enrichment over ALL held-out shapes (tilers included), for several ways to combine the heads
    p_tile = 1 / (1 + np.exp(-pt))
    variants = {"hc only": ph, "hc*(1-p_tile)": ph * (1 - p_tile), "hc - 2*p_tile": ph - 2 * p_tile}
    tops = np.where((ht == top) & nt)[0]
    for name, score in variants.items():
        order = np.argsort(-score)
        rank = np.empty(len(order), int)
        rank[order] = np.arange(len(order))
        print(f"-- score = {name}")
        for frac in (0.01, 0.05):
            k = max(1, int(len(order) * frac))
            topk = order[:k]
            parts = []
            for lvl in range(max(2, top - 1), top + 1):
                got = int(((ht[topk] >= lvl) & (tt[topk] == 0)).sum())
                allp = int(((ht >= lvl) & (tt == 0)).sum())
                parts.append(f"{got}/{allp} of hc>={lvl}")
            print(f"   top {frac*100:.0f}% ({k} shapes) captures " + ", ".join(parts))
        if len(tops):
            pct = 100.0 * rank[tops] / len(order)
            print(f"   hc={top} shapes ranked at percentiles (0 = best): median {np.median(pct):.2f}, "
                  f"best {pct.min():.2f}, worst {pct.max():.2f}")

    # search-style report: held-out shapes from one source (e.g. a search log), ranked by score
    if args.eval_source >= 0:
        sel = src[test] == args.eval_source
        if sel.any():
            sc_ = (ph * (1 - p_tile))[sel]
            ts, hs = tt[sel], ht[sel]
            order = np.argsort(-sc_)
            base_t, base_g = ts.mean(), ((hs >= 2) & (ts == 0)).mean()
            print(f"-- search-style report on source {args.eval_source}: {sel.sum()} held-out shapes; "
                  f"base rates: tilers {100*base_t:.1f}%, hc>=2 {100*base_g:.2f}%")
            for frac in (0.02, 0.05, 0.2):
                k = max(1, int(len(order) * frac))
                topk = order[:k]
                print(f"   top {frac*100:.0f}% ({k}): tilers {100*ts[topk].mean():.1f}%, "
                      f"hc>=2 {100*((hs[topk] >= 2) & (ts[topk] == 0)).mean():.2f}%, "
                      f"hc>=3 {int(((hs[topk] >= 3) & (ts[topk] == 0)).sum())}/{int(((hs >= 3) & (ts == 0)).sum())}")

    if args.save:
        sd = {k: v.detach().numpy() for k, v in model.state_dict().items()}
        np.savez(args.save, width=args.width, blocks=args.blocks, window=args.window, **sd)
        print(f"saved weights to {args.save}")


if __name__ == "__main__":
    main()
