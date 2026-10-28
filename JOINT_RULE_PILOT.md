# Joint rule and corona synthesis

2026-10-27, native M4 Max / 64 GiB. **No new qualifying unmarked Hc>=5.**
The new inverse solver invents markings and placements together on a supplied
polyhex body. It recovers marked three- and four-ring controls without marking
or layout templates, and a staged check recovers the known marked Hc=5 pillar.
Six/seven remain unresolved. Existing production jobs and ANER were unchanged.

## The inverse problem now implemented

For a fixed body B, the shared variables q_e are its boundary labels in
{-1,0,+1}. Every congruent copy uses those same labels. The solver chooses both
q and a complete k-corona patch P, subject to:

    sum_e q_e = -1
    geometry(B, P, k)
    q_e + q_f = 0 at every shared edge of every selected copy pair.

By default every label is unknown; no reference pose, contact graph or patch
is supplied. The body is still fixed. This is a concrete finite inverse model,
not a closed coordinate formula for arbitrary Heesch number or a synthesized
unmarked tile. The nonzero charge is a mechanism constraint; it does not alone
establish either seven rings or a useful finite upper bound for these bodies.

`halo/joint_marked.py` wraps a separate native binary built by
`scripts/setup_joint_marked.sh`. It retains all orientations and the fixed
backend's hole checks at every prefix. Unlike ordinary unmarked classification,
these isolated symbolic solvers must disable geometry-only tiling shortcuts:
those shortcuts ignore the labels. Production `-isohedral` checks are unchanged.

The first lazy prototype exhausted 256 refinement rounds on the one-hex control
and returned **unknown**, not UNSAT. The working encoding factors compatibility
into shared edge-match literals and then relative-fit literals. Every occurrence
of a relative fit reuses the same literal. This passed the controls below.
The lazy prototype's failed record is retained.

## Controls and bounded attempts

These are single-run timings under concurrent native workloads, not a hardware
benchmark or a measured improvement in discovery rate. RSS is sampled.

| Fixed body / request | Result | Wall / peak RSS |
| --- | --- | --- |
| One hex, all labels unknown, three rings | Verified 37-copy patch | 0.3952 s / 7.5 MB |
| One hex, all labels unknown, four rings | UNSAT, agreeing with the independent charge bound | 0.0747 s / 12.7 MB |
| Two-hex straight body, all labels unknown, four rings | Verified 81-copy patch; the separate fixed-rule classifier also gives exact Hc=4 in tests | 0.2019 s / 60.0 MB |
| Four-hex straight body, all labels unknown, five rings directly | 30 s timeout; unresolved | 30.0174 s / 1,499.8 MB |
| Same four-hex body, synthesize three rings first | Verified 80-copy patch and newly chosen labels | 0.7105 s / 179.7 MB |
| Check that synthesized rule with all poses free through level eight | **Exact marked Hc=5**, sixth-ring UNSAT, verified five-ring 121-copy witness | 7.3977 s / 1,010.9 MB |

Only after synthesis was the four-hex rule compared to Mann's rule: it is the
same up to a body isometry. That is a control recovery, not a novel construction.
Its independently checked five-ring witness does not meet the unmarked goal.

Raw records are append-only:

- `results/joint_marked_controls_20261027.jsonl`: six development/control attempts.
- `results/joint_marked_extensions_20261027.jsonl`: fixed-rule Hc=5 classification.
- `results/joint_marked_search_20261027.jsonl`: four staged runs, including caps.
- `results/joint_compact_pilot_20261027.jsonl`: six other free four-hex bodies.

The initial staged six-ring run independently recovered the same marked Hc=5
rule, then timed out on alternatives. A 15 s synthesis retry with the stronger
feedback below also timed out. These are unresolved searches, not exclusions
of six rings. A resumed seven-ring run using one-ring synthesis checked 24 new
rule classes, all exact Hc=1. A subsequent two-ring run checked two new exact
Hc=2 classes, then timed out. Completed checks are reused across runs.

The compact pilot requested three-ring seeds for six-ring checks, with 5 s and
2 GB per synthesis. Five bodies timed out. The body
`H 0 0 0 1 1 1 2 0` was UNSAT for three rings in the tested ternary/net-minus-one
family; consequently that family cannot reach six. This says nothing about
other labels, net charges or bodies. The other five bodies remain unresolved.

## Sound feedback from failed rules

Let Fits(A) be all nonoverlapping contacting relative placements permitted by
rule A on this fixed body. If Fits(B) is a subset of Fits(A), every corona
permitted by B is also permitted by A. Therefore, after A is conclusively
proved unable to reach k, a prospective k-ring rule B must enable at least one
fit absent from A:

    OR over T not in Fits(A): enabled_B(T).

`halo/joint_rule_search.py` adds these clauses after completed forward
classifications, including their body-symmetry equivalents. Python independently
enumerates relative fits and checks every returned rule against the clauses.
This excludes whole weaker families instead of just one label vector. It is
sound pruning, with no measured discovery-rate gain claimed yet.

Resource-capped candidates are deferred and receive only exact rule-orbit
exclusions. If any deferred candidate exists, exhaustion of the remaining space
is not reported as nonexistence for the whole family. Resumption checks the
body, input digest, checker binary digest, final UNSAT level and all positive
prefix geometries/labels before reusing a completed forward check. This reuses
the checker's recorded UNSAT result; it is not an independent proof-log checker.

## Reproduction and validation

```sh
bash scripts/setup_marked_polyforms.sh
bash scripts/setup_joint_marked.sh
.venv/bin/python halo/joint_marked.py --pillar 2 --target 4 \
  --seconds 10 --mem-mb 1000 --out results/my_joint_control.jsonl
.venv/bin/python halo/joint_rule_search.py --pillar 4 --target 7 \
  --synthesis-level 2 --max-candidates 12 --total-seconds 30 \
  --joint-seconds 5 --check-seconds 12 --mem-mb 2500 \
  --out results/my_joint_search.jsonl
```

Add `--resume` to the last command to reuse completed exclusions in its output.
It cannot reuse a check whose fixed-rule binary digest has changed. Each solver
has wall/RSS caps plus the cooperative 8 GB system-available reserve. The run
limits are not estimates of time to a discovery.

The full suite ran 90 tests: 89 passed; the existing opt-in native Hc=4 defect
regression was skipped. Twelve new cases cover unseeded controls, sign reversal,
independent rejection of invalid labels, exact/symmetry exclusions, fit-feedback
preservation of a better rule, resumption, and resource/error handling.
All saved positive patches were independently rechecked; counts and source/log
digests are in `benchmarks/2026-10-27/joint_rule_summary.json`.

## Next gates

The no-marking-template control is now passed through marked Hc=5 by staged
synthesis. The remaining obstacle is mathematical usefulness, not ANER speed.
Do not restart an unchanged long five-ring synthesis merely because it capped.

1. Couple body selection and geometric realizability to the rule model. A deep
   marked rule on an elongated body is not useful if its compact geometric
   realization cannot fit the 200-cell/span-29 limits. Retain the independent
   three/four/five controls as gates for changes to this model.
2. Test a richer delayed obstruction: multiple complementary label pairs or
   a hierarchy/parity mechanism on different compact bodies. Preserve actual
   early-corona witnesses; a plausible obstruction without them is insufficient.
3. Continue the compact achiral geometric compiler track independently. It must
   retain intended reflected fits and reject unintended fits before ordinary
   unmarked maxlevel-12 certification can turn a symbolic result into progress
   on the challenge. The earlier chiral macrohexagon failures still apply.

These are follow-up experiments, not claims that six or seven are imminent.
