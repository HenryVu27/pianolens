# F-05d coherence minimum length (2026-09-28)

Rule (DECISIONS 2026-09-28 after R-09), in `shaping._coherence`: summary has `n_written_bars`
(distinct measure numbers among the channel's rows) and `n_blocks = ceil(n_written_bars /
block_bars)`. R² defined only if `n_blocks >= ShapingConfig.min_blocks` (3) AND
`n_written_bars >= min_written_bars` (12); else all R² NaN, no fit, no bars/predictions for that
channel, `undefined_reason` in {too_few_rows, constant, too_few_bars, too_few_blocks, cv_failed}.
At block_bars=4 the 12-bar rule is the binding one. CV folds still use bar-number blocks.

- `extract.segment_features` (R-04 short segments, 1-bar blocks) overrides
  `min_written_bars=ExtractConfig.coherence_min_bars` (8), else every 8-bar PercePiano segment
  would go NaN. Channel rows can span fewer bars than the score (timing: 7 of 8 in D960 mv2/mv3).
- `takes.py` (F-07) now uses the same rule (distinct written bars, `ceil(n / block_bars)`,
  `min_blocks` and `min_written_bars` from `ShapingConfig`, `undefined_reason`); the old
  range-based count there is gone (checked 2026-09-29). Short-segment output (1-bar blocks,
  lowered minimum) is "short-segment coherence", never the H4 measure.

## Impact measured (outputs `data/interim/f05d_check/`)
- R-04 (1,202 rows): only timing coherence changes, 11 rows defined -> NaN (5 Score renditions).
  Rerun of run.py: S0 primary c|all within pairacc 0.6239 -> 0.6233, spearman 0.3497 -> 0.3492;
  H3 verdicts unchanged. Baseline rerun of run.py on the old parquet is deterministic except 24
  baseline_train_mean leaves.
- Code drift: current code does NOT reproduce R-04 features.parquet coherence (median |dR2|
  ~0.02, max ~2 after clipping) because clip_to_train became default after R-04. With
  clip_to_train=False values match to 1e-16.
- R-09 (1,604 rows): defined values identical (<1e-11); 31-35 rows per channel -> NaN (Czerny
  Op.101 etudes etc.), 23-24 inside the analysis pool (1,081 -> 1,057 valid). Verdicts all still
  inconclusive; articulation b_rank 0.0082 -> 0.0030, timing 0.0045 -> 0.0047, velocity
  (secondary) 0.142 [-0.014, 0.482] -> 0.019 [-0.005, 0.039].
