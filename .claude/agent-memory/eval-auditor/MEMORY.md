# eval-auditor memory

Index. One line per note; details in topic files beside this one. Settled facts belong in
`.claude/rules/` or `.claude/skills/`, not here.

- [factor-analyzer-traps.md](factor-analyzer-traps.md): phi_ misaligned with loadings_ after variance sort; get_communalities wrong for oblique (fake Heywood); sklearn shim verified harmless
- [percepiano-audit-facts.md](percepiano-audit-facts.md): authoritative item order (LABEL_LIST19 + README example), articulation pole ambiguity, filename player = 2nd-to-last token, pedal doublet props up PA
- Pre-registration check without git: read subagent transcript jsonl timestamps (see percepiano-audit-facts.md last bullet)
- Cluster bootstrap of PA duplicates rows; the permutation null then treats copies as independent, so thresholds are too low and it leans toward MORE factors. Conservative for "never more than k" claims; do not use it to argue a count is at least k.
- [r03-muq-audit-facts.md](r03-muq-audit-facts.md): CrescendAI paper-era files location, pooled R² semantics, PercePiano passage/performer structure, Score renditions inflate within-passage metrics, D960 merge sensitivity, rater-tie cap in WP parity
- [r04-symbolic-audit-facts.md](r04-symbolic-audit-facts.md): prereg hash recipe from transcripts, rerun-to-scratch recipe (r4.py on PYTHONPATH for loky), stale code_hash, per-work heterogeneity (S0 wins only D960 mv3), pedal importance real, split-half is not a ceiling
- [r02-dimensionality-audit-facts.md](r02-dimensionality-audit-facts.md): prereg hash (head -144), rerun recipe from cached curves, phase null weak -> envelope null + parallel analysis (3-5 comps above null, 35-46% var), seed/weight/QC robustness, Disklavier k80 capped at d-1
- [r06-expression-h2h-audit-facts.md](r06-expression-h2h-audit-facts.md): prereg timeline, PERiScoPe v1.0 csv (D960/WoO80 unpaired), SyMuPe mask verified, rerun recipe, deadpan-variant test (robust AUC 0), c2 is a fail, per-target/per-work deltas, overlapping D960 segments
- [r08a-llm-phrase-audit-facts.md](r08a-llm-phrase-audit-facts.md): transcript-based blinding audit recipe (jq tool calls, instructions attachment), propagation fair check (printed-only), detector repeat-invariant, memorisation weak-evidence trap (unrecognised = easiest), n=5 bootstrap vs t-interval
- [r09-coherence-skill-audit-facts.md](r09-coherence-skill-audit-facts.md): prereg diff (trailing newline), rerun recipe, recording_id = video (row bootstrap), Czerny <12-bar rows drive S8, pooled effect = top levels (context unidentifiable), SESOI branch unreachable (P about 0.08/0.16), Aria vs Transkun noise CIs
- [r08b-memorisation-audit-facts.md](r08b-memorisation-audit-facts.md): thinking redacted (self-report recognition only), prompt-template sha, read-only rerun recipe, recognised-vs-not pooled means confounded by movement, J. C. Bach next
- [f07-takes-audit-facts.md](f07-takes-audit-facts.md): prereg via heredoc in transcript, safe rerun recipe (copy artifacts), cross-pianist control passes H5 too (delta 0.097; the informative part is R²(diff) 0.011 vs 0.049), residual dups deflate, ASAP basis has markings
- [r08c-unfamiliar-audit-facts.md](r08c-unfamiliar-audit-facts.md): split-read END check, read-only rerun recipe (patch ART for harness), primary 0.750 t [0.588, 0.912] p 0.22, Q3 granularity mismatch argues against label recall, DCML labels predate cutoff, Romantic untested
