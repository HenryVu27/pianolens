---
name: r10-h1b-prerun-review-facts
description: R-10 H1b pre-run review 2026-10-05 - author transcript id, content n-gram leakage check (whole-set ids escape work keys), near-duplicate renditions, top-p switch timeline, PERiScoPe v1.0 confirmed by model card
metadata:
  type: project
---

- Author transcript: subagents/agent-a69b0bd85886c19a8.jsonl (session 73c389dd).
  - The first README Write was at 16:46:59Z, with the primary at top-p 1.0 and the thresholds
    already in.
  - Run3 `summarize` printed both arms' R²c at 16:56:49Z, and the switch to 0.95 came at
    16:58:18Z.
  - Extract an early draft with jq: select the Write tool_use with file_path ending
    README.md, then `.input.content`.
- Expert-side rerun: `summarize_h1b.py --experts-only --set artifacts/sets/fresh --out <scratch>`
  is byte-identical to artifacts/prereg_experts (about 1 min). To test exclusions, make a scratch
  set dir with symlinked items/ and gen_items/ plus a filtered manifest.csv.
- **Leakage trap.** R-07 `work_key` gives whole-set ids (for example
  `pianocore:Debussy,_Claude/2_Arabesques`) a key separate from their movement ids, so the
  work-mate and alias rules miss paired movements inside a whole set.
  - Catch it with a content check: 12-onset pitch-set n-grams from the refined score MIDI in the
    zip (prefix `PianoCoRe/refined/`), checked against all held scores.
  - The separation is clean: 3 hits at most for unrelated pieces, 114 or more for real overlap.
  - Fresh hits: Debussy Arabesques, Ravel Tombeau whole, Bartók Sz.56/3. On R-07's R10u, 5 of
    74: bwv856/857/862 whole, k545 whole, clementi op36 no1.
- PianoCoRe piece "Clementi Op.36 No.1/1. Spiritoso" is really No. 1's Allegro (C-E-C-G-G
  opening). It is mislabelled; the PERiScoPe folder title is ambiguous too.
- **Near-duplicates.** `is_duplicate` is False, yet within-piece deviation r > 0.9 occurs in 25
  of 1,788 renditions. Examples are the same Gould recording in ATEPP and PERiScoPe (r 0.997),
  and a Transkun/Aria copy with velocity r only 0.34.
  - They inflate the held-out expert oracle when the copies split across held-out and
    reference (captured-share oracle 0.389 -> 0.256).
  - The median within-piece r is 0.04; there is no clean gap above 0.8.
- The HF model card `SyMuPe/EncDec-base` at 1b942f28 says it was trained on PERiScoPe v1.0.
  v1.1 (Jan 2026) has 1,162 fewer pairs, and its root metadata.csv equals v1.1.
- Transcriber velocity scale is not a confound: within-piece per-rendition velocity s.d.
  relative to Aria-AMT is 0.91-1.04.
- R²c is 2rb - b², with b = sd(pred) / sd(target). In the dry run log IOI r was 0.56 but R²c
  was -1.62, i.e. amplitude overshoot. Always ask for b.

Related: [[r07-symupe-finetune-audit-facts]], [[f07-takes-audit-facts]] (duplicates deflate there), [[r06-expression-h2h-audit-facts]].
