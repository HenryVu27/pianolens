# R-08b LLM memorisation control audit facts (2026-09-28)

- Transcripts: `<session>/tasks/<id>.output`. The 15 ids are listed in DECISIONS (R-08b annotation run).
  Thinking blocks are EMPTY in the transcripts (redacted), so implicit recognition cannot be
  audited. Only `recognised_piece` and the hand-back text are available. Check the hand-back as
  well: B2 M4 wrote `null` but said "possibly an early Mozart finale", and D4 guessed Haydn.
- Prompt-template check: normalise the folder and id with perl (`\b` does not work in BSD sed),
  then sha. All 15 prompts were identical.
- Reproduce without touching the repo:
  - `import score as SC; SC.ART=Path(<scratch>)`, with `PYTHONPATH=<exp>:<R-08a exp>:scripts`;
  - run `run_llm` for A/B1/B2, then `compare()`;
  - `harness()`, with ART patched, is read-only;
  - `disguise.py --check` is read-only;
  - `DG.render_one(p).text` re-renders for a determinism check.
  All outputs were byte-identical.
- Trap: pooled "recognised vs unrecognised" means across runs are confounded by movement.
  kv330_2 (easiest, 0.952) is never named. Within movement, named runs were higher (kv330_3
  0.763 vs 0.674). Use A vs U within movement only.
- Numbers: A 0.802, U 0.789, A − U +0.014 t [−0.029, +0.056], run SD 0.031, A − detector +0.237
  t [+0.051, +0.423]. D4, with 57 double accidentals, held at 0.952.
- Open item: an unfamiliar-repertoire test (DCMLab `jc_bach_sonatas`, 29 pieces, 442 phrase
  ends) is needed before any claim beyond these 5 famous movements. Koželuch has no phrase
  labels.
