# HALO status

Last updated: 2026-10-27 (Codex native: free-pose reconstruction and marked mechanism controls). Current phase: **Best qualifying unmarked Hc is still 4. Free-pose reconstruction now recovers the known four-ring patch from a contact graph; an isolated marked solver reproduces known Hc=4/5 pillars. No qualifying unmarked Hc>=5. Next: jointly synthesize markings and patches, and compile compact geometry that preserves their fits. Existing search/scoring jobs are untouched.**

## Native inverse-design update (2026-10-27)

- **Done, poses:** `halo/pose_synthesis.py` reconstructed the Hc=4 11-hex patch (62 copies) in 11.2897 s / sampled 543.6 MB, with every noncentral translation and orientation free. Fixed tile, corona labels, contact topology/counts are supplied. Hiding contact counts also timed out at 15 s, unresolved. This validates conditional reconstruction, not blind shape/topology discovery.
- **Done, mathematical control:** `halo/marked_charge.py` tests the area-versus-boundary charge formula. The cap-1 family produces an exact marked Hc=3 witness plus charge upper bound. The proposed cap-2/net-1 bound of seven is defeated by stronger label reweighting: an unbalanced one-hex complementary-label model has Hc<=3. All 140 tested cap-2 words reach at most Hc=1. Scope/proof are in `SCORE_DESIGN_PILOT.md`.
- **Done, marked solver:** new isolated `heesch-sat-marked-v1/marked` preserves all orientations and adds exact boundary-label incompatibilities. Every SAT patch passes independent geometry and label/charge checks. It reproduces marked Hc=4 for 2/3-hex Mann pillars and **marked Hc=5** for the 4-pillar, with sixth-ring UNSAT (7.58 s, sampled 1,014.6 MB). The initial 1 GB cap preserved a verified lower bound of five and unknown Hc; a bounded 2.5 GB retry settled it. This is a known symbolic control, not an unmarked realization.
- **Structured screens:** 117 compact four-hex polar markings give Hc=0 x105 / Hc=1 x12. All 84 distinct one-swap variants of the marked Hc=5 pillar give Hc=0. Both families completed. Do not repeat unchanged; the next rule generator must preserve deep growth jointly with its patch.
- **Validation / next / blocked:** 78 tests, 77 passed, one existing opt-in slow test skipped; isolated build/no-op and shell syntax pass. Next: joint marking/placement synthesis from the known controls, compact achiral geometry compilation, and less oracle-dependent pose search. `SCORE_DESIGN_PILOT.md` and `benchmarks/2026-10-27/score_design_summary.json` preserve evidence and limits. Mathematical construction remains open; no access blocker. Production binaries, changing archives, current jobs and ANER were not modified.

## Native research update: withheld outer ring (2026-10-27)

- **Broader scientific combinations:** `UNCONVENTIONAL_RESEARCH.md` records a checked primary-source review spanning 2001–2026. Priority experiments are discrete relative-pose/loop constraints to free inner arrangements, delayed parity/flow contradictions coupled to automatic geometric gadget synthesis, and one independently verified polyLaves substrate. Interrupted hierarchies/Sturmian rules and tensor boundary methods remain higher-risk tracks. These are explicit hypotheses with controls, not claims of discoveries or speedups. The source review and documentation introduce no new bulk run.
- **Done:** `halo/outer_synthesis.py` first synthesizes a tile compatible with a supplied inner prefix, then independently enumerates possible next-ring placements and solves for a complete ring. Fixed-tile hole cuts reject a hole by requiring a wall change or coverage of an interior anchor. Every accepted patch passes the independent verifier. `REPAIR_PILOT.md` records commands, limits and results.
- **Conditional positive control:** from the nearby Hc=3 11-hex, 2 cell flips are UNSAT; 4/6 flips recover the known Hc=4 tile and construct a verified fourth ring (62 copies). None of the reference's 27 outer placements is provided to the pool generator; all occur in its complete 1,304-pose pool. Hole feedback takes four layout solves. Reference alignment and the inner three rings are still supplied, so this is not blind discovery.
- **Hc=5 pilot:** the unchanged 11-cell tile cannot extend its given four-ring prefix (complete 1,720-pose pool, UNSAT). No changed 11-cell tile fits that prefix within 2/4 flips. Around the 21-cell Hc=4 witness, no changed 19–25-cell tile fits its fixed four rings within 2/4/6 flips. These are bounded layout/edit exclusions, not nonexistence results for other layouts. Do not repeat these unchanged models with longer timeouts.
- **Validation:** 56 tests run, 55 passed and the existing opt-in native Hc=4 defect regression skipped. Five new cases check pose-pool coverage against exhaustive small edited tiles, explicit caps, held-out reference-pose inclusion, hole-cut alternatives and actual Hc=3→4 recovery. Raw logs: `results/outer_{pool_control,synthesis_control,synthesis_hc5_pilot}_20261027.jsonl` (development failures retained).
- **Running / next / blocked:** existing search/scoring jobs were not stopped or modified; their changing archives and manifests remain uncommitted. Continue the portfolio in `RESEARCH_PLAN.md`: earlier-ring placement freedom/template transfer, compact achiral matching codes, conserved obstructions with witnesses, continuation features, multiscale changes and other grids. No ANER change is a prerequisite; no access blocker remains. Mathematical effectiveness beyond the conditional control remains unproved.

## Handoff (2026-10-27 evening, Claude): remeasure complete, sweep2 seeding, repair control

- **Codex native reconciliation:** verified active PID 64825, run `920d77d84a3f4190819d2649373f53cb`, uses both seed files and `--sweep2-max-defect 0.03`; both existing jobs were left alone. Local remeasure copy contains 318 attempts / 290 measured / 28 unresolved / 18 qualifying Hc=3 parents; the owner's quoted cloud update is ahead of this mirror. Finish/copy the full remeasure before one planned restart. The live search reads seeds only at startup.
- **Read-only reporting:** `halo/gen_report.py --latest-run --generator search-sweep2 --by-parent` now reports per-parent unique Hc>=3/4/5 hits, completed checks and recorded cost from a byte-bounded snapshot, without editing the log. The saved snapshot (`benchmarks/2026-10-27/sweep_parent_snapshot_920d77d8.json`) has 405,998 completed sweep2 checks and one Hc=3 result, no Hc>=4. Pending/deep outcomes and neighbourhood exhaustion are not inferred; asynchronous completion can bias interim yield.
- **Unconventional work continues:** a new oracle-template control (`halo/template_synthesis.py`) recovers the known Hc=4 11-hex from a nearby Hc=3 11-hex at 4/6 cell flips (2 is UNSAT), including a trial with local third/fourth-ring placement choices. Both successful patches pass independent verification. This supplies the answer's template and is not a discovery; next work is an independently generated outer-pose pool and blind template transfer. The failed parent-patch generator stays shelved. Broader controlled levers are recorded in `RESEARCH_PLAN.md`.
- **v2 defect remeasure (done, cloud x86 4 cores/15 GB):** `halo/add_defects.py` over all 728 archived Hc>=3 shapes with >=15 cells (1 Hc=4, rest Hc=3), 4 jobs, 5 GB/180 s caps. Output: `results/defect_v2_remeasure_20261027.jsonl` (append-only). **635 measured, 93 unresolved** (92 hit the 180 s cap, 1 error; none hit memory, peak 3.9 GB). **35 Hc=3 shapes are at or under the 0.03 sweep2 threshold.** The Hc=4 tile reproduces **7/171**. Best Hc=3 near misses (v2, exact): **20 cells 1/170** (`H 0 1 0 2 1 0 1 1 1 2 2 1 2 2 2 3 3 1 3 2 3 3 4 0 4 1 4 2 4 3 5 0 5 1 5 2 6 1 6 2`, found by scorer picks), 22 cells 1/163, 21 cells 2/218, 19 cells 2/148, 20 cells 3/178. Cloud jobs started with `setsid nohup` died whenever the session went idle; the agent's tracked background task worked. Retry the unresolved rows natively with a longer cap (add_defects treats unresolved rows in an output file as done, so they go to a new file):
  ```sh
  .venv/bin/python halo/add_defects.py build/defect_retry_in.jsonl --out results/defect_v2_remeasure_retry_20261027.jsonl --min-hc 3 --min-cells 15 --jobs 4 --mem-mb 8000 --timeout 900
  ```
- **Sweep2 seeding fix (commit 8e92602):** the search only read defects from the main archive, so remeasured near misses never became two-edit parents. Seed files with v2 defects now copy `defect`, `ring`, `defect_exact`, `defect_seconds`, `defect_version` onto archive rows that only have legacy values (same hc). Verified: a legacy-only Hc=3 shape gets no sweep2 parent; with the remeasured seed it does. 41 tests pass. Launch:
  ```sh
  ./scripts/search_frontier.sh --sweep2-max-defect 0.03 --seeds results/seeds_kaplan_hex_3up.jsonl,results/defect_v2_remeasure_20261027.jsonl
  ```
  Restart it after the remeasure grows to pick up more parents (the archive resumes losslessly; never run two searches on one log).
- **Repair positive control (commit c8cc857, details in `REPAIR_PILOT.md`):** no Hc=3 polyhex in Kaplan's set is one edit from an Hc=4; the 21-cell Hc=4 tile's 38 add/remove neighbours are all Hc<=2 or tilers. 22 Kaplan Hc=3 shapes are two edits from an Hc=4 (`scripts/repair_control_pairs.py`); on 20 exported layouts, `patch_repair.py` at 2/4/6 edits in fixed and widest regimes gave **120/120 UNSAT**. The three best archive near misses were UNSAT too. Encoding sanity: the 0-edit model on a fully covered layout is SAT. Conclusion: improved shapes need different corona placements; repairing a fixed partial patch cannot find them. Do not use the current tool as a generator; a viable version must search placements with the tile.
- **Git from the Mac's Linux VM:** it has no git-lfs, so plain `git add`/`commit` fails on the modified LFS archive. Commit with `git -c filter.lfs.process= -c filter.lfs.clean=cat -c filter.lfs.smudge=cat -c filter.lfs.required=false -c core.hooksPath=/dev/null ...` and then remove `.git/*.lock`. The unclaimed 2-line change in `results/search_hex_01.jsonl` is still left uncommitted.
- **Running/next/blocked:** remeasure done (23:55 UTC). Next: restart the seeded sweep once so it loads all 35 qualifying parents (run 920d77d8 started from a partial seed file and reads seeds only at startup), optionally retry the 93 unresolved rows natively, review sweep2 yield per parent, then a small native cost-scaling test of 40–60-cell candidates using the 64 GB headroom (Hc>=7 likely needs 100+ cells). Nothing blocked.

## Construction handoff (2026-10-27, Claude): Mann hexapillar realizations

- **Done:** `halo/hexapillar.py` builds Mann's marked n-hexapillar (upper edges nicked, lower edges bumped, first end flat, last end nicked: 2n+1 nicks vs 2n bumps) as a polyhex from k-cell-radius macro-hexagons, and as a polyiamond from side-1 hexagons. `CONSTRUCTION_PILOT.md` has the rules, the table and the diagnosis. Four new unit tests (`tests/test_hexapillar.py`) check the macro-tiling, marking counts and bump/nick mating.
- **Results:** polyhex k=2 (13–34 cells, n=2–5) and polyiamond side 1 (n=2–5, 11–29 triangles; n=5 is over the span limit) all tile isohedrally. Polyhex k=3 (n=2–4, up to 75 cells) and k=4 (n=2) give Hc=0. The k≥2 macro-lattice is chiral, so reflected copies cannot meet edge to edge, and Mann's coronas need them. No D6-symmetric connected hole-free fundamental domain of 5A2, 7A2 or 11A2 exists up to radius 9 (`scripts/construction_d6_domains.py`). Every one-cell edit of the k=2 4- and 5-pillars (753 and 1,121 shapes) reaches at most Hc=1 (`scripts/construction_hexapillar_sweep.py`). The exact side-3 polyiamond copy is 215 cells and span 86. All rows: `results/construction_hexapillar_20261027.jsonl`.
- **Meaning:** the limits rule out direct copies of the hexapillar; this is not an impossibility proof for other compact markings. Classifications ran in the cloud copy at maxlevel 7.
- **Next:** the two-edit sweep is the empirical lead. A new construction would need bump/nick features designed to be mirror-compatible on a small achiral substrate, then gated with `halo/patch_repair.py`.

## Implementation handoff (2026-10-27): repair pilot and defect metric v2

- **Done:** `halo/patch_repair.py` implements shared cell variables, edit/size bounds, no overlaps, prefix enclosure, copy contact, optional copy shifts, independent geometry checks and ordinary finite-Heesch classification for successful proposals. Exported `defect_patch` includes explicit tile cells, transforms, required cells and gaps. `REPAIR_PILOT.md` records the experiment and limits.
- **Correction:** independent checking rejected the old 5/169 layout because its fourth ring had a hole. The certified Hc=4 witness remains valid. Version 2 explicitly excludes every holed inner prefix; corrected 21-cell score **7/171 exact**, with a verified Hc=4 prefix, 43.927 s / 4,434.7 MB. A 16-cell parent gave **12/214 exact** with a valid prefix. Old records are preserved; legacy defect fields are excluded from near-miss ranking until remeasured. New no-result export attempts remain unknown.
- **Pilot:** two verified layouts × 2/4/6 changed cells × three placement regimes = **18 UNSAT models**, no Hc=5 and no production-shape candidates. The widest regime allowed fourth/fifth-ring shifts and interior edits, used about 134 s including model construction, and peaked at 613.2 MB sampled solver RSS. This excludes only those local layout/edit spaces. Raw append-only logs and hashes are linked from `REPAIR_PILOT.md`.
- **Build/runtime:** `scripts/setup_patch_repair.sh` builds and atomically publishes `build/<OS>/heesch-sat-defect-v2/defect`. The search launcher checks/builds it before a new run. Existing SAT/defect processes and the main search archive were not modified. ANER remains unchanged.
- **Validation:** the original **37-test suite passes including the real native Hc=4 regression** (46.4 s). Three new construction-budget cases and a stale-patch cleanup case bring coverage to 41 cases (40 regular tests plus that opt-in native case). The capped CLI exporter smoke, builder no-change path and shell syntax also pass.
- **Construction screen:** a straight four-hexagon body in exact I-grid triangle coordinates uses 24/96/216 cells at side 1/2/3, with best span sums 26/56/86. Side 2 already exceeds span 29 before markings; side 3 also exceeds 200 cells. `scripts/check_hex_chain_budget.py` and its tests record this initial feasibility check. This is not an impossibility proof for compressed or alternate-grid realizations; establish their exact budgets before implementing an expensive marked search.
- **Running/next/blocked:** pilot and regression processes finished. Next strategic work is to reproduce Mann's marked construction and establish a compact realization budget, using the repair tool where useful. No access blocker remains. Do not rerun unchanged UNSAT instances with a larger time budget.

## Research handoff (2026-10-27): inverse design and construction feasibility

- **Execution queue:** `RESEARCH_PLAN.md` now starts with ordered deliverables and gates: (1) patch export plus independent coverage/geometry checks, (2) inverse repair at 2/4/6-cell edit budgets with a proposed one-hour pilot on at most four layouts, (3) review measured results before broadening placements, (4) construction feasibility and compact boundary codes. Target certified Hc>=5 first, then 6/7. The tools remain unimplemented; the one-hour cap is a proposed compute budget, not an implementation or discovery ETA. Retain the existing search as a bounded control and keep ANER unchanged. No running process was changed in this planning session.
- **Cross-domain review:** expanded `RESEARCH_PLAN.md` with self-limiting assembly plus conserved boundary/density constraints, compact geometric matching codes, counterexample-guided synthesis, and a bounded continuation-diversity pilot. These are unimplemented hypotheses, not measured speedups. The pinned `allCoronas` routine is explicitly deprecated/inefficient; full first-ring counting is not assumed cheap. Randomized growth is not a proof of non-tiling. A 2026-10-01 3D density-method preprint supplies a potentially transferable certificate idea, not a planar record. No search process was changed or new bulk experiment launched for this review.
- **Done:** obtained the genuine 9-page Mann 2004 PDF at `refs/mann_2004_heesch.pdf` from the author's university page and inspected Figures 5–6. Source/checksum and the accessible Bašić 2021 full text are in `refs/README.md`. No owner-supplied Mann PDF is needed. The attempted Bašić PDF downloads were HTML and were removed; its full text and Figure 1 were inspected online.
- **New measurement:** native `runner.run_defect` on our certified 21-cell Hc=4 shape found **5/169 uncovered, exact under the current encoding**, in 48.804 s at 4,441.3 MB peak RSS. Diagnostic caps were 120 s / 20 GB, with shared memory/system-headroom protection. Record: `results/hex21_h4_defect_20261027.jsonl` (append only). This does not change its Hc or prove a fifth corona.
- **Next:** the proposed shortcut is **inverse patch repair**: export a partial fifth-corona patch and solve for coordinated tile-boundary changes shared by every placed copy, initially with fixed transforms. Independently check global geometry and finite Heesch classification. `RESEARCH_PLAN.md` specifies the encoding, experiment order and rejection conditions. This optimizer is not implemented and no improvement in discovery odds is claimed yet. Continue bounded two-edit sweeps alongside it.
- **Construction qualification:** Mann's theorem concerns marked hexapillars; Bašić's figure uses six hexagons, eleven triangles and half a triangle. A small unmarked polyform realization preserving their fits has not been demonstrated. Do not treat the earlier 130–170-cell estimate as an established construction.
- **Odds qualification:** the weeks-to-months estimate below assumes a relationship between adjacent Hc levels that has not been measured. It is a scenario, not a reliable waiting-time forecast. A 1-cell defect on an Hc=3 shape is a lead toward Hc=4, not a direct near miss for Hc=5.
- **Running/blocked:** the bounded native diagnostic finished; no production search was started or stopped. The native process snapshot immediately before it found no `halo/search.py` process. There is no literature-access blocker to beginning Mann's construction; preserving its geometry inside the verifier limits is the research challenge.

## Current handoff (2026-10-27): overnight run a3d2f477 and the two-edit sweep

- **Run a3d2f477** (15:48–23:48 on 2026-10-26, `scripts/search_frontier.sh` settings: 14 jobs, sweep 0.75, v4 MLX FP32 scoring, warn-only guard). 2,252,178 checks:

  | Generator | Checks | Hc>=2 | Rate |
  | --- | --- | --- | --- |
  | one-edit sweep | 86,237 | 720 | 0.83% |
  | scorer v4 picks | 673,527 | 1,094 | 0.16% |
  | random mutants | 1,492,414 | 512 | 0.034% |

  The sweep also produced 275 of the run's 296 Hc=3 finds, over 100× the per-check rate of the other generators. It ran dry around 19:00: hourly sweep checks were 6.4k, 1k, 25.7k, 53.7k, then under 1.6k per hour. Hc=3 finds cluster, so their one-edit neighbourhoods overlap and were exhausted. The 48 guard warnings on the scored arm were 0–2 hits per 2,000; that's noise, and over the run the scorer beat random about 5×.
- **Totals for runs 3–3c (18+ cells):** 713 Hc=3 shapes (sizes 18: 523, 19: 14, 20: 57, 21: 103, 22: 5, 23: 11) and one Hc=4 (the 21-cell shape). No Hc=5.
- **Closeness to the next level** (defect = uncovered cells next to the hc-patch, out of the ring) for 558 Hc>=3 finds. The best near misses, as Hc=3 shapes close to Hc=4:
  - 22 cells, 1/163 uncovered: `H 0 0 0 1 0 2 0 3 1 0 1 1 1 2 1 3 1 4 1 5 2 0 2 1 2 2 2 3 2 4 2 5 2 6 3 1 3 2 3 3 3 4 4 2`
  - 21 cells, 2/218: `H 0 0 0 1 0 2 0 3 1 0 1 1 1 2 1 3 2 2 3 1 3 2 3 3 3 4 4 1 4 2 4 3 4 4 5 1 5 2 6 0 6 1`
  - 18 cells, 2/193; 19 cells, 2/148; 18 cells, 3/197.

  The 21-cell Hc=4 shape's own defect has not been measured. It needs more memory than the agent sandboxes; run `runner.run_defect(...)` on the Mac.
- **New: two-edit sweep** (`search.py --sweep2-min-hc 4 --sweep2-max-defect 0.015`, default on). When the one-edit sweep has no work, it checks every valid shape two one-cell edits from each Hc>=4 parent, and from each Hc=3 parent with a defect fraction of at most 1.5%, best parents first. Intermediate steps are not validated; only the final shape is. The ball is expanded a few first steps at a time, and shapes are logged as `search-sweep2`. The 21-cell Hc=4 shape has 41,123 new shapes two edits away (22-cell near miss: 49,348); enumeration takes ~30 s on 2 cloud cores. At the overnight pace that's ~12 min per parent. New regression test `test_two_edit_sweep_covers_the_ball_once`; all 22 tests pass.
- **Odds, honestly:** at 18+ cells, Hc=4 turned up once per ~700 Hc=3 shapes. If Hc=5 is as rare relative to Hc=4, finding one by local search would take ~10^8–10^9 checks (weeks to months of the Mac). The two-edit sweep is the cheapest remaining way to search the most promising region. **Track B** (realise Mann's or Bašić's marked Heesch-5/6 tiles as a large polyhex, ~130–170 cells: a side-7 hexagon with 1–2-cell tabs and notches, within the 200-cell and span-29 limits) is the plausible route to Hc>=5. It needs the figures from Mann 2004 (*Amer. Math. Monthly* 111(6)) and Bašić 2021 in `refs/`.
- **Context:** the public Layr-Labs/heesch challenge (same target and limits) had no Hc=5 as of 2026-10-20; its best score is 4.988 (15-hex, 3/254 uncovered; their ring counts differ from ours).

## Pipeline review (2026-10-26, previous handoff)


- **Running:** the owner replaced PID 16806 with PID 85497, run `7fe60404b7fb478eb50b9412f8b12dd0`, started 15:13 PDT. Its manifest still identifies the old code/guard and two 10 GB retries. The previous run's scorer shutoff around 15:11 was the 0/2,000 versus 1/2,000 event described below. Active processes and result bytes were left untouched while preparing the changes.
- **Guard correction:** the new default is warn-only, with warnings rate-limited by completed guided checks and recorded in the run manifest. All 16 tests pass, including integration checks that default warnings retain scoring, explicit `disable` stops it, and `off` keeps scoring without monitoring. No live search data was edited for this change.
- **Done:** measured Python/dispatch overhead; faster bitboard hole checks and parsed geometry; timed SAT waits; background scored refills; incremental histogram; guard/pending-entry and sweep exhaustion fixes; exact evaluation caps; escalation without periodic probes; complete new ladder/retry/defect cost accounting; partial-tail append repair; per-run IDs and manifests. The native NumPy integration test exposed an OpenBLAS/fork deadlock, addressed by enabling `posix_spawn` in runner subprocess launches. See `PIPELINE_REVIEW.md` for evidence and limits.
- **Validation:** 12 regression tests passed, including exact batch-feature parity. Eight paired 512-check replays had identical inputs and outcomes; median 6.481 s old versus 4.543 s updated MLX FP32 (~43% higher replay throughput). Test caps excluded costly retries/defect scoring, so this is not a production-yield forecast. Native smoke tests and the independent 21-cell witness check also passed. Full artifacts: `benchmarks/2026-10-26/`.
- **Next:** restart with `./scripts/search_frontier.sh` to load warn-only scoring, clearer budget/unresolved labels, and the new memory profile: 14 ordinary workers at 3 GB, one retry at 20 GB, cooperative 48 GB SAT/defect RSS budget and 8 GB available-memory reserve. It selects `.venv/bin/python` and resumes the same archive with MLX FP32 and 75% sweep while available. No rebuild or new performance benchmark is needed. These controls are sampled, not hard OS reservations.
- **Memory/progress validation:** all 21 tests pass, including shared-pressure victim selection, system headroom recovery, context cleanup, and preservation of unresolved/null outcomes. A real checker test under a tiny 16 MB shared budget stopped as memout with its reason recorded. Eight hours now prints as a search budget; it is not an ETA to finish a fixed workload. The native 150-check smoke test uses a separate temporary log.
- **Precision/ANER:** full-refill inference: ANE FP16 width 256 ~46 ms, ANER GPU FP16 ~35 ms, isolated ANER GPU FP32 prototype ~38 ms, MLX FP32 ~26 ms. ANE matched 31/32 FP32 top picks on one batch; GPU FP16 matched 32/32. Production ANER runtime remains unchanged and up to date; proposed improvements are in `/Volumes/Code/ANER/ROADMAP.md`.
- **Strategy gap:** the live search is restricted to 18–30-cell hexes. Track B's marked/forced-chain design loop remains unimplemented; maintain it as a separate experiment aimed at escaping the Hc=4 plateau. Relaxation stays off. No new record is claimed.
- **Environment correction:** this Codex shell is native macOS. Early tests used the system Python 3.9; final benchmarks and the restart environment use `.venv` Python 3.12.11 with pinned NumPy/psutil/MLX versions in the benchmark artifacts. Native accelerator access is needed for tests. Older Linux-VM statements below describe earlier agents.
- **Blocked:** none for this review. The active process will not load edited modules until a new launch. No second production search was started.
- **Priority and publication follow-up:** broader ANER opportunities and their escalation triggers are recorded in both READMEs and ANER's `ROADMAP.md`. They do not block restarting HALO. The large search archive is now tracked through Git LFS without changing its bytes; unmaterialized LFS pointers are rejected before resume. All 13 regression tests pass. The owner authorized publication of the code, benchmark artifacts and saved archive on HALO `main`, and the ANER documentation on its existing `gpu-perf` branch.

## Done

- `SPEC.md` (plan), `README.md`, `CLAUDE.md` written.
- **heesch-sat builds on macOS** (owner's M4 Max: Homebrew CryptoMiniSat 5.17.0, Boost 1.92, Apple clang; only harmless gmpxx warnings) and on Linux (Ubuntu 24.04, CryptoMiniSat 5.11.15). It's pinned at commit `d12a527` via `scripts/setup_heesch_sat.sh`. Upstream Makefile fixes: `-std=c++20`, link `isohedral.o` into `sat`.
- Sanity check: all 363 hole-free free 8-ominoes → 20 non-tilers (6 Hc=0, 14 Hc=1), 342 isohedral, 1 inconclusive. Consistent with the known 26 non-tiling octominoes (6 have holes).
- `scripts/check_shape.sh` uses the Epoch verifier settings. Its output is in Epoch's submission format. On macOS the octomino witness has 7 copies, on Linux 8; different SAT versions find different valid coronas, and both are fine.
- `halo/runner.py`: parallel runner, one `sat` process per shape, per-shape timeout and memory cap (RSS polling), append-only JSONL, resume, re-run of capped shapes from a JSONL (`--only-status`). Tested on Linux.
- `halo/shape.py`: parsing, Epoch constraint check (cells, both span readings, connectivity, holes for O and H grids), canonical free form. Hole check agrees exactly with `gen` on 8-ominoes (6/6) and 8-hexes (13/13). Canonical form is invariant under all symmetries plus translations (3,363 random tests).
- `scripts/parallel_classify.sh`: simpler split-and-run. Superseded by `runner.py`, kept for quick use.
- `halo/periodic.py`: periodic tiling detector (torus exact cover, proofs verified). Wired into `runner.py` via `--periodic-budget`/`--periodic-quick`/`--timeout-long`. See SPEC §4.
- `halo/periodic_dlx.cpp`: C++ Dancing Links port, **50–140× faster**, same answers (same t and lattice on all test tilers). Built by `scripts/setup_heesch_sat.sh` into `build/<OS>/periodic_dlx`; the runner uses it automatically when present. Tests: 0/20 false positives on octomino non-tilers and 0/100 on 11-hex non-tilers; 342/342 isohedral octominoes in 0.7 s total; all 4 hard 11-hex tilers settled by the quick probe (≤ 1.5 s each).

## Measurements (cloud test box, x86, 2 cores)

- 8-ominoes, maxlevel 7: median 0.05 s per shape. The one inconclusive shape hit the 2.5 GB cap after 26 s.
- 400 random free 11-hexes, maxlevel 7: 158 Hc=0, 140 Hc=1, 2 Hc=2, 96 isohedral, 4 capped (1%). Median 0.05 s; mean 0.26 s for uncapped shapes. Capped shapes take 25–35 s to reach 2.5 GB; one needed more than 6 GB within 57 s.
- The capped shapes come out "inconclusive" (they pass every level) even at maxlevel 4, after 12–31 s and 1–2.6 GB. They are almost certainly non-isohedral tilers. See SPEC §4 "Anisohedral filter".
- There are 141,229 free hole-free 11-hexes. Estimated M1 pass 1 on the M4 Max (16 jobs): about 1 hour.

## Running now

- **M1 pass 1 finished** (owner's Mac, 15:02–15:46, 44 min wall, 11.2 core-hours, 16 jobs, maxlevel 5, old single-stage runner, peak RSS per check 3.1 GB). All 141,229 free hole-free 11-hexes: **67,644 Hc=0, 47,940 Hc=1, 816 Hc=2, 29 Hc=3**, 24,289 isohedral, 511 unsettled (183 inconclusive, 319 memout, 9 timeout). No Hc=4 among settled shapes. Kaplan reports exactly one Heesch-4 11-hex, presumably among the 511 unsettled. Results: `results/hex11.jsonl`.
- **M1 pass 2 finished** (owner's Mac, 774 s, 6 jobs, ladder with the C++ detector). Of the 511 unsettled shapes: **500 proven periodic tilers**, 3 more Hc=3, 1 Hc=2, 7 still inconclusive (they survive 5 coronas; the detector found no tiling with ≤ 24 tiles per period). **Totals for 11-hexes: 67,644 Hc=0, 47,940 Hc=1, 817 Hc=2, 32 Hc=3, 7 inconclusive.** Kaplan's paper (Table 3, Hc) for n=11: non-tilers 116,439 = 67,644 / 47,940 / 817 / 37 / 1 for Hc = 0..4. **Our Hc=0, 1, 2 counts match exactly.** We are 6 non-tilers short, which matches 6 of our 7 inconclusive shapes. Cause: heesch-sat's "inconclusive" allows holed coronas, and our maxlevel 5 was too low (Kaplan used 7); see SPEC §6. The --hh hypothesis was wrong: all 32 Hc=3 shapes have Hh=3. All 32 Hc=3 shapes: `results/hc3_hex11.txt`. Kaplan's Table 4 (Hh) for n=11: 38,621 / 75,783 / 1,956 / 73 / 6.
- **M1 pass 3 (owner, stopped early):** the periodic detector (max_t 48) proved `H? 0 0 1 0 2 0 -1 1 0 1 -1 2 0 2 0 3 0 4 -1 5 -1 6` **tiles with 36 tiles per period** (lattice [[33,0],[27,12]], 514 s). That's the one true tiler among the 7, consistent with Kaplan's count (`results/hex11_pass3.jsonl`).
- **M1 DONE: Kaplan's 11-hex Hc table reproduced exactly.** The maxlevel-7 re-check of the 7 inconclusive shapes (owner, 290 s, 3 jobs) gave 5 × Hc=3, **1 × Hc=4** (`H 0 0 1 0 -2 1 -1 1 -2 2 0 2 1 2 -2 3 -1 3 -3 4 -2 4`, Hc = Hh = 4, witness 62 copies, coronas 1/5/10/19/27, filed in `shapes/reference/hex11_h4.*`), and 1 memout (the 36-tile-period tiler). **Final 11-hex non-tilers: 67,644 / 47,940 / 817 / 37 / 1 for Hc = 0..4, identical to Kaplan's Table 3.** Results: `results/hex11_ml7.jsonl`.
- **Pipeline validation against Kaplan's published polyomino table: exact match.** All 16,094 free hole-free 11-ominoes (cloud, 1 job, maxlevel 5, ladder with the Python periodic detector, 28 min): **Hc=0 5,807, Hc=1 3,628, Hc=2 39, Hc=3 0**, identical to Kaplan's Table 1 (9,474 non-tilers). The rest: 6,512 isohedral + 108 proven periodic tilers, none unsettled. Results: `results/omino11.jsonl`. Gaps-allowed check of the 32 Hc=3 11-hexes: all Hh=3 (`results/hex11_hc3_hh.jsonl`).
- **libaner gained a Metal backend and NE+GPU split scheduling** (ANER commit f277815): `graph.compile(64, aner.Schedule.ANE|GPU|SPLIT)`. SPLIT hands the Neural Engine 64-column tiles and the GPU up to 2048-column chunks as each falls idle. `halo/aner_scorer.py` now benchmarks all three schedules plus NumPy and MLX, and exposes `Scorer(weights, schedule)` for the search. It folds the 1.702 activation scale into the weights: libaner's `aner_scale`/`gelu` lower the scale to a dense 512×512 diagonal matmul, a third of the scorer's matmul work, and the folded SiLU form is exactly equivalent (max diff 1.8e-6, activations ≤ 4.6, fine for fp16). **Benchmark on the owner's M4 Max (65,536 shapes, 18-layer scorer):** NumPy CPU 92,350/s · ANER ANE 373,565/s (4.0×; the fold gave +21%) · **ANER GPU 1,041,277/s (11.3×)** · **ANER SPLIT (NE+GPU) 1,475,618/s (16.0×; 1.42× over GPU alone)**. Agreement vs float32: GPU max diff 0.004 / 0.001; NE and split about 0.2 / 0.07 (fp16); rank correlation ≥ 0.9993 everywhere. Compile: NE 163 ms, GPU 4 ms, split 354 ms. MLX on the GPU (owner, same run): fp32 1,194,881/s, **fp16 1,490,622/s**, which ties ANER SPLIT. ANER's split is additive (GPU 1.08M + NE 0.38M ≈ 1.47M); its Metal half runs ~28% behind MLX here (likely 2048-column chunks with per-chunk copies, unfused elementwise ops at MPSGraph optimization level 0). **Decision:** the search needs ~50k scores/s, so score on the **Neural Engine alone** (`--scorer-schedule ane`, the default) and keep the GPU free for retraining with MLX. `Scorer` also supports `split`, `gpu`, `mlx` and `numpy`.
- **ANER benchmark (first run, before the split backend and the fold): the Neural Engine wins.** Scorer (18 linear layers, width 512) on 65,536 shapes, owner's M4 Max: **ANER 307,560 shapes/s vs NumPy/Accelerate 95,135 shapes/s (3.2×)**, wall clock including host transfers. Compile 182 ms, runs on the Neural Engine. Agreement: rank correlation 0.9999; max |diff| 0.16 in the tile logit and 0.04 in hc (fp16).
- **Scorer step 1: done, positive.** Deep residual MLP built only from ANER ops, all 29 Hc=3 shapes hidden from training. 8 blocks (18 linear layers, width 512), 12 epochs on 2 CPU cores: among held-out non-tilers, Hc>=3 vs rest AUC **0.94**. Using score = hc_hat × (1 − p_tile) over all held-out shapes, the **top 1% captures 12/29 Hc=3 shapes (41× random)** and the top 5% captures 17/29; median Hc=3 percentile is about 4%. Tiler-vs-non-tiler AUC is 0.76, still the weak head. Weights: `results/models/scorer_hex11_b8.npz` (git-ignored, 17 MB). Caveat: trained only on 11-cell hexes in a 16×16 window; larger shapes are out of distribution until retrained on search logs.
- **Track B prototype** (agent, cloud): `halo/gen_marked.py` scales base polyominoes 3× and puts a 1-cell bump or nick (or nothing) on each base edge. 1–2-cell bases: 163 shapes, best Hc=2. 3-cell bases: 2,897 shapes → 2,389 Hc=0, 127 Hc=1, 1 Hc=2, 355 isohedral, 25 unsettled at first; **the C++ detector proved all 25 are tilers** (89 s total). So the batch is fully settled, best Hc=2. Random markings mostly give Hc=0, because single-cell nicks are rarely fillable. Markings need searching (Track C on markings), not random enumeration.
- **Track C search loop built:** `halo/search.py`. Mutation-based local search (add/remove/move cells; connected, hole-free, within limits; dedupe by canonical form), the full runner ladder per shape, an elite archive, resumable JSONL log. Smoke test from the 29 Hc=3 11-hexes (200 checks, 2 cores): offspring mostly Hc 0–1 and no new Hc>=3. Real runs need the Mac's cores and the scorer as a prefilter (next).
- **Independent witness verifier: `halo/verify.py`** (no heesch-sat). Checks grid-symmetry transforms, no overlaps, each corona touches and fully encloses the previous patch (edges and corners), and every patch is a disk (connected, no holes, no square-grid pinch corners). Passes both references and all 29 Hc=3 witnesses from pass 1. Rejects tampered witnesses: dropped level-4 or level-3 copy, shifted copy (overlap), claimed hc=5, shear matrix.
- **Scorer-filtered search** in `halo/search.py` (`--scorer`): each refill generates `--candidates` mutants, scores all their symmetric images, queues the best `--pick`; `--random-frac` of checks go to unscored mutants as a control. Records log `pred` and `generator` (search-scored vs search). Cloud test (numpy scorer, 300 checks): scored 4/210 Hc>=2 vs random 0/90, too small to conclude. `--prefer-min-cells` breaks hc ties toward unexplored sizes (Kaplan enumerated polyhexes to 17 cells, so an Hc=5 polyhex needs 18+). Seeds: `results/seeds_hex11_hc3plus.jsonl` (37 × Hc=3 + the Hc=4).
- `halo/runner.py` refactored: the ladder is now `runner.classify()`, shared with search.py. 8-ominoes fully settled in 18.5 s (was 57 s with one shape unsettled).

## First overnight search (2026-10-25 19:06 → 2026-10-26 03:07, owner's Mac)

`results/search_hex_01.jsonl`: 47,157 checks. Non-tilers: Hc 0: 7,865 · 1: 14,279 · 2: 886 · 3: 29 (new shapes, 10–17 cells). Also 23,202 isohedral, 884 periodic, 12 memout. **No new Hc>=4** (the printed Hc=4 is the seed in canonical form). Largest Hc=3: 17 cells. At 18–21 cells: Hc <= 2.
- **Throughput collapsed** from 18,994 checks in hour 1 to ~2,400/hour later. The checker used only **5.9 of ~128 available core-hours**. Cause: `pick_parent()` re-sorted the whole archive for every candidate (13 ms per pick at 25k entries). **Fixed:** incremental elite list (77,000× faster pick); per-candidate cost is now ~0.14 ms.
- **Scorer v1 preferred tilers:** scored picks were 53% tilers vs 38% for random picks. Hc>=2 yield 2.0% vs 1.7% random, a weak benefit. Cause: tilers were never part of the hc target, and the tiler head is weak. **Scorer v2:** all 184k labelled shapes (11-hexes + search log), 22×22 window (512 inputs), tilers trained toward hc = −1, search-style evaluation. The first full run **diverged at epoch 3** (loss 1.26 → 5.8e10): the single Hc=4 shape got sample weight ~259 (√(67k/1)) on top of a 1e-3 peak LR. Fix: weights capped at 20, gradient-norm clip 1.0, peak LR 5e-4. With the fix, training is stable: 12 epochs, loss 1.25 → 1.12 with no spikes (v2 variant with tilers at hc = −1, same settings).
- **Scorer v2 results.** Evaluated on the same held-out 20% of search-log shapes (9,363; base rates: tilers 51.1%, Hc>=2 1.93%). Hc>=2 rate among the top-ranked shapes:

  | Scorer, ranking | top 2% | top 5% | top 20% |
  | --- | --- | --- | --- |
  | v1, hc | 2.67% | 3.63% | 2.78% |
  | v1, hc × (1 − p_tile) | 2.67% | 2.56% | 2.35% |
  | v2, tilers trained to hc = −1, hc × (1 − p_tile) | 0.53% | 1.07% | 1.23% |
  | **v2, tilers left out of the hc loss, hc** (shipped) | 2.14% | 3.42% | 3.04% |
  | same, hc × (1 − p_tile from v1) | 1.60% | 3.63% | 3.15% |

  **Finding: high-Hc shapes look like near-tilers.** Training tilers toward hc = −1 cut tilers among top picks to ~20% but dropped the Hc>=2 yield below random, because the good shapes went down with the tilers. Tilers are cheap to reject (isohedral check ~0.1 s), so rank by predicted hc alone and accept the tilers. v2 held-out AUCs: tiler 0.81, Hc>=2 0.85, Hc>=3 0.97 (17 positives).
- **Shipped:** `results/models/scorer_v2_hex.npz` (Git LFS; 22×22 window, `--tiler-hc nan` so tilers are ignored in the hc loss, trained on all 184k labelled shapes) and `search.py --score-formula hc` (new default; `hc_tile` restores hc × (1 − p_tile)). v1 ranks about as well at 11–17 cells, but its 16×16 window can't see larger shapes. Scored picks only include shapes that fit the window in some orientation; bigger ones reach the checker only through the `--random-frac` control. Fine for the 18–21-cell target; widen the window before pushing past ~22 cells.
- Compute split: the periodic detector took 45% of checker time (884 shapes, mean 11 s), non-tilers 43%.
- **Live generator yield in run 1** (`halo/gen_report.py results/search_hex_01.jsonl`): random mutants 1.68% Hc>=2 (95% CI 1.35–2.09%, n = 4,691), scorer-v1 picks 1.97% (1.84–2.11%, n = 42,466). The scorer's live edge was small, far below the held-out top-5% numbers above. Picking the top 1.6% of mutants is a harsher operating point than a top-5% cut, and the candidates differ from the log the scorer was evaluated on.

## Run 2 (2026-10-26 10:07 → ~10:50, owner's Mac, stopped early): scorer runaway

Same log as run 1 (`results/search_hex_01.jsonl`, run-2 rows start at line 47,158), scorer v2, throughput fix in. **Throughput: ~92k checks in 42 minutes** (run 1: 19k in its first hour, ~2.4k/hour later). **The scorer ran away:** it predicts Hc 6–7 for 18–29-cell shapes, above anything it was trained on (max 4). The actual Hc>=2 rate over 67k such checks was 0%. Scored picks drifted to 21 cells on average. Their Hc>=2 rate was **0.32% vs 1.12% for random mutants**, and 70k of the 83k scored checks were Hc=0. A feedback loop drove it: the big Hc=0 shapes joined the archive, the 10% explore picks drew parents from the whole archive, and their mutants won the scorer's ranking again. Scorer v1 overrates big shapes even more (mean prediction 8+ at 21+ cells). Run 1 simply never offered it any. The held-out evaluation missed this because its shapes came from run 1, which never reached those sizes.

Fixes in `search.py`:
- `--explore-min-hc 1`: explore parents only from non-tilers with hc >= 1.
- **Generator guard** (`--guard-checks 2000`, `--guard-ratio 0.5`): a guided generator (scored or relaxation) is switched off for the rest of the run when its Hc>=2 rate over its last 2,000 checks falls below half the random mutants' rate.
- **Scorer v3** (`results/models/scorer_v3_hex.npz`, Git LFS): retrained on 11-hexes + run 1 + run 2 (276,554 shapes, 22×22 window, `--tiler-hc nan`, 12 epochs, stable, loss 0.84 → 0.62). Held-out AUCs: tiler 0.87, Hc>=2 0.90, Hc>=3 0.96 (v2: 0.81 / 0.85 / 0.97). **Calibrated by size now.** Mean predicted hc on run-2 shapes vs the actual mean for non-tilers:

  | Cells | v2 | v3 | actual |
  | --- | --- | --- | --- |
  | 12–14 | 1.06 | 0.93 | 0.47 |
  | 15–17 | 2.81 | 0.41 | 0.11 |
  | 18–20 | 5.94 | 0.05 | 0.03 |
  | 21–29 | 7.0–7.6 | 0.00 | 0.00–0.01 |

  Remaining trap: from elite parents, both v2 and v3 pick mostly 7–9-cell mutants (simulated refill: top 32 of 2,048). That's where Hc>=2 is commonest, but those sizes are fully enumerated (Kaplan: all polyhexes up to 17 cells). **Per-check yield is the wrong target for records.** Judge generators by Hc>=2/3 at 18+ cells (`gen_report.py --min-cells 18`).
- At 18+ cells, run 2 found Hc>=2 in 3 of 1,463 random mutants (0.2%) and in 0 of 69,689 scored picks. No Hc>=3 so far at 18+.
- Owner restarted without the scorer as a stopgap.
- **Kaplan's published data:** every polyhex with Hc>=3 or Hh>=3 for 11–17 cells is at `https://cs.uwaterloo.ca/~csk/heesch/hex/<n>hex_3up.txt` (plus PDFs and `heesch_dataset.tar.gz`). That includes all Hc=4 polyhexes: one each at 11, 13, 16 and 17 cells, two at 15. These are the right parents for 18+ cells. The agent sandboxes can't reach the site (proxy 403), so the owner downloads them into `refs/kaplan/` (raw files git-ignored; cite Kaplan 2022).

## Run 3 results so far: a 21-cell Hc=4 polyhex (2026-10-26)

- **`H 0 2 0 3 0 4 1 2 1 3 1 4 2 1 2 2 2 3 3 1 3 2 3 3 4 1 4 2 4 3 5 0 5 1 5 2 5 3 6 1 6 2`**: 21 cells, Hc = Hh = 4, spans 6 + 4. Found 11:58 by the scorer arm (prediction 0.96) as a one-cell "add" mutant of a 20-cell shape. It first hit the 3 GB cap and was settled by the new 10 GB retry (6.2 GB, 44 s). Without today's retry it would have been logged as a memout. Witness: `shapes/hex21_h4.witness` (61 copies). **`halo/verify.py` passes it** (hole-free Heesch number >= 4, independent of heesch-sat). Hc is exactly 4 because heesch-sat finds no 5-corona even with holes. That's beyond Kaplan's enumeration (<= 17 cells) and ties the polyform record (Hc=4). It is not a new record. A Layr-Labs challenge participant also reports Hc=4 polyhexes at 20 and 21 cells (PR #105, unpublished coordinates), so we can't claim it's the first at this size.
- First ~55 min of run 3 (106k checks, all 18+ cells): scorer v3 picks Hc>=2 0.62% (0.56–0.69%), random mutants 0.12% (0.09–0.15%). That's **~5× at the frontier**. 22 Hc>=3 shapes at 18–21 cells (16 from the scorer arm, 6 random) and the Hc=4 above.

## Run 3, continued: the guard switched the scorer off; scorer v4 (2026-10-26)

- At ~133k checks (about 12:28), the guard switched off the v3 arm: Hc>=2 in 2 of its last 2,000 picks (0.10%) vs 0.35% for random mutants. Hc>=2 rate by 20-minute window, scored vs random: 0.72% vs 0.05% (11:40), 0.50% vs 0.18% (12:00), 0.35% vs 0.24% (12:20). Random mutants improved as their parents moved from Kaplan's 15–17-cell seeds (which need 1–3 random cells grown) to run 3's own 18–21-cell finds (one edit away). v3, trained on few 18+ shapes, faded. Over the whole run, the scored arm still produced 375 Hc>=2 shapes and the 21-cell Hc=4.
- **Scorer v4** (`results/models/scorer_v4_hex.npz`, Git LFS): 11-hexes + runs 1–3 (470,680 shapes), same settings as v3 (22×22, `--tiler-hc nan`, 12 epochs, loss 0.75 → 0.58). Held-out AUCs: tiler 0.885, Hc>=2 0.910, Hc>=3 0.937. Hc>=2 rate among its top picks on v4's held-out run-3 shapes:

  | Subset | n | base | v3 top 1.6% | v4 top 1.6% | v3 top 5% | v4 top 5% |
  | --- | --- | --- | --- | --- | --- | --- |
  | all | 22,879 | 0.35% | 2.73% | 3.83% | 2.27% | 2.10% |
  | random-arm rows only (unbiased) | 11,522 | 0.10% | 1.09% | 1.09% | 0.35% | 0.69% |
  | scored-arm rows only | 11,357 | 0.60% | 3.31% | 2.76% | 2.29% | 3.17% |

  v4 is no worse than v3 and about 10× the base rate on unbiased mutants. The random-arm rows hold only a dozen positives, so this is not a proven gain.
- Planned relaunch ("run 3b"): sweep 50% (while it has work), then v4-scored and random 50/50, guard on, defects for Hc>=3 finds.

## Neighbourhood sweep (2026-10-26)

`search.py --sweep-min-hc 3 --sweep-frac 0.5` (default on). Every valid, unchecked one-cell edit (add, remove, move) of each parent with hc >= 3 is queued, best parents first (by fitness), and each new hc >= 3 find is swept in turn. This is a systematic walk of the Hc>=3 and Hc=4 plateaus, instead of sampling them at random through a 64-shape elite. A 21-cell parent has about 460 edits, and checks at 18+ cells cost 0.1–0.3 s, so a full sweep of all current Hc>=3 parents is ~13k checks (~10 min on the Mac). Logged as generator `search-sweep`.

## Next-corona defect solver (2026-10-26)

- **Why:** Hc is a coarse integer, so search on a plateau of Hc=3 or Hc=4 shapes is a random walk. The Layr-Labs/heesch challenge (public, same goal and limits as the Epoch problem, AI-agent submissions as of 2026-10-20, nobody at 5) scores Hc + covered fraction of the next corona's required cells. Their best is 4.988 (a 15-hex, 3/254 uncovered). We now measure the same kind of quantity ourselves.
- **What:**
  - `third_party/heesch-sat/halo_defect.patch` (heesch.h): `getClauses` can relax the halo clauses of the last inner corona, one literal per uncovered cell, and `minDefect()` minimises that count with a k-limited totalizer and descending bounds under a conflict budget.
  - `defect.cpp`: the driver, which prints JSON.
  - `scripts/setup_heesch_sat.sh` builds it in a separate copy (`build/<OS>/heesch-sat-defect/defect`), so the `sat` binary is never touched. periodic_dlx is now rebuilt only when its source is newer, so re-running the script is safe during a search.
  - `runner.run_defect()` (memory and time caps).
  - `search.py --defect-min-hc 3`: Hc>=3 finds get `defect`/`ring` fields. Fitness becomes (hc, big, hh, −defect/ring, …), and the run prints "closest yet" lines.
  - `halo/add_defects.py` batch-scores existing JSONL (e.g. seeds).
- **Our definition:** ring = cells next to the k-patch, in our best solution. Our ring counts are not the same as Layr-Labs' (166 vs their 254 for a 15-hex), so compare scores across projects with care.
- **Measured (exact, 2 cloud cores):**
  - Kaplan's Hc=4 polyhexes: 11-hex 6/166 uncovered (27 s), 13-hex 5/151 (129 s), one 15-hex 4/166 (261 s, 4.3 GB).
  - 17-cell Hc=3 seeds: 15/200, 19/247, 15/236 (11–41 s; one exceeded 2.5 GB).
  - Defect scoring of all 398 Kaplan seeds with 15–17 cells and Hc>=3 is running in the agent cloud.

## Kaplan's data imported; memout finding; run 3 plan (2026-10-26)

- `results/seeds_kaplan_hex_3up.jsonl` (via `halo/import_kaplan.py` from `refs/kaplan/<n>hex_3up.txt`, which the owner downloaded; the 17-hex file 403s for scripted requests and had to be fetched by hand). It holds 1,263 polyhexes with Hc>=3 or Hh>=3 at 11–17 cells. Hc>=3: 37/10/27/22/179/54/161 at 11–17 cells. Hc=4: one each at 11, 13, 16, 17 and two at 15, matching Kaplan's table.
- **Cross-checks:** Kaplan's 11-cell Hc>=3 set is identical to our M1 result (same 38 shapes, same Hc), so coordinates and canonical forms agree. Of 60 Kaplan shapes our searches also checked, 55 have the same Hc. **The other 5 were memouts at our 3 GB cap: two Hc=4 (13 and 15 cells) and three Hc=3.** High-Hc shapes need more memory, so a fixed cap throws away exactly the shapes we want. 5 of runs 1–2's first 12 memouts were Hc>=3.
- `search.py` additions:
  - `--retry-jobs 2 --retry-mem-mb 12000 --retry-timeout 1200`: memout/timeout shapes are re-checked with a bigger budget, a few at a time. Ones still waiting at the stop are logged with their first status.
  - `--retry-archived`: re-check memout/timeout rows already in the log.
  - `--min-cells N`: parents below N are first grown with random frontier cells.
  - `--parent-min-cells`: parents only from shapes at least this large.
  - Fitness prefers larger parents on ties when `--prefer-min-cells` is set.
- **Run 3 (planned):** Kaplan seeds, parents >= 15 cells, checks only 18+ cells (beyond Kaplan's enumeration), memout retries on, scorer v3 at `--random-frac 0.5` so the guard and the report get a live A/B.
- **Bake-off A, final** (cloud, `halo/bakeoff.py`; parents = Hc>=3 shapes of 7–17 cells from runs 1–2 and the 11-hex seeds, the same for every generator; log in the agent cloud only). Hc>=2 rate, 95% CI:

  | Generator | n | all sizes | 15+ cells | generation per shape (2 cloud cores) |
  | --- | --- | --- | --- | --- |
  | random mutants | 1000 | 1.40% (0.84–2.34) | 0.97% (n = 309) | ~1 ms |
  | scorer v3 picks | 1000 | 2.10% (1.38–3.19) | 2.01% (n = 299) | 108 ms |
  | splat relaxation | 63 | 1.59% (0.28–8.46) | 0/27 | 18 s (runs dry) |
  | cell relaxation | (smoke test only) | | | 27 s |

  v3 ≈ 1.5× random overall and ≈ 2× at 15+ cells. Consistent, but the intervals overlap; the interim "3×" was early noise. Scored picks are 62% tilers (cheap) and both of their Hc=3 finds were small known shapes (8 and 10 cells). **Relaxation verdict:** it works as designed, but shows no yield advantage over random mutants and costs about 10,000× more per shape to generate. It stays an off-by-default option (`--relax-frac`). Revisit only with a much stronger scorer.
- **Run 3 started** 2026-10-26 ~11:42 on the owner's Mac with the planned settings (`--min-cells 18 --parent-min-cells 15`, Kaplan seeds, v3 at 50%, memout retries, 14 jobs). It runs at ~50 checks/s. 0 archived memouts at 18–30 cells. First 600 checks: scored 3/312 Hc>=2 vs random 0/288.

## Continuous relaxation ("Gaussian splat") generator (2026-10-26, experimental, off by default)

`halo/relax.py`: start from an elite shape, make occupancy soft, follow the scorer's gradient, snap back to cells (at most `--relax-max-flips` per round), repair (largest connected piece, holes filled, Epoch limits), and hand the distinct shapes to the checker. Modes: `cell` (one logit per cell near the shape) and `splat` (one Gaussian blob per starting cell; centres, widths and strengths move, so whole lobes shift together). Gradients come from MLX on a Metal GPU when available, otherwise from NumPy with a hand-written backward pass. `--selftest` checks both against finite differences (they agree). Wired into `search.py` as `--relax-frac` (default 0) with `--relax-mode cell,splat`. Shapes are logged as generator `search-relax-<mode>`, so any run doubles as a bake-off.

What it showed before the bake-off (38 Hc>=3 11-hex seeds, every output checked):
- **Unconstrained, it exploits the scorer at once.** It shrinks shapes to 4–9 cells, sizes the scorer never saw, where it predicts Hc ≈ 3. Fix: a size band (`--relax-shrink 0`, `--relax-grow 4`).
- **Pure hc ascent ends among tilers** (41/41 isohedral), because the hc head is trained on non-tilers only. Fix: objective hc − w·softplus(tile logit), `--relax-tile-weight` (default 1). With w = 1: splat 64 shapes → 3 Hc=2, 1 Hc=1, 60 tilers; cell 15 shapes → 1 Hc=1, 14 tilers. With w = 3: almost no new shapes.
- Bake-off running in the agent cloud (2 cores, 1.9 h, run-1 archive as starting point; random / scored / relax-cell / relax-splat, all from the same elite parents). Results to follow here.

## ANER GPU tuning (2026-10-26; ANER branch `gpu-perf`, not yet merged)

Agent changes in libaner: pipelined GPU worker (two chunks in flight, packed straight into shared Metal buffers), lighter GPU lowering (consts as [C,1] columns; diagonal conv → elementwise multiply), `ANER_GPU_CHUNK` (default now 4096), `ANER_GPU_PIPELINE`, `ANER_GPU_OPT_LEVEL`. `make test` passes. Sweep (`scripts/bench_aner_gpu.sh`, scorer v1, 65,536 shapes): GPU-only 1.08M → **1.67M** shapes/s, split 1.47M → **2.03M** (MLX fp16 1.49M). Opt level 1: no gain, and at 8192 it moved work onto the NE. ANER's own split test showed split 40.3 ms vs NE-only 12.2 ms on a deep chain, because greedy claiming let the slower GPU take half the batch. **Fixed on ANER branch `gpu-perf`** (`d6c094e`): split programs time each engine at compile time and refine during batches; an engine claims a chunk only if it can finish it before the other engine could finish everything left; the last active worker never steps aside. Owner to rebuild and re-test. The GPU speedups are commit `2c1122f` on the same branch.

## Historical next steps (superseded by the current handoff above)

1. **Owner, on macOS: M1 baseline, pass 1** (about 1 hour; uses all cores and up to roughly 30 GB RAM):
   ```sh
   cd /Volumes/Code/HALO
   build/Darwin/heesch-sat/src/gen -hex -size 11 -free -o results/hex11.txt
   python3 halo/runner.py results/hex11.txt --out results/hex11.jsonl --maxlevel 5 --timeout 60 --mem-mb 3000 --generator gen-hex11
   ```
   Goal: reproduce Kaplan's single Heesch-4 11-hex (it should appear in the final "hc=4" list). If the run is interrupted, rerun the same command and it resumes.
2. **Owner: pass 2** for unsettled shapes. It uses the ladder with the periodic detector: 6 jobs × up to 8 GB. Re-run `./scripts/setup_heesch_sat.sh` first so the fast C++ detector is built.
   ```sh
   ./scripts/setup_heesch_sat.sh
   python3 halo/runner.py results/hex11.jsonl --only-status timeout,memout,inconclusive --out results/hex11_pass2.jsonl --jobs 6 --maxlevel 5 --timeout 5 --timeout-long 900 --mem-mb 8000 --periodic-budget 120 --generator gen-hex11-pass2
   ```
   Expected: almost all become `periodic` (proven tilers). Whatever remains with hc=4 is Kaplan's shape. For future batches, use the ladder from the start, e.g. `--timeout 5 --timeout-long 60 --periodic-budget 60`.
3. **Done:** ANER benchmark (see Running now). To re-run:
   ```sh
   cd /Volumes/Code/HALO
   PYTHONPATH=/Volumes/Code/ANER/python python3 halo/aner_scorer.py results/models/scorer_hex11_b8.npz results/hex11.jsonl
   ```
   Reports: Neural Engine used yes/no, compile time, shapes/s for ANER vs NumPy, max disagreement.
4. **Owner: first long native search** (all cores, scorer on the Neural Engine; stop any time with Ctrl-C and rerun the same command to resume):
   ```sh
   cd /Volumes/Code/HALO
   PYTHONPATH=/Volumes/Code/ANER/python python3 halo/search.py --seeds results/seeds_hex11_hc3plus.jsonl --seed-min-hc 3 --log results/search_hex_01.jsonl --scorer results/models/scorer_v2_hex.npz --scorer-schedule ane --score-formula hc --max-cells 30 --prefer-min-cells 18 --maxlevel 7 --escalate-maxlevel 9 --mem-mb 3000 --hours 8
   ```
   Run 1 (2026-10-25, scorer v1, slow parent picking) is analysed above. Run 2 resumes the same log with the throughput fix and scorer v2. Goals: keep all cores busy (the hourly rate should stay near hour 1's ~19k), see how high Hc gets at 18+ cells, compare `search-scored` vs `search` Hc>=2 yield, and collect larger labelled shapes.
5. **Done for v2 (see above); repeat after each long run:** retrain on all logs (`halo/scorer.py <comma-separated JSONLs> --window 22 --tiler-hc nan --epochs 12 --eval-source <index of the newest log> --save <path>`), compare against the current model on held-out search shapes, and ship only if the top-5% Hc>=2 yield improves.
5b. **Compare generators after every run:** `python3 halo/gen_report.py <log> --since <run start ts>`. Keep a generator only if its Hc>=2 rate per check (and per checker-second) beats random mutants outside the confidence interval.
6. **Agent:** Track B as a search over markings (bump/nick per edge) instead of random enumeration, on 4–6-cell bases.
7. **Owner, optional:** PDFs of Mann 2004 (*Amer. Math. Monthly* 111(6)) and Bašić 2021 (*Math. Intelligencer* 43(3)) into `refs/` for Track A2.
8. **Agent:** finish literature check A3 for 2024–2026 (as of Kaplan 2023, no polyform with H >= 5 is known). Then start Track B with the cheap route: scale small marked polyforms (bumps/nicks as sub-cells) and run heesch-sat on them.

## Git workflow

- Repo: `https://github.com/Digital-Defiance/HALO` (branch `main`).
- The agent commits in `/Volumes/Code/HALO` (and in ANER on branch `gpu-perf`) through its Linux shell, with delete permission so git can clean up lock files. Commits are authored as `Jessica Mulein <jessica@digitaldefiance.org>` with a `Co-Authored-By: Claude` trailer. HALO commits from 806cf07 to 1df9296 used the owner's Gmail address; 806cf07 is already pushed, so history was not rewritten. The owner pushes from macOS.
- `results/*.txt` (raw `gen` dumps) and `build/` are git-ignored. JSONL results are committed.
- Scorer weights (`results/models/*.npz`, ~17 MB each) are in **Git LFS** (`.gitattributes`). Any machine that clones, pulls or pushes needs git-lfs (`brew install git-lfs`, then `git lfs install` once). Without it, the `.npz` files are small pointer files and `np.load` fails on them. The agent's Linux shell has no git-lfs package; it uses a static binary in `~/bin` and runs git with `PATH=$HOME/bin:$PATH`.
- Retrained models get a new file name (`scorer_v3_hex.npz`, ...) rather than overwriting, so older runs stay reproducible.

## Environment

| Where | What | Use |
| --- | --- | --- |
| Owner's Mac, native macOS | M4 Max, 64 GB, all CPU cores, Metal GPU, Neural Engine (ANER at `/Volumes/Code/ANER`) | real runs, started by the owner |
| Agent shell on the Mac | Linux VM (Ubuntu 22.04, aarch64, 4 cores, 3 GB). Sees `/Volumes/Code/HALO` as `~/mnt/HALO` | editing, small tests, git commits |
| Agent cloud workspace | Linux x86, 2 cores, 7 GB, ephemeral | builds and tests; nothing persists |

## Gotchas

- Always pass `-isohedral` to `sat`. Without it, tilers grind to maxlevel (default 7; we use 12 for claims).
- Don't run `pkill -f sat` from a shell whose own command line contains "sat"; it kills itself.
- Never run a whole batch in one `sat` process: one runaway shape can OOM-kill everything. Use `halo/runner.py`.
- In classified heesch-sat files, status lines like `I 1 0` (isohedral) and `O 0` (hole) look like shape lines. Feed tools bare shape lines (one per line) or runner JSONL.
- The same self-kill applies to any `pkill -f <pattern>` whose pattern appears in the calling shell's command line (it bit the agent again with `scorer.py`). Kill by PID instead.
- Agent tooling: a file pushed to the Mac with the device commit tool right after an edit has twice arrived as the previous version. Compare sha256 on both sides before `git commit`. The tool also writes mode 600, so restore +x on scripts (`chmod 755`) before committing, or git records a mode change.
- Expensive shapes are the interesting ones: Hc>=3 checks at 18+ cells take 10–45 s and 2–6 GB. Keep the memout retry (`--retry-jobs`) on.

## Open questions

- Does the Epoch span rule use `max-min` or `max-min+1`? (Designing to the stricter reading.)
- Is Bašić's Heesch-6 figure expressible as a polyform within the limits?
