# Phone-audio transcription baseline (A-01)

How much error the audio front end adds when the input is a phone recording of an acoustic grand,
and which report findings survive it. All numbers were measured in this repo on 2026-09-28.
Henry's recordings are personal data (DECISIONS 2026-09-28, O-01). This page gives piece names,
methods and aggregate numbers only. Audio, derived MIDI and reports stay in `data/` (gitignored).

## Inputs

- **Takes:** 5 phone recordings of one amateur on a Kawai SK-7 grand, one take per piece, about
  3.4-6 minutes each. The audio came from YouTube, so it is lossy (48 kHz stereo WAV).
  Pieces: Chopin Nocturne Op. 27 No. 2, Waltz Op. 64 No. 2, Nocturne Op. 9 No. 3, Nocturne in
  C-sharp minor Op. posth. (No. 20), and Nocturne Op. 9 No. 1.
- **Scores:** the PianoCoRe MusicXML for each piece, loaded with `report.io.load_score`.
- **References:** PianoCoRe tier A for each piece, 221-1,631 performances. Almost all are
  transcriptions (Aria-AMT or Transkun V2) of professional audio.

## Transcribers

| Model | Build | Device | Runtime on the 5 takes |
|---|---|---|---|
| Transkun 2.0.1 (pretrained 2.0) | gitignored venv `data/interim/envs/transkun` | MPS | 11-17 s per take |
| Aria-AMT, `piano-medium-double-1.0` | venv `data/interim/envs/aria-amt` (Python 3.11), `scripts/transcribe_aria_amt_mac.py` | MPS, fp32 | 80-160 s per take |

Aria-AMT's own CLI needs CUDA. The Mac driver reuses its model, segment decoder and stitching and
replaces only the CUDA plumbing (see the script docstring). Aria-AMT outputs no soft pedal.

## Measures

Code: `pianolens.audio.transcription` (note F1, onset sanity, pedal summary, velocity fit) and
`pianolens.audio.phone` (simulation). Scripts write to `data/interim/henry_takes/`.

1. **Correctness through the pipeline** (`scripts/a01_henry_baseline.py`). Each MIDI is aligned to
   the score with `align_performance` and checked with F-02 `correctness`. The outputs are the
   error rate (errors per score note) and the wrong, missed and extra rates.
2. **Transcription floor.** The same measures on 15 PianoCoRe references per piece and transcriber
   family (Aria-AMT or Transkun V2), 150 in total. All have match ratio 0.8 or higher. This is what
   a professional performance looks like after transcription, piece by piece. D-10's pooled figure
   is 0.080.
3. **Transkun vs Aria-AMT agreement** on the same audio. Note F1 at 50 ms (after removing a
   constant offset), velocity fit, agreement of per-score-note error labels, and agreement of
   report tiers bar by bar.
4. **Controlled check** (`scripts/a01_controlled_check.py`). MAESTRO v3 has Disklavier
   performances of 3 of the pieces: Op. 27 No. 2, Op. 9 No. 3 and Op. posth. Each is rendered with
   the S-02 renderer (Salamander C5, FluidSynth, 44.1 kHz) in two conditions:
   - `clean`: the render as is;
   - `phone`: `simulate_phone` (synthetic room RT60 0.5 s, DRR 3 dB, 120 Hz high-pass, 12 kHz
     low-pass, pink noise at 35 dB SNR, -3 dBFS peak), then an AAC 128 kbit/s round trip.

   Both conditions are transcribed by both models and scored against the true MIDI.
   - Caveats: MAESTRO audio is both models' training domain, and the simulation is not
     calibrated to any phone or room.
   - Neither MAESTRO nor ASAP has Op. 64 No. 2 or Op. 9 No. 1.
5. **Reports** (`scripts/a01_henry_reports.py`). The F-08 generator, provenance `transcribed`, so
   velocity is low confidence and not practise-eligible. There is one report per take and
   transcriber, and each carries the per-piece floor as a header note.

## Results

### Controlled check: error the transcriber adds, true MIDI known

Means over the 3 pieces, with the range in brackets.

| Condition, model | Note F1 (50 ms) | Onset error robust SD | Velocity slope / residual SD | Error rate added (F-02) | Extra rate | Sustain down, est vs true |
|---|---|---|---|---|---|---|
| clean, Transkun | 0.989 | 2.3 ms | 0.96 / 6.4 MIDI | +1.7 pts [1.2, 2.0] | 2.3% | 0.57 vs 0.89 |
| phone, Transkun | 0.986 | 2.3 ms | 0.99 / 6.0 MIDI | +2.2 pts [1.8, 2.6] | 2.6% | 0.65 vs 0.89 |
| clean, Aria-AMT | 0.982 | 4.4 ms | 1.23 / 5.5 MIDI | +2.8 pts [2.1, 3.9] | 3.5% | 0.78 vs 0.89 |
| phone, Aria-AMT | 0.979 | 4.5 ms | 1.31 / 6.0 MIDI | +3.3 pts [2.0, 5.4] | 4.0% | 0.79 vs 0.89 |

- The true Disklavier MIDI itself scores a 7.4% error rate (6.4-9.0%) with this checker.
- The simulated phone costs little over clean audio: under 1 point of error rate and no change in
  onset precision.
- Most added extras are overtones of played notes: 39-75% sit a harmonic interval (+12 to +36
  semitones, mostly the octave) above a note played at the same onset.
- Sustain pedal is under-read by both models, most by Transkun.

### Floor vs takes: correctness through transcription

| | Error rate | Wrong | Missed | Extra | Match ratio |
|---|---|---|---|---|---|
| Floor, Transkun V2 (75 refs), median | 6.7% | 0.6% | 3.8% | 1.3% | 0.961 |
| Floor, Aria-AMT (75 refs), median | 8.2% | 0.8% | 4.5% | 2.0% | 0.953 |
| Floor per piece, Transkun medians | 4.3-9.8% | | | 1.1-2.0% | |
| Takes, Transkun, median [range] | 19.9% [10.7, 39.2] | 1.0% | 6.9% | 15.5% [3.0, 29.3] | 0.903 |
| Takes, Aria-AMT, median [range] | 23.7% [14.3, 37.1] | 1.3% | 6.4% | 18.6% [4.9, 26.2] | 0.885 |

- **Wrong and missed rates on the takes are near the floor.** The excess is almost all extra
  notes: 3 of the 5 takes have extra rates of 15-29%, against 1-2% for the floor.
- **The two transcribers agree on those extras,** so they are in the audio, not in one model.
- **Most extras in those takes are not overtones of played notes.** They sit a harmonic interval above a
  note played at the same onset in 3-13% of cases, against 39-75% in the controlled check.
- **Many sit high.** At G6 (MIDI 91) or above:
  - the takes have 0-19.5% of score notes (Transkun), with up to 6.7% above the highest note in the
    score;
  - the controlled check has at most 0.2%.
- **They cluster on a few fixed pitches regardless of the piece's key,** and do not re-strike a
  note just played. Possible causes are sound in the room, or overtones of an acoustic grand that
  a far-field phone picks up. Listening would tell them apart; the
  audio was not listened to.
  - *Superseded:* (BL-22 audit, 2026-09-29: the high extras are a recurring C-major melody at G6-G7, a second sound source in the recording, not a phone-chain or room artefact; source undetermined. See `experiments/2026-09-29-BL-22-phantom-extras/`.)
- **The remaining extras are in the middle register** and not explained. In one piece, one of 15
  expert transcriptions shows the same count in the same bars, which points to an edition or
  repeat variant rather than playing.

### Transkun vs Aria-AMT on the takes

| Measure | Range over 5 takes |
|---|---|
| Note F1 at 50 ms | 0.91-0.97 |
| Onset difference, robust SD | 4.6-6.0 ms (4.5-5.9 ms on score-aligned notes) |
| Velocity slope / Spearman / residual SD | 0.82-0.96 / 0.80-0.88 / 6.4-9.2 MIDI |
| Per-score-note error labels, Jaccard | 0.55-0.84 |
| Report tiers, timing (control) bars, Jaccard | 0.17-1.0 (1.0 on 2 takes; 0.17 on a take with 3-4 flagged bars) |
| Report tiers, tempo (interpretation) bars, Jaccard | 0.29-1.0 |
| Report tiers, correctness bars, Jaccard | 0.56-0.75 |
| Report tiers, velocity (interpretation) bars, Jaccard | 0.0-0.67 |
| Top-3 practise items of the Transkun report also tiered by Aria-AMT | 15 of 15 |

## What to trust on phone input

- **Timing and tempo: yes.**
  - Transcriber onset error is 2-5 ms, against 27-79 ms of timing noise measured on the takes.
  - Tempo and timing tiers mostly agree between the transcribers.
  - F-08b found no provenance bias for timing flags.
  - Skill validity is still unproven (D-10 / R-09).
- **Velocity and dynamics: no.**
  - The two models disagree by 6-9 MIDI units of residual, and their slopes differ (Aria-AMT
    expands velocity range: slope 1.2-1.3 against the truth).
  - Velocity tiers do not replicate across models.
  - Velocity stays low confidence and out of "What to practise" until A-03 calibrates it.
- **Pedal: no.**
  - Sustain is under-read in the controlled check.
  - Soft pedal comes from Transkun only, and has not been checked against ground truth.
- **Correctness: only relative to the per-piece floor, and only for wrong and missed notes.**
  - Extra-note flags on phone input are unreliable: they can be several times the floor for
    reasons the controlled check does not reproduce.
    - *Superseded as an explanation:* on these takes the reason is most likely a second sound
      source in the recording, not the phone itself (BL-22 audit, 2026-09-29).
      Extras stay low confidence on transcribed input.
  - The reports now carry a note when extras at G6 or above exceed 2% of score notes. It names the
    affected bars and practise items.
  - A single take cannot separate these artefacts from real errors. Repeated takes (F-07 /
    recurring errors, wrong pitch only) can.
- **Per-bar expert checks are implemented in F-08c (see report-validation.md section 4).** One practise item sits in bars where expert transcriptions
  also show errors (median 6 against the take's 8). The recurring-error expert filter would catch
  this with several takes; a single-take report does not.

## Open

- **Calibrate the phone simulation against a real phone and room**, for example a Disklavier or
  PianoVAM recording captured by a phone (BL-13). It currently reproduces neither the level nor
  the kind of the takes' extras.
  - *Superseded in part:* the takes' extras are most likely a second sound source (BL-22 audit),
    which no phone simulation should reproduce. The calibration is still useful for bandwidth:
    the takes are 6-13 dB darker at 3-6 kHz than PianoVAM (BL-22 post hoc).
- ~~Consider an extra-note filter for phone input~~: done as A-01b (below). It is safe but
  removes only part of the artefacts.
- **The A-02 fine-tune target** should include far-field grand audio, not only MAESTRO-like
  close-miked audio.

## A-01b: extra-note filter (2026-09-28)

Can the phone-take extras be removed before scoring without deleting real notes? Measured on
audio with ground truth first, then applied to the 5 takes.

### Ground truth: PianoVAM microphone audio

- **Data.** PianoVAM v1.2: a dedicated microphone on a Disklavier in a practice room, mono
  44.1 kHz WAV, Disklavier MIDI as truth, amateur players (DATASETS.md). Subset: 84 of 107
  recordings (4.4 GB), 10 pianists (Advanced 47 recordings, Intermediate 27, Beginner 10), 343,550
  true notes. The Beginner recordings are short (2,644 notes in all).
- **Transcription.** Transkun 2.0.1 on MPS (`scripts/a01b_transcribe_pianovam.py`; 92 min of summed run time, two workers).
- **Label.** A transcribed note with no true note of the same pitch within 50 ms, after removing
  the per-file constant offset (-18 to +7 ms), is a false extra.
- Code: `pianolens.audio.extra_filter`, `scripts/a01b_extra_filter.py` (`prep`, `cv`, `henry`).
  Outputs under `data/interim/pianovam_a01b/` and `data/interim/henry_takes/a01b/`.

### Real-room audio does not reproduce the takes' extras

| | PianoVAM, Transkun | Henry's takes, Transkun (A-01) |
|---|---|---|
| Note F1 at 50 ms, per file | median 0.989 [0.939, 1.000] | no ground truth |
| False extras per true note | 0.26% (per file 0-0.7%) | 3.0-29.3% extra rate against the score |
| Extras at G6 or above per true note | 0.007% | up to 19.5% of score notes |
| Share of extras at G6 or above | 2.8% (25 notes) | 35.5% (422 of 1,189) |
| Share of extras with a harmonic source | 43.5% (a played note a harmonic step below) | 17% of the high extras |

- **Extras on PianoVAM are ordinary transcriber errors.** They are spread over the middle
  register (octaves 3-4 hold half of them). They are quieter than their context (median 15
  velocity units below the local median, against 0 for true notes) and short (median 52 ms
  against 125 ms). About 44% sit a harmonic step above a sounding note.
- **Rates barely depend on skill:** 0.27% Advanced, 0.26% Intermediate, 0% Beginner (few notes).
- **Timing and velocity floor (BL-13, `a01b_extra_filter.py floor`), per recording:**
  - onset error robust SD median 3.1 ms [1.5, 10.0];
  - velocity slope 0.92 [0.80, 1.15], Spearman 0.92, residual robust SD 4.5 MIDI [3.2, 6.8];
  - no skill effect on these numbers.
- **Real-room microphone audio of a Disklavier does not reproduce the high fixed-pitch extras.**
  Neither did the simulated phone (A-01). What remains is the phone itself (far-field, automatic
  gain, codec), the YouTube re-encode, or something sounding in Henry's room. Nobody has listened
  to the audio yet.
  - *Superseded:* (BL-22 audit, 2026-09-29: the high extras are a recurring C-major melody at G6-G7, a second sound source in the recording, not a phone-chain or room artefact; source undetermined. See `experiments/2026-09-29-BL-22-phantom-extras/`.)
- **The takes' high extras have a clear signature.** They sit on G6, C7, D7 and E7 (MIDI 91, 96,
  98, 100) in all takes. They are short (median 67 ms), no quieter than their context, and 83% have
  no harmonic source.

### Two filters, held out by pianist

Leave-one-pianist-out over the 10 PianoVAM pianists. Everything is chosen on the training
pianists only.

1. **Classifier trained on PianoVAM** (gradient boosting on 13 features: register, velocity,
   relative velocity, duration, harmonic source at onset or still sounding, chord size, density,
   gap to neighbouring pitches, time since the same pitch, fixed-pitch spike). The threshold is
   the lowest one keeping true-note loss at or below 0.5% on out-of-fold training scores.
2. **Signature rule** for the A-01 artefact. A note is removed if it is at or above a pitch
   floor, has no harmonic source, is shorter than a duration cap, and sits on a pitch that recurs
   more than its neighbours. The grid covers pitch floor, duration cap, spike and relative
   velocity (240 points).
   - A safety budget was fixed first: at most 0.1% of true notes removed, and at most 5% of true
     notes at G6 or above. Removing a real note creates a false "missed note" flag.
   - Among the grid points within budget, the tie-break is the one that removes the most notes
     from Henry's Transkun takes. It is label-free, and the score labels are not used.

| Held-out (pooled over 10 folds) | Classifier | Signature rule |
|---|---|---|
| Notes removed | 1,742 | 338 |
| of which false extras (removal precision) | 194 (11%) | 0 (0%) |
| Share of false extras removed | 21% | 0% |
| True notes lost, all | 0.46% | 0.10% (budget 0.1%; one fold chose a looser rule) |
| True notes lost, at G6 or above (7,782) | 0.4% | 4.3% |
| Note F1, before -> after | 0.9853 -> 0.9833 | 0.9853 -> 0.9848 |

- **On clean real-room audio, any filter costs more than it gains.** Extras are too rare there
  (0.26%). The classifier learns PianoVAM's own extras (quiet, short, harmonic), which are not the
  phone-take kind.
- **The rule finds no PianoVAM extras,** because none have the phone-take signature. PianoVAM
  therefore validates only its safety, not its recall.
- **Chosen rule (all pianists):** pitch at or above C7 (96), no harmonic source, shorter than
  100 ms, fixed-pitch spike at least 0.5, any velocity. In-sample loss is 0.087% of all true notes
  and 3.7% of true notes at G6 or above. These are the defaults of `rule_scores`.

### Applied to the 5 takes and to the floor

Takes re-aligned to the score after filtering (same code as A-01). Transkun:

| Take | Extra rate before -> after | Missed rate before -> after | Removed notes | of which score extras / correct |
|---|---|---|---|---|
| Op. 27 No. 2 | 4.7% -> 4.7% | 4.9% -> 4.9% | 0 | - |
| Op. 64 No. 2 | 3.0% -> 3.0% | 6.9% -> 6.9% | 1 | 0 / 1 |
| Op. 9 No. 3 | 19.5% -> 17.6% | 8.2% -> 8.2% | 48 | 48 / 0 |
| Op. posth. | 29.3% -> 22.2% | 9.0% -> 8.8% | 69 | 69 / 0 |
| Op. 9 No. 1 | 15.5% -> 14.1% | 3.7% -> 3.7% | 24 | 24 / 0 |

- **The removals are almost all score extras:** 141 of 142 over the 5 takes. The rule removes
  33% of the extras at G6 or above (141 of 422) and 12% of all extras (141 of 1,189).
  - It does not reach G6 (91). It keeps longer artefacts, and the middle-register extras are a
    different problem.
- **Extra rates stay at 14-22% on the three affected takes,** against a floor of 1-2%.
- **Aria-AMT:** the rule removes 2 notes in all. The tie-break used Transkun output, and Aria-AMT's
  artefacts do not pass the 100 ms duration cap. The rule is validated for Transkun only.
- **Floor (150 PianoCoRe references, all with match ratio at least 0.8):**
  - Transkun: the rule removes 55 of 129,981 notes (0.04%, at most 5 per performance). All 55 were
    correct notes. It removes nothing from Aria-AMT references.
  - The PianoVAM classifier removes 449 Transkun notes (365 of them correct) and 811 Aria-AMT
    notes (580 of them correct). It raises the missed rate, so it is not used.
- **The classifier on the takes (Transkun)** removes 36 notes, of which 15 were extras, and
  raises the missed rate of Op. 64 No. 2 from 6.9% to 7.5%.

### Decision and integration

- **The rule is safe but does not solve the problem.** It is an optional step:
  - `scripts/pianolens_report.py --filter-extras rule`, for `--provenance transcribed` only;
  - `pianolens.audio.extra_filter.filter_midi` for scripts.
- **Off by default.** Validation numbers: held-out true-note loss 0.10% (4.3% at G6 or above),
  0.04% on professional references, 1 correct note removed on the takes; removes 33% of the takes'
  high extras.
- The report says how many notes the filter removed.
- **Extra-note flags on phone input stay low confidence and out of practise items.** Wrong and
  missed notes are unaffected by the filter (the missed rate changed by at most 0.2 points).
- **Next:**
  - Listen to the high extras in Op. posth. to tell a room sound from the phone chain.
    *Superseded:* the BL-22 audit gives a listening list (is there a separate high melody, what
    it sounds like, is it in the original phone files).
  - Record one phone take next to a MIDI capture (O-01) to get phone ground truth.
  - A phone-and-room augmentation for the A-02 fine-tune.

## BL-21 pre-registration: fast repeated notes (2026-09-29)

Written before any repeat-recall number was computed. Experiment folder:
`experiments/2026-09-29-BL-21-repeated-notes/`.

- **Question.** When a key is struck again while its string still sounds, does the transcriber
  merge the two strikes, and at what inter-onset interval (IOI) does that start to cost recall?
  A merged repeat leaves one score note unmatched, which the report would call a missed note.
- **Data.** (1) Primary: PianoVAM microphone audio, the 84 recordings Transkun already
  transcribed in A-01b (`data/interim/pianovam_a01b/transkun/`), Disklavier MIDI as truth.
  (2) Rendered path: the A-01 controlled check (3 MAESTRO Disklavier performances, S-02 render,
  `clean` and `phone`), Transkun and Aria-AMT outputs already on disk. (3) Aria-AMT on PianoVAM:
  no outputs exist; the model is installed, so it is run on a subset fixed here: per pianist, the
  one recording with the most true same-pitch repeats at IOI < 200 ms (chosen from the truth
  MIDI only), capped at about 2 h of audio in total (drop the longest if over).
- **Unit.** A *repeat* is a true note whose previous true note of the same pitch started less
  than 500 ms earlier; its IOI is the gap between the two onsets. *Reference notes* are true
  notes with no same-pitch onset in the previous 500 ms. Bins: < 80, 80-120, 120-200, 200-500 ms
  (the < 50 ms tail is also reported inside < 80).
- **Measure.** Recall = share of notes matched by a transcribed note of the same pitch within
  50 ms after removing the per-file clock offset (`pianolens.audio.transcription.note_f1` /
  `match_notes`, as A-01b). Per bin and for the reference. 95% CIs by bootstrap over recordings
  (2,000 resamples, seed 0). Failure type for a missed repeat: *merged* (the previous same-pitch
  note was matched and no transcribed note of that pitch starts within 50 ms of the repeat) vs
  other. Descriptive splits: true sustain pedal down or up at the repeat, and velocity below or
  above the recording's median.
- **Decision rule.** A bin *matters* if reference recall minus bin recall is at least 2.0
  percentage points (about half the professional floor's missed rate, 3.8%) and the
  recording-bootstrap CI of that difference excludes 0. "Too few" if a bin has fewer than 30
  repeats. The answer to "at what tempo" is the slowest bin that matters, converted to the
  tempo at which sixteenth-note repeats have that IOI (bpm = 15,000 / IOI in ms). If no bin
  matters, merged repeats are not a measurable source of missed notes on this audio.
- **Reachability.** With hundreds of thousands of notes, a 2-point drop is detectable in any bin
  holding a few hundred repeats; bins with only tens of repeats can only come out "too few" or
  with a wide CI, which is reported as such.
- **Not answered here.** Real phone audio of repeats (no phone ground truth exists).

## BL-22 pre-registration: source of the high fixed-pitch extras (2026-09-29)

Written before any of the measures below were computed on the takes. Nobody has listened to the
audio; this is a data analysis only and cannot settle the cause. Experiment folder:
`experiments/2026-09-29-BL-22-phantom-extras/`. Outputs that touch the takes stay under
`data/interim/henry_takes/bl22/`.

- **Data.** The A-01 Transkun (primary) and Aria-AMT (secondary) transcriptions of the 5 takes,
  labelled against the score with the A-01 code (`align_performance` + `correctness`). A *high
  extra* is a note labelled `extra` at G6 (MIDI 91) or above. The three affected takes (Op. 9
  No. 3, Op. posth., Op. 9 No. 1) are primary; all 5 are reported. Pedal = the transcriber's own
  sustain track (CC64, down at value >= 64), which is under-read and not validated.
- **(a) Pedal.** Per take: high extras per minute with pedal down vs up (rate ratio RR_time), and
  high extras per correctly played note with pedal down vs up (RR_density, normalises for how
  much is played). Null: circular shift of the pedal track against the notes by a random offset
  of at least 10 s, 1,000 shifts, seed 0; p = share of shifts with RR_density at least the
  observed. Pooled over the affected takes by summing counts. Controls: the same numbers for
  middle-register extras (below G6) and for correct notes at G6 or above. A take with pedal up
  under 10% of its span is reported but not used for the verdict.
  *Rule:* pedal-linked if pooled RR_density >= 1.5 and pooled circular-shift p < 0.05;
  not pedal-linked if RR_density < 1.2 or p >= 0.05; otherwise inconclusive.
  Caveat fixed in advance: if the transcriber infers pedal from the same resonance, (a) is
  partly circular.
- **(b) Harmonic relation.** For each high extra, sources are the other transcribed notes below
  G6 or labelled correct/wrong, with onset in [t - 2 s, t + 50 ms] ("recently sounded", primary)
  or within 50 ms ("concurrent", secondary). A hit: the extra's pitch lies in
  [p_s + 12 log2 k - 0.5, p_s + 12 log2 k + 0.5 + d_k] for some partial k in 2..6, where
  d_k = 6 log2((1 + B k^2) / (1 + B)) with B = 0.001, a generous inharmonicity allowance (an
  assumption, not a measured value for this piano). Nulls, 1,000 draws each, seed 0: (1) permute
  pitches among the take's high extras (keeps the pitch set, breaks the timing link); (2) uniform
  pitch in 91-108. *Rule:* harmonic if the pooled hit rate is >= 1.5 times the null mean and
  above the null's 95th percentile for both nulls; not harmonic if below 1.2 times either null
  mean; otherwise inconclusive. Positive control: the same test on PianoVAM false extras
  (Transkun) and on the controlled-check extras, where overtone extras are known to occur.
- **(c) Fixed pitch and silence.** Per take: share of high extras on the take's 4 most common
  extra pitches; how many affected takes share each of those pitches; share of high extras at
  pitches never played correctly in that take. *Rule:* fixed-pitch if in every affected take the
  top 4 pitches hold >= 50% of high extras and at least 3 pitches are in the top 4 of all three
  affected takes. Silence: share of high extras with no other note (excluding high extras) starting in
  [t - 0.5 s, t + 0.1 s], and audio level (RMS, dB relative to the take median) over 100 ms from
  onset, against 1,000 uniformly random times in the take span (seed 0); also counts before the
  first and after the last played note. *Rule:* "in silence" if the isolated share is >= 1.5
  times the random-time share.
- **(d) Spectrogram, numbers only.** The densest 10 s window of high extras in each affected
  take. For each high extra and, as reference, each correct note at G6 or above in the same
  take: (i) prominence at the fundamental (dB, +-50 cent band vs bands 1 and 2 semitones away,
  0-100 ms after onset); (ii) onset rise in that band (dB, 0-50 ms after vs 100-50 ms before);
  (iii) presence before onset (band level 300-100 ms before vs the take's band median);
  (iv) prominence at the 2nd partial; (v) broadband flux at onset (4-10 kHz). Descriptive only.
  Images, if any, go to `data/interim/henry_takes/bl22/`.
- **Mapping to hypotheses, fixed now.** Sympathetic resonance is favoured if (a) pedal-linked
  and (b) harmonic. A transcription artefact (a partial read as a note) is favoured if (b)
  harmonic, (a) not pedal-linked and (c) not fixed-pitch. A room or phone artefact is favoured if
  (b) not harmonic and (c) fixed-pitch; "in silence" strengthens it. Any other combination is
  inconclusive. Whatever the result, only a listening check or a second recording chain settles
  the cause.
