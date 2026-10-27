# Inverse repair pilot — 2026-10-27

## Outcome

Implemented partial-patch export, independent geometry inspection, and a SAT
inverse-design prototype. No new Hc=5 tile was found. The widest tested local
models were definitively UNSAT rather than timed out. This is not a negative
result about all edits, all layouts or the existence of Hc=5 polyforms.

## A correctness issue found by exporting the actual patch

The legacy scorer's claimed 5/169 minimum for our 21-cell Hc=4 tile used a patch
with a hole in its fourth ring. Its numerical optimization was exact for a
relaxation that omitted a needed constraint; it was not a valid fifth-corona
near miss. The independent verifier caught this when inspecting copy transforms.
The existing Hc=4 witness still passes and the tile's classification is unchanged.

Version 2 checks every inner prefix with the checker library's hole finder and
excludes any holed prefix assignment before accepting a defect solution. The
exclusion includes both selected and unselected prefix variables, allowing a
different solution to fill the hole without unnecessarily banning its border.
The best accepted partial patch is then checked independently in Python.

The corrected native measurement is **7 uncovered / 171 required cells**, exact
for this encoding, with a separately verified four-ring prefix (61 copies).
It took 43.927 s and 4,434.7 MB sampled peak RSS. The 16-cell reference produced
12/214, exact, with a verified four-ring prefix (65 copies), in 56.816 s and
3,532.2 MB. Other attempted 17/15-cell parents did not yield an exported patch
under their budgets; these are unknown, not evidence of a defect lower bound.
Some early diagnostic rows use the old `over-maxd` stop label even when a
conflict budget could have expired. New version-2 calls say `no-solution-found`.

All old result bytes are preserved. New version-2 scores carry `defect_version: 2`.
Search ignores legacy values for fitness and near-miss sweep admission. The
ordinary Hc labels remain valid and usable for scorer training.

## Model and validation

- One Boolean per candidate cell, shared by all transformed copies.
- Exact cardinality bounds on cell changes and tile size; minimum 18, maximum
  30 cells in this pilot.
- No pairwise overlaps. Each selected copy must contact the preceding corona.
  Every inner-copy cell's edge/corner neighbourhood must be occupied by the next
  prefix, so later rings cannot retroactively repair earlier enclosure.
- Optional shifted-copy selectors allow omission or a one-cell displacement of
  copies at chosen levels. Their occupancy is the conjunction of selector and
  shared tile-cell variable.
- Independent final checks reject disconnected/holed tiles, bad corona geometry
  and span/cell-limit violations. Invalid layouts are blocked lazily, preserving
  alternative layouts for the same tile where appropriate.
- A geometrically successful proposal is still classified by ordinary
  `sat -isohedral -maxlevel 12`. A tiler is rejected; resource caps remain unknown.

Regression fixtures include preservation of the actual Hc=4 witness, recovery
of missing inner/outer copies, and a synthetic repair where one shared boundary
cell addition repairs all nine copies. The legacy holed Hc=4 patch is a negative
fixture. Signed cardinality constraints are checked against exhaustive small
truth tables with an independent SAT oracle.

## Bounded production-shape trials

Two verified layouts (21 and 16 cells), three edit budgets (2, 4, 6), and a
two-cell-wide candidate band were used in each row:

| Placement model | Models | Outcome | Build + solver time |
| --- | ---: | --- | ---: |
| Fixed copies; original interior frozen | 6 | All UNSAT | 0.37 s |
| Fifth-ring copies optional/shiftable | 6 | All UNSAT | 3.31 s |
| Fourth/fifth rings optional/shiftable; interior editable | 6 | All UNSAT | 133.53 s |

The largest model had 703,797 variables and 2,486,232 clauses. The largest sampled
solver RSS was 613.2 MB. Fast runs' tiny/zero RSS samples are not reliable peak
measurements. No candidate reached the classification stage. The one-hour
ceiling was unnecessary because all 18 models finished decisively.

Files:

- `results/repair_layouts_20261027.jsonl`: initial legacy exports, including the
  holed layout; retain as diagnostic evidence.
- `results/repair_layouts_checked_20261027.jsonl`: version-2 exports and independent
  checks, plus unsuccessful export attempts.
- `results/repair_checked_{fixed,shifted,two_rings}_20261027.jsonl`: tested models,
  run IDs, code/input/CNF hashes, caps and outcomes. The fixed file also retains
  an earlier single-layout run; compare the final completed run in each file.
- `benchmarks/2026-10-27/repair_pilot_summary.json`: summary and raw-file hashes.

The earlier radius-1 experiments on legacy layouts are retained in
`results/repair_{fixed,shifted}_20261027.jsonl`; they are not the controlled
version-2 comparison above.

## Decision

An initial construction budget screen is also implemented in
`scripts/check_hex_chain_budget.py`. In heesch-sat's sparse triangle coordinates,
the unmarked straight four-hexagon body has these best spans over grid symmetries:

| Macro-hex side in triangle edges | Triangle cells | Best span sum (max−min) |
| --- | ---: | ---: |
| 1 | 24 | 26 |
| 2 | 96 | 56 |
| 3 | 216 | 86 |

Thus the side-2 body already exceeds span 29 even though its cell count fits.
The side-3 body exceeds both limits. This checks unmarked bodies only; it does
not prove that every marked, compressed or alternate-grid realization fails.
It does show why the plan's 96-triangle cell-count example is insufficient as
a feasibility argument. The exact sparse-cell construction and arithmetic have
three regression tests. Raw results and source hash are in
`benchmarks/2026-10-27/hex_chain_budget.json`.

Keep this as a tested experimental tool. Do not spend another night increasing
time on these unchanged UNSAT instances. The next strategic work is a marked
construction: reproduce Mann's rules, check realization budgets, and use the
inverse solver to compile/repair compact geometry around that mechanism. Broader
placement freedoms can be tested later when a concrete construction or failure
case motivates them. No ANER changes were needed for this pilot.

## Positive control (2026-10-27, cloud x86, 4 cores)

The pilot never showed the tool can succeed on a case with a known answer, so
its UNSAT results were uninterpretable. Control inputs come from Kaplan's
enumerated polyhexes (`results/seeds_kaplan_hex_3up.jsonl`, 11–17 cells):

- **No Hc=3 polyhex is one edit (add, remove or move one cell) from an Hc=4
  polyhex.** The same holds for our 21-cell Hc=4 tile: its 38 valid add/remove
  neighbours classify as 14 isohedral, Hc=0 ×3, Hc=1 ×19 and Hc=2 ×2. Hc=4
  shapes are isolated peaks.
- 22 Hc=3 shapes are two edits from an Hc=4 shape
  (`scripts/repair_control_pairs.py`). 20 exported a v2 defect patch
  (`results/repair_control_kaplan_patches_20261027.jsonl`).

`patch_repair.py` at 2/4/6 changed cells on all 20 layouts, both in the default
fixed regime and in the widest regime (`--radius 2 --outer-shifts 1
--shift-from-level 3 --free-interior`): **120/120 models UNSAT, zero
proposals** (`results/repair_control_kaplan_{fixed,wide}_20261027.jsonl`).
The three closest archive near misses (22 cells 1/163, 21 cells 2/218,
19 cells 2/148) were also UNSAT in both regimes. Encoding sanity check: on the
layout whose ring is already covered (0/133), the same model with 0 edits and
`require_change=False` is SAT, so the UNSATs are not an encoding failure.

**Conclusion:** a known two-edit improvement is not reachable by repairing the
parent's own partial patch, even with outer shifts. The improved shape's
coronas use different placements. Fixed-layout inverse repair should not be
used as a generator for Hc=4→5. A useful version must let the layout change
with the tile (for example, search over placements as well as cells, as
heesch-sat does); until then, the layout-free two-edit sweep is the better
tool.
