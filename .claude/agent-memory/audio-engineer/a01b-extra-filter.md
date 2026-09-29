# A-01b extra-note filter + BL-13 (2026-09-28)

Spec section: `docs/specs/phone-audio-baseline.md` A-01b. Scripts: `a01b_transcribe_pianovam.py`
(Transkun, skips done files, `--reverse` + .lock for a 2nd worker), `a01b_extra_filter.py
{prep,cv,henry,floor}`. Module `pianolens.audio.extra_filter`. Report flag
`pianolens_report.py --filter-extras rule` (transcribed only).

- PianoVAM audio subset: `data/raw/pianovam/Audio` (84 wav, 4.4 GB, list + sha256 beside it).
  HF resolve with short commit `1f039ab9` works. Transkun MPS: ~50-100 s per file, 2 MPS workers
  roughly doubled throughput; 92 min summed.
- PianoVAM = mic on Disklavier, offsets -18..+7 ms, F1 median 0.989. False extras 0.26%, ~0 >= G6.
  Does NOT reproduce Henry's G6/C7/D7/E7 extras. BL-13 floor: onset rsd 3.1 ms, vel resid 4.5.
  Onset rsd sits at 3.089 ms in many files (time quantisation), so do not over-read it.
- PianoVAM-trained HistGB classifier: net harmful (precision 11%, removes correct notes on floor).
- Chosen rule: pitch >= 96, dur < 0.1 s, no harmonic source, spike >= 0.5. Safety budget on
  PianoVAM (0.1% all / 5% >= G6), tie-break = most notes removed from Henry Transkun (label-free).
  Henry Transkun: 141/142 removed were score extras; extra rates 19.5/29.3/15.5 -> 17.6/22.2/14.1.
  Aria-AMT: removes 2 notes (its artefacts are longer than 0.1 s). Floor: 55/129,981 real notes.
- Henry score-labelled features cache: `data/interim/henry_takes/tmp/a01b_henry_feats.parquet`.
- Next ideas: listen to Op. posth. high extras; phone + MIDI capture (O-01) for real phone truth.
