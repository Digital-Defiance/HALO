#!/usr/bin/env python3
"""HALO shape utilities: parsing, Epoch constraint checks, canonical forms.

Supported grids for geometry checks: O (square) and H (hex, Kaplan's axial
coordinates with the y axis at 60 degrees). Other grids are parsed, and cell
counts and spans are checked, but connectivity/holes are left to heesch-sat
(which reports holed shapes with status "hole").

CLI:
  python3 halo/shape.py FILE      check every shape line in FILE against SPEC.md §1
"""
import sys

NEIGHBOURS = {
    "O": [(1, 0), (-1, 0), (0, 1), (0, -1)],
    "H": [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)],
}

# Point symmetries of each grid as integer 2x2 matrices (a, b, d, e): x' = a x + b y, y' = d x + e y.
SYMMETRIES = {
    "O": [(1, 0, 0, 1), (0, -1, 1, 0), (-1, 0, 0, -1), (0, 1, -1, 0),
          (-1, 0, 0, 1), (1, 0, 0, -1), (0, 1, 1, 0), (0, -1, -1, 0)],
    # hex axial coords: rotation by 60 degrees is (x, y) -> (x - ... ); generated below
}


def _hex_symmetries():
    rot = (0, -1, 1, 1)      # 60-degree rotation in 60-degree axial coordinates: (x, y) -> (-y, x + y)
    ref = (0, 1, 1, 0)       # reflection swapping the axes
    def mul(m, n):
        a, b, d, e = m
        p, q, r, s = n
        return (a * p + b * r, a * q + b * s, d * p + e * r, d * q + e * s)
    mats, m = [], (1, 0, 0, 1)
    for _ in range(6):
        mats.append(m)
        mats.append(mul(m, ref))
        m = mul(rot, m)
    return mats


SYMMETRIES["H"] = _hex_symmetries()


def parse(line):
    """Return (grid, cells) from a heesch-sat shape line like 'H? 0 0 1 0 ...'."""
    toks = line.split()
    grid = toks[0].rstrip("?")
    nums = list(map(int, toks[1:]))
    if len(nums) % 2:
        raise ValueError("odd number of coordinates")
    return grid, list(zip(nums[0::2], nums[1::2]))


def fmt(grid, cells):
    return grid + " " + " ".join(f"{x} {y}" for x, y in cells)


def spans(cells):
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    return max(xs) - min(xs), max(ys) - min(ys)


def connected(grid, cells):
    nb = NEIGHBOURS[grid]
    s = set(cells)
    stack, seen = [cells[0]], {cells[0]}
    while stack:
        x, y = stack.pop()
        for dx, dy in nb:
            c = (x + dx, y + dy)
            if c in s and c not in seen:
                seen.add(c)
                stack.append(c)
    return len(seen) == len(s)


def has_hole(grid, cells):
    """True if some empty cell is enclosed (not reachable from outside via grid adjacency)."""
    nb = NEIGHBOURS[grid]
    s = set(cells)
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    start = (x0, y0)
    stack, seen = [start], {start}
    while stack:
        x, y = stack.pop()
        for dx, dy in nb:
            c = (x + dx, y + dy)
            if x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and c not in s and c not in seen:
                seen.add(c)
                stack.append(c)
    empty = (x1 - x0 + 1) * (y1 - y0 + 1) - len(s)
    return len(seen) != empty


def canonical(grid, cells):
    """Canonical free form (minimum over grid symmetries and translations). O and H only."""
    best = None
    for a, b, d, e in SYMMETRIES[grid]:
        pts = [(a * x + b * y, d * x + e * y) for x, y in cells]
        mx = min(x for x, _ in pts)
        my = min(y for _, y in pts)
        key = tuple(sorted((x - mx, y - my) for x, y in pts))
        if best is None or key < best:
            best = key
    return fmt(grid, best)


def check(line, max_cells=200, max_span_sum=29):
    """Check a shape against SPEC.md §1. Returns (ok, list_of_problems, info)."""
    grid, cells = parse(line)
    problems = []
    if len(set(cells)) != len(cells):
        problems.append("duplicate cells")
    if len(cells) > max_cells:
        problems.append(f"{len(cells)} cells > {max_cells}")
    sx, sy = spans(cells)
    info = {"grid": grid, "cells": len(cells), "span_x": sx, "span_y": sy,
            "span_sum_minmax": sx + sy, "span_sum_extent": sx + sy + 2}
    if sx + sy > max_span_sum:
        problems.append(f"span (max-min) {sx}+{sy} > {max_span_sum}")
    elif sx + sy + 2 > max_span_sum:
        problems.append(f"warning: span under the stricter reading {sx + 1}+{sy + 1} > {max_span_sum}")
    if grid in NEIGHBOURS:
        if not connected(grid, cells):
            problems.append("not connected")
        if has_hole(grid, cells):
            problems.append("has a hole")
    else:
        info["note"] = "connectivity/holes not checked for this grid"
    ok = not any(not p.startswith("warning") for p in problems)
    return ok, problems, info


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    # Input must be bare shape lines (one shape per line, e.g. `gen` output).
    # Classified heesch-sat files also contain status lines like "I 1 0" that look like shapes.
    bad = 0
    with open(sys.argv[1]) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln or not ln[0].isalpha() or ln[0] in "~!#$":
                continue
            try:
                ok, problems, info = check(ln)
            except ValueError as exc:
                print(f"SKIP {ln[:40]}... ({exc})")
                continue
            bad += not ok
            print(("OK  " if ok else "BAD ") + str(info) + ("  " + "; ".join(problems) if problems else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
