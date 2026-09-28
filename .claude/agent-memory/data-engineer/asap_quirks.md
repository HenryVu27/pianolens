# (n)ASAP quirks (D-01, commit 4097b45)

- metadata.csv `note_alignments` mangled for all 28 Schubert D.899 rows; derive from MIDI path
  (`<stem>_note_alignments/note_alignment.tsv`). 3 perfs have no alignment at all.
- 1,066 rows (README says 1,067). 242 score folders, 222 (composer, title).
- Full pass (perf + score + alignment) takes ~5 min: `scripts/check_asap.py`.
- Performer ids are heuristic from file names; surnames merge (asap:huang = 17).
- La campanella filed as Paganini "2"; mapped to liszt_s141_no3.
- Haydn / Debussy / Ravel / Glinka / Mephisto / Italian Concerto keep `asap:` ids (no guessed
  catalogue numbers).
