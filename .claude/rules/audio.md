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
