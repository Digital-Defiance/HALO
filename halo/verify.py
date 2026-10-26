#!/usr/bin/env python3
"""HALO independent witness verifier (does not use heesch-sat).

Checks a heesch-sat witness record (the exact text Epoch's verifier accepts):

    GRID x1 y1 ... xn yn
    ~ hc hh P
    N
    level <a,b,c,d,e,f>      (N lines; x' = a x + b y + c, y' = d x + e y + f)

and confirms, from first principles, that it demonstrates hole-free Heesch number >= hc:

  1. the tile is connected and hole-free, and every placement's linear part is a symmetry of
     the grid (so each copy is congruent to the tile);
  2. no two placed copies overlap;
  3. level 0 is a single copy, and levels 1..hc are all present;
  4. for every k = 1..hc, with P_k = union of copies at levels <= k:
       a. every copy at level k touches P_{k-1} (shares an edge or a corner),
       b. P_{k-1} lies in the interior of P_k: every cell sharing an edge or a corner with
          P_{k-1} is covered by P_k,
       c. P_k is a topological disk: connected, no holes, and (square grid) no pinch corners.

Only the first patch is checked (the hole-free one); a second "hh" patch is ignored.
Square (O) and hex (H, Kaplan's axial coordinates) grids are supported.

Usage:
  python3 halo/verify.py WITNESS_FILE [...]
Exit code 0 if every file verifies.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape as shp  # noqa: E402

# cells sharing an edge OR a corner with a cell (for hexes, corner-sharing implies edge-sharing)
TOUCH = {
    "O": [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)],
    "H": shp.NEIGHBOURS["H"],
}


def parse_witness(text):
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    grid, cells = shp.parse(lines[0])
    status = lines[1].split()
    if status[0] != "~":
        raise ValueError(f"not a non-tiler record (status line {lines[1]!r})")
    hc, hh = int(status[1]), int(status[2])
    n = int(lines[3 - 1 + 1]) if False else int(lines[2])
    placements = []
    for ln in lines[3:3 + n]:
        lvl, rest = ln.split(None, 1)
        a, b, c, d, e, f = (int(v) for v in rest.strip().strip("<>").split(","))
        placements.append((int(lvl), (a, b, c, d, e, f)))
    if len(placements) != n:
        raise ValueError(f"expected {n} placements, found {len(placements)}")
    return grid, cells, hc, hh, placements


def no_pinch_square(cells):
    s = set(cells)
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    for x in range(min(xs) - 1, max(xs) + 1):
        for y in range(min(ys) - 1, max(ys) + 1):
            a, b, c, d = (x, y) in s, (x + 1, y) in s, (x, y + 1) in s, (x + 1, y + 1) in s
            if (a and d and not b and not c) or (b and c and not a and not d):
                return False, (x, y)
    return True, None


def verify(text):
    """Returns (ok, message)."""
    grid, cells, hc, hh, placements = parse_witness(text)
    if grid not in TOUCH:
        return False, f"grid {grid} not supported by this verifier"
    if not shp.connected(grid, cells) or shp.has_hole(grid, cells):
        return False, "tile is disconnected or has a hole"
    syms = set(shp.SYMMETRIES[grid])

    owner = {}  # cell -> copy index
    levels = []
    copies = []
    for i, (lvl, (a, b, c, d, e, f)) in enumerate(placements):
        if (a, b, d, e) not in syms:
            return False, f"placement {i} uses a non-symmetry matrix {(a, b, d, e)}"
        img = [(a * x + b * y + c, d * x + e * y + f) for x, y in cells]
        for p in img:
            if p in owner:
                return False, f"copies {owner[p]} and {i} overlap at {p}"
            owner[p] = i
        copies.append(img)
        levels.append(lvl)

    if levels.count(0) != 1:
        return False, f"expected exactly one level-0 copy, found {levels.count(0)}"
    top = max(levels)
    missing = [k for k in range(1, top + 1) if k not in levels]
    if missing:
        return False, f"missing corona levels {missing}"
    if top < hc:
        return False, f"claims hc={hc} but the patch only reaches level {top}"

    touch = TOUCH[grid]
    patch = set(copies[levels.index(0)])
    for k in range(1, hc + 1):
        ring = [copies[i] for i in range(len(copies)) if levels[i] == k]
        for j, img in enumerate(ring):
            if not any((x + dx, y + dy) in patch for x, y in img for dx, dy in touch):
                return False, f"a level-{k} copy (#{j}) does not touch the level-{k - 1} patch"
        new_patch = set(patch)
        for img in ring:
            new_patch.update(img)
        for x, y in patch:
            for dx, dy in touch:
                q = (x + dx, y + dy)
                if q not in new_patch:
                    return False, f"level {k} leaves cell {q} next to the level-{k - 1} patch uncovered"
        cl = sorted(new_patch)
        if not shp.connected(grid, cl):
            return False, f"level-{k} patch is not connected"
        if shp.has_hole(grid, cl):
            return False, f"level-{k} patch has a hole"
        if grid == "O":
            ok, where = no_pinch_square(cl)
            if not ok:
                return False, f"level-{k} patch has a pinch corner at {where}"
        patch = new_patch
    return True, f"verified: hole-free Heesch number >= {hc} ({len(placements)} copies, grid {grid})"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bad = 0
    for path in sys.argv[1:]:
        with open(path) as fh:
            try:
                ok, msg = verify(fh.read())
            except Exception as exc:
                ok, msg = False, f"could not parse: {exc}"
        print(f"{'PASS' if ok else 'FAIL'} {path}: {msg}")
        bad += not ok
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
