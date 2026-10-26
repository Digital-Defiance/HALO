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
    if grid not in NEIGHBOURS:
        raise KeyError(grid)
    x0 = min(x for x, _ in cells) - 1
    y0 = min(y for _, y in cells) - 1
    width = max(x for x, _ in cells) - x0 + 2
    height = max(y for _, y in cells) - y0 + 2
    # Flood all exterior cells together in a bitboard. The extra border is empty
    # and connected; masking columns prevents shifts wrapping between rows.
    full = (1 << (width * height)) - 1
    left = full // ((1 << width) - 1)
    right = left << (width - 1)
    row = (1 << width) - 1
    occupied = 0
    for x, y in cells:
        occupied |= 1 << ((y - y0) * width + x - x0)
    empty = full ^ occupied
    seen = left | right | row | (row << (width * (height - 1)))
    while True:
        neighbours = ((seen & ~left) >> 1) | ((seen & ~right) << 1)
        neighbours |= (seen >> width) | (seen << width)
        if grid == "H":
            neighbours |= ((seen & ~right) >> (width - 1)) | ((seen & ~left) << (width - 1))
        expanded = (seen | neighbours) & empty
        if expanded == seen:
            return seen != empty
        seen = expanded


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
    return check_cells(grid, cells, max_cells, max_span_sum)


def check_cells(grid, cells, max_cells=200, max_span_sum=29):
    """Constraint checks for already parsed cells (the search's hot path)."""
    problems = []
    if not cells:
        return False, ["empty shape"], {"grid": grid, "cells": 0}
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
