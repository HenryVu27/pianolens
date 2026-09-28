# R-08d LLM Romantic-repertoire audit facts (2026-09-28)

- Transcripts `<session>/tasks/<id>.output`, 10 ids in DECISIONS (R-08d annotation run). Both R4
  readers (A a78c9c4c..., B ac8bb7be...) read in two Reads (offset 797); the tail shows `END`.
  Thinking blocks are 0 length (redacted).
- Read-only rerun (script `scratchpad/r08d_audit/rerun.py`): `sys.path` += exp, `import score as
  SC`; set `SC.ART` to an ABSOLUTE scratch copy of artifacts (relative paths resolve against the
  repo cwd and fail); `run_llm(dir, run, out=art)`, `compare(art=art, ann_root=EXP)`,
  `run_comparators(out=art)`, `harness(abs_scratch)`. `build.py --check` only prints; importing
  `build` does not run main, so `B.load(p)` + `B.C.render(s, id)` re-renders for a determinism
  check. Draw replicates from `selection.json` pool without reloading scores. All byte-identical.
- Timeline: README mtime 04:37:12 local (-0500); first annotator event 09:39:09Z.
- Numbers: primary 0.737 t [0.439, 1.036] p 0.373; LOO min 0.687 (no R3); worst-run 0.698;
  between-movement SD 0.241 (prereg assumed 0.13); paired +0.348 t [0.267, 0.430].
- R5 Liszt Au lac de Wallenstadt (3/8, 5 DCML ends at bars 19, 35, 59, 77, 108): both runs hit
  19/35/77 exactly and miss 59 (HC, LLM put it at 53) and 108 (LLM 104/111). F1 identical at
  +-1 beat, +-1 quarter and +-1 bar. 8 extras per run are half-phrase / coda subdivisions.
  Not "granularity only".
- Granularity check logic: ratio near 1 with high P/R is what the prereg says a recaller would
  show, so it is uninformative about exposure; only mismatched movements argue against recall.
- Recognition 0/10 (R-08a/b undisguised Mozart: 2-4/5 per run). No period cue in instructions.
  "Andante placido" (Liszt's own heading) stayed in R5; not recognised.
