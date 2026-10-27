#!/usr/bin/env python3
"""Transfer a certified corona template to a nearby source tile via inverse SAT.

This is a synthesis sketch, not a measured defect patch of the source tile.
The target witness is deliberately supplied in a known-answer control. Recovering
it validates synthesis within that template; it is not a new Heesch discovery.
Optional local placement choices are inherited from patch_repair.RepairModel.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch_repair as repair
import runner
import shape
import verify


def align_cells(grid, source, target):
    """Choose a grid isometry minimizing occupied-cell symmetric difference."""
    target = set(target)
    if not source or not target:
        raise ValueError("cannot align an empty shape")
    best = None
    for a, b, d, e in shape.SYMMETRIES[grid]:
        moved = [(a * x + b * y, d * x + e * y) for x, y in source]
        offsets = {(u - x, v - y) for x, y in moved for u, v in target}
        for dx, dy in offsets:
            image = frozenset((x + dx, y + dy) for x, y in moved)
            key = (len(image ^ target), tuple(sorted(image)))
            if best is None or key < best[0]:
                best = (key, image, (a, b, dx, d, e, dy))
    return sorted(best[1]), best[0][0], best[2]


def make_sketch(parent, witness):
    valid, message = verify.verify(witness)
    if not valid:
        raise ValueError("template failed independent verification: " + message)
    grid, target, hc, _, placements = verify.parse_witness(witness)
    source_grid, cells = shape.parse(parent)
    if source_grid != grid:
        raise ValueError("source and template grids differ")
    aligned, distance, alignment = align_cells(grid, cells, target)
    sketch = {"grid": grid, "cells": aligned, "level": hc,
              "placements": [[level, *T] for level, T in placements if level <= hc]}
    return sketch, {"parent": shape.canonical(grid, cells),
                    "template_tile": shape.canonical(grid, target),
                    "alignment": alignment, "aligned_distance": distance,
                    "target_cells": len(target), "target_level": hc}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent", required=True, help="a bare O/H tile line")
    ap.add_argument("--template", required=True, help="independently verifiable witness file")
    ap.add_argument("--out", required=True, help="append-only control/proposal JSONL")
    ap.add_argument("--edit-budgets", default="2,4,6")
    ap.add_argument("--radius", type=int, choices=[0, 1, 2], default=2)
    ap.add_argument("--outer-shifts", type=int, choices=[0, 1], default=0)
    ap.add_argument("--shift-from-level", type=int)
    ap.add_argument("--seconds", type=float, default=60, help="wall-time cap per SAT solve")
    ap.add_argument("--mem-mb", type=float, default=1000)
    ap.add_argument("--reserve-mb", type=float, default=8000)
    args = ap.parse_args()
    if (any(not math.isfinite(v) or v <= 0 for v in (args.seconds, args.mem_mb))
            or not math.isfinite(args.reserve_mb) or args.reserve_mb < 0):
        ap.error("invalid solver resource limits")
    if Path(args.template).resolve() == Path(args.out).resolve():
        ap.error("template and output must differ")
    text = Path(args.template).read_text()
    sketch, info = make_sketch(args.parent, text)
    budgets = [int(x) for x in args.edit_budgets.split(',')]
    if not budgets or any(b < 0 for b in budgets):
        ap.error("edit budgets must be nonnegative")
    runner.ensure_jsonl_boundary(args.out)
    for edits in budgets:
        model = repair.RepairModel(sketch, edits, radius=args.radius,
            min_cells=info['target_cells'], max_cells=info['target_cells'],
            freeze_interior=False, outer_shifts=args.outer_shifts,
            shift_from_level=args.shift_from_level)
        result = repair.solve_cnf(model.cnf, timeout=args.seconds, mem_mb=args.mem_mb,
                                  reserve_mb=args.reserve_mb)
        positive = result.pop('positive', None)
        row = {"experiment": "corona-template-synthesis", **info, "edits": edits,
               "template": args.template, "template_sha256": hashlib.sha256(text.encode()).hexdigest(),
               "radius": args.radius, "outer_shifts": args.outer_shifts,
               "shift_from_level": args.shift_from_level, "ts": time.time(), **result}
        if positive is not None:
            cells, placements = model.decode(positive)
            valid, message, _ = repair.validate_candidate(model, cells, placements)
            canon = shape.canonical(model.grid, cells)
            row.update(canon=canon, verified_lower_bound=model.target if valid else None,
                       verification_message=message, matches_reference=canon == info['template_tile'])
            if valid:
                row['witness'] = repair.witness_text(model.grid, cells, placements, model.target)
            row['qualification'] = ('Target template supplied; not a discovery. '
                                     'Every proposed tile needs separate non-tiling classification '
                                     'unless it matches an already classified reference.')
        with open(args.out, 'a') as f:
            f.write(json.dumps(row) + '\n')
        print(json.dumps({k: v for k, v in row.items() if k != 'witness'}), flush=True)


if __name__ == '__main__':
    main()
