#!/usr/bin/env python3
"""HALO periodic tiling detector for polyforms on the square (O) and hex (H) grids.

Idea. A shape tiles the plane periodically if and only if, for some full-rank sublattice
L of Z^2, copies of the shape (in any grid orientation) exactly partition the finite
torus Z^2 / L. Every sublattice of index N has a unique basis {(a, 0), (b, d)} with
a * d = N and 0 <= b < a. We try N = t * area for t = 1..max_t, and for each such lattice
solve an exact-cover problem (Knuth's Algorithm X). A solution lifts to a periodic tiling
of the plane, which proves the shape tiles. Such a shape has infinite Heesch number and
can never be a record candidate.

Why: heesch-sat proves isohedral tilings but not anisohedral ones, which it reports as
"inconclusive" after building coronas to the max level. Those checks cost 10-60 s and
gigabytes each, about half of all compute in M1 measurements. Running this detector on
shapes that are slow in heesch-sat removes most of that cost.

Guarantees: a returned tiling is always verified by `verify()` before it's reported, so
"tiles" is a proof. "not found" only means no periodic tiling with at most max_t tiles
per period was found within the budget.

CLI:
  python3 halo/periodic.py FILE [--max-t 24] [--budget 30]
FILE holds bare shape lines (one per line). Prints one result line per shape.
"""
import argparse
import math
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import shape as shp  # noqa: E402


class Budget(Exception):
    pass


def orientations(grid, cells):
    """Distinct images of the shape under grid point symmetries, each normalized to min corner."""
    seen, out = set(), []
    for a, b, d, e in shp.SYMMETRIES[grid]:
        pts = [(a * x + b * y, d * x + e * y) for x, y in cells]
        mx = min(x for x, _ in pts)
        my = min(y for _, y in pts)
        key = tuple(sorted((x - mx, y - my) for x, y in pts))
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def lattices(n):
    """All sublattices of Z^2 of index n, as (a, b, d) for basis {(a,0), (b,d)}."""
    for a in range(1, n + 1):
        if n % a:
            continue
        d = n // a
        for b in range(a):
            yield a, b, d


def _egcd(p, q):
    if q == 0:
        return (abs(p), 1 if p >= 0 else -1, 0)
    g, s, t = _egcd(q, p % q)
    return g, t, s - (p // q) * t


def hnf(v1, v2):
    """Basis (a, b, d) in our normal form for the lattice spanned by integer vectors v1, v2."""
    (x1, y1), (x2, y2) = v1, v2
    det = abs(x1 * y2 - x2 * y1)
    dd, s, t = _egcd(y1, y2)
    a = det // dd
    wx = s * x1 + t * x2
    return a, wx % a, dd


def unique_lattices(n, grid):
    """Sublattices of index n up to the grid's point symmetries (the tiling problem is invariant)."""
    mats = shp.SYMMETRIES[grid]
    for a, b, d in lattices(n):
        best = (a, b, d)
        for m00, m01, m10, m11 in mats:
            v1 = (m00 * a, m10 * a)
            v2 = (m00 * b + m01 * d, m10 * b + m11 * d)
            cand = hnf(v1, v2)
            if cand < best:
                best = cand
                break
        if best == (a, b, d):
            yield a, b, d


def reduce_mod(x, y, a, b, d):
    k = y // d
    y -= k * d
    x -= k * b
    return x % a, y


def placements(orients, a, b, d):
    """Distinct placements (frozensets of torus cell indices) of all orientations."""
    seen, rows = set(), []
    for o in orients:
        for ty in range(d):
            for tx in range(a):
                idx = []
                for x, y in o:
                    rx, ry = reduce_mod(x + tx, y + ty, a, b, d)
                    idx.append(ry * a + rx)
                fs = frozenset(idx)
                if len(fs) != len(idx) or fs in seen:   # self-overlap on the torus, or duplicate
                    continue
                seen.add(fs)
                rows.append((fs, (o, tx, ty)))
    return rows


def exact_cover(ncols, rows, deadline, node_limit):
    """Algorithm X with the minimum-remaining-values heuristic. Returns list of row indices or None."""
    X = {c: set() for c in range(ncols)}
    for i, (fs, _) in enumerate(rows):
        for c in fs:
            X[c].add(i)
    if any(not s for s in X.values()):
        return None
    Y = [fs for fs, _ in rows]
    sol, nodes = [], [0]

    def select(r):
        cols = []
        for j in Y[r]:
            for i in X[j]:
                for k in Y[i]:
                    if k != j:
                        X[k].discard(i)
            cols.append(X.pop(j))
        return cols

    def deselect(r, cols):
        for j in reversed(list(Y[r])):
            X[j] = cols.pop()
            for i in X[j]:
                for k in Y[i]:
                    if k != j:
                        X[k].add(i)

    def search():
        if not X:
            return True
        nodes[0] += 1
        if nodes[0] % 2000 == 0 and (time.monotonic() > deadline or nodes[0] > node_limit):
            raise Budget()
        c = min(X, key=lambda col: len(X[col]))
        for r in list(X[c]):
            sol.append(r)
            cols = select(r)
            if search():
                return True
            deselect(r, cols)
            sol.pop()
        return False

    return list(sol) if search() else None


def verify(cells_orients_used, a, b, d, area):
    """Check that the chosen placements partition the torus exactly."""
    covered = [0] * (a * d)
    for fs in cells_orients_used:
        for c in fs:
            covered[c] += 1
    return all(v == 1 for v in covered) and len(cells_orients_used) * area == a * d


def find_periodic_tiling(line, max_t=24, budget=30.0, node_limit=2_000_000):
    """Returns (status, info). status in {"tiles", "not_found", "budget", "unsupported"}."""
    grid, cells = shp.parse(line)
    if grid not in shp.SYMMETRIES:
        return "unsupported", {}
    area = len(cells)
    orients = orientations(grid, cells)
    deadline = time.monotonic() + budget
    tried = 0
    try:
        for t in range(1, max_t + 1):
            n = t * area
            for a, b, d in unique_lattices(n, grid):
                if time.monotonic() > deadline:
                    raise Budget()
                rows = placements(orients, a, b, d)
                if len(rows) < t:
                    continue
                tried += 1
                sol = exact_cover(n, rows, deadline, node_limit)
                if sol is not None:
                    used = [rows[i][0] for i in sol]
                    if not verify(used, a, b, d, area):
                        raise AssertionError("exact cover returned an invalid tiling")
                    return "tiles", {"t": t, "lattice": [[a, 0], [b, d]], "tried": tried,
                                     "orientations_used": len({rows[i][1][0] for i in sol}),
                                     "placements": [rows[i][1] for i in sol]}
    except Budget:
        return "budget", {"tried": tried, "t_reached": t}
    return "not_found", {"tried": tried, "max_t": max_t}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--shape", help="check one shape line instead of a file")
    ap.add_argument("--json", action="store_true", help="with --shape: print one JSON object")
    ap.add_argument("--max-t", type=int, default=24)
    ap.add_argument("--budget", type=float, default=30.0)
    args = ap.parse_args()
    if args.shape:
        import json
        t0 = time.monotonic()
        status, info = find_periodic_tiling(args.shape, args.max_t, args.budget)
        info["status"] = status
        info["seconds"] = round(time.monotonic() - t0, 3)
        if args.json:
            info["placements"] = [[list(map(list, o)), tx, ty] for o, tx, ty in info.get("placements", [])]
            print(json.dumps(info))
        else:
            info.pop("placements", None)
            print(status, info)
        return
    if not args.file:
        sys.exit("give FILE or --shape")
    with open(args.file) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln or not ln[0].isalpha() or ln[0] in "~!#$":
                continue
            t0 = time.monotonic()
            status, info = find_periodic_tiling(ln, args.max_t, args.budget)
            info.pop("placements", None)
            print(f"{status:10s} {time.monotonic() - t0:7.2f}s {info}  {ln}")


if __name__ == "__main__":
    main()
