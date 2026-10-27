#!/usr/bin/env python3
"""Capped marked-polyhex controls with independent geometry and label checks.

Ordinary unmarked classifiers remain unchanged and require -isohedral. This
isolated symbolic model adds complementary boundary labels and disables the
geometry-only tiling shortcuts, which cannot certify marked tilings.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import marked_charge
import patch_repair as repair
import runner
import shape
import verify

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_BINARY=ROOT/'build'/platform.system()/'heesch-sat-marked-v1'/'marked'


def boundary_marks(cells,marks=()):
    cells=set(map(tuple,cells))
    result={(x,y,dx,dy):0 for x,y in cells for dx,dy in marked_charge.DIRS
            if (x+dx,y+dy) not in cells}
    seen=set()
    for x,y,dx,dy,q in marks:
        edge=x,y,dx,dy
        if edge not in result or edge in seen or type(q) is not int:
            raise ValueError('invalid/duplicate boundary mark')
        seen.add(edge);result[edge]=q
    return result


def mann_pillar(n):
    if type(n) is not int or not 1<=n<=20:
        raise ValueError('pillar length outside bounded controls')
    cells=[(i,0) for i in range(n)]
    marks=boundary_marks(cells)
    for i in range(n):
        for d in (1,2,4,5):
            dx,dy=marked_charge.DIRS[d]
            marks[i,0,dx,dy]=-1 if d in (1,2) else 1
    marks[n-1,0,1,0]=-1
    return cells,[[*edge,q] for edge,q in sorted(marks.items())]


def verify_patch(cells,marks,placements,level):
    ok,message=verify.verify(repair.witness_text('H',cells,placements,level))
    if not ok:
        raise ValueError('geometry: '+message)
    labels=boundary_marks(cells,marks)
    occupied={}
    world={}
    for copy,(lev,a,b,tx,d,e,ty) in enumerate(placements):
        T=a,b,tx,d,e,ty
        for p in cells:
            occupied[repair.transform(T,p)]=copy
        for (x,y,dx,dy),q in labels.items():
            u,v=repair.transform(T,(x,y))
            du,dv=a*dx+b*dy,d*dx+e*dy
            world[u,v,du,dv]=q
    exposed=[];contacts=0
    for (x,y,dx,dy),q in world.items():
        neighbour=x+dx,y+dy
        if neighbour in occupied:
            if q+world[neighbour[0],neighbour[1],-dx,-dy]!=0:
                raise ValueError('boundary marks do not match')
            contacts+=1
        else:
            exposed.append(q)
    if sum(exposed)!=len(placements)*sum(labels.values()):
        raise ValueError('boundary-charge identity failed')
    return {'geometry':message,'copies':len(placements),'matched_edges':contacts//2,
            'exposed_edges':len(exposed),'boundary_charge':sum(exposed),
            'net_charge_per_tile':sum(labels.values())}


def run(cells,marks,maxlevel=7,seconds=20,mem_mb=1000,reserve_mb=8000,
        conflicts=2000000,binary=DEFAULT_BINARY):
    if (not 1<=maxlevel<=12 or conflicts<1
            or any(not math.isfinite(v) or v<=0 for v in (seconds,mem_mb))
            or not math.isfinite(reserve_mb) or reserve_mb<0):
        raise ValueError('invalid marked solver limits')
    ok,problems,_=shape.check_cells('H',cells)
    if not ok or any('stricter' in p for p in problems):
        raise ValueError('invalid body: '+'; '.join(problems))
    labels=boundary_marks(cells,marks)
    payload=(str(len(cells))+'\n'+'\n'.join(f'{x} {y}' for x,y in cells)+'\n'
             +str(len(labels))+'\n'+'\n'.join(' '.join(map(str,(*edge,q)))
             for edge,q in sorted(labels.items()))+'\n')
    budget=runner.MemoryBudget(mem_mb,reserve_mb)
    if not budget.may_start():
        return {'status':'memory-pressure','hc':None,'lower_bound':0,'levels':[]}
    start=time.monotonic();peak=0;stopped=None
    with tempfile.TemporaryDirectory(prefix='halo-marked-run-') as folder:
        path=Path(folder)/'input'
        path.write_text(payload)
        with path.open() as inp,(Path(folder)/'stdout').open('w+') as out,(Path(folder)/'stderr').open('w+') as err:
            proc=subprocess.Popen([str(binary),str(maxlevel),str(conflicts)],stdin=inp,
                                  stdout=out,stderr=err,close_fds=False)
            budget.register(proc.pid,priority=mem_mb)
            try:
                while proc.poll() is None:
                    rss=runner.rss_mb(proc.pid) or 0;peak=max(peak,rss)
                    if rss>mem_mb:stopped='memout'
                    elif budget.stop_reason(proc.pid,rss):stopped='memory-pressure'
                    elif time.monotonic()-start>seconds:stopped='timeout'
                    if stopped:
                        proc.kill();break
                    try:proc.wait(timeout=.05)
                    except subprocess.TimeoutExpired:pass
            finally:
                if proc.poll() is None:proc.kill()
                proc.wait();budget.unregister(proc.pid)
            out.seek(0);raw=out.read()
            err.seek(0);diagnostic=err.read()[-2000:]
    levels=[];lower=0
    for line in raw.splitlines():
        try:row=json.loads(line)
        except json.JSONDecodeError:
            if stopped:break
            raise
        if (row['level']!=len(levels)+1 or row['status'] not in ('sat','unsat','unknown')
                or levels and levels[-1]['status']!='sat'):
            raise ValueError('invalid marked solver sequence')
        if row['status']=='sat':
            row['verification']=verify_patch(cells,marks,row['placements'],row['level'])
            lower=row['level']
        levels.append(row)
    status=stopped or ('solver-error' if proc.returncode else
        'classified-in-marked-grid' if levels and levels[-1]['status']=='unsat' else 'unresolved')
    return {'status':status,'hc':lower if status=='classified-in-marked-grid' else None,
            'lower_bound':lower,'levels':levels,'seconds':round(time.monotonic()-start,4),
            'peak_rss_mb':round(peak,1),'returncode':proc.returncode,'diagnostic':diagnostic,
            'input_sha256':hashlib.sha256(payload.encode()).hexdigest(),
            'binary_sha256':hashlib.sha256(Path(binary).read_bytes()).hexdigest()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pillars',nargs='+',type=int,default=[2,4])
    ap.add_argument('--out',required=True)
    ap.add_argument('--maxlevel',type=int,default=7)
    ap.add_argument('--seconds',type=float,default=20)
    ap.add_argument('--mem-mb',type=float,default=1000)
    ap.add_argument('--reserve-mb',type=float,default=8000)
    args=ap.parse_args()
    if (args.maxlevel<1 or any(not math.isfinite(v) or v<=0 for v in (args.seconds,args.mem_mb))
            or not math.isfinite(args.reserve_mb) or args.reserve_mb<0):
        ap.error('invalid limits')
    if not DEFAULT_BINARY.exists():ap.error('run bash scripts/setup_marked_polyforms.sh first')
    run_id=uuid.uuid4().hex
    runner.ensure_jsonl_boundary(args.out)
    for n in args.pillars:
        cells,marks=mann_pillar(n)
        expected=4 if n in (2,3) else 5 if n>=4 else None
        result=run(cells,marks,args.maxlevel,args.seconds,args.mem_mb,args.reserve_mb)
        row={'experiment':'marked-polyhex-pillar-control-v1','run_id':run_id,'ts':time.time(),
             'n':n,'cells':cells,'marks':marks,'expected_continuous_hc':expected,
             'limits':vars(args),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'qualification':'Edge-matched polyhex lattice model. An unmarked geometric realization '
                 'within the challenge limits has not been produced. Geometry-only tiling shortcuts disabled.',
             **result}
        row['matches_control']=result['hc']==expected if result['hc'] is not None and expected is not None else None
        with open(args.out,'a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps({k:row[k] for k in ('n','status','hc','lower_bound','seconds',
                                          'peak_rss_mb','matches_control')}),flush=True)


if __name__=='__main__':
    main()
