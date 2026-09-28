# F-03 tempo model: design choices, traps, measured numbers (2026-09-27)

Code: `src/pianolens/features/tempo.py`, tests `tests/features/test_tempo.py`, sanity run
`scripts/check_tempo_f03.py` (outputs `data/interim/tempo_f03/`).

## Design (why)
- Fit the TIME MAP t(b) (P-spline, cubic B-splines, 1 knot/beat, order-3 difference penalty),
  not raw IOIs: residual = jitter directly, derivative = beat period. Order-3 penalty => constant
  tempo AND linear ritardando are in the null space (recovered exactly).
- Weights = beat spacing (trapezoid) so the cutoff is in beats regardless of note density.
  lam = (P/2pi)^6 / h^5 gives gain ~0.45 at period P, <0.01 at P/2, >0.98 at 2P (tested).
- Default cutoff 1.5 bars: bar-periodic metric pattern leaks ~8%; 1-bar cutoff leaks ~50%.
- Robust IRLS bisquare; scale = 1.4826*median(|r|) about ZERO (median-centered MAD collapsed
  all weights to 0 on a periodic pattern: bug fixed) times sqrt(n/(n-edf)).
- Theil-Sen step detector gives a plateau of equal stats; refine location with a hinge fit.
- Step splitting is opt-in: on Op.10/12 a 1-bar window flagged 13-22 steps/perf (rubato);
  2-bar window still 4-9. Score-marked tempo changes always split.
- Pauses (IOI >= 2.5x expected and >= 0.3 s) and fermatas are gaps; 6-11 per Op.10/12 perf,
  mostly at x.75 beats (breaths before a downbeat).

## partitura facts
- onset_beat counts time-signature denominator units (6/8 -> 6 beats/bar, eighths).
- ASAP MusicXML has many hidden metronome `Tempo` marks (Op.10/3: 20, ~10% apart): only a >=25%
  jump counts as a break. `tenuto` and `stretto` parse as ConstantTempoDirection: excluded.
- Constructors: ConstantTempoDirection(text, raw_text), Fermata(), both via part.add(obj, t).

## Measured (Chopin Op.10 No.12, first 6 ASAP perfs, default config)
- tempo_bpm_geomean 132.5-147.0 (quarter), log-tempo SD 0.139-0.167, jitter RMS 46-67 ms,
  MAD 32-46 ms, nometric RMS 37-51 ms; smooth-curve corr across perfs mean 0.638.
- Residual corr across performers (markings off run): 0.52 at 1-bar, 0.59 at 1.5, 0.58 at 2;
  after removing each perf's metric profile 0.31 / 0.42 / 0.48. => residual is largely
  shared score-driven timing; raw "jitter" is NOT pure motor noise.
- GCV picks cutoffs of 1.3-2.0 beats (undersmooths), jitter 26-39 ms.
- Runtime ~0.2-0.5 s per performance (1300 positions); alignment ~3 s.
