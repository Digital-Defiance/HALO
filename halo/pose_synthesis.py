#!/usr/bin/env python3
"""Reconstruct a corona from a supplied contact graph, with free grid poses.

No noncentral absolute transform is accepted by PoseModel. The fixed tile and
reference contact graph (optionally contact counts) are still supplied. This is
a conditional reconstruction control, not blind tile discovery or SE-Sync.
Uses the Z3 CLI; no Python Z3 dependency or production-checker changes.
"""
import argparse
import collections
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outer_synthesis
import patch_repair as repair
import runner
import shape
import verify

IDENTITY = (1, 0, 0, 0, 1, 0)


def compose(A, B):
    a, b, c, d, e, f = A
    g, h, i, j, k, l = B
    return (a*g+b*j, a*h+b*k, a*i+b*l+c,
            d*g+e*j, d*h+e*k, d*i+e*l+f)


def inverse(T):
    a, b, c, d, e, f = T
    det = a*e-b*d
    if abs(det) != 1:
        raise ValueError('expected a unimodular grid isometry')
    p, q, r, s = e//det, -b//det, -d//det, a//det
    return p, q, -p*c-q*f, r, s, -r*c-s*f


def contact_count(grid, A, B):
    return sum((x+dx, y+dy) in B for x, y in A for dx, dy in verify.TOUCH[grid])


def graph_from_witness(text, level=None):
    ok, message = verify.verify(text)
    if not ok:
        raise ValueError('invalid reference: ' + message)
    grid, cells, hc, _, copies = verify.parse_witness(text)
    level = hc if level is None else level
    if not 1 <= level <= hc:
        raise ValueError('level must lie within the reference witness')
    copies = [(k, T) for k, T in copies if k <= level]
    images = [{repair.transform(T, p) for p in cells} for _, T in copies]
    edges = []
    for i, j in itertools.combinations(range(len(copies)), 2):
        count = contact_count(grid, images[i], images[j])
        if count:
            edges.append([i, j, count])
    graph = {'levels': [k for k, _ in copies], 'edges': edges,
             'root': next(i for i, (k, _) in enumerate(copies) if k == 0)}
    # Choose an occupied anchor so every orientation contains the local origin.
    x, y = min(cells)
    cells = sorted((u-x, v-y) for u, v in cells)
    return grid, cells, graph


def legal_contacts(grid, cells):
    source = set(cells)
    result = collections.defaultdict(list)
    for a, b, d, e in shape.SYMMETRIES[grid]:
        rotated = {(a*x+b*y, d*x+e*y) for x, y in source}
        offsets = {(x+dx-u, y+dy-v) for x, y in source
                   for dx, dy in verify.TOUCH[grid] for u, v in rotated}
        for tx, ty in sorted(offsets):
            image = {(x+tx, y+ty) for x, y in rotated}
            if not source & image:
                result[contact_count(grid, source, image)].append((a, b, tx, d, e, ty))
    return dict(result)


def smt_int(value):
    return str(value) if value >= 0 else f'(- {-value})'


def smt_or(items):
    items = list(items)
    return '(or ' + ' '.join(items) + ')' if items else 'false'


def ite_lookup(symbol, values):
    result = smt_int(values[-1])
    for i in reversed(range(len(values)-1)):
        result = f'(ite (= {symbol} {i}) {smt_int(values[i])} {result})'
    return result


def linear(coeff, symbol):
    return '0' if coeff == 0 else symbol if coeff == 1 else f'(- {symbol})' if coeff == -1 else f'(* {smt_int(coeff)} {symbol})'


class PoseModel:
    def __init__(self, grid, cells, graph, weighted=True):
        if grid not in verify.TOUCH or not cells or (0, 0) not in cells:
            raise ValueError('O/H fixed tile must contain the occupied origin')
        ok, problems, _ = shape.check_cells(grid, cells)
        if not ok or any('stricter' in p for p in problems):
            raise ValueError('invalid fixed tile: ' + '; '.join(problems))
        self.grid, self.cells = grid, sorted(set(map(tuple, cells)))
        self.graph, self.weighted = graph, weighted
        self.levels, self.root = list(graph['levels']), graph['root']
        n = len(self.levels)
        if (not 0 <= self.root < n or self.levels[self.root] != 0
                or self.levels.count(0) != 1
                or set(self.levels) != set(range(max(self.levels)+1))):
            raise ValueError('invalid graph levels/root')
        self.target = max(self.levels)
        self.syms = shape.SYMMETRIES[grid]
        self.contacts = legal_contacts(grid, self.cells)
        all_contacts = [T for ts in self.contacts.values() for T in ts]
        self.composition = [[self.syms.index((A*a+B*d, A*b+B*e, D*a+E*d, D*b+E*e))
            for a,b,d,e in self.syms] for A,B,D,E in self.syms]
        # Each graph step is a rotated legal contact displacement. Its largest
        # axial coordinate bounds every path sum, without a reference pose box.
        step = max(abs(v) for T in all_contacts for a, b, d, e in self.syms
                   for v in (a*T[2]+b*T[5], d*T[2]+e*T[5]))
        adjacency = collections.defaultdict(list)
        for i, j, count in graph['edges']:
            if not (0 <= i < j < n and count > 0):
                raise ValueError('invalid graph edge')
            adjacency[i].append(j)
            adjacency[j].append(i)
        distance = {self.root: 0}
        todo = collections.deque([self.root])
        while todo:
            i = todo.popleft()
            for j in adjacency[i]:
                if j not in distance:
                    distance[j] = distance[i]+1
                    todo.append(j)
        if len(distance) != n:
            raise ValueError('contact graph must be connected')
        self.bounds = [step*distance[i] for i in range(n)]
        extent = max(abs(v) for x, y in self.cells for a, b, d, e in self.syms
                     for v in (a*x+b*y, d*x+e*y))
        self.stride = 2*(max(self.bounds)+extent+1)+1
        self.lines = ['(set-logic QF_LIA)', '(set-option :produce-models true)',
                      '(set-option :smt.threads 1)']
        self.symbols = []
        for i in range(n):
            for name in (f'r{i}', f'x{i}', f'y{i}'):
                self.lines.append(f'(declare-const {name} Int)')
                self.symbols.append(name)
            self.add(f'(and (<= 0 r{i}) (< r{i} {len(self.syms)}) '
                     f'(<= {smt_int(-self.bounds[i])} x{i}) (<= x{i} {self.bounds[i]}) '
                     f'(<= {smt_int(-self.bounds[i])} y{i}) (<= y{i} {self.bounds[i]}))')
            self.lines.append(f'(define-fun anchor{i} () Int (+ (* {self.stride} x{i}) y{i}))')
            for j, p in enumerate(self.cells):
                self.lines.append(f'(define-fun k{i}_{j} () Int {self.world_key(i, p)})')
        self.add(f'(and (= r{self.root} 0) (= x{self.root} 0) (= y{self.root} 0))')
        self.add('(distinct ' + ' '.join(f'anchor{i}' for i in range(n)) + ')')
        # Tables depend only on the fixed tile's legal two-copy contacts.
        for s, (a, b, d, e) in enumerate(self.syms):
            indices = []
            for A, B, D, E in self.syms:
                indices.append(self.syms.index((A*a+B*d, A*b+B*e, D*a+E*d, D*b+E*e)))
            self.lines.append(f'(define-fun rot{s} ((r Int)) Int {ite_lookup("r", indices)})')
            self.lines.append(f'(define-fun leftrot{s} ((r Int)) Int {ite_lookup("r", self.composition[s])})')
        for edge, (i, j, count) in enumerate(graph['edges']):
            choices = self.contacts.get(count, []) if weighted else all_contacts
            # Factor the table from world orientation: one relative rotation
            # and displacement per edge, followed by twelve linear maps.
            # Expanding each pose choice into all world frames is much larger.
            s, u, v = f's{edge}', f'u{edge}', f'v{edge}'
            for symbol in (s,u,v):
                self.lines.append(f'(declare-const {symbol} Int)')
            grouped = collections.defaultdict(list)
            for a,b,tx,d,e,ty in choices:
                grouped[self.syms.index((a,b,d,e))].append((tx,ty))
            self.add(smt_or(f'(and (= {s} {r}) {smt_or(f"(and (= {u} {smt_int(x)}) (= {v} {smt_int(y)}))" for x,y in offsets)})'
                            for r,offsets in sorted(grouped.items())))
            for r,(a,b,d,e) in enumerate(self.syms):
                self.add(f'(=> (= r{i} {r}) (and (= r{j} (leftrot{r} {s})) '
                         f'(= x{j} (+ x{i} {linear(a,u)} {linear(b,v)})) '
                         f'(= y{j} (+ y{i} {linear(d,u)} {linear(e,v)}))))')
        self._cuts = set()

    def add(self, formula):
        self.lines.append('(assert ' + formula + ')')

    def world_key(self, i, p):
        x, y = p
        values = [self.stride*(a*x+b*y)+d*x+e*y for a, b, d, e in self.syms]
        return f'(+ (* {self.stride} x{i}) y{i} {ite_lookup(f"r{i}", values)})'

    def relation(self, i, j, T):
        a, b, tx, d, e, ty = T
        s = self.syms.index((a, b, d, e))
        dx = ite_lookup(f'r{i}', [A*tx+B*ty for A, B, _, _ in self.syms])
        dy = ite_lookup(f'r{i}', [D*tx+E*ty for _, _, D, E in self.syms])
        return f'(and (= r{j} (rot{s} r{i})) (= x{j} (+ x{i} {dx})) (= y{j} (+ y{i} {dy})))'

    def cover(self, i, p, maxlevel):
        key = self.world_key(i, p)
        return smt_or(f'(= {key} k{j}_{q})' for j, level in enumerate(self.levels)
                      if level <= maxlevel for q in range(len(self.cells)))

    def script(self):
        return '\n'.join(self.lines + ['(check-sat)', '(get-value (' + ' '.join(self.symbols) + '))']) + '\n'

    def decode(self, values):
        placements = []
        for i, level in enumerate(self.levels):
            r, x, y = (values[f'{s}{i}'] for s in ('r', 'x', 'y'))
            if not (type(r) is int and type(x) is int and type(y) is int
                    and 0 <= r < len(self.syms) and abs(x) <= self.bounds[i] and abs(y) <= self.bounds[i]):
                raise ValueError('invalid/out-of-bounds pose assignment')
            a, b, d, e = self.syms[r]
            placements.append((level, a, b, x, d, e, y))
        if placements[self.root][1:] != IDENTITY:
            raise ValueError('root pose changed')
        images = [{repair.transform(p[1:], q) for q in self.cells} for p in placements]
        for i, j, count in self.graph['edges']:
            actual = contact_count(self.grid, images[i], images[j])
            if (self.weighted and actual != count) or (not self.weighted and actual == 0):
                raise ValueError('model violates a supplied contact constraint')
        return placements, images

    def refine(self, placements, images):
        """Sound fixed-tile cuts: overlaps, enclosure and holes at every prefix."""
        added = collections.Counter()
        def cut(tag, formula):
            if formula not in self._cuts:
                self._cuts.add(formula)
                self.add(formula)
                added[tag] += 1
        for i, j in itertools.combinations(range(len(images)), 2):
            if images[i] & images[j]:
                T = compose(inverse(placements[i][1:]), placements[j][1:])
                cut('overlap', '(not ' + self.relation(i, j, T) + ')')
        if added:
            return dict(added)
        for i, (level, *T) in enumerate(placements):
            if level >= self.target:
                continue
            prefix = set().union(*(im for lev, im in zip(self.levels, images) if lev <= level+1))
            missing = {(x+dx, y+dy) for x, y in images[i]
                       for dx, dy in verify.TOUCH[self.grid]} - prefix
            inv = inverse(T)
            for q in missing:
                cut('coverage', self.cover(i, repair.transform(inv, q), level+1))
        if added:
            return dict(added)
        for formula in self.hole_formulas(placements, images):
            cut('hole', formula)
        return dict(added)

    def hole_formulas(self, placements, images):
        for level in range(1, self.target+1):
            indices = [i for i, lev in enumerate(self.levels) if lev <= level]
            occupied = set().union(*(images[i] for i in indices))
            for hole in outer_synthesis.hole_components(self.grid, occupied):
                wall = {(x+dx, y+dy) for x, y in hole
                        for dx, dy in shape.NEIGHBOURS[self.grid]} - hole
                nodes = [i for i in indices if images[i] & wall]
                anchor = min(nodes)
                terms = []
                for j in nodes:
                    if j != anchor:
                        T = compose(inverse(placements[anchor][1:]), placements[j][1:])
                        terms.append('(not ' + self.relation(anchor, j, T) + ')')
                local = repair.transform(inverse(placements[anchor][1:]), min(hole))
                terms.append(self.cover(anchor, local, level))
                yield smt_or(terms)


def parse_values(text):
    tokens = re.findall(r'\(|\)|[^\s()]+', text)
    index = 0
    def read():
        nonlocal index
        if index >= len(tokens):
            raise ValueError('truncated SMT model')
        token = tokens[index]
        index += 1
        if token == '(':
            out = []
            while index < len(tokens) and tokens[index] != ')':
                out.append(read())
            if index == len(tokens):
                raise ValueError('unterminated SMT model')
            index += 1
            return out
        if token == ')':
            raise ValueError('unexpected closing parenthesis')
        return token
    data = read()
    if index != len(tokens) or not isinstance(data, list):
        raise ValueError('extra SMT model output')
    result = {}
    for entry in data:
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError('invalid SMT value pair')
        key, value = entry
        if isinstance(value, list) and len(value) == 2 and value[0] == '-':
            value = -int(value[1])
        else:
            value = int(value)
        if key in result:
            raise ValueError('duplicate SMT model symbol')
        result[key] = value
    return result


def solve(model, seconds=15, mem_mb=1000, reserve_mb=8000, solver='z3'):
    solver = shutil.which(solver)
    if not solver:
        raise ValueError('Z3 CLI not found')
    if (any(not math.isfinite(v) or v <= 0 for v in (seconds, mem_mb))
            or not math.isfinite(reserve_mb) or reserve_mb < 0):
        raise ValueError('invalid solver limits')
    budget = runner.MemoryBudget(mem_mb, reserve_mb)
    if not budget.may_start():
        return {'status': 'memory-pressure', 'seconds': 0.0}
    script = model.script()
    info = {'smt_sha256': hashlib.sha256(script.encode()).hexdigest(), 'smt_bytes': len(script)}
    start, peak, stopped = time.monotonic(), 0, None
    with tempfile.TemporaryDirectory(prefix='halo-poses-') as folder:
        path = Path(folder) / 'model.smt2'
        path.write_text(script)
        with (Path(folder)/'stdout').open('w+') as out, (Path(folder)/'stderr').open('w+') as err:
            proc = subprocess.Popen([solver, '-smt2', f'-t:{max(1,int(seconds*1000))}',
                    f'-memory:{math.ceil(mem_mb)}', str(path)], stdout=out, stderr=err, close_fds=False)
            budget.register(proc.pid, priority=mem_mb)
            try:
                while proc.poll() is None:
                    rss = runner.rss_mb(proc.pid) or 0
                    peak = max(peak, rss)
                    if rss > mem_mb:
                        stopped = 'memout'
                    elif budget.stop_reason(proc.pid, rss):
                        stopped = 'memory-pressure'
                    elif time.monotonic()-start > seconds:
                        stopped = 'timeout'
                    if stopped:
                        proc.kill()
                        break
                    try:
                        proc.wait(timeout=.05)
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                budget.unregister(proc.pid)
            out.seek(0)
            output = out.read()
            err.seek(0)
            errors = err.read()
    info.update(seconds=round(time.monotonic()-start,4), peak_rss_mb=round(peak,1), returncode=proc.returncode)
    if stopped:
        return dict(info, status=stopped)
    if 'out of memory' in (output+errors).lower():
        return dict(info, status='memout')
    lines = output.strip().splitlines()
    if not lines or lines[0] not in ('sat', 'unsat', 'unknown'):
        return dict(info, status='solver-error', diagnostic=(output+errors)[-2000:])
    status = lines[0]
    if status == 'sat':
        values = parse_values('\n'.join(lines[1:]))
        if set(values) != set(model.symbols) or proc.returncode != 0 or errors:
            raise ValueError('incomplete/unexpected SMT result')
        return dict(info, status='sat', values=values)
    # get-value after unsat/unknown intentionally reports no model. Reject all
    # other parser errors, which could otherwise silently drop a constraint.
    remainder = '\n'.join(lines[1:])
    expected = re.fullmatch(r'\(error "line \d+ column \d+: model is not available"\)', remainder)
    if not expected or errors or proc.returncode not in (0,1):
        return dict(info, status='solver-error', diagnostic=(output+errors)[-2000:])
    return dict(info, status=status)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('reference')
    ap.add_argument('--level', type=int)
    ap.add_argument('--unweighted', action='store_true', help='hide reference contact counts too')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=15, help='per solver call, including file writing')
    ap.add_argument('--mem-mb', type=float, default=1000)
    ap.add_argument('--reserve-mb', type=float, default=8000)
    ap.add_argument('--max-models', type=int, default=12)
    args = ap.parse_args()
    if Path(args.reference).resolve() == Path(args.out).resolve() or args.max_models < 1:
        ap.error('invalid output/iteration bounds')
    text = Path(args.reference).read_text()
    grid, cells, graph = graph_from_witness(text, args.level)
    start = time.monotonic()
    model = PoseModel(grid, cells, graph, weighted=not args.unweighted)
    build_seconds = round(time.monotonic()-start,4)
    run_id = uuid.uuid4().hex
    runner.ensure_jsonl_boundary(args.out)
    for attempt in range(args.max_models):
        result = solve(model, args.seconds, args.mem_mb, args.reserve_mb)
        values = result.pop('values', None)
        row = {'experiment': 'relative-pose-reconstruction', 'run_id': run_id,
               'encoding': 'factored-relative-contact-v1',
               'ts': time.time(), 'attempt': attempt+1, 'reference': args.reference,
               'reference_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'grid': grid, 'canon': shape.canonical(grid,cells), 'target_level': model.target,
               'copies': len(graph['levels']), 'graph': graph, 'weighted': model.weighted,
               'build_seconds': build_seconds, 'limits': vars(args), **result,
               'qualification': 'Fixed tile and reference contact topology supplied; contact counts '
                   'also supplied in weighted mode. No noncentral absolute pose supplied. '
                   'Only the recorded graph/pose bounds are searched; not blind discovery.'}
        if values is not None:
            placements, images = model.decode(values)
            witness = repair.witness_text(grid,cells,placements,model.target)
            ok, message = verify.verify(witness)
            row.update(verified=ok, verification_message=message,
                       assignment_sha256=hashlib.sha256(json.dumps(placements).encode()).hexdigest())
            if ok:
                row.update(status='verified', witness=witness)
            else:
                cuts = model.refine(placements,images)
                row.update(status='refined' if cuts else 'invalid-unrefined', cuts=cuts)
                if cuts and attempt+1 == args.max_models:
                    row['status'] = 'model-limit'
        with open(args.out,'a') as f:
            f.write(json.dumps(row)+'\n')
        print(json.dumps({k: row[k] for k in ('run_id','attempt','status','seconds','peak_rss_mb',
              'weighted','copies','verification_message','cuts') if k in row}),flush=True)
        if row['status'] != 'refined':
            break


if __name__ == '__main__':
    main()
