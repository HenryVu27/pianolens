# R-04 symbolic features on PercePiano: facts and traps (2026-09-27)

- Feature batch helper: `pianolens.features.extract` (`segment_features`, `reference_features`,
  `group_features`). One flat row per performance, prefixes corr__/tempo__/ctrl__/shape__/glob__/ref__.
  PercePiano extraction: 1,202 segments, 99 passages, ~83 s on 14 workers (one worker per
  passage; AlignedPerformance does not pickle, so workers return DataFrames).
  Cache: `experiments/2026-09-27-R-04-symbolic-percepiano/artifacts/features.parquet`.
- BUG FIXED (data/types.py): multi-track MIDI gave duplicate performance note ids (partitura
  numbers ids per track). All 124 PercePiano Score/Score2 renditions are 2-track; duplicates made
  tempo/voicing read the wrong notes (Score "deadpan" looked like it had 500 ms chord spreads) and
  crashed parangonar's ornament step on 2 D935 Score segments. `performance_from_partitura` now
  renumbers n0.. in onset order only when ids repeat. ASAP midi_score.mid and MAJEPPA score MIDIs
  also have dup ids but go through score loaders, not this function.
- shaping.voicing divides by beat_period_sec, which can be 0 on a degenerate tempo segment
  (ZeroDivisionError). Not fixed (F-05b owns shaping.py); extract.py catches it.
- Short segments: coherence with 4-bar blocks is impossible; used 1-bar blocks, no buffer, NaN
  below 8 written bars (all of D935), smooth-tempo channel dropped, clip at -1.
- 4 D960 mv3 passages (16b_18, 8b_10, 8b_19, 8b_36) align badly for every performer (match
  ratio < 0.8, Score included) -> segment score / MIDI mismatch, not player error.
- sklearn 1.9 HistGradientBoosting crashes on a column with < 2 distinct non-NaN values
  ("window shape cannot be larger"): drop such columns per fit.
- LightGBM is installed but libomp is missing on this Mac (dlopen error); no pygam. Use sklearn
  HGB and SplineTransformer + ridge as the GAM.
- F-04b landed mid-ticket: always record control.py hash in features_meta.json; the first full run used stale features and was redone.
- Fast cluster bootstrap: per-passage sufficient stats + weight matrix (`PassageStats` in R-04
  run.py), self-checked against R-03's row-level metrics, incl. one resample.
- Post-audit (2026-09-27): README corrections applied as a separate section; prereg check is
  `head -n 217 README.md | shasum -a 256` vs `artifacts/prereg_sha256.txt` (still matches).
  Lessons: (1) half-panel vs half-panel agreement is NOT a ceiling for a full-panel-mean target;
  use Spearman-Brown (R-04: half WP rho 0.374 -> reliability ~0.54 -> attainable ~0.74).
  (2) Any feature added after seeing a verdict line is a pre-registration deviation: disclose it
  and refit without it. (3) Always report per-work paired deltas and margin sensitivity.
