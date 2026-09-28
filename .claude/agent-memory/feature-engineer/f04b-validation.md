# F-04b validation facts (2026-09-27)

Spec with all numbers: `docs/specs/control-validation.md`. Script:
`scripts/validate_control_f04b.py` (~5.5 min harmony grid of 168 variants, ~2 min pedal).

## Batik DCML ground truth (how to get it)
- `score_parts_annotated/<stem>_spart_harmony.csv`: labels attached to score note ids, UNFOLDED
  like the match files (ids n15-1 / n15-2), so ids map straight onto `ap.score.notes`.
  Rows with `label` and `chord` non-null are chord labels. It lacks chord_tones / root.
- `annotations/harmonies/K279-1.tsv` (DCML, folded): `chord_tones`, `root`, `bass_note` as fifths
  above the LOCAL tonic. Join on (mn, label, globalkey, localkey): 14,796/14,796 joined.
- Local tonic: globalkey (lowercase = minor) + localkey numeral read in the global key's scale
  (natural minor for minor keys), '/' nesting resolved right to left. No ms3 installed; parsing is
  in the script (`key_pc`, `numeral_key`).
- DCML annotations license: CC BY-NC-SA 4.0 (annotations/LICENSE); DATASETS.md still says
  "not checked" (data-engineer path, reported to lead).
- Beat units: partitura beats are the denominator (6/8 -> eighth, 2/2 -> half, 3/8 -> eighth).
  Anything musical measured in beats is meter-dependent: use quarters.
- Vienna K.331 unfolded bars = theme bars 1-8,1-8,9-18,9-18 (36 rows).

## Findings
- F-04 rule by meter: 2/2 recall 0.56 (two chords per half-note window), 6/8 precision 0.60.
  Fix: 1-quarter windows. maj7/min7 templates swallow I+V / vi+I incomplete chords: drop them.
- Remaining errors: misses = common bass / pedal points (rule needs a bass change), fast
  harmonic rhythm; false alarms = mostly bass moves under one root (inversions), then NCTs.
  RH-only bars: precision 0.29 (melody acts as bass).
- Pedal: Vienna experts lift at the change (K.331 median -0.02 beat); Batik pedals rarely (22%
  of changes) and lifts BEFORE the change (median -0.21 beat). Blur flat for CC64 thr 32-112.
  Window 0.25/0.5 kept. `pedal_down_fraction` is threshold-sensitive on Vienna (partial pedal).
- Strict evenness share 0-46% of onsets vs broad 24-99% (sanity set).

## Traps
- DataFrame column named `gt` clashes with `DataFrame.gt` method in attribute access.
- `_per_bar(..., "count")` counts NaNs too; count finite values via a flag "sum".
