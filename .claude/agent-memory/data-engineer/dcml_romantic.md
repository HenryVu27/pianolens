# DCML Romantic corpora + shared loader (D-13, 2026-09-28)

- Shared loader `src/pianolens/data/dcml.py` (`CORPORA`, `ROMANTIC`, corpus-first API:
  `load_score(corpus, stem)`, `phrase_annotations(score)` reads the corpus from `score_id`).
  `dcml_jc_bach.py` is a wrapper; its outputs were byte-identical before/after (116 variants:
  render text + notes + phrase tables + meta hashed; scratch script, easy to rewrite).
- Download: `git clone --depth 1 --branch <tag> --filter=blob:none --sparse` then
  `git sparse-checkout set notes measures chords harmonies` (no MS3/PDF). 1.4-12 MB each.
  Tags: chopin v3.2, others v2.3 (all 2025-04-27). LICENSE file present (CC BY-NC-SA 4.0).
  `git clone --branch <annotated tag>` warns "is not a commit!": harmless.
- Romantic TSV quirks vs jc_bach:
  - chords facet: spanner columns (`crescendo_hairpin`, `decrescendo_hairpin`,
    `crescendo_line`, `diminuendo_line`, `HairPin:2_<text>`, `TextLine_<text>`, `Ottava:8va`,
    `pedal`) hold spanner ids on chord rows; the `Spanner` event row is the start. Read for
    Romantic only (`Corpus.spanners`).
  - staff text has `<font .../>` markup and private-use glyphs; tempo marks are unicode
    note glyphs that NFC decomposes to notehead+stem (U+1D158 U+1D165) -> `clean_text`.
  - "Tempo I" trips R-08a's ROMAN regex -> spelled "Tempo primo".
  - movement titles name the piece (Traumerei, Gondoliera): never rendered for Romantic; tempo
    comes from `Tempo` events instead. Liszt stems contain titles too (blind ids needed).
  - `octave`/`midi` are sounding pitch (ottava applied); name+octave == midi everywhere.
  - Ties: ms3 exports some tie continuations starting after a gap or on another staff ->
    fallback merge within 4 quarters (`n_gap_ties`). Remaining orphan heads: grace notes marked
    as tie continuations (Kinderszenen 7: 3, Liszt 160.02: 1), 161.04: 1 (not inspected), and
    2 cross-voice ties in Dante.
  - Unfolding: ms3 metadata is WRONG for BI16-2 and BI73 (next = -1 at the Fine before the
    D.C.; ms3 truncates to 24 / 12 bars) and empty for BI61-5 (senza fine) and BI77-3 (D.S. al
    Fine, Fine in volta 1). Loader rules in `playthrough`; hand-checked lengths 64/62/36/174.
  - Chopin BI105-1op30-1 has no harmonies table (listed by `pieces`, not by
    `pieces(labelled=True)`).
- QA: `scripts/check_dcml_romantic.py` -> `data/interim/dcml_romantic/` (pieces.csv with
  eligibility, comparators.csv, cands.pkl keyed by score_id, summary.txt; ~2.5 min). Numbers:
  DATASETS.md D-13 notes. Eligible (>=5 folded ends) / simple meter: Chopin 52/52, Grieg 53/45,
  Tchaikovsky 12/9, Schumann 10/10, Liszt 19/8. Detector end F1 +-1 beat is lower than on
  J. C. Bach (0.18-0.42 vs 0.427).
- R-08a leakage vocabulary is conservative: legit score text tripped it twice ("Temp. I." as a
  Roman numeral, Liszt's "una chorda" as "chord"); fixed by normalising in `clean_text`. Any new
  corpus: run the check and look at hits before assuming a real leak.
