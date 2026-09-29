# F-05e LLM phrase measures audit facts (2026-09-28)

- Prereg hash: `head -n 160 README.md | shasum -a 256` = d7205e40...069b18 (header through the
  "## Command" closing fence; line 161 blank, 162 "## Run record"). Feature-engineer transcript
  `<session>/subagents/agent-ab42b94657b26256c.jsonl`: README 23:37:59Z, first compute 23:42:25Z.
- Rerun recipe: `import run as F` from the exp dir, set `F.ART`/`F.ROWS` to an absolute scratch
  copy, `F.summary()` -> byte-identical. Scripts in scratchpad `f05e_audit/` (controls.py uses
  `importlib.import_module('pianolens.features.shaping')`: `from pianolens.features import shaping`
  returns a FUNCTION, not the module; and never seed with `hash(str)` across processes).
- Fast `concave_excess`: `_arc_table(grid, starts, 3)` + `_shift_bounds(starts, ±2*bpb, lo, hi)`
  with `grid = tempo_model(ap).beats`, lo/hi from `ap.score.notes.onset_beat` (min, max+1).
  Matches `phrase_tempo_shaping` to 1e-16. 8 units x 200 draws x 4 control types: 3.5 min, 8 procs.
- PianoCoRe refined vs DCML score (R1-R3): DTW map is a constant offset (0 / 3 / 4 beats). The
  reported 0.94-0.97 agreement pools ends and detector boundaries; starts are ~100% exact.
- Controls (8 units): random at LLM density -0.03 / +0.01; DCML halved 0.140 (vs 0.473): the ±2-bar
  null lands on the true boundaries when phrases are 2 bars, so finer = penalised; DCML + random
  extras to LLM count 0.409; DCML ±2-bar jitter 0.096. LLM 0.418 ~ "DCML + random extras"; on
  Romantic LLM is below that control (placement loss).
- Reachability with observed SD 0.098: P(RECOVERED) 0.99 / 0.90 / 0.50 / 0.10 at true 0 / -.05 /
  -.10 / -.15.
