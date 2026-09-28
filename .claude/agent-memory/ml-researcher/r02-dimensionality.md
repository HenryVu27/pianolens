# R-02 notes (2026-09-27)

- Curve cache: `experiments/2026-09-27-R-02-expression-dimensionality/artifacts/curves/<slug>.npz`,
  one per piece (730), keys T (log tempo ratio on the integer-beat grid, NaN outside span), Tobs,
  V (raw per-beat mean velocity), R (dev_beats per score position), grid, pos_grid, bar_starts,
  bpb, perf_ids, s_* F-03 summaries. QC + blocks: `analyze.load_blocks(path)`. Reuse for R-05 /
  tier D reference sets instead of re-running F-03 (70 min on a loaded machine; 0.08 s/perf alone).
- PianoCoRe: all performances of a piece share one refined score per score_id, so the beat
  grids line up with no alignment; ~20% of pieces have 2 score_ids ("mini" vs full refined), so
  use the majority score only (730 -> 698 pieces with >= 50 left).
- `tempo_from_onsets` needs no partitura: pass s_onset_beat / p_onset_sec of `match` rows and
  beats_per_bar = median s_ts_beats. Beats are denominator units (12/8 -> 12 per bar).
- Vienna 4x22 to PianoCoRe beat offset: match score (onset, pitch) sets; Op.10/3 offset +2
  (Vienna starts at -0.5), Op.38 +6, K331 0 but repeats differ (only 49 beats map).
- In-sample PCA counts grow with n and with piece length: always compare at fixed n, and use held-out
  reconstruction R² (`pianolens.eval.dimensionality.heldout_r2_curve`) plus a phase-randomized null.
