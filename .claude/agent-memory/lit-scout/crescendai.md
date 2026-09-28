# CrescendAI facts (L-02, 2026-09-27); full write-up in docs/research/2026-09-27-crescendai.md

- The paper-era state is commit `d8b603fd` (2026-01-26). Results are in
  `model/data/results/01_main_experiments/*.json` and `02_muq_fusion_experiments/`.
  Folds: `model/data/cache/audio_fold_assignments.json` (4 folds plus a 181 test set).
  Get them with `git fetch --unshallow --filter=blob:none` and then `git show`.
- The March 2026 "clean" folds (`model/data/labels/percepiano/folds.json`) group by performer
  recording because the filename order was misread. Every validation passage is in train, and
  Beethoven is dropped. All of their post-March numbers are on these folds.
- Headline 0.537 = the A2 Pianoteq run on 3/4 folds. A1a Salamander 4-fold = 0.536.
  - The CI [0.465, 0.575] comes from B2 cross-soundfont (fold 3 only).
  - p < 1e-25 is MERT vs symbolic (aligned_fusion/S1).
- MuQ features: hidden_states[9:13] averaged to 1024-d, 300 frames, mean+std pooling, MLP 512,
  dropout 0.2.
- No public weights. The Pianoteq renders are lost (their 01-data.md says so).
