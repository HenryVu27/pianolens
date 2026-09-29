# F-05e phrase measures with LLM boundaries (2026-09-28)

Experiment `experiments/2026-09-28-F-05e-llm-phrase-measures/` (run.py compute|summary, ~8 min,
6 processes; rows cached in artifacts/rows, delete a unit's parquet to recompute it). Spec:
`docs/specs/phrase-coherence-validation.md`, F-05e section. Provisional (needs eval-auditor).

## Numbers (concave_excess, mean over units)
- 8 units (Batik M1-M5 + PianoCoRe R1-R3): LLM 0.418, DCML 0.473, detector 0.197; LLM - DCML
  -0.055 (t [-0.138, +0.027]), LLM - detector +0.221 (8/8). Batik -0.014; Romantic -0.124 (n=3).
- merge_short_phrases(4 bars) -0.090 vs DCML, 8 bars -0.265; oracle grouping -0.009.
  => losses come from LLM boundary placement (extras/misses), not from level. Use raw starts.
- Coherence tempo R2 on these units: DCML ~ proxy (+0.015), so it cannot validate anything.

## Facts / traps
- Half a parabola keeps its curvature sign: splitting a concave arc in two does NOT flip c2.
  concave_excess is intrinsically fairly robust to 2-way over-segmentation.
- Reuse the R-08 scorers: importlib-load R-08a/b/d score.py; `movement_inputs()` +
  `map_events()` give LLM events in performed-score beats; R-08b `inputs_A()` for disguised run
  (D id -> m_id via mv["param"]). R-08d `detector()` returns (ends, starts).
- PianoCoRe refined scores: Romantic full = score_MS_refined.mid, Mozart full =
  score_ATEPP_refined.mid; abridged = *_mini_refined.mid. Pickups: DCML starts at -0.5/-1 beat,
  PianoCoRe pads a full bar (offset +3 / +4 beats). Onset DTW with pitch-set Jaccard (librosa
  sequence.dtw) maps them; agreement 0.94-0.97 Romantic, but K.333/1 0.67, K.457/3 0.76.
- Tier A has no Grieg op.57/1 or Liszt S.160/2; MazurkaBL has no op.7/4; J.C. Bach has no perfs.
- Harness: Batik dcml/cadence/proxy/grid excess equal F-05c phrase_tempo.csv exactly.
