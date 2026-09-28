# Small labeled sets quirks (D-04 / D-05, 2026-09-27)

- Download script: `scripts/download_labeled_sets.sh <name ...>` (idempotent).
- Expert-Novice (zenodo 8392772): 83 WAV + 83 beat-alignment txt + 7 mxl. WAV "<Piece>-NN.wav",
  txt "<Piece>.NNN.txt", NN = Recording_number. zips contain __MACOSX junk. 803 ratings = paper.
  Novice rater ids 1-21 overlap Player_id range (unclear whether same people).
- NeuroPiano (HF): 2,265 rows (card says 2,255), 104 recordings, score scale 0-6, 13 questions.
  Audio is WAV bytes inside the parquet `audio_path` struct.
- Vienna 4x22: `midi/*-average.mid` are averages, skip. Use match files (88).
- Batik: annotations submodule = DCMLab/mozart_piano_sonatas; per-note annotation CSVs in
  score_parts_annotated use match score ids (n15-1).
- MazurkaBL: 46 mazurkas (not 44; xml_scores has 44), 2,098 recordings. Recording ids can have a
  letter suffix (pid9070b-01). License only in README.
- MAESTRO v3 MIDI zip 58 MB; no performer names.
- PianoJudges repo index.json/splits.json IS the CIPI label index (652 works, Henle 1-9). CIPI
  Zenodo 8037327 is restricted.
- PSyllabus (zenodo 14794592): record metadata CC BY 4.0 but description says "Research use
  only". Splits use "val". cqt5.zip (2 GB) skipped.
- MAJEPPA is released: HF kkwsts/MAJEPPA-Dataset (88 MB, license "other"). Some score MIDIs crash
  partitura load_score_midi (time-signature assert in add_measures) -> score None, counted.
- MAESTRO-E needs Globus login (gated). Generator code: github ben2002chou/CocoChorales-E_MAESTRO-E.
