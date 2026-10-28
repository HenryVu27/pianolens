---
name: bl40-wrong-piece-stop-audit-facts
description: BL-40 (app quick-check stop under partial=True, PASS) audit 2026-10-27 - prereg/code hash recipe, read-only recompute, probe recipes (app-path re-run, file round trip, ASAP, Henry excerpts, oracle span), repeat-path memory blow-up, confirm-mode "all" zero by construction
metadata:
  type: project
---

- **Prereg anchor.** `awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-40 pre-registration\.$/{exit}'`
  gives bab3e6e3...d656.
  - Author transcript: session 73c389dd, `subagents/agent-a3d462ef8a1d4f09c.jsonl`. Hash at
    02:24:51Z, pool at 02:25:24Z.
  - Code check: `git diff 472f5fe 8134800 -- src/pianolens ':!src/pianolens/align/core.py'
    ':!src/pianolens/app/quick_check.py' | shasum` gives 30526ab7.
  - To check the post-hash edit, reverse the 02:25:04Z python-replace edit. That gives
    quick_check e79f95a3 and the script b1a77ae8.
- **Read-only recompute.** Import `scripts/eval_wrong_piece_bl40.py` as `bl40`. Then
  `load_probe(set)`, `rule_rows(df, **REGISTERED)`, `verdict`, `resample_pass`, `loo`. Takes
  about 2 min, 0 diffs.
  - Do NOT run `--stage readout`: it overwrites the readout JSON, grid and hard-cases CSV.
  - Takes pickles: `data/interim/bl40/heldout_takes/<crc32>_<fam>.pkl` = (meta, perf) pairs.
  - `takes_one` writes score copies to `bl40.OUT/scores`. In probes, set `m.OUT` to scratch.
- **Probe module.** Scratch `bl40a/probe.py`, not kept: `quick_safe`, `takes_of`,
  `write_shifted`, and `run` (ProcessPool, at most 5 workers).
  - Memory watchdog: `watch.sh` polls `top -l 1 -pid <child> -stats mem` and kills above a
    limit. `uv run` spawns python as a child; ProcessPool workers are grandchildren, so the
    watchdog misses them.
- **Main finding (repeat paths).** `align(partial=True)` builds EVERY repeat path; partial
  off builds only `max_candidates`.
  - Catalogue (804 scores): 17 have more than 16 paths. Handel HWV 432/6 has 65,536; K. 331 i
    8,192; D. 935/3 2,048; K. 331 iii 512. K. 265 enumeration alone passes 3 GB in 23 s, even
    with partial off: a pre-existing app defect.
  - K. 331 iii partial on: 157 s and 2.5 GB for 21 notes. K. 331 i and D. 935/3 do not finish.
    Batch workers reached 11 GB and 25 GB.
  - The BL-40 pools had at most 16 paths. Never batch-probe high-path scores with partial on.
- **Confirm mode "all".** H for takes under 75 notes is 0 by construction.
  - Mode "high" (same t / n_min) stops 1,331 of the 1,334 held-out wrong short excerpts asked
    to confirm. Dev registered rows are the same; held-out adds F 2-4 2.08%.
  - The dev minimum for right short excerpts was 0.733, which contradicts the prereg
    rationale for "all".
- **F 17-32** (Op. 49 No. 2 i, Aria-AMT): the true-span (oracle) ratio is 0.576, below its
  partial 0.610.
  - 33% of the excerpt's notes are extras in the whole-take alignment. So it is a noisy
    passage, not span detection; the author's mechanism was wrong.
  - Held-out right excerpts, partial minus oracle: median 0.000, minimum -0.109.
- **Henry excerpts** (3 per band from the 10 A-01 transcriptions, 600 alignments):
  - 0 wrong passes; highest wrong 0.545 (0.452 at 75 notes or more).
  - 1 right stop: take 04, Transkun, bars 40-44, 0.539 = oracle, 62% extras. Local
    room-audio noise.
- **ASAP** (11 scores x 190 right excerpts used as wrong pairs): 0 passes; highest 0.549 at
  75 notes or more. The ASAP Liszt S. 244/6 score as the right score: lowest 0.714.
- **File round trip** (excerpt written to MIDI, shifted to t = 0): 3 of 37 wrong ratios moved,
  by 0.01-0.15 (0.576 -> 0.424). Shifting in memory changes nothing.
- **Verdict:** Confirmed with caveats. App flag blocked until the repeat-path guard. See
  [[bl39-narrow-edge-audit-facts]] and [[bl36-partial-audit-facts]].
