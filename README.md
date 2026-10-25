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

A coding agent working through the Claude desktop link gets a small Linux VM on this Mac (4 cores, 3 GB), not macOS. It cannot reach Metal or the Neural Engine. Long native runs are started by the user from macOS Terminal with commands the agent provides.

## Licenses

HALO code: MIT License, © 2026 Digital Defiance (see `LICENSE`). `heesch-sat` is BSD 3-Clause, © 2021 Craig S. Kaplan. It is cloned at build time, not vendored.
