#!/usr/bin/env python3
"""Joint boundary-rule and corona-placement synthesis on a fixed polyhex body.

Rules are ternary (-1/flat/+1), shared by all congruent copies. A nonzero net
charge is required. A verified witness proves the requested lower bound in the
marked lattice model. No marking or placement template is supplied by default.
The unmarked geometric realization remains a separate research problem.
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
import marked_polyform as marked
import runner
import shape

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_BINARY=ROOT/'build'/platform.system()/'heesch-sat-joint-marked-v1'/'joint-marked'


def rule_domains(cells,domains=None):
    edges=sorted(marked.boundary_marks(cells))
    if domains is None:
        return edges,[7]*len(edges)
    domains=list(domains)
    if len(domains)!=len(edges) or any(type(d) is not int or not 1<=d<=7 for d in domains):
        raise ValueError('one nonempty ternary-domain bitmask required per boundary edge')
    return edges,domains


def check_solution(cells,domains,net,target,result):
    edges,domains=rule_domains(cells,domains)
    marks=result['marks']
    if (len(marks)!=len(edges) or {tuple(m[:4]) for m in marks}!=set(edges)
            or any(len(m)!=5 for m in marks)):
        raise ValueError('incomplete/invalid synthesized marking')
    labels=marked.boundary_marks(cells,marks)
    for edge,domain in zip(edges,domains):
        q=labels[edge]
        if q not in (-1,0,1) or not domain & (1<<(q+1)):
            raise ValueError('synthesized marking violates its domain')
    if sum(labels.values())!=net:
        raise ValueError('synthesized marking violates the net-charge constraint')
    return marked.verify_patch(cells,marks,result['placements'],target)


def synthesize(cells,target,domains=None,net=-1,seconds=20,mem_mb=2000,
               reserve_mb=8000,conflicts=2000000,max_rounds=256,binary=DEFAULT_BINARY,
               blocked_rules=(),fit_exclusions=()):
    if (type(target) is not int or not 1<=target<=12 or conflicts<1 or max_rounds<1
            or any(not math.isfinite(v) or v<=0 for v in (seconds,mem_mb))
            or not math.isfinite(reserve_mb) or reserve_mb<0):
        raise ValueError('invalid synthesis limits')
    cells=[tuple(p) for p in cells]
    ok,problems,_=shape.check_cells('H',cells)
    if not ok or any('stricter' in p for p in problems):
        raise ValueError('invalid fixed body: '+'; '.join(problems))
    edges,domains=rule_domains(cells,domains)
    if type(net) is not int or not net or abs(net)>len(edges):
        raise ValueError('nonzero feasible integer net charge required')
    blocked_rules=[list(word) for word in blocked_rules]
    fit_exclusions=[list(word) for word in fit_exclusions]
    if any(len(word)!=len(edges) or any(type(q) is not int or q not in (-1,0,1) for q in word)
           for word in blocked_rules+fit_exclusions):
        raise ValueError('invalid excluded rule')
    payload=(str(len(cells))+'\n'+'\n'.join(f'{x} {y}' for x,y in cells)+'\n'
             +f'{len(edges)} {net}\n'+' '.join(map(str,domains))+'\n'
             +str(len(blocked_rules))+'\n'+'\n'.join(' '.join(map(str,w)) for w in blocked_rules)+'\n'
             +str(len(fit_exclusions))+'\n'+'\n'.join(' '.join(map(str,w)) for w in fit_exclusions)+'\n')
    info={'target_level':target,'cells':cells,'domains':domains,'net_charge':net,
          'fixed_edges':sum(d in (1,2,4) for d in domains),
          'blocked_rules':blocked_rules,
          'fit_exclusions':fit_exclusions,
          'input_sha256':hashlib.sha256(payload.encode()).hexdigest()}
    budget=runner.MemoryBudget(mem_mb,reserve_mb)
    if not budget.may_start():
        return dict(info,status='memory-pressure',lower_bound=0,events=[],seconds=0)
    start=time.monotonic();peak=0;stopped=None
    with tempfile.TemporaryDirectory(prefix='halo-joint-marked-run-') as folder:
        path=Path(folder)/'input';path.write_text(payload)
        with path.open() as inp,(Path(folder)/'stdout').open('w+') as out,(Path(folder)/'stderr').open('w+') as err:
            proc=subprocess.Popen([str(binary),str(target),str(conflicts),str(max_rounds)],
                                  stdin=inp,stdout=out,stderr=err,close_fds=False)
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
            out.seek(0);raw=out.read();err.seek(0);diagnostic=err.read()[-2000:]
    events=[];result=None;expanded=0
    for line in raw.splitlines(keepends=True):
        if stopped and not line.endswith('\n'):break
        row=json.loads(line)
        if row.get('event')=='expanded':
            if result is not None or row['level']!=expanded+1 or row['level']>target:
                raise ValueError('invalid expansion sequence')
            expanded+=1
        elif row.get('event')=='result':
            if (result is not None or expanded!=target or row.get('level')!=target
                    or row.get('status') not in ('sat','unsat','unknown')):
                raise ValueError('invalid joint synthesis result')
            result=row
        else:raise ValueError('unknown joint synthesis event')
        events.append(row)
    info.update(seconds=round(time.monotonic()-start,4),peak_rss_mb=round(peak,1),
                returncode=proc.returncode,events=events,diagnostic=diagnostic,
                binary_sha256=hashlib.sha256(Path(binary).read_bytes()).hexdigest())
    lower=0
    if result and result['status']=='sat':
        info['verification']=check_solution(cells,domains,net,target,result)
        labels=marked.boundary_marks(cells,result['marks'])
        if [labels[e] for e in edges] in blocked_rules:
            raise ValueError('solver returned an excluded rule')
        if fit_exclusions:
            actual_fits=marked.legal_relative_fits(cells,result['marks'])
            gains=[]
            for word in fit_exclusions:
                reference_marks=[[*e,q] for e,q in zip(edges,word)]
                count=len(actual_fits-marked.legal_relative_fits(cells,reference_marks))
                if not count:raise ValueError('solver violated a relative-fit exclusion')
                gains.append(count)
            info['fit_gain_counts']=gains
        info['marks']=result['marks'];info['placements']=result['placements']
        lower=target
    status=stopped or ('solver-error' if proc.returncode else
                     'verified' if lower else result['status'] if result else 'solver-error')
    return dict(info,status=status,lower_bound=lower)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pillar',type=int,required=True,help='fixed number of cells in a straight hex body')
    ap.add_argument('--target',type=int,required=True,help='requested complete coronas')
    ap.add_argument('--out',required=True,help='append-only experimental JSONL')
    ap.add_argument('--seconds',type=float,default=20)
    ap.add_argument('--mem-mb',type=float,default=2000)
    ap.add_argument('--reserve-mb',type=float,default=8000)
    ap.add_argument('--conflicts',type=int,default=2000000)
    ap.add_argument('--max-rounds',type=int,default=256)
    ap.add_argument('--free-edges',help='diagnostic only: indices to free, with other edges fixed to Mann markings')
    args=ap.parse_args()
    if not 1<=args.pillar<=20:ap.error('pillar must have 1..20 cells')
    cells=[(i,0) for i in range(args.pillar)]
    domains=None
    if args.free_edges is not None:
        _,marks=marked.mann_pillar(args.pillar)
        labels=marked.boundary_marks(cells,marks)
        indices={int(i) for i in args.free_edges.split(',') if i}
        edges=sorted(labels)
        if any(not 0<=i<len(edges) for i in indices):ap.error('free-edge index out of range')
        domains=[7 if i in indices else 1<<(labels[e]+1) for i,e in enumerate(edges)]
    if not DEFAULT_BINARY.exists():ap.error('run bash scripts/setup_joint_marked.sh first')
    result=synthesize(cells,args.target,domains=domains,seconds=args.seconds,mem_mb=args.mem_mb,
                      reserve_mb=args.reserve_mb,conflicts=args.conflicts,max_rounds=args.max_rounds)
    row={'experiment':'joint-marked-synthesis-v1','run_id':uuid.uuid4().hex,'ts':time.time(),
         'limits':vars(args),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'qualification':'Fixed body; shared ternary boundary rules and all placements synthesized. '
             'Default has no supplied markings or reference layout. Optional fixed domains restrict '
             'the experiment explicitly. Marked lattice model only, not an unmarked realization.',**result}
    runner.ensure_jsonl_boundary(args.out)
    with open(args.out,'a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps({k:row[k] for k in ('run_id','target_level','fixed_edges','status','lower_bound',
                                       'seconds','peak_rss_mb','verification') if k in row}),flush=True)


if __name__=='__main__':
    main()
