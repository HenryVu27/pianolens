# Fast repeated notes: transcription recall by inter-onset interval
Ticket: BL-21    Owner: audio-engineer    Status: Confirmed with caveats (eval-auditor 2026-09-29; text fixes applied)

## Pre-registration

The question, unit, bins, measure and decision rule were written before any repeat-recall number
was computed. They are in `docs/specs/phone-audio-baseline.md`, section "BL-21 pre-registration"
(2026-09-29, 15:41 CDT). sha256 of that section (from its `## ` header up to the next `## `
header): `5b9508aac736e92771304623b2ea170a7db9e5e88a42db17514d2e52bcced11f`.

In short, a *repeat* is a true note whose previous same-pitch true note started less than 500 ms
earlier. Recall is the share of notes matched by a transcribed note of the same pitch within
50 ms, after removing the clock offset. It is compared with *reference* notes, which have no
same-pitch onset in the previous 500 ms. A bin **matters** if the drop from the reference is at
least 2.0 points and its recording-bootstrap 95% CI excludes 0. Tempo: bpm = 15,000 / IOI (ms)
for sixteenth-note repeats.

## Data and method

- **PianoVAM** v1.2 microphone audio (84 recordings, 10 amateur pianists, 343,550 true notes),
  with Disklavier MIDI as truth. Transkun 2.0.1 outputs are reused from A-01b.
- **Aria-AMT** `piano-medium-double-1.0` on PianoVAM. There were no existing outputs, so it was
  run on the pre-registered subset: per pianist, the recording with the most true repeats under
  200 ms, chosen from the truth MIDI only, capped at 2 h.
  - The cap dropped 2 of 10 pianists, leaving 8 recordings (1.45 h of audio, 42,833 true notes).
  - Run time was 4,111 s on MPS, fp32 (`scripts/transcribe_aria_amt_mac.py`).
  - Transkun on the same 8 recordings is reported next to it.
- **Rendered path.** The A-01 controlled check: 3 MAESTRO Disklavier performances rendered with
  the S-02 renderer (Salamander, FluidSynth), `clean` and simulated `phone`, with both
  transcribers. The outputs were already on disk.
- Bootstrap: 2,000 resamples over recordings, seed 0. A second table clusters by pianist.
- Code: `scripts/bl21_repeated_notes.py` (`subset`, `run`). Outputs go to
  `data/interim/pianovam_bl21/` (gitignored; PianoVAM is CC BY-NC-SA 4.0).

## Command

```
uv run python scripts/bl21_repeated_notes.py subset
bash <scratchpad>/run_aria.sh      # transcribe_aria_amt_mac.py on the 8 subset files, --names <stems>
uv run python scripts/bl21_repeated_notes.py run
uv run python scripts/bl21_repeated_notes.py takes     # post hoc take-level counts (aggregate only)
```

Run record: 2026-09-29. Git `dd13ab2` plus uncommitted working-tree changes; the repo carries
uncommitted edits by other agents. Script sha256 at run time:
`scripts/bl21_repeated_notes.py` 1f555a87...c32329. It is `53970391...1e75d090d` after
lint-only edits (no logic change), and `9157848e...56713e6b` after the `takes` stage was added
post audit. The `run` stage is unchanged. Data: PianoVAM HF commit 1f039ab9
(DATASETS.md).

## Results

### Primary: PianoVAM, Transkun, all 84 recordings

| Same-pitch IOI | Repeats | Recall [95% CI] | Drop vs reference, points [95% CI] | Matters? |
|---|---|---|---|---|
| < 80 ms | 434 | 0.327 [0.268, 0.379] | 64.9 [59.9, 70.7] | yes |
| 80-120 ms | 1,775 | 0.889 [0.849, 0.923] | 8.7 [5.5, 12.5] | yes |
| 120-200 ms | 14,971 | 0.969 [0.956, 0.978] | 0.7 [-0.2, 1.8] | no |
| 200-500 ms | 68,325 | 0.972 [0.965, 0.979] | 0.4 [-0.0, 0.8] | no |
| Reference (> 500 ms or first) | 258,045 | 0.976 [0.971, 0.980] | | |

- Clustering by pianist instead of recording gives the same verdicts: 64.9 [60.1, 71.2],
  8.7 [5.6, 12.1], 0.7 [-0.9, 3.1] and 0.4 [-0.0, 0.9].
- In the < 80 ms bin, 61 repeats are under 50 ms, and only 3 of them (4.9%) are found.
- **Failure type is not informative.** Among missed repeats, the share classed as "merged"
  (previous note found, nothing at the repeat) is 62% (< 80 ms) and 81% (80-120 ms). It is
  84% even at 200-500 ms, because the previous note is almost always found. The measure does
  not separate merging from any other miss.

### Aria-AMT subset (8 recordings, one per pianist)

| IOI | Repeats | Aria-AMT recall | Drop [95% CI] | Transkun, same 8 recordings | Drop [95% CI] |
|---|---|---|---|---|---|
| < 80 ms | 86 | 0.453 | 50.2 [38.4, 64.4] yes | 0.349 | 61.9 [54.1, 77.3] yes |
| 80-120 ms | 493 | 0.905 | 5.0 [0.6, 16.7] yes | 0.909 | 5.9 [0.2, 17.9] yes |
| 120-200 ms | 3,678 | 0.959 | -0.4 [-2.4, 3.2] no | 0.964 | 0.3 [-1.1, 3.4] no |
| 200-500 ms | 10,587 | 0.965 | -1.0 [-2.1, 0.5] no | 0.971 | -0.4 [-0.8, 1.2] no |
| Reference | 27,989 | 0.955 | | 0.968 | |

The two transcribers behave alike. Aria-AMT recovers somewhat more of the very fastest repeats
(13 under 50 ms: 3 found, against 0 for Transkun). With 8 recordings the CIs are wide.

### Rendered path (3 MAESTRO pieces, clean and simulated phone)

These performances contain **no repeats under 80 ms and only 14 at 80-120 ms**, so both bins are
"too few". Recall at 120-200 ms is 0.986-0.995 (no drop) for both transcribers and both
conditions. Transkun `phone` shows a 4.1-point drop at 200-500 ms ([1.9, 5.0]; 27 of 502
missed). This bin was not expected to matter. Most of those misses are soft notes (velocity
11-48) whose previous note was found. The rendered path is too thin to say anything about fast
repeats.

### Post hoc: velocity confound (added after the first results; disclosed)

Fast repeats are much softer than other notes. On PianoVAM the median velocity is 25 at < 80 ms,
against 65 for reference notes; the 10th percentiles are 7 and 42. Soft notes are missed even
when they are not repeats: reference recall is 0.18 at velocity 1-10, 0.46 at 11-20 and 0.76 at
21-30. So part of the drop above is "soft note", not "repeat".

Indirect standardisation: each bin's expected recall is taken from reference notes at the same
velocity, in bands 0-20, 20-30, ..., 70-80, 80+. The recording-bootstrap CI is on the difference.

| IOI | Observed | Expected at same velocity | Velocity-adjusted drop, points [95% CI] |
|---|---|---|---|
| < 80 ms | 0.327 | 0.679 | 35.2 [30.2, 40.5] |
| 80-120 ms | 0.889 | 0.932 | 4.3 [2.7, 6.5] |
| 120-200 ms | 0.969 | 0.984 | 1.6 [0.9, 2.5] |
| 200-500 ms | 0.972 | 0.982 | 0.9 [0.6, 1.3] |

Aria-AMT subset: 23.3 [13.7, 29.4], 4.5 [1.1, 10.4], 1.2 [-0.3, 3.8], 0.6 [-0.4, 2.0].

- **After adjusting for velocity the repeat effect is still there, but it is roughly halved
  below 80 ms.** At 80-120 ms it is 4-5 points, above the 2-point bar.
- At 120-200 ms the adjusted drop is 1.6 points. This is below the bar but its CI excludes 0,
  so there is a small real cost there too.
- The pedal does not change the picture. At 80-120 ms and velocity below the recording median,
  recall is 0.73 with the pedal up and 0.66 with it down; above the median it is 1.00 and 0.99
  (`strata.csv`).

### Post hoc: how often this arises in the phone takes (aggregate only)

This is added context, not pre-registered. In the 5 takes, a score note's expected time is taken
from the Transkun alignment. Voice unisons under 30 ms are excluded. The counts were first
computed inline. At the audit's request they were moved into the recorded script
(`uv run python scripts/bl21_repeated_notes.py takes`), which reproduces them. The two slower bins
differ by one note from the inline run (234 and 8,172 against 233 and 8,173, a boundary case);
the script's numbers are given here.

- 57 of 8,926 score notes (0.6%) are same-pitch repeats at 30-120 ms. The report counts 19 of
  them as missed (33%). They make up 19 of the 575 missed notes (3.3%).
- 234 repeats sit at 120-200 ms, and 32 of them are missed (14%).
- 8,172 repeats sit at 200 ms or more, and 434 of them are missed (5.3%).
- The missed rate of fast repeats in the takes is in line with PianoVAM. Fast repeats are rare in
  this repertoire, so they explain only a small part of the takes' missed notes.

## Answer

- **Merged or lost repeats do show up as missed notes.** The transcriber outputs one note where
  two were played. The aligner matches that note to one score note, and the other becomes
  "missed" in the report. The report's correctness code does not know about repeats.
- **When it matters.** By the pre-registered rule, the bins under 120 ms matter, with both
  transcribers.
  - The audit's finer split shows the loss is below about 100 ms, that is, sixteenth-note
    repeats faster than about 150 bpm. It is a few points at 100-110 ms and not measurable from
    about 110 ms up.
  - The 120 ms edge (about 125 bpm) is the outer edge of the pre-registered bin, not where the
    loss starts.
  - Below 80 ms (sixteenths faster than about 188 bpm; same-key tremolo, fast repeated notes or
    chords) most repeats are lost: recall 0.33 (Transkun), against 0.68 expected at their
    velocity. Most of these are isolated soft echoes, though (see Limitations).
  - At 80-120 ms, about 1 in 10 is lost, about 4-5 points more than velocity alone explains.
    Nearly all of that loss is in the soft half and below 100 ms.
  - At 120 ms and slower the loss is under 2 points.
- **Consequence for the report.** Missed notes on fast repeated-note passages (repeated chords,
  tremolo, fast repeated melody notes) should be treated as low confidence on transcribed input,
  as extras already are. One way to do that is to exempt from the per-bar missed count any score
  note whose same-pitch predecessor is due less than 100 ms earlier (the audit's reading; 120 ms
  is the conservative choice). Key the rule on the score's same-pitch IOI. This is not implemented;
  it is a suggestion for the feature-engineer, who owns `report/` and `features/`.

## Verdict (Confirmed with caveats)

On real-room microphone audio of a Disklavier, same-pitch repeats under 120 ms lose recall
beyond the 2-point bar, with both Transkun and Aria-AMT. This is the pre-registered result. For
Transkun the drops are 64.9 points under 80 ms and 8.7 at 80-120 ms. The loss is concentrated
below about 100 ms (sixteenth-note repeats faster than about 150 bpm). About half of the < 80 ms loss and half of the 80-120 ms loss is explained by
velocity, because fast repeats are soft; the rest remains. Repeats at 120 ms and slower cost less
than 2 points.

## Limitations

- No phone audio with ground truth exists. PianoVAM is a dedicated microphone in a practice room.
  A phone's gain control and codec could make soft repeats harder still; this is not measured.
- The rendered path has almost no fast repeats. It cannot confirm or refute this on rendered
  audio.
- The Aria-AMT subset is 8 recordings chosen for having many repeats. Its CIs are wide.
- **Key bounces and echoes (audit check 3).** Most sub-80 ms "repeats" look like Disklavier
  re-triggers or key bounces, not intended repeated notes. 79% (341 of 434) start within 5 ms of
  the previous note's release. They are about half as loud as the previous note (median ratio
  0.45), and 88% are isolated pairs. Their recall is 0.22, against 0.73 for the other 93. Nobody
  has listened to them.
  - Drops without "bounce-like" pairs (isolated, velocity at most half the previous note's), next
    to the pre-registered ones: under 80 ms, 49.1 points [42.7, 56.3] (pre-registered 64.9);
    80-120 ms, 2.1 [0.5, 4.3] (8.7); 120-200 ms, 0.0 [-0.6, 1.0] (0.7). Velocity-adjusted, the
    first two are 39.8 and 2.3 [1.4, 3.6].
  - Excluding instead every pair that starts within 5 ms of the release: 24.5 [16.3, 33.7] under
    80 ms and 4.1 [1.9, 6.8] at 80-120 ms.
  - The < 80 ms verdict holds under every exclusion. The 80-120 ms verdict holds but sits at the
    2-point bar once bounce-like pairs are removed.
- The pre-registered failure-type measure ("merged") does not separate merging from other
  misses. The audit's nearest-note measure does: 88% of missed repeats under 80 ms have a
  same-pitch transcribed note within 100 ms, against 2% for missed reference notes.
- The velocity adjustment and the take-level counts are post hoc. The take-level counts are
  reproducible with the `takes` stage.
- A 50 ms onset tolerance merges nothing at IOIs of 100 ms or more. Below that, a matched note
  could in principle be matched to the wrong strike of a pair; the one-to-one greedy matching
  prevents double counting.

## Audit (2026-09-29)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** The pre-registered verdict (bins under
120 ms matter, 120 ms and slower do not) reproduces exactly and survives the confound checks. The
threshold wording and the "trills" example need fixing (below), and the < 80 ms bin is mostly
isolated soft echoes that may not be intended repeats.

**Pre-registration and order.** The section hash reproduces: `5b9508aa...d11f` (header to the next
`## `, lines joined with a trailing newline). The author transcript (subagent `a83a1e7c`) shows the
section appended at 20:41:10Z (15:41 CDT). The script was written at 20:41:52Z and the first recall
table printed at 20:42:53Z. Before 20:41:10Z the author only read code, file lists and note counts,
so no repeat-recall number existed. The velocity adjustment was added at 20:44:02Z, after the
first table, and it is disclosed as post hoc. The Aria-AMT subset follows the pre-registered rule
(most repeats < 200 ms per pianist from the truth MIDI, longest dropped until under 2 h). Script
sha256 matches the README (`53970391...1e75d090d`).

**Rerun.** `bl21_repeated_notes.py run` with the output directory redirected to scratch:
`summary.json` is byte-identical and the printed tables are identical (all 84 recordings, the
Aria-AMT subset, the rendered path, and the velocity-adjusted tables).

**Checks.**

1. **Alignment error at short gaps is not a confound.** The robust SD of matched onset errors is
   3.1 ms per recording (median; max 10.0). Local clock drift (median residual within ±10 s) is 1 ms
   (median; 99th percentile 36 ms). Re-matching after a local drift correction leaves every bin's
   recall unchanged (< 80 ms 0.325 vs 0.327; the others equal to 3 decimals). Matched repeats
   under 80 ms have a median absolute error of 2.6 ms.
2. **Velocity.** The post-hoc standardisation is sound, and finer bands barely move it. With 5-point
   velocity bands the adjusted drops are 33.3 [28.0, 38.3], 3.7 [2.1, 5.7], 1.6 [0.9, 2.5] and
   0.9 [0.6, 1.4] points (the README's 10-point bands give 35.2 / 4.3 / 1.6 / 0.9). Adding register
   (5 pitch bands) to the velocity cells gives 26.3 / 2.3 / 1.2 / 0.8. At 80-120 ms, repeats at or
   above the recording's median velocity are found 99-100% of the time (`strata.csv`). The whole
   80-120 ms drop is in the soft half.
3. **Key bounces and re-triggers (new, material).** In the < 80 ms bin, 79% of repeats (341 of 434)
   start within 5 ms of the previous note's release. The median gap is 1 ms, and the median
   velocity is 0.45 times the previous note's. 88% are isolated pairs, not part of a run of fast
   repeats. This pattern looks like Disklavier re-triggers or key bounces on release, not like
   intended repeated notes. Nobody has listened to them. Recall of these near-zero-gap pairs is
   0.22, against 0.73 for the other 93 repeats under 80 ms.
   - Excluding "bounce-like" pairs (isolated, with velocity at most half the previous note's;
     228 under 80 ms, 162 at 80-120 ms, 9% of that bin) changes the drops as follows. Under 80 ms
     it is 49.1 [42.7, 56.3] points (velocity-adjusted 39.8). At 80-120 ms it is **2.1 [0.5, 4.3]**
     (velocity-adjusted 2.3 [1.4, 3.6]). At 120-200 ms it is 0.0 [-0.6, 1.0].
   - Excluding every pair that starts within 5 ms of the release instead, the drops are
     24.5 [16.3, 33.7] under 80 ms and 4.1 [1.9, 6.8] at 80-120 ms.
   - So the < 80 ms verdict holds under every exclusion. The 80-120 ms verdict holds but sits at
     the 2-point bar once bounce-like pairs are removed.
4. **Where in 80-120 ms the loss is.** With bounce-like pairs excluded, recall and raw drop by
   finer IOI are:

   | IOI | Recall | Raw drop |
   |---|---|---|
   | 80-90 ms | 0.806 | 17.0 points |
   | 90-100 ms | 0.930 | 4.6 points |
   | 100-110 ms | 0.951 | 2.5 points |
   | 110-120 ms | 0.981 | -0.5 points |
   | 120-200 ms | | 0.4 points or less |

   Without the exclusion, 110-120 ms still shows only 2.5 points.
5. **Merging can be identified.** The README's "failure type is not informative" is true of its
   pre-registered measure only. Using the nearest same-pitch transcribed note instead: 88% of
   missed repeats under 80 ms have one within 100 ms (25% within 50 ms, already used by the
   previous strike; 62% at 50-100 ms). The same holds for 47% at 80-120 ms, against 2% for missed
   reference notes. The transcriber does output one note for the pair.
6. **Clustering** is adequate. There are 84 recordings in the primary bootstrap and 10 pianists in
   the second one. The < 80 ms bin spans 57 recordings and all 10 pianists, but 5 pianists hold
   96% of it. The verdicts agree under both units.
7. **Tempo arithmetic is correct.** For sixteenths, bpm = 60,000 / (4 x IOI) = 15,000 / IOI, so
   120 ms is 125 bpm and 80 ms is 187.5 bpm. For triplet eighths it is 20,000 / IOI, so 120 ms is
   about 167 bpm.

**Required text fixes (author).**

- In the Answer and the Verdict, keep the pre-registered result ("bins under 120 ms matter") and
  add that the loss is concentrated below about 100 ms (sixteenth-note repeats faster than about
  150 bpm). It is a few points at 100-110 ms and not measurable from about 110 ms up. "Faster than
  about 125 bpm" is the outer edge of the bin, not where the loss starts.
- Remove "trills" from the < 80 ms example. A trill alternates two keys, so each key's IOI is
  twice the note IOI. Same-key tremolo and repeated notes or chords are the right examples.
- Add the bounce finding (check 3) to Limitations. Most sub-80 ms "repeats" are isolated soft
  echoes that start at the previous note's release. Report the drops without them next to the
  pre-registered ones.
- The "how often this arises in the phone takes" counts (57 of 8,926; 19 of 575) were computed in
  an inline session command, not by the recorded script, so they cannot be rerun from the Command
  section. Mark them as such or add the code.

**For the lead.** BL-25 (the low-confidence missed flag) is supported. A 100 ms cut-off covers the
measurable loss once echoes are excluded. 120 ms is the conservative choice, and the lead decides
between them. Either way, the flag should key on the score's same-pitch IOI, as proposed.
