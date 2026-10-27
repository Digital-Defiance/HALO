#!/usr/bin/env python3
"""Synthesize a tile and a withheld outer corona from a geometric pose pool.

Known-answer controls retain the reference's alignment and inner prefix, but
never give its outer placements to the pool generator. This is a conditional
synthesis experiment, not a blind tile generator or a non-tiling proof.
"""
import argparse
import collections
import hashlib
import itertools
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
import template_synthesis as templates
import verify


def cell_window(grid, cells, radius):
    possible = set(cells)
    for _ in range(radius):
        possible |= {(x + dx, y + dy) for x, y in possible
                     for dx, dy in shape.NEIGHBOURS[grid]}
    return possible


def hole_components(grid, occupied):
    """Finite empty edge-connected components inside a one-cell padded box."""
    if not occupied:
        return []
    xmin, xmax = min(x for x, _ in occupied) - 1, max(x for x, _ in occupied) + 1
    ymin, ymax = min(y for _, y in occupied) - 1, max(y for _, y in occupied) + 1
    empty = {(x, y) for x in range(xmin, xmax + 1) for y in range(ymin, ymax + 1)} - occupied
    holes = []
    while empty:
        start = min(empty)
        component, todo, boundary = {start}, [start], False
        empty.remove(start)
        while todo:
            x, y = todo.pop()
            boundary |= x in (xmin, xmax) or y in (ymin, ymax)
            for dx, dy in shape.NEIGHBOURS[grid]:
                q = x + dx, y + dy
                if q in empty:
                    empty.remove(q)
                    component.add(q)
                    todo.append(q)
        if not boundary:
            holes.append(component)
    return holes


def add_fixed_tile_hole_cuts(model, cells, placements):
    """Reject a hole by changing its wall or covering an interior anchor.

    Sound only with a fixed tile: keeping all current wall copies and leaving
    an anchor empty leaves a bounded empty component, however other poses
    change. Unlike a full-assignment block, one cut excludes many holed layouts.
    """
    if (set(cells) != set(model.variables)
            or any((v,) not in model.cnf._seen for v in model.variables.values())):
        raise ValueError('hole cuts require a fixed occupied tile')
    selected = set(map(tuple, placements))
    images = [(p, selector, {repair.transform(p[1:], cell) for cell in cells})
              for p, selector in model.placements]
    occupied = set().union(*(image for p, _, image in images if p in selected))
    holes = hole_components(model.grid, occupied)
    for hole in holes:
        wall = {(x + dx, y + dy) for x, y in hole
                for dx, dy in shape.NEIGHBOURS[model.grid]} - hole
        anchor = min(hole)
        remove = {-selector for p, selector, image in images
                  if selector and p in selected and image & wall}
        cover = {selector for _, selector, image in images if selector and anchor in image}
        model.cnf.add(remove | cover)
    return [len(hole) for hole in holes]


def outer_pool(grid, cells, prefix, target, edits, target_cells, radius=2,
               max_poses=512, max_deletion_masks=200000):
    """Enumerate possible contacts, prune necessary original-cell collisions.

    Every feasible outer pose must touch the previous ring through some cell
    in the shared cell window. Original-cell collisions require deletion of at
    least one of the two involved source cells, in EVERY copy. Enumerating the
    allowed deletion masks provides a sound necessary filter. No target outer
    pose or target tile cells are used. Ranking/capping makes a limited pool
    incomplete; the returned metadata explicitly records that limitation.
    """
    cells = sorted(map(tuple, cells))
    prefix = [tuple(p) for p in prefix]
    if (grid not in verify.TOUCH or radius not in (0, 1, 2) or edits < 0
            or max_poses < 1 or target < 1 or not 1 <= target_cells <= 200
            or not cells or len(set(cells)) != len(cells)):
        raise ValueError("invalid pose-pool bounds or tile")
    if (any(len(p) != 7 or any(type(v) is not int for v in p) for p in prefix)
            or set(p[0] for p in prefix) != set(range(target))
            or sum(p[0] == 0 for p in prefix) != 1
            or any((p[1], p[2], p[4], p[5])
                   not in shape.SYMMETRIES[grid] for p in prefix)):
        raise ValueError("prefix must contain exactly levels 0..target-1 and valid transforms")
    possible = cell_window(grid, cells, radius)
    delta = target_cells - len(cells)
    # Flips = removed + added = 2*removed + target_size-source_size.
    lo = max(0, -delta)
    hi = min(len(cells), (edits - delta) // 2, len(possible) - target_cells)
    mask_count = sum(math.comb(len(cells), k) for k in range(lo, hi + 1))
    if mask_count > max_deletion_masks:
        raise ValueError(f"deletion-mask preflight cap: {mask_count} > {max_deletion_masks}")
    masks = [sum(1 << i for i in indices) for k in range(lo, hi + 1)
             for indices in itertools.combinations(range(len(cells)), k)]
    keep = [sum(1 << j for j, mask in enumerate(masks) if not mask & (1 << i))
            for i in range(len(cells))]
    by_size = collections.defaultdict(int)
    for j, mask in enumerate(masks):
        by_size[mask.bit_count()] |= 1 << j
    survivors = (1 << len(masks)) - 1
    owners = collections.defaultdict(list)
    previous, prefix_original = set(), set()
    for copy, (level, *T) in enumerate(prefix):
        for i, p in enumerate(cells):
            q = repair.transform(T, p)
            owners[q].append((copy, i))
            prefix_original.add(q)
        if level == target - 1:
            previous |= {repair.transform(T, p) for p in cells}
    for entries in owners.values():
        for (copy, i), (other, j) in itertools.combinations(entries, 2):
            if copy != other:
                survivors &= ~(keep[i] & keep[j])
    metadata = {"target_level": target, "mandatory_prefix_copies": len(prefix),
                "cell_window": len(possible), "deletion_masks": len(masks),
                "prefix_feasible_deletion_masks": survivors.bit_count(),
                "max_poses": max_poses}
    if not survivors:
        return [], dict(metadata, enumerated_poses=0, collision_feasible_poses=0,
                        selected_poses=0, pool_capped=False)
    # Candidate translations come from possible contact, using the window for
    # both the preceding copy and the proposed outer copy.
    contact_cells = set()
    for level, *T in prefix:
        if level == target - 1:
            contact_cells |= {(x + dx, y + dy)
                              for x, y in (repair.transform(T, p) for p in possible)
                              for dx, dy in verify.TOUCH[grid]}
    required = {(x + dx, y + dy) for x, y in previous
                for dx, dy in verify.TOUCH[grid]} - prefix_original
    ranked, enumerated = [], 0
    for a, b, d, e in shape.SYMMETRIES[grid]:
        rotated = [(a * x + b * y, d * x + e * y) for x, y in cells]
        window = {(a * x + b * y, d * x + e * y) for x, y in possible}
        offsets = {(u - x, v - y) for u, v in contact_cells for x, y in window}
        enumerated += len(offsets)
        for dx, dy in sorted(offsets):
            feasible = survivors
            image = [(x + dx, y + dy) for x, y in rotated]
            for j, q in enumerate(image):
                for _, i in owners.get(q, ()):
                    feasible &= ~(keep[i] & keep[j])
                if not feasible:
                    break
            if not feasible:
                continue
            removed = next(k for k in sorted(by_size) if by_size[k] & feasible)
            covers = len(set(image) & required)
            contacts = sum((x + u, y + v) in previous for x, y in image
                           for u, v in verify.TOUCH[grid])
            pose = (target, a, b, dx, d, e, dy)
            ranked.append(((removed, -covers, -contacts, pose), pose))
    ranked.sort()
    poses = [p for _, p in ranked[:max_poses]]
    metadata.update(enumerated_poses=enumerated, collision_feasible_poses=len(ranked),
                    selected_poses=len(poses), pool_capped=len(ranked) > len(poses),
                    pool_sha256=hashlib.sha256(json.dumps(poses).encode()).hexdigest())
    return poses, metadata


def prefix_synthesis(sketch, info, edits, radius=2, max_poses=1536,
                     seconds=15, mem_mb=1000, reserve_mb=8000,
                     max_shapes=2, max_layouts=16, min_cells=None, max_cells=None):
    """Enumerate prefix-compatible tiles, then solve their missing outer ring.

    This avoids constructing the very large joint variable-window pose model.
    Failed extension is feedback to try the next prefix-compatible shape.
    Caps remain unresolved and finite iteration limits do not prove exhaustion.
    """
    target, grid = sketch['level'], sketch['grid']
    if target < 2 or max_shapes < 1 or max_layouts < 1:
        raise ValueError('prefix synthesis needs target>=2 and positive iteration limits')
    prefix = [p for p in sketch['placements'] if p[0] < target]
    start = time.monotonic()
    min_cells = info['target_cells'] if min_cells is None else min_cells
    max_cells = info['target_cells'] if max_cells is None else max_cells
    base = repair.RepairModel(dict(sketch, placements=prefix, level=target - 1), edits,
        radius=radius, min_cells=min_cells, max_cells=max_cells,
        freeze_interior=False, require_change=edits > 0)
    build_seconds = round(time.monotonic() - start, 4)
    for attempt in range(max_shapes):
        result = repair.solve_cnf(base.cnf, timeout=seconds, mem_mb=mem_mb, reserve_mb=reserve_mb)
        positive = result.pop('positive', None)
        row = {'strategy': 'prefix-enumeration', 'shape_attempt': attempt + 1,
               'prefix_build_seconds': build_seconds, 'prefix_solve': result,
               'max_shapes': max_shapes, 'max_layouts': max_layouts,
               'min_cells': min_cells, 'max_cells': max_cells,
               'excluded_prefix_shapes': attempt, 'refinement': 'fixed-tile-hole-cuts-v1'}
        if positive is None:
            yield dict(row, status='prefix-' + result['status'])
            return
        cells, _ = base.decode(positive)
        valid, message, bad_shape = repair.validate_candidate(base, cells, prefix)
        row.update(canon=shape.canonical(grid, cells), prefix_verified=valid,
                   prefix_verification_message=message)
        base.block(positive, shape_only=True)
        if not valid:
            yield dict(row, status='invalid-prefix', invalid_shape=bad_shape)
            continue
        start = time.monotonic()
        poses, metadata = outer_pool(grid, cells, prefix, target, 0, len(cells),
                                    radius=0, max_poses=max_poses)
        row.update(metadata, pool_seconds=round(time.monotonic() - start, 4),
                   generated_outer_poses=poses)
        if not poses:
            yield dict(row, status='empty-pool')
            continue
        start = time.monotonic()
        extension = repair.RepairModel(dict(sketch, cells=cells, placements=prefix + poses),
            0, radius=0, min_cells=len(cells), max_cells=len(cells),
            freeze_interior=False, require_change=False, optional_from_level=target)
        row['extension_build_seconds'] = round(time.monotonic() - start, 4)
        for layout in range(max_layouts):
            result = repair.solve_cnf(extension.cnf, timeout=seconds,
                                      mem_mb=mem_mb, reserve_mb=reserve_mb)
            positive = result.pop('positive', None)
            attempt_row = dict(row, extension_solve=result, layout_attempt=layout + 1)
            if positive is None:
                yield dict(attempt_row, status='extension-' + result['status'])
                break
            new_cells, placements = extension.decode(positive)
            valid, message, _ = repair.validate_candidate(extension, new_cells, placements)
            attempt_row.update(verification_message=message,
                               verified_lower_bound=target if valid else None,
                               matches_reference=attempt_row['canon'] == info['template_tile'])
            if valid:
                yield dict(attempt_row, status='verified',
                           witness=repair.witness_text(grid, new_cells, placements, target))
                return
            holes = add_fixed_tile_hole_cuts(extension, new_cells, placements)
            attempt_row['hole_cut_sizes'] = holes
            yield dict(attempt_row, status='invalid-extension')
            if not holes:
                extension.block(positive)
        else:
            yield dict(row, status='extension-layout-limit')
    yield {'strategy': 'prefix-enumeration', 'status': 'prefix-shape-limit',
           'max_shapes': max_shapes, 'max_layouts': max_layouts}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent', required=True, help='bare O/H source tile line')
    ap.add_argument('--template', required=True, help='known-answer witness; last ring is withheld')
    ap.add_argument('--out', required=True, help='append-only result JSONL')
    ap.add_argument('--edit-budgets', default='2,4,6')
    ap.add_argument('--radius', type=int, choices=[0, 1, 2], default=2)
    ap.add_argument('--max-poses', type=int, default=1536)
    ap.add_argument('--pool-only', action='store_true')
    ap.add_argument('--strategy', choices=['prefix-enumeration', 'joint'], default='prefix-enumeration')
    ap.add_argument('--max-shapes', type=int, default=2)
    ap.add_argument('--max-layouts', type=int, default=16)
    ap.add_argument('--extend-one', action='store_true',
                    help='use all known rings as a prefix and attempt one new ring')
    ap.add_argument('--min-cells', type=int)
    ap.add_argument('--max-cells', type=int)
    ap.add_argument('--seconds', type=float, default=15)
    ap.add_argument('--mem-mb', type=float, default=1000)
    ap.add_argument('--reserve-mb', type=float, default=8000)
    args = ap.parse_args()
    if (any(not math.isfinite(v) or v <= 0 for v in (args.seconds, args.mem_mb))
            or not math.isfinite(args.reserve_mb) or args.reserve_mb < 0):
        ap.error('invalid solver resource limits')
    if Path(args.template).resolve() == Path(args.out).resolve():
        ap.error('template and output must differ')
    if (args.extend_one or args.min_cells is not None or args.max_cells is not None) and (args.strategy != 'prefix-enumeration' or args.pool_only):
        ap.error('extension/size bounds require prefix-enumeration and a solve')
    budgets = [int(x) for x in args.edit_budgets.split(',')]
    if not budgets or any(b < 0 for b in budgets):
        ap.error('edit budgets must be nonnegative')
    text = Path(args.template).read_text()
    sketch, info = templates.make_sketch(args.parent, text)
    if args.extend_one:
        sketch['level'] += 1
        info['target_level'] += 1
    target = sketch['level']
    prefix = [p for p in sketch['placements'] if p[0] < target]
    # Held-out data is used ONLY after generation, to report control coverage.
    gold_outer = {tuple(p) for p in sketch['placements'] if p[0] == target}
    runner.ensure_jsonl_boundary(args.out)
    for edits in budgets:
        if args.strategy == 'prefix-enumeration' and not args.pool_only:
            for result in prefix_synthesis(sketch, info, edits, args.radius, args.max_poses,
                    args.seconds, args.mem_mb, args.reserve_mb, args.max_shapes, args.max_layouts,
                    args.min_cells, args.max_cells):
                poses = result.pop('generated_outer_poses', None)
                row = {'experiment': 'next-corona-synthesis' if args.extend_one else 'withheld-outer-corona-synthesis', **info,
                    'edits': edits, 'radius': args.radius, 'ts': time.time(),
                    'template': args.template,
                    'template_sha256': hashlib.sha256(text.encode()).hexdigest(),
                    'gold_outer_copies': None if args.extend_one else len(gold_outer),
                    'gold_outer_in_pool': len(gold_outer & set(poses)) if poses is not None and not args.extend_one else None,
                    'qualification': 'Alignment and inner prefix supplied by reference. '
                        'Prefix-compatible tile synthesized first; outer poses generated from that tile. '
                        'Reference outer poses used only for post-generation coverage reporting. '
                        'A valid patch is a lower bound; finite non-tiling classification remains separate.',
                    **result}
                with open(args.out, 'a') as f:
                    f.write(json.dumps(row) + '\n')
                print(json.dumps({k: row[k] for k in ('edits', 'status', 'shape_attempt',
                    'layout_attempt', 'selected_poses', 'pool_capped', 'gold_outer_in_pool',
                    'verified_lower_bound', 'verification_message', 'hole_cut_sizes') if k in row}), flush=True)
            continue
        start = time.monotonic()
        poses, metadata = outer_pool(sketch['grid'], sketch['cells'], prefix,
                                    target, edits, info['target_cells'], args.radius,
                                    args.max_poses)
        row = {'experiment': 'withheld-outer-corona-synthesis', **info, **metadata,
               'edits': edits, 'radius': args.radius, 'ts': time.time(),
               'template': args.template,
               'template_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'gold_outer_copies': len(gold_outer),
               'gold_outer_in_pool': len(gold_outer & set(poses)),
               'pool_seconds': round(time.monotonic() - start, 4),
               'qualification': 'Alignment and inner prefix supplied by reference. '
                   'Outer poses generated without reference outer ring or reference tile cells. '
                   'A valid patch proves a lower bound only, not finite Heesch number.'}
        if args.pool_only:
            row['status'] = 'pool-only'
        elif not poses:
            row['status'] = 'prefix-infeasible' if not metadata['prefix_feasible_deletion_masks'] else 'empty-pool'
        else:
            start = time.monotonic()
            model = repair.RepairModel(dict(sketch, placements=prefix + poses), edits,
                radius=args.radius, min_cells=info['target_cells'], max_cells=info['target_cells'],
                freeze_interior=False, require_change=edits > 0, optional_from_level=target)
            row['build_seconds'] = round(time.monotonic() - start, 4)
            result = repair.solve_cnf(model.cnf, timeout=args.seconds,
                                      mem_mb=args.mem_mb, reserve_mb=args.reserve_mb)
            positive = result.pop('positive', None)
            row.update(result)
            if positive is not None:
                cells, placements = model.decode(positive)
                valid, message, _ = repair.validate_candidate(model, cells, placements)
                canon = shape.canonical(model.grid, cells)
                row.update(canon=canon, verified_lower_bound=target if valid else None,
                           verification_message=message,
                           matches_reference=canon == info['template_tile'])
                if valid:
                    row['witness'] = repair.witness_text(model.grid, cells, placements, target)
        with open(args.out, 'a') as f:
            f.write(json.dumps(row) + '\n')
        print(json.dumps({k: v for k, v in row.items() if k != 'witness'}), flush=True)


if __name__ == '__main__':
    main()
