# ml-researcher memory

Index. One line per note; details in topic files beside this one. Settled facts belong in
`.claude/rules/` or `.claude/skills/`, not here.

- [percepiano-labels.md](percepiano-labels.md): CSV layout, cleaning rules, filename = piece_Nbars_player_segment, duplicate rows, two differing mean jsons (labels/ one matches the CSV)
- [library-gotchas.md](library-gotchas.md): factor-analyzer/sklearn shim; MuQ; **SyMuPe ignores lm_top_p (pass top_p)**; parallel numpy
- [results-index.md](results-index.md): numbers measured so far and where they live (R-01, R-03 incl. post-audit variants)
- E-01 harness API: `pianolens.eval` (group_kfold, bootstrap_ci with groups=, rater_parity, fit_bradley_terry); use it, do not re-implement
- S-02/R-03 facts: `pianolens.audio.render` (Salamander C5 Light, FluidSynth pinned); MuQ gotchas in library-gotchas.md; R-03 numbers in results-index.md
- run.py pattern for fast within-passage bootstrap metrics (vectorised over seeds x dims, self-checked against pianolens.eval): `experiments/2026-09-27-R-03-muq-percepiano/run.py`
- [r04-symbolic-percepiano.md](r04-symbolic-percepiano.md): R-04 feature pipeline, loader dup-id bug (fixed), short-segment settings, HGB/LightGBM traps, fast passage bootstrap; post-audit lessons (SB ceiling, deviation disclosure, per-work deltas)
- [r02-dimensionality.md](r02-dimensionality.md): R-02 curve cache layout/reuse, PianoCoRe majority-score rule, Vienna offsets, fixed-n + held-out + phase-null method
- `pianolens.eval.dimensionality`: explained_variance_ratio, n_components_for, heldout_r2_curve, loo_r2_curve, phase_randomize, column_shuffle, whittaker_smooth (R-02)
- Parallel numpy: set OMP/VECLIB threads = 1 in pool workers (library-gotchas.md)
- [r06-expression-models.md](r06-expression-models.md): R-06 SyMuPe vs Pianist Transformer: venv recipes, teacher-forcing API, note-order traps, training-overlap facts, results (tie; likelihood prefers deadpan), audit outcome + post-audit fixes
- `pianolens.models.expression_io`: matched_pairs, global_seconds_per_quarter, note_expression (velocity / log IOI / log art), deadpan, time_signature_events (R-06)
- [r08a-llm-phrase-pilot.md](r08a-llm-phrase-pilot.md): R-08a prep: pilot ids/movements, MusicXML embeds DCML labels (<harmony>), unfolded measure numbers, cadence-vs-phrase-end ceiling, comparator numbers
- [r09-coherence-skill.md](r09-coherence-skill.md): R-09 H4 on MAJEPPA inconclusive (Confirmed w/ caveats, post-audit fixes applied); coherence cache CSV; n_blocks>=3 loophole; articulation fails the Aria-AMT noise floor, timing passes (Transkun unresolved); pooled effect = top levels, not shown to be context
- [r08b-memorisation-control.md](r08b-memorisation-control.md): R-08b prep: disguise by patching R-08a common.py globals, line-of-fifths respelling, importlib for R-08a score.py, hash-after-append trap, DCMLab phrase-labelled corpora (JC Bach best; Kozeluch unlabelled)
- [r07-finetune-job.md](r07-finetune-job.md): R-07 split/job/training gotchas; audited, author fixes closed 2026-10-10 (pair_ci.py, posthoc_tables.py)
- `pianolens.models.expression_split` (work_key, catalogue_tokens, alias_conflicts, assign_split, leakage_check) and `expression_data` (interchange_from_aligned, item_variants = deadpan battery, flat_training_rendition) (R-07)
- [r08c-unfamiliar-repertoire.md](r08c-unfamiliar-repertoire.md): R-08c prep: J. C. Bach Q1-Q5, importlib reuse of R-08a score/render, detector not pass-consistent on JC Bach (propagation changes its F1), worked example moved to bars 25/28
- [r08d-romantic-repertoire.md](r08d-romantic-repertoire.md): R-08d prep: R1-R5 Romantic draw, runs A/B, no period phrase, recognition non-gating, tempo words in staff text, title-word check false positives, mixed-meter quarter tolerance
- [r05-context-shortcut.md](r05-context-shortcut.md): R-05 H8 simulated-context shortcut (supported, Provisional); reusable MuQ cache of 1,500 MAJEPPA renders x 4 contexts; zsh word-split trap
- [r11-teacher-annotations.md](r11-teacher-annotations.md): R-11 tonebase pilot (Confirmed w/ caveats); protocol v1.3 (BL-31); PianoCoRe staff/empty-measure/target-grid traps
- [bl17-romantic-llm.md](bl17-romantic-llm.md): BL-17 run (68 blind annotators launched by me): simple 0.635 t [0.549, 0.720] INCONCLUSIVE, Confirmed with caveats; post-audit text fixes applied (what I overclaimed); reuse of R-08b/d code, concurrency limit 20, transcript audit script
- [r10-h1b-prereg.md](r10-h1b-prereg.md): R-10: prereg, amendments, result (falsified, scoped: amplitude + partial shape), audit fixes 1-6 closed (PT, dev_gen top-p 1.0 traps)
- [r10b-captured-share.md](r10b-captured-share.md): R-10b, a duplicate R-10 design made on the RTX box without seeing the Mac's R-10; superseded, exploratory only. Finding worth keeping: span captured share has a high envelope-null floor (~0.58 at K=32).
