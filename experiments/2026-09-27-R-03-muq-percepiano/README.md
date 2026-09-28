# Reproduce the frozen-MuQ baseline on PercePiano, then evaluate it honestly

Ticket: R-03    Hypothesis: H3a (reproduce the published MuQ number; prerequisite for H3)    Status: Confirmed with caveats (eval-auditor, 2026-09-27; see Audit)

Pre-registered 2026-09-27 by `ml-researcher`, before any embedding was extracted or any head
trained. Sections below "Command" were added after the runs.

## Question

1. Does a frozen MuQ-large-msd-iter + MLP head reproduce CrescendAI's R² = 0.536 (experiment A1a:
   Salamander render, their paper-era folds) when rebuilt from their code in this repo?
2. How much of that number survives (b) an inner validation split, (c) leave-work-out,
   (d) within-passage evaluation, and (e) how does it compare with individual raters?
3. Which MuQ layer carries the most linearly decodable information, when the layer is chosen on
   validation data only?

## Recipe (from CrescendAI's code at commit `d8b603fd`, not the paper text)

Checked in the repo itself, because the paper and our crescendai doc differ from the code:

| Item | Value used | Source |
|---|---|---|
| Render | Salamander C5 Light SF2, FluidSynth CLI, 44.1 kHz, gain 0.8, default reverb/chorus, then 24 kHz mono | `render_midi.py` (commit `1ec53b10`), `extractors/muq.py` (`librosa.load(sr=24000, mono=True)`). Ours: S-02 `pianolens.audio.render`, config `fc5f24d36e3e` |
| Encoder | `OpenMuQ/MuQ-large-msd-iter`, fp32, whole clip in one pass, `output_hidden_states=True` | `extractors/muq.py` |
| Layers | `torch.stack(hidden_states[9:13]).mean(0)`: 13 hidden states, indices 9-12 | `extractors/muq.py`, M1c |
| Frames | **first 1,000 frames** (40 s at 25 Hz). Our crescendai doc says 300; `BASE_CONFIG["max_frames"] = 1000` and the saved A1a/M1c configs both say 1000. 300 is run as a sensitivity check | `constants.py`, `M1c_muq_L9-12.json` |
| Pooling | masked mean ‖ std (population variance, `sqrt(var + 1e-8)`), 2,048-d | `MuQStatsModel.pool` |
| Head | Linear 2048→512, GELU, Dropout 0.2, Linear 512→512, GELU, Dropout 0.2, Linear 512→19, Sigmoid | `MuQStatsModel` |
| Training | MSE; AdamW lr 1e-4, wd 1e-5; cosine annealing T_max 200 epochs, eta_min 1e-6; grad-clip 1.0; batch 64; max 200 epochs; early stopping patience 15 on validation R²; keep the best-validation-R² checkpoint | `constants.BASE_CONFIG`, notebook `01_main_experiments.ipynb` cell 11 |
| Targets | `label_2round_mean_reg_19_with0_rm_highstd0.json`, first 19 values (0-1 scale) | notebook cell 6 |
| Metric | sklearn `r2_score(all_labels, all_preds)` on the **pooled out-of-fold** predictions of the 4 folds, uniform average over 19 dimensions. The 0.536 is this pooled number, not the fold mean (their fold R² average 0.530) | notebook cell 11, `A1a_piece_fold.json` |
| Folds | `model/data/cache/audio_fold_assignments.json` at `d8b603fd` (sha256 `fd7db652...b3ada1`): fold_0..3 = 263/234/255/269 keys + `test` 181. Train = the other three folds; "val" = the evaluated fold | `MERTDataset` |

We reimplement the head in plain PyTorch on pre-pooled features. That is exactly equivalent:
the head only sees the pooled vector, and pooling does not depend on the batch.

## Falsified if

- **H3a, reproduction.** "Reproduced" if protocol (a), L9-12, 1,000 frames, official means, gives
  a pooled out-of-fold R² whose mean over the 5 seeds lies within **±0.03 of 0.536**, i.e. in
  [0.506, 0.566]. Outside that range, the reproduction fails and that is the finding. Seed 42
  alone is reported too.
- R-03 does not test H3 itself (symbolic vs MuQ); that is R-04. R-03 fixes the MuQ side on
  identical folds and saves the out-of-fold predictions for paired comparisons.
- Pre-stated expectations (reported against, not used as H3 criteria):
  - E1: (b) is lower than (a) (selection on the test fold inflates (a)).
  - E2: (c) leave-work-out is lower than (b).
  - E3: within-passage R² is much lower than pooled R²; within-passage pairwise accuracy is
    closer to 0.5 than pooled metrics suggest.
  - E4: the model does not reach rater parity on most dimensions within passages.

## Data

- PercePiano, `data/raw/percepiano`, commit e672299, via `pianolens.data.percepiano` (D-02).
- Primary targets: `load_percepiano_official_means()` (1,189 segments, 0-1 scale).
- Sensitivity targets: de-duplicated means, `load_percepiano_ratings().mean() / 7`.
- Per-rater labels for rater parity: `load_percepiano_ratings()` (63 raters, 1-7 scale).
- Audio: S-02 renders, `data/interim/renders/salc5light2-fc5f24d36e3e/percepiano/` (1,202 files).
- Encoder weights: HF `OpenMuQ/MuQ-large-msd-iter` revision `0562a57814f6f8bbd9fdea0a25921a2fce1a841a`
  (CC BY-NC 4.0; muq package 0.1.0, transformers 4.57.6, torch 2.14.0).
- The CV folds hold 1,021 keys, of which 1,009 have official labels (CrescendAI reports
  `n_samples: 1005`, presumably after missing audio). Score renditions are included, as in theirs.
- Passage id = (work, bars, segment), i.e. one notated excerpt played by several performers.

## Splits

| Id | Split | Segments | Early stopping / selection on |
|---|---|---|---|
| (a) | CrescendAI folds 0-3 (leave-passage-out) | 1,009 | the evaluated fold itself (their protocol) |
| (b) | same folds | 1,009 | inner split: 15% of the training *passages* (grouped), seeded |
| (b-test) | train on folds 0-3, test on the `test` key set | 1,009 → 180 | inner split as (b) |
| (c) | leave-work-out, 4 works (D960 mv2, D960 mv3, D935 no.3, WoO 80) | 1,189 | inner split as (b), within training works |
| (d) | leave-performer-out, `group_kfold(performer_id, 4, seed=0)` (reported separately; never replaces (c)) | 1,189 | inner split as (b) |

Seeds 42, 123, 456, 789, 1337 for every head run (torch init, shuffling, inner split).

## Baselines and ceiling

- Trivial: predict the training-set mean of each dimension.
- Reference, not a legitimate model under a passage split: leave-one-out passage mean (predict a
  segment by the mean label of the other performances of the same passage). It shows how much R²
  passage identity alone buys.
- Ceiling: rater parity (`pianolens.eval.rater_parity`, Pearson, per dimension) against each
  rater's leave-one-rater-out panel mean, using out-of-fold predictions. Plus a within-passage
  parity: on pairs of segments of the same passage that rater j rated, compare how often rater j
  and the model order the pair like the other raters' mean does.

## Metrics

All on out-of-fold predictions, averaged over the 19 dimensions:

- pooled R² (CrescendAI's number), per-fold R², per-work R² for (c) (SST around that work's mean);
- within-passage R²: subtract each passage's mean from labels and predictions (within the
  evaluated set), then R²;
- within-passage pairwise accuracy (`pairwise_accuracy(groups=passage)`, chance 0.5) and
  within-passage Spearman (mean over passages with ≥ 3 segments);
- 95% CIs by cluster bootstrap over passages (2,000 replicates); paired bootstrap for (a) − (b).

## Method

1. `extract.py`: MuQ on MPS, fp32, whole clip. For every hidden state 0-12 and for the L9-12
   average, pooled mean ‖ std over the first 1,000 and first 300 frames. Cached to
   `artifacts/muq_pooled.npz`. Time a sample first; if the full set would take more than about
   2 h, package a `job/` folder instead (gpu-job skill).
2. `run.py`: the MLP head for (a), (b), (b-test), (c), (d) on L9-12 / 1,000 frames, official
   means; sensitivity runs: 300 frames, and de-duplicated means.
3. Layer sweep (linear probes, as the plan asks): ridge on standardised pooled features per
   hidden state 0-12 and L9-12; alpha in logspace(-1, 4, 11). Inside each outer fold of (b) and
   (c), the (layer, alpha) pair is chosen on the inner validation split; the outer fold is scored
   once with that choice. The per-layer outer table is reported as description only.
4. Rater parity and within-passage metrics on the (b) and (c) out-of-fold predictions.

## Command

```
uv run --extra torch --extra audio python experiments/2026-09-27-R-03-muq-percepiano/extract.py
uv run --extra torch --extra audio python experiments/2026-09-27-R-03-muq-percepiano/run.py
```

## Run record

- Date 2026-09-27. Git: no commit yet in this repo ("uncommitted"); code hash `230ade29f564`
  (sha256 of `src/**/*.py` + `run.py` + `extract.py`, first 12 hex, stored in `results.json`).
- Render: S-02 config `fc5f24d36e3e`, FluidSynth 2.6.1, soundfont sha256 `f0c8cb73...68fca4`.
- Extraction: 1,202 clips, MPS fp32, 592 s. Frames per clip 225-3,073 (median 707); 259 clips
  exceed 1,000 frames and are truncated.
- Heads and probes: CPU, 2,065 s wall for everything in `run.py`. Seeds 42, 123, 456, 789, 1337.
- Outputs (gitignored): `artifacts/results.json`, `oof_predictions.npz` (row ids in `pids_cv` / `pids_all_labeled`, added after the run), `per_dimension.csv`,
  `parity_*.csv`, `run.log`, `muq_pooled.npz`.
- Post-audit (2026-09-27): `postaudit.py` (imports `run.py` unchanged; no re-extraction) writes
  `artifacts/postaudit.json`, `postaudit.log`, `parity_c3_official_1000.csv` and
  `oof_predictions_postaudit.npz`. See "Post-audit corrections".

## Results

All numbers are means over 19 dimensions and over the 5 seeds, with 95% CIs from a cluster
bootstrap over passages. The target is the official means unless stated otherwise. "Within R²" =
R² after subtracting passage means. "WP pair acc" = within-passage pairwise ordering accuracy
(chance 0.5). The render is Salamander C5 Light via FluidSynth, not the Logic Pro piano the
raters heard.

### Main table (MuQ L9-12 average, 1,000 frames, MLP head)

| Protocol | n | Pooled R² | Within R² | WP pair acc | WP Spearman |
|---|---|---|---|---|---|
| Train-mean baseline, CrescendAI folds | 1,009 | -0.019 [-0.038, -0.016] | 0 | 0.500 | n/a |
| LOO passage-mean reference (uses other performers' test labels; not a legal model) | 1,009 | 0.306 [0.257, 0.348] | n/a | n/a | n/a |
| **(a) CrescendAI protocol** (selection on the evaluated fold); fold mean 0.491 (theirs 0.530)† | 1,009 | **0.509 [0.471, 0.537]** | 0.357 [0.319, 0.391] | 0.673 [0.660, 0.685] | 0.463 [0.432, 0.491] |
| (b) same folds, inner passage-grouped validation | 1,009 | 0.460 [0.417, 0.491] | 0.335 [0.299, 0.368] | 0.668 [0.655, 0.680] | 0.450 [0.418, 0.480] |
| (a) − (b), paired | | 0.049 [0.036, 0.063] | | | |
| (b-test) folds 0-3 → CrescendAI's unreported 181-key test set (train-mean baseline -0.063) | 180 | 0.525 [0.384, 0.591] | 0.410 [0.296, 0.487] | 0.685 [0.662, 0.709] | 0.485 [0.432, 0.534] |
| Train-mean baseline, leave-work-out | 1,189 | -0.142 [-0.178, -0.123] | 0 | 0.500 | n/a |
| **(c) leave-work-out** (4 works), inner validation | 1,189 | **-0.087 [-0.208, -0.000]** | 0.155 [0.102, 0.201] | 0.620 [0.609, 0.630] | 0.336 [0.308, 0.365] |
| (d) leave-performer-out (reported separately), inner validation | 1,189 | 0.478 [0.437, 0.507] | 0.126 [0.068, 0.177] | 0.618 [0.609, 0.628] | 0.327 [0.301, 0.354] |
| † Train-mean baseline, leave-work-out, D960 merged (3 works) | 1,189 | -0.070 [-0.100, -0.059] | 0 | 0.500 | n/a |
| † **(c3) leave-work-out, D960 mv2 + mv3 merged** (3 works), inner validation | 1,189 | -0.031 [-0.134, 0.047] | **0.046 [-0.033, 0.116]** | 0.618 [0.607, 0.630] | 0.334 [0.304, 0.364] |
| † (b) no Score renditions (evaluation only) | 911 | 0.404 [0.354, 0.441] | 0.173 [0.144, 0.200] | 0.636 [0.620, 0.651] | 0.357 [0.318, 0.392] |
| † Train-mean baseline, leave-work-out, no Score | 1,073 | -0.172 [-0.217, -0.149] | 0 | 0.500 | n/a |
| † (c) leave-work-out, no Score | 1,073 | -0.163 [-0.291, -0.076] | 0.063 [0.038, 0.085] | 0.590 [0.579, 0.601] | 0.249 [0.219, 0.279] |
| † Train-mean baseline, D960 merged, no Score | 1,073 | -0.096 [-0.141, -0.075] | 0 | 0.500 | n/a |
| † (c3) D960 merged, no Score | 1,073 | -0.084 [-0.185, -0.015] | 0.068 [0.044, 0.090] | 0.586 [0.574, 0.599] | 0.241 [0.211, 0.274] |

† Added after the audit (2026-09-27); see "Post-audit corrections". "No Score" drops the deadpan
`Score`/`Score2` renditions from scoring only (98 of the 1,009 CV segments, 116 of the 1,189);
the models and predictions are the same.

Per-seed pooled R², protocol (a): 0.516 (seed 42), 0.503, 0.512, 0.505, 0.510; two of the five
seeds (0.503, 0.505) fall below the band floor of 0.506 on their own (post-audit note). Per-fold (a),
seed mean: 0.467 / 0.508 / 0.543 / 0.445 (CrescendAI: 0.513 / 0.543 / 0.483 / 0.580). Fold mean
0.491 against CrescendAI's 0.530, a gap of 0.039, outside ±0.03 (post-audit note). Median
best epoch: 99 in (a), 72.5 in (b).

### (c) leave-work-out, per work

| Held-out work | n | Pooled R² (SST around that work's mean) | Train-mean R² | Within R² | WP pair acc | WP Spearman |
|---|---|---|---|---|---|---|
| Beethoven WoO 80 | 226 | 0.105 [-0.135, 0.200] | -0.174 | 0.226 [0.133, 0.297] | 0.623 [0.596, 0.647] | 0.315 |
| Schubert D935 no.3 | 116 | 0.400 [0.282, 0.435] | -0.083 | 0.479 [0.431, 0.520] | 0.737 [0.713, 0.759] | 0.577 |
| Schubert D960 mv2 | 288 | -0.364 [-0.597, -0.240] | -0.575 | -0.045 [-0.121, 0.011] | 0.637 [0.624, 0.651] | 0.371 |
| Schubert D960 mv3 | 559 | -1.203 [-1.640, -1.034] | -0.615 | -0.030 [-0.081, 0.015] | 0.594 [0.579, 0.607] | 0.249 |

On the two D960 movements the model gets the within-passage *order* partly right (0.59-0.64) but
the within-passage *spread* wrong (within R² ≤ 0), and it misplaces the work's overall level so
badly that it does worse than predicting the other works' mean.

### Sensitivity

| Variant | (a) pooled R² | (b) pooled R² | (c) pooled R² | (c) WP pair acc |
|---|---|---|---|---|
| Primary: official means, 1,000 frames | 0.509 | 0.460 | -0.087 | 0.620 |
| De-duplicated means | 0.507 [0.469, 0.535] | 0.458 [0.414, 0.489] | -0.102 [-0.228, -0.014] | 0.621 |
| 300 frames (as our crescendai doc said) | 0.484 [0.444, 0.516] | 0.439 [0.394, 0.474] | not run | not run |
| (d) with de-duplicated means | | | | 0.619 (pooled R² 0.481) |

The target choice changes nothing. Truncating at 300 frames costs about 0.02-0.025.

### Layer sweep (ridge linear probes, layer and alpha chosen on inner validation)

| Split | Selected-probe pooled R² | Within R² | WP pair acc | Layers chosen per outer fold |
|---|---|---|---|---|
| (b) CrescendAI folds | 0.485 [0.440, 0.517] | 0.348 [0.311, 0.381] | 0.673 [0.660, 0.684] | 8, 4, 9, 11 |
| (c) leave-work-out | -0.292 [-0.459, -0.174] | 0.127 [0.071, 0.176] | 0.615 [0.605, 0.625] | 12, L9-12, 9, 9 |

Descriptive only (not used for selection): outer pooled R² per hidden state 0..12, then L9-12,
under (b): 0.377, 0.410, 0.435, 0.453, 0.464, 0.464, 0.477, 0.480, 0.470, 0.490, 0.482, 0.490,
0.469, 0.487. The curve rises to about layer 6 and is flat after that; no single layer stands
out. Within-passage accuracy per layer runs 0.651 (layer 0) to 0.677 (layer 4), again flat after
the first few layers. A linear probe does as well as the MLP under (b) (0.485 vs 0.460) and worse
under (c) (-0.29 vs -0.09).

### Rater parity (out-of-fold predictions averaged over the 5 seeds)

Pearson with each rater's leave-one-rater-out panel mean, per dimension; then the mean over 19
dimensions. Counts give the number of dimensions where the 95% CI of (model − rater), bootstrapped
over raters, is above 0, below 0, or includes 0.

| Split | Rater r | Model r | Model above / tied / below | WP pair acc, rater | WP pair acc, model | Model above / tied / below |
|---|---|---|---|---|---|---|
| (b) CrescendAI folds | 0.449 | 0.665 | 17 / 2 / 0 | 0.593 | 0.673 | 17 / 2 / 0 |
| (c) leave-work-out | 0.454 | 0.434 | 10 / 4 / 5 | 0.590 | 0.631 | 13 / 4 / 2 |
| † (c3) leave-work-out, D960 merged | 0.454 | 0.467 | 11 / 1 / 7 | 0.590 | 0.630 | 12 / 5 / 2 |

† Added after the audit. Parity uses the seed-ensembled prediction (mean over the 5 seeds), which
is slightly stronger than the seed-averaged metrics in the main table: (c) pooled R² -0.059 vs
-0.087, WP pair acc 0.623 vs 0.620. Within-passage parity scores a rater's tied pair as 0.5; see
"Post-audit corrections" for the untied-pair bracket. Under leave-work-out the model **roughly
matches** a single rater; it does not clearly beat one.

Under leave-work-out the model falls below a typical single rater on pedal (both items),
brightness, dynamic range and mood valence. Valence is the extreme case: model r = -0.21 against
rater r = 0.58. It stays above a single rater on articulation, timbre richness and colour,
"honest/imaginative", balance and interpretation. Per-dimension tables are in `parity_*.csv` and
`per_dimension.csv`.

## Verdict (Provisional)

- **H3a reproduction: reproduced, at the low edge.** Protocol (a) gives a pooled R² of 0.509 (seed
  mean; seed 42: 0.516). That is inside the pre-registered band [0.506, 0.566] but 0.027 below
  CrescendAI's 0.536. The per-fold pattern differs from theirs (their fold 3 is best at 0.580;
  ours is worst at 0.445), so the match is in the total, not fold by fold.
- **E1 (b < a): supported.** Choosing the checkpoint on the evaluated fold inflates R² by 0.049
  [0.036, 0.063]. The honest number on CrescendAI's own folds is 0.460.
- **E2 (c < b): supported, strongly.** Leave-work-out pooled R² is -0.087, barely above the
  train-mean baseline (-0.142) and below 0. Almost all of the published R² comes from passages of
  works that were also in training. Per-work R² ranges from 0.40 (D935) to -1.20 (D960 mv3).
- **E3 (within-passage much weaker): supported.** Under the passage split, within-passage R² is
  0.335 against 0.460 pooled, and pairwise accuracy is 0.668. Under leave-work-out: 0.155 and
  0.620.
- **E4 (no rater parity within passages): not supported on CrescendAI's folds; borderline under
  leave-work-out** (corrected after the audit). Under the passage split the model orders
  same-passage performances in agreement with the other raters' mean more often than a single
  rater does (17/19 dimensions). Under leave-work-out it roughly matches a single rater: 0.631 vs
  0.590 with rater ties scored 0.5, but 0.639 vs 0.623 on pairs the rater did not tie, and
  0.610 vs 0.599 on those pairs without Score renditions. Parity uses seed-ensembled predictions.

What this means for H3 (R-04): the number the symbolic model has to meet is not 0.536. On the
leave-work-out split the plan requires, frozen MuQ gets a pooled R² below 0, a within-passage R²
of 0.155 and a within-passage pairwise accuracy of 0.620. R-04 should be judged on the same folds
(`oof_predictions.npz` holds the per-segment MuQ predictions for paired tests). Post-audit: the
within-passage R² drops to 0.046 with D960 merged and to 0.063 without Score renditions, while WP
pair accuracy stays at 0.59-0.62; the merged and no-Score predictions are in
`oof_predictions_postaudit.npz`.

## Threats to validity

- **Renderer.** Our FluidSynth (2.6.1) defaults may differ from CrescendAI's unrecorded version
  (reverb/chorus parameters changed across 2.x). That may explain part of the 0.027 gap and the
  different fold pattern. Neither piano is the Logic Pro piano the raters heard, so the timbre
  dimensions are learned from a sound the raters never heard.
- **Rater parity is a loose ceiling here.** Single raters are noisy (R-01: within-rater
  test-retest median 0.52), and the model is trained on panel means, so beating one rater is a
  low bar. A panel-level ceiling (split-half reliability of the mean) would be tighter. Parity
  under the passage split also still rewards knowing the work.
- **Few groups.** Leave-work-out has 4 groups of very different sizes (116-559), and D960 mv3 is
  47% of the data. Pooled leave-work-out R² is dominated by the between-work offset. The CIs
  resample passages, not works, so they understate uncertainty about new works.
- **Leave-performer-out** ((d)): the same passage appears in several folds, so within-passage
  pairs mix predictions from different fold models. That is why the train-mean baseline's
  within-passage accuracy is 0.44, not 0.5. Read (d)'s within-passage numbers with that in mind.
- **Selection.** Everything reported under (b), (c), (d) and the probes was chosen on inner
  validation. (a) intentionally reproduces selection on the evaluated fold.
- **Head reimplementation.** Plain PyTorch, not Lightning. Same architecture, optimiser,
  schedule, clipping, patience and checkpoint rule. The Lightning sanity-check pass and the
  data-loader worker seeding are not reproduced.
- **n.** 1,009 CV segments vs CrescendAI's reported 1,005 (they are likely missing 4 audio files;
  one PercePiano file name starts with a space).
- Score renditions (deadpan `Score`/`Score2`, 129 segments) are included, as in CrescendAI. They
  may be easy to rank within a passage.

## Audit (2026-09-27)

Auditor: `eval-auditor`. Verdict: **Confirmed with caveats.** Every headline number reproduces
exactly from the recorded code and cached embeddings, the splits are clean, and no scaler or
selection step touches a test fold except where protocol (a) does so by design. Three caveats
change how the leave-work-out numbers should be read and used as the R-04 target (findings 2-4).
Audit scripts and outputs are in the auditor's scratchpad, not in the repo; the numbers below
come from them.

### What was checked

| Check | Result |
|---|---|
| Pre-registration (no git; checked against the ml-researcher transcript) | README written in one `Write` at 23:34:05 UTC; `extract.py` first ran at 23:34:25, `run.py` at 23:44:37. Everything from the title to "Command" in the current file is identical to that write; "Falsified if" is byte-identical. Results were appended at 00:26:44. |
| Fold file | sha256 `fd7db652...b3ada1`; byte-identical to CrescendAI's paper-era `audio_folds.json` (d8b603fd). Sizes 263/234/255/269 + test 181. 99 passages; 0 straddle folds (independent rebuild). `check_disjoint` passes for passages in (a)/(b) and for works and passages in (c). |
| CrescendAI's 0.536 is pooled | Yes. Their notebook cell 11 concatenates `all_preds` over the 4 folds; `A1a_piece_fold.json` has `overall_r2` 0.5360 while its fold R² average 0.530. |
| Rerun (`run.py` functions imported unchanged; (a), (b), (c) primary, 5 seeds) | **Exact match to 4 decimals** for pooled, within R², WP pair acc, WP Spearman, CIs, per-seed and per-fold R²: (a) 0.5091 [0.4714, 0.5366]; (b) 0.4599; (c) -0.0865 [-0.2083, -0.0003], within R² 0.1548, WP acc 0.6195, per-work 0.1045 / 0.3999 / -0.3637 / -1.2029. Wall time 70 s, 46 s, 118 s. |
| Leakage: scalers and selection | The MLP has no feature scaler; targets are not rescaled. Ridge standardisation is fit on the inner-train rows for selection and on the outer-train rows for the refit. Layer and alpha are chosen on inner validation. The L9-12 layer, 1,000 frames and official targets were fixed before the run, and the 300-frame and de-duplicated variants are all reported. (a) early-stops on the evaluated fold, which is CrescendAI's protocol and is labelled as such. |
| Within-passage metrics | Definition is correct. Labels and predictions are each centred on their own passage mean within the evaluated set. Passages are nested in folds for (a), (b) and (c), so each passage's predictions come from one model. Centring labels on test labels is part of the metric's definition, not an input to the model. The vectorised metrics equal `pianolens.eval` on random data (`selfcheck`). |
| LOO passage-mean reference | Labelled "uses other performers' test labels; not a legal model". It is not used as a baseline in any verdict line, in `EXPERIMENTS.md` or in the R-04 targets. Its within-passage columns are correctly left as n/a (by construction it orders same-passage pairs backwards: WP acc 0.0). |
| Pooled vs fold mean | Pooled is reported (matches CrescendAI), and per-fold values are listed, but the fold mean is not. (a) fold mean **0.491** vs CrescendAI's 0.530 (gap 0.039). (c) mean of per-work R² is **-0.266**. |
| Bootstrap unit | Passages (99; 83 in the CV folds), 2,000 replicates; paired for (a) − (b). Right unit for within-passage metrics. For (c) it understates uncertainty about new works (4 works); the README already says so. |
| Rater parity semantics | Pearson parity calls `pianolens.eval.rater_parity` directly: the held-out rater vs the mean of the *other* raters, and the model vs the same target on the same segments, with CIs over raters. The within-passage version uses the same `loo_means` target. Correct. |
| Render determinism | 8 PercePiano MIDIs (3 clipped, 5 random) re-rendered with FluidSynth 2.6.1: all 8 WAV sha256 equal to `manifest.csv`, max abs sample diff 0.0. |
| The 8 clipping clips | All 8 are deadpan `Score`/`Score2` renditions (7 labelled). Peaks 1.008-1.178; 5-8 samples per million are at full scale. Dropping the 7 labelled clips: (a) 0.509 → 0.504, (c) WP acc 0.620 → 0.617, (c) within R² 0.155 → 0.139. The shifts come from removing those segments, not from the clipping itself. Immaterial. |

### Findings on the claims

1. **(a) Reproduction: holds by the pre-registered rule, but the margin is thin.** The seed mean
   of 0.509 is 0.003 above the band floor. Two of the five seeds (0.503, 0.505) fall below it on
   their own. The fold pattern does not reproduce: ours 0.467/0.508/0.543/0.445 against theirs
   0.513/0.543/0.483/0.580, with fold 3 off by 0.135. On fold means the gap is 0.039, outside
   ±0.03. "Reproduced in total, not fold by fold" is the accurate statement, and the README says
   so. The likeliest cause is the render (FluidSynth version and defaults), which cannot be
   checked because the renders are gone.
2. **(b) The 0.049 [0.036, 0.063] inflation reproduces exactly and is paired correctly.** It is
   well supported.
3. **(c) Leave-work-out: numbers exact. The within-passage R² depends on how works are grouped.**
   D960 mv2 and mv3 are movements of one sonata. They share all 12 human performers (plus the deadpan Score rendition), and both
   use 8- and 16-bar passages. Treating them as one work (3 folds; Beethoven and D935 folds
   unchanged):

   | Grouping | Pooled R² | Train-mean | Within R² | WP pair acc | WP Spearman |
   |---|---|---|---|---|---|
   | 4 works (reported) | -0.087 [-0.208, -0.000] | -0.142 | 0.155 [0.102, 0.201] | 0.620 [0.609, 0.630] | 0.336 |
   | D960 merged (3 works) | -0.031 [-0.134, 0.047] | -0.070 | **0.046 [-0.033, 0.116]** | 0.618 [0.607, 0.630] | 0.334 |

   With the whole sonata held out, D960 within R² is -0.25 (mv2 -0.11, mv3 -0.39), while its WP
   pair accuracy stays at 0.61. Pooled R² per seed ranges from -0.17 to +0.05. So:
   - "pooled R² ≈ 0 or below" holds under both groupings;
   - WP pair accuracy (and WP Spearman) is robust at about 0.62;
   - **within-passage R² is not robust** (0.155 vs 0.046). Its CI under merging includes 0.

   The 4-work grouping is defensible: it matches `piece_id` and the DECISIONS entry. But the
   stricter grouping, one sonata, is closer to hard rule 1. R-04 should report both groupings
   and treat WP pair accuracy and WP Spearman as the co-primary within-passage metrics.
4. **Deadpan `Score` renditions carry much of the within-passage signal.** These are 116 of the
   1,189 labelled segments. Excluding them from evaluation only (same OOF predictions):

   | Protocol | Pooled R² | Within R² | WP pair acc |
   |---|---|---|---|
   | (b) all / no Score | 0.460 / 0.404 [0.357, 0.439] | 0.335 / **0.173** [0.144, 0.198] | 0.668 / 0.636 [0.620, 0.650] |
   | (c) all / no Score | -0.087 / -0.163 [-0.291, -0.077] | 0.155 / **0.063** [0.038, 0.084] | 0.620 / **0.590** [0.579, 0.601] |

   About 60% of the leave-work-out within R² comes from telling deadpan renditions apart from
   human performances. A symbolic model can detect deadpan MIDI almost trivially (quantised
   timing, flat velocity), so the R-04 comparison must also be made **without Score
   renditions**. Otherwise a trivial deadpan detector gets partial credit. For reference, a
   legal "deadpan indicator" baseline (the training-set within-passage offset for Score vs
   human) reaches WP pair acc 0.541 under (c) by itself.
5. **Performer overlap across works does not explain MuQ's within-passage accuracy.** Under (c),
   Schubert performers appear in both train and test (no Schubert work can be held out
   performer-clean), and Score/Score2 appear in every work. I checked this with a legal
   performer-prior baseline: each test segment's performer's passage-centred mean over the
   *training* works. It reaches WP pair acc 0.570 and within R² 0.080, against MuQ's 0.620 and
   0.155. On the one performer-disjoint fold (Beethoven: its 12 performers play no Schubert),
   MuQ still gets 0.623. So performer leakage adds at most a little. The performer-prior
   baseline is worth adding to R-04's table, because a symbolic model could learn performer
   style too.
6. **(d) Rater parity: "beats a single rater on their folds" is fair; under leave-work-out
   "roughly matches" is the accurate wording, not "beats".**
   - The within-passage parity scores a rater's tied pair (same integer rating) as 0.5. That is
     28% of a rater's same-passage pairs, which caps a single rater's accuracy.
   - On pairs the rater did not tie, the gaps shrink:

     | Protocol | Ties scored 0.5: rater / model | Rater-untied pairs: rater / model | Untied, no Score: rater / model |
     |---|---|---|---|
     | (b) | 0.593 / 0.673 | 0.626 / 0.682 (17/19 dims model ahead) | 0.602 / 0.648 |
     | (c) | 0.590 / 0.631 | **0.623 / 0.639** (12/19 dims) | **0.599 / 0.610** |

     Restricting to untied pairs favours the rater (the pairs are selected on the rater), so the
     truth lies between the two columns.
   - Pearson parity under (c) is 0.434 model vs 0.454 rater, with 10 dims above, 4 tied and 5
     below. That is "roughly matches".
   - Parity uses the seed-ensembled prediction (mean over 5 seeds), which is slightly stronger
     than the seed-averaged metrics in the main table: pooled (c) -0.059 vs -0.087, WP acc
     0.623 vs 0.620. This should be stated.
   - E4's "not supported" stands for (b). For (c) it is borderline.
7. **Minor.** In (c) the inner validation split holds out passages *within* the training works,
   so early stopping optimises within-work generalisation, not new-work generalisation. That is
   not leakage, but a work-grouped inner split (leave-one-training-work-out) would match the
   outer question and is worth trying in R-04. (d)'s within-passage numbers mix fold models, as
   the README says. The train-mean within-passage acc of 0.44 is the symptom.

### Required changes (reporting only; no rerun needed)

1. Add the fold-mean R² for (a) (0.491 vs their 0.530) next to the pooled number, and note that
   2 of 5 seeds fall below the band.
2. Add the D960-merged leave-work-out row (finding 3). State that within R² is not robust to the
   grouping, and that WP pair accuracy and WP Spearman are.
3. Add the no-Score rows (finding 4). The R-04 "numbers to beat" in `WORKBOARD.md` should list
   both variants: all segments (-0.087 / 0.155 / 0.620) and no Score (-0.163 / 0.063 / 0.590).
   Add the D960-merged variant too. This is a lead edit.
4. Reword the rater-parity claim for (c) to "roughly matches a single rater". Note the tie
   handling and that parity uses seed-ensembled predictions.

With these, the verdict is **Confirmed with caveats**: H3a reproduced (thin margin, in total not
per fold); E1 and E2 supported; E3 supported, with within R² sensitive to grouping and to Score
renditions; E4 not supported on CrescendAI's folds and borderline under leave-work-out.

## Post-audit corrections (2026-09-27)

By `ml-researcher`, applying the four required changes above. Reporting only: no MuQ
re-extraction, no change to `run.py` or to any number in the pre-registration or the Audit.
`postaudit.py` imports `run.py` unchanged and reads the cached `muq_pooled.npz` and
`oof_predictions.npz`. Only the D960-merged variant needed new head training (5 seeds, same recipe
and inner-split rule as (c)). CPU, 378 s. Outputs: `artifacts/postaudit.json`, `postaudit.log`,
`parity_c3_official_1000.csv`, `oof_predictions_postaudit.npz`. Rows added to the results tables
are marked †.

```
uv run --extra torch --extra audio python experiments/2026-09-27-R-03-muq-percepiano/postaudit.py
```

### 1. Fold-mean R² for (a)

| | Pooled OOF R² | Fold mean R² |
|---|---|---|
| Ours, (a), seed mean | 0.509 | **0.491** (per seed 0.497, 0.486, 0.494, 0.486, 0.492) |
| CrescendAI A1a | 0.536 | 0.530 |

The pre-registered rule is on the pooled number, which is inside the band [0.506, 0.566] by 0.003.
Two of the five seeds (0.503, 0.505) are below the band on their own. On fold means the gap is
0.039, outside ±0.03. So H3a is reproduced in total by the pre-registered rule, with a thin margin,
and not fold by fold.

### 2. D960 mv2 + mv3 merged into one work (3 folds)

| Grouping | Train-mean pooled R² | Pooled R² | Within R² | WP pair acc | WP Spearman |
|---|---|---|---|---|---|
| 4 works (as run) | -0.142 | -0.087 [-0.208, -0.000] | 0.155 [0.102, 0.201] | 0.620 [0.609, 0.630] | 0.336 [0.308, 0.365] |
| D960 merged (3 works) | -0.070 | -0.031 [-0.134, 0.047] | 0.046 [-0.033, 0.116] | 0.618 [0.607, 0.630] | 0.334 [0.304, 0.364] |

My retrain reproduces the auditor's merged numbers to 3 decimals. Pooled R² per seed:
-0.113, 0.033, -0.171, 0.047, 0.048. With the whole sonata held out, D960 (n = 847) has pooled R²
-0.335 (train-mean -0.113), within R² -0.247 and WP pair acc 0.606. Beethoven and D935 are
unchanged from the 4-work run.

**Within-passage R² is not robust to how works are grouped** (0.155 vs 0.046; the merged CI
includes 0). **WP pair accuracy and WP Spearman are robust** (0.620 / 0.618 and 0.336 / 0.334).
Following the DECISIONS entry, a claim stands only if it holds under both groupings.

### 3. Without deadpan Score renditions (evaluation only)

Same out-of-fold predictions; the 98 (CV) / 116 (all labelled) `Score`/`Score2` rows are dropped
from scoring.

| Protocol | Pooled R² | Within R² | WP pair acc | WP Spearman |
|---|---|---|---|---|
| (b) all / no Score | 0.460 / 0.404 [0.354, 0.441] | 0.335 / 0.173 [0.144, 0.200] | 0.668 / 0.636 [0.620, 0.651] | 0.450 / 0.357 |
| (c) all / no Score | -0.087 / -0.163 [-0.291, -0.076] | 0.155 / 0.063 [0.038, 0.085] | 0.620 / 0.590 [0.579, 0.601] | 0.336 / 0.249 |
| (c3) D960 merged, all / no Score | -0.031 / -0.084 [-0.185, -0.015] | 0.046 / 0.068 [0.044, 0.090] | 0.618 / 0.586 [0.574, 0.599] | 0.334 / 0.241 |
| Train-mean, (c) / (c3), no Score | -0.172 / -0.096 | 0 | 0.500 | n/a |

The (b) and (c) no-Score numbers match the auditor's exactly. About 60% of the leave-work-out
within R² comes from telling deadpan renditions apart from human ones. Without them, MuQ's
leave-work-out WP pair accuracy is 0.586-0.590 under both groupings.

### 4. Rater parity, reworded

- **Under leave-work-out, frozen MuQ roughly matches a single rater within passages; it does not
  clearly beat one.** On CrescendAI's folds ((b)) it does beat a single rater (17/19 dimensions).
- **Tie handling.** Within-passage parity scores a pair the held-out rater tied (same integer
  rating) as 0.5. That caps a single rater's accuracy. The auditor measured 28% of a rater's
  same-passage pairs as ties; my count over pairs with an untied target is 31%. Restricting to
  pairs the rater did not tie favours the rater, because the pairs are selected on the rater, so
  the truth lies between the two columns:

  | Protocol | Ties scored 0.5: rater / model | Rater-untied pairs: rater / model | Untied, no Score: rater / model |
  |---|---|---|---|
  | (b) | 0.593 / 0.673 | 0.626 / 0.682 (17/19 dims model ahead) | 0.602 / 0.648 |
  | (c) | 0.590 / 0.631 | 0.623 / 0.639 (12/19 dims) | 0.599 / 0.610 |
  | (c3) D960 merged (recomputed here) | 0.590 / 0.630 | 0.627 / 0.636 (13/19 dims) | 0.604 / 0.605 (10/19 dims) |

  The (b) and (c) rows are the auditor's. My recomputation (`postaudit.json`, `wp_parity`)
  averages per-rater accuracies slightly differently and gives 0.628 / 0.683 and 0.627 / 0.639
  on untied pairs, and 0.604 / 0.648 and 0.604 / 0.611 without Score. The conclusion is the same.
  (c3) uses my recomputation.
- Pearson parity under (c): model 0.434 vs rater 0.454; 10 dims above, 4 tied, 5 below. Under
  (c3): 0.467 vs 0.454; 11 above, 1 tied, 7 below. Both read as "roughly matches".
- **Parity uses seed-ensembled predictions** (the mean over the 5 seeds). These are slightly
  stronger than the seed-averaged metrics in the main table:

  | Protocol | Pooled R², seed-averaged / ensembled | WP pair acc, seed-averaged / ensembled |
  |---|---|---|
  | (b) | 0.460 / 0.479 | 0.668 / 0.670 |
  | (c) | -0.087 / -0.059 | 0.620 / 0.623 |
  | (c3) | -0.031 / 0.017 | 0.618 / 0.619 |

- E4 ("the model does not reach rater parity within passages"): not supported on CrescendAI's
  folds; borderline under leave-work-out, under both groupings.

### Out-of-fold predictions for R-04

`artifacts/oof_predictions_postaudit.npz` (float32, shape (rows, 5 seeds, 19), seeds as in
`SEEDS`):

| Key | Rows (ids) |
|---|---|
| `c3_official_1000` | `pids_all_labeled` (1,189; same order as `oof_predictions.npz`); fold per row in `work_c3`, fold names in `works_c3` |
| `b_official_1000_noscore` | `pids_cv_noscore` (911) |
| `c_official_1000_noscore` | `pids_all_labeled_noscore` (1,073) |
| `c3_official_1000_noscore` | `pids_all_labeled_noscore` (1,073) |
| `noscore_mask_cv`, `noscore_mask_all_labeled` | boolean masks over `pids_cv` / `pids_all_labeled` |

The no-Score arrays are row subsets of the original predictions, not new models.

### Verdict after corrections

Confirmed with caveats, as the audit states: H3a reproduced by the pre-registered rule (thin margin,
in total, not per fold); E1 and E2 supported; E3 supported, with within-passage R² sensitive to the
work grouping and to Score renditions; E4 not supported on CrescendAI's folds and borderline under
leave-work-out. The MuQ numbers R-04 must meet under leave-work-out (pooled R² / within R² / WP
pair acc): all segments -0.087 / 0.155 / 0.620; no Score -0.163 / 0.063 / 0.590; D960 merged
-0.031 / 0.046 / 0.618; D960 merged, no Score -0.084 / 0.068 / 0.586.
