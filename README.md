# HALO

**Heesch Annuli via Learned Optimization.** An open-source search for a tile with a record Heesch number.

## Goal

Find a single polyform tile whose **Heesch number is at least 7**. The world record is 6 (Bojan Bašić, 2021). The tile must be hole-free, have at most 200 cells, satisfy `span_x + span_y <= 29`, and must not tile the plane. The full acceptance rules are in `SPEC.md` §1.

A tile's Heesch number is how many complete rings ("coronas") of copies of itself can surround it before no further ring fits. Shapes that tile the plane have an infinite Heesch number. Heesch's problem (1968) asks whether finite Heesch numbers are bounded. Nobody knows.

Epoch AI lists this as an open problem ("A shape with Heesch number 7"), rated "Solid result". No entry is required: a result counts once it is published with a certificate anyone can check.

## Where things are

| Path | What |
| --- | --- |
| `SPEC.md` | The plan: acceptance criteria, prior art, strategy tracks, architecture, milestones, risks, decision log |
| `STATUS.md` | Living handoff log: what's done, running, next. **Read this first when resuming.** |
| `PIPELINE_REVIEW.md` | Pipeline measurements, fixes, current allocation, and remaining strategy gaps |
| `RESEARCH_PLAN.md` | Next research experiments: inverse patch repair, construction feasibility and targeted sweeps |
| `refs/README.md` | Obtained construction papers, public sources and local PDF checksum |
| `scripts/search_frontier.sh` | Next native frontier run; resume after the current run finishes |
| `CLAUDE.md` | Short orientation for coding agents |
| `scripts/setup_heesch_sat.sh` | Clones and builds Craig Kaplan's `heesch-sat` checker at a pinned commit |
| `third_party/heesch-sat/` | Our Makefiles for building `heesch-sat` on macOS and Linux |
| `shapes/reference/` | Certified reference shapes (heesch-sat text format) |
| `results/` | Search outputs (JSONL); never delete |
| `halo/` | Our code: harness, generators, scorer (in progress) |
| `build/<OS>/` | Generated; the cloned checker lives here (separate per OS, so Linux and macOS builds never mix) |

## Quick start

macOS (Apple Silicon, Homebrew):

```sh
brew install cryptominisat boost
./scripts/setup_heesch_sat.sh
./scripts/check_shape.sh shapes/reference/octomino_h1.txt
```

Ubuntu 24.04:

```sh
sudo apt-get install -y libcryptominisat5-dev libboost-dev
./scripts/setup_heesch_sat.sh
./scripts/check_shape.sh shapes/reference/octomino_h1.txt
```

`check_shape.sh` runs the checker exactly the way the Epoch verifier does: isohedral check on, up to 12 coronas. It prints the witness patch.

## Hardware

The main machine is an Apple M4 Max with 64 GB. Search runs use all CPU cores for SAT checks. The GPU and Neural Engine (through ANER, `/Volumes/Code/ANER`) are used for the learned scorer in Track D.

Execution environments vary by agent. The older Claude desktop link uses a small Linux VM; this Codex review used the native Mac shell, and verified the Neural Engine outside the sandbox. Check the actual host and backend rather than assuming accelerator access. Long search runs are started from macOS Terminal.

## Search environment and restart

The native runtime is now installed in `.venv` (Python 3.12). Activate it with
`source /Volumes/Code/HALO/.venv/bin/activate`, or run
`/Volumes/Code/HALO/scripts/search_frontier.sh`, which selects that interpreter
automatically. The launcher resumes the existing archive with scorer v4 using
MLX FP32, 75% sweep while work is available, 14 ordinary workers and one larger
retry worker. Ordinary SAT checks are capped at 3,000 MB and the retry at
20,000 MB. A cooperative guard monitors combined SAT/defect RSS against a
48,000 MB budget and aims to retain 8,000 MB of system-available RAM. It pauses
dispatch and stops selected checks as unresolved under pressure, preferring to
stop defect enrichment before classification. These are sampled controls with
possible overshoot, not an OS-enforced memory reservation. Periodic probes and
the Python/GPU process are outside the RSS sum but count toward system headroom.
The generator guard defaults to `--guard-mode warn`: it reports low recent yield
and keeps the scorer enabled. Rare-hit windows are too noisy for an automatic
permanent cutoff. `--guard-mode disable` explicitly restores the old shutoff;
`--guard-mode off` or `--guard-checks 0` disables monitoring. Warnings and opt-in
shutoffs are recorded in the run manifest.
The default eight hours is an open-ended search time budget, not a prediction of
how long a fixed job needs. Progress labels show when new checks stop; in-flight
checks may finish later. Sweep backlog time is a separate rough estimate.
Resource-capped retries remain unresolved (`hc: null` in JSON), not Hc=0.
To reserve the GPU for training, override with
`--scorer-schedule ane --scorer-spatial 256`.

The dependency lock, fixed benchmark inputs, raw results and environment hashes
are in `benchmarks/2026-10-26/`. See `PIPELINE_REVIEW.md` for the measured benefits
and the limits of the replay benchmark.

## Broader compute opportunities and priority

[ANER's roadmap](https://github.com/Digital-Defiance/ANER/blob/gpu-perf/ROADMAP.md)
records explicit FP32 support, accurate execution/fallback reports, measured
backend/tile selection, reusable buffers and asynchronous execution, and
workload-driven operation and portability improvements.

None of that broader work needs to precede the next HALO run. The immediate
pipeline changes are implemented and tested. Resume searching, compare frontier
discoveries per wall-hour, and prioritize better scorer training and designed
constructions over additional inference throughput. Existing ANE width-256
inference is available if GPU training competes with the MLX scorer. Unexpected
CPU fallback would justify bringing ANER diagnostics forward before relying on
that path for another long run.

Model weights and the large `results/search_hex_01.jsonl` archive use Git LFS.
Clones need Git LFS and `git lfs pull` to materialize them before searching.

## Licenses

HALO code: MIT License, © 2026 Digital Defiance (see `LICENSE`). `heesch-sat` is BSD 3-Clause, © 2021 Craig S. Kaplan. It is cloned at build time, not vendored.
