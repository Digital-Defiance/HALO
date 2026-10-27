#!/usr/bin/env python3
"""Exact cell/span screen for unmarked straight hexagon-chain bodies in grid I.

This is not Mann's marked tile: no tabs/notches are realized here. Each regular
hexagon of side s is decomposed into 6*s*s unit equilateral triangles. Triangle
centres use heesch-sat's sparse I coordinates. Screen the body before designing
markings; alternate grids or redesigned macro geometry require separate checks.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "halo"))
import shape


def hexagon(side, centre=(2, -1)):
    if side < 1:
        raise ValueError("side must be positive")
    cx, cy = centre
    radius = 3 * side
    cells = set()
    for x in range(cx - radius, cx + radius + 1):
        for y in range(cy - radius, cy + radius + 1):
            kind = x % 3
            if kind not in (0, 1) or y % 3 != kind:
                continue
            offsets = [(-1, -1), (-1, 2), (2, -1)] if kind == 0 else [(1, 1), (-2, 1), (1, -2)]
            if all(max(abs(x + dx - cx), abs(y + dy - cy),
                       abs(x + dx - cx + y + dy - cy)) <= radius for dx, dy in offsets):
                cells.add((x, y))
    return cells


def screen(length, side):
    if length < 1:
        raise ValueError("length must be positive")
    body = set().union(*(hexagon(side, (2 + i * 3 * side, -1 + i * 3 * side)) for i in range(length)))
    expected = 6 * length * side * side
    if len(body) != expected:
        raise ValueError("unexpected overlap or missing triangle cells")
    # I grid symmetries have the same twelve linear parts as H, with some
    # affine offsets. Offsets do not change bounding-box spans.
    sums = []
    for a, b, d, e in shape.SYMMETRIES["H"]:
        pts = [(a * x + b * y, d * x + e * y) for x, y in body]
        sx, sy = shape.spans(pts)
        sums.append(sx + sy)
    best = min(sums)
    return {"hexagons": length, "triangle_side": side, "cells": len(body),
            "best_span_sum_minmax": best, "best_span_sum_extent": best + 2,
            "body_within_cell_limit": len(body) <= 200,
            "body_within_span_limit": best <= 29,
            "body_within_strict_span_limit": best + 2 <= 29,
            "markings_included": False}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--length", type=int, default=4)
    ap.add_argument("--side", type=int, nargs="+", default=[1, 2, 3])
    args = ap.parse_args()
    print(json.dumps([screen(args.length, side) for side in args.side], indent=2))
