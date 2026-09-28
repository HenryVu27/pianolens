# F-05b phrase boundaries and tempo coherence (2026-09-27)

Spec with all numbers: `docs/specs/phrase-coherence-validation.md`. Script
`scripts/check_phrase_f05b.py` (outputs `data/interim/phrase_f05b/`). Batik data facts:
`batik-annotations.md`.

## Headline numbers (Batik, 36 movements, R² no markings, mean)
- Proxy boundary F1 0.34 at +-1 beat, 0.51 at +-1 bar; a 4-bar grid gets 0.26 / 0.50.
- Tempo R²: proxy 0.070, annotated drop-in 0.090 (n.s.), annotated + phrase_detail 0.143,
  + cadence 0.141, shifted-2-bar null 0.074, proxy + phrase_detail 0.065. Other channels
  unchanged (+-0.01). GBM: 0.18 proxy, 0.24 annotated. Leave-movement-out ~0 for everything.
- 81% of annotated phrases have concave tempo arcs vs 44% shifted.
- Vienna K.331/1 pooled 22 pianists: tempo -0.27 proxy -> 0.42 annotated + detail.

## Traps
- `pianolens.features.shaping` as an attribute resolves to the FUNCTION `shaping` (the package
  re-exports it); monkeypatch via `sys.modules["pianolens.features.shaping"]`.
- Sparse features (a cadence type in one CV block) blow up ridge out of fold (R² -70):
  use `ShapingConfig(clip_to_train=True)` with `phrase_detail` / `cadence`.
- Vienna MusicXML numbers bars in performed order: renumber to written bars or repeats leak
  across CV folds (inflated R² by ~0.4 on tempo).
- sklearn HistGradientBoosting on a loaded machine: set OMP_NUM_THREADS=1 (else 100x slower).
- Coherence min-length rule superseded by F-05d (see coherence-f05d.md): enforced in code now.
