# Structural coherence vs skill (MAJEPPA)
Ticket: R-09    Hypothesis: H4    Status: Provisional

Pre-registered by `ml-researcher` before any coherence value was computed on MAJEPPA by skill
level. Procedural pilot before this was written: one MAJEPPA performance (the 6th row of the
coverage-filtered index), run to check the API and the time per performance (about 2 s). No
skill-level quantity was looked at.

## Question

H4 (plan, section 2): "Structural coherence (the fraction of a performer's own expressive
variance explained by score features) separates skill levels and correlates with rated quality."
MAJEPPA has skill levels, not ratings, so this experiment tests only the first half: is
structural coherence monotone in skill, within a piece, **when recording context is held fixed**
(CLAUDE.md rule 3; D-10 found tier B's apparent skill effect vanished within matched contexts)?

### Channels, stated exactly

- **Coherence** is `pianolens.features.shaping.structural_coherence`: out-of-fold ridge R² of a
  performer's expressive curve on the F-05 score basis, folds = 4-written-bar blocks with a
  1-bar buffer, `clip_to_train=True` (default). It is defined only for `n_blocks >= 3`
  (DECISIONS, after F-05b, item 6); performances below that are dropped per channel.
- **Without markings** (`r2_no_markings`; DECISIONS, F-05 follow-ups, item 2). MAJEPPA scores are
  MIDI files, which carry no dynamics, articulation, tempo or fermata markings, so on MAJEPPA
  `r2_no_markings` equals `r2` by construction. It is still the column used, so that the ASAP
  noise-floor numbers (MusicXML, with markings) are on the same definition.
- **Primary channels (two, co-primary):**
  1. `articulation`: `art_log_ratio` = log(key-down duration / notated duration at the local
     smooth beat period), per matched note.
  2. `timing`: `dev_beats`, the per-position onset residual from the F-03 smooth tempo curve
     (timing residual), per score position.
- **Why not velocity:** DECISIONS (after F-05b) names velocity and articulation as H4's primary
  channels, but DECISIONS (after D-10) excludes velocity-based features from skill claims on
  transcribed MIDI (Transkun velocity residual SD about 9 MIDI, slope 0.64). MAJEPPA is Transkun
  output, so velocity drops out and the timing residual takes its place, as the ticket says
  ("timing features only; no velocity on transcribed MIDI"). Velocity coherence is computed and
  reported descriptively only; it never enters the verdict.
- **Why not smooth-tempo coherence:** DECISIONS (after D-11 / F-05c) limits tempo coherence R²
  to annotated phrases, which MAJEPPA does not have.
- **Secondary channel:** `phrase_tempo_shaping(...).summary["concave_excess"]` (concave-arc share
  of per-phrase smooth-tempo parabolas minus the mean of the ±2-bar shifted-boundary null), with
  phrase starts from `cadence_phrase_ends(score).starts` (DECISIONS after D-11 / F-05c, item 1).
  Defined only when at least 4 phrases are fitted (`n_phrases >= 4`).

## Falsified if

Plan: "No monotone relationship with skill level in MAJEPPA / Expert-Novice / PianoCoRe."
Refined here for MAJEPPA, per primary channel `c` in {articulation, timing}:

- `b_c` = within-piece linear trend of coherence R² per skill-level step (6-level ordinal rank,
  below), estimated in the **matched-context sample** (primary analysis A1 below).
- Two co-primary channels, so the verdict uses **97.5% cluster-bootstrap CIs** (Bonferroni);
  95% CIs are also shown.
- Smallest effect of interest (SESOI): **0.01 R² per level step** (0.05 across five steps). Fixed
  before seeing MAJEPPA results. For scale: across 6 ASAP expert performances of D.899/3 (F-05),
  articulation R² ranged 0.13 to 0.25 and timing 0.04 to 0.22, so 0.05 is roughly a third to a
  half of the spread among experts on one piece.

Per channel:

- **Supported:** the 97.5% CI of `b_c` lies entirely above 0, **and** the adjusted 3-group
  point estimates are ordered beginner <= intermediate <= advanced (analysis A1-3g).
- **Falsified (no monotone relationship):** the 97.5% CI of `b_c` lies entirely below +0.01
  (it excludes the SESOI: any positive trend is too small to matter), or entirely below 0.
- **Inconclusive:** anything else (the CI includes 0 and also values >= 0.01).

H4 on MAJEPPA overall:

- **supported** if at least one primary channel is supported and no primary channel has a CI
  entirely below 0;
- **falsified** if both primary channels are falsified;
- **inconclusive / mixed** otherwise, reported per channel.

The pooled (context-uncontrolled) analysis can never support H4 on its own (CLAUDE.md rule 3).

## Data

- **MAJEPPA** (`pianolens.data.majeppa`, DATASETS.md row; Transkun-transcribed MIDI, MIDI scores).
- **Selection** = D-10's selection (`scripts/build_skill_control_d10.py::select`):
  `score_coverage >= 0.85`, a score exists, and the score has performances in at least two
  skill groups. Then per performance:
  - aligned with `align_performance`, then `majeppa.prepare_aligned` (staff from tracks,
    duration snap);
  - **trusted alignment:** F-02 match ratio >= 0.8 (`alignment_suspect == False`);
  - **quantized score:** at most 10% of onsets off a 1/48-quarter grid (D-10 gate);
  - per channel: `n_blocks >= 3` and at least 20 observations (the shaping minimum).
- The counts per level x context after each gate are reported in Results. Pieces enter an
  analysis only if they have at least two distinct skill levels within that analysis's sample.
- **Transcription-noise pairs** (D-10): the 65 PianoCoRe duplicates that pair an ASAP Disklavier
  performance with a transcription of the same performance (59 Aria-AMT, 6 Transkun V2), found
  and matched exactly as in `scripts/check_transcription_noise_d10.py` (its `pairs()` and
  matching logic are imported, not copied). ASAP scores (MusicXML, with markings).
- **Piece difficulty:** PSyllabus (open CIPI substitute; CIPI itself is gated). Joined to
  MAJEPPA by composer surname plus catalogue tokens (op / no / BWV / K / Hob / D), exact match
  only. Piece fixed effects absorb any piece-level difficulty, so difficulty enters only the
  secondary analyses S7 below.

## Splits

This is an association test within pieces, not a predictive claim, so the primary estimate uses
piece fixed effects (every comparison is between performances of the same piece). Rule 1
(hold out whole pieces) is honoured by the secondary predictive check S8 (leave-piece-out).

- Bootstrap: cluster bootstrap over `recording_id` (MAJEPPA's only performer proxy; one video),
  2,000 resamples, seed 0. Piece fixed effects are re-estimated in every resample.
- S8 folds: `pianolens.eval.group_kfold` by `piece_id`, 5 folds, seed 0.

## Baselines

- For the association (A1-A3): the covariate-only model (piece FE + context FE + log note rate +
  log clip duration). `b_c` is the skill coefficient added on top of it, so the trivial
  baseline is `b_c = 0`.
- For S8 (prediction of skill rank on unseen pieces): covariates only (log note rate, log clip
  duration, recording-type dummies) vs covariates + coherence features.
- No rater-parity ceiling exists: MAJEPPA labels are self-/source-declared levels, not ratings.
- **Noise floor** (instead of a ceiling): how much coherence moves when the same performance is
  transcribed instead of recorded on a Disklavier (the D-10 lesson).

## Method

### Skill coding

- **6-level ordinal rank** (primary): child_beginner 1, adult_beginner 2, adult_intermediate 3,
  child_professional 4, piano_teacher 5, virtuoso 6. MAJEPPA does not document an order between
  child and adult beginners or between child professionals, teachers and virtuosos; this order
  is an assumption, so the 3-group coding below is reported beside it.
- **3 groups** (D-10): beginner (child + adult beginner), intermediate (adult intermediate),
  advanced (child professional, piano teacher, virtuoso); as dummies (beginner = reference) and as
  a 0/1/2 trend.

### Model (per outcome, per analysis sample)

```
y = piece FE + [recording_type FE] + b * skill_rank + g1 * log(note rate) + g2 * log(duration s) + e
```

OLS after within-piece demeaning (Frisch-Waugh). `note rate` = performed notes per second;
`duration` = first to last performed onset (clip length). Also reported: the model without
covariates, and FE-adjusted level means (level dummies instead of the trend).

### Analyses

- **A1 (primary): matched contexts.** `recording_type` in {practice, performance} (both skill
  groups recorded the same way; D-10's "practice + performance" subset), with a recording_type
  FE. Piece FE.
  - A1-p / A1-f: the practice and performance strata separately (each with piece FE), where a
    piece has at least two levels within the stratum.
  - A1-3g: the same sample with the 3-group coding (dummies and 0/1/2 trend).
- **A2: pooled, context-controlled.** All recording types except `fast_demo` (1 clip), with
  recording_type FE. Context and level are nearly collinear at the top (every virtuoso clip is a
  concert, most teacher clips are demos), so this is reported but is not the primary.
- **A3: pooled, context-confounded.** All recording types, no recording_type term. Reported to
  show how much of any pooled trend is context, as D-10 did for tier B.
- **Secondary S1:** `concave_excess` (cadence boundaries) through A1, A2, A3; same decision rule
  with SESOI 0.02 per level step (0.1 across five steps; F-05c held-out Batik mean with cadence
  boundaries was +0.21), 95% CIs.
- **S2:** velocity coherence through A1-A3, descriptive only (excluded from claims, D-10).
- **S5:** 6-level coding restricted to the four lowest levels (child_beginner..child_professional),
  the only levels present in quantity in practice/performance.
- **S7 (difficulty):** join coverage; among joined pieces, the A1 model without piece FE plus
  PSyllabus difficulty, and the A1 model with a `skill_rank x difficulty` interaction.
- **S8 (leave-piece-out prediction):** in the A1 sample, predict `skill_rank` with ridge
  (alpha chosen by inner grouped CV) from (a) covariates only and (b) covariates + articulation,
  timing and concave_excess coherence; metric = Spearman of out-of-fold prediction with rank,
  within-piece pairwise accuracy (`pianolens.eval.pairwise_accuracy` with piece groups); paired
  bootstrap over pieces of (b) - (a). Rows missing a coherence value are imputed with the training
  fold median plus a missing indicator.

### Transcription-noise floor

On each of the 65 pairs, compute `structural_coherence` (`r2_no_markings`: articulation, timing,
velocity) and `concave_excess` (cadence starts from the ASAP score) on both renditions, each
aligned to the same ASAP score. Report per transcriber (Aria-AMT, Transkun): paired median of
transcribed minus Disklavier, median absolute difference, Spearman across pairs (does
transcription keep the ranking?), and the share of pairs whose difference exceeds the SESOI. The
Transkun rows (n = 6) are the relevant ones for MAJEPPA; Aria-AMT gives the larger sample.

### Seeds and record

Seeds: bootstrap 0, folds 0. The git commit (or "uncommitted" + diff hash), the MAJEPPA and
PianoCoRe versions from DATASETS.md, the wall times and the exact commands go under Results.

## Command

```
OMP_NUM_THREADS=1 uv run python experiments/2026-09-28-R-09-coherence-skill/build.py --workers 8
OMP_NUM_THREADS=1 uv run python experiments/2026-09-28-R-09-coherence-skill/noise_floor.py --workers 6
OMP_NUM_THREADS=1 uv run python experiments/2026-09-28-R-09-coherence-skill/analyze.py --boot 2000
```

Outputs (gitignored) in `experiments/2026-09-28-R-09-coherence-skill/artifacts/`.

---

## Run record

- Pre-registration: the first 191 lines of this file, sha256
  `c44a4b74b71a6d70847b040383d3e890f253f61a608a31932beb8d07eaba8517` (written 2026-09-27 23:05
  CDT, before `build.py` ran; re-verified after the results).
- Code: the repo is not a git repository, so there is no commit. sha256 prefixes: `build.py`
  `47fe752440fee678`, `noise_floor.py` `1520b2eda7799eec`, `analyze.py` `98b24c0564b0926d`
  (final version, which includes the post-hoc section). *[Post-audit fix 6: the prefixes were
  first attached to the wrong files; re-verified 2026-09-28.]*
- Data: MAJEPPA HF commit 7a462f4; PianoCoRe Zenodo v1.0; ASAP as in DATASETS.md.
- Seeds: bootstrap 0 (2,000 resamples over `recording_id`; S8 over pieces), folds 0.
- Wall time: `build.py` 632 s (8 workers, machine shared with other agents' jobs; 1,604
  performances, 2 failures "no matched onsets", the same 2 as D-10); `noise_floor.py` about
  17 min (4 workers; 65/65 pairs); `analyze.py` about 2 min.
- Commands as registered, except that `noise_floor.py` ran with `--workers 4`, not the
  registered `--workers 6` (worker count only; no effect on results). *[Post-audit fix 6.]*
  Outputs: `artifacts/` (`coherence.csv`, `noise_pairs.csv`,
  `counts.csv`, `context_by_level.csv`, `effects.csv`, `level_means.csv`, `verdict.csv`,
  `difficulty.csv`, `lpo.csv`, `noise_floor.csv`, `effects_posthoc.csv`, `analyze_stdout.txt`).

### Deviations

1. **Noise pairs list.** The pre-registration says `pairs()` and the matching logic of
   `check_transcription_noise_d10.py` are imported. The matching code lives inside that script's
   `main()`, so `noise_floor.py` reads the script's output list
   (`data/interim/skill_control_d10/transcription_pairs.csv`: `trans_path`,
   `asap_performance_id`) instead. Same 65 pairs, same 59 / 6 split. No effect on results.
2. **Post-hoc robustness section (added after the results were seen).** See "Post hoc" below.
   It is not used for the verdict.
3. **Test runs after the pre-registration.** *[Post-audit fix 5; not disclosed in the first
   version of this record.]* After the header was written and before the full run:
   - a 2-score test of `build.py` (31 performances). One row was printed: one piano teacher's
     coherence values. No skill comparison was made.
   - an `analyze.py --boot 20` smoke test on that 31-row file. It crashed on empty effect
     tables, so no skill estimate was produced or seen.
   - Two code fixes followed: `n_score_bars` was added to `build.py`, and the PSyllabus join
     key was fixed in `analyze.py`. Neither touches the model, the gates or the decision rule.

## Results

### Sample

Gates (level x gate): the D-10 selection gives 1,604 performances; trusted alignment 1,149;
quantized score 1,081 (identical to D-10's tier B set). Valid articulation 1,081, timing 1,080,
`concave_excess` (>= 4 cadence phrases) 685.

Gated sample, level x context (the confound):

| Level | concert | demo class | performance | practice | sight read | slow demo |
|---|---|---|---|---|---|---|
| child beginner | 0 | 0 | 55 | 50 | 1 | 1 |
| adult beginner | 0 | 3 | 25 | 172 | 63 | 1 |
| adult intermediate | 0 | 5 | 64 | 105 | 12 | 1 |
| child professional | 0 | 0 | 47 | 41 | 0 | 0 |
| piano teacher | 17 | 218 | 6 | 7 | 1 | 72 |
| virtuoso | 113 | 0 | 0 | 0 | 0 | 0 |

So the matched-context sample (A1) spans child beginner to child professional, plus 9 teacher
clips; it has no virtuosos. A1: 388 performances, 106 pieces (rank coding; pieces with >= 2 of the
6 levels); 331 performances, 89 pieces for the 3-group coding.

### Primary (A1, matched contexts, piece FE + context FE + log note rate + log duration)

`b_rank` = change in coherence R² per level step. 97.5% CIs are the verdict CIs.

| Outcome | n (pieces) | Mean R² | `b_rank` | 95% CI | 97.5% CI | Intermediate - beginner | Advanced - beginner (95% CI) | Verdict |
|---|---|---|---|---|---|---|---|---|
| articulation | 388 (106) | 0.208 | +0.0082 | -0.0155 to 0.0317 | -0.0193 to 0.0344 | -0.021 | -0.023 (-0.095 to 0.044) | inconclusive |
| timing | 388 (106) | 0.099 | +0.0045 | -0.0125 to 0.0192 | -0.0144 to 0.0214 | +0.022 | -0.012 (-0.055 to 0.030) | inconclusive |

Both CIs include 0 and include the SESOI (+0.01), so neither channel is supported or falsified.
The 3-group ordering also fails for both: the advanced point estimate is below the beginners'.

Adjusted level differences vs child beginner (A1): articulation adult beginner +0.069,
adult intermediate +0.020, child professional +0.019, teacher (n = 9) +0.064; timing +0.052,
+0.049, +0.014, -0.048. All 95% CIs include 0. Nothing is monotone.

Strata (rank coding, with covariates): practice only (220, 68 pieces) articulation +0.010
(95% CI -0.028 to 0.052), timing +0.009 (-0.009 to 0.026); performance only (89, 25 pieces)
articulation +0.017 (-0.020 to 0.047), timing +0.004 (-0.032 to 0.050). S5 (levels 1-4 only):
articulation +0.005 (-0.021 to 0.031), timing +0.009 (-0.009 to 0.026). Without covariates the
A1 point estimates are larger (articulation +0.019, timing +0.009) but the CIs still include 0.

### Context: controlled vs confounded

| Outcome | A1 matched | A2 pooled, context FE | A3 pooled, no context term |
|---|---|---|---|
| articulation `b_rank` | +0.008 (-0.016 to 0.032) | +0.006 (-0.012 to 0.030) | +0.006 (-0.006 to 0.018) |
| timing `b_rank` | +0.005 (-0.013 to 0.019) | +0.008 (-0.004 to 0.018) | **+0.007 (0.000 to 0.013)** |
| timing, advanced - beginner (3 groups) | -0.012 (-0.055 to 0.030) | +0.016 (-0.019 to 0.044) | **+0.037 (0.010 to 0.059)** |
| articulation, advanced - beginner | -0.023 (-0.095 to 0.044) | +0.005 (-0.045 to 0.065) | +0.021 (-0.022 to 0.070) |

(95% CIs.) The only CI that excludes 0 is timing in the **context-confounded** pooled model
(advanced about 0.04 R² more coherent than beginners). It shrinks with a context term and
reverses sign within matched contexts.

*[Post-audit fix 2; this replaces "the same pattern D-10 found for tier B".]* That does **not**
show the pooled effect is context. The pooled effect comes entirely from teacher and virtuoso
clips, and there skill and context cannot be separated: every virtuoso clip is a concert and
nearly every teacher clip is a demo. Going from A3 to A1 drops the context and the top two
levels together. With child professionals as the only "advanced" group (levels 1-4, any
context, no context term), timing advanced - beginner is +0.018 (95% CI -0.020 to 0.062;
402 performances, 106 pieces), against +0.037 (0.010 to 0.059) with all levels. So the data
allow only this: the pooled timing effect sits at the top of the scale, where context and skill
are collinear. "It is context" and "it needs the top levels" cannot be told apart here.

### Secondary

- **S1 `concave_excess`** (cadence phrases): A1 `b_rank` +0.006 (-0.043 to 0.056), inconclusive
  (SESOI 0.02). Practice stratum -0.055 (-0.113 to 0.003); performance stratum +0.079
  (-0.028 to 0.183). Pooled confounded +0.011 (-0.007 to 0.026).
- **S2 velocity** (descriptive, excluded from claims): A1 `b_rank` +0.142 (-0.015 to 0.482);
  the SD of velocity R² is 4.1 because of blowups (below), so see the post-hoc table. Raw medians
  in matched contexts fall with level (adult beginner 0.53, child professional 0.27, teacher
  0.24), which is not interpretable on Transkun velocity.
- **S7 difficulty.** PSyllabus joins 51% of gated performances (555; 119 pieces). In A1 with a
  difficulty term and no piece FE (229 performances, 57 pieces): articulation `b_rank` -0.002
  (-0.030 to 0.026), timing +0.012 (-0.002 to 0.026); harder pieces have lower articulation
  coherence (-0.031 per difficulty point, -0.054 to -0.009). With piece FE, `rank x difficulty`
  is -0.007 (-0.015 to 0.002) for articulation and -0.000 (-0.009 to 0.007) for timing: no sign
  that the skill effect depends on difficulty.
- **S8 leave-piece-out prediction of skill rank** (A1 sample, 388 performances, 106 pieces, 5
  piece folds): covariates only (note rate, duration, practice vs performance) Spearman 0.522
  (0.429 to 0.601), within-piece pair accuracy 0.650 (0.589 to 0.719). Adding the coherence
  features: Spearman 0.502, pair accuracy 0.590. Difference -0.020 (-0.045 to 0.002) and
  -0.061 (-0.106 to -0.017). *[Post-audit fix 1; this replaces "coherence makes held-out skill
  prediction worse, not better".]* The registered -0.061 comes from 3 short-score rows (Czerny
  Op. 101, fewer than 12 written bars, articulation R² -2.75 and -0.96 used as ridge features).
  With at least 12 written bars (385 performances, 105 pieces), pair accuracy is 0.641 without
  and 0.608 with coherence: difference **-0.032 (-0.074 to +0.012)**, Spearman difference -0.017
  (-0.039 to 0.005). So coherence **adds nothing** to leave-piece-out skill prediction beyond
  note rate and duration; it is not shown to make it worse. Most of the predictable skill
  signal is note rate (advanced players play faster pieces faster).

### Transcription-noise floor (same performance, Disklavier vs transcribed; ASAP scores)

| Outcome | Transcriber | Pairs | Disklavier median | Transcribed median | Median diff | Median abs diff | Spearman across pairs |
|---|---|---|---|---|---|---|---|
| articulation | Aria-AMT | 59 | 0.221 | 0.184 | -0.033 | **0.080** | **0.36** |
| articulation | Transkun V2 | 6 | 0.350 | 0.426 | +0.143 | 0.143 | 0.88 |
| timing | Aria-AMT | 59 | 0.095 | 0.085 | -0.001 | 0.008 | 0.95 |
| timing | Transkun V2 | 6 | 0.114 | 0.103 | -0.003 | 0.012 | 0.58 |
| concave_excess | Aria-AMT | 51 | 0.100 | 0.115 | 0.000 | 0.000 | 0.96 |
| concave_excess | Transkun V2 | 6 | 0.100 | 0.275 | +0.136 | 0.136 | 0.03 |
| velocity (descriptive) | Aria-AMT | 59 | 0.224 | 0.217 | -0.002 | 0.037 | 0.76 |
| velocity (descriptive) | Transkun V2 | 6 | 0.282 | 0.284 | +0.010 | 0.012 | 0.58 |

Reading it (*[post-audit fix 3: both claims below are qualified as Aria-AMT results]*):

- **Timing-residual coherence survives Aria-AMT transcription.** The typical change (0.008 R²)
  is about one SESOI per level step, and the ranking across performances is kept (0.95 on 59
  Aria-AMT pairs; 0.89 within piece).
- **Articulation coherence does not survive Aria-AMT transcription.** On 59 Aria-AMT pairs the
  typical change is 0.08 R² (the whole five-step SESOI is 0.05) and the ranking across
  performances is mostly lost (Spearman 0.36; 0.07 within piece). Articulation needs key-release
  times, and transcribers estimate offsets far worse than onsets.
- **Transkun (MAJEPPA's transcriber) is unresolved.** On its 6 pairs, timing Spearman is 0.58
  (bootstrap 95% CI 0.00 to 1.00) and articulation 0.88 (0.49 to 1.00) with a +0.14 shift. Six
  pairs cannot establish either "survives" or "fails" for Transkun. Timing's robustness on
  Transkun rests on D-10's onset-level check (onset robust SD 9.3 ms, timing features about
  1%), not on this table.
- So, on the Aria-AMT evidence, **articulation coherence on transcribed MIDI is not a trustworthy
  skill measure**, and its inconclusive result above may be mostly transcription noise. Dropping
  it from H4 on transcribed MIDI stays the conservative choice.
- `concave_excess` is stable under Aria-AMT but moves by +0.14 on the 6 Transkun pairs, with no
  ranking kept; treat MAJEPPA `concave_excess` as low-confidence.
- Limit (as in D-10): these are fast expert competition recordings. The noise on phone
  recordings of home pianos, much of MAJEPPA's beginner material, is not measured.

### Post hoc (added after the results were seen; not in the verdict)

Small MAJEPPA scores slip past `n_blocks >= 3`: the Czerny Op. 101 etudes have 8 bars numbered
0-8, which makes three 4-bar blocks (one of a single bar). They give velocity R² down to -80 and
articulation down to -2.7 (the worst articulation value, -4.7, is a Czerny Op. 101 No. 13 clip
too). Variants, A1 / A2 / A3 `b_rank` with covariates (95% CI):

| Outcome | Variant | A1 matched | A2 context FE | A3 no context |
|---|---|---|---|---|
| articulation | >= 12 score bars (385 in A1) | +0.003 (-0.020 to 0.024) | -0.000 (-0.016 to 0.016) | +0.001 (-0.007 to 0.008) |
| articulation | + within-piece percentile rank | +0.023 (-0.028 to 0.068) | -0.000 (-0.033 to 0.036) | +0.006 (-0.010 to 0.023) |
| timing | >= 12 score bars | +0.005 (-0.013 to 0.021) | +0.008 (-0.004 to 0.019) | +0.007 (0.000 to 0.012) |
| timing | + within-piece percentile rank | +0.006 (-0.042 to 0.050) | +0.012 (-0.023 to 0.045) | +0.008 (-0.011 to 0.022) |
| velocity (descriptive) | >= 12 score bars | +0.019 (-0.005 to 0.039) | +0.031 (0.008 to 0.048) | +0.017 (0.006 to 0.026) |

Flooring R² at -1 changes nothing once the 12-bar rule is applied. The primary reading does not
change: every A1 CI includes 0. Velocity coherence (excluded from claims) is the only channel
with a positive pooled trend, and its A1 CI includes 0.

## Verdict (Provisional)

Audited status (2026-09-28): **Confirmed with caveats** by `eval-auditor`. The inconclusive
reading holds. The six required text fixes from the Audit section are applied in place (each
flagged *[Post-audit fix N]*) and listed under "Post-audit corrections" at the end.

**H4 on MAJEPPA: inconclusive, by the pre-registered rule.**

- Articulation coherence: inconclusive (`b_rank` +0.008, 97.5% CI -0.019 to 0.034). And the
  noise floor shows it is not measured reliably on transcribed MIDI.
- Timing-residual coherence: inconclusive (`b_rank` +0.005, 97.5% CI -0.014 to 0.021). On
  Aria-AMT evidence plus D-10's Transkun onset check, this channel survives transcription, so
  the null here is a real lack of signal at this sample size, not noise from transcription.
  *[Post-audit fix 3: qualified; the 6 Transkun pairs alone cannot show this.]*
- Neither channel is falsified: the CIs still allow a trend of 0.01 to 0.02 per level step.
- **Power** *[post-audit fix 4]*: falsification was nearly out of reach. The 97.5% CI
  half-widths (articulation 0.027, timing 0.018) are 2-3 times the SESOI (0.01), so a CI entirely
  below +0.01 needs a point estimate below about -0.017 (articulation) or -0.008 (timing). With
  a true slope of 0, the chance of that is about 8% (articulation) and 16% (timing) (normal
  approximation from the bootstrap SE; eval-auditor). "Inconclusive" was therefore the expected
  outcome of this design under a null. A decisive MAJEPPA-style test would need a half-width
  below the SESOI, roughly 3-7 times the within-piece sample.
- In plain terms: within matched recording contexts, no coherence measure separates MAJEPPA skill
  levels. The one pooled effect (timing, advanced about 0.04 above beginners) comes from teacher
  and virtuoso clips, where skill and context cannot be separated; with levels 1-4 only it is
  +0.018 (-0.020 to 0.062). So it is not shown to be skill, and not shown to be context either.
  *[Post-audit fix 2: this replaces "disappears once context is held fixed".]* Coherence adds
  nothing to leave-piece-out skill prediction beyond note rate and duration (-0.032, -0.074 to
  +0.012, with at least 12 written bars; *[post-audit fix 1]*). MAJEPPA does not support H4. It
  does not refute it either: the matched-context sample has no virtuosos, only 9 teacher clips,
  and mostly beginners through child professionals, and the design could rarely reach
  "falsified".

## Threats to validity

- **Context and skill cannot be separated at the top of the scale.** Every virtuoso clip is a
  concert, most teacher clips are demos, so A1 covers levels 1-4 (plus 9 teachers).
- **Transcription.** Articulation coherence changes by more than the effect of interest between
  Disklavier and Aria-AMT transcription of the same performance (above); Transkun is not
  resolved by 6 pairs. Beginner phone recordings are likely noisier still, which would lower
  beginners' coherence and create a spurious skill effect; that is one reason the pooled timing
  effect might be context, not skill (it is not shown either way; see fix 2).
- **Power.** Under a zero slope, "falsified" had only about 8% / 16% probability (fix 4).
- **Gate bias.** Trusted alignment removes 29-36% of beginners (D-10), keeping the more fluent
  ones. This favours a null.
- **Performer identity.** `recording_id` is a video, not a person; recurring channels would make
  CIs too narrow.
- **Skill order** among the 6 levels is assumed (child vs adult beginners); the 3-group coding
  gives the same reading.
- **Short scores.** `n_blocks >= 3` admits 8-bar scores with a bar 0 (post hoc above); the
  verdict holds without them.
- **Difficulty** is absorbed by piece FE; the join covers only 51% of performances and is a
  surname + catalogue-number match (not checked by hand).
- **No ratings.** H4's second half (correlation with rated quality) is not tested here.

## Audit (2026-09-28)

Auditor: `eval-auditor`. Verdict: **Confirmed with caveats.** H4 on MAJEPPA is inconclusive by the
pre-registered rule. That reading survives every check below. Three supporting claims overreach
and must be reworded (required fixes 1-3).

### Reproduction

- `analyze.py --boot 2000` was rerun into a scratch copy of `artifacts/` (copied `coherence.csv`
  and `noise_pairs.csv`; `ART` patched). All nine output CSVs are **byte-identical** to the
  artifacts (`counts`, `context_by_level`, `effects`, `level_means`, `verdict`, `difficulty`,
  `lpo`, `effects_posthoc`, `noise_floor`). Wall time 2 min 50 s.
- `build.py` and `noise_floor.py` were not rerun (about 30 min). The inputs to the analysis were
  taken as given.
- The first analysis run (before the post-hoc section was added) printed the same verdict row
  (+0.0082 [-0.0193, 0.0344]; +0.0045 [-0.0144, 0.0214]; ml-researcher transcript). Adding the
  post-hoc code did not change the primary numbers.

### Pre-registration

- `head -191 README.md` hashes to `c44a4b74...8517`. It is identical to the README content of the
  ml-researcher's `Write` at 04:05:05 UTC (23:05 CDT); the only difference is one trailing blank
  line. It was written before `build.py` existed.
- Before the header: one pilot performance. The first attempt crashed on a missing argument. The
  second printed one coherence summary, not tied to any skill comparison.
- **After the header, not disclosed:** a 2-score test of `build.py` (31 performances; one row
  printed, a piano teacher's coherence), and an `analyze.py --boot 20` smoke test on that file.
  The smoke test crashed with empty effect tables, so no skill estimate was seen. Two code fixes
  followed before the full run: `n_score_bars` in `build.py`, and the PSyllabus key in
  `analyze.py`. Both are harmless. Disclose them under Deviations (fix 5).
- The decision rule in `analyze.py::verdict` matches the text: 97.5% percentiles (1.25, 98.75),
  SESOI 0.01, supported = lower bound > 0 **and** 0 <= d_int <= d_adv (3-group dummies,
  covariates, context FE), falsified = upper bound < 0.01. Model: within-piece demeaning of y and
  all regressors (Frisch-Waugh), a practice/performance dummy, and log note rate and log duration.
  Piece FE are re-estimated in every resample. This is as registered.

### Checks and findings

1. **The n_blocks bug and the primary channels.** 24 gated performances have fewer than 12
   distinct written bars, all Czerny Op. 101 (No. 70, 13, 12, 47, 71). Three are in A1 (two
   child-beginner clips of No. 70, articulation R² -2.75 and -0.96). The articulation estimate
   was contaminated; timing was hardly touched. Primary rerun with at least 12 written bars (the
   same 385 rows at >= 16 bars):

   | Channel | Registered | >= 12 bars | >= 12 bars, clustered by piece | >= 12 bars, no covariates |
   |---|---|---|---|---|
   | articulation | +0.0082 [-0.0193, 0.0344] | +0.0030 [-0.0231, 0.0270] | +0.0030 [-0.0196, 0.0247] | +0.0148 [-0.0104, 0.0356], groups ordered |
   | timing | +0.0045 [-0.0144, 0.0214] | +0.0047 [-0.0144, 0.0222] | +0.0047 [-0.0117, 0.0212] | +0.0092 [-0.0093, 0.0245], not ordered |

   (97.5% CIs, n = 385 or 388, 105 or 106 pieces.) Every variant is inconclusive. The 3-group
   point estimates do not change (the Czerny No. 70 piece has beginners only). Without covariates
   the articulation groups become ordered (+0.019, +0.026). Log note rate may partly mediate
   skill, so the covariate choice matters for the ordering, but not for the verdict.
2. **Bootstrap unit and performers.** In A1, each of the 388 rows is its own `recording_id`, and
   across MAJEPPA each recording is one YouTube video (3,946 videos, 3,946 recordings). So the
   "cluster" bootstrap is in effect a row bootstrap. MAJEPPA releases no channel or uploader
   field, so repeat performers cannot be checked. If channels recur, the CIs are too narrow. A
   piece-clustered bootstrap gives similar or narrower CIs (table above). Wider CIs cannot turn
   "inconclusive" into support or falsification, so the verdict holds either way. This caveat
   applies to the pooled "CI excludes 0" claim (A3), not to the verdict.
3. **Composition and power.** A1: child beginner 85, adult beginner 117, adult intermediate 99,
   child professional 78, piano teacher 9, virtuoso 0. Practice 254, performance 134. Median 3
   performances per piece; 37 of 106 pieces have exactly 2. In 57 of 106 pieces the performers
   are only one level step apart. Only 5% of the within-piece rank variance comes from
   pieces whose sole contrast is child vs adult beginner (the assumed order). **The falsification
   branch was nearly out of reach.** The 97.5% half-widths (articulation 0.027, timing 0.018) are
   2-3 times the SESOI, so a CI entirely below +0.01 needs a point estimate below about -0.017 or
   -0.008. With a true slope of 0, the chance of that is about 8% (articulation) and 16% (timing)
   (normal approximation from the bootstrap SE). "Inconclusive" was the expected outcome of this
   design under a null. Say so (fix 4).
4. **The pooled timing effect is not shown to be context.** With no context term, advanced minus
   beginner is +0.037 (95% [0.010, 0.059]). It is carried entirely by teacher and virtuoso clips:

   | Timing, advanced - beginner, no context term | n (pieces) | Estimate (95% CI) |
   |---|---|---|
   | Registered A3 (all levels) | 991 (228) | +0.037 [0.010, 0.059] |
   | Child professionals as the only "advanced" (levels 1-4, any context) | 402 (106) | +0.018 [-0.020, 0.062] |
   | Teachers and virtuosos as the only "advanced" | 905 (222) | +0.037 [0.008, 0.060] |
   | Matched contexts, no context term | 331 (89) | +0.016 [-0.026, 0.058] |

   Every virtuoso clip is a concert and nearly every teacher clip is a demo. The pooled effect
   therefore sits exactly where skill and context are perfectly confounded. Going from A3 to A1
   drops the context **and** the top two levels together. "It disappears once context is held
   fixed" and "it is context, the D-10 pattern" cannot be told apart from "it needs the top of the
   scale". The data allow only: *the pooled effect comes from teacher and virtuoso clips, where
   context and skill cannot be separated* (fix 2).
5. **The S8 leave-piece-out claim is driven by the short-score rows.**

   | S8 variant (A1, 5 piece folds) | Covariates pair acc. | + coherence | Difference in pair accuracy [95%] | Difference in Spearman [95%] |
   |---|---|---|---|---|
   | Registered | 0.650 | 0.590 | -0.060 [-0.106, -0.017] | -0.020 [-0.045, 0.002] |
   | >= 12 written bars | 0.641 | 0.608 | -0.032 [-0.074, +0.012] | -0.017 [-0.039, 0.005] |
   | >= 12 bars + R² floored at -1 | 0.641 | 0.608 | -0.032 [-0.074, +0.012] | -0.017 [-0.039, 0.005] |
   | >= 12 bars, timing coherence only | 0.641 | 0.629 | -0.012 [-0.036, +0.008] | -0.003 [-0.014, 0.008] |

   Removing 3 of 388 rows (R² -2.7 and -1.0 as ridge features) makes the CI include 0. The
   supportable claim is "coherence adds nothing to leave-piece-out skill prediction beyond note
   rate and duration". "Coherence makes prediction worse" is not supported (fix 1).
6. **Noise floor.** It uses the same 65 pairs as D-10 (`transcription_pairs.csv`: identical
   `trans_path` set, 59 Aria-AMT, 6 Transkun V2). They cover 54 distinct ASAP performances in 44
   pieces, so the pairs are not fully independent. Bootstrap CIs over pairs:
   - **Aria-AMT.** Articulation ρ 0.36 [0.09, 0.59]; within piece it is 0.07 (18 pairs,
     7 pieces). Timing ρ 0.95 [0.87, 0.98]; within piece 0.89. Across pieces, the Spearman
     partly reflects differences between pieces, but the within-piece values, which are what a
     piece-FE analysis needs, tell the same story.
   - **For scale.** The articulation |Δ| (0.080) exceeds the typical within-piece spread among
     MAJEPPA A1 performers (median |deviation| 0.068). Timing |Δ| (0.008) is small beside its
     0.047.
   - **Transkun** (MAJEPPA's transcriber, n = 6). Timing ρ 0.58 [0.00, 1.00]; articulation ρ 0.88
     [0.49, 1.00] with a +0.14 shift.

   So "articulation fails and timing survives" is shown for **Aria-AMT**. For Transkun, the 6
   pairs cannot establish either statement. Timing robustness on Transkun rests on D-10's
   onset-level result (onset robust SD 9.3 ms, timing features +1%), not on this table. The
   DECISIONS drop of articulation from transcribed-MIDI H4 remains a sound conservative choice,
   but its wording should name the transcriber (fix 3).
7. **Piece difficulty (S7)** and the concave_excess secondary were checked for code consistency
   only. The PSyllabus join is exact surname + catalogue, unchecked by hand, as the README says.

### Required fixes (text only; no rerun needed)

1. S8 (Results and Verdict): replace "coherence makes held-out skill prediction worse" with
   "adds nothing". Report the >= 12-bar row (pair accuracy -0.032 [-0.074, +0.012]) and say the
   registered -0.061 comes from 3 short-score rows.
2. The context paragraph, the verdict's plain-terms bullet and the EXPERIMENTS row: say that the
   pooled timing effect comes from teacher and virtuoso clips, where skill and context are
   collinear. Do not say it "disappears once context is held fixed", as if context were shown to
   be the cause. Add the levels 1-4 row (+0.018 [-0.020, 0.062]).
3. Noise floor: qualify "timing survives / articulation fails" as Aria-AMT results, with the
   Transkun CIs (timing ρ 0.58 [0.00, 1.00], articulation 0.88 [0.49, 1.00]). The verdict bullet
   "the null here is a real lack of signal, not noise from transcription" should say "on Aria-AMT
   evidence plus D-10's Transkun onset check".
4. Add the power note: under a zero slope, falsification had about 8% / 16% probability, so
   inconclusive was the expected result. A decisive MAJEPPA-sized test would need a CI half-width
   below the SESOI, roughly 3-7 times the within-piece sample.
5. Deviations: disclose the 2-score `build.py` test and the `--boot 20` smoke test (crashed, no
   estimates) run after the pre-registration, and the two code fixes that followed.
6. Run record: the code hash prefixes are attached to the wrong files. The actual prefixes are
   `build.py` 47fe752440fee678, `noise_floor.py` 1520b2eda7799eec, `analyze.py` 98b24c0564b0926d.
   The Command section says `--workers 6` for `noise_floor.py`; it ran with 4 (the Run record
   says 4).

Audit scripts (scratch, not kept): the patched `analyze.py` copy and an `audit.py` that calls its
functions (`design`, `fe_ols`, `samples`, `run_lpo`) with the variants above; bootstrap 2,000,
seed 0.

## Post-audit corrections (2026-09-28)

By `ml-researcher`. Text only: no code was changed and nothing was rerun. The six required fixes
from the Audit section are applied **in place** above, each flagged *[Post-audit fix N]*. The
pre-registered header (the first 191 lines) is unchanged and still hashes to
`c44a4b74...8517`. Its Status line and its Command block (`noise_floor.py --workers 6`) stay as
registered; the audited status is in "Verdict", and the actual worker count is in the Run record.

| Fix | What changed | Where |
|---|---|---|
| 1 | S8: "coherence makes held-out skill prediction worse" becomes "adds nothing". The >= 12-bar row is reported (pair accuracy -0.032 [-0.074, +0.012]); the registered -0.061 is traced to 3 short Czerny Op. 101 rows. | Results, Secondary S8; Verdict, plain-terms bullet |
| 2 | The pooled timing effect is attributed to teacher and virtuoso clips, where skill and context are collinear, not to context. The levels 1-4 row is added (+0.018 [-0.020, 0.062]). "The same pattern D-10 found" and "disappears once context is held fixed" are removed. | Results, Context; Verdict, plain-terms bullet; Threats, Transcription |
| 3 | "Timing survives / articulation fails transcription" is qualified as Aria-AMT results. Transkun (n = 6) is unresolved: timing ρ 0.58 [0.00, 1.00], articulation 0.88 [0.49, 1.00]. The timing verdict bullet now rests on "Aria-AMT evidence plus D-10's Transkun onset check". | Results, noise-floor reading; Verdict, timing bullet; Threats, Transcription |
| 4 | Power note: under a zero slope, "falsified" had about 8% (articulation) / 16% (timing) probability, so inconclusive was the expected outcome; a decisive test needs roughly 3-7 times the within-piece sample. | Verdict, new Power bullet; Threats, new Power bullet |
| 5 | The post-pre-registration 2-score `build.py` test, the crashed `analyze.py --boot 20` smoke test (no estimates seen) and the two code fixes that followed are disclosed. | Run record, Deviations item 3 |
| 6 | Code hash prefixes re-attached to the right files (`build.py` 47fe752440fee678, `noise_floor.py` 1520b2eda7799eec, `analyze.py` 98b24c0564b0926d; re-verified against the files on disk). `noise_floor.py` ran with 4 workers, not the registered 6. | Run record, Code and Commands |

The same top-level/context caveat applies to D-10's tier-B conclusion (DECISIONS, 2026-09-28,
"R-09 is Confirmed with caveats"). A post-audit note was added to
`docs/specs/skill-control-check.md`.
