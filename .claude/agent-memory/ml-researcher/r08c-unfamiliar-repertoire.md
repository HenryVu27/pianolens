# R-08c LLM phrase analysis on unfamiliar repertoire (preparation 2026-09-28)

Folder `experiments/2026-09-28-R-08c-llm-unfamiliar-repertoire/`. Pre-registered, README hash
ef243096...7796 (computed after appending the prep record; verified). Ids Q1-Q5 = wa06op05no6a
(Grave), wa06op05no6b (Allegro Moderato, fugal), wa07op17no1a (minuet + variations),
wa10op17no4a, wa12op17no6a; map only in `artifacts/selection.json`. 2 runs (R1, R2) x 5 = 10
annotators; primary = mean over movements of the per-movement mean of runs; t-interval decides
"beats detector". Status: waiting for the lead's annotator run.

## How it is built (reuse)
- `build.py` imports R-08a `common` (renderer) and loads R-08a `render.py` via importlib for
  BANNED_WORDS/ROMAN. Don't name an R-08c file `common.py` or `render.py` (would shadow R-08a's).
- `score.py` loads R-08a `score.py` via importlib as `S`, then sets `S.BLIND` (pointer_map reads
  it) and `S.TYPES = jc.CADENCE_TYPES` (adds PC). Movement inputs use D-12 `cands.pkl`.
- Detector = `cadence_phrase_ends(load_score(stem, tempo_word=False))`; identical with the tempo
  word (checked on all 21 eligible movements).
- `harness(scratch)` runs an end-to-end dry run (oracle / detector as annotation JSON, 2 runs,
  `compare(art=, ann_root=)`) in a scratch dir; only `artifacts/harness.txt` is written.

## Facts / traps
- **The F-05c detector is not pass-consistent on J. C. Bach** (unlike the Mozart pilot): Q4 0.541
  own vs 0.560 through the propagating annotation path, Q5 0.527 vs 0.522. Comparator stays its
  own score (mean 0.437, t [0.297, 0.577]).
- DCML J. C. Bach labels are dense: R-08a's worked example (bars 3/6) collided; every pair up to
  (24, 27) collided; moved to (25, 28) by the pre-registered rule.
- All J. C. Bach HCs sit on DCML phrase ends (oracle HC 31/31), unlike Mozart (38/62).
- Staff texts kept as printed: Q1 "Siegue subito", "[2. Allegro Moderato]" (next movement's
  heading); Q2 "Arpeggio"; Q3 "Var. 1..5", "Min. D.C.". "FERMATA" always appears in the legend,
  so grepping a rendering for it says nothing.
- Note names D1..D5 are valid pitches: an old-id check for `D#` must skip renderings.
- Planted-label pick: sort label strings by (len, str), not len only (set order varies).
