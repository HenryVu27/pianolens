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

- **Extra-note flags from phone audio are low confidence.** On Henry's phone recordings, 15-29% of
  notes came out as extras, many of them high pitches (G6 and above) on fixed pitches with no
  plausible source note. The controlled phone simulation does not reproduce this. Wrong and missed
  notes are read against the per-piece transcription floor. Extras are not used for practise items
  until a phone-audio extra filter is validated (BL-13 / PianoVAM).
- **Logs and outputs that name personal recordings never go in the repo root.** `*.log` is
  gitignored. Personal data lives only under `data/`.
