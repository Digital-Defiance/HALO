# Controlled pipeline and precision measurements

Hardware: the owner's M4 Max, with the production HALO search stopped.
Environment: HALO-local Python 3.12.11; exact packages, source/model/library
hashes, and the fixed-input hash are in `environment.json` and `requirements.txt`.

`final-matrix-summary.json` compares the previous Python code with the updated
pipeline on the same 512 checker inputs, 14 workers, model, and checking bounds.
Individual replay files include timings, stage costs, inputs, and classifications.
There are two runs per configuration in balanced order. All eight runs produced
the same classifications. Median old-code time was 6.481 s versus 4.543 s for
the updated MLX FP32 profile: approximately 43% higher replay throughput.

This replay includes geometry validation/canonicalization, feature construction,
real inference and asynchronous/synchronous dispatch, and real SAT/periodic
checks. It excludes archive startup, retries, and defect solves. SAT quick/long
limits were 0.5/1 s, RSS cap 1,500 MB, and periodic budgets 0.05/0.1 s. It is not
a production high-Hc yield estimate. Checker picks are frozen to the FP32
reference so inference rounding cannot change the timed workload.

- `fixture.json.gz`: the exact fixed proposal attempts, ordinary checker inputs,
  FP32-selected scored inputs, and old-code Git revision.
- `accelerators.json`: median of five warm calls per backend/batch size,
  including NumPy/MLX/runtime boundary conversion and output readback.
- `precision.json`: per-head and averaged-Hc errors and top-32 agreement against
  the FP32 reference. These are measurements on one batch, not error guarantees
  for arbitrary future inputs.
- `gpu-fp32-prototype-opt0.json` and `gpu-fp32-prototype.json`: the temporary
  FP32 GPU build at optimization levels 0 and 1, respectively.
- `aner-gpu-fp32-prototype.patch`: the isolated GPU-only experiment. A production
  precision API, fallback guarantees, split semantics, and broad tests have not
  been implemented. Do not treat this patch as a complete ANER FP32 release.
- `before-batched-features-summary.json`: the previous replay, before batching
  occupancy construction.
- `smoke-batched-mlx-fp32.jsonl*`: the actual launcher's 250-evaluation native
  smoke test with the new batch encoder. No error statuses; all shapes unique
  and geometry-valid. Its tight caps and small starting archive differ from
  production, so its rate is not a predicted production rate.

The benchmark driver is `scripts/benchmark_pipeline.py`. `prepare` creates an
isolated working directory and extracts baseline modules from local Git;
`freeze` fixes checker picks using the FP32 reference; `final-matrix` performs
the paired replays. `accelerators`, `precision`, and `gpu-precision` measure
backends. The last phase needs `ANER_LIBRARY` to identify an isolated GPU-only
FP32 prototype, not the normal production library. Prepared inputs can be
replaced with the decompressed published fixture for the same corpus; use the
baseline revision recorded in that fixture.

No files in HALO's production results archive were edited or overwritten.
