#!/usr/bin/env python3
"""Bounded polar-marking screen on compact polyhex bodies.

Upper-facing edges are negative, lower-facing edges positive, horizontal edges
flat. Change one horizontal edge to negative for a net -1 charge. All signs are
symbolic matching rules, not an unmarked realization. Canonicalize the entire
marked tile under D6, including reflected directions and charge values.
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
import marked_charge
import marked_polyform as marked
import runner
import shape


def bodies(size):
    if not 1<=size<=5:
        raise ValueError('screen is restricted to 1..5 cells')
    current={shape.canonical('H',[(0,0)])}
    for _ in range(1,size):
        following=set()
        for canon in current:
            _,cells=shape.parse(canon)
            candidates={(x+dx,y+dy) for x,y in cells for dx,dy in marked_charge.DIRS}-set(cells)
            for p in candidates:
                following.add(shape.canonical('H',cells+[p]))
        current=following
    return [shape.parse(canon)[1] for canon in sorted(current)]


def canonical_marked(cells,marks):
    labels=marked.boundary_marks(cells,marks)
    keys=[]
    for a,b,d,e in shape.SYMMETRIES['H']:
        points=[(a*x+b*y,d*x+e*y) for x,y in cells]
        mx=min(x for x,y in points);my=min(y for x,y in points)
        transformed=tuple(sorted((a*x+b*y-mx,d*x+e*y-my,a*dx+b*dy,d*dx+e*dy,q)
                                 for (x,y,dx,dy),q in labels.items()))
        keys.append((tuple(sorted((x-mx,y-my) for x,y in points)),transformed))
    return min(keys)


def candidates(size=4,compact_only=True):
    straight=shape.canonical('H',[(i,0) for i in range(size)])
    seen=set()
    for body in bodies(size):
        if compact_only and shape.canonical('H',body)==straight:
            continue
        for a,b,d,e in shape.SYMMETRIES['H']:
            cells=sorted((a*x+b*y,d*x+e*y) for x,y in body)
            labels=marked.boundary_marks(cells)
            for edge in labels:
                dx,dy=edge[2:]
                labels[edge]=-1 if dy>0 else 1 if dy<0 else 0
            assert sum(labels.values())==0
            for edge in labels:
                if edge[3]!=0:
                    continue
                changed=dict(labels);changed[edge]=-1
                marks=[[*key,q] for key,q in sorted(changed.items())]
                key=canonical_marked(cells,marks)
                if key in seen:continue
                seen.add(key)
                normalized,edges=key
                yield list(normalized),[list(e) for e in edges]


def marking_swaps(size=4):
    cells,marks=marked.mann_pillar(size)
    baseline=canonical_marked(cells,marks)
    seen={baseline}
    for i in range(len(marks)):
        for j in range(i+1,len(marks)):
            if marks[i][-1]==marks[j][-1]:continue
            changed=[list(m) for m in marks]
            changed[i][-1],changed[j][-1]=changed[j][-1],changed[i][-1]
            key=canonical_marked(cells,changed)
            if key in seen:continue
            seen.add(key)
            body,edges=key
            yield list(body),[list(e) for e in edges]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cells',type=int,default=4)
    ap.add_argument('--family',choices=['compact','pillar-swaps'],default='compact')
    ap.add_argument('--out',required=True)
    ap.add_argument('--total-seconds',type=float,default=60)
    ap.add_argument('--seconds',type=float,default=3)
    ap.add_argument('--mem-mb',type=float,default=1500)
    ap.add_argument('--reserve-mb',type=float,default=8000)
    ap.add_argument('--maxlevel',type=int,default=7)
    args=ap.parse_args()
    if (not 1<=args.maxlevel<=12 or any(not math.isfinite(v) or v<=0 for v in
            (args.total_seconds,args.seconds,args.mem_mb))
            or not math.isfinite(args.reserve_mb) or args.reserve_mb<0):
        ap.error('invalid limits')
    trials=list(candidates(args.cells) if args.family=='compact' else marking_swaps(args.cells))
    trials.sort(key=lambda pair:(sum(shape.spans(pair[0])),pair))
    runner.ensure_jsonl_boundary(args.out)
    run_id=uuid.uuid4().hex;start=time.monotonic();completed=0
    for cells,marks in trials:
        remaining=args.total_seconds-(time.monotonic()-start)
        if remaining<=0:break
        result=marked.run(cells,marks,args.maxlevel,min(args.seconds,remaining),args.mem_mb,args.reserve_mb)
        row={'experiment':'polar-marked-polyhex-screen-v1','family':args.family,'run_id':run_id,'ts':time.time(),
             'cells':cells,'marks':marks,'net_charge':sum(m[-1] for m in marks),
             'family_size':len(trials),'limits':vars(args),
             'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),**result,
             'qualification':'Bounded symbolic marked-grid screen; no unmarked realization. '
                 'All results are restricted to the recorded body/marking family.'}
        with open(args.out,'a') as f:f.write(json.dumps(row)+'\n')
        completed+=1
        if result['lower_bound']>=3 or completed%20==0:
            print(json.dumps({'completed':completed,'family':len(trials),'hc':result['hc'],
                              'lower_bound':result['lower_bound'],'status':result['status']}),flush=True)
    print(json.dumps({'run_id':run_id,'completed':completed,'family':len(trials),
                      'seconds':round(time.monotonic()-start,4)}),flush=True)


if __name__=='__main__':
    main()
