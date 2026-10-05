# S-04 protocol: blind pairwise preference among expert performances (H7)

Ticket: S-04 (design; S-05 app and S-06 analysis follow). Hypothesis: H7. Protocol version 0.1,
2026-09-29.
Status: **DRAFT, not frozen.** Nothing here has been run on a listener and no stimulus has been
built. The design choices marked "decision" in section 11 need the lead and Henry. After they are
made and the pilot (section 8) has run, the lead records the sha256 of this file in `DECISIONS.md`
and later changes go in a "Deviations" section, never in place. Recruiting, consent approval,
payment and hosting are Henry's (O-02).

Where things are (and will be):

| What | Path |
|---|---|
| Design simulation (this protocol, section 6) | `src/pianolens/study/power_s04.py`, `scripts/power_s04.py` -> `data/interim/study_s04/power/` |
| Bradley-Terry fit | `src/pianolens/eval/bradley_terry.py` (`fit_bradley_terry`) |
| BT standard errors, SSR (draft, moves to the S-06 analysis module) | `pianolens.study.power_s04.bt_standard_errors`, `_ssr` |
| Excerpt cutting and rendering (reused from S-03) | `src/pianolens/study/excerpt.py`, `pianolens.audio.render`, `scripts/build_study_s03.py` (pattern) |
| Features | `pianolens.features.extract.segment_features`, `pianolens.features.interpretation.interpret` |
| Stimulus spec and build (to write, S-04 build step) | `study/stimuli-S04.json`, `scripts/build_study_s04.py` -> `data/interim/study_s04/` |
| Study app (S-05) | `study/app/` with a `study=S04` flag (section 12) |

## 1. Question

Among expert performances of the same passage, what makes listeners prefer one over another?

H7 (plan, section 2): "Among expert performances, blind pairwise preference is explained
substantially by interpretable features (beyond 'closeness to the mean')." Falsified if
"features explain no more than distance-to-mean alone".

Why distance-to-mean is the null to beat: Repp 1997 found that the average of ten student
performances of Träumerei was rated second-highest in quality and second-lowest in individuality,
and that the expert-average timing pattern was rated highest of 30 synthesized performances
(landscape 1.3). So "sound like the average expert" is a strong, cheap predictor of preference.
H7 asks whether the interpretable features that PianoLens computes (tempo, rubato, dynamics,
voicing, articulation, pedal, timing control) add to it. If they do not, tier D can stay a
typicality measure and the interpretable features are only descriptive. If they do, the features
can carry weights in a preference model.

This is the "taste" regime of the plan (1.3): audio models reach 49-60% on pairs of Chopin
Competition entrants (PianoJudges, landscape 3.3). Listeners are expected to disagree, so the
study measures the listener ceiling as well (section 7.4).

## 2. H7 test (draft pre-registered reading)

For every passage, the BT scale (section 7.1) gives one score per performance, centred within
the passage. Two regressions of these scores are fitted with passage-centred predictors and no
intercept:

- **M0 (null):** `d2m`, one distance-to-mean number per performance (section 5.2).
- **M1:** `d2m` plus the seven interpretable features of section 5.3.

Both are evaluated **leave-one-piece-out**: each passage's scores are predicted from coefficients
fitted on the other pieces (CLAUDE.md rule 1). Held-out R² is pooled over the held-out
passages: `R2 = 1 - sum SSE / sum SST`, with SST the within-passage sum of squares of the
observed scores.

The statistic is the **reliable-variance gain**

    G = (R2_M1 - R2_M0) / SSR

where SSR is the pooled scale separation reliability of the BT scores (7.2). G is the share of
the reliable between-performance variance that the features explain beyond `d2m`. Its 95% CI
comes from a bootstrap over passages (2,000 resamples of the per-passage SSE and SST sums).

Margin: delta = 0.10 (draft, section 11 decision 1): the features must add at least a tenth of
the reliable variance to count as "substantially".

- **Supported:** the lower 95% bound of G is above 0 **and** G is at least delta.
- **Falsified:** the upper 95% bound of G is below delta (the features add less than delta).
- **Inconclusive:** anything else.

Under H7-false the held-out G is usually negative, because M1 spends seven extra coefficients
on noise; the reading counts that as evidence against H7, which is the intended behaviour of a
held-out test. Implementation of the reading: `pianolens.study.power_s04.h7_verdict`.

Secondary statistics, reported but not used for the verdict:

- Held-out pairwise accuracy of the raw judgements under M0 and M1 (the plan's "Preference"
  metric, section 4), with the rater-parity ceiling (7.4).
- The same test with `d2m` replaced by tier D typicality (`interp__*_typicality_median`), which
  is a likelihood under the expert distribution, not a distance (F-06 design).
- The same test with the three `d2m` channels as three separate M0 predictors.
- Per-feature coefficients with passage-bootstrap CIs (descriptive).

## 3. Stimuli

### 3.1 Sources: exact capture only

Only performances captured as MIDI by the instrument itself are used as stimuli:

- **(n)ASAP** (Disklavier, Yamaha e-Competition via MAESTRO; CC BY-NC-SA 4.0; DATASETS.md).
  Ground-truth note alignments ship with the set.
- **Vienna 4x22** (Bösendorfer SE sensor, 4 excerpts x 22 pianists; CC BY 4.0).

PianoCoRe transcriptions (Aria-AMT, Transkun, ATEPP, ByteDance; about 99.6% of PianoCoRe rows,
DATASETS.md) are **not** used as stimuli. After rendering, transcription errors in velocity,
pedal and extra notes would be a cue that has nothing to do with interpretation (DECISIONS after
D-10: velocity on transcribed MIDI is low-confidence). PianoCoRe is used only as a reference
distribution for the tempo channel of `d2m` (5.2).

What "expert" means here: e-Competition entrants and the Vienna 4x22 pianists, in the same
capture setup per passage. No skill label is shown or used.

### 3.2 Passages

Counts measured on this repo's copy (2026-09-29, `asap_index()`, `robust_note_alignment == 1`,
performer ids from the file-name heuristic in `pianolens.data.asap`, which can merge pianists
with the same surname key):

- 20 ASAP pieces have at least 10 distinct performers, 31 have at least 8.
- Largest: Chopin Op. 10 No. 8 (28 performances, 27 performers), Op. 10 No. 1 (25, 25),
  Beethoven Op. 53/1 (25, 24), Liszt S.141 No. 3 (29, 24), Chopin Op. 25 No. 11 (24, 23),
  Op. 10 No. 4 (22, 21), Beethoven Op. 110/1 (21, 21), Haydn Keyboard Sonata 50-1 in ASAP's numbering (18, 17), Liszt
  S.139 No. 10 (16, 16), Chopin Op. 23 (17, 15), Beethoven Op. 31 No. 2/1 (14, 14), then
  Chopin Op. 10 No. 12, Op. 52, Op. 25 No. 10, Schubert D. 899 No. 3 (12 or 13 each), Chopin
  Op. 31, Liszt S.139 No. 5, Chopin Op. 10 No. 5, Beethoven Op. 81a/1 (11 each), Chopin Op. 10
  No. 2 (10).
- Vienna 4x22 adds 4 passages with 22 pianists each.

Base design (section 6): **24 passages, one per piece** (the 20 ASAP pieces above plus the 4
Vienna excerpts), **10 performances each**, 240 items. Two passages from one piece would let the
design reach 36 passages, but then cross-validation folds must be whole pieces.

Known imbalance: 11 of the 20 ASAP pieces are Chopin, many of them études with fast uniform
figuration, where interpretive freedom is mostly tempo and dynamics. Section 11 decision 3 asks
whether to swap some for 8- or 9-performer pieces (Bach, Beethoven, Schubert) to widen the
repertoire.

Passage rules (fixed before listening; no choice by ear):

- One phrase or phrase group ending at a cadence, **15-25 s at the median tempo** of the
  passage's performances, and at least 8 written bars where the tempo allows
  (`ExtractConfig.coherence_min_bars`; DECISIONS after D-10 raises the coherence minimum to 12
  written bars, which is one reason coherence is exploratory here, 5.3).
- The opening of the piece unless it is shorter than the rule allows; ASAP performances are
  complete, so a later passage is possible where the opening is unsuitable.
- Every performance of a passage covers the same score bars (repeat structure checked in the
  alignment; a performance that plays a different repeat structure in the window is not used).
- Cut with the S-03 `excerpt()` (score bars through the alignment, lead-in and release as S-03).
- For the pieces also used in S-03 (Vienna excerpts, Schubert D. 899 No. 3, and Bach BWV 848,
  which is below 10 performers here and is not in the base set): the performance used in S-03 is
  excluded, and S-03 participation is recorded (section 11 decision 6).

### 3.3 Choosing the performances

- Eligible: robustly aligned, one performance per performer (the earliest in the file list when
  a performer has several), and **no tier A wrong-pitch or extra note** in the window
  (`corr__wrong_pitch_rate == 0` and `corr__extra_rate == 0` on the cut; ornaments whitelisted as
  in F-02). If fewer than 10 are clean, the ones with the fewest errors are added and
  `corr__error_rate` enters both M0 and M1 as a nuisance covariate.
- From the eligible performances: 10 by **stratified random draw on overall tempo** (F-03
  `tempo__log_bpm` on the window; five tempo bands, two per band, seeded). Stratifying keeps the
  full tempo range in the set without choosing by ear. The seed and the draw are recorded in the
  spec.

### 3.4 One renderer, one loudness

As S-03 (section 3.2 there): Salamander C5 Light SF2, FluidSynth 2.6.1, pinned settings, mono,
44.1 kHz; trimmed, faded, then **-23 LUFS integrated**. Loudness normalization removes each
pianist's overall level, which is an interpretive choice; it is still required (rules/study.md),
and the analysis keeps the velocity features, which are relative within the passage. The
manifest records render config hash, soundfont hash, FluidSynth version and code state.

## 4. Procedure

### 4.1 Session

1. Consent (section 10), five background questions (as S-03 section 9, plus "Did you take part in
   the earlier PianoLens listening study?").
2. Volume setting on one clip, then the Woods et al. 2017 headphone check (as S-03 4.1).
3. Instructions: "You will hear two performances of the same music. Which do you prefer?" No
   performer names, no mention of competitions or skill (rules/study.md).
4. 1 practice pair, then the trials, with a break halfway.
5. Debrief and JSON download.

### 4.2 Trials per listener (base)

- **50 test pairs**, each two performances of one passage (A then B, each played once, no
  replay), "Which performance do you prefer?". Answers are enabled after B ends; the response time
  is recorded from then.
- **4 repeat pairs**: four of the listener's own test pairs again, in the other order, spread
  through the second half. They measure within-listener consistency and are not used in the BT
  fit.
- **3 catch pairs**: a performance against itself with gross wrong notes (S-01 `wrong_notes` at
  rate 0.3, as the S-03 catch). "Correct" means preferring the unaltered one.
- Listening time with 20 s clips: about 36 minutes for the 50 test pairs
  (`session_minutes_s04`), about 42 minutes with repeats, catch and practice. With consent and
  checks the session is about 50 minutes. Shorter clips or 40 test pairs reduce this (section 6
  has the 40-pair variant).

### 4.3 Pair schedule (non-adaptive)

- All within-passage unordered pairs (45 per passage with 10 performances; 1,080 for 24
  passages) are laid out as a sequence of shuffled permutations of the full pair list, and
  listener `l` takes positions `50 l .. 50 l + 49`. Every pair is therefore judged about equally
  often, and each listener hears a spread of passages (`schedule_pairs`).
- **Position.** Each pair's order alternates between its occurrences, so every pair is heard in
  both orders about equally often (listeners favour the second item; Kroger and Margulis 2017).
- Within a listener the trial order is shuffled with a seeded PRNG (seed = participant code), the
  same passage is not played twice in a row where it can be avoided, and catch pairs are spread
  evenly.
- Pair selection is **not adaptive**, so Bramley and Vitello's caveat (adaptive pairing inflates
  SSR) does not apply. An adaptive variant is not planned for S-04.

### 4.4 Comparisons per item

With N listeners, 50 test pairs each, 24 passages and 10 performances, each item is in
`2 x 50 N / 240 = 0.42 N` comparisons on average.

- The rules/study.md target of at least 20 comparisons per item (total judgements at least
  10 x 240 = 2,400) is met from **N = 48** pooled.
- Because musicians and non-musicians are also analysed separately, each group alone should
  reach 20 as well: **N = 96** (48 per group). This also gives each split half at least 10 per
  item, as Kinnear et al. 2025 recommend for a new kind of stimulus (landscape 1.4).

## 5. Measures

### 5.1 Listener measures

Chosen performance, position, response time, repeat-pair agreement, catch accuracy, background.

### 5.2 Distance to the mean (`d2m`, the null predictor)

Computed on the cut window of each performance with `interpret()` (F-06), leave-one-out so a
performance is never part of its own reference:

- tempo channel: `ref__tempo_smooth_rms` against the PianoCoRe tier A references of the piece
  (hundreds per piece, transcribed; smooth tempo is the channel least affected by transcription)
  plus all exact-capture performances of the piece;
- velocity channel: `ref__velocity_smooth_rms` against **exact-capture references only** (all
  ASAP / Vienna performances of the piece, not only the 10 stimuli);
- timing channel: `ref__timing_rms` against exact-capture references only (F-08 found a
  reference-provenance mismatch for timing flags: DECISIONS 2026-09-28).

`d2m` is the mean of the three channel values after z-scoring each within the passage.

### 5.3 Interpretable features (M1 adds these seven)

Fixed now so the test cannot be tuned after the data are seen. All from
`segment_features` on the cut window (ASAP and Vienna are exact capture, so velocity features
are full-confidence), z-scored within passage:

| # | Feature | What it captures |
|---|---|---|
| 1 | `ref__rel_log_bpm` | overall tempo relative to the references' median (signed) |
| 2 | `tempo__smooth_log_sd` | amount of rubato |
| 3 | `glob__vel_sd_midi` | dynamic range |
| 4 | `shape__voicing_vel_diff_mean_midi` | melody over accompaniment |
| 5 | `tempo__jitter_rms_beats` | timing unevenness (control) |
| 6 | `glob__art_median_log` | articulation (legato vs detached) |
| 7 | `ctrl__pedal_down_fraction` | amount of sustain pedal |

Exploratory only (not in M1): structural coherence (`shape__coherence_*`; the plan lists "could
reward formulaic playing" as a risk that Phase 4 should check), chord asynchrony, dynamic-marking
compliance, and the typicality measures.

## 6. Design check by simulation

Method (`pianolens.study.power_s04`, `uv run python scripts/power_s04.py --n-rep 200 --seed 0`,
200 simulated studies per cell):

1. For each passage, simulate true strengths `q` (logit units) as `d2m` part + feature part +
   unexplained part; the feature part is orthogonal to `d2m`, so `r2_feat` is exactly the share
   of `var(q)` the features add beyond `d2m`. Three of the seven features carry the effect.
2. Simulate listeners (each with their own offsets per performance: taste), the schedule of
   section 4.3, position bias and lapses.
3. Analyse as pre-registered: BT per passage (ridge 0.1, see 7.1), SSR, split-half SHR over
   listeners (one random split per simulated study), SSR for one stratum alone, then the
   leave-one-passage-out H7 test with a 500-resample passage bootstrap and the section 2 reading.

**Every simulation parameter is an assumption, not a measurement.** How much of preference
`d2m` and the features explain, and how much listeners disagree, is what the study measures.

| Assumption | Base value | Varied to |
|---|---|---|
| s.d. of true strength within a passage (logit) | 1.0 | 0.5 |
| Share of it explained by `d2m` alone | 0.15 | 0.3 |
| Extra share explained by the features (the H7 effect) | 0, 0.1, 0.2, 0.3 | |
| Features carrying the effect | 3 of 7 | 1 of 7 |
| Correlation among features / with `d2m` | 0.3 / 0.3 | n/a |
| Feature measurement reliability | 1 | 0.7 |
| Listener taste s.d. (logit) | 0.5 | 1.0 |
| Position bias (logit), lapse | 0.3, 0.02 (as S-03) | n/a |
| Test pairs per listener | 50 | 40 |

Results (base assumptions; medians or proportions over 200 simulated studies; full grid in
`data/interim/study_s04/power/power_grid.csv` and `summary.md`). "r2_feat" is the true extra
share of preference variance the features explain beyond `d2m` (0 = H7 false). "Comparisons"
is per item, pooled.

| Design | N listeners | Comparisons | P(supported), r2_feat 0.2 | r2_feat 0.3 | P(falsified), r2_feat 0 | SSR pooled | P(SSR >= .8) | SSR one stratum | SHR |
|---|---|---|---|---|---|---|---|---|---|
| 12 passages | 48 | 40 | 0.36 | 0.75 | 0.91 | 0.88 | 1.00 | 0.79 | 0.85 |
| 12 passages | 96 | 80 | 0.45 | 0.84 | 0.93 | 0.93 | 1.00 | 0.88 | 0.92 |
| **24 passages** | 48 | 20 | 0.75 | 0.98 | 0.98 | 0.79 | 0.14 | 0.66 | 0.73 |
| **24 passages** | **96** | **40** | **0.87** | **1.00** | **0.99** | **0.88** | **1.00** | **0.78** | **0.85** |
| **24 passages** | 144 | 60 | 0.91 | 1.00 | 1.00 | 0.91 | 1.00 | 0.84 | 0.90 |
| 36 passages | 96 | 27 | 0.96 | 1.00 | 1.00 | 0.83 | 0.99 | 0.71 | 0.79 |
| 36 passages | 144 | 40 | 0.97 | 1.00 | 1.00 | 0.88 | 1.00 | 0.79 | 0.85 |

What the simulation says, under its assumptions:

- **False positives:** P(supported) was 0.000 at r2_feat = 0 in every design and variant.
  Under H7-false the verdict is "falsified" in 89-100% of studies (the held-out gain is negative
  when the features add nothing).
- **Power for H7 comes from passages, not listeners.** At r2_feat = 0.2, 12 passages reach at
  most 0.50 even with 144 listeners; 24 passages reach 0.87 at 96; 36 reach 0.96 at 96.
- **A true effect of 0.1 is at the margin** (delta = 0.10) and is almost never "supported"
  (at most 0.29 over the grid); it is "falsified" in 13-37% of studies, because the held-out
  gain after the cost of seven coefficients is below the margin. This is the price of the
  margin: an effect of about delta is not distinguishable from "less than delta".
- **20 comparisons per item was not enough for SSR .8 here.** At exactly 20 (24 passages,
  48 listeners) the median SSR was 0.79 and only 14% of studies reached 0.8. The rules/study.md
  target is a minimum, not a guarantee; with a true within-passage s.d. of 1 logit and
  listener taste s.d. 0.5, about 40 per item gave SSR 0.88.
- **Per-stratum scales need more listeners.** With 48 per group (N = 96) one group's SSR median
  was 0.78; with 72 per group (N = 144) 0.84.
- **Sensitivity (24 passages, r2_feat 0.2, P(supported) at N = 96 / 144):** smaller true
  spread (s.d. 0.5): 0.55 / 0.74, and pooled SSR only 0.70 / 0.77 (the worst case); more
  listener taste variance (1.0): 0.79 / 0.88; `d2m` explaining 0.3: 0.93 / 0.96; feature
  reliability 0.7: 0.79 / 0.75; one active feature: 0.86 / 0.92; 40 test pairs: 0.80 / 0.89.
- **Accuracy scale:** in the base truth model the best possible pairwise accuracy (true
  strengths) was about 0.70, M0 held-out about 0.57, M1 about 0.61 at r2_feat 0.2. Small
  accuracy differences carry the H7 effect; this is the taste regime.

**Recommendation for O-02 (draft):** 24 passages x 10 performances, **96 listeners (48
musicians, 48 non-musicians), one 50-minute session each** (about 80 listener-hours). Under the
base assumptions this gives 0.87 power for a features effect of 0.2 of the preference
variance, pooled SSR about 0.88, and a reliable falsification when the features add nothing. It
does not give per-stratum SSR of 0.8 (about 0.78); 144 listeners (72 per group, about 120
listener-hours) does. If listeners agree less than assumed (s.d. 0.5), even 144 is not enough,
so an **internal pilot** is pre-registered as in S-03: after the first 12 listeners, re-estimate
the BT spread and the listener-taste variance only (not the H7 contrast), re-run
`power_s04.py` with them, and increase N if needed (N can go up, never down).

## 7. Analysis plan

### 7.1 Scale

- Per passage, fit `fit_bradley_terry` on the test pairs (not repeats, catch or practice) with
  ridge `l2 = 0.1` (`BT_L2`). With about 20 comparisons per item, a performance that wins or
  loses all of them is common in simulation, and its plain maximum-likelihood score is infinite.
  The ridge is a weak Gaussian prior (s.d. about 3.2 logits) that keeps such scores finite.
- Standard errors from the Fisher information of the penalized fit (`bt_standard_errors`).
- Position bias: the logit of P(second chosen) over all test pairs, with a listener-bootstrap CI.
  Every pair is counterbalanced, so position does not bias the scores; it only adds noise. A fit
  with a position term (an extension of `fit_bradley_terry`, S-06) is a robustness check.

### 7.2 Reliability (rules/study.md)

- **SSR** pooled over passages: `(observed variance - mean SE^2) / observed variance`, scores
  centred per passage. Target at least 0.8.
- **SHR**: listeners split at random into halves 1,000 times; per split, the pooled
  within-passage Pearson r of the two half-scales, stepped up with Spearman-Brown; report the
  median and the 2.5-97.5% range. Kinnear et al. 2025 found SHR below 0.7 in 9% of datasets with
  SSR at least 0.8, so both are reported.
- Both for the pooled panel and for musicians and non-musicians separately.
- Within-listener consistency: agreement on the 4 repeat pairs.
- If SSR is below 0.8 pooled, the H7 verdict is still computed (G divides by SSR) but labelled
  "low reliability" and the recruiting stop rule of section 6 applies first.

### 7.3 H7 test

Section 2. Folds are whole pieces (one passage per piece in the base design). The coefficients
of M0 and M1 are ordinary least squares on passage-centred data; with 7 features and about 230
training scores per fold no penalty is needed. A ridge M1 is a robustness check.

### 7.4 Baseline and ceiling

- **Baseline:** chance (50%) for pairwise accuracy; M0 for the H7 gain.
- **Ceiling (rater parity):** for each listener, the pairwise accuracy of the BT scale fitted on
  all other listeners in predicting that listener's test pairs. The mean over listeners is the
  accuracy a typical held-out listener reaches against the panel. M1's held-out accuracy is
  reported next to it.

### 7.5 Strata and robustness (reported, not used for the verdict)

- All of 7.1-7.4 for musicians and non-musicians separately; the feature x group interaction is
  tested by adding `feature x group` terms to M1 (Wald test, 7 df).
- Leave-performer-out (ASAP performers recur across pieces; heuristic ids), reported separately,
  never instead of leave-piece-out.
- Without listeners who report a hearing difficulty; without listeners who took part in S-03.
- `d2m` against exact-capture references only for all three channels.
- M1 with ridge; M1 with the nuisance `corr__error_rate` for every passage.

### 7.6 What would change the plan

- Anything added after the data are seen is labelled as such and the verdict is also reported
  without it (rules/experiments.md).
- The verdict stays "Provisional" until `eval-auditor` signs it off.

## 8. Pilot plan (Henry, subject zero)

Henry's data set nothing in the analysis and are never part of it.

1. **Stimulus audit.** Henry listens to every passage's 10 clips once and flags artefacts (clicks,
   stuck notes, a cut that falls mid-phrase, a clip that is much longer than the others). Fixes go
   in `DEFECTS.md`.
2. **Timing run.** One full session in the app. Measure the real session length; if it is above
   55 minutes, move to the 40-pair variant.
3. **Catch check.** The catch pairs should be obvious to him; if not, raise the wrong-note rate.
4. Then O-02: recruiting, with an internal pilot as S-03 (first 12 listeners re-estimate listener
   variance only; N can go up, never down).

## 9. Data management

As S-03 section 9: a random participant code, the background answers, headphone-check answers,
per trial the clips, the answer and the response time, the session day and version strings. No
name, email, age (a checkbox for 18 or older), location, IP address or browser details. The
stimuli are derived from CC BY-NC-SA data: research use only, not redistributed without O-02
review.

## 10. Consent text

To be adapted from S-03 section 10 by Henry (O-02). The only change in substance: the task is
choosing between two performances of the same music, about 50 minutes, one session.

## 11. Decisions for the lead and Henry

1. **Margin delta** for "substantially": draft 0.10 of the reliable variance. A larger margin
   needs more passages (section 6).
2. **Number of passages** (24 in the base design) and **listeners** (section 6 recommendation).
3. **Repertoire balance**: keep the 20 ASAP pieces with at least 10 performers (11 Chopin), or
   swap some for 8- or 9-performer pieces.
4. **Clip length** (15-25 s) and **50 vs 40 test pairs** per listener.
5. **Skill range.** The plan's Phase 4 text and DECISIONS (after D-10) also want a stimulus set
   *across* skill levels (amateurs, Expert-Novice, Henry) for H4 and tier B validation. S-04 is
   experts only, because H7 is about experts and mixing skill levels would let accuracy dominate
   the scale. A cross-skill study is proposed as a separate ticket (S-04b) with its own protocol.
6. **S-03 overlap**: may S-03 listeners take S-04? The draft allows it, records it, and runs a
   sensitivity analysis without them.
7. Consent, payment, hosting, ethics review: O-02.

## 12. The app: reuse the S-03 app with a mode flag

The S-03 app's Part B already plays two clips and asks "Which performance do you prefer?", and
it has the consent flow, background questions, headphone check, break, local storage, JSON
export and headless autotest. S-04 can reuse it with a `study=S04` URL flag (S-05 ticket, not
built yet):

- `app.js`: choose the manifest global (`S04_MANIFEST`) and the default stimulus folder
  (`data/interim/study_s04/`) by the flag, skip Part A, and record `passage` plus the two
  performance ids instead of `dimension` / `level` / `chose_original` (which stays for catch
  pairs).
- A new `design_s04.js` builds the session: the listener's slice of the pair schedule (4.3),
  repeats, catch pairs, practice. The schedule itself is generated offline by
  `scripts/build_study_s04.py` into the manifest, so the app only reads it.
- `smoke_test.py`: an S04 autotest mode that checks the counts, the position balance and the
  catch pairs.

A new app is not needed.

## 13. Threats to validity

- **Tempo is a strong, easy cue.** Faster and slower performances also give clips of different
  lengths. Tempo is in M1 (feature 1), so a "supported" verdict driven by tempo alone is
  possible; the per-feature coefficients show it.
- **Loudness normalization** removes each pianist's overall level (3.4).
- **One renderer** gives every pianist the same instrument; interpretations that depend on a
  particular instrument's sound are judged on another. This is shared by every stimulus and is
  the price of keeping recording quality out.
- **Competition context.** ASAP performances come from competition rounds; the 10 per passage
  are e-Competition entrants, so the range of quality is narrow by design.
- **Feature measurement error** attenuates M1 (the simulation varies feature reliability).
- **Few pieces.** 24 folds is small for a bootstrap over passages; the CI may be optimistic.
