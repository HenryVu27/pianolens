# F-07 repeated takes + H5 (2026-09-27)

Code: `src/pianolens/features/takes.py` (`decompose_takes`, `take_structure`, `variance_components`,
`align_takes`, `takes_from_files` for Henry's MIDI), tests `tests/features/test_takes.py` (9).
Experiment: `experiments/2026-09-27-F-07-H5-intent-vs-noise/` (run.py, asap.py, analyze.py).

## Design (why)
- Channels come from `shaping.channel_data` (timing dev_beats, tempo, velocity, articulation).
  Match across takes: notes by score_id; positions by the smallest score_id starting at that beat
  (works when takes unfold repeats differently). Intersection only; `n_dropped` counts the rest.
- Variance components = two-way consistency ANOVA (ICC(3,1), ICC(3,k) = Spearman-Brown). Takes
  centered per channel first; level offsets reported as `level_<j>`.
- TRAP: regressing pooled per-take deviations e_ij on shared score features gives R² <= 0 by
  construction (sum_j e_ij = 0). Score the specific part per take, and for H5 use the pairwise
  half-sum vs half-difference (equal noise variance for exchangeable takes). k-mean vs deviation
  is unbalanced for k > 2.
- Synthetic timing: F-03 smooth fit + outlier removal absorbs ~20% of iid fine-timing variance.

## Data facts
- PianoCoRe tier A: 1,897 (piece, named performer) groups with >= 2 takes (102 pianists, 524
  pieces), all transcribed (ATEPP / PERiScoPe), one score_id per group. 1,728 after coverage
  (n_match / n_score_notes) >= 0.80. No `is_duplicate` rows in tier A, but many duplicates remain:
  same recording has timing r 0.95-0.98+ and tempo r > 0.99 (Arrau BWV 773: tempo 0.99996).
- Pair r distribution (5,472 pairs): no clean gap. ASAP Disklavier distinct performances by the
  same player reach tempo r 0.99 (Islamey) with timing r ~0.7, so a tempo-r rule over-merges;
  timing r is the better duplicate signal. ASAP "<Name>NN" vs "<Name>NNM" are different
  performances (max timing r 0.92), not duplicates.
- Oversubscription: set OMP/OPENBLAS/VECLIB_MAXIMUM_THREADS=1 in the parent env before a
  ProcessPool; setting it inside the worker is too late (load hit 45 with R-09 running).
- Runtime: ~0.7 s per group at 6 workers (PianoCoRe loader + tempo + basis + CV ridge).
  ASAP alignment of long pieces under load: ~20-60 s per take.

## Measured (H5, pianist bootstrap, dedup r > 0.98, 1,390 groups / 91 pianists / 415 pieces)
- timing: R²(pair sum) 0.123 [0.114, 0.132], R²(pair diff) 0.005 [0.003, 0.008],
  delta 0.118 [0.110, 0.126]; ICC(3,1) 0.60. Supported; holds at 0.95 / 0.90 thresholds and k=2.
- articulation delta 0.229, velocity 0.259 (transcribed), smooth tempo 0.103 (diff R² < 0).
- 88 of 91 pianists have mean delta > 0.
