# F-02 correctness + D-08 mistake set (2026-09-27)

- MAESTRO-E generator (ben2002chou/CocoChorales-E_MAESTRO-E `mistake_augmentations.py`):
  n = ceil(lambda*N) +- half, lambda 0.03-0.05; type uniform 0..15 (0 drop, 1 wrong pitch,
  2 wrong-then-corrected, 3 extra, 4-15 timing only); pitch delta int(N(0,1)) != 0 (so +-1/+-2);
  timing shift N(0, 300 ms). Our differences are in `perturb.py` docstring.
- (n)ASAP robust GT already has ~52 insertions and ~40 deletions per 1000 notes (rate-0 copies of
  mistakes_v1). Evaluations must treat them as don't care; at bar level that removes 46% of bars
  for "any" (optimistic bar numbers).
- mistakes_v1 uses single-path scores only: GT score ids == align_performance ids there.
  Multi-path scores would need `validate.ground_truth_variant` to map ids.
- parangonar ornament handling (`process_ornaments`) matches only ONE performed note to an
  ornamented score note (possibly a different pitch); the other trill notes stay insertions ->
  correctness.py whitelists insertions within +-2 st, [onset-0.25 s, expected offset].
- Missed-note FP on clean perfs = aligner picks another same-pitch duplicate (133/133 checked on
  3 perfs were GT matches). Missed precision at the 100 ms default (rates 0.02-0.10): note
  level 0.385-0.691, bar level 0.921-0.960 (the older 0.38-0.67 / 0.90-0.95 were the 50 ms
  run; correctness-validation spec, "pipeline as deployed").
- Wrong-pitch recall with the GT alignment: 0.91 at 50 ms, 0.95 at 100 ms (expected-onset estimate
  from chord-mates misses rolled chords). F-02b: default is now 100 ms
  (`WRONG_PITCH_WINDOW_SEC`, param `wrong_pitch_window_sec`, renamed from `pair_window_sec`);
  `ONSET_TOLERANCE_SEC` = 50 ms kept as a named reference only.
- F-02b ornament test "failure" was a 6 ms boundary: with ornaments=False the grace note is
  graded, its expected onset = chord-mates' median (2.006 s); the extra 1 st off at 1.95 s
  pairs at 100 ms. Correct by the rule; the test now asserts both windows.
- eval_correctness.py is deterministic: F-02b rerun reproduced every tp/fp/fn count.
- Numbers: `docs/specs/correctness-validation.md`; raw counts
  `data/interim/correctness_eval/counts.csv`. Eval: 3 min on 12 workers (align median 3.2 s).
