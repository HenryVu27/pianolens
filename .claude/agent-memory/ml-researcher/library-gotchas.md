# Library gotchas

- factor-analyzer 0.5.1 + scikit-learn 1.9 (installed 2026-09-27): `FactorAnalyzer.fit`
  crashes with `check_array() got an unexpected keyword argument 'force_all_finite'`. Workaround
  without touching pyproject: wrap `factor_analyzer.factor_analyzer.check_array` to translate
  `force_all_finite` -> `ensure_all_finite` (see R-01 run.py top). `calculate_kmo` and
  `calculate_bartlett_sphericity` are unaffected. If factor analysis moves into src/, put the
  shim there once, or pin/replace the library (lead decision).
- `FactorAnalyzer.transform` returns factors in the fitted (unsorted) order; `phi_` exists only
  for oblique rotations.
- factor-analyzer 0.5.1 oblique traps (phi_ not re-sorted; get_communalities() wrong under
  oblimin) are now a rule in `.claude/rules/experiments.md`. R-01 run.py has `aligned_phi` and
  `communalities` helpers; reuse them.

## MuQ / audio stack (R-03, 2026-09-27)

- `muq` 0.1.0 declares no version pins. With transformers 5.x it crashes
  (`'EasyDict' object has no attribute '_attn_implementation'` in wav2vec2_conformer). Pinned
  `transformers>=4.45,<5` in the `torch` extra (resolves 4.57.6). That also moved the project's
  huggingface-hub from 2.0.0 to 0.36.2.
- MuQ caches rotary tables on the device of the first forward call. Load it straight onto MPS
  (`MuQ.from_pretrained(...).to("mps")` before any call); a model that ran on CPU first and then
  moved fails with a "mps:0 and cpu" device error.
- MuQ on MPS fp32 matches CPU (cos-sim > 0.99999 per frame). 25 frames/s; 13 hidden states
  (index 0 = conv/embedding output, 12 = last_hidden_state). About 0.1 s per 18 s clip,
  1.4 s for a 123 s clip on the M4 Pro.
- FluidSynth 2.6.1 `-F` fast render keeps going 2-3 s past the last MIDI event (release tail),
  and its defaults in 2.6.1 are reverb room 0.5 / level 0.7 / engine "dat", chorus level 0.6.
  `pianolens.audio.render` pins them.

## Parallel numpy on this Mac (R-02, 2026-09-27)

- ProcessPoolExecutor workers doing numpy/scipy linear algebra each spin up multithreaded BLAS
  (seen at ~120% CPU per worker) and oversubscribe the 14 cores, which other agents share.
  Launch with `OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OPENBLAS_NUM_THREADS=1`.
- `pkill -f "<script> --workers"` also kills your own `until pgrep ...` wait loops (their command
  line contains the pattern). Kill by PID or use a narrower pattern.
