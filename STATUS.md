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

## Measurements (cloud test box, x86, 2 cores)

- 8-ominoes, maxlevel 7: median 0.05 s per shape. The one inconclusive shape hit the 2.5 GB cap after 26 s.
- 400 random free 11-hexes, maxlevel 7: 158 Hc=0, 140 Hc=1, 2 Hc=2, 96 isohedral, 4 capped (1%). Median 0.05 s; mean 0.26 s for uncapped shapes. Capped shapes take 25–35 s to reach 2.5 GB; one needed more than 6 GB within 57 s.
- The capped shapes come out "inconclusive" (they pass every level) even at maxlevel 4, after 12–31 s and 1–2.6 GB. They are almost certainly non-isohedral tilers. See SPEC §4 "Anisohedral filter".
- There are 141,229 free hole-free 11-hexes. Estimated M1 pass 1 on the M4 Max (16 jobs): about 1 hour.

## Running now

- M1 pass 1 (owner's Mac, started 15:02): 83,654 / 141,229 done by 15:30. Partial counts: 37,162 Hc=0, 28,932 Hc=1, 642 Hc=2, 23 Hc=3, 16,502 isohedral, 141 inconclusive, 246 memout, 8 timeout. No Hc=4 yet. The Heesch-4 shape may be among the memouts, since proving the 5th corona impossible is expensive.
- This run uses the old single-stage runner. Pass 2 (below) uses the new ladder.

## Next steps (in order)

1. **Owner, on macOS: M1 baseline, pass 1** (about 1 hour; uses all cores and up to roughly 30 GB RAM):
   ```sh
   cd /Volumes/Code/HALO
   build/Darwin/heesch-sat/src/gen -hex -size 11 -free -o results/hex11.txt
   python3 halo/runner.py results/hex11.txt --out results/hex11.jsonl --maxlevel 5 --timeout 60 --mem-mb 3000 --generator gen-hex11
   ```
   Goal: reproduce Kaplan's single Heesch-4 11-hex (it should appear in the final "hc=4" list). If the run is interrupted, rerun the same command and it resumes.
2. **Owner: pass 2** for unsettled shapes. It uses the ladder with the periodic detector: 6 jobs × up to 8 GB.
   ```sh
   python3 halo/runner.py results/hex11.jsonl --only-status timeout,memout,inconclusive --out results/hex11_pass2.jsonl --jobs 6 --maxlevel 5 --timeout 5 --timeout-long 900 --mem-mb 8000 --periodic-budget 120 --generator gen-hex11-pass2
   ```
   Expected: almost all become `periodic` (proven tilers). Whatever remains with hc=4 is Kaplan's shape. For future batches, use the ladder from the start, e.g. `--timeout 5 --timeout-long 60 --periodic-budget 60`.
3. **Agent:** summarize the M1 results here (counts, hc histogram, time, the H=4 shape copied to `shapes/reference/`).
4. **Agent (M2):** Track C local search seeded from Heesch-3/4 shapes. Speed up `periodic.py` (C++ port or SAT) if the detector becomes a bottleneck.
5. **Owner, optional:** PDFs of Mann 2004 (*Amer. Math. Monthly* 111(6)) and Bašić 2021 (*Math. Intelligencer* 43(3)) into `refs/` for Track A2.
6. **Agent:** literature check A3: is any polyform with H >= 5 known?

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
