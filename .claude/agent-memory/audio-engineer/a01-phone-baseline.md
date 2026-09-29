# A-01 phone-audio baseline (2026-09-28)

Spec: `docs/specs/phone-audio-baseline.md`. All outputs under `data/interim/henry_takes/`
(a01/, controlled/, transcribed/, scores/) and `data/interim/reports/henry/`. PERSONAL DATA:
never commit or upload Henry's audio, MIDI or reports.

## Envs and tools (all gitignored under data/interim/envs/)
- Transkun 2.0.1: `data/interim/envs/transkun/bin/transkun --device mps in.wav out.mid`,
  11-17 s per 3-6 min take on MPS. Outputs soft pedal (67); unverified.
- Aria-AMT: Python 3.11 venv `envs/aria-amt`, weights `envs/aria-weights/
  piano-medium-double-1.0.safetensors`, driver `scripts/transcribe_aria_amt_mac.py` (own CLI
  asserts CUDA). fp32 MPS, 80-160 s per take. No soft pedal output.
- Pipeline scripts: `a01_henry_baseline.py` (takes + 150-ref floor + agreement, ~2 min, 10
  workers), `a01_controlled_check.py [--skip-transcribe]`, `a01_henry_reports.py` (10 reports,
  ~2 min; adds a "Suspect extra notes" confidence note when extras >= G6 exceed 2% of score notes).
- Report notes: append to `rep["confidence"]["notes"]` (rendered) and `rep["input"]["notes"]`
  after build instead of rebuilding.
- correctness `notes.measure_index == -1` = notes before bar 1 (pre-roll).

## Findings
- Controlled (MAESTRO Disklavier -> S-02 render -> phone sim + AAC): transcription adds
  +1.7..+3.3 pts error rate; phone sim costs < 1 pt over clean; onset rsd 2.3 ms (Transkun),
  4.4 ms (Aria); Aria velocity slope 1.2-1.3 (expands); sustain under-read (Tk 0.57-0.65 vs 0.89).
- Floor (15 PianoCoRe refs/piece/transcriber): Transkun median error 6.7%, extras 1.3%.
- Henry's takes: wrong/missed near floor; EXTRAS 15-29% on Op9/3, Op.posth, Op9/1 (both models
  agree). Up to 19.5% of score notes at >= G6 on fixed pitches (C7/D7/E7/G6), key-independent,
  not overtones at onset (3-13% vs 39-75% controlled), not re-strikes. Cause unknown (room sound
  vs far-field grand overtones); nobody listened. The phone sim does NOT reproduce it.
- Tk vs Aria on takes: timing/tempo tiers agree (Jaccard up to 1.0), velocity tiers do not
  (0-0.67). Top-3 practise items: 15/15 also tiered by Aria.
- Op64/2 bars 78-79 practise item: experts also show errors there (median 6 vs 8) = score artefact
  likely; single-take reports have no per-bar expert filter.
- F-08c (feature-engineer, 2026-09-28): single-take reports now have the per-bar expert check
  (the A-01 floor transcriptions, cached in `data/interim/reports/calibration/f08c_floor_tables.pkl`)
  and extras never count on transcribed input. Op64/2 bar 78 now suppressed as an edition artefact.
