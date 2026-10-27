#!/usr/bin/env python3
"""Positive-control inputs for halo/patch_repair.py (2026-10-27).

Finds every Hc=3 polyhex in Kaplan's enumerated set that is at most two one-cell
edits (add, remove or move) from an Hc=4 polyhex in the same set; none is one edit away.
Usage: python3 scripts/repair_control_pairs.py results/seeds_kaplan_hex_3up.jsonl OUT.jsonl
"""
import json,sys,collections
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'halo')); import shape as shp
rs=[json.loads(l) for l in open(sys.argv[1])]
canon={}
for r in rs:
    s=r.get('canon') or r['shape']; g,c=shp.parse(s); canon[shp.canonical(g,c)]=r
NB=[(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]
def edits(c):
    out=set()
    for x in c: out.add(frozenset(c-{x}))
    bd={(x[0]+d[0],x[1]+d[1]) for x in c for d in NB}-c
    for n in bd: out.add(frozenset(c|{n}))
    for x in c:
        for n in bd: out.add(frozenset((c-{x})|{n}))
    return out
res=collections.Counter(); ex=[]
for k,r in canon.items():
    if r.get('hc')!=4: continue
    g,c=shp.parse(k); c=frozenset(map(tuple,c))
    d1=edits(c); seen=set()
    for s1 in d1:
        for s2 in edits(set(s1)):
            if s2 in seen: continue
            seen.add(s2)
            if not s2: continue
            s=sorted(s2)
            if len(s)<11 or len(s)>17: continue
            if not shp.connected(g,s) or shp.has_hole(g,s): continue
            kk=shp.canonical(g,s)
            h=canon.get(kk,{}).get('hc')
            if h==3: res[k]+=1; ex.append((kk,k))
print({k[:30]:v for k,v in res.items()}, len(set(ex)))
with open(sys.argv[2],'w') as f:
    for a,b in sorted(set(ex)):
        r=dict(canon[a]); r['canon']=a; r['shape']=a; r['cells']=(len(a.split())-1)//2; r['hc4_neighbour']=b
        [r.pop(x,None) for x in ('defect','ring','defect_exact','defect_version','defect_seconds')]
        f.write(json.dumps(r)+'\n')
