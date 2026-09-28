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
  - The reports now carry a note when extras at G6 or above exceed 2% of score notes. It names the
    affected bars and practise items.
  - A single take cannot separate these artefacts from real errors. Repeated takes (F-07 /
    recurring errors, wrong pitch only) can.
- **Per-bar expert checks are needed.** One practise item sits in bars where expert transcriptions
  also show errors (median 6 against the take's 8). The recurring-error expert filter would catch
  this with several takes; a single-take report does not.

## Open

- **Calibrate the phone simulation against a real phone and room**, for example a Disklavier or
  PianoVAM recording captured by a phone (BL-13). It currently reproduces neither the level nor
  the kind of the takes' extras.
- **Consider an extra-note filter for phone input** (register, fixed-pitch recurrence, no
  plausible source note), validated on audio with ground truth before use.
- **The A-02 fine-tune target** should include far-field grand audio, not only MAESTRO-like
  close-miked audio.
