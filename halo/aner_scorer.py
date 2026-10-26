#!/usr/bin/env python3
"""HALO scorer inference on the Apple Neural Engine and GPU via ANER, with references.

Loads weights saved by halo/scorer.py (--save FILE.npz), builds the same network as an
ANER graph, and benchmarks every way of running it on the owner's Mac:

  NumPy (CPU / Accelerate), MLX (GPU, fp32 and fp16, if installed), and ANER with each
  schedule: ANE (Neural Engine only), GPU (Metal only) and SPLIT (both at once; ANER hands
  each engine the next chunk of the batch as it falls idle). Older libaner builds without
  schedules fall back to ANE only.

Two ANER-specific details:
- ANER keeps a graph on the Neural Engine only when every channel count is a multiple of
  64 and at most 512, so the 2-value head is padded to 64 output channels and trimmed.
- The network's activation is g(z) = z*sigmoid(1.702 z). ANER's built-in gelu lowers the
  1.702 scale to a dense 512x512 diagonal matmul, a third of all matrix work here. Instead
  we use g(z) = SiLU(1.702 z)/1.702 with SiLU(y) = y*sigmoid(y) (just sigmoid + mul) and
  fold the factors into the weights, carrying the residual stream scaled by s = 1.702:
      input layer W, b  -> s*W, s*b          block l1: W -> W,   b -> s*b
      block l2:  W -> W,   b -> s*b          head:     W -> W/s, b -> b
  This is exactly the same function in exact arithmetic, with no extra matmuls.

Usage (on the Mac, from the HALO folder):
  PYTHONPATH=/Volumes/Code/ANER/python python3 halo/aner_scorer.py results/models/scorer_hex11_b8.npz \
      results/hex11.jsonl [--n 65536]

Library use (e.g. from search.py):
  from aner_scorer import Scorer
  sc = Scorer("results/models/scorer_hex11_b8.npz", schedule="ane")   # or "split", "gpu", "mlx", "numpy"
  out = sc.score(X)   # X: (N, 256) float32 -> (N, 2): [tile logit, hc estimate]
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

S = 1.702


def act(x):
    return x * (1.0 / (1.0 + np.exp(-S * x)))


def load_weights(path):
    z = np.load(path)
    blocks = int(z["blocks"])
    W = {k: z[k].astype(np.float32) for k in z.files if k not in ("width", "blocks", "window")}
    return W, blocks, int(z["window"])


def numpy_forward(W, blocks, X):
    """Reference forward pass. X: (N, inputs) -> (N, 2)."""
    h = act(X @ W["inp.weight"].T + W["inp.bias"])
    for i in range(blocks):
        t = act(h @ W[f"blocks.{i}.l1.weight"].T + W[f"blocks.{i}.l1.bias"])
        h = h + t @ W[f"blocks.{i}.l2.weight"].T + W[f"blocks.{i}.l2.bias"]
    return h @ W["head.weight"].T + W["head.bias"]


def fold(W, blocks):
    """Weights for the SiLU formulation with the residual stream scaled by S (see module doc)."""
    F = {"inp.weight": S * W["inp.weight"], "inp.bias": S * W["inp.bias"],
         "head.weight": W["head.weight"] / S, "head.bias": W["head.bias"].copy()}
    for i in range(blocks):
        F[f"blocks.{i}.l1.weight"] = W[f"blocks.{i}.l1.weight"].copy()
        F[f"blocks.{i}.l1.bias"] = S * W[f"blocks.{i}.l1.bias"]
        F[f"blocks.{i}.l2.weight"] = W[f"blocks.{i}.l2.weight"].copy()
        F[f"blocks.{i}.l2.bias"] = S * W[f"blocks.{i}.l2.bias"]
    return F


def numpy_forward_folded(F, blocks, X):
    """Same function via the folded weights; used to test fold() against numpy_forward."""
    silu = lambda y: y / (1.0 + np.exp(-y))  # noqa: E731
    h = silu(X @ F["inp.weight"].T + F["inp.bias"])
    for i in range(blocks):
        t = silu(h @ F[f"blocks.{i}.l1.weight"].T + F[f"blocks.{i}.l1.bias"])
        h = h + t @ F[f"blocks.{i}.l2.weight"].T + F[f"blocks.{i}.l2.bias"]
    return h @ F["head.weight"].T + F["head.bias"]


def mlx_bench(W, blocks, X, ref, repeats, dtype_name):
    """GPU (Metal) forward pass via Apple's MLX. Returns (shapes/s, max |diff| vs ref) or None."""
    try:
        import mlx.core as mx
    except ImportError:
        return None
    dt = mx.float16 if dtype_name == "fp16" else mx.float32
    Wm = {k: mx.array(v).astype(dt) for k, v in W.items()}

    def act_mx(x):
        return x * mx.sigmoid(S * x)

    def fwd(x):
        h = act_mx(x @ Wm["inp.weight"].T + Wm["inp.bias"])
        for i in range(blocks):
            t = act_mx(h @ Wm[f"blocks.{i}.l1.weight"].T + Wm[f"blocks.{i}.l1.bias"])
            h = h + t @ Wm[f"blocks.{i}.l2.weight"].T + Wm[f"blocks.{i}.l2.bias"]
        return h @ Wm["head.weight"].T + Wm["head.bias"]

    fwd_c = mx.compile(fwd)
    xs = mx.array(X).astype(dt)
    mx.eval(fwd_c(xs))  # warm-up / compile
    best = 1e9
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fwd_c(xs)
        mx.eval(out)
        best = min(best, time.perf_counter() - t0)
    got = np.array(out.astype(mx.float32))
    return len(X) / best, float(np.abs(got - ref).max())


def build_graph(W, blocks):
    """ANER graph of the folded network (SiLU via sigmoid+mul, head padded to 64)."""
    import aner
    F = fold(W, blocks)
    g = aner.Graph()
    x = g.input(F["inp.weight"].shape[1])

    def linear(t, w, b):
        return g.add(g.conv(t, w), g.const(b))

    def silu(t):
        return g.mul(t, g.sigmoid(t))

    h = silu(linear(x, F["inp.weight"], F["inp.bias"]))
    for i in range(blocks):
        t = silu(linear(h, F[f"blocks.{i}.l1.weight"], F[f"blocks.{i}.l1.bias"]))
        t = linear(t, F[f"blocks.{i}.l2.weight"], F[f"blocks.{i}.l2.bias"])
        h = g.add(h, t)
    hw = np.zeros((64, F["head.weight"].shape[1]), np.float32)
    hb = np.zeros(64, np.float32)
    hw[:2] = F["head.weight"]
    hb[:2] = F["head.bias"]
    g.output(linear(h, hw, hb))
    return g


def compile_schedule(g, name, spatial=64):
    """Compile with a named schedule; returns (program, label) or (None, reason)."""
    import aner
    sched = getattr(aner, "Schedule", None)
    if name == "ane":
        return (g.compile(spatial, sched.ANE) if sched else g.compile(spatial)), "ANE"
    if sched is None:
        return None, "this libaner has no schedules (rebuild ANER for GPU/SPLIT)"
    return g.compile(spatial, sched.GPU if name == "gpu" else sched.SPLIT), name.upper()


class Scorer:
    """Batch scorer: ANER (schedule 'ane', 'gpu' or 'split'), MLX on the GPU ('mlx', fp16),
    or NumPy on the CPU ('numpy'). Falls back to NumPy if the chosen backend is unavailable."""

    def __init__(self, weights, schedule="ane"):
        self.W, self.blocks, self.window = load_weights(weights)
        self.schedule = schedule
        self.prog = None
        self.mlx_fwd = None
        if schedule == "mlx":
            try:
                import mlx.core as mx
                Wm = {k: mx.array(v).astype(mx.float16) for k, v in self.W.items()}
                blocks = self.blocks

                def fwd(x):
                    a = lambda z: z * mx.sigmoid(S * z)  # noqa: E731
                    h = a(x @ Wm["inp.weight"].T + Wm["inp.bias"])
                    for i in range(blocks):
                        t = a(h @ Wm[f"blocks.{i}.l1.weight"].T + Wm[f"blocks.{i}.l1.bias"])
                        h = h + t @ Wm[f"blocks.{i}.l2.weight"].T + Wm[f"blocks.{i}.l2.bias"]
                    return h @ Wm["head.weight"].T + Wm["head.bias"]

                self._mx = mx
                self.mlx_fwd = mx.compile(fwd)
            except Exception as exc:
                print(f"Scorer: MLX unavailable ({exc}); using NumPy", file=sys.stderr)
        elif schedule != "numpy":
            try:
                self.graph = build_graph(self.W, self.blocks)
                self.prog, _ = compile_schedule(self.graph, schedule)
            except Exception as exc:  # aner missing or compile failure: fall back to NumPy
                print(f"Scorer: ANER unavailable ({exc}); using NumPy", file=sys.stderr)
                self.prog = None

    @property
    def backend(self):
        if self.mlx_fwd is not None:
            return "mlx-gpu-fp16"
        if self.prog is None:
            return "numpy"
        parts = [n for n, on in (("ane", self.prog.uses_neural_engine),
                                 ("gpu", getattr(self.prog, "uses_gpu", False))) if on]
        return "+".join(parts) or "interpreter"

    def score(self, X):
        X = np.ascontiguousarray(X, dtype=np.float32)
        if self.mlx_fwd is not None:
            mx = self._mx
            out = self.mlx_fwd(mx.array(X).astype(mx.float16))
            return np.array(out.astype(mx.float32))
        if self.prog is None:
            return numpy_forward(self.W, self.blocks, X)
        n = len(X)
        if n < 64:  # pad to one tile
            X = np.vstack([X, np.zeros((64 - n, X.shape[1]), np.float32)])
        out = self.prog.run_batch(np.ascontiguousarray(X.T))
        return out[:2, :n].T


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weights")
    ap.add_argument("jsonl", help="runner JSONL to draw shapes from")
    ap.add_argument("--n", type=int, default=65536)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--schedules", default="ane,gpu,split", help="ANER schedules to time (comma-separated)")
    ap.add_argument("--no-mlx", action="store_true", help="skip the MLX GPU reference")
    ap.add_argument("--label", default="", help="prefix for ANER result lines (e.g. the config being tested)")
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
    print(f"{'NumPy CPU':14s}: {n / best:12,.0f} shapes/s")
    folded_err = float(np.abs(numpy_forward_folded(fold(W, blocks), blocks, X[:4096]) - ref[:4096]).max())
    print(f"{'(fold check)':14s}: folded network max |diff| vs original {folded_err:.2e}")

    for dt in (() if args.no_mlx else ("fp32", "fp16")):
        res = mlx_bench(W, blocks, X, ref, args.repeats, dt)
        if res is None:
            print(f"{'MLX GPU':14s}: not installed (pip install mlx), skipped")
            break
        print(f"{'MLX GPU ' + dt:14s}: {res[0]:12,.0f} shapes/s, max |diff| vs CPU {res[1]:.4f}")

    g = build_graph(W, blocks)
    Xt = np.ascontiguousarray(X.T)  # ANER wants (channels, columns)
    rank_ref = np.argsort(np.argsort(ref[:, 1]))
    for name in [x for x in args.schedules.split(",") if x]:
        prog, label = compile_schedule(g, name)
        if prog is None:
            print(f"{'ANER ' + name.upper():14s}: skipped: {label}")
            continue
        engines = "+".join(e for e, on in (("NE", prog.uses_neural_engine),
                                          ("GPU", getattr(prog, "uses_gpu", False))) if on) or "CPU interpreter"
        prog.run_batch(Xt)  # warm-up
        best = 1e9
        for _ in range(args.repeats):
            t0 = time.perf_counter()
            out = prog.run_batch(Xt)
            best = min(best, time.perf_counter() - t0)
        got = out[:2].T
        diff = np.abs(got - ref)
        rc = np.corrcoef(np.argsort(np.argsort(got[:, 1])), rank_ref)[0, 1]
        print(f"{args.label}{'ANER ' + label:14s}: {n / best:12,.0f} shapes/s on {engines} (compile {prog.compile_ms:.0f} ms); "
              f"max |diff| tile {diff[:, 0].max():.3f}, hc {diff[:, 1].max():.3f}; rank corr {rc:.4f}")
        prog.close()


if __name__ == "__main__":
    main()
