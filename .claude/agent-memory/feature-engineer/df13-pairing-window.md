---
name: df13-pairing-window
description: DF-13 wrong-pitch pairing window on transcribed input - dev decomposition of DF-12 loss, candidate rules, criteria, script and trap notes
metadata:
  type: project
---

DF-13 (2026-10-10). Prereg `docs/specs/correctness-validation.md` "Pre-registration DF-13"
(anchor hash 44bd842e...1214, end marker line "End of the DF-13 pre-registration.").
Script `scripts/eval_pairing_window_df13.py` (`--set dev|heldout`, `--from-cache`,
`--reachability`); outputs `data/interim/df13/`. Floor rebuild
`scripts/rebuild_floor_tables_df13.py --rule <r>`; `a01_henry_reports.py --floor-tables`.

**Dev decomposition (BL-18b targeted copies, 6,765 injected notes)** - the audit's "window is
the main cause" is only half right:
- Unpaired injected notes: only 43% (Transkun V2) / 48% (Aria-AMT) have the intended score note
  *missed*; the rest have it re-matched by the aligner to another same-pitch performed note
  (median 0.28 / 0.37 s from its expected onset; in the clean copy that note was matched to
  another score note). Realigning after the injection moves matches (643 re-partnered matches in
  238 copies, 38% onto an injected note). No window can fix that half -> window-reachable loss
  is 4.3% / 6.4% of injected notes.
- In the clean copy the LOO expected-onset error of those notes was small (median 25 ms); the
  targeted copy's error (141 / 180 ms) comes from the realignment plus genuine chord asynchrony
  (bass played 100-200 ms before the melody).
- Robust (outlier-knot) time map made things worse; isotonic fit no help.
- Rules (correctness `wrong_pitch_window`): fixed 100 ms, wide 200 ms, tempo 0.4 quarter
  (clip 0.1-0.3 s), error 2 x max LOO residual within 3 onsets (clip 0.1-0.3). Pair cost stays
  in units of 100 ms. Dev tempo: strict +3.3 / +3.7 pt, clean wrong labels +9%, report strong
  unchanged (expert tables move with the target), targeted 3-wrong strong 71.5 -> 77.3 /
  68.4 -> 74.6%. Tempo shrinks windows in fast runs, so no added mispairing there.
- Dev reachability (16 pieces): tempo PASS 0.64, binding M1 Transkun (mispair vs a third of gain).

**Held-out result (16 pieces, seed 1010): FAIL by rule.** tempo passed everything but F1 (clean
wrong-pitch labels +15.02% Transkun / +16.8% Aria vs bar 15%); error FAIL, wide PARTIAL. Ravel
"Scarbo" (clean wrong 15.7 / 28.3 per 1k) gave half the added pairs; dev F1 reachability 0.99
was optimistic because held-out repertoire had higher base rates. Lesson: a relative clean
false-pairing bar is dominated by the noisiest transcription piece; register a per-piece-robust
statistic (median of per-piece ratios, or leave-one-piece-out) or a GT precision check instead.
Also: P clean strong under fixed = 1.49 / 1.86% on these pieces (BL-18b band 1.25%).
Floor tables relabelled today differ from cached f08c_floor_tables.pkl in 9 bars of 150 tables.

**Traps**
- The whole report-level effect of a checker change on clean bars is near 0 because transcribed
  expert tables are relabelled with the same rule; always relabel experts with the candidate.
- Bar labels can repeat; pivot report tiers by row position, not by label.
- BL-18b script functions are importable by path (`_load`, `targeted_copy`, `rule_tiers`).
- Load from other agents can triple wall time (dev 600 jobs: ~35 min at load ~60).

Related: [[bl18b-interim-rules]], [[bl19-bl20-density-staff]], [[correctness-and-mistakes]].
