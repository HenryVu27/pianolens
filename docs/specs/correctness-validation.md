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
