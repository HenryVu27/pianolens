---
name: partial-scores-df14
description: DF-14 (2026-10-10) whole-work titles holding one part (Italian Concerto, Op. 22), raw vs refined PianoCoRe cropping, Op. 17 i engraving verdict, how to get a PD print past IMSLP's captcha
metadata:
  type: project
---

Facts measured 2026-10-10 (details and numbers in DATASETS.md, PianoCoRe and ASAP notes):

- `bach_bwv971` and `asap:Bach/Italian_concerto` are the SAME file: PianoCoRe's
  `score_dataset` is `ASAP_midi_score`. 2nd movement, 49 bars 3/4. metadata `score_note_count`
  1,084 vs partitura 1,085 (one-note gap between PianoCoRe metadata and partitura is normal).
- `chopin_op22` score = Polonaise only (no Andante spianato). Most raw performances include it.
- **Raw vs refined PianoCoRe:** raw performance MIDI can hold more than the score (whole
  concerto, Andante spianato); the refined files are cropped to the score's span (onsets start
  at 0). Cache/loader (refined) are fine; scripts reading `performance_midi_path` (BL-18/18b,
  DF-13, F-08c, D-10 scripts) are exposed. Detect with `performance_note_count /
  score_note_count > 1.5` and `raw_precision` ~0.16.
- Fix mechanism: `piece_ids.PARTIAL_SCORES` + `score_movement()`; ids never renamed.
  `pianovam.SCORE_CANDIDATES` kind `mismatch` for Italian mvt 1/3 (entries kept so BL-19b's
  recording list and null pairing reproduce; removing them would shift the null pairs).
- Not relabelled (outside catalogue, part unidentified): PianoCoRe whole-title Schwanengesang
  D.957 (one song) and Op. 78 (73 bars 2/4).
- Op. 17 (all 4 PianoCoRe ids) = one MuseScore score `MS_8284988`. mm. 41-48 LH figure on
  staff 1 matches the Peters print (IA `31761040729832`, printed pp. 4-5): engraving choice.

How-to:
- IMSLP file downloads are behind mtcaptcha (do not bypass). The wiki page/API work; for the
  scan itself use Internet Archive `advancedsearch.php` (University of Toronto / BYU Peters
  copies are there), download `https://archive.org/download/<id>/<id>.pdf`, render with
  `uv run --with pymupdf`.
- Scan method that worked: compare whole-title score notes to sibling movement scores in the
  same PianoCoRe composition; for the rest, list time sigs / key sigs / Words per score.
- Never name a scratch script `struct.py` (shadows stdlib, numpy import dies).

**Why:** DF-14 relabelled titles only; raw-MIDI exposure is a latent risk for future tickets.
**How to apply:** before using a PianoCoRe raw performance or a whole-work title as the unit,
check it against the score; add new partial scores to `PARTIAL_SCORES`. See [[pianocore]],
[[asap-quirks]], [[pianovam-hands]].
