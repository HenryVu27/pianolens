# BL-16 Rach3 Hanon takes (2026-09-28)

Code: `src/pianolens/data/rach3_takes.py`, build `scripts/build_rach3_hanon_takes.py` (~20 min
under load; 3 chord thresholds x 20 exercises x 247 sessions), outputs `data/interim/rach3_hanon_takes/`.
Experiment `experiments/2026-09-28-BL-16-rach3-takes/` (run.py --window same_day|next_day, analyze.py).

## Score / data facts
- Book MusicXML = 1 part, 1,433 measures. Part I Nos. 1-20 = measures 0-582: measure number restarts
  at 1; each ends with a light-heavy backward repeat and a one-chord bar. Part II (583-1432) has no
  separators. Only the first measure has key/clefs: copy it into each cut-out exercise.
- partitura unfold appends `-1` to score ids (`n9-1`): strip it before comparing with DP ids.
- p3 hand asynchrony up to ~50 ms: a 40 ms chord threshold splits events (event match drops to
  ~0.85). Build picks 40/60/80 ms per session.
- p3: 1 session/day, each exercise ~once/day -> 0 same-day groups after QC (11 before). p1: files
  are usually single takes (several sessions/day). p2: repeats Nos. 1-2 many times per session.
- Pauses at the bar-14 turnaround are the main QC failure (max_gap_ratio > 8).
- Coverage of session notes by Part I takes: p1 0.44, p2 0.79, p3 0.80.

## Measured (timing)
- R²(diff) gap cross-same: advanced same-day 0.036 [0.013, 0.056] (t touches 0; p1 0.003, p2 0.057);
  p3 next-day 0.051 [0.039, 0.065]. Take SD 0.011 beats / 7.5 ms adv, 0.013 / 11.3 ms p3; ICC 0.31 / 0.18.
- Tempo channel R² strongly negative in every cell: uninformative on Hanon.
