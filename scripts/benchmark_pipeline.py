#!/usr/bin/env python3
"""Bounded, reproducible HALO benchmarks; never writes to the search archive.

prepare makes fixed inputs and copies the old Python modules from local Git.
Workers run one implementation in a fresh process to avoid import contamination.
The replay measures geometry + real scoring + dispatch + real SAT/periodic checks
on the same candidate set. It excludes archive loading, retries and defect solves.
"""
import argparse
import collections
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(items):
    return hashlib.sha256("\n".join(sorted(items)).encode()).hexdigest()


def modules(directory):
    sys.path.insert(0, str(directory))
    import shape
    import search
    import runner
    import aner_scorer
    runner.PERIODIC_DLX = str(ROOT / "build/Darwin/periodic_dlx")
    runner.DEFAULT_SAT = str(ROOT / "build/Darwin/heesch-sat/src/sat")
    return shape, search, runner, aner_scorer


def prepare(folder, count):
    shape, search, _, _ = modules(ROOT / "halo")
    rng = random.Random(261026)
    pools = {g: [] for g in ("search", "search-sweep")}
    counts = collections.Counter()
    parents = {}
    with (ROOT / "results/search_hex_01.jsonl").open() as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("status") == "nontiler" and (row.get("hc") or 0) >= 3 and row.get("cells", 0) >= 15:
                parents[row["canon"]] = row
            gen = row.get("generator")
            if (gen not in pools or row.get("ts", "") < "2026-10-26T12:48:00"
                    or row.get("cells", 0) < 18 or row.get("status") not in ("nontiler", "isohedral")
                    or (row.get("seconds") or 0) > 0.2):
                continue
            counts[gen] += 1
            pool = pools[gen]
            if len(pool) < count:
                pool.append(row["canon"])
            else:
                j = rng.randrange(counts[gen])
                if j < count:
                    pool[j] = row["canon"]
    search.PREFER_MIN_CELLS = 18
    elite = sorted(parents.values(), key=search.fitness, reverse=True)[:64]
    if not elite or any(len(p) < count for p in pools.values()):
        raise RuntimeError("not enough benchmark inputs")
    known = pools["search"][:count // 4] + pools["search-sweep"][:count // 2]
    excluded = set(known)
    batches = []
    for batch in range(count // 128):
        raw, accepted = [], set()
        while len(accepted) < 2048:
            parent = rng.choice(elite)
            grid, cells = shape.parse(parent["canon"])
            cells = set(cells)
            while len(cells) < 18:
                cells.add(rng.choice(sorted({(x + dx, y + dy) for x, y in cells
                                             for dx, dy in shape.NEIGHBOURS[grid]} - cells)))
            new, _ = search.mutate(grid, cells, rng, 1 + int(rng.random() < 0.3) + int(rng.random() < 0.1))
            raw.append([grid, new])
            if not 18 <= len(new) <= 30:
                continue
            ok, problems, _ = shape.check_cells(grid, new)
            if ok and not any("stricter" in p for p in problems):
                canon = shape.canonical(grid, new)
                if canon not in excluded:
                    accepted.add(canon)
        excluded.update(accepted)
        batches.append(raw)
        print(f"prepared batch {batch + 1}: {len(raw)} attempts -> 2048 candidates", flush=True)
    baseline = folder / "baseline"
    baseline.mkdir()
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "HEAD", "halo"], cwd=ROOT, text=True)
    for filename in files.splitlines():
        if filename.endswith(".py"):
            data = subprocess.check_output(["git", "show", "HEAD:" + filename], cwd=ROOT)
            (baseline / Path(filename).name).write_bytes(data)
    fixture = {"count": count, "known": known, "batches": batches,
               "base_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (folder / "fixture.json").write_text(json.dumps(fixture))
    print(f"fixed inputs saved in {folder}; {count} total checks per replay", flush=True)


def candidate_batch(raw, excluded, shape):
    candidates = []
    seen = set(excluded)
    for grid, cells in raw:
        cells = [tuple(c) for c in cells]
        if not 18 <= len(cells) <= 30:
            continue
        if hasattr(shape, "check_cells"):
            ok, problems, _ = shape.check_cells(grid, cells)
        else:
            ok, problems, _ = shape.check(shape.fmt(grid, cells))
        if not ok or any("stricter" in p for p in problems):
            continue
        canon = shape.canonical(grid, cells)
        if canon not in seen:
            candidates.append(canon)
            seen.add(canon)
    assert len(candidates) == 2048, len(candidates)
    return candidates


def replay(folder, implementation, schedule, repeat, spatial=64):
    import numpy as np
    source = folder / "baseline" if implementation == "baseline" else ROOT / "halo"
    shape, _, runner, scorer_mod = modules(source)
    fixture = json.loads((folder / "fixture.json").read_text())
    scorer = scorer_mod.Scorer(str(ROOT / "results/models/scorer_v4_hex.npz"), schedule)
    if spatial != 64:
        scorer.prog.close()
        scorer.prog, _ = scorer_mod.compile_schedule(scorer.graph, schedule, spatial)
    if schedule in ("ane", "gpu", "split") and scorer.backend not in ("ane", "gpu", "ane+gpu"):
        raise RuntimeError("accelerator unavailable: " + scorer.backend)
    scorer.score(np.zeros((64, 512), np.float32))
    excluded = set(fixture["known"])
    batch_excludes = []
    for raw in fixture["batches"]:
        batch_excludes.append(set(excluded))
        # Setup is excluded from timings. Both implementations must accept the same cells.
        excluded.update(candidate_batch(raw, excluded, shape))
    opts = argparse.Namespace(sat=runner.DEFAULT_SAT, maxlevel=7, timeout=0.5,
                              timeout_long=1.0, mem_mb=1500, periodic_budget=0.1,
                              periodic_quick=0.05, periodic_max_t=24, escalate_maxlevel=9)
    metrics = {"geometry": 0.0, "features": 0.0, "inference": 0.0, "candidate_hashes": []}

    def refill(index):
        t = time.perf_counter()
        candidates = candidate_batch(fixture["batches"][index], batch_excludes[index], shape)
        t1 = time.perf_counter()
        if hasattr(scorer, "featurize_many"):
            images, owners = scorer.featurize_many(candidates)
            assert np.array_equal(owners, np.repeat(np.arange(len(candidates)), 12))
        else:
            images = np.stack([v for c in candidates for v in scorer.featurize(c)])
        t2 = time.perf_counter()
        scores = scorer.score(images)[:, 1].reshape(len(candidates), 12).mean(axis=1)
        t3 = time.perf_counter()
        metrics["geometry"] += t1 - t
        metrics["features"] += t2 - t1
        metrics["inference"] += t3 - t2
        metrics["candidate_hashes"].append(digest(candidates))
        ranked = sorted(zip(scores.tolist(), candidates), reverse=True)[:32]
        # Freeze checker inputs across precision/backend comparisons. Ranking
        # agreement is measured separately; this replay compares execution cost.
        return fixture.get("fixed_picks", {}).get(str(index), [c for _, c in ranked])

    known = collections.deque(fixture["known"])
    scored = collections.deque()
    submitted, answers = [], []
    next_batch = 0
    prefetch = None
    child0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu0 = time.process_time()
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="halo_bench_sat_") as workdir, \
            ThreadPoolExecutor(max_workers=1) as producer, ThreadPoolExecutor(max_workers=14) as checkers:
        running = {}
        turn = 0
        while known or scored or running or next_batch < len(fixture["batches"]) or prefetch is not None:
            if prefetch is not None and prefetch.done():
                scored.extend(prefetch.result())
                prefetch = None
            if (implementation == "current" and prefetch is None
                    and next_batch < len(fixture["batches"]) and len(scored) <= 16):
                prefetch = producer.submit(refill, next_batch)
                next_batch += 1
            while len(running) < 14 and (known or scored or next_batch < len(fixture["batches"])):
                want_scored = turn % 4 == 3
                turn += 1
                if implementation == "baseline" and want_scored and not scored and next_batch < len(fixture["batches"]):
                    scored.extend(refill(next_batch))
                    next_batch += 1
                if scored and (want_scored or not known):
                    canon = scored.popleft()
                elif known:
                    canon = known.popleft()
                elif scored:
                    canon = scored.popleft()
                else:
                    break
                submitted.append(canon)
                running[checkers.submit(runner.classify, canon, opts, workdir)] = canon
            if running:
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in done:
                    canon = running.pop(future)
                    record = future.result()
                    answers.append([canon, record["status"], record.get("hc"), record.get("hh")])
            elif prefetch is not None:
                wait([prefetch])
            elif next_batch >= len(fixture["batches"]) and not known and not scored:
                break
    elapsed = time.perf_counter() - start
    child1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = time.process_time() - cpu0 + child1.ru_utime - child0.ru_utime + child1.ru_stime - child0.ru_stime
    assert len(answers) == fixture["count"], len(answers)
    result = {"phase": "replay", "implementation": implementation, "schedule": schedule,
              "backend": scorer.backend, "spatial": spatial, "repeat": repeat, "seconds": elapsed,
              "checks_per_second": len(answers) / elapsed, "cpu_seconds": cpu,
              "average_busy_cores": cpu / elapsed, "checks": len(answers),
              "input_hash": digest(submitted), "statuses": dict(collections.Counter(r[1] for r in answers)),
              "stages": metrics, "answers": answers, "python": sys.version}
    suffix = "" if spatial == 64 else f"-w{spatial}"
    path = folder / f"replay-{implementation}-{schedule}-{repeat}{suffix}.json"
    path.write_text(json.dumps(result))
    print(json.dumps({k: v for k, v in result.items() if k != "answers"}), flush=True)


def accelerators(folder):
    import numpy as np
    shape, _, _, scorer_mod = modules(ROOT / "halo")
    fixture = json.loads((folder / "fixture.json").read_text())
    weights = str(ROOT / "results/models/scorer_v4_hex.npz")
    base = scorer_mod.Scorer(weights, "numpy")
    candidates = candidate_batch(fixture["batches"][0], set(fixture["known"]), shape)
    images = np.stack([v for c in candidates for v in base.featurize(c)])
    reference = base.score(images)
    results = []
    configs = [("ane", 64), ("gpu", 64), ("split", 64), ("ane", 128), ("ane", 256), ("ane", 512)]
    for name, spatial in configs:
        s = scorer_mod.Scorer(weights, name)
        if spatial != 64:
            s.prog.close()
            s.prog, _ = scorer_mod.compile_schedule(s.graph, name, spatial)
        if s.backend not in ("ane", "gpu", "ane+gpu"):
            results.append({"schedule": name, "spatial": spatial, "backend": s.backend, "skipped": True})
            continue
        for n in (384, 3072, len(images)):
            x = images[:n]
            s.score(x)
            times = []
            for _ in range(5):
                t = time.perf_counter()
                out = s.score(x)
                times.append(time.perf_counter() - t)
            error = float(np.max(np.abs(out - reference[:n])))
            assert np.isfinite(out).all()
            groups = n // 12
            target = reference[:n, 1].reshape(groups, 12).mean(axis=1)
            scores = out[:, 1].reshape(groups, 12).mean(axis=1)
            k = min(32, groups)
            overlap = len(set(np.argsort(target)[-k:]) & set(np.argsort(scores)[-k:])) / k
            result = {"schedule": name, "spatial": spatial, "backend": s.backend, "images": n,
                      "median_ms": statistics.median(times) * 1000,
                      "images_per_second": n / statistics.median(times), "max_abs_error": error,
                      "top32_overlap": overlap}
            results.append(result)
            print(json.dumps(result), flush=True)
        s.prog.close()
    try:
        import mlx.core as mx
    except ImportError:
        print("MLX unavailable in this interpreter", flush=True)
    else:
        for dtype in ("fp16", "fp32"):
            dt = mx.float16 if dtype == "fp16" else mx.float32
            W = {k: mx.array(v).astype(dt) for k, v in base.W.items()}
            def fwd(x):
                act = lambda v: v * mx.sigmoid(1.702 * v)
                h = act(x @ W["inp.weight"].T + W["inp.bias"])
                for i in range(base.blocks):
                    h = h + act(h @ W[f"blocks.{i}.l1.weight"].T + W[f"blocks.{i}.l1.bias"]) @ W[f"blocks.{i}.l2.weight"].T + W[f"blocks.{i}.l2.bias"]
                return h @ W["head.weight"].T + W["head.bias"]
            compiled = mx.compile(fwd)
            for n in (384, 3072, len(images)):
                def run():
                    return np.array(compiled(mx.array(images[:n]).astype(dt)).astype(mx.float32))
                run(); times = []
                for _ in range(5):
                    t = time.perf_counter(); out = run(); times.append(time.perf_counter() - t)
                result = {"schedule": "mlx", "backend": f"mlx-gpu-{dtype}", "images": n,
                          "median_ms": statistics.median(times) * 1000,
                          "max_abs_error": float(np.max(np.abs(out - reference[:n])))}
                results.append(result)
                print(json.dumps(result), flush=True)
    (folder / "accelerators.json").write_text(json.dumps(results, indent=2))


def precision(folder):
    import numpy as np
    shape, _, _, scorer_mod = modules(ROOT / "halo")
    fixture = json.loads((folder / "fixture.json").read_text())
    weights = str(ROOT / "results/models/scorer_v4_hex.npz")
    base = scorer_mod.Scorer(weights, "numpy")
    candidates = candidate_batch(fixture["batches"][0], set(fixture["known"]), shape)
    images = np.stack([v for c in candidates for v in base.featurize(c)])
    t = time.perf_counter()
    reference = base.score(images)
    results = [{"backend": "numpy-fp32", "seconds": time.perf_counter() - t}]
    mean_ref = reference[:, 1].reshape(len(candidates), 12).mean(axis=1)
    ref_best = set(np.argsort(mean_ref)[-32:])
    for schedule in ("ane", "gpu", "split", "mlx-fp32"):
        s = scorer_mod.Scorer(weights, schedule, 256 if schedule == "ane" else 64)
        s.score(images)
        t = time.perf_counter(); out = s.score(images); seconds = time.perf_counter() - t
        delta = np.abs(out - reference)
        mean_out = out[:, 1].reshape(len(candidates), 12).mean(axis=1)
        best = set(np.argsort(mean_out)[-32:])
        result = {"backend": s.backend, "seconds": seconds,
                  "max_tile_logit_error": float(delta[:, 0].max()),
                  "max_hc_image_error": float(delta[:, 1].max()),
                  "max_mean_hc_error": float(np.abs(mean_out - mean_ref).max()),
                  "p99_mean_hc_error": float(np.percentile(np.abs(mean_out - mean_ref), 99)),
                  "top32_overlap": len(best & ref_best),
                  "top32_mean_fp32_score": float(mean_ref[list(best)].mean()),
                  "reference_top32_mean_score": float(mean_ref[list(ref_best)].mean())}
        results.append(result)
        print(json.dumps(result), flush=True)
        if s.prog is not None:
            s.prog.close()
    (folder / "precision.json").write_text(json.dumps(results, indent=2))


def gpu_precision(folder):
    """Run against the explicit temporary FP32 GPU prototype, never a split."""
    import numpy as np
    shape, _, _, scorer_mod = modules(ROOT / "halo")
    fixture = json.loads((folder / "fixture.json").read_text())
    weights = str(ROOT / "results/models/scorer_v4_hex.npz")
    base = scorer_mod.Scorer(weights, "numpy")
    candidates = candidate_batch(fixture["batches"][0], set(fixture["known"]), shape)
    images = np.stack([v for c in candidates for v in base.featurize(c)])
    reference = base.score(images)
    s = scorer_mod.Scorer(weights, "gpu")
    assert s.backend == "gpu"
    results = []
    for n in (384, 3072, len(images)):
        s.score(images[:n]); times = []
        for _ in range(5):
            t = time.perf_counter(); out = s.score(images[:n]); times.append(time.perf_counter() - t)
        delta = np.abs(out - reference[:n])
        group = n // 12
        mean_ref = reference[:n, 1].reshape(group, 12).mean(axis=1)
        mean_out = out[:, 1].reshape(group, 12).mean(axis=1)
        k = min(32, group)
        overlap = len(set(np.argsort(mean_ref)[-k:]) & set(np.argsort(mean_out)[-k:]))
        result = {"backend": "gpu-fp32-prototype", "images": n,
                  "median_ms": statistics.median(times) * 1000,
                  "max_tile_logit_error": float(delta[:, 0].max()),
                  "max_hc_image_error": float(delta[:, 1].max()),
                  "max_mean_hc_error": float(np.abs(mean_out - mean_ref).max()), "top32_overlap": overlap}
        results.append(result); print(json.dumps(result), flush=True)
    (folder / "gpu-fp32-prototype.json").write_text(json.dumps(results, indent=2))


def freeze_picks(folder):
    import numpy as np
    shape, _, _, scorer_mod = modules(ROOT / "halo")
    fixture = json.loads((folder / "fixture.json").read_text())
    scorer = scorer_mod.Scorer(str(ROOT / "results/models/scorer_v4_hex.npz"), "numpy")
    excluded = set(fixture["known"])
    picks = {}
    for index, raw in enumerate(fixture["batches"]):
        candidates = candidate_batch(raw, excluded, shape)
        excluded.update(candidates)
        x = np.stack([v for canon in candidates for v in scorer.featurize(canon)])
        scores = scorer.score(x)[:, 1].reshape(len(candidates), 12).mean(axis=1)
        picks[str(index)] = [canon for _, canon in sorted(zip(scores.tolist(), candidates), reverse=True)[:32]]
    fixture["fixed_picks"] = picks
    (folder / "fixture.json").write_text(json.dumps(fixture))
    print("froze checker picks to the same FP32-ranked workload for all backends", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=["prepare", "replay", "accelerators", "matrix", "tune", "precision", "gpu-precision", "freeze", "final-matrix"])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--implementation", choices=["baseline", "current"], default="current")
    ap.add_argument("--schedule", default="ane")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--spatial", type=int, default=64)
    ap.add_argument("--count", type=int, default=512)
    args = ap.parse_args()
    if args.phase == "prepare":
        if args.count < 128 or args.count % 128:
            ap.error("--count must be a positive multiple of 128")
        args.folder.mkdir(parents=True, exist_ok=False)
        prepare(args.folder, args.count)
    elif args.phase == "replay":
        replay(args.folder, args.implementation, args.schedule, args.repeat, args.spatial)
    elif args.phase == "accelerators":
        accelerators(args.folder)
    elif args.phase == "precision":
        precision(args.folder)
    elif args.phase == "gpu-precision":
        gpu_precision(args.folder)
    elif args.phase == "freeze":
        freeze_picks(args.folder)
    elif args.phase == "final-matrix":
        runs = [("baseline", "ane", 64, 3), ("current", "ane", 64, 3),
                ("current", "ane", 256, 3), ("current", "mlx-fp32", 64, 1),
                ("current", "mlx-fp32", 64, 2), ("current", "ane", 256, 4),
                ("current", "ane", 64, 4), ("baseline", "ane", 64, 4)]
        for implementation, schedule, spatial, repeat in runs:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "replay", str(args.folder),
                            "--implementation", implementation, "--schedule", schedule,
                            "--spatial", str(spatial), "--repeat", str(repeat)], check=True, close_fds=False)
        loaded = []
        for impl, schedule, spatial, repeat in runs:
            suffix = "" if spatial == 64 else f"-w{spatial}"
            loaded.append(json.loads((args.folder / f"replay-{impl}-{schedule}-{repeat}{suffix}.json").read_text()))
        assert len({r["input_hash"] for r in loaded}) == 1, "checker workloads differ"
        labels = collections.defaultdict(set)
        for run in loaded:
            for canon, status, hc, hh in run["answers"]:
                if status in ("nontiler", "isohedral", "periodic"):
                    labels[canon].add(("tiler", None) if status != "nontiler" else (status, hc))
        assert not any(len(values) > 1 for values in labels.values()), "contradictory settled classifications"
        summary = {}
        for impl, schedule, spatial, _ in runs:
            key = f"{impl}-{schedule}-w{spatial}"
            group = [r for r in loaded if r["implementation"] == impl and r["schedule"] == schedule and r["spatial"] == spatial]
            summary[key] = {"median_seconds": statistics.median(r["seconds"] for r in group),
                            "checks_per_second": statistics.median(r["checks_per_second"] for r in group),
                            "runs": [r["seconds"] for r in group], "statuses": [r["statuses"] for r in group]}
        summary["fixed_input_hash"] = loaded[0]["input_hash"]
        summary["identical_outcomes"] = len({digest([json.dumps(a) for a in r["answers"]]) for r in loaded}) == 1
        summary["python"] = sys.version
        (args.folder / "final-matrix-summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary), flush=True)
    elif args.phase == "matrix":
        for implementation, repeat in [("baseline", 1), ("current", 1), ("current", 2), ("baseline", 2)]:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "replay", str(args.folder),
                            "--implementation", implementation, "--schedule", args.schedule,
                            "--repeat", str(repeat)], check=True, close_fds=False)
        runs = [json.loads((args.folder / f"replay-{impl}-{args.schedule}-{rep}.json").read_text())
                for impl, rep in [("baseline", 1), ("current", 1), ("current", 2), ("baseline", 2)]]
        assert len({r["input_hash"] for r in runs}) == 1, "checker workloads differ"
        assert all(r["stages"]["candidate_hashes"] == runs[0]["stages"]["candidate_hashes"] for r in runs)
        labels = collections.defaultdict(set)
        for run in runs:
            for canon, status, hc, hh in run["answers"]:
                if status in ("nontiler", "isohedral", "periodic"):
                    labels[canon].add(("tiler", None) if status != "nontiler" else (status, hc))
        assert not any(len(values) > 1 for values in labels.values()), "contradictory settled classifications"
        summary = {impl: {"median_seconds": statistics.median(r["seconds"] for r in runs if r["implementation"] == impl),
                          "runs": [r["seconds"] for r in runs if r["implementation"] == impl]}
                   for impl in ("baseline", "current")}
        summary["speedup"] = summary["baseline"]["median_seconds"] / summary["current"]["median_seconds"]
        summary["fixed_input_hash"] = runs[0]["input_hash"]
        (args.folder / "matrix-summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary), flush=True)
    else:
        for schedule, spatial, repeat in [("ane", 256, 1), ("gpu", 64, 1), ("split", 64, 1),
                                          ("split", 64, 2), ("gpu", 64, 2), ("ane", 256, 2)]:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "replay", str(args.folder),
                            "--schedule", schedule, "--spatial", str(spatial),
                            "--repeat", str(repeat)], check=True, close_fds=False)


if __name__ == "__main__":
    main()
