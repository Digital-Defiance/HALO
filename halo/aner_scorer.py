#!/usr/bin/env python3
"""HALO scorer inference on the Apple Neural Engine via ANER, with a NumPy reference.

Loads weights saved by halo/scorer.py (--save FILE.npz), builds the same network as an
ANER graph, and benchmarks it against a NumPy (Accelerate) forward pass on the CPU.

ANER keeps a graph on the Neural Engine only when every channel count is a multiple of
64 and at most 512, so the 2-value head is padded to 64 output channels and trimmed.

Usage (on the Mac, from the HALO folder):
  PYTHONPATH=/Volumes/Code/ANER/python python3 halo/aner_scorer.py results/scorer_hex11.npz \
      results/hex11.jsonl [--n 65536]

Prints: whether the Neural Engine is used, compile time, throughput (shapes/s) for ANER
and NumPy, and the largest disagreement between them.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def act(x):
    return x * (1.0 / (1.0 + np.exp(-1.702 * x)))


def load_weights(path):
    z = np.load(path)
    blocks = int(z["blocks"])
    W = {k: z[k].astype(np.float32) for k in z.files if k not in ("width", "blocks", "window")}
    return W, blocks, int(z["window"])


def numpy_forward(W, blocks, X):
    """X: (N, inputs) -> (N, 2)."""
    h = act(X @ W["inp.weight"].T + W["inp.bias"])
    for i in range(blocks):
        t = act(h @ W[f"blocks.{i}.l1.weight"].T + W[f"blocks.{i}.l1.bias"])
        h = h + t @ W[f"blocks.{i}.l2.weight"].T + W[f"blocks.{i}.l2.bias"]
    return h @ W["head.weight"].T + W["head.bias"]


def build_aner(W, blocks, spatial=64):
    import aner
    g = aner.Graph()
    x = g.input(W["inp.weight"].shape[1])

    def linear(t, w, b):
        return g.add(g.conv(t, w), g.const(b))

    h = g.gelu(linear(x, W["inp.weight"], W["inp.bias"]))
    for i in range(blocks):
        t = g.gelu(linear(h, W[f"blocks.{i}.l1.weight"], W[f"blocks.{i}.l1.bias"]))
        t = linear(t, W[f"blocks.{i}.l2.weight"], W[f"blocks.{i}.l2.bias"])
        h = g.add(h, t)
    hw = np.zeros((64, W["head.weight"].shape[1]), np.float32)
    hb = np.zeros(64, np.float32)
    hw[:2] = W["head.weight"]
    hb[:2] = W["head.bias"]
    g.output(linear(h, hw, hb))
    prog = g.compile(spatial)
    return g, prog


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weights")
    ap.add_argument("jsonl", help="runner JSONL to draw shapes from")
    ap.add_argument("--n", type=int, default=65536)
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()

    import scorer  # featurization lives there; torch is not needed for this path
    W, blocks, window = load_weights(args.weights)
    rows = scorer.load(args.jsonl)[: args.n]
    X = np.stack([scorer.images(line)[0] for line, _, _ in rows]).astype(np.float32)  # (N, 256)
    n = len(X)
    print(f"{n} shapes, network: {blocks} residual blocks, width {W['inp.weight'].shape[0]}, "
          f"{2 + 2 * blocks} linear layers")

    best = 1e9
    for _ in range(args.repeats):
        t0 = time.perf_counter()
        ref = numpy_forward(W, blocks, X)
        best = min(best, time.perf_counter() - t0)
    print(f"NumPy CPU : {n / best:12,.0f} shapes/s")

    g, prog = build_aner(W, blocks)
    print(f"ANER      : uses Neural Engine = {prog.uses_neural_engine}, compile {prog.compile_ms:.0f} ms")
    Xt = np.ascontiguousarray(X.T)  # ANER wants (channels, columns)
    prog.run_batch(Xt)  # warm-up
    best = 1e9
    for _ in range(args.repeats):
        t0 = time.perf_counter()
        out = prog.run_batch(Xt)
        best = min(best, time.perf_counter() - t0)
    got = out[:2].T
    print(f"ANER      : {n / best:12,.0f} shapes/s (wall, including host transfers)")
    diff = np.abs(got - ref)
    print(f"agreement : max |diff| tile logit {diff[:, 0].max():.4f}, hc {diff[:, 1].max():.4f}; "
          f"rank corr hc {np.corrcoef(np.argsort(np.argsort(got[:, 1])), np.argsort(np.argsort(ref[:, 1])))[0, 1]:.4f}")


if __name__ == "__main__":
    main()
