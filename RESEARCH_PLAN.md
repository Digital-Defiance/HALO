# Experiments for reaching Hc=5–7 sooner

2026-10-27. These are research priorities, not measured discovery-rate gains.
The goal remains a connected, hole-free tile accepted under `SPEC.md` §1.

## Execution order and checkpoints

The immediate milestone is a certified Hc>=5 non-tiler. Work toward Hc>=6 and
Hc>=7 follows from a working method; no discovery date is predicted.

1. **Build the patch exporter and independent diagnostic checks.** Export a
   partial fifth-corona layout, all copy transforms and uncovered coordinates.
   Independently recompute the gap count, overlaps, corona contacts and inner
   patch geometry. Check the 21-cell parent's recorded 5/169 result when the
   same optimum/layout is reproduced; equal minimum gap counts can have
   different ring sizes. Gate: a trustworthy machine-readable repair input,
   plus positive and negative regression fixtures. Existing scalar defect
   output alone is insufficient.
2. **Build and run one bounded inverse-repair pilot.** Start with fixed
   placement layouts and shared shape-cell variables. Try edit budgets of
   2, 4 and 6 cells, beginning with one layout and widening to at most four.
   Proposed first compute budget: one hour, one large solver at a time, up to
   20 GB per solver, retaining the system headroom safeguard. This is an
   experiment budget, not an implementation-time estimate. Check every proposed
   tile with the normal classifier and independently verify any claimed corona
   improvement. Record genuine UNSAT results separately from resource caps.
   Gate: validated distinct proposals or a precise account of which bounded
   layout/edit spaces failed. No Hc=5 in this pilot does not refute the method.
3. **Evaluate once before widening the search.** Compare checker cost and new
   Hc>=4/5 discoveries with the existing sweep control. If fixed layouts block
   repair, choose another partial patch or allow limited placement changes;
   do not just increase CPU time on an unchanged failed model. Reserve enough
   exploration to detect different shape families. The two-edit sweep remains
   a bounded background control; no running job should be stopped merely to
   write or test the exporter.
4. **Develop a construction after this first implementation cycle.** Extract
   Mann's marked hexapillar rules and reproduce the known behaviour. Calculate
   the exact cell/span budget of a proposed unmarked realization before
   expensive classification. Combine a verified weak imbalance/density
   obstruction with compact boundary matching codes and the inverse solver.
   Gate: retain intended fits, exclude unintended escape fits, satisfy shape
   limits and produce complete verified early coronas. A successful marked
   construction alone does not meet the unmarked-tile goal.

Keep ANER and the existing scoring backend as they are during the first pilot.
Full first-corona enumeration, GPU growth simulation, new neural architectures
and broader multidimensional experiments remain follow-ups, contingent on a
specific bottleneck or a small pilot demonstrating useful ranking information.

The next concrete deliverable is working, tested patch export and an
inverse-repair prototype. Those tools are not yet implemented.

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

## Cross-domain combinations worth testing

These are proposed transfers of ideas, not reductions that solve the Heesch
problem. Physical systems with elastic strain, temperature or reversible bonds
have different rules from rigid, gap-free polyform coronas.

### Self-limiting assembly + conservation laws + inverse design

Materials physics studies assemblies whose local preferences become harder to
satisfy as their size grows. The useful transfer is to deliberately design weak
incompatibility that permits several complete coronas but excludes unlimited
growth. Equilibrium preference for a finite physical aggregate does not itself
prove a hard geometric growth limit.

An exact discrete starting point is an additive boundary charge. Give matching
edge features opposite weights so their contributions cancel at an internal
join. A tile with nonzero net charge contributes that charge every time it is
copied; the boundary must carry the total. Mann discusses a concrete bump/nick
counting obstruction, while Bašić's H=6 non-tiling argument uses incompatible
densities of hexagons and triangles. Describing both as an explicit counter
program is only an analogy, not the argument established by these papers.

Research experiment: choose a marked family with a weak imbalance or a verified
density obstruction, and use inverse SAT to seek complete early coronas. Search
for useful conserved weights with linear constraints on legal matches. Any
proposed obstruction must hold for every allowed rotation, reflection and fit;
it must not assume a regular corona outline. A necessary inequality or an upper
bound cannot prove that the desired early coronas actually exist. Use a witness
for that side of the argument.

Primary sources:

- Hackney, Amey and Grason, *Dispersed, condensed and self-limiting states of
  geometrically frustrated assembly* (2023):
  <https://arxiv.org/abs/2303.02121>.
- Mann and Bašić references: `refs/README.md`.

### Coding theory + geometric realization

Treat each intended boundary match as a short complementary code, realized by
tabs and notches. Search for profiles that permit intended joins while excluding
unintended label pairs, shifted fits and reflected fits. Minimize the geometric
cost of those profiles subject to the 200-cell/span constraints.

This is an analogy to synchronization/error-detecting codes, not a claim that
Hamming distance alone controls geometric fitting. Test actual relative grid
placements, including partial and multi-edge contacts. A correct marked rule
system is not enough if its unmarked realization introduces escape routes.
This is a proposed way to attack Track B's main realization bottleneck.

### Program synthesis + counterexample-driven repair

Use a candidate generator and a verifier in a feedback loop. A gap, collision,
unwanted fit or actual periodic tiling can supply a concrete reason to change
the geometric sketch. Where expressible soundly, add a constraint that excludes
other candidates with the same failure. An UNSAT core of one fixed patch is not
automatically a valid restriction on unrelated patches or shapes; a timeout is
not a counterexample.

This is the counterexample-guided synthesis pattern applied to the inverse
design experiment above. It is closer to synthesizing a small constrained
program than training a score and hoping that its largest prediction is valid.
Begin with our Hc=4 partial fifth-corona layout before building general marked
rule synthesis.

Primary source: Solar-Lezama et al., *Combinatorial Sketching for Finite Programs*
(2006), <https://people.eecs.berkeley.edu/~sseshia/pubdir/asplos06-final.pdf>.

### Statistical mechanics: continuation diversity, not unrestricted counting

The pinned checker supports `allCoronas`, but its own comment marks the method
deprecated and highly inefficient. Enumerating every first corona is not a
reliably cheap or one-hour task, and a large count could simply select tilers.

Proposed bounded pilot: sample a small size-matched set of known Hc=1,2,3,4
shapes and proven tilers; cap time, memory and the number of distinct first/second
coronas. Measure how often sampled patches extend another one or two levels,
along with diversity and solver cost. Report censored counts/timeouts explicitly;
SAT enumeration order does not give uniform samples. Validate ranking on held-out
parent families before running this on hundreds of archive shapes.

Randomized GPU growth can be a proposal/feature source, but may miss rare valid
extensions or strongly prefer tilers. Validate every claimed complete corona.
Failed rollouts do not prove a finite Heesch number or an upper bound. The GPU
is not necessarily idle: the current MLX scorer already uses it.

### Higher dimensions: borrow certificates, not projected shapes

A new preprint by Džuklevski, submitted 2026-10-01, compares prototile frequencies
in perpendicular planar sections to establish finite Heesch numbers for certain
3D prisms: <https://arxiv.org/abs/2610.02579>. Its abstract does not supply a 2D
Hc=7 tile. The useful question is whether analogous competing frequency
constraints can be engineered in a planar marked family. Projection or slicing
does not automatically preserve congruent copies, non-overlap or coronas.

Height functions and tiling-group invariants may provide additional certificates
in suitable families, but they are not generic predictors of a shape's Heesch
number. A cycle or modulo counter alone can repeat forever; an engineered clock
needs a genuine finite-growth obstruction.

The practical combined pipeline is: specify a weak but provable incompatibility,
compile intended matches into compact geometry, synthesize coordinated edits,
and feed exact checker counterexamples back into the sketch. None of these
cross-domain experiments has yet demonstrated a discovery-rate improvement.
