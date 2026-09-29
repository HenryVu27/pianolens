# R-05 (H8 simulated context shortcut) audit facts, 2026-09-28

- Prereg: header = the 186 lines before `## Results` without the blank separator
  (`head -n $((n-1)) README.md | sed '$d' | shasum -a 256` gives 7add1490...f0c5). Transcript
  agent-afbdac87bf38b1825.jsonl (session 9591b65d): README written 00:13:54Z, first analyze 00:15:18Z.
  Undisclosed: a ruff E501 rewrap of build.py and reachability.py at 00:15:27Z (no behaviour change).
- Rerun recipe: copy embeddings.npz, sample.csv and excerpt_stats.csv plus common.py to scratch, sed
  `ART = HERE / "artifacts"` to the scratch path, run as r5.py (primary 43 s; `--skip-secondary`
  variants 13 s). Run the variants one after another, not in a for-loop with grep: one attempt
  printed nothing. All 4 results JSONs are identical except wall_s.
- Design: each clip is used once per condition (emb[idx, ctx_idx]), so context copies cannot leak.
  Context decoding reshapes clip-major and uses repeat(g3, 4) (verified).
- Groups: 559 for 1,250 binary clips, 320 of them multi-clip (max 10); url = recording_id 1:1.
- Key benchmark: with context decodable at 0.997, compare CC against a stacked matched MuQ score +
  one-hot context label (inner OOF, LR C=100): 0.959 / permuted 0.705 vs CC 0.943 / 0.730. So the
  size is about 80% of an explicit-label ceiling. Appending the one-hot to the 2,048-d embedding under
  the same L2 gives only 0.916 (the penalty shrinks it); do not use that version as the ceiling.
- Within-piece AUC (138 pieces, 398 pairs): M 0.800, CC 0.922, delta +0.122 [0.066, 0.182], larger
  than the pooled +0.073. Repertoire lifts the matched baseline, which makes the pooled delta
  conservative.
- Teachers: `slow_demo` median 2.9 notes/s, clean context nearly exclusive to them (context-only AUC
  0.956), symbolic AUC 0.70. The inflation is +0.180 for teachers, +0.061 for virtuosos, -0.022 for
  child professionals.
