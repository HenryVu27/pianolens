# F-04 tier B control features (2026-09-27)

Code: `src/pianolens/features/control.py` (`control_features(ap, curve, references=...)`),
shared helper `src/pianolens/features/_score_utils.py` (score/matched note frames with staff,
voice, measure_idx), tests `tests/features/test_control.py`, sanity run
`scripts/check_control_f04.py` -> `data/interim/control_f04/{summary,bars}.csv` (~2 min).

## Design choices (why)
- Timing noise = dev_beats - mean of reference dev_beats at the same score beat (rounded 1e-6),
  leave-one-out by performance_id key, min 3 refs. References must share the performed
  (unfolded) score path; otherwise positions don't line up and it falls back to
  jitter_nometric (source switch at coverage 0.5).
- Evenness runs: (staff, voice) stream, >= 6 contiguous equal-duration onsets (shortest note
  at an onset). IOIs normalized by the F-03 smooth time map so ritardando != unevenness.
  Velocity detrended (deg 1, deg 2 for >= 12 notes).
- Hand sync: staff 1 minus staff 2 mean onset (positive = LH first), OLS on dv within 3 robust
  SD; robust (MAD) SDs. Real data: slope negative (RH louder -> RH earlier), as Goebl predicts.
- Tempo stability: second fit_time_map per F-03 segment at 4-bar cutoff; instability = RMS of
  l - l_phrase (1.5-4 bar band). Synthetic: 2-bar wobble keeps ~82% of its SD, 8-bar arc ~16%.
- Pedal blur (F-04 original; superseded window/templates in F-04b): harmony change = bass pc change AND union of the two 1-beat windows' pcs
  (weight >= 0.15) not inside one triad/7th chord template. Blurred = CC64 >= 64 with no lift in
  [t - 0.25 beat, t + 0.5 beat]. Vienna Chopin Op.10/3 p01: expert lifts ~0-0.1 s after every
  detected change (clean syncopated pedalling), blur 0.
- Harmony rule VALIDATED in F-04b (see f04b-validation.md): default now 1-quarter window +
  "functional" templates (no maj7/min7); F1 0.761 vs DCML root changes (was 0.726).

## Traps
- Aligned scores keep the partitura part -> AlignedPerformance does not pickle
  (RecursionError). Align sequentially or return only arrays from workers.
- Vienna 4x22 match scores have staff/voice but no `part` (no tempo/gradual markings).
- Batik pedal has CC64 and CC67. Vienna pedal values are continuous (1..127), threshold 64.

## Measured (sanity run: 6 ASAP perfs each of Chopin Op.10/12, Bach BWV 848 prelude, Schubert
D.899/3; Vienna 22 each of Chopin Op.10/3 and Mozart K.331; Batik kv279_1), group medians
- timing_noise_rms_ms (LOO consensus, 5 refs ASAP / 21 Vienna): Bach 8.9, Op.10/12 36.8,
  Schubert 54.0, Vienna Op.10/3 42.1, K.331 29.2. jitter_nometric: 8.1 / 43.7 / 65.9 / 73.2 /
  35.4; Batik 20.4 (no refs). Consensus R2 0.08 (Bach) to 0.70 (Vienna Op.10/3); min -0.64.
- even_ioi_cv 0.095-0.30 (Op.10/12 highest); even_vel_sd 5.3-9.3 MIDI.
  even_share_of_onsets 0.82-0.99 except K.331 0.24: the "even run" rule covers most of the
  onsets in figurative music, so it is broad (lead to decide whether to narrow).
- hand_async_resid_sd_ms 10-32 (max 91, Schubert); slope -0.14 to -1.08 ms / velocity unit.
- tempo_instability_log_sd 0.033-0.088; section_log_sd 0.05-0.14.
- pedal_blur_fraction: 0 (Bach, Batik, Vienna medians), Schubert 0.034, Op.10/12 0.22.
