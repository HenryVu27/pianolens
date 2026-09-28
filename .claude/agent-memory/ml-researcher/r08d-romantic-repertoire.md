# R-08d LLM phrase analysis on Romantic repertoire (preparation 2026-09-28)

Folder `experiments/2026-09-28-R-08d-llm-romantic-repertoire/`. Pre-registered, README hash
dbef84ae...7708. Ids (map only in `artifacts/selection.json`): R1 tchaikovsky op37a06 (June,
4/4+3/4), R2 chopin BI61-4op07-4, R3 schumann n07 (Traumerei, famous), R4 grieg op57n01, R5
liszt 160.02 (Wallenstadt, 3/8 mostly, only 5 DCML ends in 112 bars). Runs are A and B (R# are
movement ids now). Status: waiting for the lead's annotator run.

## Design choices (pre-registered)
- INSTRUCTIONS = R-08a's minus "from the Classical period" (no replacement period: false /
  style cue / raises recognition; conservative). Cadence set unchanged; PC reported only.
- Recognition does NOT gate (style test, not unfamiliarity); >= 3 recognised -> verdict
  worded "on largely recognised pieces"; sensitivity without recognised movements.
- Draw: within-corpus tertiles of rendered chars (tempo_word=False, id X); tertile per corpus =
  (1,2,3)+2 distinct extras, permuted; ids by rng.permutation. Seed 20261001.
- Identity rule: printed text items hitting the identity check would be removed before render
  (none were). Title words of all 5 corpora (193 after TITLE_STOP) are checked.

## Facts / traps
- tempo_word=False drops only `Tempo` events; Romantic scores also carry tempo words as
  staff/system text (Grieg op57n01, Liszt 160.02) which stay. Not identity cues.
- Title-word check false positives: "flat"/"sharp" (key-signature text), "may"/"event" in R-08a
  INSTRUCTIONS; use case-sensitive `May` and a stoplist.
- `(?-i:...)` inline flag works for a case-sensitive sub-pattern under re.I.
- Detector is pass-consistent on the 5 drawn pieces (propagated F1 = own F1); drawn mean 0.389
  (t [0.102, 0.676]); Liszt R5 0.000. D-13 cands.pkl is keyed by score_id, comparators.csv needs
  a corpus filter as well as movement.
- Mixed meters: ±1 quarter tolerance computed by converting beats to quarters bar by bar
  (`score.to_quarters`), since the beat unit changes with the denominator.
- Header hash: hash the prefix before `## Preparation record`, then edits below it keep it.
