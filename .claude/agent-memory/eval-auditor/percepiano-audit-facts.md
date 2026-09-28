# PercePiano facts verified by eval-auditor (2026-09-27, R-01)

- Item order is authoritative from the authors' code, not only the README table:
  `virtuoso/virtuoso/train_m2pf.py` and `virtuoso/case_study_result_comparison.py` define
  `LABEL_LIST19`, and the README example segment (`Beethoven_WoO80_var27_8bars_3_15`) "Label"
  column equals that key's vector in both mean jsons element by element. CSV cols 4-22 ->
  json index -> LABEL_LIST19 is a closed chain.
- Pole direction trap: README says `Articulation_Short_Long`, code says `Articulation_Long_Short`.
  Direction of item 2 is undocumented; do not interpret its sign strongly.
- Filename = `<piece>_<N>bars_<player>_<segment>`; PercePiano README line 44 says segment then
  player, which is wrong. Authors' code uses `split("_")[-2]` as pianist. Check: second-to-last
  tokens are {0-14,18,19,22,24,26,Score,Score2}; each (piece, last token) has 8-14 distinct
  players. R-01 run.py parses it correctly (20 humans + Score = 21 performers).
- Independent csv-module parse (authors' code path verbatim) gives 1,189 segments, key set equal
  to `labels/label_2round_mean_*.json`, max diff 4e-16.
- The two pedal items correlate 0.89 on segment means; averaging them (or dropping
  Pedal_Clean_Blurred) drops PCA-PA from 4 to 3. Near-duplicate items prop up minor components.
- Timeline evidence for pre-registration: subagent transcripts live in
  `~/.claude/projects/-Users-vuducdung-personal/<session>/subagents/*.jsonl`; extract Write/Edit
  tool_use events with timestamps when git history is empty.
