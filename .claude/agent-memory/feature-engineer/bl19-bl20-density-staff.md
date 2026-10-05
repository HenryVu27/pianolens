# BL-20 density and BL-19 staff-vs-hand (2026-09-29)

## BL-20 (experiments/2026-09-29-BL-20-density/, scripts/eval_correctness_density.py)
- Per-item rerun of the F-02 eval reproduces counts.csv bar "any" exactly (1,600 rows): the
  `bar_sets` helper is a faithful copy of eval_correctness.score_one. Reuse it for any
  stratification.
- Local IOI: chords within 30 ms, median gap of chords k-2..k+2. In mistakes_v1, Liszt and Chopin
  hold most notes under 100 ms; the < 60 ms bin has only 93 bars.
- Findings: bar F1 is not worse in dense passages (it is better). Note-level: the aligner
  "absorbs" wrong keys equal to a nearby written pitch (dense-N 15.7%, 0 with the GT alignment).
  Window mispairing is at most 1.1% everywhere, and 100 ms beats 50 ms in dense cells. The
  ornament whitelist swallows 6-13% of dense wrong notes.
- Trap: the "silent" (bar count unchanged) metric is inflated by bars that already had errors
  (82% of silent cases). Use "bar has no error at all" too.
- Trap: pandas `df.gt` is a method, so use `df["gt"]` for a column named gt.
- Wall time: Part A 7 min, Part B 11 min on 12 workers.

## BL-19 (experiments/2026-09-29-BL-19-staff-hand/, scripts/staff_hand_proxies.py)
- partitura `Words` imports hand words ("m.g" with the trailing dot stripped) but `staff=None`.
  Parse the MusicXML `<direction><staff>` directly for the staff.
- MusicXML voice convention in ASAP and PianoCoRe: voices 1-4 on staff 1, 5-8 on staff 2. A
  voice-1 note with staff 2 is cross-staff (Chopin Op. 10/1 has 213).
- Some PianoCoRe `score.mxl` files are plain XML, not zips (4 Beethoven movements). Check with
  zipfile.is_zipfile before parsing.
- Staff numbering gap: 25 catalogue scores give hand_synchrony zero events. Causes: staves
  numbered 3/4 (e.g. ASAP liszt_s162_no1); one staff per part merging onto staff 1 (Bach
  inventions, the Minute Waltz); Mozart PianoCoRe scores numbered 1/3.
- PianoVAM v1.2 upstream has Fingering/ (per-note L/R hand + finger from video, 99.2% hand
  accuracy on labelled notes per the card) and Fingering_GT/. They are not in data/raw. About 20
  recordings match catalogue scores (list in the BL-19 README).
- Numbers: 5.2% of notes and 3.9% of events at risk; median piece 0.9% of events.
