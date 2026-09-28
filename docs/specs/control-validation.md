# Tier B control: evenness variants, harmony rule and pedal window (F-04b)

Measured 2026-09-27 by `feature-engineer`. Code: `src/pianolens/features/control.py`. Rerun:

```
uv run python scripts/validate_control_f04b.py            # harmony grid + pedal, about 8 min
uv run python scripts/check_control_f04.py                # F-04 sanity run, now with strict evenness
```

Outputs (gitignored) go to `data/interim/control_f04b/`:

- `harmony_grid.csv`: tp / fp / fn per movement, rule variant, ground-truth kind and tolerance.
- `harmony_errors.csv`: every miss and false alarm, with its category.
- `texture.csv`, `pedal_lifts.csv`, `pedal_threshold.csv`, `pedal_window.csv`.

The F-04 sanity outputs go to `data/interim/control_f04/`.

## Summary

- **Strict evenness** is added next to the broad rule (`even_strict_*`). It covers 0 to 46% of
  score onsets, against 24 to 99% for the broad rule. R-04 decides which one to keep.
- **Note rate** (`even_note_rate_nps`, `even_strict_note_rate_nps`) is now reported per run, per
  bar and in the summary. Unevenness rises with rate, so compare `even_*` values only at similar
  rates.
- **Harmony rule, validated against DCML labels** on Batik-plays-Mozart (36 movements, 11,675
  root changes, tolerance 1 quarter note):
  - The F-04 rule scored precision 0.759, recall 0.696, F1 0.726.
  - Two changes, adopted as the new default:
    - the window is **one quarter note**, not one beat;
    - the major-7 and minor-7 templates are **dropped**.
  - The new rule scores precision 0.749, recall 0.774, **F1 0.761**.
  - On held-out sonatas, F1 rose from 0.710 to 0.752.
- **Pedal window and threshold kept** (0.25 beat before, 0.5 beat after; CC64 >= 64).
  - Expert lifts cluster at the harmony change: Vienna K.331, median -0.02 beats.
  - The blur fraction barely moves for thresholds from 32 to 112.
  - Narrowing the window would flag clean expert pedalling as blurred.

## 1. Strict evenness variant

**Rule** (`strict_runs`, module docstring feature 2). A strict run lies inside a broad run and
meets all of these conditions:

- Its notes are sub-beat: the notated duration is below one beat.
- It has at least `run_min_notes` (6) onsets.
- Every onset belongs to a **monotone stretch** or a **repeated figure**, or to both.
  - A monotone stretch moves in one pitch direction throughout, judged on the top pitch of each
    onset. Examples: scales, arpeggio runs.
  - In a repeated figure, the set of pitches at an onset recurs exactly with a period of 1 to 4
    onsets, at least twice. Examples: Alberti bass, broken chords, repeated notes.
- Stretches that touch or overlap merge into one run.

The same IOI-CV and velocity-SD statistics are computed on strict runs. Each strict run records
its `kind`: `monotone`, `figure` or `mixed`.

**Tests with known answers** (`tests/features/test_control.py`):

- **Mixed texture.** The score has a scale, a zigzag melody, an Alberti bass, a repeated-note
  bass and a quarter-note scale.
  - Broad runs: 5.
  - Strict runs: 3: the scale (monotone), the Alberti bass and the drum bass (figures).
  - Neither the zigzag nor the quarter notes form a strict run.
- **Noise on the zigzag only** (20 ms).
  - Broad CV > 0.02.
  - Strict CV < 0.005. The only trace of the noise comes through the smooth time map.
- **A 16-bar scale under a ritardando** is one monotone strict run with CV below 1e-4.
- **Note rate.** Eighths at 0.25 s and quarters at 0.5 s give:
  - 4 and 2 notes/s per run;
  - 3 notes/s in bar 1;
  - the pooled summary rate.

**On real performances** (F-04 sanity set, medians per group):

| Group | broad share | strict share | broad CV | strict CV | broad vel SD | strict vel SD | broad rate (notes/s) | strict rate (notes/s) |
|---|---|---|---|---|---|---|---|---|
| Bach BWV 848 prelude (6 ASAP) | 0.84 | 0.34 | 0.099 | 0.110 | 5.97 | 4.27 | 7.4 | 8.7 |
| Chopin Op.10/12 (6 ASAP) | 0.97 | 0.37 | 0.299 | 0.302 | 9.25 | 7.03 | 9.5 | 9.2 |
| Schubert D.899/3 (6 ASAP) | 0.82 | 0.07 | 0.242 | 0.347 | 7.74 | 7.89 | 5.3 | 8.3 |
| Batik K.279/1 | 0.83 | 0.39 | 0.156 | 0.146 | 6.10 | 5.57 | 7.5 | 7.8 |
| Vienna Chopin Op.10/3 (22) | 0.99 | 0.46 | 0.142 | 0.147 | 8.21 | 6.00 | 1.6 | 2.1 |
| Vienna Mozart K.331 theme (22) | 0.24 | 0.00 | 0.095 | n/a | 5.26 | n/a | 2.4 | n/a |

Reading the numbers:

- **The strict rule is much narrower.** In Schubert D.899/3 the strict rule keeps only the fast
  triplet figuration (7% of onsets). Its CV there is higher than the broad CV (0.35 against
  0.24). The broad rule mixes in slow melody and bass notes, which are played more evenly
  relative to their length.
- **Strict velocity SD is lower in 4 of the 5 groups that have strict runs.** The exception is
  Schubert (7.9 against 7.7). Strict runs leave out melodies, where velocity shaping is intended.

Reference ranges from the landscape doc, section 1.5, all from instructed metronomic scales:

- Professionals: IOI SD of about 8 to 9 ms at 8 notes/s, a CV of about 0.07 (van Vugt 2013).
- Audible unevenness: about 10 ms, a CV of about 0.08.
- Smallest audible velocity step: 2.7 to 4.5 MIDI units (Slade 2023).

Our values are tempo-normalized repertoire values: CV 0.10 to 0.35 at 5 to 9 notes/s. They also
contain expressive micro-timing and alignment noise. The nearest comparison is Bach BWV 848 at
about 8 notes/s: strict CV 0.11, against the scale floor of 0.07. Use the published values as a
floor, not a norm.

## 2. Harmony-change rule against DCML annotations

### Ground truth

- **Labels.** DCML harmony labels for the Mozart sonatas (Hentschel, Neuwirth, Rohrmeier, TISMIR
  2021). They come from the `annotations` submodule of Batik-plays-Mozart
  (DCMLab/mozart_piano_sonatas).
  - License: **CC BY-NC-SA 4.0**, per `annotations/LICENSE` and the README. `DATASETS.md` still
    says "not checked" for this submodule. That is a data-engineer path, so this ticket did not
    edit it.
  - No download was needed.
- **Placement on the score.** The Batik repo attaches each label to a score note id
  (`score_parts_annotated/<stem>_spart_harmony.csv`). The file is unfolded like the match
  files, so each label maps straight to a performed-score beat.
- **Chord content.** Chord tones and root come from `annotations/harmonies/*.tsv`, as fifths
  above the local tonic. They were joined on (mn, label, globalkey, localkey): 14,796 of 14,796
  labels joined.
- **Two kinds of ground-truth change:**
  - `root`: the absolute root pitch class changes. This is the primary kind, with 11,675
    changes. Inversions, suspensions and added tones do not count.
  - `pcset`: the chord-tone pitch-class set changes, with 13,801 changes. V to V7 counts here.
- **Matching.** Detected and annotated changes are matched greedily one to one, by distance,
  within a tolerance. The main tolerance is 1 quarter note, which is comparable across metres.
  Tolerances in beats are in the grid file.
- **Split.** Rule variants were chosen on 15 dev movements (K.279 to K.283) and checked on 21
  test movements (K.284, K.330 to K.333, K.457, K.533).

### F-04 rule (baseline)

The F-04 rule used a 1-beat window, all 9 templates, weight 0.15 and a bass-change requirement.

| Ground truth | Tolerance | Precision | Recall | F1 |
|---|---|---|---|---|
| root | 1 quarter | 0.759 | 0.696 | 0.726 |
| root | 0.5 quarter | 0.732 | 0.672 | 0.701 |
| pcset | 1 quarter | 0.797 | 0.618 | 0.696 |

- By split (root, 1 quarter): dev F1 0.755, test F1 0.710.
- By time signature, the beat-sized window is the problem:
  - 2/2 (half-note beat): recall 0.56. Two chords fall into one window.
  - 6/8 (eighth-note beat): precision 0.60. Non-chord tones start new "harmonies".

### Failure modes of the F-04 rule (root, tolerance 1 quarter)

**Misses: 3,551.**

| Category | Count | What happens |
|---|---|---|
| Two changes in one window | 1,240 | Harmonic rhythm is faster than the window, e.g. ii6 to V within one half-note beat in 2/2 |
| Union fits one chord | 1,169 | The two windows together fit a template. Root a fifth apart: 654; a third: 283. Incomplete I + V fills a major 7th; vi + I fills a minor 7th |
| Same bass | 1,130 | Pedal points and common-bass progressions, e.g. I to IV6/4 over a tonic pedal |
| Detected 1 to 2 windows away | 12 | |

- 763 misses fall on or next to an annotated DCML pedal point.
- 1,955 misses are at inverted chords.

**False alarms: 2,585.**

| Category | Count | What happens |
|---|---|---|
| Label change, same root | 1,886 | The bass moves under one harmony: an inversion change (I to I6), or V(64) to V |
| Non-chord tones | 541 | Passing or neighbour tones hold 15% or more of a window |
| Chord tones only | 158 | The chord is outside the templates, e.g. augmented sixths or added-note labels |

Most false alarms are bass moves within one root. For pedalling, these are arguably real events:
holding the pedal over a new bass note blurs two bass notes. Against the `pcset` ground truth,
precision is 0.797.

**By left-hand texture of the bar** (F-04 rule):

| Texture | Precision | Recall | F1 |
|---|---|---|---|
| broken (Alberti, broken chords) | 0.822 | 0.639 | 0.719 |
| chordal | 0.787 | 0.705 | 0.744 |
| sparse (bass line) | 0.745 | 0.734 | 0.739 |
| no LH | 0.279 | 0.568 | 0.374 |

- Broken-chord texture has the highest precision and the lowest recall. The rule is built not to
  react to figuration within a chord.
- Right-hand-only bars are poor. With no left hand, the lowest melody note acts as a false bass.
  There are 430 detections and 183 true changes in such bars.

### Variants tried

The grid covered:

- template sets: all, no maj7, functional, triads only;
- bass-change requirement: on or off;
- minimum weight: 0.10, 0.15, 0.25;
- window: 0.5, 1 or 2 beats, or 0.5, 1, 1.5 or 2 quarters.

That is 168 variants. One factor at a time from the baseline (root, 1 quarter, F1):

| Change | Dev F1 | Test F1 |
|---|---|---|
| none (baseline) | 0.755 | 0.710 |
| window 1 quarter instead of 1 beat | 0.761 | 0.742 |
| templates "functional" (no maj7, min7) | 0.767 | 0.729 |
| templates "no maj7" | 0.763 | 0.723 |
| templates triads only | 0.752 | 0.722 |
| minimum weight 0.10 | 0.775 | 0.728 |
| minimum weight 0.25 | 0.696 | 0.645 |
| no bass-change requirement | 0.749 | 0.711 |
| window 0.5 beat / 2 beats | 0.716 / 0.664 | 0.707 / 0.629 |

The best dev variant was functional templates, weight 0.10 and a 1-quarter window: dev F1 0.786,
test F1 0.751. It gains nothing on test over weight 0.15 (test F1 0.752).

### Adopted rule

The new default is a 1-quarter window, "functional" templates, weight 0.15 and the bass-change
requirement. In `ControlConfig` these are `harmony_window=1.0`, `harmony_window_unit="quarter"`
and `harmony_templates="functional"`.

Why these two changes:

- **The quarter window** removes the dependence on the metre's beat unit. That dependence was
  the largest structural error.
- **Dropping maj7 and min7** removes the main way two incomplete chords a fifth or a third apart
  merge into one template.
- Both changes help on dev and on test, and both have a musical reason. The weight change was
  not adopted: its test gain was small.

| Ground truth | Tolerance | Precision | Recall | F1 (F-04 rule) |
|---|---|---|---|---|
| root | 1 quarter | 0.749 | 0.774 | **0.761** (0.726) |
| root | 0.5 quarter | 0.726 | 0.749 | 0.737 (0.701) |
| pcset | 1 quarter | 0.790 | 0.690 | 0.737 (0.696) |

**By split** (root, 1 quarter): dev 0.780, test 0.752.

**By time signature** (F1, with the F-04 rule in brackets):

| 2/2 | 2/4 | 3/4 | 3/8 | 4/4 | 6/8 |
|---|---|---|---|---|---|
| 0.766 (0.690) | 0.794 (0.771) | 0.743 (0.727) | 0.761 (0.732) | 0.751 (0.743) | 0.768 (0.699) |

**By texture** (F1): broken 0.760, chordal 0.786, sparse 0.765, no LH 0.407.

**Remaining misses: 2,640.**

- Same bass: 1,145.
- Two changes in one window: 846.
- Union fits one chord: 592.

**Remaining false alarms: 3,020.** 2,297 of them are bass moves under one root.

Pedal points and common-bass progressions are now the largest miss category. The rule cannot
see them by design: it needs a bass change.

**Tests.**

- In 2/2, C and G triads alternating every quarter give 15 changes with the new rule and 0
  with the 1-beat rule.
- Incomplete I (C-E) and V (G-B) alternating give 7 changes with the functional templates and
  0 with all templates.

**Effect on the F-04 sanity set** (median `pedal_blur_fraction`, old rule then new):

- Chopin Op.10/12: 0.22 then 0.24.
- Schubert D.899/3: 0.034 then 0.062.
- Vienna K.331: 0 then 0.020.
- The other groups stay at 0.

## 3. Pedal lift window and CC64 threshold

### Data

- **Batik.** 36 movements, with Bösendorfer sensor pedal data. Ground truth is the DCML root
  changes above.
- **Vienna 4x22, Mozart K.331 theme.** 22 performances, with sensor pedal data.
  - The DCML labels of the Batik K.331/1 score were mapped by theme bar and offset in the bar.
    The 36 unfolded Vienna bars follow the pattern 1-8, 1-8, 9-18, 9-18.
  - This gives 1,320 changes.
- **Vienna Chopin Op.10/3.** 22 performances. There are no annotations, so it uses the detected
  changes (new rule) as a proxy.

### Method

- Change times come from the performed onsets, as in `pedal_blur`.
- A "lift" is a CC64 crossing from at least 64 to below 64.
- For each change where the pedal was down 1 beat earlier, the nearest lift within ±1 beat is
  found. Its offset is measured in local beats.
- **Control.** The same measurement at score onsets at least 1 beat from any label boundary.
  The number of control onsets is capped at the number of changes per movement.

### Lift offsets (threshold 64)

| Source | Changes | Pedal down 1 beat before | Lift in [-0.25, +0.5] | q10 | median | q90 | median (s) |
|---|---|---|---|---|---|---|---|
| Batik, GT root | 11,675 | 2,625 | 0.529 | -0.73 | -0.21 | +0.12 | -0.11 |
| Batik, control onsets | 8,286 | 2,178 | 0.427 | -0.83 | -0.17 | +0.49 | -0.10 |
| Vienna K.331, GT root | 1,320 | 406 | 0.865 | -0.32 | -0.02 | +0.17 | -0.01 |
| Vienna Op.10/3, detected | 396 | 211 | 0.962 | -0.03 | +0.01 | +0.07 | +0.02 |

Reading the numbers:

- **Vienna.** Most of the 22 pianists lift within about a quarter beat of the annotated change:
  q10 -0.32, q90 +0.17. This is the legato-pedal behaviour the rule assumes. In Op.10/3 the
  lift comes just after the detected change (median +0.013 beats), as the F-04 memory noted.
- **Batik.**
  - Batik pedals little in Mozart: the pedal is down before only 22% of root changes.
  - When he pedals, he lifts *before* the change: median -0.21 beats, -0.11 s.
  - His lifts are frequent near non-change onsets too (0.43 against 0.53), so they are only
    loosely tied to root changes.
  - `pedal_blur` counts an early lift as clean, because the pedal is then up at
    t - 0.25 beat, so this style is handled.

### Blur fraction on ground-truth root changes, by window

Threshold 64; mean over movements or performances. Columns are `before`, rows are `after`, both
in beats.

| after \ before | Batik 0 | Batik 0.125 | Batik 0.25 | Batik 0.5 | Vienna K.331 0 to 0.25 | Vienna K.331 0.5 |
|---|---|---|---|---|---|---|
| 0.125 | 0.056 | 0.022 | 0.013 | 0.008 | 0.099 | 0.090 |
| 0.25 | 0.045 | 0.017 | 0.010 | 0.006 | 0.030 | 0.029 |
| **0.5** | 0.028 | 0.011 | **0.006** | 0.004 | **0.008** | 0.008 |
| 1.0 | 0.006 | 0.003 | 0.001 | 0.001 | 0.005 | 0.005 |

- With the default window, expert blur is at most 1%: 0.6% for Batik, 0.8% for Vienna K.331.
- Shrinking `after` to 0.25 beat would flag 3% of the Vienna experts' changes as blurred. Those
  lifts come just after the new chord, which is what legato pedalling looks like.
- Shrinking `before` to 0 would flag 2.8% of Batik's changes, where he lifted just before the
  chord.
- Widening either side lowers these numbers only slightly, and a wider window would let real
  blur pass as clean.
- **Verdict: keep 0.25 before and 0.5 after.** The evidence covers only two expert sources, and
  no student data. There is no case for a different window.

### Threshold

Median blur fraction on GT root changes, by threshold:

| CC64 threshold | 16 | 32 | 48 | 64 | 80 | 96 | 112 |
|---|---|---|---|---|---|---|---|
| Batik | 0.064 | 0.009 | 0.004 | 0.004 | 0.003 | 0.002 | 0.000 |
| Vienna K.331 | 0.067 | 0 | 0 | 0 | 0 | 0 | 0 |
| Batik pedal-down time share | 0.54 | 0.41 | 0.34 | 0.31 | 0.30 | 0.28 | 0.27 |
| Vienna K.331 pedal-down time share | 0.76 | 0.64 | 0.55 | 0.43 | 0.24 | 0.08 | 0.02 |

- The blur fraction is flat from 32 to 112. Only 16 differs: it falls within the resting-foot
  range, where 49% of Batik's CC64 events (194,489 of 398,990) lie below 32.
- The pedal-down time share depends strongly on the threshold for the Vienna pianists. They use
  partial depths a lot (Bernays and Traube 2014).
- **Verdict: keep 64.** Blur does not depend on the threshold choice, but `pedal_down_fraction`
  does. Read it as context only.

## Limits

- The ground truth is one annotation style (DCML) on one composer (Mozart). In Romantic
  repertoire the pedal-point and non-chord-tone rates differ, so the numbers may not transfer.
- The dev/test split is by sonata, not by independent annotators. Both splits share the style.
- Pedal evidence comes from two expert sources. Batik pedals sparsely. The Vienna K.331 theme is
  18 bars. No student pedalling was measured, so the window's power to separate skill levels is
  untested.
- The note rate uses performed IOIs, so it includes the performer's tempo. That is the intent:
  unevenness depends on the rate actually played.
