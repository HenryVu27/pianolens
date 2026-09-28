# F-05c cadence-derived phrase ends + per-phrase tempo (2026-09-27)

Spec with all numbers: `docs/specs/phrase-coherence-validation.md` (F-05c section). Script
`scripts/check_phrase_f05c.py` (cands -> fit -> eval -> coherence -> vienna), outputs in
`data/interim/phrase_f05c/`. Code: `features/cadence.py`, `shaping.phrase_tempo_shaping`,
`BasisConfig.phrase_source` (opt-in "cadence").

## Headline numbers
- Detector (21 cues, logistic, fitted on K.279-283 = 15 mvts, thr 0.2, gap 1.5 bars, start =
  onset after longest silence/IOI within 2 bars). Held out 21 mvts, ±1 beat: end F1 0.46
  (proxy-derived ends 0.29, grid 0.18), start F1 0.44 (proxy 0.35). ±1 bar: ends 0.59 vs grid
  0.53. Recall by DCML type: PAC 65%, IAC 35%, HC 32%, EC 19%, DC 0%.
- Tempo coherence R² (no markings) held out: cad_detail 0.067 < proxy 0.097 < ann_detail 0.149;
  shifted-cad null 0.052. Vienna pooled: cad -0.40, proxy -0.27, ann 0.375. => boundary errors
  of a beat kill the phrase-end kernels; coherence needs annotated phrases.
- Per-phrase `concave_excess` (vs mean of ±2-bar shifts), held out: ann +0.42, cadence +0.21,
  proxy +0.24, grid -0.01 (only grid n.s.). Vienna: ann +0.73, cadence +0.51, proxy +0.11.
  This is the annotation-free tempo-shaping measure. Compare excesses, not raw shares (raw
  arc R² grows with the number of phrases).

## Traps / lessons
- Vienna K.331/1 is 6/8: detector ends are within a bar (F1 0.82) but not within an eighth
  (0.12); "±1 beat" is meter-dependent (partitura beat = denominator).
- `bass_fifth_down` is interval-class: I->IV (up a fourth) also fires. The logistic model
  relies on metrical strength (+3.2) and bass on dominant (+1.4) to disambiguate.
- Scratchpad is shared with other agents; use a subfolder (`scratchpad/f05c/`).
- The F-06 agent's tests can fail transiently while it edits; rerun before blaming your change.
