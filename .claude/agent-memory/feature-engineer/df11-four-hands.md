---
name: df11-four-hands
description: DF-11 four-hands detection (rule, catalogue facts, Op. 29 Flauta margin), DF-08 footer, and the old-vs-new report byte-identity recipe (repo-relative caches trap)
metadata:
  type: project
---

# DF-11 / DF-08 (2026-10-10)

## Four-hands detection (`report/four_hands.py`)
- Reads the MusicXML itself (merge_parts erases parts). Rule 1: >= 4 staves, each in a part with
  >= 2 staves, holding a pitched non-grace non-cue note in >= half the part's bars. Rule 2: two
  parts named primo/prima/secondo/seconda. Rule 3: `KNOWN_FOUR_HANDS` piece ids (fallback).
- Catalogue (805 scores): 778 one part, 24 two, 3 three. Rule 1 finds exactly Fauré Op. 56/1
  (Prima/Seconda), Dvořák Op. 72/2 (both "Piano", abbr I/II), Ravel Ma mère l'Oye 5 (Piano 1/2).
  All three are source "pianocore" in the catalogue, not ASAP.
- Look-alikes that must stay solo: Rachmaninoff Op. 3/2 (2nd 2-staff part in 17/62 bars),
  Gershwin Rhapsody (2-staff part in 4/452 bars), Chopin Op. 15/3 ("Piano"/"Piano 2", 1 staff
  each: why "Piano 2" alone is not evidence), Bach parts per voice, cue-note parts.
- Speed: full XML read of all 805 = 64-91 s; `quick=True` (byte regex on <staff>/<staves> per
  part, full read only if >= 2 multi-staff parts or a part with >= 4 staves) = 5.6 s. Catalogue
  and report both use quick. CATALOG_VERSION 2 (load_catalog rebuilds old json).
- Report gate: `ReportInputs.four_hands` None = detect from paths["score"] + piece_id; False =
  skip. Duet -> hand_async_* NaN, `piece.four_hands` record, confidence note, control-card line.
  Solo reports gain no keys. `features/extract.py` (experiment features) still emits hand_async
  for duets: not gated.

## Chopin Op. 29 "Flauta"
- Merged staves: 1 Flauta 944 notes mean 74.246; 2 piano upper 473, 64.351; 3 piano lower 1080,
  54.234. Main pair = staves 1 and 3; staff 2 goes up by 0.11 semitone above the midpoint
  (distance gap 0.22). DF-11 does not change it (not a duet; align/ untouched).

## Byte-identity recipe (old vs new report code)
- `git archive HEAD src | tar -x -C <scratch>/old`, run with PYTHONPATH=<scratch>/old/src.
- Trap: DEFAULT_ROOTs and the R-02 curve cache (`interpretation.R02_CURVES`) are
  `parents[3]`-relative. Symlink `data`, `experiments`, `docs` into <scratch>/old, or the old
  run rebuilds references from PianoCoRe and every interpretation float drifts ~1e-8.
- Same code twice is exactly deterministic (threaded vs 1 thread identical). Use the same
  scratch dir for scores/MIDI in both runs (paths are in the JSON).

## BL-23 README
- N3 "58 dissolved different-pitch matches" is a slip: summary.json match_kept mean 0.28358 x
  201 = 57. Correction section appended 2026-10-10.
