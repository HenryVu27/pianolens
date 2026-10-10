---
name: bl26-bl33-score-loading
description: BL-26 tremolo expansion and BL-33 wide-chord hand split in to_part (2026-10-10) - encodings found, conventions chosen, validation sources, measured effects and where the scratch scripts were
metadata:
  type: project
---

# BL-26 / BL-33 / DF-11 Op. 29 warning (wave 2a, 2026-10-10)

Related: [[bl23-df09-df10]], [[df11-four-hands]], [[bl19b-hand-labels]], [[partitura-parangonar-traps]].

## Tremolos (`align/tremolo.py`, used by `_adapters.to_part` for MusicXML paths only)
- partitura 1.9 keeps only the name "tremolo" in `Note.ornaments`; type/marks are lost, so read
  the XML. Map XML `<note>` to partitura notes by `Note.doc_order` (= index of `<note>` children
  across `part_el.xpath("measure")`, rests and grace included). Ids stay the same as
  `pt.load_score` when no rescale is needed.
- Catalogue (805): 38 scores, 1,062 groups; the mark is ALWAYS on the chord's first note only
  (0 of 1,064 chord mates marked) -> expand/mark the whole chord. No `unmeasured` type anywhere;
  "unmeasured" = level >= 3 by my convention (346 groups kept, mostly two-note 3-4 marks).
- Validation source: ASAP `midi_score.mid` has tremolos written out. D899/1 score-MIDI notes with
  no XML note 1,218 -> 27 after expansion; D760 480 -> 159. Liszt S.178 onsets do not line up
  with its score MIDI at all (use pitch multisets: 707 -> 165).
- (n)ASAP GT ids refer to written notes: `validate._load_part` parses first, so no expansion.
- D899/1 after expansion: bars 82-84 misalign (repeated identical chords; 39+38 missed / 75
  extra). Net errors still drop (856 -> 520, 782 -> 492).
- F-08 calibration rerun off/on (scratch `calib_effect.py`, ~2 min each, 12 workers): "old"
  reproduces every published constant exactly; only D899/1 changes; missed+extra/note q99
  0.634 -> 0.50, error-rate q99 0.207 -> 0.171. D899/1 BL-23 N3 re-flags 124 -> 1. BL-28 owns the
  constant update.

## Hand split (`_adapters.split_wide_upper_chords`)
- Op. 64/1 PianoCoRe XML: parts "rh"/"lh", no staff element, voice 1 for every note; LH chord
  notes are `<chord/>` members of the RH melody chord. Only pitch separates them.
- MuseScore exports put a cross-staff LH note on `<staff>1` but keep its LH voice number (5-8):
  most catalogue moves (Op. 25/12, K.331 i, Op. 106 iv) are these.
- Same-voice wide chords in multi-voice staves are mostly RH (5/20 LH on BL-19b labels); the
  voice condition fixed precision (343/344 LH). Gap guard 8 then barely matters there.
- BL-19b `run.py` uses `load_score_part`, so it now sees expanded tremolos and split chords.
- Staff is now a hand proxy, not the printed staff (data-engineer: Op. 17 i mm. 41-48 are an
  engraving choice in the Peters print).

## Op. 29
- Only catalogue score with an in-between staff margin < 1 semitone (0.11). Warning goes to
  `logging` (report.io silences `warnings`, not logging) and `meta["load_notes"]` via `align`.
