# DF-02 LLM phrase cache in the report (2026-09-29)

Code: `src/pianolens/features/phrases_llm.py`, `score_basis` `phrase_source="llm"`,
`scripts/build_llm_phrases.py` (render -> blind annotators -> ingest), report
`_phrase_tempo_block` in `report/build.py`, `_phrase_tempo_text` in `report/text.py`,
`_phrase_method` in `report/render.py`. Build record in `data/interim/phrases_llm/_build/`
(key.json maps P# -> piece; agents.json; annotations/A|B verbatim; leakage_check.txt;
access_audit.txt; identity_removals.json).

## Design
- Cache key: file-safe piece id + sha1[:10]. Env `PIANOLENS_PHRASES_LLM_DIR` overrides the folder
  (tests use it). Provenance needs model/date/protocol/score_hash/edition_hash.
- score_hash = exact unfolded variant; edition_hash = set of (base id, pitch). Same edition, other
  repeat path -> boundaries moved by anchor base note ids to every repeat.
- Report uses raw starts per run and averages the summary over runs (F-05e convention), NOT the
  8-bar-split basis phrases (the cadence path still uses split starts, unchanged).
- Ratio reference is the cadence detector count on the same score (no DCML for arbitrary pieces).
- Caveats: `romantic` (style from composer in piece id), `style_unvalidated`, `compound_meter`
  (ts_beats 6/9/12).

## Protocol facts
- R-08d prompt template text is only in the transcripts (subagents/agent-af78638f3a2b4fa6f.jsonl
  first message); copied into `PROMPT` in the build script.
- Importing R-08d `build.py` gives identity_hits, TITLE_STOP, R-08a vocabulary; R-08a `score.py`
  gives `map_events` (needs mv {bars, d.onset_beats (non-grace unique onsets), pointers}).
- PianoCoRe score.mxl: title tempo words (lento, giusto, larghetto, sostenuto) hit the title-word
  rule and are removed everywhere (also mid-piece "lento"); "Tempo I" -> "Tempo primo" needed
  (roman check). Added `tempo`, `major` to the stop list.
- Henry's 5 scores have no repeats: ap.score == maximal unfolding (mapping "exact").

## Measured (O-01 takes, Transkun / Aria), concave_excess cadence -> LLM (phrase ratio)
- 01: -0.29/-0.25 -> +0.31 (1.39); 02: +0.36/+0.38 -> +0.37 (0.86); 03: +0.30/+0.33 ->
  +0.31/+0.32 (0.75); 04: +0.05 -> -0.05 (1.10); 05: +0.08/+0.16 -> +0.44/+0.38 (1.26).
- Run spread up to 0.26 (05: A +0.57 vs B +0.31). 9/10 annotators recognised the piece.
- Cadence-path values in henry_llm equal the original reports exactly (harness).

## Post-BL-17-audit disclosure (2026-09-29)
- `_phrase_tempo_block` adds `undetermined` (LLM and cadence concave_excess of opposite sign),
  `llm_provenance.recognised_runs` / `n_runs` (from cache provenance `recognised_piece`, a
  run -> string|None dict), caveat `genre_untested` + `untested_genre` (nocturne/waltz/valse in
  the piece id; `UNTESTED_GENRES`). `PHRASE_CAVEATS["genre_untested"]` is a `{genre}` template;
  the text formats every caveat with `genre=`, so no other caveat may contain braces.
- Text always shows per-reading values, the detector value, "No practice item depends on this
  measure." (`PHRASE_DESCRIPTIVE`, also on the cadence path). Methods footer cites BL-17 numbers.
- BL-17 numbers used (audited): 0.64 mean, 0.55-0.72, 0.14-0.92 per piece, detector 0.31;
  compound n 6 mean 0.65, 0.46-0.85 (6/8, 12/8 only). F-05e: Romantic below DCML level.
- henry_llm rerun: 01 (both transcribers) and 04 (both) undetermined; practise lists and
  stability.json identical to before. Rerun: `scripts/a01_henry_reports.py --out
  data/interim/reports/henry_llm` (about 100 s). Recognition: 2/2 runs on 01, 02, 04, 05; 1/2 on 03.
- Another agent was editing report/build.py concurrently (BL-18 tiering); touch only the DF-02
  block and re-grep after edits.
