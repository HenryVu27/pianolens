# partitura 1.9.0 / numpy 2.5 traps (measured 2026-09-27)

- `PerformedPart.note_array()["duration_sec"]` is PEDAL-EXTENDED by default
  (`sustain_pedal_threshold=64` -> uses `sound_off`). Set `pp.sustain_pedal_threshold = 128` for
  key-down durations. `types.performance_from_partitura` does this. The docstring says 127
  disables pedal, but pedal CC value 127 is common; 128 is safe.
- `part.note_array(include_metrical_position=True)` crashes: `np.row_stack` removed in numpy 2.
  time_signature / staff / grace_notes / key_signature options work.
- Note-array `id` field is `U256` (1 KB per note). `types.compact_ids` narrows it.
- `unfold_part_maximal(part, update_ids=True)` gives ids `n22-1`, `n22-2`; measures keep their
  original `number` (duplicates after unfolding). Deep copy: raise recursion limit (10_000).
- Tied-continuation notes are folded into the first note in `note_array()`; (n)ASAP alignments
  still reference some of them (636 ids over the whole set).
- `quarter_map` of a score with a pickup starts negative (beat 0 = first downbeat).
- MusicXML loads print many "error parsing" / slur warnings: filter warnings in scripts.
- `pt.io.importparangonada.load_alignment_from_ASAP(tsv)` returns partitura list-of-dicts.
- **quarter_map / beat_map anacrusis offset** (D-12): partitura puts the first full bar at
  quarter 0, so a pickup has negative onset_quarter. Going from "my quarters from the first
  onset" through `inv_quarter_map` is off by the pickup length. Map external positions via divs
  (`t = q * divs`, then `beat_map(t)`), never via `inv_quarter_map`.
- Building a Part by hand works: `Part(id, name, quarter_duration=divs)`, `part.add(obj, t0, t1)`
  for Measure(number, name), TimeSignature, KeySignature(fifths, None), Note/GraceNote(step,
  octave, alter, id, voice, staff), Rest(staff), ConstantLoudnessDirection, Words,
  ConstantTempoDirection, Barline(style). divs = lcm of all fraction denominators.
