# PercePiano label quirks (measured 2026-09-27, R-01)

- `labels/total_2rounds.csv`: 14,934 rows, 65 raters, 1,202 file names. 19 items are CSV columns
  4-22 (`Question_1_1_1`..`Question_9_1_1`); `Question_9_2_1` (464 non-empty) and `message` are
  not labels. Authors take `row[3:-2]`.
- Scale 1-7. 208 rows have a value > 7.1 (up to 9): authors drop the whole row. Empty or 0 =
  "not rated" for that item.
- Filename = `<piece>_<N>bars_<player>_<segment>` (player is the SECOND-TO-LAST token, not last,
  despite the README). `Score`/`Score2` = deadpan score renders; authors rename some `Score` to
  `Score2` (Beethoven WoO80 Score seg 5-16, Schubert D935 no.3 Score seg 1) and lowercase
  `_score` to `_Score`. 20 pieces (17 WoO80 variations/theme, D935 no.3, D960 mv2, D960 mv3);
  D960 mv3 + mv2 are ~72% of segments.
- Repeated (rater, file) pairs: 3,634 rows repeat a pair; 2,198 are exact resubmissions (same
  dataID). The rest are re-ratings (new dataID) -> usable for test-retest. Authors keep all rows.
- Two different mean-label jsons: `labels/label_2round_mean_*.json` (1,189 keys) and a top-level
  copy (1,202 keys); values differ for ~490 shared keys. 20th element of each value is a
  pianist index, not a label. Recomputing means from the CSV with the authors' rules reproduces
  `labels/` exactly (1,189 segments); the top-level copy is another version (1.1% differ, up to
  1.5 points). Use `labels/`.
- Parser used in R-01: `experiments/2026-09-27-R-01-percepiano-factors/run.py` (`load_long`).
  Switch to the D-02 loader once it exists and check counts match.
- CrescendAI paper folds (`audio_fold_assignments.json`, d8b603fd): fold_0..3 = 263/234/255/269
  keys + `test` 181; 1,009 of the CV keys have official labels (they report n=1005). Their
  "overall_r2" is the pooled OOF sklearn R² (uniform over 19 dims), not the fold mean, and
  `max_frames` was 1000, not 300 (the crescendai doc is wrong on frames).
