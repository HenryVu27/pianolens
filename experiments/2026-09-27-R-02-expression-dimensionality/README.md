# Dimensionality of expert expression (PianoCoRe tier A)
Ticket: R-02    Hypothesis: H1    Status: Provisional

Pre-registered 2026-09-27, before any curve was extracted or any PCA was run. Sections below
"Results" were added afterwards.

## Question

Across expert performances of one piece, how many components does it take to describe how the
performances differ in phrase-level tempo and dynamics? Is that number small in absolute terms
(plan: at most 10 for 80% of variance) and small relative to a null with the same smoothness and
variance but no shared structure?

## Falsified if

Plan H1 row: "at most 10 components explain at least 80% of variance in normalized per-beat tempo +
velocity curves" on most pieces; falsified if "more than 20 components are needed for 80% on most
pieces". Refined here (fixed before results):

- Unit of analysis: a piece. "Most pieces" = more than 50% of the analysed pieces.
- Primary block: **joint smooth tempo + smooth velocity** (definition below), **n = 50 performances
  per piece** (fixed random subsample, seed 0), so every piece has the same n and the same upper
  bound on the component count (49).
- Statistics per piece:
  - `k80_in`: smallest k whose in-sample cumulative explained variance is at least 0.80 (plan's
    literal criterion).
  - `k80_ho`: smallest k (1..20) at which held-out reconstruction R² reaches 0.80 (5 random 80/20
    splits of performances, R² pooled over held-out performances, averaged over splits); "> 20"
    if it never does.
  - Null: the same counts for phase-randomized surrogates (below).
- **Supported** if all three hold: `k80_in` ≤ 10 on most pieces; `k80_ho` ≤ 10 on most pieces;
  `k80_in` is smaller than the phase-randomized null's `k80_in` on most pieces.
- **Falsified** if `k80_in` > 20 on most pieces (the plan's criterion).
- **Partly supported / inconclusive** otherwise; the report says which part failed.
- Tempo-only, velocity-only, raw per-beat velocity and residual timing blocks, and the
  all-performances analysis are reported with the same statistics but do not decide the verdict.

## Data

- PianoCoRe tier A cache (D-07, `data/processed/pianocore_A`, reader
  `pianolens.data.pianocore_cache`; Zenodo 19186016 v1.0). Rows with label `match` only
  (`interpolated`, insertion, deletion excluded; grace notes excluded).
- Pieces with at least 50 tier A performances: 730. Within a piece only performances of the
  majority `score_id` are used (some pieces have a "mini" and a full refined score whose beat
  grids differ). A piece enters the primary analysis if at least 50 performances pass QC.
- Transcription-noise controls: the 978 Disklavier (ASAP) rows of tier A (pieces with at least 8
  Disklavier performances on the majority score), and Vienna 4x22 (`pianolens.data.vienna4x22`,
  22 sensor performances x 4 excerpts, ground-truth match files).

## Curves (per performance)

- Positions and tempo: `pianolens.features.tempo_from_onsets(s_onset_beat, p_onset_sec,
  beats_per_bar=median s_ts_beats)` with the F-03 defaults (1.5-bar half-gain cutoff,
  robust P-spline, pauses as gaps, steps reported not split, no score markings: the cache has no
  partitura part). Beats are score beats (time-signature denominator units).
- **Smooth tempo** `T[i, b]`: `tempo_log_ratio` on the integer-beat grid (log of own geometric-mean
  beat period over local beat period; zero mean per performance), re-centered to zero mean over the
  retained beats.
- **Raw per-beat velocity** `V[i, b]`: mean MIDI velocity of the matched notes whose score onset is
  in [b, b+1), centered per performance (subtract the performance's mean over retained beats;
  MIDI units, not scaled). Z-scored velocity is a sensitivity check.
- **Smooth velocity**: the raw per-beat velocity, linearly interpolated over beats without an
  observed value, then Whittaker-smoothed (order-3 difference penalty, lambda = (P / 2 pi)^6 with
  P = 1.5 bars in beats: half gain at the same period as the tempo curve).
- **Residual timing** `R[i, j]`: F-03 `dev_beats` (onset minus smooth time map, in beats) per score
  position j (distinct onset), centered per performance.
- **Joint block**: `[T / s_T, V_smooth / s_V]`, where `s_T`, `s_V` are the root mean total
  variance of each column-centered block in that piece, so each block carries half the variance.

## Missing data

- Tempo: a beat is observed in a performance if a non-outlier matched position lies within one bar
  of it. Beats unobserved in more than 10% of performances are dropped (this mostly trims the
  edges); then performances unobserved on more than 10% of the remaining beats are dropped. The
  remaining gaps are filled by the P-spline itself (it is defined over the whole span); beats
  outside a performance's span take the nearest edge value.
- Raw velocity: only beats with at least one score onset count. Same 10% / 10% rule; remaining
  gaps are linearly interpolated within the performance.
- Residual timing: positions unobserved (unmatched or outlier) in more than 20% of performances
  are dropped, performances with more than 20% missing positions are dropped, remaining gaps take
  the position's mean over performances.
- Counts of dropped beats / positions / performances are reported per piece.

## Analyses

1. **Per piece PCA** on each block (column-centered; SVD). Report `k80_in`, `k90_in`, PC1 share,
   the scree, and the share of per-performance variance carried by the mean curve
   (1 - sum of squares after column centering / before).
   "Functional PCA": the tempo curves are pre-smoothed by the P-spline and the velocity curves by
   the Whittaker smoother, so PCA on them is FPCA with pre-smoothing (Ramsay and Silverman 2005,
   ch. 8 approach of smoothing the data first). Sensitivity: an extra Whittaker smoothing to a
   3-bar cutoff, to show how the count depends on the smoothing.
2. **Across pieces**: median, IQR of the counts; vs number of beats (tertiles) and number of
   performances (all-performances analysis, bins). Counts are bounded by min(n - 1, p); the ratio
   k80 / min(n - 1, p) is reported too.
   **Nulls**, each run through the same PCA:
   - phase-randomized (primary null): each performance's deviation from the piece mean curve
     gets independent random Fourier phases (same phases for its tempo and velocity blocks, so
     the within-performance tempo-velocity coupling and each curve's spectrum and variance are
     kept; the structure shared across performances is destroyed);
   - column-shuffled: each beat's values permuted independently across performances;
   - white noise with the per-beat variance of the data;
   - smooth noise: white noise through the same 1.5-bar Whittaker smoother, scaled to the data's
     per-beat variance (for the smooth blocks).
3. **Held-out reconstruction**: fit PCA (mean + components) on a random 80% of performances,
   reconstruct the held-out 20% with k = 1..20 components; R² = 1 - SSE / SS about the training
   mean. 5 splits, seeds 0-4. Also run on the phase-randomized null.
4. **Transcription-noise control**:
   - Disklavier vs transcribed at matched n, same piece: pieces with d >= 8 Disklavier
     performances (majority score). In-sample `k80`, PC1 share and leave-one-out reconstruction
     R² at k = 1..3 for the d Disklavier performances vs the median over 50 random subsamples of d
     transcribed performances. Paired Wilcoxon over pieces, bootstrap CI of the median difference
     (pieces resampled).
   - Vienna 4x22 (n = 22 per excerpt, ground-truth alignments, `sensor`) vs 50 random subsamples
     of 22 transcribed PianoCoRe performances of the same bars (score beats mapped by matching
     score notes), for the excerpts present in tier A.
   - If Disklavier/sensor curves have clearly lower dimensionality than transcribed ones at matched
     n, transcription noise inflates the PianoCoRe counts and the verdict carries that caveat.
5. **Interpretability**: Chopin Op. 10 No. 3 and Op. 9 No. 2 (all performances): mean curve and
   PC1-PC3 loadings (tempo, velocity) against bar lines. Figures in `artifacts/figures/`.

## Splits

Not a prediction task, so no leave-piece-out. Held-out performances within a piece (5 seeds).
Performance subsample seed 0. Surrogate seeds 0.

## Baselines

The nulls above are the baselines: "low-dimensional" is judged relative to curves with the same
smoothness and variance and no shared structure. Bootstrap 95% CIs (pieces resampled, 2,000
resamples, seed 0) on the medians and on the fraction of pieces meeting each criterion.

## Method

Code: `experiments/2026-09-27-R-02-expression-dimensionality/curves.py` (curve extraction, cached
per piece to `artifacts/curves/`), `analyze.py` (PCA, held-out, nulls, controls, figures).
Reusable pieces: `pianolens.eval.dimensionality`.

## Command

```
uv run python experiments/2026-09-27-R-02-expression-dimensionality/curves.py --workers 13
uv run python experiments/2026-09-27-R-02-expression-dimensionality/analyze.py --workers 13
```

## Amendments (before the full run; after looking at Op. 10 No. 3 and an 8-piece dry run)

These were added after seeing the first results on 9 pieces, so they are **exploratory** and do not
enter the verdict. The pre-registered statistics, blocks and verdict rule above are unchanged.

- Held-out R² is also computed for k = 21..40 (`k80_ho_ext`, "> 40" if never reached). Reason:
  on the first pieces held-out R² stayed below 0.8 at k = 20, so the pre-registered `k80_ho` was
  censored at "> 20" everywhere, which hides how far above 20 it is.
- `joint_win16`: the joint block in consecutive non-overlapping 16-bar windows (same n = 50
  performances; tempo re-centered per window, velocity re-smoothed per window), with its own
  phase-randomized null; per piece the median over windows. Reason: plan section 1.2 predicts
  a few parameters per phrase, so a whole-piece count grows with length; a fixed-length window
  separates "how many ways to shape a phrase group" from "how long is the piece".
- `joint_trim10`: drop the 10% of performances farthest (Euclidean) from the piece's median joint
  curve, then draw n = 50. Reason: checks whether a few badly aligned or atypical performances
  drive the count.

## Run record

- Code: uncommitted (repo has no commits); sha256 of the concatenated `*.py` in this folder plus
  `src/pianolens/eval/dimensionality.py` and `tests/eval/test_dimensionality.py` (sorted paths):
  `1ddcf7004eb25f605fd7be8b745ae6e728f5ff9d867721be6a8b52997efff564`.
- Data: PianoCoRe tier A cache (D-07, Zenodo 19186016 v1.0); Vienna 4x22 commit 1033ade.
- Commands: `curves.py --workers 13` (run with `OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1`;
  the first launch was killed after 49 pieces for BLAS oversubscription and resumed; per-piece
  files are deterministic), then `analyze.py pieces`, `disklavier`, `vienna`, `summarize`,
  `figures`, and `extra.py` (exploratory).
- Wall time: curve extraction about 70 min in total on a shared, heavily loaded machine (load
  average 20-45 from other agents); analysis 60 s; controls under 1 min each.
- Seeds as pre-registered. Outputs: `artifacts/summary.txt`, `headline_{n50,all}.csv`,
  `nulls_*.csv`, `strata_*.csv`, `piece_stats.csv`, `piece_qc.csv`, `disklavier_*.csv`,
  `vienna_control.csv`, `extra_exploratory.csv`, `figures/`, curves in `artifacts/curves/`.

## Results

**Coverage.** 730 pieces, 137,517 performances extracted (majority score only), 0 extraction
failures. QC dropped 2,106 performances (1.5%) and 2.6% of beats (mostly the edges). 698 pieces keep
at least 50 performances and form the primary n = 50 analysis; all 730 enter the all-performances
analysis (median 119 performances, IQR 78-189). Median piece: 329 beats on the tempo grid (IQR
193-585), 3 beats per bar, median of 1 detected pause per performance.

### Headline (primary: joint smooth tempo + smooth velocity, n = 50 per piece, 698 pieces)

95% CIs: bootstrap over pieces (2,000 resamples, seed 0). `k80_in` = components for 80% in sample;
`k80_ho` = components for 80% held-out reconstruction R² (pre-registered range 1-20).

| Block | k80_in median [IQR] | share k80_in ≤ 10 | share k80_in > 20 | PC1 | held-out R² at k = 5 / 10 / 20 | share k80_ho ≤ 10 | phase-null k80_in | share real < null |
|---|---|---|---|---|---|---|---|---|
| **joint (primary)** | **19 [16, 21]** | **0.03 [0.02, 0.04]** | **0.35 [0.31, 0.38]** | 0.16 | 0.23 / 0.31 / 0.42 | **0.00 [0.00, 0.01]** | 25 | **1.00 [1.00, 1.00]** |
| tempo | 13 [9, 16] | 0.31 [0.27, 0.34] | 0.06 [0.04, 0.07] | 0.21 | 0.33 / 0.45 / 0.58 | 0.04 [0.03, 0.06] | 19 | 1.00 |
| velocity, smooth | 16 [13, 18] | 0.10 [0.08, 0.13] | 0.11 [0.09, 0.14] | 0.21 | 0.33 / 0.43 / 0.55 | 0.01 | 20 | 1.00 |
| velocity, raw per beat | 20 [17, 23] | 0.02 | 0.44 | 0.17 | 0.26 / 0.34 / 0.43 | 0.00 | 25 | 1.00 |
| residual timing (per position) | 25 [22, 28] | 0.04 | 0.81 | 0.11 | 0.11 / 0.14 / 0.20 | 0.01 | 30 | 0.98 |
| joint, 3-bar smoothing | 15 [12, 18] | 0.13 | 0.11 | 0.18 | 0.29 / 0.40 / 0.53 | 0.01 | - | - |
| joint, velocity z-scored per performance | 20 [17, 22] | 0.01 | 0.46 | 0.14 | 0.19 / 0.27 / 0.38 | 0.00 | - | - |

Medians of k80_in have CIs of ±1 or less (joint 19 [19, 19], tempo 13 [12.5, 13]). Held-out R²
never reaches 0.8 within k ≤ 40 for the median piece in any block (`k80_ho_ext` "> 40").

**Mean curve.** Before any PCA, the piece's mean curve carries a median 0.62 (joint), 0.58 (tempo)
and 0.63 (smooth velocity) of each performance's own normalized variance. The counts above
describe only the remaining between-performance deviations.

### Nulls (joint, n = 50, medians over 698 pieces)

| Source | k80_in | k90_in | PC1 | held-out R² k = 10 |
|---|---|---|---|---|
| real | 19 | 28 | 0.156 | 0.315 |
| phase-randomized (same spectrum, no shared structure) | 25 | 33 | 0.091 | 0.123 |
| smooth noise (same 1.5-bar smoother) | 31 | 38 | 0.056 | - |
| column-shuffled | 33 | 41 | 0.044 | 0.032 |
| white noise | 33 | 40 | 0.045 | - |

Real curves need fewer components than the phase-randomized null on every piece (in-sample), and
their held-out R² at k = 10 is 2.6 times the null's. So there is shared, low-rank structure, but
it is a modest part of the between-performance variance: most of that variance is spread over
many directions.

### Stratification

| joint, n = 50, beats tertile | pieces | k80_in | phase null | k80_in / 49 |
|---|---|---|---|---|
| 37-229 beats | 233 | 16 | 21 | 0.33 |
| 230-463 | 233 | 19 | 25 | 0.39 |
| 464-3,135 | 232 | 22 | 28 | 0.45 |

| joint, all performances, n bin | pieces | k80_in | phase null | k80_in / min(n - 1, p) |
|---|---|---|---|---|
| 50-75 | 172 | 19 | 26 | 0.34 |
| 76-150 | 293 | 28 | 42 | 0.27 |
| 151-300 | 165 | 38 | 60 | 0.20 |
| > 300 | 100 | 54 | 89.5 | 0.11 |

In-sample counts grow with piece length and with n (no plateau), as expected when a spectrum has a
long tail rather than a few components plus small isotropic noise. The fixed-n design exists
because of this.

### Held-out reconstruction (most honest number)

At n = 50 (40 training performances), the joint held-out R² is 0.23 at k = 5, 0.31 at k = 10 and
0.42 at k = 20. For the pieces with more than 300 performances, nested subsamples show little
gain from more training data (exploratory, `extra.py`): joint held-out R² at k = 10 is 0.28 (n = 50),
0.33 (100), 0.36 (200), 0.37 (300); at k = 20 it is 0.37 / 0.43 / 0.47 / 0.50. The low values are
therefore not mainly an estimation-size artefact.

### Transcription-noise controls

- **Disklavier vs transcribed, same piece, matched n** (37 pieces with 8-29 Disklavier
  performances, median 10; 50 transcribed subsamples each). Joint: k80_in median 6 vs 6 (Disklavier
  higher on 13 pieces, lower on 6); PC1 0.222 vs 0.252, median difference -0.041 [-0.052, -0.030],
  Wilcoxon p = 4e-6; top-3 share -0.045 [-0.069, -0.022]. Tempo and velocity alone show the same
  direction. Disklavier (ASAP) curves are **not** lower-dimensional; if anything they are slightly
  less concentrated. Caveat: the ASAP players are a different population (competition
  performances), so this compares populations as well as capture methods.
- **Vienna 4x22** (sensor, ground-truth alignments, n = 22) vs 50 subsamples of 22 transcribed
  PianoCoRe performances of the same bars. Beat offset found by matching score notes: Op. 10 No. 3
  bars 1-21 (100% of notes mapped); Op. 38 first 129 beats (the PianoCoRe score's repeat structure
  differs after that); K. 331 first 49 beats only (repeat mismatch). Schubert D783 No. 15 is not in
  tier A.

  | Excerpt | block | Vienna k80_in | transcribed k80_in (median) | Vienna PC1 | transcribed PC1 median [5-95%] |
  |---|---|---|---|---|---|
  | Op. 10 No. 3, bars 1-21 | joint | 9 | 8 | 0.23 | 0.24 [0.18, 0.45] |
  | Op. 38, 129 beats | joint | 9 | 9 | 0.16 | 0.20 [0.18, 0.36] |
  | K. 331, 49 beats | joint | 7 | 6 | 0.30 | 0.31 [0.23, 0.40] |

  Sensor-recorded performances are as high-dimensional as transcribed ones, or one component
  higher. Both controls point the same way: transcription noise does not inflate the counts.

### Exploratory (added after the dry run; not in the verdict)

- **16-bar windows** (692 pieces, median 96 joint columns per window): k80_in median 10 [10, 11];
  share ≤ 10 is 0.51 [0.47, 0.55]; phase null 14; held-out R² 0.41 / 0.58 / 0.76 at k = 5 / 10 /
  20; `k80_ho_ext` median 24. Within a 16-bar span, the in-sample count sits right at the plan's
  threshold, but held-out reconstruction still needs about 24 components.
- **Trimming the 10% most atypical performances** does not lower the count (k80_in 20 [17, 23]).
  Outliers or bad alignments are not the driver.
- **Total-variance reading** (mean curve counted as explained, held-out): joint R² 0.59 with the
  mean curve alone (k = 0), 0.73 at k = 10, 0.78 at k = 20; median k for 80% = 29; share of pieces
  ≤ 10 = 0.26. Tempo alone: 0.56 / 0.78 / 0.83, median k = 14, share ≤ 10 = 0.41. Even under this
  generous reading, the joint block does not reach 80% with 10 components on most pieces.

### Interpretability (figures)

`figures/loadings_chopin_op10_no3.png` (713 performances) and `loadings_chopin_op9_no2.png` (1,975):
- Op. 10 No. 3, tempo: PC1 (37%) is how much faster the agitated middle section (roughly beats
  44-107, bars 22-53) is than the outer sections. PC2 (10%) is positive over the start of the middle section
  and the climax / return (beats about 45-65 and 105-125) and negative just before the climax (90-105). PC3 (7%) is the build-up and the climax around bars 55-60.
  Velocity PC1 (41%) is the dynamic contrast of the same middle-section plateau.
- Op. 9 No. 2 (12/8, eighth-note beats): tempo PC1 (17%) is mostly the cadenza / coda (last 2-3
  bars) plus the phrase ends at about beats 140 and 250. Tempo PC2 (13%) is the depth of the
  two-bar rubato oscillation, which grows toward the end. Velocity PC1 (25%) is the loudness of the
  coda and the returning theme's climaxes. Velocity PC3 (8%) is the depth of the four-bar phrase
  swell, phase-locked to the phrase structure.
- Leading components line up with the form (sections, cadenza, phrase periodicity). This is
  consistent with the plan's global / phrase layers, but these explain only 15-40% of the
  between-performance variance each.

Other figures: `scree_heldout_n50.png` (cumulative variance and held-out R² vs k, real vs phase
null, median and IQR across pieces), `k80_hist_joint_n50.png`, `k80_vs_beats_n50.png`.

## Verdict (Provisional; audited 2026-09-27: Confirmed with caveats, see Audit)

**H1 as pre-registered: not supported, not falsified (partly supported only relative to the null).**

- In-sample `k80_in` ≤ 10 holds on 3% of pieces (need > 50%): **not met**.
- Held-out `k80_ho` ≤ 10 holds on 0.3% of pieces: **not met**.
- `k80_in` below the phase-randomized null holds on 100% of pieces: **met**.
- Falsifier (`k80_in` > 20 on most pieces): met on 35% [31, 38], so **H1 is not falsified** at
  n = 50. With all performances (median n 119), 74% of pieces need more than 20, but that
  analysis is not the pre-registered one, and the count rises with n.

Plain reading: expert expression across whole pieces has more structure than chance, and its top
components are musically interpretable (section tempo plans, climaxes, phrase-rubato depth). But
it is **not low-dimensional in the plan's sense**. About 19 components are needed in sample at
n = 50. A PCA basis learned from other experts reconstructs only about 31% of a new expert's
deviations with 10 components, and about 50% with 20 even when 300 references are available.
Tempo alone is lower (13) than velocity (16) or joint (19). Fine-scale residual timing is the
highest (25) and closest to its null. The Disklavier and sensor controls show this is not
transcription noise.

Implication for the plan: "distance to the expert space" (tier D) should not assume a
≤ 10-dimensional expert subspace for whole pieces. Candidates to test are a per-phrase / windowed
subspace (about 10 in-sample per 16 bars), score-conditioned models (H1 asks for an unconditional
basis, and much of the variance may be predictable from score features even if it is not low-rank
across performers), or distances that do not rely on a low-rank basis.

## Threats to validity

- **Smoothing sets the ceiling.** The counts depend on the 1.5-bar F-03 cutoff (3-bar smoothing:
  19 to 15). The phase null has the same spectra, so the real-vs-null comparison does not depend
  on it, but the absolute count does.
- **The in-sample count depends on n and length** (tables above). The verdict is at n = 50 by
  design, and whole-piece length varies from 37 to 3,135 beats.
- **Beat grid choice.** Beats are score denominator units (eighths in 6/8 and 12/8), so grid
  density differs across meters. The smoothing cutoff is in bars, so the curve content is
  comparable, but column counts are not.
- **Pauses and fermatas are excluded from tempo** (F-03 gaps), and tempo steps are smoothed across
  rather than split. Large expressive holds are therefore missing, and sudden section changes
  are blurred.
- **Transcribed velocities** depend on the AMT model and the recording. Centering removes an
  offset, but not a scale difference; the z-scored sensitivity raises the count (20). Controls
  above suggest this does not inflate the count relative to sensor data.
- **Performer duplication.** Aria-MIDI and other sources may contain several recordings by the same
  pianist, or duplicates of one recording. Duplicates would *lower* the count, so they do not
  explain the high numbers.
- **Joint-block weighting** (equal variance per block) is a choice. Tempo and velocity counts
  are reported separately.
- **Disklavier control** compares populations as well as capture methods, and has small n (8-29).
- **The exploratory analyses** (windows, trimming, total-variance reading, k up to 40) were added
  after the first 9 pieces were seen. They are disclosed above and do not enter the verdict.

## Audit (2026-09-27)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** The pre-registered verdict (H1 not
supported, not falsified; real curves below the phase null) follows from the numbers, and the
numbers reproduce. The caveats change how the "real structure" result should be worded, not the
verdict.

### What was checked

1. **Pre-registration.** The README `Write` in the ml-researcher transcript (2026-09-28 00:34 UTC)
   precedes the first curve extraction (00:36) and any PCA (00:39). Its sha256
   `3ae426a9c06ea0db4d7515a42b742430606ddb439deba204b0c674a3c2d1a0d5` equals the sha256 of lines
   1-144 of this README. The header is unchanged. The joint block as primary, n = 50 (seed 0), the
   three-part support rule and the falsifier are all in that text. The Amendments section was
   appended at 00:54, after Op. 10 No. 3 and an 8-piece dry run had been seen, and before the full
   analysis (01:57). It is labelled exploratory. The verdict uses none of it. `k80_ho` still uses
   the pre-registered range 1-20 (`KS`). `KS_EXT` only adds `k80_ho_ext`.
2. **Reproduction.** I reran the full pipeline from the cached curves (`load_blocks`, `joint`, the
   same seeds) on 30 random n = 50 pieces (seed 2026). Joint `k80_in`, the phase-null `k80_in` and
   held-out R² at k = 10 match `piece_stats.csv` exactly on 30/30 pieces. Over all 698 pieces,
   `k80_in` is 19 (median), with share ≤ 10 = 0.030 and share > 20 = 0.345. Held-out `k80_ho` ≤ 10
   holds on 0.29% of pieces. These match the README. `uv run pytest -q tests/eval/test_dimensionality.py`:
   9 passed.
3. **Mean removal and held-out R².** `explained_variance_ratio` column-centers before the SVD,
   so the across-performer mean curve is removed. The counts describe differences from the
   average, as intended. Held-out: the mean and axes are fit on the 40 training rows, the held-out
   rows are centered on the training mean and projected, and R² is taken relative to the
   training-mean baseline. The mean curve earns no credit. An independent scikit-learn `PCA`
   reimplementation gives the same held-out R² at k = 10, within 4e-4 on all 30 pieces. The
   held-out rows' own scores are used for the projection. This is standard and slightly
   optimistic, so it favours H1 and does not weaken the negative result. The joint block scales
   use all 50 rows, including held-out ones. That leak is trivial.
4. **Subsample seed.** The n = 50 draw is one seed. Across draw seeds 0-4, the median is 19 every
   time, and the share > 20 is 0.345 / 0.348 / 0.347 / 0.354 / 0.364. The not-falsified call
   (need > 0.5) does not depend on the draw.
5. **Joint weighting.** With a tempo variance share of 25% / 50% / 75%, the median `k80_in` on the
   30 pieces is 20 / 19 / 18. The equal-variance choice does not drive the count.
6. **Missing data.** In the n = 50 subsets of the 30 pieces, a median 0.26% of tempo cells
   (max 0.9%) are not observed within a bar, and 0.15% lie outside the performance's span
   (filled with the edge value). Velocity is interpolated on a median 3% of tempo-grid cells
   (max 15%). These are mostly beats with no score onset. Keeping only performances observed on
   at least 99% of beats and redrawing n = 50 does not lower the count: the median difference is
   +1 (range -2 to +7, with subsample noise of about ±3). Filling does not create or hide the
   dimensions.
7. **Duplicates.** In the n = 50 subsets, the median of the maximum pairwise correlation of
   joint deviation curves is 0.83. Pieces have at most 2 pairs above 0.9. Near-duplicate
   recordings are not a factor.

### The null: correct, but a weak test

Phase randomization keeps each performance's spectrum and variance and gives circularly
stationary rows. It removes two things at once: alignment across performers, and any
beat-dependent variance profile (where in the score performers differ most). A profile alone
concentrates variance, so "below the phase null on 100% of pieces" is close to guaranteed for
real music. It does not show much by itself. I ran two stricter checks on all 698 pieces, with
20 surrogates per piece. These were added by the auditor after the results and are not part of
the verdict:

| Check (joint, n = 50, 698 pieces) | median | IQR | share ≤ 10 | share = 0 |
|---|---|---|---|---|
| `k80_in` of an envelope null (phase null, then each beat rescaled to the real per-beat SD) | 24 | - | - | - |
| Components above the phase null (parallel analysis, eigenvalue > 95th percentile of 20 surrogates) | 5 | 3-7 | 0.97 | 0.02 |
| Components above the envelope null | 3 | 1-5 | 0.99 | 0.16 |
| Share of between-performer variance in the components above the phase null | 0.46 | 0.37-0.53 | - | - |
| Share in the components above the envelope null | 0.35 | 0.22-0.44 | - | - |
| Tempo only: components above the phase null | 4 | 2-6 | 0.98 | 0.05 |

- Real `k80_in` is below the envelope null on 100% of pieces, 19 vs 24. So "more structured than
  chance" survives the stricter null.
- The structure that clears the null is small and low-rank: about 3-5 components, carrying about
  35-46% of the between-performer variance. The other 55-65% cannot be told apart from smooth,
  performer-specific curves with the same spectrum and per-beat variance. The 80% criterion counts
  all of it, so the pre-registered count (19) is mostly a count of individual variation.
- **Wording fix.** Replace "there is shared, low-rank structure, but it is a modest part" with the
  measured version: "3-5 components per piece clear a phase / envelope null (≤ 10 on 97-99% of
  pieces), and they carry about 35-46% of the between-performer variance." This is a post-hoc
  reading. It does **not** rescue H1 as pre-registered, which asked for 80% of variance. It does
  support the H1b / tier-D direction in `DECISIONS.md`: a small shared, score-locked part plus a
  large individual part.

### Transcription-noise controls: direction supported, power limited

- **Disklavier.** n and beats are matched: the same piece, the same QC columns, and d
  transcribed performances drawn 50 times. The summary rows reproduce from
  `disklavier_control.csv` (37 pieces, d = 8-29; `k80_in` Disklavier higher on 13 pieces, lower
  on 6). With median d = 10, `k80_in` is capped at d - 1 = 9, so the count itself has little
  power. The evidence is PC1 / top-3 / LOO R², which are *less* concentrated for Disklavier.
  Near-duplicates are not the cause: no Disklavier row has a transcribed twin (correlation above
  0.95), and pairs above 0.9 are a median 0.008% of transcribed pairs per piece. The caveat that these are different
  populations (ASAP) remains the main limit.
- **Vienna.** The table reproduces from `vienna_control.csv`, with n = 22 on 41-130 beats.
  Counts are small and near their cap. The beat-drop QC in `_curves_matrix` runs separately on the
  Vienna set and on the transcribed set, so the two may keep slightly different beats. I did not
  check this. The effect is small: 1.5-bar smoothing, and little missing data.
- The fair wording is "no evidence that transcription inflates the counts; the controls can
  detect a change in the leading-component concentration, not a change of a few components in
  `k80_in` at n = 50".

### Smoothing

With 3-bar smoothing the count falls from 19 to 15, and only 13% of pieces have ≤ 10. The
negative verdict holds at both cutoffs. The count still depends on the cutoff, as the README says.
The phase null was not rerun at 3 bars. The claim that the real-vs-null comparison does not depend
on smoothing is an argument, not a measurement.

### Required changes (text only; no rerun needed)

1. Reword the "real structure" claim as in the wording fix above (Nulls paragraph, Verdict plain
   reading, `EXPERIMENTS.md` row). State that the phase null is a weak test.
2. Transcription controls: add the power caveat (k80 capped at d - 1 ≈ 9; the evidence is the PC1
   / LOO direction).
3. Say that the not-falsified share (35%) is stable across subsample seeds (0.345-0.364).

Audit scripts and outputs are in the auditor's session scratchpad and are not in the repo:
`r02audit.py` (30-piece rerun, sensitivities) and `r02audit_all.py` (698 pieces: seeds, envelope
null, parallel analysis, Disklavier duplicates). Their numbers are quoted above.
