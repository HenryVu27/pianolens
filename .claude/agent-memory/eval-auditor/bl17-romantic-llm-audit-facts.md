# BL-17 LLM Romantic (24 simple + 6 compound DCML, disguised) audit facts (2026-09-29)

- Prereg hash recipe: Python `t[:t.index('## Preparation record')]` (raw bytes incl. the blank
  line) = c3803f83... `head -n (line-1)` does NOT match (different trailing bytes); use Python.
- ml-researcher transcript `subagents/agent-a5c313a816c9ab685.jsonl`: README Write 20:48:55Z, first
  draw run 20:48:59Z, hash 21:09:06Z, first Agent 21:09:28Z. 82 Agent calls: 14 "Concurrent
  subagent limit reached" refusals (never started), 68 ran. Check `is_error` on Agent tool_results
  whenever a launch list shows duplicates.
- Annotator ids in `artifacts/bl17_agents.tsv`; transcripts `subagents/agent-<id>.jsonl`.
  `audit_transcripts.py` writes into artifacts/ (copy it to scratch before rerunning); its issue list
  flags fractions like `/4`; independent check script `scratchpad/bl17_audit/blind_check.py`.
  Env attachment shows cwd = repo, AutoMem index names PianoLens (same as R-08a-d); no cue words.
- Read-only rerun: `sys.path` += exp, `import score as SC`, `SC.ART` = absolute scratch copy,
  `run_llm(E/annotations_X, X, out=ART)`, `compare(art=ART, ann_root=E)`, `run_comparators(out=ART)`,
  `harness(scratch)`. All byte-identical. Draw replicates from `selection.json` pool.
- Numbers: primary 0.635 t [0.549, 0.720] SD 0.202; worst-run 0.596 [0.516, 0.676]; paired +0.327
  [+0.237, +0.418] 23/24; +-1 bar 0.702 [0.625, 0.778]; compound 0.654 [0.460, 0.849];
  U - disguised +0.032 [-0.082, +0.147].
- Auditor numbers: R-08d minus BL-17 Welch +0.103 [-0.189, +0.394] p 0.41; corpus-equal BL-17 mean
  0.687 (R-08d is one-per-corpus); no-Chopin-guess (P03 P05 P06 P11 P22) 0.619 [0.517, 0.722];
  per run 88/314 DCML ends missed at +-1 beat, only 26 (A) / 21 (B) within +-1 bar; extras 188/158.
  +-1 bar is lenient: grid4 0.171 -> 0.405, proxy 0.261 -> 0.459.
- P19 Grieg op. 57/5: bar 170 tonic bass under held dominant, tonic chord in 171 (verified in
  rendering); 1-bar misses 7/9 in A but 4/8 in B.
- DF-02 cached pieces: 4 Chopin nocturnes + op. 64/2 waltz; op. 9/1 6/4, op. 27/2 6/8, op. 9/3
  2/2+6/8. BL-17 tested mazurkas only; compound stratum had no 6/4 or Chopin.
