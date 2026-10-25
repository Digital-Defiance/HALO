#!/usr/bin/env python3
"""HALO parallel runner.

Classifies polyforms with Kaplan's heesch-sat, one checker process per shape, with
per-shape time and memory caps, append-only JSONL logging, and resume.

Usage:
  python3 halo/runner.py INPUT --out results/RUN.jsonl [--jobs N] [--maxlevel 7]
                         [--timeout 120] [--mem-mb 4000] [--witness-min-hc 3]

INPUT is a text file with one shape per line in heesch-sat format, e.g. the output of
`gen` ("H? 0 0 1 0 ...") or a bare "O 0 0 1 0 ..." line. Other lines are ignored.
INPUT may also be a JSONL file from an earlier run; with --only-status you can re-run,
for example, just the shapes that hit a cap:

  python3 halo/runner.py results/A.jsonl --only-status timeout,memout \
      --out results/A_pass2.jsonl --jobs 3 --timeout 1800 --mem-mb 18000

Each checked shape appends one JSON object to --out:
  shape, grid, cells, status, hc, hh, seconds, peak_rss_mb, maxlevel, stop, witness
status is one of: nontiler, isohedral, anisohedral, aperiodic, inconclusive, hole,
unknown, timeout, memout, error. Shapes already present in --out are skipped, so an
interrupted run can simply be restarted with the same command.

Works on macOS and Linux. Python 3.8+, standard library only (psutil used if present).
"""
import argparse
import collections
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SAT = os.path.join(ROOT, "build", platform.system(), "heesch-sat", "src", "sat")
GRID_LETTERS = set("OHIKCDAXTB")  # first character of a heesch-sat shape line

STATUS_CODES = {
    "?": "unknown",
    "O": "hole",
    "!": "inconclusive",
    "~": "nontiler",
    "I": "isohedral",
    "#": "anisohedral",
    "$": "aperiodic",
}

try:
    import psutil  # optional
except ImportError:  # pragma: no cover
    psutil = None


def rss_mb(pid):
    """Resident set size of a process in MB, or None if unavailable."""
    try:
        if psutil is not None:
            return psutil.Process(pid).memory_info().rss / 1e6
        status = f"/proc/{pid}/status"
        if os.path.exists(status):
            with open(status) as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1e3
            return None
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True).stdout.strip()
        return int(out) / 1e3 if out else None
    except Exception:
        return None


def shape_key(line):
    """Key used for dedupe and resume: grid letter plus the sorted cell list."""
    toks = line.split()
    grid = toks[0].rstrip("?")
    nums = list(map(int, toks[1:]))
    cells = sorted(zip(nums[0::2], nums[1::2]))
    return grid + " " + " ".join(f"{x} {y}" for x, y in cells)


def parse_output(text):
    """Parse one classified record written by `sat -show`."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {"status": "error"}
    toks = lines[1].split()
    status = STATUS_CODES.get(toks[0][0], "error")
    rec = {"status": status, "hc": None, "hh": None}
    if status == "nontiler" and len(toks) >= 3:
        rec["hc"], rec["hh"] = int(toks[1]), int(toks[2])
    rec["record"] = "\n".join(lines)
    return rec


def run_one(sat, line, maxlevel, timeout, mem_mb, workdir):
    fd, inp = tempfile.mkstemp(suffix=".txt", dir=workdir)
    with os.fdopen(fd, "w") as fh:
        fh.write(line + "\n")
    out = inp[:-4] + ".out.txt"
    cmd = [sat, "-isohedral", "-show", "-maxlevel", str(maxlevel), inp, "-o", out]
    start = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    peak = 0.0
    stop = None
    while proc.poll() is None:
        r = rss_mb(proc.pid)
        if r is not None:
            peak = max(peak, r)
            if r > mem_mb:
                stop = "memout"
                proc.kill()
                break
        if time.monotonic() - start > timeout:
            stop = "timeout"
            proc.kill()
            break
        time.sleep(0.05 if time.monotonic() - start < 1 else 0.25)
    proc.wait()
    secs = time.monotonic() - start
    stderr = proc.stderr.read().decode(errors="replace")[-500:] if proc.stderr else ""
    text = ""
    if os.path.exists(out):
        with open(out) as fh:
            text = fh.read()
    for p in (inp, out):
        try:
            os.remove(p)
        except OSError:
            pass
    if stop:
        rec = {"status": stop, "hc": None, "hh": None}
    elif proc.returncode != 0:
        rec = {"status": "error", "hc": None, "hh": None, "stderr": stderr}
    else:
        rec = parse_output(text)
    rec.update({"seconds": round(secs, 4), "peak_rss_mb": round(peak, 1),
                "maxlevel": maxlevel, "stop": stop})
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sat", default=DEFAULT_SAT)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--maxlevel", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=120.0, help="seconds per shape")
    ap.add_argument("--mem-mb", type=float, default=4000.0, help="kill a check above this RSS")
    ap.add_argument("--witness-min-hc", type=int, default=3,
                    help="store the witness patch for non-tilers with hc >= this")
    ap.add_argument("--limit", type=int, default=0, help="check at most this many new shapes")
    ap.add_argument("--generator", default="file", help="label stored with each record")
    ap.add_argument("--only-status", default="",
                    help="with JSONL input: comma-separated statuses to re-run (e.g. timeout,memout)")
    args = ap.parse_args()

    if not os.access(args.sat, os.X_OK):
        sys.exit(f"checker not found at {args.sat}; run scripts/setup_heesch_sat.sh")

    done = set()
    if os.path.exists(args.out):
        with open(args.out) as fh:
            for ln in fh:
                try:
                    done.add(json.loads(ln)["key"])
                except Exception:
                    pass

    wanted = {s for s in args.only_status.split(",") if s}
    todo, seen = [], set()
    with open(args.input) as fh:
        for ln in fh:
            ln = ln.strip()
            if args.input.endswith(".jsonl"):
                try:
                    row = json.loads(ln)
                except Exception:
                    continue
                if wanted and row.get("status") not in wanted:
                    continue
                ln = row.get("shape", "")
            if not ln or ln[0] not in GRID_LETTERS:
                continue
            key = shape_key(ln)
            if key in done or key in seen:
                continue
            seen.add(key)
            todo.append((key, ln))
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(done)} already done, {len(todo)} to check, {args.jobs} jobs, "
          f"maxlevel {args.maxlevel}, timeout {args.timeout}s, mem cap {args.mem_mb} MB", flush=True)
    if not todo:
        return

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="halo_")
    lock = threading.Lock()
    counts = collections.Counter()
    best = []
    t0 = time.monotonic()
    with open(args.out, "a") as outfh, ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(run_one, args.sat, ln, args.maxlevel, args.timeout, args.mem_mb, workdir): (key, ln)
                for key, ln in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            key, ln = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:  # keep going no matter what
                rec = {"status": "error", "hc": None, "hh": None, "stderr": repr(exc)}
            grid = ln.split()[0].rstrip("?")
            row = {"key": key, "shape": ln, "grid": grid, "cells": (len(ln.split()) - 1) // 2,
                   "generator": args.generator, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            record = rec.pop("record", None)
            row.update(rec)
            if row["status"] == "nontiler" and row["hc"] is not None and row["hc"] >= args.witness_min_hc:
                row["witness"] = record
                best.append((row["hc"], ln))
            counts[row["status"] if row["status"] != "nontiler" else f"nontiler hc={row['hc']}"] += 1
            with lock:
                outfh.write(json.dumps(row) + "\n")
                outfh.flush()
            if i % 500 == 0 or i == len(todo):
                rate = i / (time.monotonic() - t0)
                print(f"  {i}/{len(todo)}  {rate:.1f} shapes/s  " +
                      ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())), flush=True)
    try:
        os.rmdir(workdir)
    except OSError:
        pass
    print(f"done in {time.monotonic() - t0:.1f} s")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    for hc, ln in sorted(best, reverse=True)[:10]:
        print(f"  hc={hc}: {ln}")


if __name__ == "__main__":
    main()
