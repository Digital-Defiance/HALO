# Inverse score design and marked-polyform pilot

2026-10-27, native macOS. **No new qualifying unmarked Hc>=5 tile.** This session
implements a free-pose reconstruction control, tests a charge-based inverse
design idea, and validates an isolated marked-polyhex solver against known
Hc=4/5 constructions. Existing search/scoring jobs and ANER remain unchanged.

**Follow-up implemented:** `JOINT_RULE_PILOT.md` now records joint unknown-label
and free-placement synthesis. It passes unseeded marked three/four-ring controls
and recovers known marked Hc=5 by shallow synthesis plus forward checking. The
bounded six/seven pilots remain unresolved; no unmarked improvement is claimed.

## What “solve for Heesch 7” means

Let C(S,P,k) say that P is a valid k-corona patch of tile S. Then

    Hc(S) = max { k : there exists P with C(S,P,k) }.

Exact Hc=7 can be posed as a synthesis problem:

    find a valid S and P7 with C(S,P7,7), and prove no P8 satisfies C(S,P8,8).

For a finite Hc>=7, an independently valid non-tiling certificate can replace
the exact eighth-ring exclusion, while the ordinary challenge classifier still
has to settle the shape below its maxlevel-12 bound. There is no known closed
coordinate formula that eliminates the arrangement/existence part of this
search. The methods below address specific pieces of that inverse problem.

## Free poses from a contact graph

`halo/pose_synthesis.py` accepts a fixed tile and a graph of required contacts.
Only the central copy's pose is fixed. All other translations and rotations/
reflections are integer variables. Required contacts come from a table of legal
two-copy relative transforms. Shared node poses enforce loop consistency.

Factoring each contact into a relative rotation/displacement and a grid-frame
map substantially reduces the initial SMT expression. No reference absolute
pose or reference bounding box is supplied to `PoseModel`. Pose bounds follow
from graph distances and the largest possible legal contact displacement.
The occupied local origin supplies a sound distinct-anchor constraint.

Geometric validation independently checks every accepted patch. If needed,
sound lazy constraints reject pair overlaps, require missing prefix coverage,
or change a hole's wall/cover an interior anchor. These constraints are invariant
under a common grid isometry. The new tests check that known valid layouts remain
available after each kind of cut.

| Control | Result |
| --- | --- |
| Hc=4 11-hex, first corona; reference graph/contact counts | Verified, 6 copies |
| Four coronas, expanded contact expression | 15 s timeout, unresolved |
| Four coronas, factored expression | **Verified, 62 copies**, 11.2897 s, sampled peak 543.6 MB |
| Four coronas, reference contact counts also hidden | 15 s timeout, unresolved |

This passes a stronger placement control than retaining the reference's inner
rings. The fixed tile, corona labels, topology and (in the successful large
case) contact counts are still supplied. It does not yet synthesize the tile
with all poses or demonstrate blind graph selection.

```sh
.venv/bin/python halo/pose_synthesis.py shapes/reference/hex11_h4.witness.txt \
  --level 4 --seconds 15 --mem-mb 1000 \
  --out results/pose_reconstruction_control_20261027.jsonl
```

## A concrete charge formula and its first falsification

In an edge-matched regular-hex lattice model, assign scalar charges to the six
edges of one hexagon. Matched internal edges have opposite charges. Let delta
be the net charge per tile and c bound the absolute charge per exposed edge.
The radius-r lattice ball contains

    N(r) = 1 + 3r(r+1) tiles,     P(r) = 6(2r+1) exposed edges.

Cancellation gives the necessary inequality

    |delta| N(r) <= c P(r).

For delta=1, c=2, seven rings satisfy 169<=180, while eight would require
217<=204. That is an upper bound of seven in this model, not an existence proof.

`halo/marked_charge.py` exhausts all **140 D6-distinct words** using charges
-2,-1,0,1,2, net +1 and actual cap 2. **139 have Hc=0; one has Hc=1.** An
independent exhaustive orientation enumeration confirms every first-ring result.

There is also a stronger obstruction. For each complementary label pair l/-l,
let d_l be the difference in their multiplicities on the tile. Reassign the
pair charges to sign(d_l) and -sign(d_l), leaving balanced pairs at zero. Every
allowed join still cancels, but the tile now has

    Delta = sum_l |d_l| >= 1,     exposed-edge capacity <= 1.

At four rings N(4)=61>P(4)=54, so **any such unbalanced one-hex complementary-
label model has at most three coronas**. The proposed seven-ring family is
therefore ruled out by a stronger certificate. This statement is restricted to
that marked regular-hex lattice model, not arbitrary polyforms or matching rules.

The inverse idea has a positive smaller control: with cap 1/net 1, all 13
distinct words were checked. One reaches exactly Hc=3, five reach Hc=1, seven
Hc=0. The three-ring witness has 37 tiles; the charge inequality excludes the
fourth ring. Its word is `[-1,-1,0,1,1,1]`. Thus a witness plus a conserved
quantity genuinely settles a small inverse-design case.

## Validated multi-cell marked solver

The single-hex restriction motivates a multi-cell model. The new isolated
`build/<OS>/heesch-sat-marked-v1/marked` uses the pinned checker's geometric
placement expansion, with additional incompatibility clauses for mismatched
boundary labels. It keeps all grid orientations, disables geometric adjacency
reduction and geometry-only tiling shortcuts, and independently checks every
prefix for holes. A rejected prefix blocks its exact selected/unselected copy
assignment, allowing other assignments to fill the hole.

`halo/marked_polyform.py` verifies every emitted SAT patch with `halo/verify.py`,
then checks each shared boundary label and the global charge identity. Ordinary
unmarked checks still require `-isohedral`; this separate symbolic driver must
not use an unmarked tiling shortcut to classify marked tiles.

| Marked pillar | Result in marked lattice model | Native time / sampled peak |
| --- | --- | --- |
| 1 hex (extra computed control) | Hc=3 | 0.0571 s; too fast for a reliable RSS sample |
| 2 hexes | Hc=4, fifth ring UNSAT | 0.8845 s / 181.7 MB |
| 3 hexes | Hc=4, fifth ring UNSAT | 1.7853 s / 674.1 MB |
| 4 hexes, initial 1 GB cap | Verified five rings; sixth unresolved at memory cap | 6.6592 s / 1,009.1 MB |
| 4 hexes, 2.5 GB retry cap | **Hc=5, sixth ring UNSAT** | 7.58 s / 1,014.6 MB |

The 2/3/4-pillar values reproduce Mann's known Hc=4/5 examples (rules and primary
paper are recorded in `CONSTRUCTION_PILOT.md` and `refs/README.md`). The fourth-
pillar five-ring witness contains 121 copies. These are marked controls; the
old geometric-realization budget and unintended-fit problems remain open.

```sh
bash scripts/setup_marked_polyforms.sh
.venv/bin/python halo/marked_polyform.py --pillars 2 3 4 --maxlevel 7 \
  --seconds 30 --mem-mb 2500 --out results/marked_pillar_control_20261027.jsonl
```

The builder copies headers to fresh temporary storage, injects only the new
public methods there, and publishes a separate binary. Production source,
checker binaries and active processes are not replaced. Only macOS was tested.
The no-change build path is verified.

## First structured rule screens

`halo/marked_screen.py` generates and canonicalizes entire marked tiles under
D6, including transformed edge directions and unchanged scalar charges.

- **117 compact four-hex polar-marking candidates:** upper-facing edges nicked,
  lower-facing edges bumped, one horizontal nick to give net -1. Excludes the
  straight pillar. 105 Hc=0, 12 Hc=1; none unresolved.
- **84 distinct single swaps of unequal markings on the known four-pillar:**
  preserve net -1 and exclude the unchanged control. All Hc=0.

These are complete finite screens of those generated families, not all
markings. Their fast negative results argue for **joint rule/patch synthesis**
rather than more unchanged polar or single-swap trials. A nonzero conserved
charge precludes an infinite edge-matched lattice tiling: a large patch's tile
count grows with area, while only a boundary layer can carry its unmatched
charge. This certificate must hold for all actual fits after any geometric
realization; intended symbolic matches alone are insufficient.

## Next gates

1. **Inverse rule synthesis:** choose boundary labels and corona placements
   together, require nonzero charge, and recover known marked Hc=3/4/5 controls
   without supplying their markings. Then target six/seven-ring witnesses.
2. **Geometric compilation:** synthesize a compact achiral realization and test
   every geometric relative fit for conformity with the symbolic rule system.
   Alternate grids remain available after independent verification support.
3. **Placement synthesis:** reduce dependence on reference contact counts,
   topology and the fixed tile. The unweighted timeout is an unresolved scaling
   test, not a mathematical exclusion.

No production allocation is changed on these controls. Do not rerun the completed
140-word, 117-polar or 84-swap screens unchanged.

## Evidence and validation

All experimental records are append-only under `results/`:

- `pose_reconstruction_control_20261027.jsonl`
- `marked_charge_cap{1,2}_20261027.jsonl`
- `marked_pillar_control_20261027.jsonl`
- `marked_compact_screen_20261027.jsonl`
- `marked_swap_screen_20261027.jsonl`

The initial capped pillar row retains an old `matches_control:false` reporting
default; its `status:memout`, `hc:null` and verified lower bound are authoritative.
Current reporting uses null for an unresolved control comparison. Source and
input/binary hashes accompany the records; a final source snapshot and artifact
hashes are in `benchmarks/2026-10-27/score_design_summary.json`.

Validation: 78 tests run, 77 passed, one existing opt-in slow defect regression
skipped. New tests cover grid-group algebra, strict SMT parsing, safe geometric
cuts, exhaustive first-ring label controls, exact charge bounds, marked witness
checks, capped-result preservation, known marked Hc=4 and whole-marked-tile
canonicalization. No unmarked record or discovery-rate improvement is claimed.
