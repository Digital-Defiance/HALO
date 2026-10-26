# Pipeline review, 2026-10-26

HALO's acceptance target remains a connected, hole-free, unmarked polyform with
finite Hc >= 7, at most 200 cells, and span sum <= 29. I rechecked the
[Epoch prompt](https://epoch.ai/frontiermath/open-problems/heesch-number):
classification at maxlevel 12 must settle, and an isohedral tiler is rejected.
The existing independent witness check still passes for the 21-cell Hc=4 find.
The search currently explores hexes of 18–30 cells; that is a useful experiment,
not coverage of the whole allowed search space or a demonstrated route to Hc=7.

## Active run and observed yield

The previous native search was PID 97377, launched around 12:48 PDT with scorer v4, 14
ordinary workers, 2 retry workers, 50% sweep, and the remaining proposals split
between scored and random. The owner stopped it with Ctrl+C at 176,000
evaluations (archive 651,859) to allow controlled benchmarking. No production
search is currently running. This review did not edit the production result log
or rebuild the production checker or ANER library.

## Controlled follow-up and precision decision

After the owner stopped the run, paired replays used 512 fixed checker inputs,
14 workers, the same model and bounds, and Python 3.12.11. Checker picks were
frozen to the FP32 reference so backend rounding could not change the workload.
Each configuration ran twice in balanced order. All eight runs had identical
classification outcomes: 418 non-tilers, 85 isohedral tilers, and 9 timeouts.

| Configuration | Median seconds | Checks/second |
| --- | ---: | ---: |
| Previous Python code, ANE width 64 | 6.481 | 79.0 |
| Updated pipeline, ANE width 64 | 4.500 | 113.8 |
| Updated pipeline, ANE width 256 | 4.566 | 112.1 |
| Updated pipeline, MLX FP32 | 4.543 | 112.7 |

The updated pipeline completed about 43% more checks per second than the old
code on this replay. Backend differences in whole-replay time were small and
within the variation of these short runs. This is not a predicted production
discovery rate: startup/archive loading, high-memory retries, and defect scoring
were excluded, and quick/long SAT limits were 0.5/1 seconds with a 1.5 GB cap.

The final update also batches symmetry/occupancy encoding rather than creating
one NumPy array per image. Its occupancy vectors match the original exactly in
mixed-grid/window tests. Feature-construction time in the updated MLX replay
fell from about 0.39 to 0.24 seconds across four refills; whole-replay improvement
from this last change alone was modest.

Isolated v4 inference on 2,048 candidates (24,576 symmetric images), measured as
median wall time including wrapper conversions and readback:

| Backend and precision | Full-refill milliseconds |
| --- | ---: |
| ANER ANE FP16, width 64 | 85.9 |
| ANER ANE FP16, width 256 | 46.3 |
| ANER GPU FP16 | 35.1 |
| ANER split FP16 | 32.8 |
| ANER GPU FP32 prototype, optimization level 0 | 37.7 |
| ANER GPU FP32 prototype, optimization level 1 | 37.9 |
| MLX GPU FP16 | 20.1 |
| MLX GPU FP32 | 26.3 |

The FP32 ANER prototype is a separate build under the temporary benchmark
directory. It uses FP32 tensors and constants on the GPU; it is not a new public
ANER precision API. Its maximum averaged Hc error against the NumPy FP32
reference was about 3.6e-7. The production ANER source and library were not
changed; `make -q build/libaner.dylib` confirmed the library was up to date.

On one 2,048-candidate batch, the ANE selected 31 of the reference's top 32 and
had maximum averaged Hc error 0.0313. GPU FP16 selected all 32 with maximum
averaged error 0.000458. MLX FP32 matched the reference to a few parts per
million in the measured outputs. This is a numerical comparison on one batch,
not evidence about which backend discovers more high-Hc shapes. Approximate
ranking can omit candidates; the independent SAT check remains exact.

The launch profile now uses **MLX FP32** while the GPU is available. It preserves
near-reference ranking at no measurable whole-replay cost versus ANE. ANE width
256 remains available when the GPU is needed for training. The broader ANER
roadmap is `/Volumes/Code/ANER/ROADMAP.md`: explicit precision, accurate fallback
reports, measured automatic placement, buffer reuse and workload-driven ops.

Raw timings, compressed fixed inputs, prototype patch, environment hashes and
dependency versions are saved in `benchmarks/2026-10-26/`. The new HALO-local
`.venv` contains Python 3.12, NumPy, psutil and MLX. Both the environment and pip
cache are scoped inside HALO. No broad filesystem discovery is needed.

Snapshot of rows since 12:48 at approximately 13:27 PDT, restricted to 18+ cells:

| Generator | Checked | Hc >= 2 | Hc >= 3 | Worker seconds/check | Hc >= 3 / worker-hour |
| --- | ---: | ---: | ---: | ---: | ---: |
| Random | 25,816 | 0.09% | 9 | 0.13 | 10.0 |
| Scored v4 | 26,045 | 0.42% | 5 | 0.36 | 1.9 |
| Sweep | 52,081 | 0.62% | 188 | 0.22 | 59.8 |

Historical cost is a lower bound: the old `seconds` field measured the final SAT
attempt, omitting earlier ladder stages. These figures add logged retry and
defect time. They are elapsed worker time, not OS CPU measurements. This is an
observational comparison with different proposal distributions and shape sizes,
not a randomized proof that one allocation is optimal. Hc>=2 is a useful scorer
diagnostic, but Hc>=3/4 discoveries per unit of compute are closer to the goal.

Sweep is the strongest current frontier producer. The next-run profile in
`scripts/search_frontier.sh` requests 75% sweep and splits the remainder evenly
between scored and random proposals. Keeping both other arms preserves
diversity and a live control. Actual fractions vary when a queue is empty;
random proposals fill gaps while scoring runs. Keep the existing high-memory
retry lane: expensive shapes have already included Hc=4 finds.

## Implemented changes

- Replace the runner's fixed 50 ms sleeps with timed process waits, retaining
  RSS/timeout checks. Quick solves can be collected immediately.
- Use `posix_spawn` where Python supports it by allowing non-inheritable file
  descriptors to retain their default close-on-exec behavior. This also avoids
  an OpenBLAS/fork deadlock found in the native NumPy fallback integration test.
- Replace per-cell exterior flooding with an integer bitboard flood, with row
  boundary masks for both square and hex adjacency. Check parsed cells directly
  in the generator and cache parsed parents.
- Prepare scored batches on one background thread using parent snapshots and a
  separate RNG. Only the dispatcher publishes pending candidates and commits
  completed results. Inference calls are serialized if relaxation is also used.
  Scoring does not block new checker dispatch.
- Maintain the Hc histogram incrementally instead of traversing the growing
  archive every 100 results.
- Skip exhausted sweep parents immediately, restrict the generator guard to
  scored/relaxation arms, and release queued pending entries when disabling an
  arm. The sweep can no longer be reported as disabled while still scheduled.
- Enforce `--max-evals` for submitted evaluations, preserve retry cost, and allow
  inconclusive escalation even with periodic probes disabled.
- Before resuming, append a newline when necessary so a partial JSONL tail
  cannot consume the next result. Existing bytes remain unchanged.
- Add per-run IDs and append-only `LOG.runs.jsonl` manifests containing options,
  Python/platform information, and hashes of key source files and model weights.
  `gen_report.py --run-id ID` selects a run; its cost includes total ladder,
  retry, and defect time, and it reports Hc>=3 yield per worker-hour.

## Validation and measured limits

- `python3 -m unittest discover -s tests -v`: 11 tests passed, covering geometry equivalence, process exit,
  time/memory limits, periodic short-circuiting, escalation, cost accounting,
  partial-tail preservation, exact evaluation limits, resume, retries, and slow
  background scoring. The small-shape test exhausts 8,190 square/hex patterns;
  another 1,000 random shapes exercise larger spans.
- A separate 8,000-shape geometry comparison matched the independent exterior
  flood every time: 2.647 s reference versus 0.125 s bitboard, about 21x faster.
- Native checker benchmark on the same 60 logged 18+ cell Hc=0 shapes: 3.474 s
  before versus 1.334 s after the timed-wait change, with all status/Hc/Hh values
  identical. Median recorded time fell from 56.45 to 20.30 ms. This is a quick
  shape benchmark, not an overall search throughput claim.
- Native ANER v4 scoring on a background thread returned 24,576 finite outputs
  using the Neural Engine in 93.3 ms. The sandbox cannot compile an ANE graph;
  native validation succeeded. ANER needs no source changes for this pipeline.
- An isolated 100-evaluation native search with the real SAT checker and NumPy
  scorer completed in 12.6 seconds after the `posix_spawn` fix. All three
  generators ran; outputs went only to `/tmp`. Tight one-second/1 GB test caps
  deliberately limited expensive checks; this was an integration test, not a
  production-yield comparison.
- `python3 halo/verify.py shapes/hex21_h4.witness`: PASS, Hc >= 4, 61 copies.

The initial microbenchmarks above ran alongside the old search; the controlled
follow-up ran after it was stopped. A full run is required to measure frontier discoveries per
wall-hour after these changes; synthetic/mock-checker dispatch rates are not
evidence of faster mathematical progress.

## Next decisions

1. Start `./scripts/search_frontier.sh` in the
   native terminal. Do not run two searches against the same log. Extra
   arguments override defaults, for example `--hours 2` or a newer scorer path.
2. Evaluate Hc>=3, Hc>=4 and new bests per wall-hour, alongside total worker cost.
   The next manifest makes exact run boundaries available. Avoid tuning purely
   for Hc>=2 per check or raw ANER throughput.
3. Use MLX FP32 while the GPU is free; choose ANE width 256 when GPU contention
   justifies it. More raw inference throughput did not materially improve the
   whole replay. Continue measuring candidate geometry, packing and dispatch.
4. Keep relaxation off. Its prior bake-off showed high generation cost without
   a yield gain. Defect scoring remains a useful, expensive experiment inline
   with classification. Track its cost and predictive value; a separate bounded
   enrichment lane is a future option if it begins occupying most workers.
5. Restore attention to Track B's forced-chain/marked constructions. The current
   generator realizes arbitrary small square-grid markings, but there is no
   marked-rule solver or forced-chain design loop in the live hex search. More
   Hc=3 plateau samples alone do not establish a path beyond Hc=4. Test designed
   constructions as a separate budgeted experiment, with the same verifier,
   independent certificates, and all <=200-cell/span constraints.

The changes improve measured costs and remove correctness problems. They do not
establish a globally optimal allocation or guarantee a new Heesch record.
