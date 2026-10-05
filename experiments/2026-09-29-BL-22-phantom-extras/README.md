# Where do the high fixed-pitch extras on the phone takes come from? (data analysis)
Ticket: BL-22    Owner: audio-engineer    Status: Confirmed with caveats (eval-auditor 2026-09-29; the audit returned the reading, not the numbers; verdict rewritten below)

Nobody has listened to the audio yet. This is a data analysis of the existing transcriptions and
audio. It can make one hypothesis more or less likely; only a listening check (OWNER) or a second
recording chain can settle the cause.

## Pre-registration

The question, measures, decision rules and the mapping from results to hypotheses were written
before any of the measures were computed on the takes. They are in
`docs/specs/phone-audio-baseline.md`, section "BL-22 pre-registration" (2026-09-29, 15:41 CDT).
sha256 of that section (from its `## ` header up to the next `## ` header, or the end of the file):
`9e2a41ec2d563f0ae12e89dea8a78045d31b46d90a5ee9726714f0686934bccd`.

Deviations and additions, all made after results were seen, are listed under "Post hoc".

## Data and method

- **Takes.** The 5 phone takes of A-01 (one amateur, a Kawai SK-7 grand, YouTube audio). Three are
  "affected" (Op. 9 No. 3, Op. posth. in C-sharp minor, Op. 9 No. 1) and two are not (Op. 27
  No. 2, Op. 64 No. 2). Personal data: audio, MIDI, labels and per-note outputs stay under
  `data/interim/henry_takes/bl22/` (gitignored). Only aggregate numbers are given here.
- **Transcriptions.** The A-01 outputs: Transkun 2.0.1 (primary) and Aria-AMT
  `piano-medium-double-1.0` (secondary).
- **Labels.** Each transcription is aligned to the PianoCoRe score with the A-01 code
  (`align_performance` + `correctness`). A *high extra* is a note labelled `extra` at G6 (MIDI 91)
  or above. Counts per affected take (Transkun): 144, 197, 68 (409 in all); unaffected: 13 and 0.
- **Pedal.** The transcriber's own sustain track (CC64 >= 64). Unvalidated, and under-read in the
  A-01 controlled check.
- **Positive controls (public data).** Transkun false extras on PianoVAM (84 recordings, labelled
  against the Disklavier MIDI, as in A-01b) and the Transkun / Aria-AMT extras of the A-01
  controlled check (rendered MAESTRO, clean and simulated phone), where overtone extras are known
  to occur.
- Code: `scripts/bl22_phantom_extras.py` (`labels`, `analyse`, `spectro`, `posthoc`). Seed 0,
  1,000 null draws per test.

## Command

```
uv run python scripts/bl22_phantom_extras.py labels
uv run python scripts/bl22_phantom_extras.py analyse
uv run python scripts/bl22_phantom_extras.py spectro
uv run python scripts/bl22_phantom_extras.py posthoc     # post hoc, see below
```

Run record: 2026-09-29, git `dd13ab2` plus uncommitted working-tree changes (the repo has many
uncommitted edits by other agents); script sha256 in "Run record" at the end. Data: PianoVAM v1.2
(HF commit 1f039ab9), A-01 transcriptions and controlled-check files as listed in DATASETS.md and
the A-01 spec.

## Results

### (a) Pedal down vs up: not testable on these takes

The transcriber reads the sustain pedal as down for almost the whole of every take:

| Take | Pedal down, share of span (Transkun) | (Aria-AMT) | High extras, pedal down / up (Transkun) |
|---|---|---|---|
| Op. 27 No. 2 | 0.97 | 0.96 | 13 / 0 |
| Op. 64 No. 2 | 0.89 | 0.87 | 0 / 0 |
| Op. 9 No. 3 | 0.94 | 0.93 | 140 / 4 |
| Op. posth. | 0.93 | 0.92 | 176 / 21 |
| Op. 9 No. 1 | 0.93 | 0.93 | 67 / 1 |

- **No affected take has the pedal up for 10% of its span**, so by the pre-registered rule none
  enters the verdict. Test (a) gives no answer.
- For the record, pooled over the three affected takes anyway (Transkun): RR_time 1.02,
  RR_density 0.57 (circular-shift null mean 1.10, p = 0.96). Aria-AMT: RR_time 1.42,
  RR_density 0.89 (p = 0.66). Middle-register extras behave the same way (Transkun RR_density
  0.52). With 6-7% of the time pedal-up, these ratios rest on 26 (Transkun) and 14 (Aria-AMT)
  pedal-up extras and are not evidence either way.
- What can be said: **high extras also occur while the transcriber reads the pedal as up**
  (26 of 409 with Transkun, at about the rate expected from the pedal-up time). This is weak,
  because the pedal reading is unvalidated.

### (b) Harmonic relation to sounding notes: not harmonic (primary window)

A hit: the extra's pitch is partial 2-6 of a source note (with an inharmonicity allowance of
B = 0.001 on the sharp side). Sources: other notes starting in the 2 s before the extra
(primary) or within 50 ms (concurrent, secondary).

| Set | Window | n | Hit rate | Pitch-permutation null (mean / 95th pct) | Uniform-pitch null | Rule |
|---|---|---|---|---|---|---|
| Affected takes, Transkun | 2 s | 409 | 0.628 | 0.609 / 0.638 | 0.593 / 0.628 | not harmonic |
| Affected takes, Aria-AMT | 2 s | 277 | 0.653 | 0.613 / 0.653 | 0.598 / 0.639 | not harmonic |
| Affected takes, Transkun | 50 ms | 409 | 0.059 | 0.046 / 0.061 | 0.048 / 0.064 | inconclusive |
| Affected takes, Aria-AMT | 50 ms | 277 | 0.116 | 0.043 / 0.061 | 0.049 / 0.069 | harmonic |
| Control: PianoVAM false extras, Transkun | 2 s | 905 | 0.560 | 0.425 / 0.443 | 0.374 / 0.399 | inconclusive (p < 0.001 on both) |
| Control: PianoVAM false extras, Transkun | 50 ms | 905 | 0.373 | 0.187 / 0.203 | 0.127 / 0.145 | harmonic |
| Control: rendered extras, Transkun | 2 s | 116 | 0.991 | 0.729 / 0.776 | 0.390 / 0.457 | inconclusive (p < 0.001 on both) |
| Control: rendered extras, Transkun | 50 ms | 116 | 0.957 | 0.384 / 0.448 | 0.098 / 0.147 | harmonic |
| Control: rendered extras, Aria-AMT | 50 ms | 288 | 0.823 | 0.320 / 0.351 | 0.096 / 0.125 | harmonic |

- **On the primary 2 s window the takes' high extras are no more often partials of recent notes
  than a random high pitch would be** (ratio to the null 1.03-1.09), with both transcribers.
- **Implied overtone share (from the audit).** With null hit rate q and observed rate h, the
  share of extras that are overtones is about f = (h - q) / (1 - q). Approximate binomial 95%
  intervals, ignoring the null's own uncertainty:
  - Transkun: 0.05 [-0.07, 0.17] (2 s window) and 0.01 [-0.01, 0.04] (50 ms window).
  - Aria-AMT: 0.10 [-0.04, 0.25] (2 s) and 0.08 [0.04, 0.12] (50 ms).
  - Positive controls: PianoVAM false extras 0.23; rendered extras 0.74-0.97.

  **Overtones of played notes are at most a small minority of the high extras.** The 50 ms window
  carries this conclusion, not the primary one.
- **The primary window turned out to be weak.** With 2 s of sources almost any high pitch is a
  partial of something, so the null hit rate is about 0.6. The positive controls pass the
  permutation test clearly (p < 0.001) but fall short of the pre-registered 1.5x ratio. The
  50 ms window detects the controls' overtone extras easily (ratios 2.0-9.8).
  - Reachability (audit): with q about 0.61 the largest ratio any set can reach is 1/q = 1.64. For
    the rendered controls the ceiling was 1.37-1.47, so "harmonic" (at least 1.5x) could not be
    reached by them at all (the R-09 reachability error).
  - On the takes, "not harmonic" (below 1.2x) holds whenever fewer than about 31% of the extras
    are overtones, so on its own it is weak. Use the overtone share above instead.
- **On the 50 ms window** Transkun's high extras are not significantly harmonic (0.059 vs 0.046,
  p = 0.09). Aria-AMT's are (0.116 vs 0.043, p < 0.001), but the excess is about 7 points, about
  20 of 277 notes. So at most a small minority of the high extras are overtones of a note struck
  at the same moment. Compare 37% of PianoVAM's false extras and 82-96% of the rendered ones.

### (c) Fixed pitches, and silence

| | Op. 9 No. 3 | Op. posth. | Op. 9 No. 1 |
|---|---|---|---|
| High extras (Transkun) | 144 | 197 | 68 |
| Top 4 pitches (count) | D7 31, C7 26, G6 22, E7 19 | D7 39, C7 37, E7 33, G6 30 | D7 15, G6 13, C7 12, E7 10 |
| Share on the top 4 | 0.68 | 0.71 | 0.74 |
| Share at pitches never played correctly in the take | 0.49 | 0.70 | 0.50 |
| Isolated (no other note in [-0.5 s, +0.1 s]) vs random times | 0.035 vs 0.017 | 0.122 vs 0.054 | 0.015 vs 0.031 |
| Audio level at extras vs random times, median dB re take median | -1.5 vs 0.0 | -1.1 vs 0.2 | -1.3 vs -0.1 |

- **(c) is not an independent test.** A-01 had already described "fixed pitches", and the A-01b
  features include a pitch-spike term, so (c) re-measured the pattern that motivated the study.
- **Fixed-pitch: yes, by the pre-registered rule.** The same four pitches, G6, C7, D7 and E7 (MIDI
  91, 96, 98, 100), are the top four in all three affected takes with Transkun. With Aria-AMT,
  G6, C7 and D7 are in the top four of all three (share 0.54-0.76). The pieces are in B major,
  C-sharp minor and B-flat minor, and half or more of the extras sit on pitches the take never
  plays correctly. So the pitches do not follow the music.
- The unaffected Op. 27 No. 2 take has 13 high extras (Transkun), on the same pitches (D7 4, G6 3,
  E7 3, F7 3).
- **"In silence": the rule is met, but weakly.** Pooled, 7.3% of high extras are isolated against
  3.4% of random times (Aria-AMT 8.3% vs 3.2%). The large majority (93%) occur while notes are
  being played. The audio at an extra is on median 1-1.5 dB quieter than at a random time. That
  fits a quiet source independent of the playing.
  Correct notes at G6 or above are louder than random times in two of the three takes
  (+2.7 and +4.1 dB).
- Before the first correctly played note there are 9 high extras (Op. posth. 6, Op. 9 No. 1 3).
  After the last there are 3 (Op. posth.). Other transcribed notes also sit in these stretches,
  and they may be real playing outside the score. They are not clean "extras before any string
  sounds".

### (d) Spectrogram, three extra-dense passages

The densest 10 s of high extras in each affected take (25, 37 and 26 extras), and the same
measures take-wide. STFT 4,096 points at 48 kHz (85 ms window), hop 5 ms. Reference: correct
notes at G6 or above in the same takes, and random times with a random high pitch.

| Median over notes | High extras, in the windows (n 88) | High extras, take-wide (n 321 more) | Correct notes >= G6 (n 60) | Random time and pitch (n 900) |
|---|---|---|---|---|
| (i) Prominence at the fundamental, dB | 9.7 | 10.5 | 13.1 | -0.1 |
| (ii) Onset rise in that band, dB | 11.0 | 15.5 | 22.1 | 0.0 |
| (iii) Band level 300-100 ms before, dB re band median | 1.1 | 1.7 | 15.7 | 0.0 |
| (iv) Prominence at the 2nd partial, dB (all pitches; see Post hoc 3) | 0.0 | 0.0 | 4.7 | 0.0 |
| (v) Broadband flux 4-10 kHz, dB | 0.0 | 0.0 | 0.3 | 0.0 |

- **There is real narrow-band energy at the reported pitch.** The extras are not transcriber
  hallucinations on an empty band: the fundamental stands 10 dB above its neighbours, against
  13 dB for real high notes and 0 dB for random points. It appears abruptly (+11 to +15 dB),
  and it was not there just before (+1 to +2 dB over the band's median). That fits a short
  tonal burst more than a slowly building resonance, but an 85 ms window cannot resolve rise
  times finer than that.
- Real high notes show a raised band level before their onset (+15.7 dB). This probably reflects
  melodic context (neighbouring notes sounding in that band) and was not examined further.
- **Measures (iv) and (v) turned out to be uninformative.** The takes carry almost no energy above
  about 3.3-4 kHz (see Post hoc). The 2nd partial of C7 and above lies above that, and the
  4-10 kHz band is nearly empty for every note. A restricted check at G6-A#6 is under Post hoc.
- Spectrogram images are in `data/interim/henry_takes/bl22/spectro_*.png` (not in the repo).

## Post hoc (added after (a)-(d) were seen)

1. **Octave or partial displacement.** Are the high extras transcriptions of *missed* score notes
   at the wrong octave? For each high extra, is there a missed score note (expected time from the
   alignment) within 150 ms that lies 12, 19, 24, 28 or 31 semitones below it?
   - Transkun: 0.5% of 409 high extras, against a permutation null of 0.8% (p = 0.89).
   - Aria-AMT: 0.7% of 277, against 0.7% (p = 0.64).
   - Only 8% of high extras have any missed note within 150 ms.
   - **The high extras are additions, not displaced notes.**
2. **Bandwidth.** Long-term average spectrum, level relative to the 1-2 kHz band:

   | Audio | 3-4 kHz | 4-6 kHz | 6-10 kHz |
   |---|---|---|---|
   | Takes, 5 (range) | -26.4 to -29.1 dB | -38.2 to -43.4 dB | -37.9 to -52.7 dB |
   | PianoVAM microphone, 10 files (median) | -19.9 dB | -30.1 dB | -44.1 dB |
   | Rendered MAESTRO, clean (median of 3) | -13.7 dB | -25.3 dB | -41.7 dB |
   | Rendered MAESTRO, simulated phone (median of 3) | -13.7 dB | -24.6 dB | -40.7 dB |

   - In the 3-6 kHz range all five takes are 6-13 dB below PianoVAM and 13-19 dB below the
     rendered audio. The one spectrogram image inspected (the Op. posth. passage) shows a steep
     roll-off near 3.3 kHz. Above 6 kHz the picture is mixed (one take is brighter than PianoVAM
     there).
   - **The unaffected takes are just as dark,** so bandwidth alone does not explain which takes
     have the extras.
   - It is a clear, measured way in which the A-01 phone simulation (12 kHz low-pass) differs
     from the real chain. The cause (phone processing, the YouTube encode, or the room and
     instrument) cannot be separated here.
3. **2nd partial at G6-A#6 only** (2f0 below 3.8 kHz, inside the recorded band). This was added
   because measure (iv) was defeated by the bandwidth.
   - Median prominence at the 2nd partial: high extras 0.4 dB (n 100), correct notes 5.6 dB
     (n 29).
   - Prominence at the fundamental: 9.2 dB and 12.2 dB.
   - **At G6 the extras are close to pure tones; above G6 the measure is weak.** The 2nd partial of
     G6 (3.14 kHz) lies below the roll-off. Correct G6 notes show 5.6 dB there (n 7) and G6
     extras 0.8 dB (n 65) (audit). This is not a level effect: correct notes whose fundamental is
     no more prominent than the extras' still show 4.6-5.6 dB. At A6-A#6 the 2nd partial lies
     above the roll-off, so those pitches add little, and the G6 control is thin (n 7).
   - This does **not** count against sympathetic resonance. A string driven by an outside tone
     rings mainly in the driven mode. (An earlier draft argued otherwise; the audit dropped
     that argument.)

## Verdict (Confirmed with caveats, after the audit)

**The pre-registered mapping, as written:**

- (a) **not evaluable**: the pedal reads as down 87-97% of every take.
- (b) **not harmonic**: the implied overtone share is at most a small minority (Transkun 0.01,
  Aria-AMT 0.08 on the 50 ms window).
- (c) **fixed-pitch**, and "in silence" by the rule, though weakly (93% occur during playing).

By the letter of the mapping this is the "room or phone artefact" pattern. **The audit replaced
that label with a narrower reading, adopted here.** The auditor's measurements are in the Audit
section below.

- **The high extras are mostly a second, independent musical sound in the recordings.**
  - They form a recurring melody. 97% of the 422 high extras (Transkun, 5 takes) are white keys
    of the C-major octave G6-G7. The pieces are in B major, C-sharp minor and B-flat minor.
  - The melody moves stepwise: 71-76% of close pairs, against 38-39% with pitches permuted. It
    runs at about 3 notes per second.
  - The same phrases recur in all three affected takes: 9 exact 4-note sequences shared by all
    three, against a null mean of 0.04.
  - They are not tied to the strikes being played, and sit 20-27 semitones above the highest
    note of the preceding second.
  - Their peak frequency follows this piano's stretched tuning (suggestive only).
- **They are not a phone-chain artefact or a room resonance.** Neither plays a recurring diatonic
  phrase.
- **They are not transcriber hallucinations.** Both transcribers find them, and there is real
  narrow-band energy at each reported pitch. Overtones of played notes explain at most a small
  minority, and they are not displaced missed notes.
- **The source is undetermined.** In particular, the data cannot tell whether the sound was in
  the room or added in the video edit.
- **Sympathetic resonance as the main mechanism is disfavoured.** The pitches ignore both the key
  and the strikes. It is not excluded that this piano's undamped strings ring along with an
  outside tone, which could explain the piano-like tuning.

**Caveat.** This is one player, one piano and one recording chain, with no ground truth. Only
the listening check below, the original phone files, or a second recording chain (O-01) can
settle the source.

**Practical consequence, if the melody is confirmed:** the takes are contaminated by a second
source; this is not a flaw of phone recording as such. An extras filter could detect a coherent
independent stream: stepwise, isochronous, off-score, and not tied to the played onsets.

### Listening check (OWNER), from the audit

Clusters with times, per take, are in
`data/interim/henry_takes/bl22/audit/listening_targets.txt` (personal; not in the repo).

1. Is there a quiet, separate high melody running independently of the Chopin? It would be about
   1.6-3.1 kHz, stepwise, about 3 notes per second, in C major. Is it the same tune in all three
   takes?
2. What does it sound like: a music box, a glockenspiel or toy, a chime, an electronic beep, or a
   second piano or piano-like sound?
3. Is it audible in the first seconds of two of the takes, where the extras start 0.6-2.5 s
   before the first played note?
4. If the original phone files from before the YouTube upload still exist, is the tune in them?
   That separates "in the room" from "added in the edit".
5. Was anything playing in the room or the house during those sessions?

## Limitations

- Labels come from score alignment, not ground truth. A "high extra" can be a real note the
  score does not contain (an ornament or edition variant). The fixed pitches and the
  never-played-correctly shares make this unlikely for most of them.
- The pedal track is the transcriber's inference and is known to under-read the pedal in the
  controlled check. Here it reads the pedal as down almost always.
- The primary harmonic window (2 s) had low power by design error. Its ceiling ratio 1/q is about
  1.64, and the rendered controls could not reach the pre-registered 1.5x. The concurrent
  window, and the implied overtone share, are the informative ones.
- (c) re-measured a pattern already known from A-01 and A-01b; it is not an independent test.
- The melody reading rests on the audit's post-hoc sequence analysis, not on a pre-registered test.
- The inharmonicity allowance B = 0.001 is an assumption, not a measurement of this piano.
- Spectral measures use an 85 ms window. Rise times below that are not resolved, and measures (iv)
  and (v) were defeated by the recording's bandwidth.
- Only three passages were examined in the spectrogram at the window level. Take-wide numbers agree.

## Run record

- 2026-09-29, Mac M4 Pro. Git `dd13ab2` plus uncommitted working-tree changes.
- `scripts/bl22_phantom_extras.py` sha256 `c240e713...f68d56e1d` (final). Lint-only edits were
  made after the run; `analyse` was re-run afterwards and its output was byte-identical.
- Seeds: 0 for every null and random draw. 1,000 draws each.
- Runtimes: `labels` about 1 min, `analyse` about 2.5 min, `spectro` about 10 min, `posthoc`
  about 3 min.
- Outputs, all personal and under `data/interim/henry_takes/bl22/`: `labels.parquet`,
  `analyse.json`, `spectro.json`, `spectro_notes.parquet`, `posthoc.json`,
  `spectro_{03,04,05}.png`.

## Audit (2026-09-29)

Auditor: eval-auditor. **Verdict: Returned.** Every measurement is confirmed, and the pre-registered
rules were applied as written. The reading "room or phone artefact" must be replaced by a narrower
and more specific one. The high extras form a **recurring melody**, which points to a second,
independent sound source in the recording. An artefact of the phone chain or a room resonance
cannot produce a tune.

**Pre-registration and order.** The section hash reproduces: `9e2a41ec...bccd` (header to the end of
the file, no trailing newline). The author transcript (subagent `a83a1e7c`) shows the section
appended at 20:41:10Z. The BL-22 script was written at 20:45:51Z and first run at 20:45:55Z. Before
the pre-registration the author only listed files and counted notes and pedal events in the
transcriptions.

- The pitch set was not new. A-01 had already described "fixed pitches", and the A-01b features
  include a pitch-spike term. So (c) re-measured the pattern that motivated the study and is not
  an independent test.
- The post-hoc items are disclosed: displacement, bandwidth, and the G6-A#6 2nd partial.
- Script sha256 matches the README (`c240e713...f68d56e1d`).

**Rerun.** `labels`, `analyse`, `spectro` and `posthoc` were rerun into
`data/interim/henry_takes/bl22/audit/`. `labels.parquet` is equal. `analyse.json`, `spectro.json`
and `posthoc.json` are byte-identical, and `spectro_notes.parquet` is equal.

**1. The harmonic test: a real negative, but not because of the rule.** With a 2 s window the
permutation null's hit rate q is about 0.61. The largest ratio any set of extras can reach is then
1/q = 1.64. For the rendered controls it is 1.37-1.47, so the pre-registered "harmonic" (at least
1.5x) **could not be reached by the rendered controls at all**. This is the R-09 reachability error.
On the takes, "not harmonic" (below 1.2x) holds whenever fewer than about 31% of the extras are
overtones, so on its own it is weak.

The informative number is the implied overtone share f = (h - q) / (1 - q). The intervals below
are approximate binomial 95% intervals and ignore the uncertainty in the null.

| Set | Window | f [approx. 95%] |
|---|---|---|
| Takes, Transkun | 2 s | 0.05 [-0.07, 0.17] |
| Takes, Transkun | 50 ms | 0.01 [-0.01, 0.04] |
| Takes, Aria-AMT | 2 s | 0.10 [-0.04, 0.25] |
| Takes, Aria-AMT | 50 ms | 0.08 [0.04, 0.12] |
| Control: PianoVAM false extras | 2 s and 50 ms | 0.23 |
| Control: rendered extras | 2 s and 50 ms | 0.74-0.97 |

So overtones of played notes are at most a small minority of the high extras. The concurrent
window carries that conclusion, not the primary one.

**2. The 2nd-partial measurement is sound at G6, weak above it, and does not argue against
sympathetic resonance.**

- At G6 the 2nd partial (3.14 kHz) lies below the takes' roll-off, which the README puts near
  3.3 kHz. Correct G6 notes show 5.6 dB there (n 7) and G6 extras 0.8 dB (n 65). So the chain does
  carry a real G6 note's 2nd partial.
- The difference is not a level effect. Correct G6-A#6 notes whose fundamental is no more
  prominent than the extras' 75th percentile still show a median of 5.6 dB (n 19). Even the least
  prominent third of them shows 4.6 dB.
- At A6-A#6 the 2nd partial (3.5-3.7 kHz) lies above the roll-off, so those pitches add little.
- The G6 control has n 7, so the claim is supported but thin.
- A near-pure tone does not count against sympathetic resonance. A string driven by an outside
  tone rings mainly in the mode that is driven. The README's argument on this point should be
  dropped.

**3. The extras are a melody (new, decisive for the reading).** Transkun, affected takes:

- **White keys.** 97% of the 422 high extras (all 5 takes) are white keys. They form a C-major
  octave G6-G7: G6, A6, B6, C7, D7, E7, F7, G7. The expected share is 7 of every 12 keys, and the
  correct notes at G6 and above are 45% white. With Aria-AMT the share is 88% of 280. The pieces
  are in B major, C-sharp minor and B-flat minor.
- **Stepwise and regular.** Consecutive extras less than 0.6 s apart move by at most 2 semitones
  in 71-76% of pairs, against 38-39% when pitches are permuted within the take (p < 0.001 in each
  take). 74-80% of those gaps fall between 0.2 and 0.4 s, about 3 notes per second.
- **The same phrases recur in every affected take.** Exact 4-note pitch sequences shared by all
  three takes: 9, against a pitch-permutation null mean of 0.04 (maximum 1 in 200 draws). For
  5-note sequences it is 5, against 0. Pairwise, the takes share 15, 9 and 10 four-note sequences,
  against null 95th percentiles of 4, 2 and 3. Aria-AMT, which finds fewer extras, is also
  stepwise (61-69% vs 39-48%), and 6 and 11 four-note sequences agree with Transkun within the
  same take.
- **Not tied to the playing.** An extra is no more likely than a random time to have another
  transcribed note starting within 30 ms: 0.35 / 0.19 / 0.21 against 0.34 / 0.25 / 0.29. So strikes
  do not trigger them. They sit a median 20-27 semitones above the highest note played in the
  preceding second, so they are not grazed neighbouring keys either.
- **Tuned like a piano.** The peak frequency 10-130 ms after onset tracks this piano's stretched
  tuning, not A440 equal temperament. Median offsets for extras against correct notes at the same
  pitch:

  | Pitch | Extras | Correct notes |
  |---|---|---|
  | G6 | +9.5 cents (n 68) | +8.6 (n 17) |
  | C7 | +12.4 (n 75) | +12.4 (n 4) |
  | D7 | +14.6 (n 89) | +14.4 (n 2) |
  | F7 | +18.5 (n 37) | +19.0 (n 3) |
  | G7 | +24.1 (n 28) | no correct notes |

  The spread is wider for the extras (IQR 3.5-9.4 cents, against 0.4-1.7 for correct notes at most
  pitches). This is a peak within ±60 cents, and other piano sound in the band could pull it, so
  treat it as suggestive.

**What this does to the verdict.**

- By the letter of the mapping, "(b) not harmonic and (c) fixed-pitch" still holds, so the
  pre-registered label is technically met.
- But "fixed pitch" is the scale of a tune. Neither a phone processing chain nor a room resonance
  plays a recurring diatonic phrase at about 3 notes per second.
- The narrower reading the data support: **the high extras are mostly a second, independent
  musical sound in the recordings.** It is quiet and high (G6-G7), in C major, recurs as the same
  phrases in all three affected takes, and is independent of the Chopin being played. It is
  near-pure at G6 and pitched like a stretch-tuned piano.
- Transcribers are not hallucinating these notes. Tested overtones explain at most a small
  minority, and the notes are not displaced missed notes.
- What the source is, and whether it was in the room or added to the audio later, cannot be told
  from the data.
- Sympathetic resonance as the main mechanism is disfavoured: the pitches ignore both the key and
  the strikes. It is not excluded that this piano's undamped strings ring along with an outside
  tone, which could explain the piano-like tuning.

**Required fixes (author).**

- Rewrite the Verdict and the BACKLOG line as above. Drop "tonal artefact of the recording or
  processing chain" and the 2nd-partial argument against sympathetic resonance.
- Add the reachability limit of the 2 s window (1/q) and the overtone-share estimates.
- Note that (c) re-measured a known pattern.
- Note that the extras' audio level being 1-1.5 dB below random times fits a quiet independent
  source.

**What the listening check should listen for** (OWNER). Clusters with times, per take, are in
`data/interim/henry_takes/bl22/audit/listening_targets.txt` (personal; not in the repo).

1. Is there a quiet, separate high melody (about 1.6-3.1 kHz, stepwise, about 3 notes per second,
   C major) running independently of the Chopin? Is it the same tune in all three takes?
2. What does it sound like: music box, glockenspiel or toy, chime, electronic beep, or a second
   piano or piano-like sound?
3. Is it audible in the first seconds of two of the takes, where the extras start 0.6-2.5 s
   before the first played note?
4. If the original phone files from before the YouTube upload still exist, is the tune in them?
   That separates "in the room" from "added in the edit".
5. Was anything playing in the room or the house during those sessions?

If the melody is confirmed, the practical consequence is contamination by a second source, not a
phone-chain flaw. An extras filter could detect a coherent independent stream: stepwise,
isochronous, off-score, not tied to the played onsets.
