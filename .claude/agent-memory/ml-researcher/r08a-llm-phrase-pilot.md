# R-08a LLM phrase-analysis pilot (preparation 2026-09-28)

Folder `experiments/2026-09-28-R-08a-llm-phrase-pilot/`. Pilot ids M1-M5 = kv330_2, kv333_1,
kv533_1, kv330_3, kv457_3 (map only in `artifacts/selection.json`). Blind input:
`blind_input/` (INSTRUCTIONS.md, SCHEMA.json, M*.txt). Status: Confirmed with caveats (audit 2026-09-28); post-audit corrections appended to the README
by R-08b prep. Annotations in `annotations/`. Memorisation control: see r08b-memorisation-control.md.

## Traps found
- **The Batik MusicXML embeds the DCML labels** in `<harmony>` (partitura `ChordSymbol`, kind
  text like `.F.V{`). Any blind task must never expose the MusicXML; the renderer reads only
  notes/rests/directions/fermatas/barlines.
- `Score.measures["number"]` of an unfolded score is NOT a running index (it repeats written
  numbers); use the row index. `name` is the written bar ("0" pickup, "X1" unnumbered/volta).
- Onset beats are float32: round trips through printed fractions differ by ~3e-6. Snap to onsets.
- DCML cadences often do not sit on phrase ends (train K.279-283: DC 0/23, EC 20/38, HC 71/139,
  PAC 168/198 exactly on an end). On the pilot 5, perfect phrase ends recover HC 38/62, DC 0/7:
  per-type recall via phrase ends has a ceiling (`oracle_dcml_ends` row).
- DCML labels are identical in both passes of every repeated bar in the pilot movements
  (oracle via printed bars + propagation = F1 1.0), so "same as bar k" pointers are lossless.
- Check worked examples in instructions against the ground truth: a made-up example (bar 5 b1
  HC) sat on a real M1 phrase end.
- Don't name a script `select.py` (shadows the stdlib module when run as a script).

## Comparator numbers (pilot 5, mean over movements)
Detector end F1 ±1 beat 0.565 [0.427, 0.754] (pooled 0.515); proxy 0.271; grid4 0.181.
Detector HC recall 18/62. Full table in the README "Preparation record".
