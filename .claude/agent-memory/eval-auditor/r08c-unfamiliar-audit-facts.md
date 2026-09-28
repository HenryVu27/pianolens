# R-08c LLM unfamiliar-repertoire (J. C. Bach) audit facts (2026-09-28)

- Transcripts: `<session>/tasks/<id>.output`; 10 ids in DECISIONS (R-08c annotation run). Q3-Q5 were
  read in two Reads (read-size limit): check that the last tool_result tail shows `END` to confirm
  the whole rendering was seen. The Grep for `WA06`/`WA14` hits base64 signatures, not stems.
- Instructions attachment: user global CLAUDE.md + personal MEMORY.md only (no Bach/DCML/pianolens).
- Read-only rerun: `PYTHONPATH=<R-08a exp>:scripts`, `sys.path` += R-08c exp, `import score as SC`;
  `SC.run_llm(dir, run, out=scratch)`, `SC.compare(art=scratch, ann_root=EXP)`. For `harness()`, first
  set `SC.ART` to a scratch copy of artifacts (it writes `ART/harness.txt`). `build.py --check` only
  prints. Draw: replicate the logic inline (draw.py writes selection.json). All outputs byte-identical.
- Numbers: primary 0.750, t [0.588, 0.912], one-sided p(>0.70) 0.22; LOO min 0.722; worse-run 0.731;
  paired +0.313 t [+0.154, +0.472], 5/5 positive; per movement Q1 .815 Q2 .562 Q3 .667 Q4 .843 Q5 .863.
- Q3 (variations) P 0.500 R 1.000 in both runs, identical end sets: LLM marks 4-bar phrases, DCML
  one per 8/10-bar half. This is evidence against DCML label recall (a recaller would copy DCML's level).
- DCML jc_bach labels are public (v2.4 2025-04-27, Sci. Data 2025) before the model cutoff (June 2026).
  Unfamiliar repertoire rules out recognition, not label exposure. The only clean control: labels
  made after the cutoff.
- Scope: galant/Classical sonata-type movements, simple meters. Romantic repertoire (the PianoLens
  target) is untested. Candidate: DCML Chopin/Schumann corpora if they have phrase labels (unverified).
