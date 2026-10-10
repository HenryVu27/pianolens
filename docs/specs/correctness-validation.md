# Tier A correctness validation on the synthetic mistake set (F-02)

Measured 2026-09-27 by `feature-engineer`. Code: `src/pianolens/features/correctness.py`, data
`data/processed/mistakes_v1` (D-08, `src/pianolens/data/perturb.py`). Rerun:

```
uv run python scripts/build_mistake_set.py          # 53 s, 12 workers
uv run python scripts/eval_correctness.py           # 3 min, 12 workers
```

Outputs (gitignored): `data/interim/correctness_eval/counts.csv` (tp / fp / fn per performance,
mode, window, level, type) and `summary.csv` (pooled precision / recall / F1).

## Method

- **Data.** 100 (n)ASAP performances, each as a clean copy and with injected mistakes at
  3 rates (mistakes per matched note: 0.02, 0.05, 0.10). The injected mistakes are split equally
  between wrong pitch, extra note and missed note. 246,324 performed notes per rate, 12,995 bars.
  The mistake model is described in the `perturb.py` docstring and the selection in `DATASETS.md`.
- **Pipeline under test.** `align_performance` (parangonar DualDTW, automatic repeat choice)
  on the perturbed MIDI, then `correctness()`.
- **Second mode: `gt_alignment`.** The exact ground-truth alignment of the perturbed
  performance goes into `correctness()`. This isolates the labelling step (wrong-pitch pairing,
  ornaments) from alignment errors.
- **Units.**
  - Extra and wrong pitch: performed notes.
  - Missed: score notes.
  - Bar level: every type, per measure row.
- **Don't care.** Insertions and deletions already in the (n)ASAP ground truth are neither true
  nor false positives. They are 51.7 and 40.5 per 1,000 notes and include both real slips and
  ground-truth noise. At bar level, a bar holding such a natural mistake is don't care for that
  type: 3,881 of 12,995 bars for extra, 3,946 for missed, and 5,949 for "any".
- **Lenient wrong pitch (`wrong_pitch_lenient`).** An injected wrong pitch also counts as found
  when it is labelled extra.

## Default wrong-pitch window: 100 ms (F-02b)

Since F-02b the wrong-pitch pairing window defaults to 100 ms
(`correctness.WRONG_PITCH_WINDOW_SEC`, parameter `wrong_pitch_window_sec`). It is a separate
concept from the 50 ms MIREX / `mir_eval` onset tolerance (`ONSET_TOLERANCE_SEC`): the window
bounds the distance to an *estimated* expected onset (median of the chord-mates, or an
interpolation), which carries chord spread and rolled chords. The lead chose 100 ms in DECISIONS
2026-09-27. Rerun on 2026-09-27 after F-02b; the counts for both windows are identical to the
F-02 run (the evaluation always scored both).

**The ornament test.** With the 100 ms default, `test_grace_note_skipped_and_ornament_extras`
failed in its `ornaments=False` branch. Cause: that branch grades the grace note `g0` (pitch 72)
as an ordinary score note, and its expected onset is the median of its chord-mates, 2.006 s.
The extra note `gx` (pitch 71, 1.95 s) is 1 semitone off and 56 ms early, so it paired with `g0`
as a wrong pitch at 100 ms and missed the 50 ms window by 6 ms. The pairing is correct by the
rule, and nothing changes with `ornaments=True`, where the unplayed grace note is
`ornament_skipped` and the whitelist runs before pairing. The test now checks both windows
explicitly: `wrong_pitch` (`gx` -> `g0`) at 100 ms, `missed` + `extra` at 50 ms.

## Results: pipeline as deployed (`aligned`, window 100 ms)

Precision / recall / F1, pooled over the 100 performances.

| Level | Type | rate 0.02 | rate 0.05 | rate 0.10 |
|---|---|---|---|---|
| note | wrong pitch | 0.920 / 0.872 / 0.896 | 0.944 / 0.852 / 0.896 | 0.950 / 0.814 / 0.877 |
| note | wrong pitch (lenient) | 0.629 / 0.952 / 0.757 | 0.797 / 0.947 / 0.865 | 0.870 / 0.935 / 0.901 |
| note | extra | 0.605 / 0.914 / 0.728 | 0.744 / 0.916 / 0.821 | 0.779 / 0.884 / 0.829 |
| note | missed | 0.385 / 0.899 / 0.539 | 0.583 / 0.894 / 0.706 | 0.691 / 0.864 / 0.768 |
| bar | wrong pitch | 0.998 / 0.897 / 0.945 | 0.997 / 0.893 / 0.942 | 0.996 / 0.882 / 0.936 |
| bar | extra | 0.891 / 0.916 / 0.903 | 0.928 / 0.935 / 0.931 | 0.944 / 0.932 / 0.938 |
| bar | missed | 0.921 / 0.954 / 0.937 | 0.945 / 0.953 / 0.949 | 0.960 / 0.954 / 0.957 |
| bar | any error | 0.978 / 0.977 / 0.977 | 0.990 / 0.984 / 0.987 | 0.993 / 0.986 / 0.989 |

**Noise floor on the unperturbed copies (rate 0).** These are false positives outside the
don't-care set.

- Per 1,000 performed notes:
  - 3.01 extra;
  - 0.35 wrong pitch;
  - 8.33 missed (per 1,000 score-side units).
- Per 1,000 bars:
  - 6.8 flagged for extra;
  - 6.2 flagged for missed;
  - 0 flagged for wrong pitch;
  - 3.4 flagged for any error.

Precision rises with the mistake rate because this floor stays fixed while the number of true
mistakes grows.

## Results: labelling only (`gt_alignment`, window 100 ms)

| Level | Type | rate 0.02 | rate 0.05 | rate 0.10 |
|---|---|---|---|---|
| note | wrong pitch | 0.977 / 0.947 / 0.962 | 0.972 / 0.952 / 0.962 | 0.969 / 0.948 / 0.958 |
| note | extra | 0.964 / 0.954 / 0.959 | 0.964 / 0.957 / 0.960 | 0.962 / 0.955 / 0.958 |
| note | missed | 0.819 / 0.965 / 0.886 | 0.897 / 0.963 / 0.929 | 0.926 / 0.959 / 0.942 |
| bar | any error | 0.986 / 0.985 / 0.985 | 0.993 / 0.991 / 0.992 | 0.995 / 0.993 / 0.994 |

With a perfect alignment, about 5% of wrong pitches stay unpaired at 100 ms (9% at 50 ms). Each
one becomes an extra plus a missed.

## Previous default: 50 ms window (F-02)

`aligned` mode:

| Level | Type | rate 0.02 | rate 0.05 | rate 0.10 |
|---|---|---|---|---|
| note | wrong pitch | 0.939 / 0.838 / 0.886 | 0.956 / 0.813 / 0.879 | 0.965 / 0.774 / 0.859 |
| note | extra | 0.587 / 0.922 / 0.717 | 0.718 / 0.922 / 0.808 | 0.753 / 0.895 / 0.818 |
| note | missed | 0.378 / 0.910 / 0.535 | 0.568 / 0.902 / 0.697 | 0.669 / 0.876 / 0.759 |
| bar | wrong pitch | 1.000 / 0.866 / 0.928 | 0.998 / 0.858 / 0.922 | 0.999 / 0.847 / 0.917 |
| bar | extra | 0.872 / 0.925 / 0.898 | 0.909 / 0.938 / 0.924 | 0.931 / 0.940 / 0.936 |
| bar | missed | 0.902 / 0.960 / 0.930 | 0.928 / 0.959 / 0.943 | 0.946 / 0.962 / 0.954 |
| bar | any error | 0.978 / 0.977 / 0.977 | 0.989 / 0.984 / 0.987 | 0.993 / 0.986 / 0.989 |

Clean-copy floor at 50 ms: 3.09 extra, 0.26 wrong pitch, 8.41 missed per 1,000 notes; 7.2 / 6.3
/ 0 / 3.4 bars per 1,000 flagged for extra / missed / wrong pitch / any.

`gt_alignment` at 50 ms, note wrong pitch: 0.985 / 0.908 / 0.945, 0.979 / 0.910 / 0.944,
0.978 / 0.904 / 0.939 at rates 0.02 / 0.05 / 0.10.

**What 100 ms changes** (`aligned`, rate 0.05, F1): note wrong pitch 0.879 -> 0.896, note extra
0.808 -> 0.821, note missed 0.697 -> 0.706, bar wrong pitch 0.922 -> 0.942, bar extra 0.924 ->
0.931, bar missed 0.943 -> 0.949; bar "any" is unchanged (0.987), since pairing only moves an
error between types. Clean-copy wrong-pitch false positives rise from 64 to 85 (0.26 to 0.35
per 1,000 notes). Both windows were chosen before the first run, and no other value was tried.

## Per composer (`aligned`, rate 0.05, window 100 ms, F1)

| Composer | n | bar any | bar missed | bar extra | bar wrong | note wrong | note extra | note missed |
|---|---|---|---|---|---|---|---|---|
| Bach | 12 | 0.992 | 0.936 | 0.957 | 0.952 | 0.944 | 0.898 | 0.724 |
| Beethoven | 12 | 0.980 | 0.952 | 0.924 | 0.948 | 0.918 | 0.870 | 0.764 |
| Chopin | 12 | 0.988 | 0.936 | 0.938 | 0.926 | 0.880 | 0.789 | 0.704 |
| Debussy | 2 | 0.987 | 0.955 | 0.956 | 0.981 | 0.930 | 0.845 | 0.611 |
| Haydn | 12 | 0.990 | 0.956 | 0.953 | 0.949 | 0.928 | 0.877 | 0.895 |
| Liszt | 12 | 0.995 | 0.947 | 0.931 | 0.937 | 0.827 | 0.741 | 0.559 |
| Mozart | 12 | 0.978 | 0.953 | 0.919 | 0.943 | 0.926 | 0.909 | 0.887 |
| Rachmaninoff | 4 | 0.969 | 0.932 | 0.883 | 0.943 | 0.906 | 0.872 | 0.818 |
| Ravel | 2 | 0.995 | 0.962 | 0.880 | 0.957 | 0.887 | 0.824 | 0.565 |
| Schubert | 12 | 0.988 | 0.952 | 0.935 | 0.942 | 0.917 | 0.807 | 0.692 |
| Schumann | 5 | 0.980 | 0.923 | 0.871 | 0.897 | 0.835 | 0.658 | 0.526 |
| Scriabin | 3 | 0.991 | 0.982 | 0.927 | 0.953 | 0.866 | 0.722 | 0.550 |

Median alignment time: 3.1 s (max 22.2 s). Median match ratio over all 400 runs: 0.937. No
failures in 400 runs. (F-02 reported match ratio per rate: 0.965 clean, 0.935 at rate 0.05,
0.906 at rate 0.10.)

## Reading

- **Bar-level labels are usable for feedback now.**
  - A bar that has an injected mistake is flagged with any-error F1 of 0.98-0.99.
  - Missed-per-bar F1 is 0.94-0.96.
  - Bar-level wrong-pitch flags are almost never false: precision is 0.996 or higher, and the
    clean copies have none.
- **Per-note missed labels are not reliable.**
  - Note-level precision is 0.39-0.69.
  - The clean floor is 8.3 per 1,000 notes.
  - I checked 3 clean performances (133 false-positive missed notes). Every one was a ground-truth
    match. Our aligner had matched the performed note to another score note in 127 cases and
    left it unmatched in 6. So the aligner often picks a different "skipped" duplicate than the
    ground truth (repeated notes, octave doublings), as F-01's deletion F1 of 0.75 predicted.
  - This confirms the DECISIONS rule: report missed notes per bar.
- **Wrong-pitch recall is the weakest bar-level number (0.88-0.90 at 100 ms; 0.85-0.87 at 50 ms).**
  - At note level (rate 0.05), recall is 0.85 through our aligner at 100 ms. With the
    ground-truth alignment it is 0.95 (0.91 at 50 ms). The aligner now accounts for the gap.
  - An unpaired wrong pitch is still reported, as an extra plus a missed. Lenient recall is 0.94-0.95.
- **Harder repertoire scores lower.** Liszt, Schumann and Scriabin are lowest at note level, in
  line with their F-01 alignment F1.

## Caveats

- **The mistakes are synthetic.** Real slips have their own timing and pitch statistics. Only
  real human mistakes can validate F-02 fully (DECISIONS 2026-09-27).
- **Bar-level scores are measured on the bars without natural ground-truth mistakes.** For "any",
  that is 54% of bars. These bars are probably easier than average, so treat the bar numbers as
  optimistic.
- **The set has single-path scores only.** Repeat-choice errors (F-01: 13 of 99) are not
  exercised.
- **The ornament whitelist is untested on real data.** It is covered by unit tests only, and
  injected mistakes are never placed on ornaments.

## Pre-registration BL-20: correctness at high note density (2026-09-29)

Written by `feature-engineer` before any density number was computed. Experiment folder
`experiments/2026-09-29-BL-20-density/`; script `scripts/eval_correctness_density.py`.

**Local note rate.** For each source performance (the rate-0 copy of `mistakes_v1`), performed
onsets are grouped into chords (sorted onsets within 30 ms of a chord's first onset). The local
inter-onset interval (IOI) of chord k is the median of the gaps between consecutive chord onsets
among chords k-2..k+2 (up to 4 gaps). A note takes its chord's local IOI. Bins: < 60 ms,
60-100 ms, 100-200 ms, > 200 ms. The judged dense bin is < 100 ms (the union of the first two);
the two are also reported separately. A bar takes the median local IOI of the source notes whose
ground-truth score note lies in it. Injected items take the local IOI of their source note
(wrong pitch: the note itself; extra: its anchor; missed: the dropped note).

**Part A, stratified F-02 evaluation.** `mistakes_v1` exactly as built (100 performances, rates
0 / 0.02 / 0.05 / 0.10), modes `aligned` and `gt_alignment`, windows 50 and 100 ms. Per bin:
bar-level any-error precision / recall / F1 with the F-02 don't-care rule; for injected wrong
pitches the outcome of the performed note (paired with the intended score note / paired with
another score note / labelled extra / labelled correct, i.e. absorbed by the aligner / other);
false merges (predicted wrong pitches whose performed note is an injected extra or a correct
note). Primary cell: `aligned`, 100 ms, rate 0.05. Cluster bootstrap by source performance,
2,000 resamples, seed 20260929.

**Part B, dense stress set.** Same 100 source performances. Wrong pitches only, one perturbed
copy per cell, up to 10 injections per copy, at least 2 s apart, seed fixed. Cells: density
dense (< 100 ms) or sparse (> 200 ms) x pitch type N (the wrong key equals a pitch played in
chords k-2..k+2, excluding its own chord, 1 or 2 semitones from the true pitch) or O (1 or 2
semitones away and equal to no pitch in chords k-2..k+2 or its own chord). A same-pitch note
still sounding at the wrong note's onset is cut to end 5 ms before it; the wrong note is cut to
end 5 ms before the next same-pitch onset. Per cell: strict recall (labelled wrong pitch and
paired with the intended note), lenient recall (wrong pitch or extra), absorbed share (labelled
correct), bar detection (the injected note's bar has at least one error label), and the change
in the bar's error count against the clean copy (ideal +1; 0 = silent; +2 = split into missed
plus extra; >= +3 = collateral).

**Concern thresholds (any one triggers "concern").**
1. Part A primary cell: bar any-error F1 in the < 100 ms bin is more than 0.03 below the
   > 200 ms bin, and the bootstrap 95% CI of the difference excludes 0.
2. Part A: in any bin with at least 100 injected wrong pitches, more than 5% are paired with
   another score note or absorbed.
3. Part A: strict wrong-pitch recall in the < 100 ms bin is more than 0.10 below the > 200 ms
   bin.
4. Part B (`aligned`, 100 ms): dense-N strict recall more than 0.10 below sparse-O; or dense-N
   bar detection below 0.95; or a silent share above 2%.

Otherwise "pass". Attribution: a deficit present in `gt_alignment` mode belongs to the labelling
step (window, pairing); one present only in `aligned` mode belongs to the aligner. The 50 ms
column is diagnostic only. Bins with fewer than 50 bars or 100 injected items are reported but
not judged. Production defaults are not changed in this ticket; any change is a proposal.

## Pre-registration BL-19: staff is not hand, score-only proxies (2026-09-29)

Written by `feature-engineer` before any proxy was computed. Experiment folder
`experiments/2026-09-29-BL-19-staff-hand/`; script `scripts/staff_hand_proxies.py`.

**Repertoire.** The app catalogue (`data/interim/app/catalog.json`): 221 ASAP scores and 584
PianoCoRe tier A scores with at least 50 references. Folded scores, parts merged
(`load_score_part`), grace notes excluded, tied notes merged.

**Proxies, per score note** (none is ground truth):
- P1 cross-staff voice: the note's staff differs from the most common staff of its MusicXML
  voice in the score (cross-staff beaming, a voice moving to the other staff). Likely misassigned.
- P2 pitch crossing (strict): an upper-staff note below the lowest lower-staff note sounding at
  its onset, or a lower-staff note above the highest upper-staff note sounding at its onset.
  P2-loose (sensitivity): below the highest / above the lowest. Direction of error uncertain.
- P3 one-hand capacity: the notes of one staff starting at one onset number more than 5, or span
  more than 16 semitones (wider than a major tenth). At least one of them is likely played by the
  other hand, unless the chord is rolled (rolls are not detected). All notes of that group are
  flagged.
- Hand words: MusicXML `<words>` directions reading m.d. / m.s. / m.g. / r.h. / l.h. / d. / g. /
  sopra / sotto (and spelled-out forms), with the direction's staff. Counted per score; a
  "contradicting" marker names the other staff's hand. Not mapped to notes.
- At-risk = P1 or P2-strict or P3.

**Hand-sync events**, as `control.hand_synchrony` pairs them but from the score alone: score
onsets (quarters) where staff 1 and staff 2 both have a non-grace note. An event is affected
when any of its notes is at risk. Notes on staves other than 1 and 2 are counted separately
(hand synchrony ignores them).

**Reported:** per piece and per composer (pooled, and median over pieces), per source (ASAP,
PianoCoRe): share of notes per proxy and at risk; share of hand-sync events affected.

**Concern threshold.** "Concern" if the median piece has more than 5% of hand-sync events
affected, or more than 10% of pieces have more than 20% affected. Otherwise "pass for pooled
hand synchrony" (a per-hand feedback claim would still need validation against real hand
labels). PianoVAM is checked for hand or fingering labels that could validate the proxies.

## Pre-registration BL-23: ornament whitelist and same-pitch reassignment (2026-09-29)

Written by `feature-engineer` before any BL-23 number was computed. Experiment folder
`experiments/2026-09-29-BL-23-aligner-ornaments/`; script `scripts/eval_correctness_bl23.py`.
Seen before this section: the published BL-20 tables and audit, the ornament names used in the
ASAP scores (counts of `trill-mark`, `tremolo`, `inverted-mordent`, `wavy-line`, `turn`,
`mordent`), the ornament marks of the 26 BL-20 score notes absorbed at a different pitch (all
ornamented), and the synthetic unit tests. No labeller variant was run on real data.

**Labeller variants** (`features.correctness`, window 100 ms, DF-10 pitch check on in all):
- `L` legacy: `ornament_rule="legacy"`, `reassign=False` (F-02 / BL-20 behaviour).
- `T` tight: `ornament_rule="tight"`: wrong-pitch pairing runs before the ornament whitelist,
  and only the ornament's own pitches are tolerated (trill, wavy line, turn ±2; mordent 0..-2;
  inverted mordent 0..+2; tremolo 0; played grace: its own pitch; unplayed grace ±2).
- `R` reassign: legacy rule plus the post-pass `align.postpass.reassign_same_pitch` (a match
  moves to an unmatched same-pitch note within 100 ms of the leave-one-out expected onset when
  that is at least 30 ms closer; grace and ornamented score notes never move).
- `TR` = `T` + `R`. **`TR` is the candidate.** `T` and `R` are ablations.
The constants (30 ms, 100 ms, the pitch sets) are fixed here and not tuned.

**Data.** (1) F-02 set: `mistakes_v1`, 100 performances x rates 0 / 0.02 / 0.05 / 0.10.
(2) BL-20 stress set: `eval_correctness_density.stress_copy` unchanged, same seeds, so the copies
are identical to BL-20 Part B. (3) Calibration sets of `scripts/calibrate_expert_check_f08c.py`:
the 40 covered clean D-08 copies with their 354 ASAP experts (key-sensor), and the 150 A-01 floor
transcriptions (transcribed, extras not counted). Modes `aligned` (primary) and
`gt_alignment` (diagnostic).

**Clean bar.** A bar with no error label (wrong pitch, missed or extra) in the clean copy of the
same source under the same variant and mode. An injection counts for the clean-bar metrics when
the score bar of its intended note is clean.

**Metrics** (`aligned`, 100 ms unless stated). Strict recall = injected wrong pitch labelled
wrong pitch and paired with its intended score note. Bar detection = the intended bar has at
least one error label after the injection. Cluster bootstrap by source performance, 2,000
resamples, seed 20260929; piece-clustered CIs also reported.

**Success criteria for `TR`** (upper and lower tolerances given for each):
1. *C1, primary.* Stress set, clean bars: dense-N strict recall minus sparse-O strict recall
   within [-0.10, +0.10] (point estimate; CI reported).
2. *C2.* F-02 rate 0.05, clean bars: strict recall of injected wrong pitches with local IOI
   < 100 ms minus > 200 ms within [-0.10, +0.10].
3. *C3.* Stress dense-N bar detection in clean bars at least 0.95 (upper bound 1).
4. *N1, no cost in sparse passages.* Stress sparse-O strict recall on bars clean under both `L`
   and `TR`: `TR` minus `L` at least -0.02. Upper: a gain above +0.10 is checked by hand before
   acceptance.
5. *N2, F-02 bar flags.* Bar any-error precision and recall (F-02 don't-care rule) at each rate
   0.02 / 0.05 / 0.10: `TR` minus `L` at least -0.005 each. Upper: a gain above +0.02 is checked
   by hand.
6. *N3, genuine ornaments (ASAP ornament cases).* On the 100 clean copies (`aligned`), take every
   performed note that `L` tolerates as an ornament (label `ornament`, or a different-pitch match
   kept correct by the ornament rule). At most 5% of them may be labelled `extra` or
   `wrong_pitch` by `TR`; and of the clean-copy bars error-free under `L` that contain such a
   note, at most 5% may be flagged under `TR`. Lower bound 0.
7. *N4, expert false flags.* The F-08c per-bar check (q80 / q99), with the global limits
   (`CORRECTNESS_EXPERT_BARS` quantiles) recomputed from each variant's own clean D-08 bars.
   Share of expert bars notable-or-strong: `TR` minus `L` within [-1.0, +0.5] percentage points;
   strong within [-0.5, +0.25] points. Judged for key-sensor experts and for the transcribed
   floor. (A fall beyond the lower bound would mean real slips in expert playing are hidden.)

**Verdict and decision.** "Pass" if all seven hold. `TR` becomes the default of `correctness` if
N1-N4 hold and its clean-bar dense-N strict recall is above `L`'s; if C1-C3 do not all hold the
verdict is "partial". If `TR` fails any of N1-N4, `T` and then `R` are checked against N1-N4 in
that order and the first that passes and improves dense-N strict recall becomes the default;
otherwise `L` stays. If the default changes, the calibration constants that depend on the labels
(`CORRECTNESS_EXPERT_BARS`) are recomputed with the new default and changed in
`report/calibration.py`; the BL-18 transcribed strong-tier constants are reported, not changed.

**Also reported.** DF-10: how many aligner matches are dissolved as different-pitch in each set,
and what happens to the 26 BL-20 different-pitch absorptions. Reproduction check: `L`,
`aligned`, all injections, must reproduce BL-20 Part B strict recall and absorbed shares.
Outcome shares per cell (paired intended / other, absorbed, extra, ornament).

## Pre-registration DF-13: wrong-pitch pairing window on transcribed input (2026-10-10)

Written by `feature-engineer` before any held-out transcription was drawn or aligned. Experiment
folder `experiments/2026-10-10-DF-13-pairing-window/`; script
`scripts/eval_pairing_window_df13.py`; outputs (gitignored) `data/interim/df13/`.

**Problem (DF-12 / DF-13).** On transcribed input 16-19% of injected wrong notes are not counted
as wrong (BL-18b audit, item 4). The audit attributed most of the loss to the 100 ms pairing
window. **Seen before this section (dev only, all disclosed):** the BL-18b targeted copies were
regenerated (238 targets, identical to the audit) and the 6,765 injected notes followed per rule.
The audit split reproduces (counted in the same bar 83.4 / 80.4%, unpaired 10.1 / 13.3%,
absorbed 4.9 / 4.1%, ornament 1.5 / 2.0%; Transkun V2 / Aria-AMT). New: of the unpaired notes,
only 146 / 215 (43% / 48%) have their intended score note labelled missed; in the rest the
aligner re-matched the intended score note to another performed note of the same pitch, whose
onset is a median 0.28 / 0.37 s from the note's expected onset (the realignment after the
injection moves matches; in the clean copy that note was mostly matched to another score note). No pairing
window can recover those. So the **window-reachable loss is 4.3% (Transkun V2) / 6.4%
(Aria-AMT) of injected notes**, about half of the unpaired share. A robust (outlier-knot) time
map was also tried on dev and recovered fewer notes than the current one; it is not a candidate.

**Rules** (`features.correctness`, parameter `wrong_pitch_window`; the code exists and is not
default; constants fixed here and not tuned further):
- `fixed` (baseline): 100 ms (`WRONG_PITCH_WINDOW_SEC`), as deployed.
- **`tempo` (primary):** 0.4 quarter note at the local tempo, clipped to [0.1, 0.3] s. Local
  seconds per quarter: slope of the time map between the knots 3 positions before and after the
  note's score onset.
- `error` (first fallback): 2 x the largest leave-one-out onset residual
  (`align.postpass.loo_expected_onsets`) among matched notes within 3 distinct score onsets,
  clipped to [0.1, 0.3] s.
- `wide` (second fallback): 200 ms everywhere.
Pair costs stay in units of 100 ms, so "closest first" is closest in seconds for every rule.
The primary was chosen on dev, where it had the best balance (dev values below). The constants
0.4 / 2 / 200 ms / 0.3 s were picked from a small dev sweep (fixed 150-300 ms, tempo 0.25-0.4
quarter, error factor 1-2, caps 0.25-0.4 s).

**Dev set** (already seen): the BL-18b pieces, experts and targets (12 pieces, 15 experts and
up to 10 targets per family, 238 usable targets), the BL-18b D-08 copies (seed 1) and targeted
copies (seed 2; injections may equal a pitch written in the same bar, flagged as collisions).

**Held-out set** (new): PianoCoRe pieces with at least 25 transcriptions in each family and
exactly one score.mxl, excluding Henry's 5, the 6 BL-18 T2 pieces and the 12 BL-18b pieces:
241 pieces qualify (count only, computed before the draw). Draw **16 pieces**, seed 1010
(`numpy.random.default_rng`), from the pool sorted by piece id. Per piece and family
(family = transcriber = source corpus: Transkun V2 = PERiScoPe, Aria-AMT = Aria-MIDI; reported
separately, never pooled for a verdict): the transcriptions sorted by id minus every id used in
the A-01 floor, BL-18 and BL-18b, permuted with the same generator; the first 15 are experts,
the next 10 targets. Alignments with match ratio below 0.8 are dropped. Each target gets a D-08
copy (rate 0.05, seed 1, as BL-18b) and a targeted copy (seed 2, the BL-18b procedure: up to 10
spaced clean bars where every expert has at most 1 wrong note under `fixed`, 3 wrong pitches
±1 / ±2 each) with the **collision fix**: a new pitch may not be any pitch written in that bar
of the score. Every job is aligned once per copy; every rule labels the same alignment, and a
target is checked against expert tables labelled with the same rule.

**Metrics** (per family; point estimates decide; piece bootstrap 95% CI, 2,000 resamples, seed
0, and a t-interval over pieces reported):
- Targeted injected notes: strict recall (labelled wrong pitch and paired with the intended
  score note), mispair (wrong pitch with another score note), unpaired, absorbed, ornament.
- Clean transcriptions (experts and targets): wrong-pitch labels per 1,000 graded score notes,
  and per 1,000 performed notes in fast runs (`build.fast_run_notes`, local IOI < 100 ms). On
  clean copies every new pair is counted as a false pairing (an upper bound: some are real
  transcriber or performer pitch errors).
- Report level, rule P = R1(0) + run rule (the interim transcribed default), extras not
  counted: clean strong and notable+ rates outside runs; strong share of targeted bars (the
  end-to-end DF-12 measurement, E0); D-08 injected-bar strong and notable+ (information).
- Dense passages: strict and mispair of targeted injected notes in fast runs.

**Criteria for a candidate, per family** (candidate minus `fixed`; "pt" = percentage point):
- **B1, benefit (rule-relative, detection floor):** strict recall gain in [+1.5, +10] pt. Above
  +10 pt is checked by hand before acceptance (the dev window-reachable loss is 4-6%).
- **M1, mispairing:** mispair increase at most +1.5 pt and at most one third of the B1 gain (at
  least about 75% of the newly paired injected notes go to the intended note).
- **F1, clean false pairing:** clean wrong-pitch label rate up by at most 15% of the baseline
  rate.
- **R1, clean strong:** |change| of P's clean strong rate at most 0.25 pt. (Whether the rate lies
  in BL-18b's band [0.30, 1.25]% is reported as information; it is a property of the tier rule
  and of the piece sample, and both `fixed` and the candidate are shown.)
- **R2, clean notable+:** |change| at most 0.5 pt.
- **E1, end-to-end (rule-relative, detection floor):** strong share of targeted 3-wrong-note
  bars up by [+2, +20] pt. The baseline share E0 is the tracked DF-12 number.
- **D1, dense passages (BL-20 risk):** in fast runs, strict recall change at least -1.0 pt,
  mispair increase at most +1.5 pt, and the clean fast-run wrong-pitch rate up by at most 25% of
  its baseline.

**Verdict and action.** A candidate PASSes when B1-E1 and D1 hold in both families, is PARTIAL
in one, FAILs in neither. Order: `tempo`; if it does not PASS, `error`, then `wide` (the same
criteria; this ordered fallback is a multiple comparison and is reported as such). The first
candidate that PASSes becomes the rule for **transcribed input only**: `correctness` resolves
the window rule from the performance provenance (`transcribed` -> the rule; every other
provenance, including Disklavier and other key-sensor input, keeps `fixed`, checked by a unit
test). Then: the A-01 floor expert tables are rebuilt with the rule, Henry's 10 reports are
rerun into `data/interim/reports/henry_df13/`, the BL-18b C1-C3 measurements are reported
under the rule on dev and held-out, and every transcribed calibration value that moves is
reported; key-sensor constants (`CORRECTNESS_EXPERT_BARS`) are not touched. A PARTIAL is not
implemented per family (family is confounded with corpus, BL-18 audit); if no candidate
PASSes, `fixed` stays and the lead decides.

**Dev values** (computed before this section; Transkun V2 / Aria-AMT; `tempo`): B1 +3.3 / +3.7
pt; M1 +0.8 / +0.5 pt; F1 +8.9% / +9.5% (+0.41 / +0.72 per 1,000); R1 +0.00 / +0.05 pt; R2 +0.03
/ +0.11 pt; E0 71.5% / 68.4% (reproduces BL-18b C4) -> E1 +5.8 / +6.2 pt; D1 strict +0.7 / +1.6
pt, mispair +0.3 / 0.0 pt, clean fast +13% / +11%. `error` and `wide` also meet every criterion
on dev, with larger fast-run mispair and clean increases.

**Reachability** (R-09 lesson; dev per-piece sums, 2,000 resamples of 16 pieces per family):
if the dev effect is true, `tempo` PASSes with probability 0.64, is PARTIAL 0.34, FAILs 0.02;
the binding criterion is M1 in Transkun V2 (0.76; its dev value +0.8 pt is close to one third of
+3.3 pt). (`error`: 0.51 / 0.42 / 0.07; `wide`: 0.39 / 0.48 / 0.13.) If a rule had no effect,
B1 and E1 fail by their floors, so FAIL is reachable; PASS needs a real gain.

**Also reported.** Outcome shares per rule; D-08 note outcomes with collisions split out; the
held-out collision count (zero by construction for targeted copies); the share of unpaired
losses whose intended score note was re-matched by the aligner (not reachable by any window;
proposed as a separate fix).

End of the DF-13 pre-registration.

### DF-13 results (Provisional, awaiting eval-auditor)

Recorded below the pre-registration's end marker, so its anchor hash is unchanged. Details,
tables and the run record: `experiments/2026-10-10-DF-13-pairing-window/README.md`.
**FAIL by the pre-registered rule**: `tempo` and `error` fail in both families, `wide` is
PARTIAL (Transkun V2 only); `fixed` (100 ms) stays. `tempo` meets every criterion except F1
(clean wrong-pitch label rate +15.02% Transkun V2, +16.8% Aria-AMT, against at most +15%),
with strict recall +3.6 / +4.7 pt and targeted 3-wrong bars strong 73.0 -> 78.5% / 69.0 ->
76.2%. One piece (Ravel, "Scarbo") holds about half of the added clean pairs.
