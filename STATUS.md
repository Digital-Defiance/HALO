# HALO status

Last updated: 2026-10-25 (session 1, Claude). Current phase: **M1 baseline running on the Mac (pass 1). Periodic tiling detector built and wired into the runner.**

## Done

- `SPEC.md` (plan), `README.md`, `CLAUDE.md` written.
- **heesch-sat builds on macOS** (owner's M4 Max: Homebrew CryptoMiniSat 5.17.0, Boost 1.92, Apple clang; only harmless gmpxx warnings) and on Linux (Ubuntu 24.04, CryptoMiniSat 5.11.15). It's pinned at commit `d12a527` via `scripts/setup_heesch_sat.sh`. Upstream Makefile fixes: `-std=c++20`, link `isohedral.o` into `sat`.
- Sanity check: all 363 hole-free free 8-ominoes → 20 non-tilers (6 Hc=0, 14 Hc=1), 342 isohedral, 1 inconclusive. Consistent with the known 26 non-tiling octominoes (6 have holes).
- `scripts/check_shape.sh` uses the Epoch verifier settings. Its output is in Epoch's submission format. On macOS the octomino witness has 7 copies, on Linux 8; different SAT versions find different valid coronas, and both are fine.
- `halo/runner.py`: parallel runner, one `sat` process per shape, per-shape timeout and memory cap (RSS polling), append-only JSONL, resume, re-run of capped shapes from a JSONL (`--only-status`). Tested on Linux.
- `halo/shape.py`: parsing, Epoch constraint check (cells, both span readings, connectivity, holes for O and H grids), canonical free form. Hole check agrees exactly with `gen` on 8-ominoes (6/6) and 8-hexes (13/13). Canonical form is invariant under all symmetries plus translations (3,363 random tests).
- `scripts/parallel_classify.sh`: simpler split-and-run. Superseded by `runner.py`, kept for quick use.
- `halo/periodic.py`: periodic tiling detector (torus exact cover, proofs verified). Wired into `runner.py` via `--periodic-budget`/`--periodic-quick`/`--timeout-long`. See SPEC §4.
- `halo/periodic_dlx.cpp`: C++ Dancing Links port, **50–140× faster**, same answers (same t and lattice on all test tilers). Built by `scripts/setup_heesch_sat.sh` into `build/<OS>/periodic_dlx`; the runner uses it automatically when present. Tests: 0/20 false positives on octomino non-tilers; 342/342 isohedral octominoes in 0.7 s total; all 4 hard 11-hex tilers settled by the quick probe (≤ 1.5 s each).

## Measurements (cloud test box, x86, 2 cores)

- 8-ominoes, maxlevel 7: median 0.05 s per shape. The one inconclusive shape hit the 2.5 GB cap after 26 s.
- 400 random free 11-hexes, maxlevel 7: 158 Hc=0, 140 Hc=1, 2 Hc=2, 96 isohedral, 4 capped (1%). Median 0.05 s; mean 0.26 s for uncapped shapes. Capped shapes take 25–35 s to reach 2.5 GB; one needed more than 6 GB within 57 s.
- The capped shapes come out "inconclusive" (they pass every level) even at maxlevel 4, after 12–31 s and 1–2.6 GB. They are almost certainly non-isohedral tilers. See SPEC §4 "Anisohedral filter".
- There are 141,229 free hole-free 11-hexes. Estimated M1 pass 1 on the M4 Max (16 jobs): about 1 hour.

## Running now

- **M1 pass 1 finished** (owner's Mac, 15:02–15:46, 44 min wall, 11.2 core-hours, 16 jobs, maxlevel 5, old single-stage runner, peak RSS per check 3.1 GB). All 141,229 free hole-free 11-hexes: **67,644 Hc=0, 47,940 Hc=1, 816 Hc=2, 29 Hc=3**, 24,289 isohedral, 511 unsettled (183 inconclusive, 319 memout, 9 timeout). No Hc=4 among settled shapes. Kaplan reports exactly one Heesch-4 11-hex, presumably among the 511 unsettled. Results: `results/hex11.jsonl`.
- **M1 pass 2:** waiting for the owner to start it (command below).
- **Scorer step 1: done, positive.** Deep residual MLP built only from ANER ops, all 29 Hc=3 shapes hidden from training. 8 blocks (18 linear layers, width 512), 12 epochs on 2 CPU cores: among held-out non-tilers, Hc>=3 vs rest AUC **0.94**. Using score = hc_hat × (1 − p_tile) over all held-out shapes, the **top 1% captures 12/29 Hc=3 shapes (41× random)** and the top 5% captures 17/29; median Hc=3 percentile is about 4%. Tiler-vs-non-tiler AUC is 0.76, still the weak head. Weights: `results/models/scorer_hex11_b8.npz` (git-ignored, 17 MB). Caveat: trained only on 11-cell hexes in a 16×16 window; larger shapes are out of distribution until retrained on search logs.
- **ANER benchmark: waiting for the owner** (command in Next steps). It compares the Neural Engine with NumPy (Accelerate) on the trained scorer: throughput and agreement.
- **Track B prototype** (agent, cloud): `halo/gen_marked.py` scales base polyominoes 3× and puts a 1-cell bump or nick (or nothing) on each base edge. 1–2-cell bases: 163 shapes, best Hc=2. 3-cell bases: 2,897 shapes → 2,389 Hc=0, 127 Hc=1, 1 Hc=2, 355 isohedral, 25 unsettled (being re-checked with the C++ detector). Random markings mostly give Hc=0, because single-cell nicks are rarely fillable. Markings need searching (Track C on markings), not random enumeration.
- **Track C search loop built:** `halo/search.py`. Mutation-based local search (add/remove/move cells; connected, hole-free, within limits; dedupe by canonical form), the full runner ladder per shape, an elite archive, resumable JSONL log. Smoke test from the 29 Hc=3 11-hexes (200 checks, 2 cores): offspring mostly Hc 0–1 and no new Hc>=3. Real runs need the Mac's cores and the scorer as a prefilter (next).
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
3. **Owner: first ANER benchmark** (needs numpy in the Python you run it with; no torch needed):
   ```sh
   cd /Volumes/Code/HALO
   PYTHONPATH=/Volumes/Code/ANER/python python3 halo/aner_scorer.py results/models/scorer_hex11_b8.npz results/hex11.jsonl
   ```
   Reports: Neural Engine used yes/no, compile time, shapes/s for ANER vs NumPy, max disagreement.
4. **Agent:** summarize M1 pass 2 (the Heesch-4 shape → `shapes/reference/`). Add the scorer prefilter to `search.py` (generate many mutants, score them, check only the best), then retrain the scorer on search logs with a bigger window (22×22 = 484 channels) for larger shapes.
5. **Agent:** Track B as a search over markings (bump/nick per edge) instead of random enumeration, on 4–6-cell bases.
6. **Owner, optional:** PDFs of Mann 2004 (*Amer. Math. Monthly* 111(6)) and Bašić 2021 (*Math. Intelligencer* 43(3)) into `refs/` for Track A2.
7. **Agent:** finish literature check A3 for 2024–2026 (as of Kaplan 2023, no polyform with H >= 5 is known). Then start Track B with the cheap route: scale small marked polyforms (bumps/nicks as sub-cells) and run heesch-sat on them.

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
