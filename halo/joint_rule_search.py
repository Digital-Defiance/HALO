#!/usr/bin/env python3
"""Staged rule synthesis: invent a shallow marked surround, then check deeper.

The fixed body is supplied; initial markings and layouts are not. Already tested
rule orbits are excluded explicitly. Resource-capped rules remain deferred;
their exclusion never becomes a proof that the target is impossible.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import joint_marked as joint
import marked_polyform as marked
import marked_screen
import runner
import shape


def rule_orbit(cells,marks):
    """Rule vectors under actual automorphisms of this fixed body, plus shift."""
    cells=set(map(tuple,cells));labels=marked.boundary_marks(cells,marks)
    edges=sorted(labels);out=set()
    for a,b,d,e in shape.SYMMETRIES['H']:
        image={(a*x+b*y,d*x+e*y) for x,y in cells}
        u,v=min(cells);x,y=min(image);tx,ty=u-x,v-y
        if {(x+tx,y+ty) for x,y in image}!=cells:continue
        transformed={(a*x+b*y+tx,d*x+e*y+ty,a*dx+b*dy,d*dx+e*dy):q
                     for (x,y,dx,dy),q in labels.items()}
        if set(transformed)!=set(edges):raise ValueError('body symmetry lost boundary edges')
        out.add(tuple(transformed[edge] for edge in edges))
    return sorted(out)


def validate_prior(cells,record,target):
    """Reuse only a completed exact forward check from this same fixed body."""
    if set(map(tuple,record['cells']))!=set(cells):raise ValueError('prior check has a different body')
    marks=record['marks'];labels=marked.boundary_marks(cells,marks)
    extension=record['extension']
    input_hash=hashlib.sha256(marked.solver_input(record['cells'],marks).encode()).hexdigest()
    hc=extension.get('hc');levels=extension.get('levels',[])
    if (sum(labels.values())!=-1 or any(q not in (-1,0,1) for q in labels.values())
            or extension.get('status')!='classified-in-marked-grid' or type(hc) is not int
            or not 0<=hc<target or len(levels)!=hc+1
            or levels[-1].get('status')!='unsat' or levels[-1].get('level')!=hc+1
            or extension.get('input_sha256')!=input_hash
            or extension.get('binary_sha256')!=hashlib.sha256(marked.DEFAULT_BINARY.read_bytes()).hexdigest()):
        raise ValueError('prior rule lacks a reusable completed forward exclusion')
    for level,row in enumerate(levels[:-1],1):
        if row.get('status')!='sat' or row.get('level')!=level:raise ValueError('invalid prior prefix sequence')
        marked.verify_patch(cells,marks,row['placements'],level)
    return marks


def search(cells,target=6,synthesis_level=3,max_candidates=12,total_seconds=60,
           joint_seconds=5,check_seconds=12,mem_mb=2500,reserve_mb=8000,prior_checked=()):
    if (not 1<=synthesis_level<=target<=12 or max_candidates<1
            or any(not math.isfinite(v) or v<=0 for v in
                   (total_seconds,joint_seconds,check_seconds,mem_mb))
            or not math.isfinite(reserve_mb) or reserve_mb<0):
        raise ValueError('invalid staged-search limits')
    cells=[tuple(p) for p in cells]
    blocked=set();fit_exclusions=set();deferred=0;tested=0;start=time.monotonic()
    reused=0
    for prior in prior_checked:
        marks=validate_prior(cells,prior,target)
        orbit=rule_orbit(cells,marks)
        if set(orbit)<=blocked:continue
        blocked.update(orbit);fit_exclusions.update(orbit);reused+=1
    for attempt in range(1,max_candidates+1):
        remaining=total_seconds-(time.monotonic()-start)
        if remaining<=0:
            yield {'kind':'summary','status':'budget-limit','tested':tested,'deferred':deferred}
            return
        synthesis=joint.synthesize(cells,synthesis_level,seconds=min(joint_seconds,remaining),
                                  mem_mb=mem_mb,reserve_mb=reserve_mb,
                                  blocked_rules=sorted(blocked),fit_exclusions=sorted(fit_exclusions))
        row={'kind':'candidate','attempt':attempt,'target_level':target,
             'synthesis_level':synthesis_level,'synthesis':synthesis,'reused_forward_checks':reused}
        if synthesis['status']!='verified':
            yield dict(row,status='synthesis-'+synthesis['status'])
            yield {'kind':'summary','status':'remaining-space-unsat' if synthesis['status']=='unsat'
                   else 'unresolved','tested':tested,'deferred':deferred,
                   'family_target_excluded':synthesis['status']=='unsat' and deferred==0,
                   'excluded_orbit_vectors':len(blocked),'reused_forward_checks':reused}
            return
        marks=synthesis['marks']
        key=marked_screen.canonical_marked(cells,marks)
        row['rule_id']=hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]
        row['marks']=marks
        remaining=total_seconds-(time.monotonic()-start)
        if target==synthesis_level:
            extension={'status':'already-verified','hc':None,'lower_bound':target,'levels':[]}
        elif remaining<=0:
            extension={'status':'budget-limit','hc':None,'lower_bound':synthesis_level,'levels':[]}
        else:
            extension=marked.run(cells,marks,maxlevel=target,
                                 seconds=min(check_seconds,remaining),mem_mb=mem_mb,reserve_mb=reserve_mb)
        row['extension']=extension;tested+=1
        lower=max(synthesis_level,extension['lower_bound'])
        row['lower_bound']=lower
        if lower>=target:
            yield dict(row,status='target-reached-in-marked-model')
            yield {'kind':'summary','status':'target-reached-in-marked-model',
                   'tested':tested,'deferred':deferred,'lower_bound':lower}
            return
        conclusive=extension.get('hc') is not None and extension['hc']<target
        if not conclusive:deferred+=1
        orbit=rule_orbit(cells,marks)
        blocked.update(orbit)
        if conclusive:fit_exclusions.update(orbit)
        yield dict(row,status='below-target' if conclusive else 'deferred',
                   exclusion_is_conclusive=conclusive,excluded_orbit_vectors=len(blocked),
                   monotone_fit_exclusions=len(fit_exclusions))
    yield {'kind':'summary','status':'candidate-limit','tested':tested,'deferred':deferred,
           'excluded_orbit_vectors':len(blocked)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    body=ap.add_mutually_exclusive_group(required=True)
    body.add_argument('--pillar',type=int)
    body.add_argument('--body',help='bare H tile line, with a fixed unmarked body only')
    ap.add_argument('--target',type=int,default=6)
    ap.add_argument('--synthesis-level',type=int,default=3)
    ap.add_argument('--max-candidates',type=int,default=12)
    ap.add_argument('--total-seconds',type=float,default=60)
    ap.add_argument('--joint-seconds',type=float,default=5)
    ap.add_argument('--check-seconds',type=float,default=12)
    ap.add_argument('--mem-mb',type=float,default=2500)
    ap.add_argument('--reserve-mb',type=float,default=8000)
    ap.add_argument('--out',required=True)
    ap.add_argument('--resume',action='store_true',help='reuse verified exact forward exclusions already in this output')
    args=ap.parse_args()
    if args.pillar is not None:
        if not 1<=args.pillar<=20:ap.error('pillar must have 1..20 cells')
        cells=[(i,0) for i in range(args.pillar)]
    else:
        grid,cells=shape.parse(args.body)
        if grid!='H':ap.error('only H bodies are supported')
    runner.ensure_jsonl_boundary(args.out)
    prior=[]
    if args.resume and Path(args.out).exists():
        for line in Path(args.out).read_text().splitlines():
            row=json.loads(line)
            if (row.get('experiment')=='staged-joint-rule-search-v1'
                    and row.get('kind')=='candidate' and row.get('exclusion_is_conclusive')
                    and set(map(tuple,row.get('cells',[])))==set(cells)):
                prior.append(row)
    run_id=uuid.uuid4().hex
    for result in search(cells,args.target,args.synthesis_level,args.max_candidates,
                         args.total_seconds,args.joint_seconds,args.check_seconds,
                         args.mem_mb,args.reserve_mb,prior):
        row={'experiment':'staged-joint-rule-search-v1','run_id':run_id,'ts':time.time(),
             'cells':cells,'limits':vars(args),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'qualification':'Fixed body; no positive marking or layout template. '
                 'Resumed exact negative checks are recorded as rule exclusions. '
                 'Only ternary complementary rules with net -1 in the lattice model. '
                 'Deferred exclusions do not prove target nonexistence. No unmarked realization.',**result}
        with open(args.out,'a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps({k:row[k] for k in ('kind','attempt','status','rule_id','lower_bound',
                    'tested','deferred','family_target_excluded') if k in row}),flush=True)


if __name__=='__main__':
    main()
