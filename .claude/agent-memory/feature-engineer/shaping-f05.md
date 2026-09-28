# F-05 tier C shaping: design, traps, measured numbers (2026-09-27)

Code: `features/score_basis.py`, `features/shaping.py`, tests `tests/features/test_shaping.py`,
sanity `scripts/check_shaping_f05.py` (outputs `data/interim/shaping_f05/`).

## Design (why)
- partitura `make_note_features` always calls note_array(include_metrical_position=True) ->
  numpy-2 crash. Call the individual feature functions (`articulation_feature`, `slur_feature`)
  with our own note array instead; metrical strength computed from measures + onset_beat.
  `duration_feature` reshapes the input field view in place: don't use it.
- `estimate_tonaltension(na, ws=1, ss="onset")` works on the unfolded part's note array with
  pitch spelling + key sig: ~0.6 s for 2,800 notes. Rows = unique onset_beat.
- Skyline melody must account for HELD notes: "highest note starting at the onset" picks
  accompaniment under a held melody note (D.899/3). is_top = top starting note >= held max.
- Coherence CV: folds = blocks of 4 WRITTEN measure numbers (repeat passes share a fold),
  round-robin, 1-bar buffer, nested alpha. piece_pos excluded. R² needs >= 12 distinct
  written bars and >= 3 blocks since F-05d. Random-walk (smooth, no
  structure) velocity gives R2 -0.07..-0.36 (conservative, not inflated); iid noise ~ -0.01.
- Alignment can match one score note twice (ornaments) -> dedupe by score_id (crashed repeats).
- Proxy phrases: long-melody-note cue fires ~every 2 bars in D.899/3; threshold 1.0 + min 2
  bars + max 8 bars. Not validated; external boundaries override.
- ASAP MusicXML: no slurs; cresc./dim. words often have no end (extent = until next level
  marking, cap 4 bars). Constant loudness directions do get end times.

## Measured (Schubert D.899/3, 6 ASAP perfs, default config)
- Coherence R2 per perf (mean, range): velocity 0.41 (0.35-0.48), no markings 0.33
  (0.23-0.44); timing 0.12 (0.04-0.22); smooth tempo 0.05 (-0.03-0.11); articulation 0.20
  (0.13-0.25). Pooled (6 perfs): velocity 0.41 / 0.33 no-markings, timing 0.11, tempo 0.05,
  articulation 0.18. Pitch + dynamics + harmony groups carry velocity; metrical carries timing.
- Repeats r_mean: velocity 0.77, timing 0.87, tempo 0.72, articulation 0.86 (14 runs).
- Voicing: melody +20 vel (18.8-22.3), louder at 98.7% of onsets; lead -12 ms mean (-39..24).
- Dynamics: hairpin agree 0.61, level agree 0.63, accents 0.76, level~vel spearman 0.23.
- MAJEPPA S_0077 (Chopin Op.9/2, transcribed, MIDI score = no markings): 7 of 17 clips cover
  <30% of the score (filter match_frac >= 0.85 -> 10). No monotone skill pattern in 10 clips
  (velocity R2 0.21-0.68); smooth-tempo R2 negative for all. Descriptive only.
