# PercePiano quirks (D-02, commit e672299)

- Names `<work>_<N>bars_<player>_<segment>` (README wrong). One file has a leading space.
- CSV: 20 question cols, first 19 = dims (verified: reproduces authors' JSON exactly with no
  dedupe). Drop rows with any value > 7.1; 0/blank = don't know. Authors rename Score -> Score2
  for WoO80 segs 5-16 and D935 seg 1, and `_score` -> `_Score`.
- Verbatim duplicate rows exist; authors' means count them twice (diff up to 0.070 on /7 scale).
- 63 raters after cleaning vs paper's 53; 12,444 submissions vs paper's 12,652.
- 25 human pianists only if player numbers are per composer (Beethoven 12, Schubert 13).
- Segment XMLs are renumbered from 1. Bar ranges: `scripts/build_percepiano_spans.py`
  (WoO80 full score in repo; D935 via ASAP Impromptu_op142/3; D960 unknown).
- Provenance: Yamaha e-Competition / MAESTRO MIDI (paper) -> disklavier; Score* -> synthetic.
