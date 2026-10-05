# BL-21 / BL-22 audit facts (2026-09-29)

- Prereg: `docs/specs/phone-audio-baseline.md`. BL-21 hash = section lines joined + trailing "\n";
  BL-22 (end of file) hash = joined, no trailing newline. Author transcript: session 9591b65d,
  subagent agent-a83a1e7cee51b1614.jsonl (prereg heredoc 20:41:10Z, bl21 script 20:41:52Z, bl22
  script 20:45:51Z).
- BL-21 rerun: import `scripts/bl21_repeated_notes.py`, set `b.OUT` to scratch, symlink
  `aria_amt/` into it, PYTHONPATH=scripts (process pool). Takes about 1 min; byte-identical.
- BL-21 diag (scratch, not persistent): per-note table with prev_vel, prev_dur, prev/next IOI,
  local-drift rematch, nearest est. Gap = ioi - prev_dur < 5 ms in 79% of the <80 bin; isolated
  pairs 88%; the bounce-like rule is (not in run) & vel <= 0.5 prev.
- BL-22 rerun: import the script and set `b.OUT = data/interim/henry_takes/bl22/audit` (personal data
  stays in data/interim; copy labels.parquet there first). analyse about 1.7 min, spectro about
  10 min, posthoc about 3 min; all identical.
- BL-22 key checks: white-key share (97%), consecutive step <= 2 semitones vs permutation, n-gram
  recurrence across takes, onset-locking vs random times, peak-frequency cents vs correct notes
  (stretch tuning), 1/q ceiling and f = (h-q)/(1-q).
- Listening targets file: data/interim/henry_takes/bl22/audit/listening_targets.txt (never copy
  times into committed files).
