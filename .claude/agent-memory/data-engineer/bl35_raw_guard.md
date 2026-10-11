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
- New partial/version scores found by the tail (not relabelled, lead decides): Op. 70/2 score
  is Chopin's 55-bar autograph (Gavard copy); Anh. 5 sonatinas = 1st movement only; Mussorgsky
  "Cum mortuis" all 33 rows ~3.8x. Op. 78 whole-title score = Pathetique ii (credit words) and
  its 7 performances are in A flat (Pathetique ii mislabelled). D.957 whole-title = Standchen
  arr. Heumann (credit words; same 82 bars and opening as the `schubert_d957_no4` score).
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
