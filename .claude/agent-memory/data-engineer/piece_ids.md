# Cross-dataset piece ids (D-07, 2026-09-27)

- `make_piece_id` now ASCII-folds with NFKD (`piece_ids.fold_accents`). Before/after diff over
  ASAP, PianoCoRe (tier C, 5,625 keys), MazurkaBL, Batik, Vienna, PercePiano: 0 ids changed
  (pianocore already folded the surname; catalogue strings are ASCII).
- `data/processed/piece_ids.parquet` from `scripts/build_piece_ids.py` (needs
  `pianocore_piece_counts.csv` first). Reader: `piece_ids.load_piece_id_table`,
  `datasets_by_piece`.
- MAJEPPA titles ("Op 599 No 14", "Kreisleriana, Op. 16 - V. ...") are rewritten into PianoCoRe
  form and parsed by `pianocore_piece_id` (`majeppa.majeppa_piece_id`). Titles without " - "
  that name a sonata/suite/variations, or carry a bare roman numeral, stay prefixed: they are
  single movements without a number. 655 of 886 scores canonical.
- Not in PianoCoRe as canonical: Hungarian Rhapsodies (demoted, collision), several Chopin
  mazurkas (PianoCoRe has the whole opus as one piece), K.533, D.783.
- Expert-Novice "beat" alignments are score onset positions in whole-note fractions (547/768),
  not beats, so they are not a BeatCurve.
