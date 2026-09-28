# (n)ASAP ground truth and F-01 validation numbers (2026-09-27)

- Ground truth = `<perf>_note_alignments/note_alignment.tsv` (load with
  `pt.io.importparangonada.load_alignment_from_ASAP`); identical to the `.match` where both
  complete. `Debussy/Pour_le_Piano/1/MunA12M.match` is an empty stub. No TSV for Beethoven 17-2
  KaszoS10, 29-4 DANILO01, Schubert D.935/1 Lisiecki10M. metadata `note_alignments` column is
  mangled for Schubert D.899: derive the path from the MIDI name.
- GT score ids use partitura unfolding suffixes (`n12-1`). GT is semi-automatic; `robust` flag.
  Several non-robust GTs are badly wrong (Scriabin Son.5 Ko07M, Liszt Sonata Yeletskiy05M):
  checked against ASAP downbeat annotations via `validate.beat_consistency`.
- F-01 numbers: match F1 mean 0.964 / median 0.987 / robust 0.981 over 1063 perfs; per composer
  in `docs/specs/alignment-validation.md`; per-perf CSV `data/interim/alignment_validation/`.
  Worst: Scriabin 0.782 (outliers), Glinka 0.884, Ravel 0.886, Liszt 0.920.
- Repeat choice (count-rank + best match ratio over 6 candidates): 86/99 right. Misses concentrate
  in Schubert D.935/3 (2048 paths) and Schumann.
- Weakest metric: deletion F1 0.75 (which duplicate note was skipped is ambiguous).
