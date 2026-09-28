# DCML jc_bach_sonatas (D-12, 2026-09-28)

- Clone: `data/raw/dcml_jc_bach`, tag v2.4 commit ac9fd07 (38 MB). CC BY-NC-SA 4.0 (.zenodo.json;
  no LICENSE file). 29 movements, op. 5 + op. 17. Score only.
- Only `.mscx` (labels embedded) + ms3 TSVs; no MusicXML, no MuseScore binary on the Mac.
  Loader builds the partitura Part from notes/measures/chords TSVs (label-free by construction).
- ms3 TSV traps: `duration_qb` is a rounded float -> use `duration` (whole-note fraction) x 4.
  Column sets vary per file (chords has `dynamics`/`slur`/`staff_text` only where present): read
  with pandas `dtype=str, keep_default_na=False`, use `.get`.
- Unfold with `next` column: k-th visit of an mc takes the k-th target; matches metadata
  last_mc_unfolded / length_qb_unfolded in 29/29. Tie-merged + grace note count == metadata
  `n_onsets` 29/29 (strong check; reuse for other DCML corpora).
- Labels: 442 folded phrase ends, 406 cadences (= R-08b tally); 3 `\\` phraseend rows; PC
  cadences exist (9 unfolded). Missing vs engraved score: fermatas (15), hairpins, rests
  (derived), key mode.
- F-05c detector mean end F1 +-1 beat 0.427 over 29 (grid4 0.273). HC recall 55/235.
- Op. 5 nos. 2-4 (wa02-wa04) are the sources of Mozart's K.107 concertos (README): a
  familiarity route for R-08c.
- Since D-13 the module is a wrapper of `data/dcml.py` (outputs byte-identical; keep it so:
  R-08c's pre-registered renderings depend on it).
- QA script: `scripts/check_dcml_jc_bach.py` -> `data/interim/dcml_jc_bach/` (pieces.csv,
  comparators.csv, cands.pkl in F-05c layout, summary.txt). Same approach should work for
  wf_bach_sonatas / cpe_bach_keyboard / scarlatti_sonatas (same ms3 layout).
