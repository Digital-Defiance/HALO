# Agent orientation

Before doing anything, read in this order: `STATUS.md` (current state and next steps), `SPEC.md` (plan and acceptance rules), `README.md` (layout and build).

Rules:
- Never delete or overwrite anything in `results/`. Append only.
- At the end of every work session, update `STATUS.md`: done, running, next, blocked. Add any decision to the SPEC.md decision log.
- Always run the checker with `-isohedral`. Without it, tilers grind to the max level and look like slow non-tilers.
- A claimed record must pass `scripts/check_shape.sh` (maxlevel 12, hc >= 7, not inconclusive) and the constraint checks in SPEC.md §1 before anyone announces it.
- The agent shell on the owner's Mac is a Linux VM without Metal or the Neural Engine. Hand the owner a single command for native runs.
