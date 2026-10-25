# HALO specification and plan

Version 1, 2026-10-25. Owner: Jessica Mulein. This document is the source of truth for what HALO is trying to do and how. `STATUS.md` tracks where things stand.

## 1. Objective and acceptance criteria

Produce one tile record that the Epoch AI verifier for "A shape with Heesch number 7" would accept. These rules are mirrored from Epoch's problem statement (retrieved 2026-10-25):

1. One connected, hole-free, unmarked polyform on a grid supported by `heesch-sat`. Use `O` (square), `H` (hex) or `I` (triangle). Other `heesch-sat` grids may be supported by the verifier but are unconfirmed.
2. At most 200 cells.
3. Bounding-box spans satisfy `span_x + span_y <= 29`. The verifier normalizes translation. **Ambiguity:** "span" may mean `max - min` or `max - min + 1`. Design to the stricter reading (`(max_x-min_x+1) + (max_y-min_y+1) <= 29`) unless confirmed otherwise. This limit exists because elongated shapes trigger a known fixed-bitmap SAT failure in the checker.
4. The shape must not admit an isohedral tiling.
5. The verifier recomputes the classification with a maximum search level of 12. The hole-free Heesch number `hc` must come out at least 7. A shape that reaches level 12 is "inconclusive" and is rejected even with a valid witness.
6. Submission is the record exactly as `sat -isohedral -show -maxlevel 12` prints it:

```text
GRID x1 y1 ... xn yn
~ hc hh P
N
level <a,b,c,d,e,f>      (N placement lines; affine map x' = a x + b y + c, y' = d x + e y + f)
```

`hh` is the Heesch number when the outer corona may have holes (`hh = hc` or `hc + 1`). `P = 2` adds a second patch certifying `hh = hc + 1`. Only `hc` matters for acceptance.

**Self-check before any claim:** `scripts/check_shape.sh FILE` must report `hc >= 7`, not inconclusive. A constraint checker (cells, spans, connectivity, holes) is to be added to `halo/` (see M2).

**Publication:** no entry needed. Publish the shape, the witness, the exact checker commit and the commands to reproduce. Emailing math@epoch.ai to have it marked solved is optional. Also consider notifying Craig Kaplan.

## 2. Background and prior art

Record Heesch numbers for a single connected tile:

| Year | Who | H | Notes |
| --- | --- | --- | --- |
| 1968 | Heesch | 1 | polygon |
| 1991 | Fontaine | 2 | infinitely many polyominoes |
| 1990s | Ammann | 3 (4 by some definitions) | modified hexagon |
| 2001–2004 | Casey Mann | 4, then 5 | family of tiles; Mann, "Heesch's tiling problem", *Amer. Math. Monthly* 111(6) (2004) 509–517 |
| 2021 | Bojan Bašić | 6 | Bašić, "A Figure with Heesch Number 6: Pushing a Two-Decade-Old Boundary", *Math. Intelligencer* 43(3) (2021) 50–53 |

Key facts that shape the strategy:

- **Exhaustive enumeration tops out low.** Kaplan's 2022 computation ("Heesch numbers of unmarked polyforms", *Contributions to Discrete Mathematics*) found max H = 3 among polyominoes up to 19 cells, max H = 4 among polyhexes (six shapes, 11–17 cells) and max H = 4 among polyiamonds (one 20-cell shape; enumeration to 24 cells). Small random shapes won't reach 7. The answer has to be designed.
- **Marked tiles go higher.** With coloured or marked edges, Heesch number 11 is known (DeWeese and Coronaldi, 2010, unpublished, cited by Bašić et al. 2023).
- **Forced chains give any m for two tiles.** Bašić, Džuklevski and Slivková, "Solutions to Seven and a Half Problems on Tilings", *Electron. J. Combin.* 30(2) (2023) P2.50, prove every m is reached by a two-tile protoset, and by a single tile in two disconnected parts. The mechanism: bumps and nicks force each neighbour's placement, and each corona closes a gap by a fixed amount until no further corona fits. The open step is merging this into **one connected tile**. The authors suggest cutting a multi-tile construction into pieces could do it, but don't carry it out.
- **The record shapes are not polyforms.** Kaplan's 2023 Canadam talk ("Heesch Numbers of Unmarked Polyforms") notes that Mann's H = 5 and Bašić's H = 6 shapes are not polyforms. So **a polyform with H >= 5 would itself be a new result** (milestone M4), as of 2023; re-check before claiming.
- **Marked polyforms reach 5.** Mann and Thomas (AMS abstract 1024-52-43, 2006, "Heesch numbers of polyforms with marked edges") report polyforms whose edges carry bumps and nicks, with Heesch numbers 0 through 5, computed by program. An n-edge polyform has 3^n markings (flat, bump, nick per edge). This is the Track B1 starting point.
- **Realization by scaling.** To turn a marked polyform into an unmarked one, subdivide each cell and draw bumps and nicks as added or removed sub-cells. Squares subdivide into s×s squares (polyomino stays a polyomino). Triangles subdivide into s² triangles. Hexagons don't subdivide into hexagons, but each hexagon is 6 triangles, so a marked polyhex is realized as a polyiamond. Budget: a base of m cells at scale s uses about m·s² cells (≤ 200), and spans scale by s (sum ≤ 29). For example, an 8-cell polyomino at s = 5, or a 4-hex base as 24 triangles at s = 2 (96 triangles) plus bumps.
- **Kaplan's stated future work** includes "eliminate tiling shapes efficiently", which is what `halo/periodic.py` does.
- **Precedent:** the 2023 aperiodic "hat" monotile was found by an amateur, David Smith, exploring shapes with Kaplan's software (Smith, Myers, Kaplan, Goodman-Strauss, arXiv:2303.10798).

## 3. Strategy

Tracks in priority order. B is the main bet. C runs from day one because it is cheap and parallel. D accelerates C once there is data.

### Track A: baseline and understanding

- A1. Reproduce Kaplan's H = 4 polyhexes and polyiamond with our build. Record solve times per level.
- A2. Obtain Mann's H = 5 and Bašić's H = 6 constructions. The papers are paywalled, so the owner may need to supply PDFs. Try to rasterize each as a polyform within the §1 limits and certify it. If rasterizing lowers the Heesch number, document which new neighbour placements caused it. That failure mode is exactly what Track B must avoid.
- A3. Literature check: is any **polyform** with H >= 5 already known? As of Kaplan's 2023 talk, no: the H=5 and H=6 records are not polyforms. Re-verify (2024–2026 literature) before claiming.

### Track B: forced-chain construction (primary)

- B1. **Marked-tile solver.** Write a SAT-based Heesch solver for a base polyform whose boundary edges are flat, bump or nick (Mann–Thomas style; bump must meet nick, flat meets flat), later general labels with matching rules. heesch-sat has no markings. Reuse its corona encoding ideas. First target: reproduce Mann–Thomas Heesch numbers up to 5. Cheaper alternative to try first: realize markings by scaling (§2) and run heesch-sat directly on the result, which needs no new solver.
- B2. **Design rule systems** with marked H >= 8 or 9. Aim above 7 for margin, because geometric realization tends to lose a level. Use LLM-assisted design plus local search over rule systems. Hexagon-like base shapes with 6 neighbours are a natural start. Follow Mann's and Bašić's patterns and the forced-chain mechanism of Bašić et al. 2023.
- B3. **Geometric realization.** Turn each label pair into complementary bump/notch cell patterns on a finer grid, scale s, so that only intended neighbours fit. This is the hard part. The 200-cell and span <= 29 budget is tight, so choose base size and scale together.
- B4. Certify with heesch-sat. Feed failures back to B2/B3. Hand near-misses to Track C for repair.

### Track C: guided local search over polyforms (runs continuously)

- Mutations: add or remove a boundary cell, keeping the shape connected, hole-free and within limits. Also small rigid edits: bump, notch, swap.
- Score: `hc` first. Tie-breakers to define and test: hh, solver time at the deciding level, number of distinct first-corona surrounds, fraction of SAT calls near the threshold.
- Search: simulated annealing plus a MAP-Elites archive keyed by (cells, span, hc).
- Seeds: Kaplan's H = 3 and H = 4 shapes, Track B realizations, Track A rasterizations.
- Staged checking: quick pass at maxlevel 5–7, then deep pass at maxlevel 12 only for shapes reaching the current best.

### Track D: learned scorer on GPU and Neural Engine (accelerator)

- Input: occupancy grid, canonicalized into a window of at most 512 cells (for example 22 × 22 = 484), so it fits ANER's 512-channel limit.
- Target: hc plus solver statistics from the Track C/B logs.
- Model: an MLP using only ANER's existing ops (conv, gelu, sigmoid). Train on the GPU (MLX). Compile frozen weights to the Neural Engine via ANER. ANER's router falls back to Metal when shapes don't fit.
- Use: prefilter thousands of mutations per accepted step at high throughput. The CPU checker verifies only the top slice.
- Optional: relax the occupancy grid to continuous values, gradient-ascend the scorer, snap to cells, verify. This is the "Gaussian-splat-like" idea: a candidate generator only, never a solver. Low priority.
- Caveat: a scorer trained on H <= 4 data may not extrapolate to H = 7. Measure before relying on it.

### Track E: LLM-evolved generators (optional)

AlphaEvolve-style. Programs that emit shapes or rule systems, scored by the harness. Open-source precedents: OpenEvolve, ThetaEvolve.

## 4. Architecture

- **Checker:** heesch-sat `sat`, single-threaded per process. The harness runs one process per core with a work queue. Always pass `-isohedral`. Pass `-maxlevel` explicitly (default is 7).
- **Data:** one JSONL file per run in `results/`, one line per checked shape: `{canon, grid, cells, span_x, span_y, hc, hh, status, seconds, maxlevel, generator, parent, run_id, ts}`. `canon` is the canonical free form (min over grid symmetries and translations) and is used for dedupe.
- **Cost profile (measured 2026-10-25, 400 random free 11-hexes, maxlevel 7):** median check 0.05 s, but about 1% of shapes are tilers that heesch-sat cannot classify (not isohedral, presumably anisohedral). Each of those costs 10–60 s and 1–6+ GB even at maxlevel 4–5, which is about half of all compute. Runs therefore use two passes: a fast pass with tight per-shape caps, then a re-run of capped shapes with big caps and few jobs (`runner.py --only-status timeout,memout`).
- **Periodic tiling detector (`halo/periodic.py`, built 2026-10-25):** a shape tiles periodically iff copies of it exactly cover some torus Z²/L. The detector tries sublattices L of index t·area (t = 1..24), up to grid symmetry, solving exact cover with Algorithm X. Every solution is verified, so a "tiles" result is a proof. A C++ Dancing Links port (`halo/periodic_dlx.cpp`) is 50–140× faster and is used by the runner when built. On the 11-hex sample it settled all 4 shapes heesch-sat couldn't (three in about 1 s, one needing 8 tiles per period in 23 s). On 8-ominoes: 0/20 false positives, 60/60 isohedral tilers found. Square and hex grids only.
- **Runner ladder:** quick heesch-sat (`--timeout`, e.g. 5 s) → quick periodic probe (`--periodic-quick`, 5 s) → long heesch-sat (`--timeout-long`) → long periodic probe (`--periodic-budget`). On the 400-hex sample, every shape was settled at the same wall time as the old single-stage runner, which left 1% unsettled.
- **Checkpointing:** append each result immediately. Runs must be resumable from their JSONL file.
- **Compute placement:** CPU = SAT checks. GPU = scorer training and relaxations. Neural Engine = scorer inference through ANER.
- **Native runs:** started by the owner on macOS with a single command. The agent's Linux VM is for development and small tests only.

## 5. Milestones

| ID | Milestone | Done when |
| --- | --- | --- |
| M0 | Tooling | heesch-sat builds and matches known counts on Linux ✅ and macOS |
| M1 | Baseline | Kaplan's H=4 shapes reproduced; per-level timing table in STATUS.md; Mann/Bašić status documented |
| M2 | Harness | parallel runner + constraint checker + JSONL + resume; Track C running natively overnight |
| M3 | Marked solver | solver agrees with heesch-sat on unmarked inputs; a rule system with marked H >= 7 found |
| M4 | H >= 5 polyform | first from our pipeline. Likely a new result in itself (record H=5/6 shapes aren't polyforms; Kaplan 2023) |
| M5 | H = 6 polyform | ties the record within verifier limits |
| M6 | H >= 7 | passes all §1 checks independently on two machines; write-up and public repo |

## 6. Risks

- High Heesch numbers are extremely rare. M6 is a long shot. M4/M5 are worthwhile even if M6 isn't reached.
- SAT cost grows steeply with level and shape size. Measure early (M1) and budget.
- Geometric realization creates unintended neighbour fits that collapse the Heesch number.
- Anisohedral or aperiodic tilers come out "inconclusive". They are not records. They are also the most expensive shapes to check (§4).
- The span ambiguity in §1. Design to the stricter reading.
- heesch-sat is experimental code. Cross-check any record with an independent check, e.g. re-verify the witness patch geometry with our own script.

## 7. Decision log

- 2026-10-25: Chose the Heesch record (Epoch open problem) over fast-matrix-multiplication catalog records. The bigger payoff justifies the long odds.
- 2026-10-25: Named HALO.
- 2026-10-25: heesch-sat pinned at commit `d12a527` (2026-08-30). Build needs C++20 and linking `isohedral.o` into `sat`; the upstream Makefile is out of date.
- 2026-10-25: The agent shell on the Mac is a Linux VM. Native Metal/Neural Engine runs are launched by the owner.
- 2026-10-25: Gaussian-splat-style continuous relaxations are allowed only as an optional generator in Track D.
- 2026-10-25: Periodic tiling detector via torus exact cover instead of a k-isohedral classifier: simpler, gives proofs, catches any periodic tiling with at most 24 tiles per period.
- 2026-10-25: Two-pass checking with per-shape time/memory caps. One runaway shape OOM-killed a whole batch on the 7 GB test box; the runner now isolates every shape in its own process.

## 8. References

- Epoch AI, "A shape with Heesch number 7": https://epoch.ai/frontiermath/open-problems/heesch-number
- Epoch AI, FrontierMath Open Problems FAQ: https://epoch.ai/frontiermath/open-problems/about/faq
- C. S. Kaplan, heesch-sat: https://github.com/isohedral/heesch-sat
- C. S. Kaplan, "Heesch numbers of unmarked polyforms": https://isohedral.ca/?p=2377 and https://cdm.ucalgary.ca/article/view/72886
- B. Bašić, A. Džuklevski, A. Slivková, "Solutions to Seven and a Half Problems on Tilings", EJC 30(2) 2023: https://www.combinatorics.org/ojs/index.php/eljc/article/download/v30i2p50/pdf
- B. Bašić, "A Figure with Heesch Number 6", Math. Intelligencer 43(3) 2021
- C. Mann, "Heesch's tiling problem", Amer. Math. Monthly 111(6) 2004
- Smith, Myers, Kaplan, Goodman-Strauss, "An aperiodic monotile": https://arxiv.org/abs/2303.10798
- Heesch's problem (overview): https://en.wikipedia.org/wiki/Heesch%27s_problem
- C. S. Kaplan, Canadam 2023 talk slides: https://cs.uwaterloo.ca/~cbright/talks/cam/heesch.pdf
- C. Mann, B. Thomas, "Heesch numbers of polyforms with marked edges" (AMS abstract, 2006): https://community.ams.org/amsmtgs/2134_abstracts/1024-52-43.pdf
