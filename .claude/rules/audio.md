---
paths:
  - "src/pianolens/audio/**"
  - "tests/audio/**"
---

# Audio rules

- The Mac does not hold audio corpora. Audio training and bulk transcription run on the RTX 5080
  box, following the `gpu-job` skill.
- Transcription output becomes a `Performance` with `provenance: transcribed` and the model name
  and version.
- **Velocity from audio is relative only.** Calibrate per device and room, and report dynamics as
  contour shape unless calibrated (landscape doc, section 3.1).
- **Offsets and pedal from audio are unreliable under reverb.** Articulation features from audio
  input must be marked low-confidence.
- MuQ: use fp32 and 24 kHz input. Weights are CC-BY-NC.

## From A-01 (2026-09-28)

- **Extra-note flags from phone audio are low confidence.** On three of Henry's five phone
  recordings, extras were 15-29% of the score notes (3.0-29.3% across all five, Transkun), many
  of them high pitches (G6 and above) on fixed pitches with no plausible source note. The controlled phone simulation does not reproduce this. Wrong and missed
  notes are read against the per-piece transcription floor. Extras are not used for practise items
  until a phone-audio extra filter is validated (BL-13 / PianoVAM).
  - *Superseded as to cause (BL-22 audit, 2026-09-29):* the high fixed-pitch extras are a recurring
    melody, most likely a second sound source in the recording, not a phone problem. See the
    BL-21 / BL-22 section below. Extras stay low confidence on transcribed input.
- **Logs and outputs that name personal recordings never go in the repo root.** `*.log` is
  gitignored. Personal data lives only under `data/`.

## From A-01b (2026-09-28)

- **Real-room microphone audio does not reproduce the phone-take extras.** Transkun on PianoVAM
  has 0.26% false extras, and almost none at G6 or above. Do not tune a phone extra filter on
  clean real-room audio: extras there are too rare, and a classifier trained on them removed more
  true notes than false ones. Use such audio to check a filter's *safety* (true notes lost),
  counting the high register separately.
  - *Superseded in part (BL-22 audit):* the takes' extras are a second sound source, so no clean
    real-room or phone-chain audio would reproduce them. The safety-check advice stands.
- **The extra-note rule (`pianolens.audio.extra_filter.rule_scores`) is optional and off by
  default,** and is validated for Transkun only. Changing its defaults invalidates the A-01b
  numbers. Extras stay low confidence with or without it.

## From the BL-21 / BL-22 audits (2026-09-29)

- **Disklavier truth has soft echoes.** In PianoVAM, 79% of same-pitch "repeats" under 80 ms start
  within 5 ms of the previous note's release. Most are isolated pairs at about half the previous
  velocity, which looks like re-triggers or key bounces. Report repeat and missed-note results with
  and without them (isolated, at most half the previous velocity).
- **The owner's high phone-take extras are a melody, not noise.** They are 97% white keys G6-G7,
  stepwise at about 3 notes per second, with the same phrases in every affected take, and not tied
  to the played onsets (BL-22 audit). Treat them as a second sound source in the recording until
  the OWNER listening check says otherwise. Do not design a phone-chain filter around them. A
  filter that detects a coherent off-score stream (stepwise, regular, independent of strikes) is
  the matching tool.
- **"Missing 2nd partial" claims need a same-pitch, level-matched control inside the recorded
  band.** Only G6 (2f0 3.14 kHz) qualified on the takes, whose roll-off is near 3.3 kHz. A missing
  partial does not argue against a sympathetically driven string.
