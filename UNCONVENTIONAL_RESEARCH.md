# Cross-domain research experiments for Hc=5–7

2026-10-27. Primary-source review and proposed experiments. The combinations
below are HALO research hypotheses; none of these papers supplies a qualifying
Hc=7 tile or demonstrates an improvement in our discovery rate.

## What the current failures leave open

The new withheld-ring control succeeds, but its inner three rings and alignment
come from the answer. The fifth-ring pilot permits new outer placements while
holding four inner rings fixed; those prefixes admit no changed tile in the
tested windows. This restricts the experiment, not the mathematical problem.

There are two distinct opportunities: make the arrangement search less rigid,
and design a mechanism that allows substantial local growth but forbids global
extension. Increasing the runtime of unchanged UNSAT models does neither.

The existing search and other AI's scoring remain untouched. ANER work is not
a prerequisite. The following are staged experiments, not new bulk jobs.

## 1. Robotics + exact geometry: solve relative placements around loops

**Established ingredient.** Pose-graph SLAM estimates positions/orientations
from relative measurements. SE-Sync develops certified optimization for a
specific noisy synchronization model. [Rosen et al., 2016/2017 preprint,
later journal article](https://arxiv.org/abs/1612.07386).

**Our transfer.** Represent copies as graph nodes and possible contacts as
relative grid transformations. Solve for their choices and enforce consistent
composition around cycles, while permitting inner copies to move. This could
avoid enumerating every absolute placement in a large rectangular domain.

**First gate.** Hide all noncentral absolute poses in known Hc=4 controls;
reconstruct patches using alternative relative contacts. Then jointly change
cells and poses on known Hc=3→4 pairs. A supplied graph is still an oracle;
edge changes and independent alignment are later gates.

**Limit.** SE-Sync's guarantees do not cover this discrete, reflected,
unknown-contact problem. Use exact grid-group constraints and independent
coverage/hole checks. Loop closure alone does not establish a corona.

## 2. Coding/proof theory + frustrated assembly: design delayed contradictions

**Established ingredients.** Tseitin graph constraints assign binary values to
edges and parity requirements to vertices; odd total charge makes the complete
connected system inconsistent. See §4.1 of
[Ben-Sasson and Wigderson (2001)](https://people.inf.ethz.ch/emo/SatSem05/Papers/BensassonWidgerson01.pdf).
A 2024 physics preprint formulates assembly frustration using incompatible
graph flows and cut/cycle spaces.
[Ortiz-Tavárez et al.](https://arxiv.org/abs/2407.18210).

**Our transfer.** Search for small contact rules that remain satisfiable over
early spatial neighbourhoods but become inconsistent at a later closure.
Match states could encode parity, displacement or orientation. Seek explicit
early-corona witnesses alongside an exact eventual obstruction, then compile
the rules into geometry.

**First gate.** Demonstrate a delayed obstruction in a bounded planar symbolic
model with rotations/reflections, without requiring a planted external seed
that our eventual monotile cannot enforce. Measure spatial failure depth.

**Limits.** Slow SAT proofs do not imply high Heesch number. A fixed odd cycle
or an arbitrary nonplanar code is not a tile construction. In a valid geometric
patch, every transform cycle already closes; its measured holonomy is therefore
trivial. The design problem concerns competing proposed contacts. Boundary
escape routes must be included rather than suppressed by the model.

## 3. Hierarchical tilings + number theory: interrupt a forced hierarchy

**Established ingredients.** The hat paper proves that one tile can force a
hierarchical metatile structure.
[Smith, Myers, Kaplan and Goodman-Strauss (2024)](https://escholarship.org/uc/item/3317z9z9).
A July 2026 announcement constructs aperiodic tile sets from quadratic-slope
Sturmian words; its full version was revised in August 2026.
[Akiyama, Hamada and Ito](https://arxiv.org/abs/2607.14693),
[full version](https://arxiv.org/abs/2506.19362).

**Our transfer.** Seek local rules that permit initial hierarchy levels but
prevent a later required supertile adjacency. A small rule system might thereby
delay failure over many ordinary tiles. The Sturmian construction offers a
parameterized source of rule families, not an existing finite-Heesch solution.

**First gate.** Modify a small symbolic hierarchy; exhibit complete finite
coronas and establish that alternative arrangements cannot extend forever.
Screen geometric cell/span cost before compiling.

**Limits.** The hat itself tiles and is disqualified. Hierarchy depth is not
corona count. These sources do not provide a construction satisfying our
single connected, unmarked, ≤200-cell requirements.

## 4. Automatic gadget discovery + boundary codes: synthesize the compiler

**Established ingredient.** Automated SAT searches can construct combinatorial
gadgets rather than require a person to invent every reduction.
[Bergold, Scheucher and Schröder (2024)](https://arxiv.org/abs/2402.06397).
The paper treats completion problems, not Heesch geometry.

**Our transfer.** Specify a desired small matching relation and synthesize
complementary tabs/notches on an achiral substrate. Include forbidden shifted,
reflected and partial-edge fits, connectivity, cell count and coordinate spans.
Use unintended geometric matches as counterexamples for the next synthesis.
This tackles the actual failure of the compact chiral hexapillar realizations.

**First gate.** Recover a simple known interface relation, then a nontrivial
relation needed by a candidate finite-growth mechanism. Check the entire
geometric tile, not isolated edge profiles alone.

**Limit.** A compiler restricted to preselected lattice alignments can miss
escape fits. Full geometric checking remains necessary. Marked rules do not
automatically survive realization at an affordable scale.

## 5. Change the substrate: polyLaves and mixed-cell grids

**Established ingredients.** Mann's UW Bothell project description explicitly
proposes Heesch searches among polyLaves tiles, including polykites.
[University project description](https://www.uwb.edu/stem/research/reu/mathematics).
Upstream heesch-sat implements kite, drafter, abolo, halfcairo and mixed-cell
grids in addition to O/H/I.
[Checker documentation](https://github.com/isohedral/heesch-sat).

**Our transfer.** Try compact matching mechanisms on substrates with different
local angles and reflection behaviour. These families offer structural choices
that a search over 18–30-cell polyhexes never sees.

**First gate.** Choose one family, implement independent cell/contact/symmetry
and hole verification, reproduce known controls and check encoded coordinate
budgets. Confirm the challenge verifier accepts that family. Epoch's public
prompt gives O/H/I as examples and allows other supported families, but does not
enumerate every accepted family.
[Current prompt](https://epoch.ai/frontiermath/open-problems/heesch-number).

**Limit.** Changing grids is not evidence that high Hc is easier. Sparse grid
coordinates can consume the span budget quickly. Do not launch another huge
undirected census before a construction or controlled pilot motivates it.

## 6. Tensor networks + symbolic dynamics: compute boundary feasibility

**Established ingredient.** Wang tilings can be represented with tensors, with
classical, probabilistic and quantum variants.
[Carette and Moutot (2023, revised 2024)](https://arxiv.org/abs/2302.04503).

**Our transfer.** Explore an exact Boolean/nonnegative transfer calculation
over exposed boundary states. Cache equivalent subproblems rather than rebuild
every candidate corona independently. Approximate contractions could rank
proposals on the GPU; exact small cases provide controls.

**First gate.** Reproduce SAT feasibility on small marked-grid patches, report
state growth and compare time/memory. Only proceed if useful compression appears.

**Limits.** Quantum interference changes the mathematical problem and cannot
cancel real geometric tilings. Truncated tensor calculations cannot certify
non-tiling. Boundary-state spaces can still grow exponentially. This is lower
priority than the arrangement and geometric-compiler bottlenecks.

## Concrete work order

1. **Save the synthesis avenue:** a bounded relative-pose/inner-arrangement
   control, with no supplied absolute inner layout. Treat a fixed contact graph
   as another explicit restriction, and allow changes if controls demand them.
2. **Build a mechanism route:** jointly investigate delayed symbolic
   contradictions and a small exact boundary-code compiler. Reject rules whose
   realization budget or unintended contacts defeat them.
3. **Prepare one alternate substrate:** independent verification and compactness
   controls before a native search. Use it for the mechanism/compiler work.
4. **Higher-risk research:** interrupted hierarchies and Sturmian rule families;
   exact boundary-transfer calculations if their small controls show compression.

Advance a track on a demonstrated control or a new verified candidate, not on
an attractive analogy. Keep failures scoped to their actual models. A full
patch proves a lower bound; ordinary finite-Heesch classification and independent
witness verification remain the final acceptance gates.

## Source/access notes

Sources were checked on 2026-10-27. Detailed graph-flow and gadget descriptions,
hat hierarchy passages and Tseitin definitions were inspected; the SE-Sync,
Sturmian and quantum-tiling relevance above is supported by their abstracts.
No source is claimed to implement the proposed HALO combinations.

The 2016 Mann–Thomas paper is another useful construction library to inspect:
[publisher entry](https://doi.org/10.1080/10586458.2015.1096867).
Its abstract/bibliography were available, but full text was not obtained in this
review. Do not invent a compact Hc=5 figure or budget from that abstract.
