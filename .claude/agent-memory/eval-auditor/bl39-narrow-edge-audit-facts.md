---
name: bl39-narrow-edge-audit-facts
description: BL-39 (narrow "outside" edge-bar policy, FAIL on E2) audit 2026-10-11 - prereg/timeline recipe, slow read-only recompute, disjointness from all interim pickles, cut-copy realignment probe (anchor mis-pairing), oracle-anchor counterfactual, O2 on N-edge bars, old-vs-new src report identity trick
metadata:
  type: project
---

- Prereg anchor `awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-39 pre-registration\.$/{exit}'`
  = 7e85dcd8...bc39. Same author transcript as BL-36/37 (`agent-a9af24a6302e4c775.jsonl`,
  session 73c389dd): hash + launch in ONE call 18:02:01Z; run log `scratchpad/bl39_heldout.log`
  ends 20:55Z with the verdict; API limit gap to 22:42Z, then readout only (info), no rerun.
  Code check: `git diff 87be183 1035bba -- src/pianolens/report | shasum` = fcef2308...; script
  sha b7e7493f... both match committed.
- Read-only recompute: import `scripts/eval_edge_narrow_bl39.py` as `e39`, `evaluate(rows)` on
  `data/interim/bl39/heldout_rows.pkl` takes ~20 min (9 policies x N/Na tiers), ~2.4 GB RSS.
  0 diffs. Do NOT run main (overwrites csv/summary). `heldout_bars.csv` has per-bar tiers per
  policy (cols `N_<policy>`, `clean`, `d`: -1 cut, -2 not heard, 0 edge) - fast for E rows.
- Disjointness: scanning every `data/interim/*/*.pkl` rows for piece/id finds DF-15
  `asap_rows.pkl` / `keysensor_rows.pkl` (ASAP key-sensor, other dataset) sharing piece keys with
  BL-39 held-out (7 pieces). Not a PianoCoRe draw; info only. Real PianoCoRe overlap 0.
- Probe recipe (scratch bl39a/probe.py): rebuild cut copy from `cuts[kind]` t_lo/t_hi on
  `apc.performance.notes`, realign N with `repeats=C variant or "auto"`, partial=True. Tables
  equal cache 73/73. ~60-90 s per copy; 5 workers fine on 16 GB.
- Finding: residual E2 strong cut bars (33): boundary anchor (first/last matched note) is paired
  with a different performed note than the uncut copy in 32/33; inside missed notes: 46% never
  recorded, 30% re-paired within bar, 22% clean-missed, 1/394 kept-unmatched. Op. 25/8 bar 2
  start: repeated pitches slid back onto earlier beats. Oracle anchor (outside + never-recorded
  as low conf, retiered with `tiers_lc` on a fake summ {"table", "lc"}) -> E2 -0.58.
- O2 pooled hides cost: N-edge bars only (296) lead omissions caught 58.4% k0 / 8.8% cand /
  1.4% k1. Every policy passed O2 on held-out incl. k2 (-46.96).
- Second-onset sabotage passes all held-out rows (O1 -6.94, 7/15 pieces <= -8; E2 +0.145).
- Old-vs-new src report identity: `git archive <commit> src | tar -x -C scratch/old`, then
  SYMLINK data/experiments/configs/docs/scripts/study into scratch/old (modules resolve
  `parents[3]/data`); without symlinks expert refs and LLM phrase caches vanish and the JSON
  differs for unrelated reasons. Run CLI with PYTHONPATH=scratch/old/src.
- Production `_correctness_section` rule "outside" n_missed_low_confidence == eval counts 19/19
  (fast repeat off and union on). Gaps: any non-"bar" string selects outside; default basis
  "score" not "score_le"; text.py says all missed not ranked.
- Verdict: Confirmed with caveats (FAIL stands). See [[bl37-edge-bars-audit-facts]].
