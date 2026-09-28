# R-04 (symbolic S0 vs MuQ on PercePiano) audit facts, 2026-09-27

- Prereg check recipe that worked: pull the README `Write` content from the ml-researcher
  transcript jsonl, sha256 it, compare with `artifacts/prereg_sha256.txt`, then `diff` against
  `head -n <prereg line count> README.md`. R-04: identical (217 lines). Keep the header untouched
  in audits so this stays checkable.
- Reproducing run.py without overwriting artifacts: sed-copy it to scratch with `HERE` fixed to
  the experiment dir and `ART` pointed at scratch (copy features.parquet there). To import its
  functions into joblib workers, copy it as `r4.py` and put the dir on PYTHONPATH (importlib
  spec modules do not unpickle in loky workers; also register in sys.modules for dataclasses).
  Full run ~10 min on 14 workers; features.py ~2 min. Both bit-exact.
- `code_hash` in results.json goes stale whenever anyone edits src/ (other agents do, in
  parallel). Verify reproducibility by rerunning, not by the hash.
- Pooled over passages, S0 ≈ MuQ, but per work: S0 behind on WoO80, D935 (sig.), D960 mv2;
  ahead on D960 mv3 (47% of rows). Always ask for per-work paired Δ on PercePiano claims.
- Pedal (glob__pedal_depth_mean) dominance is real on human rows (raw WP rho 0.48 with pedal
  saturated, 0.42 rich, 0.38 articulation long). 71% of Score rows have no CC64, the rest do.
- Split-half half-vs-half agreement is not a ceiling for a model scored against the full mean;
  SB on half-panel WP rho 0.374 -> ~0.54 reliability -> ~0.74 attainable vs models ~0.35.
- In S1, `ref__n_references` is an is-Score flag (Score rows get one more reference).
