# HALO status

Last updated: 2026-10-26 (session 1, Claude). Current phase: **M1 done. First overnight search (47k checks) found nothing above Hc=3 beyond the seeds. It was throttled by a Python bug (fixed). Scorer v2 trained (`scorer_v2_hex.npz`, 22×22 window); ranking by predicted hc alone works best because high-Hc shapes look like near-tilers. ANER GPU path sped up 1.55× (split 2.03M shapes/s) on ANER branch `gpu-perf`, awaiting the owner's rebuild and test. Next: rerun the search with the fix and scorer v2 (Next steps, item 4).**

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

## Next steps (in order)

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

## Open questions

- Does the Epoch span rule use `max-min` or `max-min+1`? (Designing to the stricter reading.)
- Is Bašić's Heesch-6 figure expressible as a polyform within the limits?
