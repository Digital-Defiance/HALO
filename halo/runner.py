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
import contextlib
import json
import os
import platform
import shutil
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


class MemoryBudget:
    """Cooperative RSS guard for this runner's SAT and defect processes.

    Only a selected process stops itself, so pressure does not make every
    worker kill its solver at once. Low-priority defect work goes first, then
    ordinary checks, preserving larger-budget retries where possible. This is
    sampled admission/termination control, not an OS-enforced hard RAM limit.
    """
    def __init__(self, limit_mb, reserve_mb=0, available=None):
        self.limit_mb = limit_mb
        self.reserve_mb = reserve_mb
        self._available = available or self._system_available
        self._available_mb = None
        self._poll_at = float("-inf")
        self._processes = {}
        self._stopping = None
        self._lock = threading.Lock()

    @staticmethod
    def _system_available():
        return psutil.virtual_memory().available / 1e6 if psutil else None

    def register(self, pid, priority=0):
        with self._lock:
            self._processes[pid] = {"rss": 0.0, "priority": priority}

    def unregister(self, pid):
        with self._lock:
            self._processes.pop(pid, None)
            if self._stopping == pid:
                self._stopping = None

    def _pressure(self):
        now = time.monotonic()
        if now - self._poll_at >= 0.1:
            self._poll_at = now
            try:
                self._available_mb = self._available()
            except Exception:
                self._available_mb = None
        if sum(p["rss"] for p in self._processes.values()) > self.limit_mb:
            return "shared-memory-budget"
        if self._available_mb is not None and self._available_mb < self.reserve_mb:
            return "system-memory-reserve"
        return None

    def may_start(self):
        with self._lock:
            return self._stopping is None and self._pressure() is None

    def stop_reason(self, pid, rss):
        with self._lock:
            if pid not in self._processes:
                return None
            if rss is not None:
                self._processes[pid]["rss"] = rss
            reason = self._pressure()
            if reason is None or self._stopping is not None:
                return None
            priority = min(p["priority"] for p in self._processes.values())
            victim = max((i for i, p in self._processes.items() if p["priority"] == priority),
                         key=lambda i: self._processes[i]["rss"])
            if victim == pid:
                self._stopping = pid
                return reason
            return None


MEMORY_BUDGET = None


@contextlib.contextmanager
def use_memory_budget(budget):
    global MEMORY_BUDGET
    previous = MEMORY_BUDGET
    MEMORY_BUDGET = budget
    try:
        yield
    finally:
        MEMORY_BUDGET = previous


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
        out = subprocess.run([shutil.which("ps") or "ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True, close_fds=False).stdout.strip()
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


def ensure_jsonl_boundary(path):
    """Preserve an interrupted final fragment, but don't append a record onto it."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb") as fh:
        if fh.read(128).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValueError(f"{path} is a Git LFS pointer; run git lfs pull before resuming")
        fh.seek(-1, os.SEEK_END)
        last = fh.read(1)
    if last != b"\n":
        with open(path, "a") as fh:
            fh.write("\n")


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


def run_one(sat, line, maxlevel, timeout, mem_mb, workdir, hh=False):
    fd, inp = tempfile.mkstemp(suffix=".txt", dir=workdir)
    with os.fdopen(fd, "w") as fh:
        fh.write(line + "\n")
    out = inp[:-4] + ".out.txt"
    cmd = [shutil.which(sat) or sat, "-isohedral", "-show", "-maxlevel", str(maxlevel)] + (["-hh"] if hh else []) + [inp, "-o", out]
    start = time.monotonic()
    # Python-created descriptors are non-inheritable. Keeping close_fds=False
    # enables posix_spawn on macOS instead of fork's OpenBLAS atfork handlers,
    # which can deadlock against a concurrently running NumPy scorer.
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, close_fds=False)
    budget = MEMORY_BUDGET
    if budget:
        budget.register(proc.pid, priority=mem_mb)
    peak = 0.0
    stop = None
    limit_reason = None
    while proc.poll() is None:
        r = rss_mb(proc.pid)
        if r is not None:
            peak = max(peak, r)
            if r > mem_mb:
                stop = "memout"
                limit_reason = "per-process-memory"
                proc.kill()
                break
        if budget:
            limit_reason = budget.stop_reason(proc.pid, r)
            if limit_reason:
                stop = "memout"
                proc.kill()
                break
        if time.monotonic() - start > timeout:
            stop = "timeout"
            proc.kill()
            break
        # wait() notices quick exits without imposing a 50 ms floor per shape.
        # Long solves retain the same RSS/timeout polling cadence.
        remaining = timeout - (time.monotonic() - start)
        interval = 0.05 if time.monotonic() - start < 1 else 0.25
        try:
            proc.wait(timeout=max(0.001, min(interval, remaining)))
        except subprocess.TimeoutExpired:
            pass
    proc.wait()
    if budget:
        budget.unregister(proc.pid)
    secs = time.monotonic() - start
    stderr = proc.stderr.read().decode(errors="replace")[-500:] if proc.stderr else ""
    if proc.stderr:
        proc.stderr.close()
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
    if limit_reason:
        rec["limit_reason"] = limit_reason
    return rec


DEFAULT_DEFECT = os.path.join(ROOT, "build", platform.system(), "heesch-sat-defect", "defect")


def run_defect(line, hc, hh, timeout=120.0, mem_mb=6000.0, confl=500000, max_d=64, binary=DEFAULT_DEFECT):
    """How close a non-tiler with Heesch number hc comes to an (hc+1)-corona: the fewest
    cells next to an hc-patch that an (hc+1)-corona leaves uncovered (heesch-sat patched
    by scripts/setup_heesch_sat.sh; see third_party/heesch-sat/defect.cpp). Returns
    {"defect": d or None, "ring": r, "defect_exact": bool, "defect_seconds": t, "defect_stop": ...}."""
    if not os.access(binary, os.X_OK):
        return {"defect": None, "defect_stop": "no-binary"}
    grid = line.split()[0].rstrip("?")
    record = f"{grid} {' '.join(line.split()[1:])}\n~ {hc} {hh} 0\n"
    cmd = [binary, "-maxd", str(max_d), "-confl", str(confl)]
    start = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, close_fds=False)
    budget = MEMORY_BUDGET
    if budget:
        budget.register(proc.pid, priority=-1)  # enrichment yields before classification
    out_box = {}

    def feed():
        try:
            out_box["out"] = proc.communicate(record)[0]
        except Exception:
            out_box["out"] = ""
    t = threading.Thread(target=feed, daemon=True)
    t.start()
    stop, peak, limit_reason = None, 0.0, None
    while t.is_alive():
        r = rss_mb(proc.pid)
        if r is not None:
            peak = max(peak, r)
            if r > mem_mb:
                stop = "memout"
                limit_reason = "per-process-memory"
                proc.kill()
                break
        if budget:
            limit_reason = budget.stop_reason(proc.pid, r)
            if limit_reason:
                stop = "memout"
                proc.kill()
                break
        if time.monotonic() - start > timeout:
            stop = "timeout"
            proc.kill()
            break
        t.join(0.25)
    t.join(5)
    if budget:
        budget.unregister(proc.pid)
    secs = round(time.monotonic() - start, 3)
    rec = {"defect": None, "ring": None, "defect_exact": False, "defect_seconds": secs,
           "defect_peak_rss_mb": round(peak, 1), "defect_stop": stop}
    if limit_reason:
        rec["defect_limit_reason"] = limit_reason
    if stop:
        return rec
    try:
        info = json.loads(out_box.get("out", "").strip().splitlines()[-1])
    except Exception:
        rec["defect_stop"] = "error"
        return rec
    if info.get("defect", -1) >= 0:
        rec.update({"defect": info["defect"], "ring": info["ring"], "defect_exact": bool(info.get("exact"))})
    else:
        rec["defect_stop"] = "over-maxd"
    return rec


PERIODIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "periodic.py")
PERIODIC_DLX = os.path.join(ROOT, "build", platform.system(), "periodic_dlx")


def run_periodic(line, budget, max_t):
    """Run the periodic tiling detector in its own process (keeps the GIL out of the way).
    Uses the C++ build (50-140x faster) when present, else the Python reference."""
    if os.access(PERIODIC_DLX, os.X_OK):
        cmd = [PERIODIC_DLX, line, str(max_t), str(budget)]
    else:
        cmd = [sys.executable, PERIODIC, "--shape", line, "--json", "--budget", str(budget), "--max-t", str(max_t)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=budget + 60, close_fds=False).stdout
        info = json.loads(out.strip().splitlines()[-1])
    except Exception as exc:
        return {"status": "error", "error": repr(exc)[:200]}
    if info.get("status") == "tiles":
        info.pop("placements", None)  # keep records small; rerun periodic.py --shape to get the tiling
    return info


UNSETTLED = ("timeout", "memout", "inconclusive")


def classify(line, opts, workdir):
    """Full checking ladder for one shape. `opts` needs: sat, maxlevel, timeout, timeout_long,
    mem_mb, periodic_budget, periodic_quick, periodic_max_t (e.g. the runner's argparse args).
    Ladder: quick heesch-sat -> quick periodic probe -> long heesch-sat -> long periodic probe."""
    start = time.monotonic()
    rec = _classify(line, opts, workdir)
    # Preserve seconds (last SAT attempt) for old consumers; account for every
    # SAT/periodic stage separately when comparing generators' actual cost.
    rec["total_seconds"] = round(time.monotonic() - start, 4)
    return rec


def evaluation_seconds(rec):
    """Elapsed worker time including all ladder stages, retry and defect scoring.

    Historical rows without total_seconds provide only a lower bound.
    """
    first = rec.get("retried_from") or {}
    return (float(rec.get("total_seconds", rec.get("seconds")) or 0.0)
            + float(rec.get("defect_seconds") or 0.0)
            + float(first.get("total_seconds", first.get("seconds")) or 0.0))


def _classify(line, opts, workdir):
    def periodic_stage(rec, budget):
        p = run_periodic(line, budget, opts.periodic_max_t)
        rec["periodic"] = p
        if p.get("status") == "tiles":
            rec["heesch_status"] = rec["status"]
            rec["status"] = "periodic"
            return True
        return False

    hh = getattr(opts, "hh", False)
    rec = run_one(opts.sat, line, opts.maxlevel, opts.timeout, opts.mem_mb, workdir, hh)
    grid = line.split()[0].rstrip("?")
    if rec["status"] not in UNSETTLED:
        return rec
    periodic_enabled = opts.periodic_budget > 0 and grid in ("O", "H")
    if periodic_enabled and periodic_stage(rec, min(opts.periodic_quick, opts.periodic_budget)):
        return rec
    if rec["status"] == "timeout" and opts.timeout_long > opts.timeout:
        quick = rec
        rec = run_one(opts.sat, line, opts.maxlevel, opts.timeout_long, opts.mem_mb, workdir, hh)
        rec["quick"] = {k: quick.get(k) for k in ("status", "seconds", "periodic")}
        if rec["status"] not in UNSETTLED:
            return rec
    if periodic_enabled and opts.periodic_budget > opts.periodic_quick:
        periodic_stage(rec, opts.periodic_budget)
    # heesch-sat's "inconclusive" allows holed coronas (SPEC §6): a shape that reaches maxlevel
    # with holes may still have a small hole-free Heesch number. With no periodic tiling found,
    # it is a candidate, so re-check it at a higher maxlevel.
    esc = getattr(opts, "escalate_maxlevel", 0)
    if rec["status"] == "inconclusive" and esc > opts.maxlevel:
        first = rec
        rec = run_one(opts.sat, line, esc, max(opts.timeout_long, opts.timeout), opts.mem_mb, workdir, hh)
        rec["escalated_from"] = {k: first.get(k) for k in ("status", "maxlevel", "seconds", "periodic")}
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
    ap.add_argument("--periodic-budget", type=float, default=0.0,
                    help="seconds for the periodic tiling detector on shapes heesch-sat could not "
                         "settle (timeout, memout, inconclusive); 0 = off. Proven tilers get status 'periodic'")
    ap.add_argument("--periodic-max-t", type=int, default=24, help="max tiles per period to try")
    ap.add_argument("--escalate-maxlevel", type=int, default=0,
                    help="if > --maxlevel: re-check shapes still inconclusive after the periodic probes "
                         "at this maxlevel (inconclusive can hide small hole-free Heesch numbers)")
    ap.add_argument("--hh", action="store_true",
                    help="also compute Hh (outer corona may have holes), as in Kaplan's tables; Epoch only uses Hc")
    ap.add_argument("--periodic-quick", type=float, default=5.0,
                    help="budget for the quick periodic probe right after the first heesch-sat attempt")
    ap.add_argument("--timeout-long", type=float, default=0.0,
                    help="if > --timeout: retry heesch-sat with this timeout when the quick probe finds no tiling")
    args = ap.parse_args()

    if not os.access(args.sat, os.X_OK):
        sys.exit(f"checker not found at {args.sat}; run scripts/setup_heesch_sat.sh")

    ensure_jsonl_boundary(args.out)
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
        futs = {pool.submit(classify, ln, args, workdir): (key, ln) for key, ln in todo}
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
