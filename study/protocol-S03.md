# S-03 protocol: perceptual cost of expressive degradations (H6)

Ticket: S-03 (design and build). Hypothesis: H6. Protocol version 0.1, 2026-09-27.
Status: **DRAFT pre-registration, not frozen.** Sections 1-7 become the frozen pre-registration
after the pilot (section 8) fixes the level ladders. At that point the lead records the sha256 of
this file in `DECISIONS.md` and later changes go in a "Deviations" section, never in place.
Nothing here has been run on a listener. Recruiting, consent approval, payment and hosting are
Henry's (O-02).

Where things are:

| What | Path |
|---|---|
| Degradations (S-01) | `src/pianolens/study/degrade.py`, excerpts `src/pianolens/study/excerpt.py` |
| Stimulus spec (excerpts, ladders, render) | `study/stimuli-S03.json` |
| Stimulus build | `scripts/build_study_s03.py` -> `data/interim/study_s03/` (gitignored) |
| Study app | `study/app/` (`index.html`, `app.js`, `design.js`, `style.css`) |
| App smoke test | `study/app/smoke_test.py` |
| Analysis fits | `src/pianolens/study/psychometric.py` |
| Power simulation | `src/pianolens/study/power.py`, `scripts/power_s03.py` -> `data/interim/study_s03/power/` |

## 1. Question

Does each expressive dimension have its own perceptual cost, or is the cost of a change just a
matter of how audible it is?

H6 (plan, section 2): "Each expressive dimension has a measurable perceptual cost curve, and the
curves differ enough to justify non-uniform feature weights." Falsified if "cost curves are
indistinguishable across dimensions".

Physical units differ between dimensions (ms, MIDI velocity, beats), so "the curves differ" needs
a common axis. The primary axis here is **detection-threshold units**: a level is expressed as a
multiple of that dimension's measured detection threshold. The question becomes: at equal
audibility, does a change in one dimension cost more preference than a change in another?

- If the costs are equal per threshold unit, a scorer can weight every feature by its audibility
  alone (weights = 1 / threshold). H6 is then falsified in its useful sense: no dimension-specific
  weights beyond audibility.
- If they differ, dimension-specific weights are justified.

This reading is a design choice for the lead to confirm (section 11).

## 2. Falsification criterion (pre-registered reading)

Model (section 7.2): `logit P(choose original) = gamma * s + beta_d * x / theta_d`, where `s` is
+1/2 when the original is second and -1/2 when it is first, `x` is the stimulus level and
`theta_d` the dimension's detection threshold (section 7.1). `beta_d` is the cost per threshold
unit. The margin is m = 2: a two-fold difference in cost per threshold unit is the smallest
difference that would change how a scorer weights features.

- **Supported:** the Wald test that all seven `beta_d` are equal has p < 0.05, **and** at least
  one ordered pair (i, j) has `beta_i - 2 beta_j > 0` at one-sided alpha 0.05 / 42 (Bonferroni
  over the 42 ordered pairs).
- **Falsified (indistinguishable):** every ordered pair has `beta_i - 2 beta_j < 0` at one-sided
  alpha 0.05, so every ratio lies within 1/2 to 2 (two one-sided tests; no multiplicity
  correction is needed for an intersection-union test).
- **Inconclusive:** anything else.

The uncertainty of `theta_d` is carried into `beta_d` by the delta method
(`var(beta_d) += beta_d^2 var(ln theta_d)`), and checked with a listener bootstrap (section 7.4).
Implementation: `pianolens.study.power.h6_verdict`.

## 3. Stimuli

### 3.1 Excerpts

Eight passages, all with exact timing from sensor or Disklavier capture and a ground-truth
note alignment. The app shows only the neutral codes E1-E8: no composer, title or performer
(rules/study.md). Bar ranges are measure rows of the unfolded score, row 0 being the pickup where
there is one. Where a source has several performances of the passage, the one with the median
overall tempo (F-03 `tempo_bpm_overall`, lower median) is used, so extreme interpretations are
avoided without choosing by ear.

| Code | Source (license, DATASETS.md) | Passage | Performance used | Detection clip | Preference clip |
|---|---|---|---|---|---|
| E1 | Vienna 4x22 (CC BY 4.0), sensor | Chopin Op. 10 No. 3, opening | p03 (median tempo of 22) | rows 0-1 | rows 0-4 |
| E2 | Vienna 4x22, sensor | Chopin Op. 38, opening | p08 | rows 0-1 | rows 0-4 |
| E3 | Vienna 4x22, sensor | Mozart K. 331/1, theme | p01 | rows 0-1 | rows 0-3 |
| E4 | Vienna 4x22, sensor | Schubert D. 783 No. 15 | p14 | rows 0-4 | rows 0-8 |
| E5 | Batik-plays-Mozart (CC BY-NC-SA 4.0), sensor | Mozart K. 330/1, opening | the only one | rows 0-2 | rows 0-7 |
| E6 | Batik-plays-Mozart, sensor | Mozart K. 333/2, opening | the only one | rows 0-1 | rows 0-3 |
| E7 | (n)ASAP / MAESTRO (CC BY-NC-SA 4.0), Disklavier | Schubert D. 899/3, opening | LEE_K04M (median of 11) | row 0 | rows 0-2 |
| E8 | (n)ASAP / MAESTRO, Disklavier | Bach WTC I Prelude BWV 848, opening | Mizumoto03M (median of 9) | rows 0-7 | rows 0-15 |

Measured on the pilot build (with the 1.0 s release and 0.8 s tail): detection clips 5.9-9.0 s
(median 7.3 s), preference clips 12.8-18.5 s (median 13.8 s).

### 3.2 One renderer, one loudness

- Every clip is rendered by the S-02 pipeline (`pianolens.audio.render`): Salamander C5 Light SF2,
  FluidSynth 2.6.1, the pinned synth settings, mono. For listening the sample rate is 44.1 kHz,
  not the 24 kHz model-input default.
- Each clip is trimmed to its length plus 1.8 s, faded in (5 ms) and out (0.4 s), then set to
  -23 LUFS integrated (pyloudnorm, ITU-R BS.1770).
- Level is therefore not a cue, including after dynamics flattening, which changes the raw level.
- Pilot build: 592 clips, highest peak 0.674 of full scale, none clipped.
- The manifest records the render config hash, soundfont hash, FluidSynth version and code state
  (`data/interim/study_s03/manifest.json`).

### 3.3 Degradations (S-01)

Each clip changes one dimension of the original clip, applied *after* cutting the excerpt, so
the dose is exact within the clip. Every stimulus records its change measured in physical units
(`physical` in the manifest). `x` is the analysis level, fixed before any data:

| Dimension | What changes | Control | Analysis level x | Published audibility reference (landscape 1.5) |
|---|---|---|---|---|
| timing_jitter | random onset shift per score position (chords stay together), s.d. relative to the local IOI | `cv` | added IOI CV, measured | IOI s.d. 10.22 ms at 8 notes/s, CV about 0.08 (van Vugt et al. 2013); isochronous scales, so a lower bound in repertoire |
| tempo_flatten | the F-03 smooth tempo curve pulled toward constant tempo; residual timing kept in beats | `alpha` | rubato removed: s.d. of log tempo before minus after | none |
| dynamics_flatten | velocity contour pulled toward the mean; melody vs accompaniment gap kept | `alpha` | RMS velocity change per note (MIDI) | velocity JND 2.71-4.48 MIDI units, consecutive tones (Slade et al. 2023) |
| voicing | melody (score skyline) vs accompaniment velocity gap scaled by k; local mean kept | `k` (1 = original, -1 = inverted) | change of the melody-accompaniment gap (MIDI) | same JND |
| pedal_blur | every cleanly pedalled harmony change (F-04b detector) gets a late pedal change `hold` beats after it | `hold_beats` | mean added hold (beats) | none |
| articulation | key-down durations scaled (toward staccato) | `factor` | log2(1 / factor) | none (Bresin and Battel 2000 define KOT / KOR) |
| wrong_notes | wrong pitches (neighbour keys, a few octaves), timing and velocity kept | `rate` | wrong notes per note, measured | none |

Pilot ladders (control values) and the measured x on the preference clips, median [range] over
the eight excerpts:

| Dimension | Pilot levels | x on preference clips |
|---|---|---|
| timing_jitter | cv 0.0125, 0.025, 0.05, 0.1, 0.2 | 0.020 [0.017-0.026], 0.038 [0.033-0.082], 0.072 [0.054-0.087], 0.139 [0.114-0.195], 0.259 [0.210-0.291]; as a ratio to CV 0.08: 0.24, 0.47, 0.91, 1.73, 3.24 |
| tempo_flatten | alpha 0.125, 0.25, 0.5, 0.75, 1 | 0.006 [0.003-0.021] ... 0.047 [0.026-0.181] (the excerpts' smooth log-tempo s.d. is 0.026-0.181) |
| dynamics_flatten | alpha 0.125, 0.25, 0.5, 0.75, 1 | 1.0 [0.9-1.9], 1.9 [1.7-3.6], 3.8 [3.3-7.2], 5.7 [4.9-10.8], 7.6 [6.5-14.3] MIDI |
| voicing | k 0.75, 0.5, 0, -0.5, -1 | 4.4 [1.2-7.7], 9.1 [3.0-13.8], 18.3 [5.7-28.4], 27.4 [8.3-42.5], 36.5 [11.1-56.8] MIDI (original gaps 4.5-27.9) |
| pedal_blur | hold 0.6, 0.85, 1.25, 2, 3 beats | 0.60, 0.85, 1.25 [0.83-1.25], 1.78 [0.91-2.0], 2.33 [1.03-3.0] (capped at the next change) |
| articulation | factor 0.84, 0.71, 0.5, 0.35, 0.25 | 0.25, 0.49, 1, 1.51, 2 |
| wrong_notes | rate 0.01, 0.02, 0.04, 0.08, 0.16 | 0.013 [0.008-0.019], 0.019, 0.037, 0.081, 0.161 (at least one wrong note per clip) |

Known limits of the dimensions, measured on the pilot build:

- **Pedal.** The harmony detector finds few changes in these openings: 0-6 per detection clip
  and 1-11 per preference clip. So pedal is graded by lateness, not by the share of changes.
  Three detection clips (E2, E5, E7) have no change the detector sees; the app never uses a clip
  that is identical to its original, so pedal detection uses the other five excerpts.
- **Articulation** is partly masked where the pedal is down: the sustain pedal is down for
  0-96% of the preference clips.
- **Voicing** doses differ a lot between excerpts because the original gaps differ (4.5 to 27.9
  MIDI units). The analysis level x is the measured gap change, not k.

## 4. Procedure

### 4.1 Session

1. Consent (section 10).
2. Five background questions (section 9).
3. Volume setting on one original clip.
4. Headphone check: Woods, Siegel, Traer, McDermott 2017 (Attention, Perception, &
   Psychophysics 79:2064). Three 200 Hz tones, one 6 dB quieter, one in antiphase between the
   ears; which is quietest? Six questions, pass at 5 of 6, one retry. (Verified; landscape section 6.1.)
5. Part A, then Part B. Each part opens with instructions and practice, and has a break halfway.
6. End: debrief, and the participant downloads a JSON file.

Parts A and B can run in one session or as two sessions (`?parts=A`, `?parts=B`). The analysis
uses group-level thresholds, so different listener groups may even do the two parts.

### 4.2 Part A: detection thresholds

- Each trial plays the reference (the original clip), then A, then B. One of A and B is the
  reference again; the other is degraded. Question: "Which one, A or B, is different from the
  reference?" Chance is 0.5.
- Each clip plays once, with no replay. Answers are enabled when the last clip ends, and the
  response time is recorded from then.
- Constant stimuli. Main study: 4 levels per dimension at the pilot threshold times 0.5, 1, 2
  and 4, with 3 trials per level: 84 trials. The pilot uses the 5 pilot levels with 2 trials each.
- 4 catch trials: a gross wrong-note version at rate 0.3.
- 3 practice trials with feedback: two catch-level trials and the strongest level of one random
  dimension.

### 4.3 Part B: preference cost

- Each trial plays the original and a degraded version of the same passage (A, then B).
  Question: "Which performance do you prefer?"
- Main study: 3 levels per dimension at the pilot threshold times 2, 4 and 8 (capped at the
  largest level the dimension allows), 2 trials per level: 42 trials.
- 7 identical pairs (original vs original). These measure the second-position bias with no
  difference present.
- 2 catch trials (gross wrong notes).
- 1 practice trial.
- Every (dimension, level) cell is compared about 2N times over the eight excerpts. With N = 96
  that is about 2 x 96 / 8 = 24 comparisons per stimulus (7 x 3 x 8 = 168 degraded stimuli,
  42 x 96 = 4,032 judgements, above 10 x 168). This meets the rules/study.md target of at least
  20 comparisons per item on average. Design B2 at N = 48 also gives about 24 (4 x 48 / 8).
  Designs with fewer than 80 listeners in A2 fall below 20 per stimulus. (Corrected 2026-09-29,
  DF-08: this line used to cite the withdrawn "12-17" target.) The scale-separation reliability
  part of that rule is for Bradley-Terry scaling (S-04 onward); here reliability is the
  split-half reliability of section 7.6.

### 4.4 Counterbalancing and randomisation (`study/app/design.js`)

- **Position.** Within each dimension, the degraded clip is first in half the trials and second
  in the other half (a balanced, shuffled vector), because listeners favour the second item
  (Kroger and Margulis 2017, landscape 4). The position is recorded and modelled.
- **Excerpts.** Each (dimension, level, repetition) cell is assigned an excerpt by walking a
  per-listener random permutation of the excerpts. So within a listener each excerpt is used
  about equally per dimension, and across listeners every excerpt meets every level. Clips
  identical to the original (section 3.3, pedal) are skipped.
- **Order.** Trials are shuffled per listener with a seeded PRNG (the seed is the participant
  code). Catch trials are spread evenly, and the same excerpt never comes twice in a row where
  it can be avoided.

### 4.5 Timing

With the measured clip lengths (a detection trial is about 26 s, a preference trial about 31 s),
Part A takes about 37 minutes of listening and Part B about 25 minutes, plus practice, catch
trials, consent and checks. One session with both parts is about 75 minutes, which is long. The
recommended format is two sessions of 40-45 minutes, one per part.

## 5. Listeners

- **Strata.** Musicians and non-musicians, by self-identification plus years of formal training
  (rules/study.md). Recruit about equal numbers of each. The H6 test pools both groups; each
  group is also analysed alone (section 7.5).
- **Inclusion.** Age 18 or older (a consent checkbox) and listening over headphones.
- **Exclusion (pre-registered), applied before any analysis of the test trials:**
  - failing the headphone check twice (fewer than 5 of 6, both attempts);
  - fewer than 5 of 6 catch trials correct (4 in Part A, 2 in Part B; in Part B "correct"
    means preferring the original);
  - fewer than 80% of the test trials completed.
- Listeners who report a hearing difficulty are kept. The primary analysis is repeated without
  them as a sensitivity check.
- **Sample size:** section 6.

## 6. Power analysis (simulation)

Method (`pianolens.study.power`, run with `uv run python scripts/power_s03.py --n-rep 200
--seed 0`, 200 simulated studies per cell):

1. Simulate listeners with their own thresholds and cost slopes, trial by trial, for the design
   in section 4.
2. Fit exactly as pre-registered: a psychometric fit per dimension with listener-clustered
   standard errors, then the preference logistic model on estimated threshold units.
3. Apply the section 2 reading.

**Every simulation parameter is an assumption, not a measurement.** No published study gives
them for these stimuli.

| Assumption | Base value | Varied to |
|---|---|---|
| Psychometric slope (logistic, per log2 of level) | 2 | 1 |
| Between-listener s.d. of log2 threshold | 0.5 | 0.25, 0.75 |
| Between-excerpt s.d. of log2 threshold | 0.3 | n/a |
| Lapse rate | 0.02 | n/a |
| Cost slope beta (logit per threshold unit) | 0.4 | 0.2, 0.8 |
| Between-listener s.d. of beta | 0.2 | 0.4 |
| Second-position bias (logit) | 0.3 | n/a |
| Pilot places the ladder at the true threshold | yes | off by a factor 2 |
| H6 margin | 2 | 1.5 |

Operating characteristics. "Ratio" is the true cost ratio of one dimension to the other six
(1 = H6 false). Design A2 is sections 4.2-4.3; B2 doubles the trials per listener (two sessions
per part).

| Design | N listeners (total, both strata) | P(supported), ratio 3 | P(supported), ratio 1 (false positive) | P(falsified), ratio 1 | Detection 95% CI half-width, log2 (mean over dims) |
|---|---|---|---|---|---|
| A2 | 32 | 0.16 | 0.000 | 0.00 | 0.39 |
| A2 | 48 | 0.44 | 0.000 | 0.05 | 0.31 |
| A2 | 64 | 0.69 | 0.000 | 0.15 | 0.27 |
| A2 | **96** | **0.92** | 0.000 | 0.52 | 0.22 |
| A2 | 128 | 0.98 | 0.000 | 0.72 | 0.19 |
| A2 | 160 | 0.98 | 0.000 | 0.85 | 0.17 |
| B2 | 48 | 0.84 | 0.000 | 0.20 | 0.24 |
| B2 | 96 | 0.99 | 0.000 | 0.83 | 0.17 |

Smallest N for 80% (base assumptions, and the sensitivity range over the variants above):

- **To detect a three-fold cost difference (supported):**
  - design A2 needs **96 listeners** (48-128 over the variants, and not reached by N = 160
    when beta = 0.8);
  - B2 needs 48 (24-128 over the variants);
  - beta = 0.8 is the worst case: level 8 then sits near the ceiling of the logistic, so the
    pilot must not place the preference levels too high.
- **To be able to falsify H6 when the costs are equal:** A2 needs 160 (base; most variants
  never reach 80% by N = 160); B2 needs 96. For B2, four variants never reach 80% by N = 160:
  smaller beta, larger listener variance of beta, a misplaced ladder, margin 1.5.
- **A cost ratio of exactly 2** equals the margin, so by construction it is never "supported":
  at most 0.34 by N = 160 in B2.
- **False positives:** P(supported) under ratio 1 stayed at or below 0.02 in every variant.

Full grid: `data/interim/study_s03/power/power_grid.csv` and `summary.md`.

**Recommendation for O-02:**

- Plan **96 listeners (48 musicians, 48 non-musicians) doing both parts once** (design A2,
  about 75 minutes each, best as two sessions). That is about 120 listener-hours.
- This gives 80% power only for a large (three-fold) difference, and a coin flip at falsifying.
- Being able to falsify needs about 160 listeners, or 96 listeners doing every part twice (B2).
- Before committing, run an **internal pilot**: the first 12 recruited listeners. From them,
  re-estimate the between-listener variances and slopes only. Do not look at the H6 contrast.
  Then re-run `power_s03.py` with those values. Pre-registered rule: N can go up, never down,
  and the internal-pilot listeners stay in the final analysis.

## 7. Analysis plan

### 7.1 Detection thresholds (per dimension)

- Pool all included listeners' Part A test trials for the dimension. Fit
  `P(correct) = 0.5 + (0.5 - lapse) * sigmoid(s (log2 x - a))` by maximum likelihood.
- The lapse is fixed at the catch-trial error rate times 2 (pooled; at least 0.01).
- The threshold is `theta_d = 2^a`, the level where the sigmoid is 0.5 (about 74% correct with a
  2% lapse).
- 95% CIs from listener-clustered (CR1 sandwich) standard errors. Implementation:
  `pianolens.study.psychometric.fit_detection`.
- Report `theta_d` in physical units and as a ratio to the published reference where there is
  one (timing: IOI CV 0.08; velocity: JND 2.71-4.48).
- Baseline: chance (0.5).
- Ceiling: catch-trial accuracy.
- Descriptive per-level percent correct with listener-bootstrap CIs goes alongside the fit.

### 7.2 Preference cost curves

- **Curve per dimension.** Per level, the proportion choosing the original, corrected for
  position bias. Estimate it as the per-level coefficient in a logistic model with the position
  term, and give listener-bootstrap 95% CIs (2,000 resamples). This curve is the H6 deliverable
  "cost curves with CIs".
- **Parametric model.** `logit P(choose original) = gamma * s + sum_d beta_d * x / theta_d`,
  with no intercept, fitted on the test trials, the identical pairs (x = 0) and nothing else.
  CR1 standard errors by listener. Implementation: `pianolens.study.psychometric.fit_logit`.
- **Baseline.** No preference for the original at x = 0: the identical pairs estimate `gamma`
  alone.
- **Ceiling.** Catch trials.

### 7.3 H6 test

Apply section 2 to `beta_d` with the covariance of 7.2 plus the delta-method term for
`theta_d` (`h6_verdict`).

### 7.4 Robustness (reported, not used for the verdict)

- Listener bootstrap of the whole pipeline (thresholds, then the cost fit): 2,000 resamples,
  percentile CIs for every `beta_d` and for the max/min ratio.
- A mixed logistic model with listener and excerpt random effects.
- The same analysis on the **physical axis**: `beta_d` per native unit, with no threshold
  normalization.
- The same analysis on an **expert-spread axis**: the level divided by the between-performer
  s.d. of that feature on the same passage, where several performances exist (Vienna 4x22 has
  22).
- Leave-one-excerpt-out: every verdict recomputed with each excerpt dropped. This is the study's
  version of the leave-piece-out rule.
- Without listeners who report a hearing difficulty.
- The lapse rate free instead of fixed.

### 7.5 Strata

All of 7.1-7.3 are repeated for musicians and non-musicians separately. The dimension x group
interaction is tested by adding `beta_d x group` terms (Wald test, 7 df). The H6 verdict uses
the pooled sample. Per-group verdicts are descriptive, since the study is not powered for them.

### 7.6 Reliability

- Split-half reliability of the per-dimension cost (listeners split at random 1,000 times),
  stepped up with Spearman-Brown to the full panel (rules/experiments.md).
- Test-retest from the pilot repeat (section 8).
- Pair selection is not adaptive, so Bramley's caveat does not apply.

### 7.7 What would change the plan

- A dimension whose fitted threshold lies outside the tested ladder is reported as "above the
  largest level" and left out of the H6 test.
- Anything added after the data are seen is labelled as such, and the H6 verdict is also
  reported without it (rules/experiments.md).
- The verdict stays "Provisional" until `eval-auditor` signs it off.

## 8. Pilot plan (Henry, subject zero)

Henry knows the dimensions, so his data are not naive. They set the ladders and are never part
of the main analysis.

1. **Stimulus audit (about 20 minutes).** Build the pilot stimuli
   (`uv run python scripts/build_study_s03.py`). Henry listens to each excerpt's original and its
   strongest level in every dimension. He flags artefacts: clicks, stuck notes, pedal noise,
   unnatural cut-offs, a degradation that sounds like a different dimension. The fixes go in
   `DEFECTS.md` before anything else.
2. **Pilot run.** Open `study/app/index.html?mode=pilot`: all 5 pilot levels, 2 detection
   trials per level (70 trials), 1 preference trial per level (35 trials), plus catch trials
   and identical pairs. Do it as two sittings (`&parts=A`, then `&parts=B`). Report the time
   taken, fatigue, and whether any instruction was unclear.
3. **Repeat of Part A** on another day, for test-retest reliability of the thresholds.
4. **Set the main ladders.**
   - Fit Henry's detection threshold per dimension (7.1).
   - Write `"main": {dim: {"det": [0.5, 1, 2, 4] x theta, "pref": [2, 4, 8] x theta}}` into
     `study/stimuli-S03.json`, capping each at the largest achievable x.
   - If Henry's threshold for a dimension lies below the lowest pilot level or above the
     highest, first extend that ladder and repeat step 2 for that dimension only.
   - Then run `uv run python scripts/build_study_s03.py --ladder main`. It solves, per excerpt,
     the control level that reaches each x target (bisection).
5. **Freeze.**
   - Re-run `scripts/power_s03.py` if the pilot suggests different slopes.
   - Update this protocol, sections 3-6.
   - Record its sha256 in `DECISIONS.md`.
   - Create `experiments/<date>-S-03-perceptual-cost/README.md` per the `run-experiment` skill.
6. **Then O-02.**

## 9. Data management and minimisation

- **Collected:** a random participant code (for example P7K2QX); the five background answers
  (musician yes/no; years of formal training in 5 bins; plays piano no / a little / yes; any
  known hearing difficulty yes / no / prefer not to say; headphones, earbuds or speakers); the
  headphone-check answers; per trial the stimuli, the answer, the response time and the time
  since the session start; the session date (day only); and app, protocol, consent and
  stimulus versions.
- **Not collected:** name, email, age (only an 18+ checkbox), location, IP address, browser
  fingerprint or user agent. No network requests leave the page. The app loads only local files.
- **Storage:** responses stay in the browser's localStorage (so a session can resume) until
  the participant downloads the JSON file and sends it as O-02 decides. Declining consent
  clears the storage.
- **Retention and publication:** O-02 decides. The proposal is to publish the anonymous trial
  data with the analysis. The code is the only link between a person and their data, and Henry
  keeps no list linking codes to people unless payment requires one. If it does, that list is
  kept separate and deleted after payment.
- **Withdrawal:** a participant gives their code to have their data removed before
  publication.

## 10. Consent text (DRAFT for Henry)

The same text is in the app (`study/app/index.html`) under a "DRAFT" banner. Henry must fill in
the bracketed fields, and decide whether an ethics review is needed where he recruits.

> **Piano listening study**
>
> **What this study is about.** We want to learn which changes to a piano performance
> listeners can hear, and which changes make a performance less enjoyable. You will hear short
> recordings of piano music. All recordings use the same computer piano sound.
>
> **What you will do.**
> - Answer five short questions about your musical background and your headphones.
> - Do a short headphone check.
> - Part A: hear a clip and then two more clips, and say which of the two differs from the first.
> - Part B: hear two versions of a clip and say which one you prefer.
>
> The session takes about [N] minutes, with breaks. Please use headphones in a quiet place.
>
> **Your data.**
> - We do not ask for your name, email, age or any contact details.
> - Your answers are saved under a random code, for example P7K2QX. The file stays on this
>   computer until you or the researcher sends it.
> - We record your answers to the background questions, your choices, and how long each choice
>   took. Nothing else.
> - The anonymous results may be published for research.
>
> **Your rights.**
> - Taking part is voluntary. You can stop at any time by closing this page. Nothing is sent
>   anywhere.
> - If you want your data removed after you sent it, give the researcher your code.
> - Stop if the sound is uncomfortable. Keep the volume at a comfortable level.
>
> **Contact.** Researcher: [name and contact]. Payment: [to be decided].
>
> [ ] I am 18 or older. [ ] I have read the information above and I agree to take part.

## 11. Decisions for the lead and Henry (O-02)

1. **The H6 axis:** detection-threshold units as the primary axis, and the margin of 2
   (section 1-2). The alternatives are in 7.4.
2. **N and format:** 96 listeners doing A2 (about 120 listener-hours; powered for a three-fold
   difference only), 160 listeners, or B2. The internal-pilot rule in section 6 also needs
   approval.
3. **Format and hosting:** one session or two; in person on a lab laptop, or online (which
   needs hosting, a file-return channel and possibly a recruitment platform). The app has no
   server part. Hosting is O-02, and nothing has been published.
4. **Consent and ethics:** the bracketed fields, the payment, and whether an ethics review is
   needed.
5. **Excerpt set:** three of eight excerpts show no harmony change in their detection clip
   (section 3.3). Accept this, or replace E2, E5 and E7 with passages that have more changes.

## 12. Running the app locally

```
uv run python scripts/build_study_s03.py            # renders the 592 pilot clips, about 1.5 min
python3 -m http.server 8000                         # from the repository root, local only
# open http://localhost:8000/study/app/index.html?mode=pilot
uv run python study/app/smoke_test.py --mode main   # headless Chrome, simulated answers
```

- The app also opens from `file://` (the manifest is a script, the audio uses `<audio>`), but a
  local server is more reliable.
- `?stim=<folder>` points the app at another stimulus build.
- `?parts=A` or `?parts=B` runs one part.

## 13. Threats to validity

- **Rendered piano.** Every clip uses one soundfont. Thresholds for real recordings may differ
  (H8). The soundfont's 7 velocity layers may make velocity changes more audible, or less, than
  on a real piano; the Slade JND was measured on a Disklavier.
- **Excerpt sample.** Eight openings, six of them Mozart, Chopin or Schubert. A dimension's cost
  may depend on style, and leave-one-excerpt-out (7.4) checks the verdict's dependence on single
  excerpts.
- **Threshold normalization** makes `beta_d` inherit the error of `theta_d`. The delta method
  covers the variance, not a misfit of the psychometric function.
- **A linear logit in threshold units** may saturate at high levels. The per-level curves (7.2)
  are reported so this can be seen.
- **Pilot on one non-naive listener.** The ladder may be misplaced for naive listeners. The
  simulation (ladder off by a factor 2) shows the cost in power.
