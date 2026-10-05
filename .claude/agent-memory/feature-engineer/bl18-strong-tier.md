# BL-18 strong tier on transcribed input (2026-09-29)

Spec: `docs/specs/report-validation.md` section 5 (prereg + amendment 1 + results 5.1).
Script `scripts/calibrate_strong_tier_bl18.py` (`--dev-only` seconds; `--from-cache` re-scores
from `bl18_tables.pkl`; full run 570 alignments ~55 min at load ~90). Summary `bl18_summary.json`.

- Cause is NOT mainly "q99 interpolates below a unique max": R1(0) (strictly > max) only moves dev
  Aria 2.25 -> 2.13%. Aria's excess is missed notes: Aria floor missed/note q99 0.771 vs key-sensor
  0.286 (Transkun 0.308); wrong-pitch limits equal key-sensor for both families. 55/195 dev Aria
  strong bars are runs of >=3 bars with >=80% missed (passage not played / not transcribed).
- Dev (floor LOO, n=14) overstates: held-out R0 is Transkun 0.90 / Aria 1.36% (T1 Henry pieces
  vs same floor experts 0.28 / 1.04).
- Chosen by prereg selection: R1(2)+R2s -> held-out 0.17/0.19% strong, strong detection
  4.13 -> 0.68%: overshoot. Prereg had only an upper tolerance (lesson: always set a lower bound
  or a detection floor for the tier being moved). R1(0) held-out 0.62/1.01%, det 3.45%.
- R2s = family limits for strong only -> notable+ and its detection identical to R0 by construction.
- 30 experts (R3) help: R0 1.33 -> 0.89% pooled on T2.
- Unknown family defaults to Aria limits: very conservative for Transkun (0.06%).
- `perturb(..., require_exact_timing=False)` works on transcribed perfs with predicted alignment;
  injected bars via labels' score_id -> clean cr.score_notes measure_index.
- Henry rerun: `a01_henry_reports.py --out`; strong corr bars 14 -> 3, same tiered bars.
