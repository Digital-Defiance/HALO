"""D6-symmetric, connected, hole-free fundamental domains of the achiral sublattice m*A2
(axial coords: cosets (x mod m, y mod m)) on the hex grid, built from whole D6 orbits.

Usage: python3 scripts/construction_d6_domains.py halo M RADIUS   (e.g. halo 7 9)
CONSTRUCTION_PILOT.md: m = 5, 7, 11 up to radius 9 found no connected hole-free domain."""
import sys, itertools
sys.path.insert(0, sys.argv[1])
import shape as shp
m = int(sys.argv[2]); R = int(sys.argv[3])
def dist(p): return max(abs(p[0]), abs(p[1]), abs(p[0]+p[1]))
def syms(p):
    out=set(); x,y=p
    for a,b,d,e in shp.SYMMETRIES['H']:
        out.add((a*x+b*y, d*x+e*y))
    return frozenset(out)
cells=[(x,y) for x in range(-R,R+1) for y in range(-R,R+1) if 0<dist((x,y))<=R]
orbits=sorted({syms(p) for p in cells}, key=lambda o:(min(dist(p) for p in o), sorted(o)))
cls=lambda p:(p[0]%m, p[1]%m)
# orbits whose cells hit distinct classes
good=[o for o in orbits if len({cls(p) for p in o})==len(o) and (0,0) not in {cls(p) for p in o}]
need=m*m-1
sols=[]
def rec(i, used, chosen, size):
    if size==need:
        sols.append(list(chosen)); return
    if i==len(good) or size>need: return
    o=good[i]; c={cls(p) for p in o}
    if not (c & used):
        chosen.append(o); rec(i+1, used|c, chosen, size+len(o)); chosen.pop()
    rec(i+1, used, chosen, size)
rec(0, frozenset(), [], 0)
found=0
for sol in sols:
    S=[(0,0)]+[p for o in sol for p in o]
    line=shp.fmt('H', sorted(S))
    ok,probs,info=shp.check(line)
    if ok:
        found+=1
        print(f"m={m}: {len(S)} cells, radius {max(dist(p) for p in S)}, spans {info['span_x']}+{info['span_y']}: {sorted(S)}")
print(f"m={m}: {len(sols)} orbit selections, {found} connected and hole-free")
