# F-08 practice report (2026-09-28)

Code: `src/pianolens/report/` (build = data dict, text = templates, render = HTML/SVG, io = files,
calibration = constants), CLI `scripts/pianolens_report.py`, samples + known-answer checks
`scripts/build_report_samples_f08.py` -> `data/interim/reports/{a,b,c,d}_*.{html,json}` and
`sample_checks.json`. Tests `tests/report/test_report.py` (15, ~14 s).

## Design (why)
- Bar key = row of the performed score's `measures` (correctness `measure_index`, control
  `measure_idx`, interpret `bar` all agree). Label = measure `name` (ASAP pickup is "0"), repeats
  get " (2)".
- Tiers: interpret() run twice (flag_quantile 0.95 / 0.99, same seed -> identical cores).
  too_flat at 0.99 = strong.
- Correctness tiers from clean D-08 copies (`scripts/calibrate_report_f08.py`, `--from-cache`):
  expert bars: >=1 wrong 7.1%, >=2 2.1%, >=3 0.85%; missed+extra/note q95 0.267, q99 0.634;
  per-performance error rate median 4.7%, q95 16.4%; median 42% of bars have a flagged note.
  "Any wrong note = strong" would violate the tier definition.
- Timing noise computed in the report on the F-06 curve convention (tgt.timing, refs.timing
  mapped by the beat map), not control_features (which uses the markings-aware fit), so target
  and refs match. Refs as targets (Op.10/3, 40 LOO): 6.7% notable+, 2.2% strong (nominal 5/1).
- Low-confidence velocity issues and per-bar shape flags inside a too-flat window are listed but
  not practise-eligible (otherwise a deadpan's top items were "you move ahead 67%").
- Too-flat magnitude = expert median SD / target SD. Practise rank = tier, then magnitude
  (multiple of the notable limit) across categories: a 40 ms jitter bar outranks 3 wrong notes.
- tempo_overall compares over the same mapped beats (Vienna excerpt vs whole-piece median was
  30 vs 42 bpm, misleading).
- Vienna midi folder has `*_p23-average.mid`: glob `p[0-9][0-9]` only.
- Headless check: Chrome `--headless=new --screenshot` works for visual review; dark by default.

## Measured
- (a) SunMeiting08: 7.0% error rate, 5 tiered bars; tempo 3 strong + 15 notable bars (F-06
  known); timing 16 bars tiered (8 strong) vs transcribed PianoCoRe refs: open question.
- (c) D-08 5% + 30 ms jitter: 93 injected in 56 bars, all 56 flagged, 91% more errors than (a),
  2 bars increase without injection; timing noise 67.7 -> 72.7 ms. Practise top 3 unchanged
  (single errors per bar are within the expert range).
- (d) deadpan: all 5 windows too flat strong (tempo and velocity), tempo typicality <= 0.006.
- (b) Vienna p01 + 21 sensor refs: velocity high confidence, one notable evenness bar.
- Runtime: 8 s (a), 16 s (b, 21 extra alignments).

## F-08b (2026-09-28)
- Provenance check `scripts/check_timing_provenance_f08b.py` (18 min, 10 workers) ->
  `data/interim/timing_provenance_f08b/`. 64 D-10 pairs / 43 pieces, both versions left out of
  refs. Pooled notable+/strong: Disklavier tempo 4.3/0.9%, timing 4.2/1.2%; transcribed twin
  4.5/1.0%, 4.7/1.3%; paired diff CIs include 0 (disk slightly lower). PianoCoRe refs as targets:
  Disklavier 3.5/0.6% (tempo), transcribed 5.4/1.5%. SunMeiting08 is a high-flag performer
  (its transcription 29%/32%): not provenance. No fix; timing flags leave "experimental".
- PianoCoRe tier A cache holds the ASAP copies (source id `ASAP_<stem>`, 63/65 pairs) but
  mostly NOT the transcribed duplicates (2/65): exclude both anyway.
- Recurring errors: naive "same key in >= 2 takes" fires on 24-31% of expert bars
  (3 ASAP pianists as pseudo-takes, `scripts/calibrate_recurring_f08b.py`, cache
  `recurring_signatures.pkl`). Cause: score/checker artefacts shared by all pianists (missed
  notes in chords/ornaments). Only wrong-pitch + expert filter (keys seen for other experts of
  the same score removed) is under 1%: 0.18% (2 takes) / 0.51% (3). Needs >= 2 experts;
  report_from_files auto-loads up to 6 ASAP perfs when takes are given.
- Chopin Op.10/3 has ONE ASAP performance: sample (e) uses Op.10/4 (22 perfs).
- The harness blocks Write of new .md files from subagents; the spec text went to the lead.
