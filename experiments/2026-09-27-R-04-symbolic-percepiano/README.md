# Symbolic feature model vs frozen MuQ on PercePiano, leave-work-out

Ticket: R-04    Hypothesis: H3 (H3b: symbolic features vs MuQ)    Status: Provisional

Pre-registered 2026-09-27 by `ml-researcher`, before any feature table was built or any model
fitted. Before writing this, three segments were run through the feature code to time it and to
see which features are defined on short segments; no label was looked at. Sections below
"Command" are added after the runs.

## Question

1. Under leave-work-out, does a small model on interpretable, score-aligned MIDI features
   (F-02 correctness, F-03 tempo, F-04 control, F-05 shaping, simple global descriptors) order
   performances of the same passage as well as frozen MuQ (R-03) does?
2. Does adding reference-based features (computed from the other performers' MIDI of the same
   passage, never their labels) help? This is transductive and reported separately.
3. Does MuQ + features beat either alone?
4. Which features drive each of the 19 dimensions? (What the product needs.)

## Falsified if

The plan's H3 row says: falsified if the symbolic model is worse than MuQ by more than 0.05 R²
(averaged over dimensions) with non-overlapping CIs. DECISIONS 2026-09-27 moved the decision to
leave-work-out with within-passage metrics co-primary, and requires a claim to hold under both
work groupings. Refined rule, fixed here:

- **Comparison.** The primary symbolic model **S0** (own-performance features only; see Method)
  against MuQ, both as out-of-fold predictions on the same rows. MuQ = R-03's MLP head, L9-12,
  1,000 frames, official means, **seed-ensembled** (mean over its 5 seeds; slightly stronger than
  the seed-averaged numbers in R-03's main table, so this is the conservative side for us).
- **Co-primary metrics** (each averaged over the 19 dimensions): within-passage pairwise
  accuracy (WP acc) and within-passage Spearman (WP rho), defined exactly as in R-03.
- **Variants** (all four from the R-04 bullet): {4 works (D960 mv2 and mv3 separate), 3 works
  (D960 merged)} x {all segments, Score renditions excluded from scoring}. "No Score" is
  evaluation-only, as in R-03 (same models and predictions).
- **Paired difference** Δ = S0 − MuQ per variant and metric, 95% CI from a cluster bootstrap over
  passages (1,000 replicates, same resamples for both models).
- **Non-inferiority margins:** 0.02 for WP acc, 0.05 for WP rho. (0.02 is about one sixth of
  MuQ's distance from chance, 0.62 − 0.50; 0.05 is the plan's margin number and about one sixth
  of MuQ's WP rho, 0.33.)
- Per variant and metric: **non-inferior** if CI_low(Δ) > −margin; **inferior** if
  Δ < −margin and CI_high(Δ) < 0 (the plan's "worse by more than the margin, CIs separated").
- **H3 supported ("matches or beats")** iff S0 is non-inferior on both co-primary metrics in
  all four variants. **"Beats"** is claimed only if CI_low(Δ) > 0 on both metrics in all four.
- **H3 falsified** iff, for at least one co-primary metric and one Score handling (all / no
  Score), S0 is inferior under both work groupings.
- Otherwise **inconclusive**.
- The same rule is applied to **S1** (S0 + reference-based features) as a secondary,
  transductive result. If only S1 passes, the claim is "transductive symbolic features match
  MuQ", not H3 as stated.
- Secondary (reported, not decisive): the plan's original rule on pooled R² under both
  groupings; within-passage R² (fragile, see R-03 audit); leave-performer-out.

Pre-stated expectations (reported against, not used as H3 criteria):

- E1: S0 beats every baseline (train mean, performer prior, deadpan indicator) on WP acc under
  both groupings.
- E2: MuQ + features (early or late fusion) is at least as good as the better of the two.
- E3: Timbre dimensions (colour, richness, brightness) are where MuQ keeps an edge, if anywhere;
  loudness, pedal, tempo and articulation dimensions are where symbolic features do well.
- E4: Pooled R² under leave-work-out is near or below 0 for every model (between-work offsets).

## Data

- PercePiano, `data/raw/percepiano`, commit e672299, loader `pianolens.data.percepiano` (D-02).
  1,202 segment MIDI files (provenance: `disklavier` for humans; `synthetic` for the deadpan
  Score/Score2 renditions), each with its own segment MusicXML (`virtuoso/data/score_xml`).
- Primary targets: `load_percepiano_official_means()` (1,189 labelled segments, 0-1 scale);
  sensitivity: de-duplicated means `load_percepiano_ratings().mean() / 7`.
- Per-rater labels (63 raters) for the ceilings: `load_percepiano_ratings()`.
- 99 labelled passages (passage = work + bars + segment): D935 13 (all 4-bar), D960 mv2 26,
  D960 mv3 43, WoO 80 17; 3-14 labelled segments per passage (median 13), 2-12 human
  performances per passage. Segment lengths: 4 bars (116 labelled), 8 (928), 16 (145).
- MuQ side: `experiments/2026-09-27-R-03-muq-percepiano/artifacts/oof_predictions.npz`
  (`c_official_1000`, rows `pids_all_labeled`; `d_official_1000`) and
  `oof_predictions_postaudit.npz` (`c3_official_1000`, same rows; no-Score masks);
  `muq_pooled.npz` (L9-12, 1,000 frames) for the early-fusion model.
- R-01 k = 4 loadings (`experiments/2026-09-27-R-01-percepiano-factors/artifacts/loadings_k4.csv`)
  for factor scores.

## Splits

- **(c) leave-work-out, 4 works** (D960 mv2, D960 mv3, D935 no.3, WoO 80), all 1,189 labelled
  segments, exactly R-03's folds.
- **(c3) leave-work-out, 3 works** (D960 mv2 + mv3 merged), R-03 post-audit folds.
- **(d) leave-performer-out**, `group_kfold(performer_id, 4, seed=0)` as in R-03; reported
  separately, never replaces (c)/(c3).
- **Inner selection:** leave-one-training-work-out inside each outer training set (3 inner folds
  for (c), 2 for (c3); for (d), 4 inner folds grouped by work within the training rows). Every
  hyperparameter and the model family of the primary model are chosen on the inner folds only.
- Seed 0 everywhere (HistGradientBoosting without subsampling is deterministic; ridge is exact).
  Bootstrap seeds as in R-03.

## Features

Every segment is aligned to its own segment score with `pianolens.align.align_performance`
(downstream code uses the returned performed score). Then, per segment:

- **F-02** `correctness`: accuracy, error rate, wrong-pitch / missed / extra rates per graded
  score note, match ratio.
- **F-03** `tempo_model` (defaults: 1.5-bar cutoff): log geometric-mean tempo (score beats),
  overall / smooth tempo ratio (pauses), smooth log-tempo SD and p90-p10, jitter RMS and MAD
  (beats), jitter without the metric pattern (beats), pauses.
- **F-04** `control_features`: evenness (broad and strict variants, IOI CV and velocity SD),
  hand synchrony (mean, robust SD, velocity slope, residual SD), tempo stability (instability,
  phrase SD, drift), pedal blur (fraction, beats), pedal-down fraction.
- **F-05** (components called with the segment's own tempo curve): structural coherence R² for
  velocity, timing and articulation (with and without markings); voicing (melody velocity
  difference, lead, share louder, lead-velocity correlation); dynamic-marking compliance
  (hairpin / level / accent agreement, level-velocity Spearman); repeated-material consistency
  (usually undefined on segments).
- **Global descriptors:** mean, SD and p95-p5 range of velocity; SD of bar-mean velocity;
  articulation (median and IQR of the key-down log ratio to the notated length; legato overlap
  share of consecutive melody notes); pedal (CC64 presses per second, mean CC64 depth, CC67 soft
  pedal down fraction); chord asynchrony (median onset spread of score chords, ms and beats);
  notes per second.

**Short-segment adaptations** (segments are 4-16 bars):

- Structural coherence uses 1-bar CV blocks, `min(5, written bars)` outer folds, 3 inner folds,
  no buffer, penalties `logspace(-2, 4, 13)`, and is clipped to [-1, 1]. It is **undefined (NaN)
  for segments shorter than 8 written bars**, i.e. all of D935. The **smooth-tempo channel is
  dropped** from coherence for every segment: an 8-bar segment has about 5 degrees of freedom in
  the 1.5-bar smooth curve, so its R² is not meaningful.
- Tempo stability keeps its 4-bar phrase allowance (sections of at least 2 bars).
- Repeated material, dynamic compliance and hand synchrony are NaN when the segment has no such
  material; models handle NaN (native in gradient boosting; median + missing indicator in the
  linear models).

**Reference-based features (S1 only; transductive).** References are the *other human*
performances of the same passage (never Score renditions; the target itself left out), whatever
fold they are in. Only their MIDI is used, never labels.

- F-04 timing noise against the leave-one-out consensus fine timing (min 3 references), and the
  consensus R².
- Curve agreement with the leave-one-out mean of the references at the same score notes /
  positions: Pearson r and RMS difference for per-note velocity (centred on each performance's
  mean), per-position timing residual (beats), per-beat smooth log tempo, per-note articulation
  log ratio.
- Relative level: for mean velocity, log tempo, velocity SD, articulation median, pedal-down
  fraction, pedal presses per second, jitter and smooth-tempo SD: value minus the median of the
  references.

## Models

Per feature set (S0, S1), one model per target set (19 dimensions share hyperparameters):

- **ridge**: standardized features, NaN -> training median + missing indicators (for columns
  with any NaN); alpha in `logspace(-1, 4, 11)`.
- **GAM-like**: cubic `SplineTransformer` (4 knots) per feature + ridge, alpha as above.
  (`pygam` is not installed; LightGBM is installed but its libomp is missing on this Mac, so
  gradient boosting is scikit-learn's.)
- **GBM**: `HistGradientBoostingRegressor` per dimension, `learning_rate` 0.05,
  `min_samples_leaf` 20, grid `max_depth` in {2, 3} x `max_iter` in {100, 300},
  `l2_regularization` 1.0.
- **Primary symbolic model** (the S0 / S1 used in the H3 rule): family and hyperparameters chosen
  per outer fold on the inner folds by mean inner WP rho over 19 dimensions. The individual
  families are reported descriptively.
- **Combined MuQ + features:** (i) late fusion, the plain mean of the MuQ seed-ensemble OOF
  prediction and the primary S0 prediction (no tuning); (ii) early fusion, ridge on
  [S0 features, MuQ L9-12 pooled 2,048-d], each block standardized, MuQ block scaled by
  w in {0.03, 0.1, 0.3}, (w, alpha) chosen on the inner folds.
- **Factor scores** (cheap extra): the four R-01 k = 4 factors as unit-weighted means of their
  salient items (z-scored, sign from the loading); the same primary-model procedure; WP metrics
  vs MuQ's predictions mapped through the same item weights.

## Baselines and ceilings

- **Train mean** (WP acc 0.5 by construction).
- **Performer prior:** training rows' labels centred on their passage mean; each performer's
  mean of those; prediction = train mean + the test row's performer offset (0 if unseen).
  (R-03 audit: WP acc 0.570 under (c).)
- **Deadpan indicator:** train mean + the training within-passage offset of Score rows vs human
  rows. (R-03 audit: 0.541 under (c).)
- **Single-rater parity** within passages, as R-03 `wp_parity`: ties scored 0.5, rater-untied
  pairs, and untied without Score. Pearson rater parity per dimension as R-03.
- **Panel split-half reliability of the mean:** 200 random splits of the raters into halves (de-
  duplicated ratings); per segment the mean of each half (segments with at least 2 raters per
  half); WP acc and WP rho of half A against half B, and the within-passage Pearson of the
  passage-centred half means, Spearman-Brown corrected to the full panel.

## Metrics and CIs

Pooled R², within-passage R², WP acc, WP rho (R-03 definitions; per-dimension means), per-work
values, per-dimension tables. 95% CIs from a cluster bootstrap over passages (2,000 replicates for
R², 1,000 for WP acc and paired differences, 500 for WP rho, as in R-03). These CIs resample
passages, not works, so they understate uncertainty about new works (4 works).

## Interpretability

- Grouped permutation importance on the outer test folds for the primary S0 model and for the
  S0 GBM and ridge: drop in WP rho per dimension when a feature group (correctness, tempo,
  timing noise, evenness, hand sync, pedal, velocity/dynamics, articulation, voicing, coherence,
  dynamic compliance) is permuted within passages; 5 repeats.
- Standardized ridge coefficients (fitted on all labelled segments) and GAM partial-dependence
  shapes for the top features, as tables.
- **Evenness variant** (DECISIONS, F-04 follow-up 1): broad vs strict decided by predictive
  value: grouped permutation importance of each, and S0 refits with only one variant
  (descriptive, not part of the H3 rule).

## Method

1. `features.py`: align and extract per passage, in parallel over passages (14 workers; aligned
   performances do not pickle, so workers return flat rows). Cache
   `artifacts/features.parquet` plus the per-segment curves needed for reference features.
2. `run.py`: baselines, S0 / S1 / families / fusion / factor models under (c), (c3), (d);
   metrics; paired tests vs MuQ; ceilings; importance. Writes `artifacts/results.json`,
   `oof_predictions.npz`, per-dimension and importance CSVs.

Reusable feature code goes to `src/pianolens/features/extract.py` (batch helper, with tests).

## Command

```
uv run python experiments/2026-09-27-R-04-symbolic-percepiano/features.py
uv run python experiments/2026-09-27-R-04-symbolic-percepiano/run.py
```

## Run record

- Date 2026-09-27. Git: no commits in this repo ("uncommitted"); code hash in
  `artifacts/results.json` (`code_hash`, sha256 of `src/**/*.py` + `run.py` + `features.py`).
  Pre-registration sha256 and time: `artifacts/prereg_sha256.txt` (00:58 UTC 2026-09-28).
- Features: `features.py`, 1,202 / 1,202 segments, 0 alignment failures, 0 component errors,
  81 s on 14 workers. `features_meta.json` records `control_py_sha256` `70924c344ac6`, i.e. the
  **F-04b version of `control.py`** (quarter-note harmony window, functional templates, strict
  evenness, `even_note_rate_nps`). 62 own-performance (S0) + 20 reference (S1) columns.
- Models: `run.py`, CPU, 14 workers, 418 s. Seed 0 throughout.
- Order of runs (full disclosure):
  1. A `--quick` smoke test (2 alphas, 1 GBM config) to find crashes. Its tables were seen.
     Changes after it were crash fixes only (GBM on constant columns; NaN CIs for constant
     predictions). No design choice changed.
  2. A full run on a feature table built before F-04b landed. It was stopped at the
     importance step when the coordinator reported F-04b; only its H3 verdict lines were seen
     (the same verdict as below).
  3. Features re-extracted with F-04b `control.py`, `ctrl__even_note_rate_nps` and
     `ctrl__even_strict_note_rate_nps` added (coordinator request: note rate as a covariate
     for the evenness comparison), full run repeated. **All numbers below are from run 3.**
     *[Post-audit correction, 2026-09-27]* These two note-rate columns were not in the
     pre-registered feature list, and they were added after run 2's H3 lines had been seen.
     That is a deviation from the pre-registration. S0 refit without them (60 features) is still
     non-inferior in all 8 cells; see "Post-audit corrections", item 2.
- Bugs found and fixed during feature extraction (details under Threats):
  - `src/pianolens/data/types.py`: multi-track MIDI gave duplicate performance note ids.
  - `src/pianolens/features/extract.py` (new batch helper) catches a `ZeroDivisionError` in
    `shaping.voicing` rather than fixing `shaping.py` (F-05b owns it). After the id fix it no
    longer fires on PercePiano.

## Results

All metrics are means over the 19 dimensions. 95% CIs come from a cluster bootstrap over
passages. MuQ is R-03's MLP head, seed-ensembled; R-03's seed-averaged numbers reproduce
exactly from its artifacts (c: 0.6194 WP acc; c3: 0.6181; c no-Score: 0.5903).
"S0" is the primary own-performance model: family and hyperparameters picked per outer fold
on leave-one-training-work-out. "S1" adds the reference-based features (transductive).

### Main table: leave-work-out, 4 works (c)

| Model | Pooled R² | Within R² | WP pair acc | WP Spearman |
|---|---|---|---|---|
| Train mean | -0.142 | 0 | 0.500 | n/a |
| Performer prior | -0.107 | 0.080 | 0.570 [0.562, 0.578] | 0.237 |
| Deadpan indicator | -0.086 | 0.098 | 0.541 [0.536, 0.546] | 0.246 |
| MuQ (seed ensemble) | -0.059 [-0.179, 0.027] | 0.165 [0.113, 0.209] | 0.623 [0.611, 0.634] | 0.342 [0.313, 0.372] |
| **S0 primary** | **0.163 [0.094, 0.207]** | 0.143 [0.098, 0.185] | **0.624 [0.615, 0.634]** | **0.350 [0.322, 0.378]** |
| S0 ridge / GAM / GBM | 0.046 / 0.174 / 0.148 | 0.120 / 0.156 / 0.158 | 0.624 / 0.621 / 0.623 | 0.348 / 0.344 / 0.353 |
| S1 primary (transductive) | 0.172 [0.104, 0.217] | 0.177 [0.132, 0.220] | 0.635 [0.625, 0.644] | 0.377 [0.349, 0.404] |
| MuQ + S0, late fusion (mean) | 0.192 [0.128, 0.236] | 0.200 [0.157, 0.239] | 0.638 [0.628, 0.648] | 0.378 [0.351, 0.408] |
| MuQ + S0, early fusion (ridge) | 0.010 | 0.225 | 0.635 | 0.375 |

### Leave-work-out, D960 merged (c3), and both groupings without Score renditions

WP pair acc / WP Spearman (pooled R² in brackets):

| Model | c3, all | c, no Score | c3, no Score |
|---|---|---|---|
| Performer prior | 0.554 / 0.205 (-0.068) | 0.538 / 0.109 (-0.245) | 0.516 / 0.046 (-0.169) |
| Deadpan indicator | 0.542 / 0.252 (-0.038) | 0.500 / n/a | 0.500 / n/a |
| MuQ (seed ensemble) | 0.619 / 0.337 (0.017) | 0.594 / 0.257 (-0.131) | 0.587 / 0.243 (-0.024) |
| **S0 primary** | **0.614 / 0.332** (-0.023) | **0.595 / 0.254** (0.101) | **0.585 / 0.238** (-0.096) |
| S1 primary | 0.630 / 0.365 (0.096) | 0.605 / 0.283 (0.107) | 0.602 / 0.278 (0.015) |
| Late fusion | 0.633 / 0.371 (0.124) | 0.610 / 0.298 (0.154) | 0.602 / 0.279 (0.084) |

### H3 decision (paired Δ = model − MuQ, 95% CI; margins 0.02 acc, 0.05 rho)

| Variant | S0 Δ WP acc | S0 Δ WP rho | S1 Δ WP acc | S1 Δ WP rho | S0 Δ pooled R² |
|---|---|---|---|---|---|
| c, all | +0.001 [-0.007, 0.010] | +0.008 [-0.013, 0.030] | +0.012 [0.003, 0.021] | +0.035 [0.013, 0.057] | +0.222 [0.155, 0.299] |
| c, no Score | +0.001 [-0.010, 0.012] | -0.003 [-0.029, 0.024] | +0.011 [0.000, 0.022] | +0.026 [-0.001, 0.055] | +0.232 [0.154, 0.326] |
| c3, all | -0.005 [-0.014, 0.003] | -0.005 [-0.026, 0.015] | +0.010 [0.001, 0.018] | +0.028 [0.006, 0.047] | -0.040 [-0.100, 0.013] |
| c3, no Score | -0.002 [-0.014, 0.008] | -0.004 [-0.033, 0.024] | +0.015 [0.004, 0.025] | +0.036 [0.009, 0.062] | -0.072 [-0.139, -0.012] |

Every S0 lower bound is above −0.02 (acc) and −0.05 (rho): **non-inferior in all four variants
on both co-primary metrics.** No S0 cell has CI_low > 0, so "beats" is not claimed. S1 is
non-inferior everywhere and its CI excludes 0 in 7 of 8 cells (all but WP rho in c, no Score) (not all 8, so "beats" is not
claimed for S1 either).

Other paired differences (c / c3, all segments, WP acc; WP rho in the JSON):
S1 − S0 +0.011 [0.007, 0.014] / +0.015 [0.012, 0.019]; late fusion − MuQ +0.015 [0.010, 0.020] /
+0.014 [0.008, 0.019]; late fusion − S0 +0.014 / +0.019 (CIs exclude 0); S0 − performer prior
+0.054 / +0.061; S0 − deadpan +0.083 / +0.072 (all CIs exclude 0, also without Score).

### Per work (WP pair acc; pooled R² inside the work)

| Held out | MuQ | S0 | S1 |
|---|---|---|---|
| WoO 80 (226) | 0.625 (0.13) | 0.617 (0.10) | 0.629 (0.10) |
| D935 no.3 (116) | 0.740 (0.41) | 0.717 (0.20) | 0.732 (0.21) |
| D960 mv2 (288) | 0.643 (-0.31) | 0.629 (-0.03) | 0.642 (-0.03) |
| D960 mv3 (559) | 0.596 (-1.16) | 0.612 (-0.30) | 0.620 (-0.28) |
| D960 whole, c3 (847) | 0.607 (-0.26) | 0.604 (-0.25) | 0.621 (-0.05) |

S0 loses to MuQ on the three smaller works and wins on D960 mv3, which is 47% of the data.
The pooled-R² gain of S0 under (c) comes from misplacing the D960 level much less badly; it
disappears under (c3).

### Per dimension (WP pair acc, c, all segments)

S0 ahead of MuQ by 0.02 or more: pedal clean-blurred (0.643 vs 0.592), pedal sparse-saturated
(0.661 vs 0.639), dynamic range (0.609 vs 0.567), energy (0.604 vs 0.580). MuQ ahead by 0.02 or
more: articulation short-long (0.639 vs 0.614), honest-imaginative (0.674 vs 0.651), soft-loud
(0.545 vs 0.525). Near chance for both: bright-dark (MuQ 0.510, S0 0.492) and pleasant-dark
(0.498 / 0.495). The same pattern holds under (c3) and without Score. Full table:
`artifacts/per_dimension.csv`.

### Factor scores (R-01 k = 4, unit-weighted salient items)

WP acc S0 / MuQ: c 0.611 / 0.612, c3 0.604 / 0.610; no Score 0.597 / 0.594 and 0.591 / 0.590.
Per factor under (c), S0 vs MuQ: quality 0.683 / 0.691, loudness-energy 0.607 / 0.619,
pedal-legato 0.659 / 0.637, dark mood 0.493 / 0.502 (both at chance).

### Ceilings

| | Rater | S0 | S1 | MuQ |
|---|---|---|---|---|
| WP acc, rater ties = 0.5 (c) | 0.590 | 0.626 | 0.638 | 0.631 |
| WP acc, rater-untied pairs (c) | 0.627 | 0.633 (13/19) | 0.645 (14/19) | 0.639 (12/19) |
| same, no Score (c) | 0.604 | 0.600 (11/19) | 0.613 | 0.611 |
| WP acc, rater-untied pairs (c3) | 0.627 | 0.625 (11/19) | 0.641 | 0.636 |
| same, no Score (c3) | 0.604 | 0.592 (8/19) | 0.610 | 0.605 |
| Pearson parity (c): mean r; dims above / tied / below | 0.454 | 0.493; 13/1/5 | 0.495; 13/1/5 | 0.434; 10/4/5 |
| Pearson parity (c3) | 0.454 | 0.462; 14/1/4 | 0.487; 14/1/4 | 0.467; 11/1/7 |

Panel split-half (200 random rater halves, de-duplicated ratings): half-panel vs half-panel
WP acc 0.641, WP rho 0.374, within-passage Pearson 0.461, Spearman-Brown full panel 0.631. Without
Score: 0.620 / 0.292 / 0.357 / 0.526. *[Corrected post-audit, 2026-09-27; the original sentences
said the models sit at the half-panel agreement and that little room is left above them.]*
Both models (S0 WP acc 0.624, MuQ 0.623) perform at single-rater level within passages. The
half-panel vs half-panel agreement is not the ceiling for a model scored against the full-panel
mean, because both halves are noisy. Spearman-Brown on the half-panel WP rho (0.374) gives a
full-panel reliability of about 0.54, so a noiseless predictor could reach roughly WP rho 0.74
against the full mean, versus about 0.35 for both models. This is a rough extrapolation
(Spearman treated like Pearson), but it points to substantial headroom. See "Post-audit
corrections", item 1.

### Leave-performer-out (d, reported separately)

Pooled R² / WP acc / WP rho: S0 0.462 / 0.615 / 0.322; S1 0.474 / 0.642 / 0.384; MuQ 0.497 /
0.623 / 0.339; train mean -0.021 / 0.443 (within-passage pairs mix fold models, see R-03).

### Sensitivity

- De-duplicated targets: S0 WP acc 0.626 (c), 0.616 (c3) vs MuQ 0.624, 0.621. No change.
- Without the 4 badly aligned D960 mv3 passages: S0 0.623 / MuQ 0.624 (c); 0.614 / 0.622 (c3).
- Evenness variant (F-04 follow-up 1; note rate kept in both): broad-only 0.625 / 0.613, strict-
  only 0.624 / 0.615, both 0.624 / 0.614 (c / c3 WP acc). Permutation importance of either
  evenness group is at most 0.003 in WP rho; the note rate is larger (0.005-0.006, mostly on
  fast-slow pacing). **Neither variant has measurable predictive value on PercePiano;** the data
  cannot decide between them. (Most segments are 8 bars of slow Schubert; runs are rare.)

### Interpretability (grouped permutation importance, drop in WP rho, S0 primary, c)

Mean over dimensions: pedal 0.097, velocity/dynamics 0.058, tempo shape 0.032, voicing 0.022,
sync/asynchrony 0.008, evenness note rate 0.006; correctness, jitter, articulation, coherence,
dynamic compliance and both evenness variants 0.000-0.004. The ranking is the same for the ridge
and GBM families and under (c3) (there coherence is slightly negative).

Top group per dimension: timing stability ← tempo shape (0.24) and jitter (0.10); pedal items,
articulation short-long, richness, spaciousness, balance, drama, honesty, interpretation ←
pedal; soft-loud, energy, dynamic range, colour, hard-soft articulation ← velocity; fast-slow
← tempo shape and note rate; mellow-raw ← voicing and velocity. Bright-dark and pleasant-dark:
nothing helps (all within ±0.06, mostly negative). Standardized ridge coefficients:
`artifacts/ridge_coefs.csv` (top: `glob__pedal_depth_mean` for 11 of 19 dimensions,
`glob__vel_mean_midi` for loudness, hardness and energy, `tempo__jitter_mad_beats` for timing
stability, `glob__notes_per_sec` for pacing). GAM shapes: `artifacts/gam_partial_dependence.csv`.
Importance tables: `artifacts/importance_{c,c3}_{primary,ridge,gbm}.csv`.

Chosen models: under (c) ridge (alpha 316) for the two D960 folds, GBM (depth 2, 100 trees) for
D935, GAM (alpha 32) for WoO 80; under (c3) GAM in every fold (alpha 10-1,000).

## Verdict (Provisional; audited 2026-09-27: Confirmed with caveats, see Audit)

- **H3: supported ("matches"), by the pre-registered rule.** The own-performance symbolic model
  (S0, 62 interpretable features, no audio, no other performances) is non-inferior to frozen MuQ
  on both co-primary metrics in all four variants (both work groupings, with and without Score
  renditions). The point differences are within ±0.005 WP acc and ±0.008 WP rho. It does not
  beat MuQ: no Δ CI excludes 0.
- **Plan's original R² rule (secondary): not met, so not falsified.** S0 − MuQ pooled R² is
  +0.22 under (c) in both Score variants. Under (c3) it is −0.040 [−0.100, 0.013] (all) and
  −0.072 [−0.139, −0.012] (no Score). The no-Score (c3) cell is worse by more than 0.05, but the
  two models' own CIs overlap (S0 [−0.207, −0.023], MuQ [−0.116, 0.039]), so the plan's
  "non-overlapping CIs" condition is not met; the paired CI does exclude 0 there. Pooled R²
  under leave-work-out mostly measures work-level offsets (R-03 audit), which is why DECISIONS
  moved H3 to within-passage metrics.
- **S1 (transductive, secondary): non-inferior everywhere, ahead of MuQ by about 0.01 WP acc
  and 0.03 WP rho** (CI > 0 in 7 of 8 cells). Using other performers' MIDI of the same passage
  adds a real, consistent gain over S0 (+0.011 / +0.015 WP acc, CIs exclude 0).
- **E1 supported:** S0 beats performer prior and deadpan indicator in every variant.
- **E2 supported:** late fusion beats both MuQ and S0 (+0.014 to +0.019 WP acc, CIs exclude 0);
  the two carry partly different information. Early fusion is no better than late fusion.
- **E3 partly supported:** symbolic features lead on pedal, dynamic range and energy; MuQ leads
  on articulation short-long, honest-imaginative and soft-loud, not on timbre colour or
  richness (tied). Brightness and valence are at chance for both.
- **E4 not supported for S0 under (c):** its pooled R² is +0.16, not ≤ 0; under (c3) it is
  about 0 as expected.
- *[Corrected post-audit, 2026-09-27; the original bullet said the remaining headroom on
  PercePiano is small.]* Both S0 and MuQ roughly match a single rater within passages. The
  full-panel ceiling is far higher (WP rho about 0.74 by Spearman-Brown vs about 0.35 for both
  models), so PercePiano has headroom: the limit is the models, not the labels.
- *[Added post-audit]* Headline claim, in the wording fixed in DECISIONS 2026-09-27: see
  "Post-audit corrections", item 4.

## Threats to validity

- **Few works.** 4 (or 3) works; CIs resample passages, not works. The per-work table shows the
  S0-vs-MuQ sign flips across works; "non-inferior" is an average over very unequal works
  (D960 mv3 is 47%).
- **Selection.** All hyperparameters and families are chosen on inner folds; nothing is chosen
  on outer folds. The inner split holds out whole training works, as the R-03 audit suggested.
  The quick smoke test and the stopped pre-F-04b run were seen before the final run (see Run
  record); no design choice changed after them. *[Corrected post-audit: one change did
  follow run 2, the two note-rate features; it is immaterial, see Post-audit corrections, item 2.]*
- **Loader bug, fixed before any reported number.** partitura numbers note ids per MIDI track,
  so the 2-track Score/Score2 files had duplicate performance ids. Downstream joins kept the
  first duplicate, so Score features were wrong (median chord spread 500 ms instead of 0) and
  parangonar crashed on 2 segments. `performance_from_partitura` now renumbers ids when they
  repeat. Only PercePiano Score renditions are affected among performance loads checked (ASAP,
  MAESTRO, Vienna, Batik performances have no duplicates; ASAP `midi_score.mid` and MAJEPPA
  score MIDIs do but are loaded as scores). R-03 used audio renders, so it is unaffected.
- **Alignment.** 4 D960 mv3 passages align badly for every performer, Score included (match
  ratio < 0.8): a segment-score / MIDI mismatch. Excluding them changes nothing (Sensitivity).
- **Deadpan renditions.** Both groupings are also reported without them; the verdict holds.
- **Transductive S1.** Reference features use other performers' MIDI of the test passage (never
  labels). In a product, references would come from expert recordings, not from the other
  test performances.
- **Timbre dimensions** are rated from Logic Pro audio the models never see; MuQ sees a
  different render (Salamander). Symbolic features can only reach timbre through velocity and
  pedal.
- **MIDI provenance.** Human segments are Disklavier / e-Competition MIDI; results say nothing
  yet about transcribed MIDI from phone audio (Phase 6).
- **Short segments.** Coherence is undefined for 4-bar segments (all of D935) and noisy for
  8-bar ones; its near-zero importance may reflect segment length, not irrelevance of
  structure (H4 is tested on whole pieces in R-09).

## Audit (2026-09-27)

Auditor: `eval-auditor`. Verdict: **Confirmed with caveats.** H3 is supported as non-inferiority
("matches", not "beats") by the pre-registered rule, and every headline number reproduces
bit for bit. The caveats narrow what "matches" means; they do not change the verdict. The header
above is left as pre-registered (line 3 still says Provisional) so that the pre-registration hash
can still be checked against the first 217 lines.

### What was checked

1. **Pre-registration.** The README `Write` in the ml-researcher transcript (00:58:01 UTC) hashes
   to the value in `artifacts/prereg_sha256.txt` (`32ac7ff6...`, hashed 00:58:05). The first 217
   lines of the current README are byte-identical to it. Before the hash, the only data-touching
   calls were a 3-segment timing probe and a passage/segment count; no label, no model. First
   `features.py` run 01:02, `--quick` run 01:14, full run 2 at 01:18, run 3 (reported) at 01:26.
   Margins, metrics, variants, families, grids and the decision rule are unchanged. The edits
   after the quick run are crash fixes only (GBM drops constant columns; NaN-safe CIs), as
   stated.
   **One undisclosed deviation:** between run 2 (whose H3 lines were seen) and run 3, two
   features not in the pre-registered list were added to S0 (`ctrl__even_note_rate_nps`,
   `ctrl__even_strict_note_rate_nps`, coordinator request). Refitting S0 without them (60
   features, same nested procedure): Δ WP acc / Δ WP rho vs MuQ = c all −0.000 [−0.009, 0.009] /
   +0.004 [−0.016, 0.025]; c no Score −0.001 [−0.011, 0.010] / −0.006 [−0.034, 0.021]; c3 all
   −0.002 [−0.011, 0.007] / −0.002 [−0.022, 0.020]; c3 no Score +0.004 [−0.009, 0.015] / +0.008
   [−0.023, 0.035]. Still non-inferior in all 8 cells, so the deviation is immaterial.
2. **Splits.** (c)/(c3) folds are whole works; `run.py` asserts no passage or work crosses. Inner
   selection is leave-one-training-work-out; nothing is chosen on outer folds (choices recorded
   in `results.json`). Performers do cross folds (the 12 Schubert humans play mv2, mv3 and some
   D935), so this is leave-work-out, not leave-work-and-performer-out; this applies equally to
   MuQ and does not bias the paired comparison.
3. **Leakage.** `Prep` (median, missing indicators, mean/SD) and the spline basis are fit on
   training rows only; GBM columns are chosen on training rows. S0 columns come from
   `segment_features` with `references=None`: no other performance and no label enters S0.
   Passage-level constants (tempo, note density, key-dependent pitch features) cannot help a
   within-passage metric directly, and under leave-work-out the test passages are unseen, so
   there is no passage-identity shortcut to a label. Minor: the factor-score targets are
   z-scored with full-data item means/SDs (a fixed linear map; affects only the descriptive
   factor rows). S1 is transductive in MIDI only (other performers' MIDI of the test passage,
   never labels), labelled as such; note `ref__n_references` differs by one between Score and
   human rows of a passage, i.e. it is an is-Score flag (S0's MIDI features already reveal
   Score renditions: chord spread 0, jitter 0).
4. **Paired comparison.** Same rows (`pids_all_labeled`), same passages, same metric code and
   the same bootstrap weights for both models. MuQ OOF alignment checked: mean per-dimension
   Pearson of MuQ (c) with the labels 0.42 aligned vs 0.003 after shuffling rows; 0.71 under
   (d). Spot ids (`Schubert_D935_no.3_4bars_2_1`, `Schubert_D960_mv2_8bars_3_07`,
   `Schubert_D960_mv3_8bars_Score_37`) map to the right passage, work and Score flag. The
   no-Score MuQ cells use the all-segment MuQ models masked at evaluation, as pre-registered and
   as for S0.
5. **types.py fix.** It only touches symbolic loading (MuQ used audio renders, unaffected). After
   the fix Score renditions look deadpan: chord spread 0.0 ms in all 129 Score/Score2 rows,
   jitter ≈ 0, match ratio median 1.0. 71% of Score rows have no CC64; the rest have pedal
   (depth up to 0.999), so pedal is not a pure is-Score proxy. A few Score rows show non-zero
   hand asynchrony (up to 17 ms), probably hand-assignment artifacts; immaterial.
6. **Baselines and ceilings.** Performer prior 0.570 and deadpan indicator 0.541 (c) reproduce
   the R-03 audit numbers. Single-rater parity (ties 0.5 / untied / untied no Score) and the
   split-half computation follow the pre-registered definitions (raters per segment: median 10,
   range 4-17).
7. **Interpretability.** Permutation importance is computed on outer test folds with the fold
   models, permuting within passages. Recomputed on **human rows only**: pedal is still the top
   group (mean drop 0.093 under c, 0.100 under c3; top group for 9 and 11 of 19 dimensions);
   `glob__pedal_depth_mean` alone 0.038 / 0.041. Among human performances its raw within-passage
   Spearman with the labels is 0.48 (pedal saturated), 0.44 (pedal blurred), 0.42 (rich), 0.38
   (articulation long), 0.31 (dramatic). So the pedal dominance is not a Score artifact; it is
   real and plausibly a halo (a wetter sound reads as richer, longer and more expressive),
   consistent with R-01's pedal-legato factor.
8. **Reproduction.** `run.py` rerun from the cached features (scratch copy, output redirected):
   `results.json` identical in every numeric field, OOF predictions max abs diff 0.0.
   `features.py` rerun with the current `src/`: `features.parquet` identical (max abs diff 0.0,
   no NaN mismatches). The `code_hash` in `results.json` (`334b1c86dfbe`) no longer matches the
   current tree, because of a lint rename in `run.py` after the run and later F-05b edits to
   `shaping.py` / `score_basis.py` (opt-in columns only); both reproductions show this is
   immaterial.

### Caveats (to carry with the claim)

- **"Matches" is a passage-weighted average over very unequal works.** Per held-out work (c,
  paired passage bootstrap), S0 − MuQ WP acc: WoO 80 −0.008 [−0.030, 0.012], D935 −0.023
  [−0.043, −0.004], D960 mv2 −0.014 [−0.034, 0.009], D960 mv3 +0.016 [+0.005, +0.026]. WP rho on
  D935: −0.053 [−0.096, −0.016]. S0 is behind on 3 of 4 works, significantly so on D935 (the
  only 4-bar work, where coherence is undefined), and ahead on D960 mv3, which is 47% of rows.
  Unweighted mean over works of Δ WP acc: −0.007. Per-work CIs are wide (13-43 passages), but
  "S0 matches MuQ" should be read as "on these data, on average", not "on every work".
- **The margins are generous relative to the headroom over trivial baselines.** 0.02 WP acc is
  about 38% of MuQ's gain over the performer prior (0.623 − 0.570); 0.05 WP rho is about half
  of MuQ's gain over the performer prior (0.342 − 0.237). They were fixed before any S0 result,
  so there is no drift. The data would support tighter margins: the worst lower bounds are
  −0.014 (acc) and −0.033 (rho), so the verdict holds at margins 0.015 / 0.035 and fails at
  0.01 / 0.03.
- **The headroom sentence overreaches.** "There is little room left above any of these models"
  does not follow from the split-half numbers. Half-panel vs half-panel agreement (WP acc
  0.641, WP rho 0.374) is noisy on both sides; a model is scored against the full-panel mean.
  Spearman-Brown on the half-panel WP rho gives a full-panel reliability of about 0.54, i.e. a
  noiseless predictor could reach roughly sqrt(0.54) ≈ 0.74 against the full mean, versus 0.35
  for S0 and 0.34 for MuQ. This is a rough extrapolation (Spearman treated like Pearson), but it
  points to substantial headroom, not little. What the data do show is that both models are
  at single-rater level within passages.
- The no-Score and D960-merged cells are the same models evaluated differently (or refit on
  3 works); they are not independent confirmations.

### Required fixes

None to the verdict. Text fixes for the lead (not made by the auditor beyond this section):
replace the "little room left" sentences (Ceilings and Verdict) with the headroom caveat above;
add the note-rate deviation to the Run record; add the per-work paired table.

Audit scripts (scratch, not committed): rerun of `run.py` / `features.py` with output
redirected, no-Score importance, no-note-rate refit, per-work paired differences.

## Post-audit corrections (2026-09-27)

By `ml-researcher`, applying the auditor's text fixes. No number was recomputed here; every
figure below is from the Audit section above (auditor's scratch reruns). The pre-registered
header (first 217 lines) is unchanged. In-place edits above are marked *[Corrected post-audit]*
or *[Added post-audit]*.

1. **Headroom (Ceilings and Verdict corrected in place).** The claim that little room is left
   above the models is withdrawn. Both models perform at single-rater level within passages.
   Half-panel vs half-panel agreement is not the ceiling for a model scored against the
   full-panel mean. Spearman-Brown on the half-panel WP rho (0.374) gives a full-panel
   reliability of about 0.54, so the attainable WP rho is about 0.74, versus about 0.35 for S0
   (0.350) and MuQ (0.342). This is a rough extrapolation (Spearman treated like Pearson).
2. **Note-rate deviation (Run record and Threats flagged in place).** `ctrl__even_note_rate_nps`
   and `ctrl__even_strict_note_rate_nps` were not in the pre-registered feature list. They were
   added at the coordinator's request after run 2's H3 verdict lines had been seen. The auditor
   refit S0 without them (60 features, same nested procedure). Paired Δ vs MuQ, WP acc / WP rho:

   | Variant | Δ WP acc | Δ WP rho |
   |---|---|---|
   | c, all | −0.000 [−0.009, 0.009] | +0.004 [−0.016, 0.025] |
   | c, no Score | −0.001 [−0.011, 0.010] | −0.006 [−0.034, 0.021] |
   | c3, all | −0.002 [−0.011, 0.007] | −0.002 [−0.022, 0.020] |
   | c3, no Score | +0.004 [−0.009, 0.015] | +0.008 [−0.023, 0.035] |

   Still non-inferior in all 8 cells; worst lower bounds −0.011 (acc) and −0.034 (rho). The
   deviation does not change the verdict.
3. **Per-work paired differences and margin sensitivity.** S0 − MuQ, grouping (c), paired
   passage bootstrap within each held-out work:

   | Held-out work (rows) | Δ WP acc [95% CI] | Δ WP rho [95% CI] |
   |---|---|---|
   | WoO 80 (226) | −0.008 [−0.030, 0.012] | not reported |
   | D935 no.3 (116) | −0.023 [−0.043, −0.004] | −0.053 [−0.096, −0.016] |
   | D960 mv2 (288) | −0.014 [−0.034, 0.009] | not reported |
   | D960 mv3 (559) | +0.016 [+0.005, +0.026] | not reported |

   S0 is behind on 3 of 4 works, significantly on D935 (the only 4-bar work, where coherence is
   undefined), and ahead on D960 mv3 (47% of rows). The unweighted mean over works of Δ WP acc
   is −0.007. Per-work CIs are wide (13-43 passages per work). "Non-inferior" is an average over
   passages, not a claim about every work.
   Margin sensitivity: the worst pooled lower bounds are −0.014 (acc) and −0.033 (rho), so the
   verdict holds at margins 0.015 / 0.035 and fails at 0.01 / 0.03. The pre-registered margins
   (0.02 / 0.05) were fixed before any S0 result.
4. **Headline wording (from DECISIONS 2026-09-27, verbatim):** "Averaged over passages, a
   62-feature symbolic model is non-inferior to frozen MuQ on unseen works (all 4 variants,
   margins 0.02 / 0.05). It is behind on D935's short 4-bar segments and ahead on D960 mv3.
   Both models perform at single-rater level; the full-panel ceiling is far higher (WP rho
   about 0.74 vs about 0.35)."

## Reproduction note (lead, 2026-09-28)

`artifacts/features.parquet` was built before `ShapingConfig.clip_to_train` became the default
(2026-09-27, after F-05b). To reproduce its coherence columns, run with `clip_to_train=False`;
with that flag the values match to 1e-16 (F-05d check). The F-05d minimum-length rule changes 11
timing-coherence cells, and primary metrics move only in the 3rd-4th decimal (H3 is still
supported). See `data/interim/f05d_check/` and DECISIONS 2026-09-28.
