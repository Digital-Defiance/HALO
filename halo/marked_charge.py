#!/usr/bin/env python3
"""Search a bounded marked-hex model designed from a target charge upper bound.

A tile has six scalar edge charges; adjacent charges must sum to zero. Rotations
and reflections are allowed. Complete coronas are hex-lattice balls. Internal
charges cancel, so delta*N(r) <= cap*P(r) is necessary. This is a marked lattice
model, not an unmarked-polyform construction or a Heesch record claim.
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
import uuid

sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import patch_repair as repair
import runner
import shape

DIRS=((1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1))


def ball(radius):
    if type(radius) is not int or radius < 0:
        raise ValueError('nonnegative integer radius required')
    return sorted((x,y) for x in range(-radius,radius+1) for y in range(-radius,radius+1)
                  if abs(x+y)<=radius)


def counts(radius):
    return 1+3*radius*(radius+1),6*(2*radius+1)


def charge_upper_bound(net,cap):
    if type(net) is not int or type(cap) is not int or not 0 < net <= 6*cap:
        raise ValueError('need positive integer net<=6*cap')
    r=0
    while True:
        n,p=counts(r)
        if net*n>cap*p:
            return r-1
        r+=1


def label_charge_certificate(word):
    """Reweight each complementary label pair to expose the strongest imbalance.

    Matching depends on labels being opposites, not their numeric magnitude.
    Give a pair weight +/-1 according to its multiplicity imbalance, and zero
    to balanced pairs. Thus any unbalanced one-hex word has net>=1 at cap=1,
    giving at most three complete lattice coronas. A chosen weaker bound of
    seven cannot overcome this stronger certificate.
    """
    weights={0:0}
    net=0
    for label in sorted({abs(q) for q in word if q}):
        imbalance=word.count(label)-word.count(-label)
        sign=(imbalance>0)-(imbalance<0)
        weights[label]=sign
        weights[-label]=-sign
        net+=abs(imbalance)
    return {'weights':weights,'net':net,'cap':1,
            'upper_bound':charge_upper_bound(net,1) if net else None}


def orientations(word):
    if len(word)!=6 or any(type(q) is not int for q in word):
        raise ValueError('six integer charges required')
    out=[]
    for a,b,d,e in shape.SYMMETRIES['H']:
        values=[0]*6
        for i,(x,y) in enumerate(DIRS):
            values[DIRS.index((a*x+b*y,d*x+e*y))]=word[i]
        value=tuple(values)
        if value not in out:
            out.append(value)
    return out


def patterns(cap,net):
    if type(cap) is not int or cap<1 or (2*cap+1)**6>2000000 or net<1:
        raise ValueError('invalid/too large enumeration bounds')
    seen=set()
    for word in itertools.product(range(-cap,cap+1),repeat=6):
        if sum(word)!=net or max(map(abs,word))!=cap:
            continue
        canon=min(orientations(word))
        if canon not in seen:
            seen.add(canon)
            yield canon


class MarkedModel:
    def __init__(self,word,radius):
        self.word=tuple(word)
        self.radius=radius
        self.cells=ball(radius)
        occupied=set(self.cells)
        self.words=orientations(word)
        self.adj={p:[((p[0]+dx,p[1]+dy),d) for d,(dx,dy) in enumerate(DIRS)
                     if (p[0]+dx,p[1]+dy) in occupied] for p in self.cells}
        self.compat=[[{t for t,T in enumerate(self.words) if W[d]+T[(d+3)%6]==0}
                      for W in self.words] for d in range(6)]
        self.domains={p:set(range(len(self.words))) for p in self.cells}
        self.domains[(0,0)]={0}  # global D6 symmetry gauge
        todo=collections.deque((p,q,d) for p in self.cells for q,d in self.adj[p])
        self.contradiction=None
        while todo:
            p,q,d=todo.popleft()
            allowed={s for s in self.domains[p] if self.compat[d][s]&self.domains[q]}
            if allowed==self.domains[p]:
                continue
            self.domains[p]=allowed
            if not allowed:
                self.contradiction=p
                break
            for neighbour,e in self.adj[p]:
                if neighbour!=q:
                    todo.append((neighbour,p,(e+3)%6))
        self.cnf=repair.CNF()
        self.variables={}
        if self.contradiction is not None:
            self.cnf.add([])
            return
        for p in self.cells:
            vs=[]
            for s in sorted(self.domains[p]):
                v=self.cnf.variable()
                self.variables[p,s]=v
                vs.append(v)
            self.cnf.add(vs)
            for a,b in itertools.combinations(vs,2):
                self.cnf.add([-a,-b])
        for p in self.cells:
            for q,d in self.adj[p]:
                if p>=q:
                    continue
                for s in self.domains[p]:
                    for t in self.domains[q]-self.compat[d][s]:
                        self.cnf.add([-self.variables[p,s],-self.variables[q,t]])

    def decode(self,positive):
        assignment={}
        for p in self.cells:
            choices=[s for s in self.domains[p] if self.variables[p,s] in positive]
            if len(choices)!=1:
                raise ValueError('invalid orientation assignment')
            assignment[p]=choices[0]
        return assignment


def verify_assignment(word,radius,assignment):
    """Check local matching and the full boundary-charge identity independently."""
    words=orientations(word)
    cells=set(ball(radius))
    if set(assignment)!=cells:
        raise ValueError('assignment must cover exactly the lattice ball')
    if any(type(s) is not int or not 0<=s<len(words) for s in assignment.values()):
        raise ValueError('invalid orientation index')
    boundary=[]
    for (x,y),s in assignment.items():
        for d,(dx,dy) in enumerate(DIRS):
            q=x+dx,y+dy
            if q in cells:
                if words[s][d]+words[assignment[q]][(d+3)%6]!=0:
                    raise ValueError('unmatched internal edge')
            else:
                boundary.append(words[s][d])
    n,p=counts(radius)
    if len(cells)!=n or len(boundary)!=p or sum(boundary)!=sum(word)*n:
        raise ValueError('boundary-charge identity failed')
    return {'tiles':n,'boundary_edges':p,'boundary_charge':sum(boundary),
            'capacity':max(map(abs,word))*p}


def classify(word,maxlevel=7,seconds=2,mem_mb=256,reserve_mb=8000):
    cap=max(map(abs,word));net=sum(word)
    upper=charge_upper_bound(net,cap)
    checks=[]
    lower=0
    for level in range(1,min(maxlevel,upper)+1):
        start=time.monotonic()
        model=MarkedModel(word,level)
        if model.contradiction is not None:
            result={'status':'unsat','method':'arc-consistency','contradiction_cell':model.contradiction,
                    'seconds':round(time.monotonic()-start,4)}
        else:
            build=time.monotonic()-start
            result=repair.solve_cnf(model.cnf,timeout=seconds,mem_mb=mem_mb,reserve_mb=reserve_mb)
            result.update(method='sat',build_seconds=round(build,4))
            positive=result.pop('positive',None)
            if positive is not None:
                assignment=model.decode(positive)
                result['verified']=verify_assignment(word,level,assignment)
                result['assignment']=[[x,y,s] for (x,y),s in sorted(assignment.items())]
        checks.append(dict(level=level,**result))
        if result['status']=='unsat':
            return {'status':'classified','hc':level-1,'lower_bound':lower,'upper_bound':level-1,
                    'charge_upper_bound':upper,'checks':checks}
        if result['status']!='sat':
            return {'status':'unresolved','hc':None,'lower_bound':lower,'upper_bound':upper,
                    'charge_upper_bound':upper,'checks':checks}
        lower=level
    exact=lower==upper
    return {'status':'classified' if exact else 'bounded-lower','hc':lower if exact else None,
            'lower_bound':lower,'upper_bound':upper,'charge_upper_bound':upper,'checks':checks}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cap',type=int,default=2)
    ap.add_argument('--net',type=int,default=1)
    ap.add_argument('--maxlevel',type=int,default=7)
    ap.add_argument('--out',required=True)
    ap.add_argument('--seconds',type=float,default=2)
    ap.add_argument('--mem-mb',type=float,default=256)
    ap.add_argument('--reserve-mb',type=float,default=8000)
    ap.add_argument('--total-seconds',type=float,default=60)
    args=ap.parse_args()
    if (args.maxlevel<1 or any(not math.isfinite(v) or v<=0 for v in
            (args.seconds,args.mem_mb,args.total_seconds))
            or not math.isfinite(args.reserve_mb) or args.reserve_mb<0):
        ap.error('invalid search/resource bounds')
    upper=charge_upper_bound(args.net,args.cap)
    words=list(patterns(args.cap,args.net))
    run_id=uuid.uuid4().hex
    runner.ensure_jsonl_boundary(args.out)
    done=set()
    if Path(args.out).exists():
        with open(args.out) as f:
            for line in f:
                row=json.loads(line)
                if (row.get('experiment')=='marked-hex-charge-v1' and row.get('cap')==args.cap
                        and row.get('net')==args.net and row.get('maxlevel')==args.maxlevel
                        and row.get('status')=='classified'):
                    done.add(tuple(row['word']))
    start=time.monotonic();completed=0;hist=collections.Counter()
    for word in words:
        if word in done:
            continue
        if time.monotonic()-start>=args.total_seconds:
            break
        result=classify(word,args.maxlevel,args.seconds,args.mem_mb,args.reserve_mb)
        row={'experiment':'marked-hex-charge-v1','run_id':run_id,'ts':time.time(),
             'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'cap':args.cap,'net':args.net,'word':word,'maxlevel':args.maxlevel,
             'family_patterns':len(words),'limits':vars(args),**result,
             'qualification':'Exact only in the edge-matched regular-hex lattice model. '
                 'Not an unmarked-polyform construction or a record claim.'}
        with open(args.out,'a') as f:
            f.write(json.dumps(row)+'\n')
        completed+=1;hist[str(result['hc'])]+=1
        if result['lower_bound']>=3 or completed%25==0:
            print(json.dumps({'completed':completed,'family':len(words),'word':word,
                              'hc':result['hc'],'lower_bound':result['lower_bound']}),flush=True)
    print(json.dumps({'run_id':run_id,'family':len(words),'already_classified':len(done),
        'new_attempts':completed,'hc_histogram':dict(hist),'charge_upper_bound':upper,
        'seconds':round(time.monotonic()-start,4)}),flush=True)


if __name__=='__main__':
    main()
