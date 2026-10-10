# data-engineer memory

Index. One line per note; details in topic files beside this one. Settled facts belong in
`.claude/rules/` or `.claude/skills/`, not here.

- [partitura_traps.md](partitura_traps.md) — pedal-extended durations, row_stack crash, U256 ids, unfold ids, anacrusis quarter_map offset, hand-built Part
- [asap_quirks.md](asap_quirks.md) — (n)ASAP metadata bug, missing alignments, id heuristics (D-01)
- [percepiano_quirks.md](percepiano_quirks.md) — filename order, label cleaning, rater/performer counts, spans (D-02)
- [piece_ids.md](piece_ids.md) — accent folding, piece_ids.parquet, MAJEPPA title parsing (D-07)
- [pianocore.md](pianocore.md) — PianoCoRe layout, npz index order, piece-id parse, cache build (D-03, D-07)
- [small_sets.md](small_sets.md) — Expert-Novice, NeuroPiano, Vienna, Batik, MazurkaBL, MAJEPPA quirks (D-04, D-05)
- [d10_skill_check.md](d10_skill_check.md) — MAJEPPA score fixes, context confound, transcription pairs, PianoVAM/Rach3 (D-10)
- [dcml_jc_bach.md](dcml_jc_bach.md) — DCML jc_bach: TSV-built label-free Part, unfold via `next`, ms3 traps, counts (D-12)
- [dcml_romantic.md](dcml_romantic.md) — shared `data/dcml.py`, 5 Romantic corpora: spanners, text markup, gap ties, ms3 unfold bugs (D-13)
- [rach3_takes_bl16.md](rach3_takes_bl16.md) — Hanon book structure, take-splitting DP, p3 asynchrony, no same-day beginner takes, BL-16 numbers
- [pianovam_hands.md](pianovam_hands.md) — BL-24 hand labels: chord row order != notes (match pitch+onset), counts, Noinfo, catalogue candidates
- [skypiano.md](skypiano.md) — SKY-Piano not released, license unclear; where to re-check (D-09, BL-11)
- types.py contract lives in `src/pianolens/data/types.py`; builders `performance_from_partitura`,
  `score_from_partitura` are the only sanctioned way to wrap partitura objects. D-07 added
  `BeatCurve`, `ALIGNMENT_LABELS`, `Alignment.interpolated` / `.paired`; BL-24 added `HAND_LABEL_DTYPE`.
