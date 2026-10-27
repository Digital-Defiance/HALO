# Experiments for reaching Hc=5–7 sooner

2026-10-27. These are research priorities, not measured discovery-rate gains.
The goal remains a connected, hole-free tile accepted under `SPEC.md` §1.

## What the overnight result supports

The overnight run spent 1.49 million of its 2.25 million checks on random
mutants. The one-edit sweep produced 275 of 296 Hc=3 finds from only 86,237
checks, then exhausted its available neighbourhoods. This supports testing
targeted proposals before committing another full night to the same mix.
It does not demonstrate that any proposal will reach Hc=5.

One Hc=4 among roughly 700 Hc=3 discoveries does not establish the probability
of Hc=5 conditional on Hc=4. The generators, neighbourhoods and shape sizes are
different and correlated. The earlier 10^8–10^9-check, weeks-to-months figure
is a speculative scenario, not a waiting-time forecast or guarantee.

## First research experiment: inverse design from a partial fifth corona

Instead of mutating a tile and then discovering its coronas, solve for tile
occupancy and a surrounding patch together. This is an unimplemented hypothesis.
It could find coordinated edits that random one-cell mutations almost never
make, while using a concrete failure of a known high-Hc patch as guidance.

The native diagnostic of our 21-cell Hc=4 tile found an exact minimum defect of
**5 uncovered cells out of a 169-cell required ring**, with the current defect
encoding. It took 48.804 seconds and peaked at 4,441.3 MB RSS. The append-only
record is `results/hex21_h4_defect_20261027.jsonl`. Its Hc remains exactly 4.
This is a candidate fifth-corona layout to inspect, not a witness for Hc=5.

Implement in this order:

1. Export the defect solver's best partial patch, its transforms and actual
   uncovered cell coordinates. `minDefect(..., patch_t *soln)` already exposes
   a patch internally; the driver currently discards it. Recompute its coverage
   independently before using it as an optimizer input.
2. Keep those transforms fixed initially. Let Boolean variables describe cells
   in a small region around the original tile's boundary, freezing an interior
   anchor and minimizing changes. Every placed copy must use exactly the same
   variables transformed by its own placement.
3. Forbid overlaps between every pair of copies. If an inner-copy cell is
   occupied, require every neighbouring cell to be occupied by the whole patch.
   In a fixed placement layout these constraints can be encoded as Boolean
   clauses over the shared shape variables. Search edit budgets beyond the
   existing two-edit ball without enumerating every combination.
4. Reject empty, disconnected, holed or out-of-budget tiles and verify corona
   contacts, enclosure and holes independently. Local coverage constraints
   alone do not prove all of these global properties. Block rejected occupancy
   patterns and continue within a bounded experiment.
5. Classify each valid proposal with ordinary `sat -isohedral`, then obtain a
   complete witness and verify it. A solution that tiles the plane is rejected;
   designing a large patch alone is not proof of a finite Heesch number.
6. If one fixed layout is UNSAT, try other partial patches or allow placement
   alternatives. That failure excludes only that layout/edit region; it says
   nothing about the existence of Hc=5 generally.

Stop the first prototype after a fixed engineering/compute budget if it cannot
produce valid distinct candidates. Record candidate count, complete checker
outcomes and wall time. A success gate is a separately verified five-ring
non-tiler. Only then extend the experiment to six or seven rings.

## Construction work alongside the targeted search

Mann's PDF is now in `refs/`; the author-hosted source and checksum are recorded
in `refs/README.md`. Bašić's full text and figures are accessible through PMC.
There is no need to wait for the owner to provide Mann's paper.

Reproduce the marked hexapillar's neighbour rules and known H=4/H=5 behaviour
before optimizing a realization. Determine the exact grid cell count and
coordinate span before an expensive SAT run. Treat preserving intended fits,
eliminating unintended fits, and staying inside 200 cells/span 29 as separate
acceptance gates. The handoff's proposed 130–170-cell realization has not been
built or validated. The H=5 and H=6 papers give mechanisms to learn from, not
a construction of Hc=7 or an automatic conversion to a qualifying polyform.

## Immediate background experiment

Use the existing two-edit sweep around Hc>=4 parents and selected near misses
as a bounded next experiment. A low defect on an Hc=3 parent is a lead toward
Hc=4; it is not a direct measure of closeness to Hc=5. Keep some scored/random
exploration, since restricting everything to one successful family can miss
other mechanisms. Compare the generator's new high-Hc discoveries and total
generation/checker time before choosing a larger allocation.

Do not retrain only for Hc>=2 AUC and assume it optimizes records. A future
proposal scorer should evaluate ranking of Hc>=3/4 and defect improvements on
held-out parent families or later runs, with diversity and an exploration arm.
Random row splits can overstate generalization when close relatives appear in
both training and validation sets.

No additional ANER throughput tuning is a prerequisite for these experiments.
