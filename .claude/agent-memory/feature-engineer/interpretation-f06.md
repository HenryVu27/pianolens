# F-06 tier D interpretation (2026-09-27)

Code: `src/pianolens/features/interpretation.py`, tests `tests/features/test_interpretation.py`
(26 known-answer tests). Sanity scripts were in the session scratchpad (not in the repo):
`f06_sanity.py`, `pa_diag2.py`, `consist.py`.

## Design (why)
- Frame = the target's own integer beats (performed score path); references evaluated at the
  mapped beats (`map_score_beats`: offset candidates from same-pitch pairs, Viterbi over onset
  positions, reward = matched share - 0.5, switch penalty 3). A repeat played twice is compared
  twice with the same reference bars. Always map when both scores' notes are known; equal
  integer grids do NOT imply equal content (Op.23 had equal grids but a 32-beat unmapped gap).
- Channels decomposed separately: tempo (F-03 smooth log ratio, no score markings = R-02
  cache convention) and smooth velocity (1.5-bar Whittaker). Residual timing only in ref features.
- Velocity refs: Disklavier/sensor only if >= 8, else all + `velocity_confidence="low"`.
- Typicality = likelihood of u = [shared coords z, log(SD of the row + eps)] under Ledoit-Wolf.
  The log-magnitude coordinate makes deadpan atypical (coordinator/R-06 requirement).
  Also `too_flat` / `too_extreme` (magnitude outside the 5-95% of refs).
- Target level alignment: shift so the median of (target - ref mean) is 0 (also for held-out
  refs inside `SharedCore.score`). Mean centering let one anomalous bar shift the whole window
  and create false flags elsewhere; median row-centering still leaked (~0.5).
- Per-bar flags: bar RMS of deviation vs the 95th pct of cross-fitted (10-fold) reference bar
  RMS. `shared_out_of_band` is informational: a global projection smears a local anomaly.

## Traps / measured
- **Ledoit-Wolf on mixed-scale coordinates** (MIDI-unit z vs log magnitude) shrinks toward a
  scaled identity and inflates the small-scale variance: velocity flattened to 25% scored
  typicality 0.72. Fix: shrink the correlation matrix (standardize, LW, rescale).
- **Parallel analysis:** Horn vs envelope null undercounts when strong components cover the
  window (synthetic: k = 4-5 -> 1-2). A "sequential" PA (test the residual, surrogates projected
  off removed directions, rescaled) recovers synthetic k on 95/96 runs but is unstable on real
  curves (k of one window varies by 6-7 across n=50 subsamples; hits the cap at n=500). Default
  Horn at fixed n = 50 (median of 5 draws). On 8 PianoCoRe pieces Horn@50 gives joint k median 2
  (whole piece; audit said 3), tempo ~1, velocity ~1. Per-channel k is mostly 0-2.
- Envelope null cannot detect fixed-position bumps of similar variance that tile the window
  (looks stationary): synthetic test needs graded SDs.
- Typicality floor = 1 / (n_refs + 1): with ~20 sensor velocity refs the minimum is ~0.05, so
  a deadpan's velocity typicality cannot go below ~0.045; `too_flat` catches it.
- Op.10/3 PianoCoRe LOO (40 targets x 5 windows): typicality < 0.05 in 6.0% (tempo) / 6.5%
  (velocity) of windows, bar flag rate 5.2% / 6.1%, too_flat 7% / 6%. Deadpan tempo typicality
  <= 0.004, deadpan + noise <= 0.036, too_flat 100%; flattened to 50% is NOT flagged (typ 0.23).
- ASAP Op.10/4 target via align_performance reproduces its PianoCoRe row exactly (curve corr
  1.000, same flags). Op.10/3 SunMeiting08: corr 0.981, 12 of 18 flags shared.
- Runtime: ~0.3 s per target on Op.10/3 (500 refs), ~13 s per Op.23 ASAP target incl. alignment.
