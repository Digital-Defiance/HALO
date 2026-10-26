# HALO status

Last updated: 2026-10-25 (session 1, Claude). Current phase: **M1 done (11-ominoes and 11-hexes match Kaplan exactly). Scorer runs at 1.48M shapes/s on NE+GPU via ANER. Search loop built. Next: scorer-filtered search toward the first Hc=5 polyform (M4).**

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
   PYTHONPATH=/Volumes/Code/ANER/python python3 halo/search.py --seeds results/seeds_hex11_hc3plus.jsonl --seed-min-hc 3 --log results/search_hex_01.jsonl --scorer results/models/scorer_hex11_b8.npz --scorer-schedule ane --max-cells 30 --prefer-min-cells 18 --maxlevel 7 --escalate-maxlevel 9 --mem-mb 3000 --hours 8
   ```
   Goals: measure throughput at larger sizes, see how high Hc gets at 18+ cells, and collect labelled larger shapes to retrain the scorer.
5. **Agent:** retrain the scorer on search logs with a bigger window (22×22 = 484 channels) for larger shapes, training on the GPU (MLX) or in the cloud. Measure scored-vs-random yield from the search log.
6. **Agent:** Track B as a search over markings (bump/nick per edge) instead of random enumeration, on 4–6-cell bases.
7. **Owner, optional:** PDFs of Mann 2004 (*Amer. Math. Monthly* 111(6)) and Bašić 2021 (*Math. Intelligencer* 43(3)) into `refs/` for Track A2.
8. **Agent:** finish literature check A3 for 2024–2026 (as of Kaplan 2023, no polyform with H >= 5 is known). Then start Track B with the cheap route: scale small marked polyforms (bumps/nicks as sub-cells) and run heesch-sat on them.

## Git workflow

- Repo: `https://github.com/Digital-Defiance/HALO` (branch `main`).
- The agent commits in `/Volumes/Code/HALO` through its Linux shell. It has delete permission for that folder this session, so git can clean up its lock files. Commits are authored as the owner with a `Co-Authored-By: Claude` trailer. The owner pushes from macOS.
- `results/*.txt` (raw `gen` dumps) and `build/` are git-ignored. JSONL results are committed.

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
