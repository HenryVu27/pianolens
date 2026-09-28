# S-01 / S-03 build notes (2026-09-27)

## Where things are
- Degradations: `src/pianolens/study/degrade.py` (`degrade(ap, dim, level, **opts)`); excerpt cutter
  `src/pianolens/study/excerpt.py` (cuts the score too by default: `cut_score=True`).
- Spec: `study/stimuli-S03.json`; build: `scripts/build_study_s03.py` (94 s, 6 workers, 592 clips,
  552 MB in `data/interim/study_s03/`). `--probe` prints clip durations only. `--ladder main` needs the
  spec's `main` block (set after the Henry pilot) and bisects the control level per excerpt to hit x targets.
- Power: `scripts/power_s03.py --n-rep 200` takes about 14-20 min; output `data/interim/study_s03/power/`.

## Gotchas found
- Degrade AFTER cutting the excerpt (exact dose per clip). Degrading the whole piece then cutting gave
  wrong-note counts of 0 in short clips and pedal changes outside the clip.
- The F-04b harmony detector finds very few changes in these openings (0-6 per 2-bar detection clip,
  1-11 per preference clip). Pedal blur graded by *fraction* is useless there; graded by lateness
  (`grade="hold"`) works. Clips with no change are flagged `changed: false` and design.js skips them.
- A forced pedal interval must END WITH A LIFT (late pedal change). Restoring the pianist's state
  without a lift kept the blur going until the pianist's next lift, so `hold_beats` had no effect.
- `_new_aligned` re-sorts notes by onset: tests must compare by note id, not by array position.
- Note ids like "p10" sort before "p2" as strings: sort by int(id[1:]) in tests.
- Onset jitter s.d. s adds IOI s.d. sqrt(2) s: van Vugt's 10.22 ms IOI threshold = 7.2 ms onset s.d.
- The ms threshold is at 8 notes/s; most excerpts run 2-8 positions/s, so use the CV ratio.
- `tabulate` is not installed: `DataFrame.to_markdown` fails; power_s03 has its own md_table.
- Headless Chrome (`--headless=new --dump-dom --virtual-time-budget`) runs the app's autotest mode fine,
  but an `<audio>` element never fires loadedmetadata under virtual time; probe decoding with
  fetch + `OfflineAudioContext.decodeAudioData` instead.

## Numbers (simulation under ASSUMED parameters, protocol section 6)
- Design A2 (84 detection + 49 preference trials, ~75 min with the measured clip lengths):
  N = 96 gives P(supported) 0.92 at a true cost ratio of 3 (margin 2); P(falsified | equal) 0.52 at 96,
  0.85 at 160. B2 (double trials): 48 / 96. False positives <= 0.02 in every variant.
- beta = 0.8 hurts power (level 8 near the logistic ceiling): keep preference levels moderate.
