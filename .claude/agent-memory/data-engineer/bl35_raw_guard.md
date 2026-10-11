---
name: bl35-raw-guard
description: BL-35 (2026-10-11) raw PianoCoRe MIDI guard - ratio distributions, why 1.65 and the partial-score span rule, which past samplers drew caught files, Op. 78 / D.957 score identities, compute traps
metadata:
  type: project
---

Measured 2026-10-11 on all 157,207 tier A raw files (details in DATASETS.md, PianoCoRe notes):

- Metadata `performance_note_count` = raw file note-on count in 98.9% of rows (max 13 apart);
  use metadata, do not re-read 157k files (took ~25 min with 8 workers, tracks not merged).
- Metadata `score_note_count` is PianoCoRe's own score-MIDI count: usually unfolded, but not
  for D.C. al Fine etc. Partitura folded agrees within 1% for 45% of rows, longest repeat
  reading for 52%. With folded counts the ratio tail is huge (95th pct 1.72): repeats.
- Ratio raw notes / longest-repeat score notes: median 0.979, 99th 1.341, density minimum in
  (1.65, 1.70] then a second mode 1.75-2.0 (raw_precision ~ 1/ratio). Cut 1.65 -> 404 rows.
  Metadata count instead of unfolded would add 44 false positives (repeat/D.C. pieces).
- Op. 22 + Andante is only ratio ~1.21: no note cut can catch it. Rule 2 for PARTIAL_SCORES
  pieces only: raw duration / refined duration > 1.3 (gaps: Op. 22 none in 1.262-1.326,
  BWV 971 none in 1.215-2.513). 334 rows (330 not already caught by rule 1). Total 734 rows, 71 pieces.
- BL-38 part 3 (2026-10-11) settled the tail's score defects: Anh. 5 Nos. 1-2 -> PARTIAL_SCORES
  (label now wins over the source movement); Op. 70/2 autograph -> piece_ids.SCORE_VERSION_MISMATCH
  (refined recall 0.827 / 17.3% interp vs 0.887-0.959 / 4-11% other waltzes); "Cum mortuis" was a
  false positive from 48 unexpanded 32nd tremolos -> RAW_NOTE_RULE_EXEMPT + span rule (9 of 33);
  Op. 78 whole-title rows (Pathetique ii) -> pianocore.MISLABELLED_ROWS, dropped from index and
  cache readers. Relabelling to op13_mv2 was rejected: a 2nd score per piece breaks the samplers'
  `len(sx) == 1` eligibility and shifts seeded draws. Guard total 747 rows. Leakage: only R-07
  split has beethoven_op78, same side (train) as Pathetique ii.
- R-02 (curves), R-07 (Anh. 5 in R10s test; Op. 70/2, Cum mortuis train) and R-10 (Anh. 5 dev)
  used refined data of these pieces; refined Anh. 5 is fine (recall 0.99), Op. 70/2 is not.
- Past samplers: 11 caught files drawn (BL-18 3, BL-18b/DF-13 dev/DF-15 dev/BL-27 dev/BL-36
  dev 1 shared, DF-13/DF-15 held-out 3, BL-27 held-out 3 = the DF-14 BWV 971 files, BL-36
  held-out 1). All 11 were `suspect` and excluded from every rate; only suspect counts move.
  Re-running each draw function reproduced the stored artifact id sets exactly.
- Several Transkun PERiScoPe files have ~2x the notes in the same duration (not duplicates,
  not repeated halves); unexplained, caught by the note rule.

Traps: partitura `get_paths` explodes / hangs on variation sets and one Ecossaise (D.781/11):
build script runs each score in a subprocess with a timeout and falls back to
`unfold_part_maximal` (agrees with the variant max within 0.4% in 149/150 sampled scores).

**Why:** raw-MIDI readers were exposed (DF-14); `report/io.pianocore_expert_midis` (app expert
check) still is - not wired (report/ off limits in BL-35).
**How to apply:** any new raw-MIDI sampler calls `pianocore.guard_jobs` after its seeded draw;
new partial scores go in `PARTIAL_SCORES` so the span rule covers them. See
[[partial-scores-df14]], [[pianocore]].
