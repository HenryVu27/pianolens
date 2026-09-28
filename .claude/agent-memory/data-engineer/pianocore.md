# PianoCoRe quirks (D-03, measured 2026-09-27)

- Distribution: Zenodo 19186016 v1.0 (directory layout, zips) or HF SyMuPe/PianoCoRe (parquet
  with MIDI bytes, 8.6 GB). We use Zenodo: metadata.csv 206 MB, refined.zip 3.58 GB (5.5 GB
  uncompressed, 186,298 MIDI + 184,230 npz), raw-midi.zip 2.87 GB (252,017 MIDI + 1,607
  MusicXML/MXL scores). raw-alignments.zip 5.22 GB NOT downloaded (refined alignments suffice).
- Tiers are boolean columns in metadata.csv, not separate files. A is a subset of is_refined
  (27,023 refined rows are not tier A).
- Refined npz: `perf_idx` (per score note) + `interpolated` mask. Index order = MIDI notes sorted
  by (tick, pitch), NOT partitura note ids (partitura's score MIDI ids group by voice). Loader
  reads keys with mido and maps to partitura ids by (tick, pitch). partitura also drops a few
  notes on import (~8 notes in 2 of 75 sampled files) -> loader turns those into
  deletion/insertion and counts them.
- ~9% of refined pairs are `interpolated` (synthetic notes) in a 75-file sample. Labelled
  "interpolated" in Alignment, not "match".
- Only 1,066 rows are non-transcribed (the ASAP Disklavier ones). No MAESTRO performance_dataset
  appears; MAESTRO content arrives via ASAP.
- "1,104 pieces with 50+ performances" is a tier C number. Tier A: 730 pieces >= 50.
- Piece ids: `\b` fails after "_" in titles (use `(?<![A-Za-z])`). "Nocturne_No.8" under
  "Nocturnes,_Op.27" is a global number, not in-opus; "Ballade_No.1,_Op.23" has no in-opus
  number. Only a bare leading "No.N" or "N." in the movement is trusted. Result: 1,167 of 1,591
  A pieces canonical (after tier-C collision demotion).
- Load speed: ~0.9 s/perf on a random sample (score MIDI re-parsed each time), but ~0.06-0.2 s/perf
  when rows are sorted by score so the score cache hits. The 0.44 s / 19 h estimate was pessimistic.
- D-07 cache: `scripts/build_pianocore_cache.py` -> `data/processed/pianocore_A/` (one parquet per
  piece, reader `pianolens.data.pianocore_cache`). Each spawn worker holds ~0.9 GB (zip central
  directory of 370k entries + index); 12 workers ~11 GB. Pass the index to workers as a parquet
  file and inject into `PianoCoRe.__dict__["index"]` (cached_property) instead of re-reading the
  206 MB metadata.csv per worker. Numbers: see DATASETS.md PianoCoRe cache section.
- Full A cache (2026-09-27): 157,207/157,207, 0 failures, 29 min / 12 workers (shared machine),
  4.1 GB. 8.9% interpolated pairs; 29,953 deletions all from partitura import drops (7,157
  perfs); 0 insertions; 9 perfs with pitch-disagreeing pairs. Tier A has 978 Disklavier rows,
  not 1,066.
