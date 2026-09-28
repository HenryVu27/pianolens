# Measured results (pointers; the README is the source of truth)

- R-01 (2026-09-27, Confirmed with caveats; post-audit fixes applied): PercePiano 19 items,
  1,189 segment means. PCA-PA 4 (primary), FA-PA 7, MAP 5; pedal items merged -> PCA-PA 3; no
  `Score` renders -> 5. Headline: 3-5 factors, one dominant general factor (first PC 47%),
  falsifier (> 8) never met; FA-PA alone reads "inconclusive". k=4 oblimin: general quality
  factor (10 items), loudness/energy, pedal/articulation (item-2 pole direction undocumented),
  dark mood; F1-F3 r 0.49; mean communality 76%; pedal sparse-saturated h2 0.96 (near boundary,
  no Heywood). Raters at matched n retain ~3, first PC 34%: no evidence raters use fewer dims.
  Item split-half over raters median 0.74 (0.64-0.88); within-rater test-retest median 0.52.
  `experiments/2026-09-27-R-01-percepiano-factors/`.
- Implication for R-03/R-04: per-item rater-noise ceiling is modest (split-half 0.64-0.88 for a
  full panel); report rater parity per item and maybe per factor score.
- R-03 (2026-09-27, Confirmed with caveats; post-audit fixes applied): MuQ L9-12 + MLP, Salamander C5 Light renders. (a) CrescendAI
  protocol 0.509 [0.471, 0.537] (target 0.536); (b) inner val 0.460; (a)-(b) 0.049; (b-test) 0.525;
  (c) leave-work-out -0.087 pooled, within-passage R² 0.155, WP pair acc 0.620 (per work: D935
  0.40, WoO80 0.10, D960 mv2 -0.36, mv3 -1.20); (d) leave-performer-out 0.478. Ridge probes: flat
  after layer ~6. OOF preds for paired tests: `experiments/2026-09-27-R-03-muq-percepiano/artifacts/oof_predictions.npz`
  (keys like `c_official_1000`, shape (N, 5 seeds, 19)); row ids: `pids_cv` for a_/b_/ridge_b, `pids_all_labeled` for c_/d_/ridge_c.
- R-03 post-audit (`postaudit.py`, `artifacts/postaudit.json`): (a) fold mean 0.491 (theirs 0.530);
  2/5 seeds below band. (c3) D960 mv2+mv3 merged: -0.031 / within R² 0.046 [CI incl. 0] / WP acc 0.618
  / WP Spearman 0.334 (train-mean -0.070). No Score (eval only): (b) 0.404/0.173/0.636; (c)
  -0.163/0.063/0.590; (c3) -0.084/0.068/0.586. Within R² is fragile; WP acc + WP Spearman robust.
  OOF for R-04: `artifacts/oof_predictions_postaudit.npz` (`c3_official_1000` on pids_all_labeled;
  `*_noscore` on `pids_*_noscore`; masks). Score rows = `player` starts with "Score" (116 labelled).
- Single-rater parity is a loose ceiling on PercePiano. Under leave-work-out frozen MuQ only roughly
  matches one rater (0.631 vs 0.590 ties-as-0.5; 0.639 vs 0.623 on rater-untied pairs; ~30% of a
  rater's same-passage pairs are ties). Parity used seed-ensembled preds (stronger than seed-avg:
  (c) -0.059 vs -0.087). Always bracket parity with an untied-pair version and a no-Score version;
  use a panel-level (split-half) ceiling in R-04 as well.
- R-04 (2026-09-27, Provisional; needs audit): H3 supported (matches, not beats). Leave-work-out WP acc / WP rho,
  S0 vs MuQ-ensemble: c 0.624/0.350 vs 0.623/0.342; c3 0.614/0.332 vs 0.619/0.337; no Score c 0.595/0.254 vs
  0.594/0.257, c3 0.585/0.238 vs 0.587/0.243. S1 (ref feats) 0.635/0.630; late fusion 0.638/0.633. Pooled R² S0
  c 0.163, c3 -0.023. Baselines reproduce audit (performer prior 0.570, deadpan 0.541). Split-half half-panel WP acc
  0.641 (SB within r 0.631). Importance: pedal > velocity > tempo shape > voicing; evenness ~0 (broad = strict).
  OOF: `experiments/2026-09-27-R-04-symbolic-percepiano/artifacts/oof_predictions.npz` (keys `S0__c__primary` etc).
- R-02 (2026-09-27, Provisional, awaiting eval-auditor): H1 not supported, not falsified.
  PianoCoRe tier A, joint smooth tempo + velocity, n = 50 per piece (698 pieces): k80 in-sample
  19 [16, 21] (tempo 13, vel 16, raw vel 20, residual timing 25); 3% of pieces ≤ 10, 35% > 20;
  held-out R² 0.23/0.31/0.42 at k = 5/10/20 (0.37/0.50 at k = 10/20 with n = 300); phase null
  k80 25, beaten on 100% of pieces; mean curve 62% of per-performance variance. Disklavier and
  Vienna sensor NOT lower-dimensional (transcription noise is not the cause). 16-bar windows:
  k80 10. `experiments/2026-09-27-R-02-expression-dimensionality/` (curves cached in artifacts/curves/).
- R-06 (2026-09-28, Provisional, awaiting eval-auditor): P (PercePiano WoO80/D960, unseen by both) composite r SyMuPe 0.388 [0.359,0.416], PT 0.393 [0.365,0.421], ridge 0.166, LOO others 0.720; diff -0.005 [-0.025,0.016]. A: 0.581 vs 0.425; V: 0.657 vs 0.555 (D783 unseen: 0.601 vs 0.591). c1 core jitter AUC ~0.95-1.0, deadpan 0.00 both; c2 deadpan 0.31-0.37 (ext 0.65). Tie-break jitter diff +0.008 [0.004,0.011] -> SyMuPe. `experiments/2026-09-27-R-06-expression-model-h2h/artifacts/results/`.
