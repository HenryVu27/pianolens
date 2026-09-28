# R-03 (MuQ on PercePiano) audit facts, 2026-09-27

- CrescendAI paper-era copies (fold file, result JSONs, notebooks) sit in the lead session scratchpad
  `.../scratchpad/paper_era/` and a repo clone in `.../scratchpad/crescendai/` (not in the repo; may vanish).
  `audio_folds.json` == R-03 `artifacts/audio_fold_assignments.json` byte for byte.
- CrescendAI `overall_r2` = pooled OOF R² (nb01 cell 11 concatenates all_preds); A1a fold mean 0.530 vs pooled 0.536.
- R-03 `run.py` is exactly reproducible on CPU (torch.set_num_threads(4)): importing its functions
  via importlib and rerunning (a)/(b)/(c) matched results.json to 4 decimals. (a) takes ~70 s, (c) ~120 s.
- PercePiano structure: 99 passages = work+bars+segment (Beethoven 17, D935 13, D960 mv2 26, mv3 43).
  Beethoven's 12 human performers never play Schubert; the same 12 human Schubert performers play both D960 mv2 and mv3,
  and 6 of them also play D935 (plus schubert:13, who plays only D935). Score/Score2 (deadpan) occur in every work: 116 of 1,189 labelled segments.
- Deadpan Score renditions carry about 60% of leave-work-out within-passage R² (0.155 -> 0.063 without them;
  WP acc 0.620 -> 0.590). Always ask for a no-Score sensitivity check on any PercePiano within-passage claim.
- Merging D960 mv2+mv3 into one work: within R² 0.155 -> 0.046 (CI includes 0); WP pair acc stable 0.618.
  Within-passage R² is fragile; WP pair acc and WP Spearman are robust.
- Legal performer-prior baseline under leave-work-out (passage-centred performer mean from training works):
  WP acc 0.570, within R² 0.080.
- Within-passage rater parity scores rater ties as 0.5; about 28% of a rater's same-passage pairs are ties,
  which caps single-rater accuracy. Check parity on rater-untied pairs as a bracket.
- S-02 renders: bit-identical re-renders (8/8 sha256). The 8 clipped clips are all Score renditions, with a few
  samples per million at full scale; immaterial.
