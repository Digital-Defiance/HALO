#!/usr/bin/env python3
"""Experimental inverse tile design in fixed or locally widened partial coronas.

One occupancy variable describes each possible tile cell and is shared by every
copy. SAT enforces disjointness and enclosure through the target corona. Global
tile/patch geometry is independently checked; invalid models are blocked lazily.
This proposes shapes, never infers non-tiling from SAT-model failure or a timeout.

Input: JSONL from runner.run_defect(..., include_patch=True), or bare patch objects.
Output: append-only JSONL recording bounded experiments and classifications.
Requires the CryptoMiniSat command-line solver in addition to heesch-sat.
"""
import argparse
import collections
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner
import shape as shp
import verify


def transform(T, p):
    a, b, c, d, e, f = T
    x, y = p
    return a * x + b * y + c, d * x + e * y + f


def unpack_patch(record):
    patch = record.get("defect_patch", record.get("patch", record))
    grid = patch["grid"]
    if grid not in verify.TOUCH:
        raise ValueError("inverse repair supports O and H grids")
    cells = [tuple(p) for p in patch["cells"]]
    placements = [tuple(p) for p in patch["placements"]]
    target = patch["level"]
    if type(target) is not int or target < 1:
        raise ValueError("target level must be a positive integer")
    if (not cells or any(len(p) != 2 or any(type(v) is not int for v in p) for p in cells)
            or len(set(cells)) != len(cells)):
        raise ValueError("invalid or duplicate tile cells")
    if not placements or any(len(p) != 7 or any(type(v) is not int for v in p) for p in placements):
        raise ValueError("placements must contain level and six integer transform entries")
    if [p[0] for p in placements].count(0) != 1:
        raise ValueError("expected exactly one central copy")
    if set(p[0] for p in placements) != set(range(target + 1)):
        raise ValueError("missing or out-of-range corona levels")
    for level, a, b, c, d, e, f in placements:
        if (a, b, d, e) not in shp.SYMMETRIES[grid]:
            raise ValueError("placement matrix is not a grid symmetry")
    return grid, cells, placements, target


def witness_text(grid, cells, placements, level):
    copies = [p for p in placements if p[0] <= level]
    return (shp.fmt(grid, cells) + f"\n~ {level} {level} 1\n{len(copies)}\n"
            + "".join(f"{p[0]} <{','.join(map(str, p[1:]))}>\n" for p in copies))


def analyze_patch(record):
    """Recompute counts from explicit cells; do not trust the C++ summary."""
    grid, cells, placements, target = unpack_patch(record)
    occupied, copies = {}, []
    for i, placement in enumerate(placements):
        level, *T = placement
        image = {transform(T, p) for p in cells}
        for p in image:
            if p in occupied:
                raise ValueError(f"copies overlap at {p}")
            occupied[p] = level
        copies.append(image)
    inner = {p for p, level in occupied.items() if level < target}
    required = {(x + dx, y + dy) for placement, image in zip(placements, copies)
                if placement[0] == target - 1 for x, y in image
                for dx, dy in verify.TOUCH[grid]} - inner
    uncovered = required - occupied.keys()
    patch = record.get("defect_patch", record.get("patch", record))
    for name, calculated in (("required", required), ("uncovered", uncovered)):
        if name in patch and (len(patch[name]) != len(calculated)
                              or set(map(tuple, patch[name])) != calculated):
            raise ValueError(f"exported {name} cells do not match geometry")
    for name, expected in (("defect", len(uncovered)), ("ring", len(required))):
        if record.get(name) is not None and record[name] != expected:
            raise ValueError(f"reported {name} does not match geometry")
    valid, message = verify.verify(witness_text(grid, cells, placements, target - 1))
    return {"defect": len(uncovered), "ring": len(required),
            "uncovered": sorted(uncovered), "inner_verified": valid,
            "inner_message": message, "copies": len(placements), "target": target}


class CNF:
    def __init__(self):
        self.nvars = 0
        self.clauses = []
        self._seen = set()

    def variable(self):
        self.nvars += 1
        return self.nvars

    def add(self, literals):
        clause = set(literals)
        if any(-x in clause for x in clause):
            return
        clause = tuple(sorted(clause))
        if clause not in self._seen:
            self._seen.add(clause)
            self.clauses.append(clause)

    def at_most(self, literals, limit):
        """Capped totalizer; literals may be signed (e.g. deleted original cells)."""
        if limit < 0:
            self.add([])
            return
        if limit >= len(literals):
            return
        if limit == 0:
            for x in literals:
                self.add([-x])
            return
        layer = [[x] for x in literals]
        while len(layer) > 1:
            merged = []
            for i in range(0, len(layer) - 1, 2):
                a, b = layer[i:i + 2]
                out = [self.variable() for _ in range(min(limit + 1, len(a) + len(b)))]
                for ia in range(len(a) + 1):
                    for ib in range(len(b) + 1):
                        if ia + ib:
                            cl = ([-a[ia - 1]] if ia else []) + ([-b[ib - 1]] if ib else [])
                            self.add(cl + [out[min(ia + ib, len(out)) - 1]])
                merged.append(out)
            if len(layer) % 2:
                merged.append(layer[-1])
            layer = merged
        self.add([-layer[0][limit]])

    def write(self, path):
        with open(path, "w") as f:
            f.write(f"p cnf {self.nvars} {len(self.clauses)}\n")
            for cl in self.clauses:
                f.write(" ".join(map(str, cl)) + " 0\n")

    def satisfied_by(self, positive):
        return all(any((x in positive) if x > 0 else (-x not in positive) for x in cl)
                   for cl in self.clauses)


class RepairModel:
    def __init__(self, record, edits, radius=1, min_cells=1, max_cells=200,
                 freeze_interior=True, require_change=True, outer_shifts=0,
                 shift_from_level=None):
        grid, cells, placements, target = unpack_patch(record)
        if edits < 0 or radius not in (0, 1, 2) or outer_shifts not in (0, 1):
            raise ValueError("invalid edit budget, cell radius or outer shifts")
        if not 1 <= min_cells <= max_cells <= 200:
            raise ValueError("need 1 <= min_cells <= max_cells <= 200")
        shift_from_level = target if shift_from_level is None else shift_from_level
        if not 1 <= shift_from_level <= target:
            raise ValueError("moving levels must exclude the central copy")
        self.grid, self.original, self.target = grid, set(cells), target
        self.cnf = cnf = CNF()
        possible = set(cells)
        for _ in range(radius):
            possible |= {(x + dx, y + dy) for x, y in possible for dx, dy in shp.NEIGHBOURS[grid]}
        self.variables = {p: cnf.variable() for p in sorted(possible)}
        changed = [-v if p in self.original else v for p, v in self.variables.items()]
        cnf.at_most(changed, edits)
        if require_change:
            cnf.add(changed)
        cnf.at_most(list(self.variables.values()), max_cells)
        cnf.at_most([-v for v in self.variables.values()], len(possible) - min_cells)
        core = {p for p in cells if all((p[0] + dx, p[1] + dy) in self.original
                                       for dx, dy in shp.NEIGHBOURS[grid])}
        if freeze_interior:
            # At least one fixed occupied cell prevents the empty-tile escape.
            for p in core or {min(self.original)}:
                cnf.add([self.variables[p]])
        self.placements = []  # (seven-entry placement, selector or 0 for mandatory)
        outer = set()
        for p in placements:
            if p[0] < shift_from_level or not outer_shifts:
                self.placements.append((p, 0))
            else:
                for dx, dy in [(0, 0)] + shp.NEIGHBOURS[grid]:
                    q = list(p)
                    q[3] += dx
                    q[6] += dy
                    outer.add(tuple(q))
        for p in sorted(outer):
            self.placements.append((p, cnf.variable()))
        self.decisions = list(self.variables.values()) + [s for _, s in self.placements if s]
        occupied = collections.defaultdict(list)
        images = []
        for i, (placement, selector) in enumerate(self.placements):
            level, *T = placement
            image = {}
            for p, v in self.variables.items():
                literal = v
                if selector:
                    literal = cnf.variable()
                    cnf.add([-literal, v])
                    cnf.add([-literal, selector])
                    cnf.add([-v, -selector, literal])
                q = transform(T, p)
                occupied[q].append((i, literal, level))
                image[q] = literal
            images.append(image)
        for occurrences in occupied.values():
            for (i, v, _), (j, w, _) in itertools.combinations(occurrences, 2):
                if i != j:
                    cnf.add([-v, -w])
        contacts = {}
        for (placement, selector), image in zip(self.placements, images):
            level = placement[0]
            if level == 0:
                continue
            choices = set()
            for (x, y), v in image.items():
                for dx, dy in verify.TOUCH[grid]:
                    for _, w, lev in occupied.get((x + dx, y + dy), ()):
                        if lev != level - 1:
                            continue
                        if v == w:
                            choices.add(v)
                        else:
                            key = tuple(sorted((v, w)))
                            if key not in contacts:
                                t = contacts[key] = cnf.variable()
                                cnf.add([-t, v])
                                cnf.add([-t, w])
                                cnf.add([-v, -w, t])
                            choices.add(contacts[key])
            cnf.add(([-selector] if selector else []) + list(choices))
        # Enclose each inner copy at the next prefix level. Later copies cannot
        # fill a hole retroactively in an earlier corona.
        for (placement, _), image in zip(self.placements, images):
            level = placement[0]
            if level >= target:
                continue
            for (x, y), literal in image.items():
                for dx, dy in verify.TOUCH[grid]:
                    covering = [v for _, v, lev in occupied.get((x + dx, y + dy), ()) if lev <= level + 1]
                    cnf.add([-literal] + covering)

    def decode(self, positive):
        cells = sorted(p for p, v in self.variables.items() if v in positive)
        placements = [p for p, selector in self.placements if not selector or selector in positive]
        return cells, placements

    def block(self, positive, shape_only=False):
        decisions = list(self.variables.values()) if shape_only else self.decisions
        self.cnf.add([-v if v in positive else v for v in decisions])


def solve_cnf(cnf, solver="cryptominisat5", timeout=120, mem_mb=20000, reserve_mb=8000):
    """Run one CLI solver with external wall/RSS/headroom caps and full model checks."""
    solver = shutil.which(solver)
    if not solver:
        raise ValueError("CryptoMiniSat CLI not found")
    if timeout <= 0 or mem_mb <= 0 or reserve_mb < 0:
        raise ValueError("invalid solver limits")
    budget = runner.MemoryBudget(mem_mb, reserve_mb)
    if not budget.may_start():
        return {"status": "memory-pressure", "seconds": 0.0}
    start, peak, stopped = time.monotonic(), None, None
    with tempfile.TemporaryDirectory(prefix="halo-repair-") as d:
        path = os.path.join(d, "model.cnf")
        cnf.write(path)
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with open(os.path.join(d, "stdout"), "w+") as stdout, open(os.path.join(d, "stderr"), "w+") as stderr:
            proc = subprocess.Popen([solver, "--threads", "1", "--verb", "0", "--maxtime", str(timeout), path],
                                    stdout=stdout, stderr=stderr, close_fds=False)
            budget.register(proc.pid, priority=mem_mb)
            try:
                while proc.poll() is None:
                    rss = runner.rss_mb(proc.pid)
                    if rss is not None and rss > 0:
                        peak = max(peak or 0.0, rss)
                        if rss > mem_mb:
                            stopped = "memout"
                    if not stopped and budget.stop_reason(proc.pid, rss):
                        stopped = "memory-pressure"
                    if not stopped and time.monotonic() - start > timeout:
                        stopped = "timeout"
                    if stopped:
                        proc.kill()
                        break
                    try:
                        proc.wait(timeout=min(0.1, timeout))
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                budget.unregister(proc.pid)
            stdout.seek(0)
            output = stdout.read()
            stderr.seek(0)
            errors = stderr.read()[-2000:]
    result = {"status": stopped or "unknown", "seconds": round(time.monotonic() - start, 4),
              "peak_rss_mb": round(peak, 1) if peak is not None else None, "cnf_sha256": digest,
              "variables": cnf.nvars, "clauses": len(cnf.clauses), "returncode": proc.returncode}
    if stopped:
        return result
    statuses = [line.strip() for line in output.splitlines() if line.startswith("s ")]
    if statuses == ["s UNSATISFIABLE"] and proc.returncode == 20:
        result["status"] = "unsat"
    elif statuses == ["s SATISFIABLE"] and proc.returncode == 10:
        model = [int(x) for line in output.splitlines() if line.startswith("v ") for x in line.split()[1:] if int(x)]
        if {abs(v) for v in model} != set(range(1, cnf.nvars + 1)) or len(model) != cnf.nvars:
            raise ValueError("solver returned an incomplete or duplicate assignment")
        positive = {v for v in model if v > 0}
        if not cnf.satisfied_by(positive):
            raise ValueError("solver model does not satisfy the emitted CNF")
        result.update(status="sat", positive=positive)
    elif proc.returncode not in (0, 15):
        result.update(status="solver-error", stderr=errors)
    return result


def validate_candidate(model, cells, placements):
    ok, problems, _ = shp.check_cells(model.grid, cells)
    if not ok or any("stricter" in p for p in problems):
        return False, "tile: " + "; ".join(problems), True
    ok, message = verify.verify(witness_text(model.grid, cells, placements, model.target))
    return ok, message, False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--edit-budgets", default="2,4,6")
    ap.add_argument("--radius", type=int, choices=[0, 1, 2], default=1)
    ap.add_argument("--outer-shifts", type=int, choices=[0, 1], default=0)
    ap.add_argument("--shift-from-level", type=int,
                    help="with --outer-shifts 1, allow local shifts from this level onward; default: last ring")
    ap.add_argument("--free-interior", action="store_true",
                    help="allow original interior cells to change too (minimum cell count still enforced)")
    ap.add_argument("--max-layouts", type=int, default=4)
    ap.add_argument("--max-models", type=int, default=32)
    ap.add_argument("--seconds", type=float, default=3600)
    ap.add_argument("--solve-seconds", type=float, default=120)
    ap.add_argument("--mem-mb", type=float, default=20000)
    ap.add_argument("--reserve-mb", type=float, default=8000)
    ap.add_argument("--min-cells", type=int, default=18)
    ap.add_argument("--max-cells", type=int, default=30)
    ap.add_argument("--solver", default="cryptominisat5")
    ap.add_argument("--sat", default=runner.DEFAULT_SAT)
    args = ap.parse_args()
    edits = [int(x) for x in args.edit_budgets.split(",")]
    if (not edits or any(x < 0 for x in edits) or args.max_layouts < 1 or args.max_models < 1
            or any(not math.isfinite(x) or x <= 0 for x in (args.seconds, args.solve_seconds, args.mem_mb))
            or not math.isfinite(args.reserve_mb) or args.reserve_mb < 0):
        ap.error("invalid pilot limits")
    if Path(args.input).resolve() == Path(args.out).resolve():
        ap.error("input and output must be different files")
    records = []
    with open(args.input) as f:
        for line in f:
            r = json.loads(line)
            if "defect_patch" in r or "patch" in r or "placements" in r:
                records.append(r)
    if not records:
        ap.error("input contains no exported patches")
    runner.ensure_jsonl_boundary(args.out)
    deadline = time.monotonic() + args.seconds
    run_id = uuid.uuid4().hex
    seen = set()
    with open(args.out, "a") as out:
        def log(row):
            row["run_id"] = run_id
            row["generator"] = "inverse-patch-repair"
            row["ts"] = time.time()
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(json.dumps(row), flush=True)

        source_paths = [Path(__file__), Path(runner.__file__), Path(shp.__file__), Path(verify.__file__)]
        log({"event": "pilot-start", "options": vars(args),
             "input_sha256": hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
             "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}})
        for layout, record in enumerate(records[:args.max_layouts]):
            diagnostic = analyze_patch(record)
            grid, cells, _, _ = unpack_patch(record)
            log({"event": "layout", "layout": layout, "parent": shp.canonical(grid, cells), **diagnostic})
            for budget in edits:
                if time.monotonic() >= deadline:
                    log({"event": "stop", "reason": "pilot-budget"})
                    return
                start = time.monotonic()
                model = RepairModel(record, budget, args.radius, args.min_cells, args.max_cells,
                                    freeze_interior=not args.free_interior,
                                    outer_shifts=args.outer_shifts, shift_from_level=args.shift_from_level)
                metadata = {"layout": layout, "edits": budget, "radius": args.radius,
                            "outer_shifts": args.outer_shifts,
                            "shift_from_level": args.shift_from_level,
                            "free_interior": args.free_interior,
                            "build_seconds": round(time.monotonic() - start, 4)}
                for iteration in range(args.max_models):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        log({"event": "stop", "reason": "pilot-budget"})
                        return
                    solved = solve_cnf(model.cnf, args.solver, min(args.solve_seconds, remaining),
                                       args.mem_mb, args.reserve_mb)
                    positive = solved.pop("positive", None)
                    log({"event": "solve", "iteration": iteration, **metadata, **solved})
                    if solved["status"] != "sat":
                        break
                    cells, placements = model.decode(positive)
                    valid, reason, shape_only = validate_candidate(model, cells, placements)
                    if not valid:
                        log({"event": "rejected-model", **metadata, "reason": reason})
                        model.block(positive, shape_only)
                        continue
                    canon = shp.canonical(model.grid, cells)
                    if canon not in seen:
                        seen.add(canon)
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            log({"event": "stop", "reason": "pilot-budget", "unchecked_candidate": canon})
                            return
                        opts = argparse.Namespace(sat=args.sat, maxlevel=12, timeout=min(5, remaining),
                            timeout_long=min(args.solve_seconds, remaining), mem_mb=args.mem_mb,
                            periodic_budget=0, periodic_quick=0, periodic_max_t=24, escalate_maxlevel=0)
                        with tempfile.TemporaryDirectory(prefix="halo-repair-check-") as d, \
                                runner.use_memory_budget(runner.MemoryBudget(args.mem_mb, args.reserve_mb)):
                            classification = runner.classify(canon, opts, d)
                        if classification.get("status") == "nontiler" and classification.get("hc", -1) < model.target:
                            raise RuntimeError("independent witness contradicts checker classification")
                        text = witness_text(model.grid, cells, placements, model.target)
                        log({"event": "candidate", **metadata, "canon": canon,
                             "verified_lower_bound": model.target, "witness": text,
                             "classification": classification})
                    model.block(positive, shape_only=True)
                else:
                    log({"event": "stop-models", **metadata, "reason": "model-budget"})
        log({"event": "pilot-complete", "layouts": min(len(records), args.max_layouts),
             "valid_shapes": len(seen)})


if __name__ == "__main__":
    main()
