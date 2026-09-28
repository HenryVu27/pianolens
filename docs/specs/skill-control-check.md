# Expert vs amateur control check (D-10)

Measured 2026-09-27 by `data-engineer`. This is a descriptive check of tier A (F-02) and tier B
(F-04) features across skill levels on open data. Nothing was tuned. It substitutes for
SKY-Piano (D-09, unreleased).

> **Post-audit note (2026-09-28, after the R-09 audit; DECISIONS "R-09 is Confirmed with
> caveats").** The pooled-vs-matched contrast below does two things at once. Restricting to
> practice/performance clips removes the context difference, and it also removes the top two
> skill levels: every virtuoso clip is a concert and nearly every teacher clip is a demo. So
> "the separation vanishes once context is fixed" cannot be told apart from "the separation needs
> the top of the scale". The honest reading is: **tier B skill separation is not shown within
> beginner to advanced-student levels; the top levels are confounded with concert/demo
> context.** It is not shown that the pooled effect *is* context. R-09 found the same structure
> for timing coherence (pooled effect carried by teacher and virtuoso clips). The text below is
> kept as written; read "does not survive a fair comparison" and "separate recording contexts"
> with this caveat.

## Answer first

- **Pooled MAJEPPA, piece fixed effects, matched note rate:** advanced performances have about
  25% less timing noise, unevenness and between-hand spread than beginners. The 95% bootstrap
  CIs over performers exclude "no difference" for these features:
  - timing noise;
  - broad and strict IOI evenness;
  - between-hand residual SD;
  - velocity evenness (smaller effect, 8 to 13%).
- **That separation does not survive a fair comparison of recording context.** Two cases:
  - Every virtuoso clip is a concert recording, and most piano-teacher clips are class demos.
  - Restricted to clips labelled "practice" or "performance" (both groups recorded the same
    way), every tier B ratio lies between 0.92 and 1.05, and every CI includes 1.
- **So MAJEPPA does not show that tier B features separate skill.** It shows that they
  separate recording contexts that go with skill. CLAUDE.md rule 3 (shortcuts) applies to
  transcribed audio as much as to audio models.
- **Tier A (correctness) does not separate skill in MAJEPPA at all.** Within a piece,
  advanced and beginner accuracy differ by -0.011 (CI -0.041 to 0.014).
- **Transcription noise is small for timing features and large for velocity and correctness.**
  - On 6 ASAP performances that also exist as Transkun transcriptions (Transkun is MAJEPPA's
    transcriber), onset error has a robust SD of 9.3 ms.
  - Timing features move by about 1% on these performances.
  - Velocity is compressed: fit slope 0.64, residual SD 8.7 MIDI. That is above the audible
    step of 2.7 to 4.5 MIDI.
  - The tier A error rate doubles: 0.039 to 0.080.
- **Rach3 Hanon is the one clean contrast: same exercise, keyboard MIDI, no transcription.**
  At 4 to 6 notes/s:
  - IOI CV: 0.082 for the beginner against 0.061 and 0.077 for the two advanced pianists;
  - octave onset spread: 22.4 ms against 13.9 and 14.7 ms.

  That is 1 beginner against 2 advanced pianists, so it is an illustration, not evidence.
- **PianoVAM cannot be contrasted.** It has no scores, and only one piece is played at more
  than one level, once per level.

**Which tier B features separate skill, plainly:**

| Feature | Pooled MAJEPPA | Context-matched MAJEPPA | Rach3 Hanon (n = 3 pianists) |
|---|---|---|---|
| Timing noise (`timing_noise_best_*`, `jitter_nometric_*`) | yes | no (CI includes 1) | n/a (score-free proxy below) |
| Broad evenness `even_ioi_cv` | yes | no | beginner highest; overlaps one advanced pianist |
| Strict evenness `even_strict_ioi_cv` | yes | no | n/a |
| Velocity evenness `even_*vel_sd_midi` | weak | no | beginner *lower* |
| Hand sync `hand_async_resid_sd_*` | yes | no | beginner higher (octave spread) |
| Tempo instability | no | no | n/a |
| Pedal blur | no | no | n/a |

"No" in the context-matched column means the check could not show a difference. It does not
show that there is none. The CIs there are wide: for timing noise, the ratio lies between 0.80
and 1.08.

## Data

### MAJEPPA (transcribed MIDI, Transkun)

**Selection** (`scripts/build_skill_control_d10.py`):

- **Filter.** `score_coverage >= 0.85` (DECISIONS, F-05 follow-ups), with a score, on scores
  that have performances in at least 2 skill groups. That leaves 1,606 performances, 309
  scores and 1,470 recordings. 1,604 went through the pipeline; 2 had no matched onsets.
- **Groups:**
  - beginner = child beginner + adult beginner;
  - intermediate = adult intermediate;
  - advanced = child professional + piano teacher + virtuoso.
- **Pipeline:**
  1. `align_performance` (our aligner; MAJEPPA's DTW path is not note-level);
  2. staff from the score MIDI tracks and snapped durations (see loader fixes below);
  3. F-02 `correctness`, F-03 `tempo_model` and F-04 `control_features`.
- **Timing-noise references** are the other *advanced* performances of the same score whose
  alignment is trusted (leave-one-out, at least 3). Where these cover less than half the
  positions, `timing_noise_best_*` falls back to `jitter_nometric_*`. The consensus was
  available for 32% of tier B performances, and the fallback was used for the rest.

**Tier B gate.**

- The performance must have a trusted alignment: match ratio >= 0.8, the F-01 rule in
  `docs/specs/alignment-validation.md`.
- The score must be quantized: at most 10% of onsets off a 1/48-quarter grid. This excluded
  17 scores, which look like performance-derived MIDI.
- **The gate depends on skill.** The share of performances with a suspect alignment is:

| Level | Share suspect |
|---|---|
| child beginner | 0.31 |
| adult beginner | 0.36 |
| adult intermediate | 0.22 |
| child professional | 0.18 |
| piano teacher | 0.29 |
| virtuoso | 0.22 |

  Tier B is therefore measured on the beginners who played through the piece. This favours
  finding *no* difference.

**Counts:**

| Level | All | Tier B | Recordings (tier B) | Scores (tier B) | Median notes/s |
|---|---|---|---|---|---|
| child beginner | 165 | 107 | 107 | 62 | 7.6 |
| adult beginner | 427 | 264 | 250 | 167 | 4.6 |
| adult intermediate | 261 | 187 | 185 | 142 | 8.1 |
| child professional | 115 | 88 | 88 | 53 | 11.5 |
| piano teacher | 480 | 322 | 320 | 170 | 5.8 |
| virtuoso | 156 | 113 | 112 | 71 | 13.2 |
| total | 1,604 | 1,081 | 1,062 | 277 | 7.0 |

**Recording context in tier B (the confound):**

| Level | concert | demo class | slow demo | performance | practice | sight read |
|---|---|---|---|---|---|---|
| child beginner | 0 | 0 | 1 | 55 | 50 | 1 |
| adult beginner | 0 | 3 | 1 | 25 | 172 | 63 |
| adult intermediate | 0 | 5 | 1 | 64 | 105 | 12 |
| child professional | 0 | 0 | 0 | 47 | 41 | 0 |
| piano teacher | 17 | 218 | 72 | 6 | 7 | 1 |
| virtuoso | 113 | 0 | 0 | 0 | 0 | 0 |

### Loader fixes made for D-10 (`pianolens.data.majeppa`)

- **Staff.** MAJEPPA score MIDIs carry no staff, so every note had staff 0 and hand sync was
  empty.
  - 829 of 886 score MIDIs have exactly two note tracks.
  - `with_track_staff` puts staff 1 on the higher track and staff 2 on the other, matching
    notes by (onset quarter, pitch).
  - In a 40-score check, 187 of 137,448 notes (0.14%) had no matching key.
- **Durations.** Score MIDIs hold playback durations: an eighth lasts 0.4979 or 0.4729
  quarters, not 0.5.
  - F-04's run rule needs "no rest between notes", so it found no runs. For example, the
    Burgmüller Op. 100/1 score gave 0 run onsets; after the fix it gives 300.
  - `snap_score_durations` extends a note to the next onset of its stream when the gap is at
    most 7% of that IOI. Real staccato gaps are larger and are kept.
  - `prepare_aligned` applies both fixes to the score returned by `align_performance`.

### Transcription-noise pairs (PianoCoRe duplicates)

`scripts/check_transcription_noise_d10.py`.

**Where the pairs come from.**

- PianoCoRe marks transcriptions of the same recording as duplicates (`lead_performance`).
- 68 duplicate pairs link an ASAP Disklavier file to a transcription of the same performance:
  - 59 Aria-AMT (Aria-MIDI) + 3 in the reverse direction;
  - 6 Transkun V2 (PERiScoPe).
- The transcriptions come from YouTube audio of the competition performances.

**Matching and results.**

- PianoCoRe's copies of the ASAP files are trimmed by a few notes. So each pair was matched to
  `data/raw/asap` by file name, note count (within 2%) and length (within 10 s).
- 66 pairs matched and 65 ran: 59 Aria-AMT and 6 Transkun. One pair crashed in
  `tempo_stability` (DEFECTS DF-01).
- Both renditions were aligned to the ASAP score. Notes matched to the same score note in both
  renditions give the note-level error: 98% of the Disklavier matches, median 2,531 notes per
  pair.

### PianoVAM, Rach3

See the DATASETS.md rows. **PianoVAM** (CC BY-NC-SA 4.0, not CC BY-NC as the ticket said):

- 107 Disklavier practice recordings by 10 amateur pianists, with self-reported skill.
- No scores are released.
- Only Satie's Gymnopédie No. 1 is played at more than one level: 1 recording each at
  Beginner, Intermediate and Advanced.
- The loader and smoke test are in place. It is not used in the analysis.

**Rach3** (CC BY-NC-SA 4.0):

- Only the Hanon subset was downloaded (21 MB):
  - p1: 124 sessions, advanced;
  - p2: 36 sessions, advanced;
  - p3: 87 sessions, beginner.
- The Hanon score is the whole book (22,071 notes), and each file is a long practice session.
  Note alignment and the F-04 features cannot run on it.
- A score-free proxy was used instead (below).

## 1. Transcription-noise floor

**Note level**, same performance, Disklavier against transcription. A straight line maps the
clocks (slope 1.000 and 0.999). "Local" also removes a 21-note running median, so slow drift is
not counted.

| Transcriber | Pairs | Onset error, robust SD | Local onset error, robust SD | Local RMS (clipped at 100 ms) | Share > 30 ms | IOI error, robust SD | Velocity Spearman | Velocity fit slope | Velocity residual SD |
|---|---|---|---|---|---|---|---|---|---|
| Aria-AMT | 59 | 6.7 ms | 4.5 ms | 8.0 ms | 0.5% | 6.4 ms | 0.935 | 0.95 | 5.7 MIDI |
| **Transkun V2 (MAJEPPA's)** | 6 | 38.5 ms | **9.3 ms** | 16.5 ms | 5.6% | **12.7 ms** | 0.717 | 0.64 | **9.0 MIDI** |

For Transkun, the global error (38.5 ms) is much larger than the local one. The transcription
clock wanders over the piece: the audio is probably time-stretched or its frame timing drifts.
Tempo-normalized features only see the local part.

**Feature level:** paired medians, Disklavier against transcription, same performance.

| Feature | Aria-AMT: Disklavier to transcription (ratio) | Transkun: Disklavier to transcription (ratio) |
|---|---|---|
| `jitter_nometric_rms_ms` | 34.4 to 33.9 ms (1.02) | 15.5 to 15.4 ms (1.01) |
| `even_ioi_cv` | 0.236 to 0.240 (1.02) | 0.201 to 0.168 (0.85) |
| `even_strict_ioi_cv` | 0.230 to 0.238 (1.04) | 0.178 to 0.165 (0.85) |
| `even_vel_sd_midi` | 8.0 to 7.7 (0.96) | 8.0 to 7.3 (0.90) |
| `even_strict_vel_sd_midi` | 6.1 to 5.9 (0.95) | 6.2 to 5.3 (0.86) |
| `hand_async_resid_sd_ms` | 18.2 to 19.5 ms (1.02) | 14.2 to 13.9 ms (0.98) |
| `tempo_instability_log_sd` | 0.082 to 0.079 (1.00) | 0.037 to 0.041 (1.20) |
| `pedal_down_fraction` | 0.75 to 0.71 | 0.59 to 0.35 |
| tier A `error_rate` | 0.057 to 0.077 | **0.039 to 0.080** (higher in 6 of 6) |

**Reading it:**

- **Timing features are nearly unchanged.**
  - The expert performances here have 15 to 35 ms of residual timing and 14 to 18 ms of
    hand-sync spread.
  - A 9 ms error independent of them adds only about 2 to 3 ms in quadrature. For the 6
    Transkun pairs, the median added jitter is 2.2 ms.
  - Transkun even *lowers* the IOI CV by 15%, and velocity SD by 10 to 14%. It looks like
    onset and velocity smoothing or compression, not added noise.
- **Consequence for MAJEPPA.**
  - Transcription does not create the timing differences seen between groups: it changes
    these features by about 1%, far less than the 25% group effects.
  - The effect of transcription is one of *compression*. It may shrink differences in
    evenness and velocity by 10 to 15%.
- **Velocity features on Transkun MIDI are unreliable at the scale of the skill effects.**
  - The velocity residual SD (9 MIDI) is 2 to 3 times the audible step (Slade 2023: 2.7 to
    4.5).
  - The pooled velocity-evenness effect is only 0.5 to 0.8 MIDI units.
- **Tier A on transcribed MIDI has a floor of about 4 extra error points per 100 notes**
  (Transkun) on clean expert playing.
- **Limit.** These are fast expert performances (12 to 18 notes/s) on a competition piano. The
  noise on phone recordings of upright pianos, which is much of MAJEPPA's beginner material, is
  not measured and is likely larger. It would push beginner timing features up, in the same
  direction as the skill effect. This is a second route by which recording context can create
  an apparent skill effect.

## 2. MAJEPPA by skill level

**Model** (`scripts/analyze_skill_control_d10.py`), per feature:

```
y = piece fixed effect + b_int * intermediate + b_adv * advanced + g * log(note rate) + e
```

- It is fitted by OLS. Beginner is the reference.
- Only pieces with at least two skill groups enter.
- SDs, CVs and RMS values enter as log(y), so exp(b) is a ratio (advanced / beginner).
  Fractions enter raw.
- `d` = b / residual SD: a standardized effect within a piece, adjusted for rate.
- The rate is the feature's own run rate for evenness, otherwise performed notes per second.
- The 95% CIs are percentile bootstraps over `recording_id` (1,000 resamples; 500 for the
  sensitivity subsets). `recording_id` is one source video, the only performer proxy MAJEPPA
  gives. One performer with several videos counts as several performers, so the CIs are too
  narrow if that happens often.

### Pooled (all tier B performances)

| Feature | n (pieces) | Advanced / beginner | 95% CI | d | Intermediate / beginner | Without rate term |
|---|---|---|---|---|---|---|
| `timing_noise_best_rms_ms` | 992 (228) | **0.75** | 0.69 to 0.81 | -0.66 | 0.96 | 0.57 |
| `timing_noise_best_rms_beats` | 992 (228) | **0.76** | 0.69 to 0.85 | -0.30 | 0.93 | 0.79 |
| `timing_noise_rms_ms` (consensus only) | 304 (45) | **0.81** | 0.72 to 0.91 | -0.64 | 1.00 | 0.59 |
| `jitter_nometric_rms_ms` | 992 (228) | **0.76** | 0.70 to 0.83 | -0.54 | 0.94 | 0.60 |
| `even_ioi_cv` (broad) | 953 (221) | **0.74** | 0.67 to 0.83 | -0.56 | 0.90 | 0.94 |
| `even_strict_ioi_cv` | 688 (162) | **0.68** | 0.60 to 0.78 | -0.63 | 0.92 | 0.92 |
| `even_vel_sd_midi` (broad) | 953 (221) | 0.92 | 0.88 to 0.97 | -0.31 | 1.02 | 0.95 |
| `even_strict_vel_sd_midi` | 689 (162) | 0.87 | 0.80 to 0.93 | -0.45 | 1.03 | 0.88 |
| `hand_async_resid_sd_ms` | 973 (223) | **0.75** | 0.68 to 0.83 | -0.51 | 1.00 | 0.78 |
| `hand_async_resid_sd_beats` | 973 (223) | **0.76** | 0.69 to 0.83 | -0.47 | 1.02 | 1.16 |
| `hand_async_vel_slope_ms` (raw) | 980 (224) | -0.05 | -0.14 to 0.05 | -0.11 | | |
| `tempo_instability_log_sd` | 989 (227) | 0.91 | 0.75 to 1.13 | -0.11 | 1.09 | 0.91 |
| `tempo_drift_log` | 989 (227) | 0.76 | 0.54 to 1.03 | -0.18 | 1.05 | 0.74 |
| `pedal_blur_fraction` (raw difference) | 663 (170) | +0.004 | -0.024 to 0.031 | 0.03 | +0.02 | |
| tier A `accuracy` (raw, all 1,604) | 1,604 (309) | -0.011 | -0.041 to 0.014 | -0.05 | -0.035 | |
| tier A `error_rate` (raw) | 1,604 (309) | -0.023 | -0.178 to 0.093 | -0.03 | -0.112 | |

Notes on the table:

- **Intermediates look like beginners on every tier B feature.** No intermediate tier B ratio
  has a CI that excludes 1. In tier A, intermediates play fewer extra notes (extra rate -0.146,
  CI -0.342 to -0.032) and miss slightly more (missed rate +0.036, CI 0.003 to 0.075).
- **The rate adjustment matters for timing in ms.** Without it, the advanced/beginner ratio for
  timing noise is 0.57, because advanced players play faster: 11.5 to 13.2 notes/s against
  4.6 to 7.6. Timing in ms shrinks with tempo (rate slope -0.72 on the log scale). In beats,
  the rate slope is about 0.1, and the ratio barely changes.
- **Evenness depends on rate** (slope +0.58). This matches MacKenzie and Van Eerd 1990.

### Sensitivity to recording context

| Feature | No virtuosos (n) | Ratio (CI) | Practice + performance only (n) | Ratio (CI) | Children only (n) | Ratio (CI) |
|---|---|---|---|---|---|---|
| `timing_noise_best_rms_ms` | 866 | 0.81 (0.76 to 0.88) | 331 | 0.93 (0.80 to 1.08) | 42 | 1.04 (0.74 to 1.42) |
| `timing_noise_best_rms_beats` | 866 | 0.85 (0.78 to 0.93) | 331 | 0.96 (0.79 to 1.15) | 42 | 0.96 (0.54 to 1.42) |
| `jitter_nometric_rms_ms` | 866 | 0.86 (0.80 to 0.94) | 331 | 0.99 (0.83 to 1.21) | 42 | 1.07 (0.79 to 1.42) |
| `even_ioi_cv` | 827 | 0.83 (0.76 to 0.92) | 326 | 0.96 (0.78 to 1.16) | 42 | 0.84 (0.59 to 1.20) |
| `even_strict_ioi_cv` | 571 | 0.82 (0.74 to 0.93) | 250 | 0.92 (0.72 to 1.19) | 42 | 0.78 (0.40 to 1.26) |
| `even_vel_sd_midi` | 827 | 0.95 (0.91 to 1.00) | 326 | 1.02 (0.94 to 1.10) | 42 | 0.99 (0.85 to 1.17) |
| `even_strict_vel_sd_midi` | 571 | 0.93 (0.86 to 1.01) | 250 | 1.05 (0.94 to 1.17) | 42 | 1.05 (0.87 to 1.22) |
| `hand_async_resid_sd_ms` | 851 | 0.89 (0.81 to 0.96) | 326 | 0.98 (0.83 to 1.18) | 42 | 0.90 (0.60 to 1.25) |
| `tempo_instability_log_sd` | 863 | 1.14 (0.98 to 1.36) | 329 | 0.99 (0.80 to 1.29) | 42 | 1.07 (0.71 to 1.61) |
| `pedal_blur_fraction` (difference) | 554 | +0.001 (-0.026 to 0.031) | 247 | -0.025 (-0.068 to 0.045) | 32 | -0.004 (-0.076 to 0.054) |
| tier A `accuracy` (difference) | 1,389 | -0.018 (-0.048 to 0.009) | 477 | -0.039 (-0.095 to 0.023) | 58 | -0.002 (-0.053 to 0.038) |

What each subset contains:

- **No virtuosos.** Advanced here means child professionals and piano teachers; 595 advanced
  against 547 beginners. The effects shrink but stay clear of 1. The teachers are still mostly
  class demos, set against beginners' practice and sight-reading.
- **Practice + performance only.** 85 advanced (mostly child professionals) against 147
  beginners, in 89 pieces. The effects are near 1 and the CIs cover both "no effect" and
  about a 20% reduction.
- **Children only.** Child professionals against child beginners, in 13 pieces with both. This
  is the best-matched contrast, and far too small to say anything.

### Group levels and the literature (landscape section 1.5)

These are medians within note-rate bins, tier B. The bins mix pieces, so these medians do not
control for the piece. The effects above do.

| Measure | Rate | Beginner | Intermediate | Advanced | Published |
|---|---|---|---|---|---|
| `even_strict_ioi_cv` | 6 to 8 notes/s | 0.127 (n = 36) | 0.162 (32) | 0.131 (64) | professionals about 0.07 at 8 notes/s; students 0.11 to 0.13 at 10.7 notes/s (van Vugt 2013; van Vugt, Treutler et al. 2013; instructed scales) |
| `even_ioi_cv` | 6 to 8 notes/s | 0.143 (30) | 0.182 (41) | 0.185 (82) | as above |
| `hand_async_resid_sd_ms` | 4 to 6 notes/s | 13.7 (103) | 16.8 (37) | 12.2 (94) | experts 0.008 vs amateurs 0.014 (unit unstated, probably s), Hanon and scales at 4 notes/s (Kim 2021) |
| `even_strict_vel_sd_midi` | 4 to 6 notes/s | 5.6 (73) | 5.7 (35) | 4.9 (76) | expert keystroke velocity SD 4.1 across trials (Tominaga 2016); JND 2.7 to 4.5 (Slade 2023) |
| `jitter_nometric_rms_ms` | 8 to 12 notes/s | 15.3 (75) | 16.1 (65) | 14.0 (120) | expert keystroke IOI SD 7.9 ms across trials at 4 notes/s (Tominaga 2016) |

Reading the numbers:

- MAJEPPA repertoire values sit above the published floors, as the F-04b spec expected. They
  include expressive micro-timing, alignment error and about 9 to 13 ms of transcription error.
- Hand-sync spread (12 to 17 ms) sits at or above Kim 2021's amateur value, if Kim's unit is
  seconds.
- At a matched rate and without piece control, advanced and beginner medians overlap in most
  bins.

## 3. Rach3 Hanon (score-free, keyboard MIDI)

**Method.** `scripts/check_rach3_hanon_d10.py`.

- Onsets within 40 ms merge into one event: the two hands, an octave apart.
- A steady stream is at least 24 consecutive IOIs within 0.6 to 1.6 times the running median
  of 9 IOIs.
- `ioi_cv` is the RMS of (IOI / running median - 1). This is tempo-normalized, like
  `even_ioi_cv`.
- The octave spread is the robust SD of (upper - lower onset) at two-note octave events. There
  is no velocity fit.
- Streams: p1 3,121; p2 984; p3 1,621.

| Rate (notes/s) | Pianist | Sessions | IOIs | IOI CV | Robust CV (median) | Velocity SD (median) | Octave spread SD (median, ms) |
|---|---|---|---|---|---|---|---|
| 0 to 4 | p1 advanced | 27 | 5,355 | 0.071 | 0.047 | 6.0 | 13.9 |
| 0 to 4 | p2 advanced | 16 | 3,762 | 0.069 | 0.049 | 5.7 | 13.9 |
| 0 to 4 | p3 beginner | 56 | 13,230 | 0.071 | 0.051 | 4.2 | 21.6 |
| 4 to 6 | p1 advanced | 101 | 125,227 | 0.061 | 0.048 | 5.9 | 13.9 |
| 4 to 6 | p2 advanced | 23 | 16,385 | 0.077 | 0.058 | 4.9 | 14.7 |
| 4 to 6 | p3 beginner | 78 | 42,982 | 0.082 | 0.061 | 4.1 | 22.4 |
| 6 to 8 | p1 advanced | 72 | 81,285 | 0.067 | 0.055 | 6.3 | 13.9 |
| 6 to 8 | p2 advanced | 34 | 25,006 | 0.095 | 0.077 | 6.7 | 16.2 |
| 6 to 8 | p3 beginner | 7 | 415 | 0.141 | 0.110 | 5.1 | 21.7 |
| 8 to 10 | p1 advanced | 9 | 7,105 | 0.099 | 0.081 | 9.9 | 15.5 |
| 8 to 10 | p2 advanced | 14 | 2,424 | 0.116 | 0.095 | 7.4 | 18.5 |

**Timing evenness.**

- The beginner rarely plays Hanon faster than 6 notes/s.
- At 4 to 6 notes/s, session-level CVs are:

| Pianist | Median | Interquartile range |
|---|---|---|
| p1 (advanced) | 0.060 | 0.054 to 0.069 |
| p2 (advanced) | 0.074 | 0.073 to 0.092 |
| p3 (beginner) | 0.083 | 0.073 to 0.097 |

- The beginner is least even, but p2 overlaps heavily.
- p1's 0.061 to 0.067 at 4 to 8 notes/s is close to van Vugt's professional scale value
  (CV about 0.07).
- At 0 to 4 notes/s all three are the same (0.07).

**Other measures.**

- **Octave spread separates most cleanly:** 21.6 to 22.4 ms for the beginner against 13.9 to
  16.2 ms for both advanced pianists, in every shared bin. This matches the direction of Kim
  2021 (amateurs about 1.75 times the experts).
- **Velocity SD is *lower* for the beginner** (4.1 to 5.1 against 4.9 to 6.7). A beginner who
  plays softer and flatter may simply use a narrower velocity range. Velocity SD is not a
  skill measure without a dynamics reference.
- **Over time**, the beginner's CV at 4 to 6 notes/s rose from 0.073 (first half of sessions,
  Jun to Sep 2024) to 0.095 (Sep 2024 to Feb 2025). The advanced pianists stayed flat
  (p1 0.062 to 0.060). The data do not say why: the exercise mix or the tempo within the bin
  may have changed.
- **Caveats:**
  - 3 pianists, so no inference about skill levels is possible.
  - The instrument is not stated.
  - Onset times fall on steps of about 1.04 ms (tick resolution), so the octave-spread values
    repeat. The median 13.9 ms is one such step pattern.

## Limits

- **Performer identity.** MAJEPPA gives only `recording_id` (one video). The bootstrap
  treats videos as performers. Recurring YouTube channels would make the CIs too narrow.
- **Recording context vs skill.** Context and skill cannot be separated in MAJEPPA beyond the
  89-piece practice/performance subset. That subset is underpowered for effects below about
  20%.
- **Transcription noise on amateur recordings is not measured.** The 6 Transkun pairs are
  competition recordings. The noise floor for phone recordings of home pianos is the
  missing number.
- **Gate bias.** Tier B excludes 29 to 36% of beginner performances (untrusted alignment), so
  the beginners who remain are the more fluent ones.
- **Pedal.** It comes from Transkun's pedal output, and Transkun halves the pedal-down time
  against Disklavier on the 6 pairs. `pedal_blur_fraction` on MAJEPPA is not interpretable.
- **Analysis choices.** Feature choices, the gate and the model were fixed before the results
  were seen. The 0.07 duration-snap tolerance and the 10% off-grid cut were set on score
  structure (a 40-score check), not on outcomes. The sensitivity subsets were added after the
  pooled result, because the recording-type table showed the confound.

## Rerun

```
uv run python scripts/build_skill_control_d10.py --workers 8       # 16 min, 1,604 performances
uv run python scripts/check_transcription_noise_d10.py --workers 4 # 65 pairs, each aligned twice (not timed)
uv run python scripts/check_rach3_hanon_d10.py                     # 247 sessions (not timed)
uv run python scripts/analyze_skill_control_d10.py --boot 1000     # 8 min without the sensitivity subsets
```

Outputs (gitignored) go to `data/interim/skill_control_d10/`:

- `majeppa_features.csv`, `failures.csv`;
- `effects.csv`, `effects_sensitivity.csv`, `by_level.csv`, `by_rate_bin.csv`, `counts.csv`;
- `transcription_pairs.csv`, `transcription_pairs_failures.csv`;
- `rach3_hanon_streams.csv`.
