"""Check every one-cell edit (add/remove/move) of hex-grid hexapillar realizations (k=2).

Usage: python3 scripts/construction_hexapillar_sweep.py . OUT.jsonl 4,5
Needs the heesch-sat build that halo/runner.py uses. CONSTRUCTION_PILOT.md has the counts."""
import sys, json, time, collections
sys.path.insert(0, sys.argv[1] + "/halo")
import hexapillar as hp, shape as shp
from concurrent.futures import ThreadPoolExecutor, as_completed
k = 2; out = open(sys.argv[2], "a")
for n in map(int, sys.argv[3].split(",")):
    cells, _, _ = hp.hexapillar(n, k)
    s = set(cells); nb = shp.NEIGHBOURS["H"]
    edits = set()
    for f in {(x+dx, y+dy) for x, y in s for dx, dy in nb} - s:
        edits.add(frozenset(s | {f}))
    for c in s:
        rest = s - {c}; edits.add(frozenset(rest))
        for f in {(x+dx, y+dy) for x, y in rest for dx, dy in nb} - rest - {c}:
            edits.add(frozenset(rest | {f}))
    lines = set()
    for e in edits:
        ok, pr, _ = shp.check(shp.fmt("H", sorted(e)))
        if ok and not any("stricter" in p for p in pr):
            lines.add(shp.canonical("H", sorted(e)))
    print(f"n={n}: {len(lines)} valid one-edit variants", flush=True)
    t = time.time(); tally = collections.Counter(); best = []
    with ThreadPoolExecutor(2) as pool:
        futs = {pool.submit(hp.classify, l, 7, 600, 3000): l for l in lines}
        for f in as_completed(futs):
            r = f.result(); r.pop("record", None); l = futs[f]
            key = r["status"] if r["status"] != "nontiler" else f"Hc={r['hc']}"
            tally[key] += 1
            out.write(json.dumps({"n": n, "k": k, "canon": l, **{x: r.get(x) for x in ("status", "hc", "hh", "seconds")}}) + "\n"); out.flush()
            if r["status"] == "nontiler" and (r["hc"] or 0) >= 3:
                best.append((r["hc"], l)); print(f"  Hc={r['hc']}: {l}", flush=True)
    print(f"n={n}: {dict(tally)} in {time.time()-t:.0f}s", flush=True)
