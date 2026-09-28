# Decisions

Append only. Each entry records the date, the decision, the reason, and who decided.

- **2026-09-27, Henry + lead: symbolic first.** Phases 0-2 run on MIDI only. Reason: MIDI + score
  is a near-complete description of a piano performance, and PercePiano audio is rendered from
  MIDI anyway. Audio waits for Phase 6.
- **2026-09-27, lead: leave-piece-out evaluation is mandatory.** Reason: published
  rating-prediction models drop from about 0.6 to about 0.2 rank correlation on unseen pieces.
- **2026-09-27, lead: no audio corpora on the Mac.** Keep raw data here under 60 GB. Audio work goes
  to the RTX 5080 box.
- **2026-09-27, lead: an LLM is never the judge.** It is only used for score analysis (after it is
  validated) and for wording feedback. Reason: audio LLMs are weak at hearing harmony and meter.
- **2026-09-27, lead: the expression model shortlist is SyMuPe EncDec-base and Pianist Transformer.**
  The first step is a frozen likelihood comparison on (n)ASAP; fine-tuning comes after. Reason:
  both are score-conditioned, have released weights, and should fit on a 5080
  (see `docs/research/2026-09-27-expression-models.md`).
- **2026-09-27, lead: "leave-piece-out" on PercePiano means leave-work-out (4 works).** CrescendAI's
  published split holds out passages, which is weaker. Their later folds leak by performer.
- **2026-09-27, lead: PercePiano targets.** The primary target is the authors' official means,
  which makes our numbers comparable with published work. The de-duplicated means from our loader
  are a required sensitivity check. On PercePiano, leave-piece-out has only 4 groups (works), so
  report per-work results, not just a pooled number.
- **2026-09-27, lead: build the cross-dataset `piece_ids.parquet` together with D-03** (PianoCoRe ids).
- **2026-09-27, lead: data decisions after D-03 to D-05.**
  - **CIPI:** the PianoJudges `index.json` labels plus PSyllabus stand in for the gated CIPI scores.
    Henry may request CIPI access later (optional).
  - **Mistake set:** regenerate MAESTRO-E-style synthetic mistakes from MAESTRO MIDI with our own
    degradation generator (shared with S-01). Only real human mistakes can validate F-02, so Expert-Novice and Rach3
    amateur data stay a later goal. Globus is not needed.
  - **Licenses:** MAJEPPA, PianoJudges and PSyllabus are treated as research-only. No author outreach for now.
  - **Provenance:** Bösendorfer CEUS recordings (Vienna 4x22, Batik) are `sensor`. Confirmed.
  - **Alignment labels:** `interpolated` becomes an official label. Correctness metrics exclude
    interpolated pairs.
- **2026-09-27, lead: after F-01 (mean F1 0.964, 0.981 on reliable performances):**
  - parangonar DualDTW with the repeat path picked automatically is the default aligner.
  - Nakamura is optional.
  - Missed notes are reported per bar.
  - Downstream code uses the performed score returned by `align_performance`.
- **2026-09-27, lead: accept the MAJEPPA canonical piece-id change (D-07).** It is the only way to
  link MAJEPPA to the other datasets, and nothing downstream used the old ids.
- **2026-09-27, lead: R-02 uses the PianoCoRe tier A cache.** Timing analysis excludes
  `interpolated` rows. 730 pieces have 50 or more performances. Disklavier-only checks use the 978
  Disklavier performances.
- **2026-09-27, lead: accept the huggingface-hub lock move (2.0.0 to 0.36.2) needed for MuQ and
  transformers<5.** The full test suite passes. If it conflicts later, split MuQ into its own env.
- **2026-09-27, lead: H3 is decided on leave-work-out, with within-passage metrics as co-primary.**
  Pooled R² under leave-work-out mostly measures whether a model can predict which work a segment
  comes from, and that differs across works.
- **2026-09-27, lead: F-02 wrong-pitch pairing window should move from 50 ms to 100 ms (pending ticket F-02b).**
  The default was not changed yet: a naive switch breaks the ornament test.
  - Reason: bar-level wrong-pitch F1 rises from 0.922 to 0.942 at a 5% mistake rate, and
    false positives on clean playing rise only from 0.26 to 0.35 per 1,000 notes.
  - For a practice tool, missing a wrong note is worse than a rare false flag.
  - Revisit on real mistakes.
- **2026-09-27, lead: the F-02 gate is met on the D-08 synthetic set** (it replaces the gated
  MAESTRO-E). Validating on real human mistakes remains open; see BL-10.
- **2026-09-27, lead: after F-03.**
  - Accept the 1.5-bar smoothing cutoff (in score beats) and report-only tempo-step detection as
    defaults.
  - **Tier B does not read raw residual jitter as motor noise.** F-03 found residuals correlate
    across performers (about 0.59; 0.42 after removing within-bar patterns), so the fine-scale
    timing is partly shared and intentional.
  - Tier B noise is therefore the residual *minus the expert-consensus fine timing* for that piece
    (from PianoCoRe / ASAP performances of the same piece, leave-one-out). Where no references
    exist, fall back to `jitter_nometric_*`.
  - This also makes the fine-timing consensus itself a tier C/D feature.
- **2026-09-27, lead: PercePiano "work" is reported both ways.**
  - Primary: 4 groups (D960 mv2 and mv3 separate), which matches R-03 as run.
  - Required secondary: 3 groups, with D960 merged (the two movements share all 12 human performers).
  - A claim only stands if it holds in both.
- **2026-09-27, lead: F-04 follow-ups.**
  1. **Evenness has two variants.** Report the current rule ("broad") and a "strict" variant (sub-beat notes, runs in one direction or repeated accompaniment figures). Which one is kept is decided empirically in R-04 by predictive value, not by taste.
  2. **Accept the 4-bar phrase allowance** for tempo stability.
  3. **Accept the bass + chord-template harmony rule for now.** Validate it against the Batik-plays-Mozart DCML harmony annotations (ticket F-04b), since those give ground truth.
  4. **Citations:** lit-scout ticket L-04.
- **2026-09-27, lead: F-05 follow-ups.**
  1. **Smooth-tempo coherence is near zero with the phrase proxy.** Before tempo coherence counts as
     H4 evidence, test it with real phrase boundaries: Batik's annotated phrases (F-05b).
  2. **H4's primary measure is structural coherence *without* dynamic markings,** so obedience to
     the written dynamics is not counted. The with-markings version is secondary. Velocity and
     articulation are the primary channels until F-05b settles tempo.
  3. **MAJEPPA clips enter H4 only if they cover at least 85% of the score.**
- **2026-09-27, lead: SKY-Piano is unreleased (BL-11).** D-09 stays blocked. The substitute is
  D-10 (MAJEPPA, PianoVAM, Rach3). Emailing the authors is optional for Henry.
- **2026-09-27, lead: accept the F-04b harmony rule** (1-quarter window, no 7th templates; held-out
  F1 0.752 vs 0.710). Pedal window and threshold defaults are kept (86.5% of pedalled changes in
  Vienna K.331 lift inside the window). Any F-04 features cached before this are stale; R-04 was told.
- **2026-09-27, lead: after R-04 (Provisional, under audit).**
  - Accept the `types.py` duplicate-note-id fix. D-10 was told to check multi-track MIDI.
  - Keep both evenness variants: PercePiano cannot separate them. D-10 (skill) decides.
  - Reference-based features (the S1 style: distance to other performers' curves on the same
    passage) become part of tier D (F-06). They add +0.011 to +0.015 WP accuracy over S0.
  - **LightGBM needs libomp** (`brew install libomp`). Until then, experiments use sklearn's
    HistGradientBoosting and say so.
- **2026-09-27, lead: the R-04 headline claim is worded exactly:** "Averaged over passages, a
  62-feature symbolic model is non-inferior to frozen MuQ on unseen works (all 4 variants,
  margins 0.02 / 0.05). It is behind on D935's short 4-bar segments and ahead on D960 mv3.
  Both models perform at single-rater level; the full-panel ceiling is far higher (WP rho
  about 0.74 vs about 0.35)."
  So PercePiano has headroom. The limit is the models, not the labels.
- **2026-09-27, lead: R-02 result (Provisional, under audit): H1 as written is not supported.**
  - Expert expression over whole pieces is structured (below the null on every piece) but needs
    about 19 components for 80% of variance, not 10 or fewer. Transcription noise is not the cause.
  - We do not rewrite H1 after the fact. Instead:
    - **Tier D does not assume a low-rank whole-piece expert subspace.** Distance-to-experts uses
      (a) windowed / per-phrase subspaces, and (b) a score-conditioned expression model (R-06/R-07)
      as the "expected expression". It never uses a single global PCA basis.
    - **New hypothesis H1b, pre-registered as its own experiment:** "Given the score, expert
      expression is predictable". A score-conditioned model explains most held-out between-performer
      variance *that is shared*, while the performer-specific remainder is individuality.
      H1 and H1b are different claims: low-rank across performers, versus predictable from structure.
  - This does not contradict R-01 (ratings) or R-04 (features match MuQ). Rating space and the
    feature-to-quality mapping can be low-dimensional even if the space of legitimate
    interpretations is not.
- **2026-09-27, lead: R-02 is Confirmed with caveats.** The auditor's text fixes are accepted as
  written in the README Audit section. The key refinement, from parallel analysis:
  - The *shared*, above-null structure of expert expression is low-rank: 3-5 components per piece
    (≤ 10 on 97-99% of pieces), carrying about 35-46% of between-performer variance.
  - The remaining roughly 55-65% is individual.
  - So "interpretation = a small shared space + a large individual space". The 19-component count
    mostly measures individuality.
  - H1b uses those 3-5 shared components as its reference target.
  - Tier D: score deviation from the shared components as "unusual", and treat the individual part
    as legitimate freedom rather than error.
- **2026-09-27, lead: after D-10 (descriptive, not pre-registered).**
  - **CLAUDE.md rule 3 is broadened.** Context shortcuts apply to transcribed MIDI as well as audio.
    Any MAJEPPA-based skill claim controls for `recording_type`; R-09 must stratify by context.
  - **Tier B skill validity is unproven, not disproven.** Within matched contexts MAJEPPA shows no
    separation, but the power is modest. Clean validation needs context-matched data: Henry's own
    takes (O-01), BL-13 (PianoVAM audio run through Transkun, compared with its Disklavier MIDI, on
    the GPU box), or the Phase 4 study stimuli.
  - **Velocity-based features on transcribed MIDI are low-confidence.** On Transkun, the velocity
    residual SD is about 9 MIDI units, above the audible step, and transcription compresses
    velocity spread. They are excluded from skill claims unless the source is Disklavier/sensor or
    velocity is calibrated. Timing features survive transcription (+1%, about 2 ms).
  - **Tier A on transcribed MIDI** doubles the apparent error rate (0.039 to 0.080). Correctness
    feedback on transcribed or phone input must be calibrated against that floor (A-01).
  - **Rach3 provenance:** keep `sensor` as provisional; lit-scout confirms the instrument.
- **2026-09-27, lead: after F-05b.**
  1. **H4 primary channels are velocity and articulation.** Tempo coherence is secondary, and is
     reported only with validated phrase boundaries, `phrase_detail=True` and `clip_to_train=True`.
     - The F-05 proxy is no better than a 4-bar grid: F1 0.34 at ±1 beat.
     - Annotated phrase starts, ends and cadences lift Batik tempo R² from 0.07 to 0.14 (p 0.007).
       Shifting the annotations by 2 bars removes the gain.
  2. **R-08 (LLM phrase analysis) is go only if** it reaches about 0.7 F1 at ±1 beat on Batik DCML
     phrases. First try the cheaper route: phrase ends from cadence detection (F-05c).
  3. **The per-phrase tempo measure is a new ticket (F-05c):** the share of concave arcs and the
     parabola fit vs a shifted null. It avoids assuming one arc shape for every phrase. 81% of
     annotated phrases are concave, vs 44% when shifted.
  4. **`clip_to_train` now defaults to True** (lead). It changes R² by at most 0.001 on average and
     prevents out-of-fold blowups. The test that relied on the old default now sets it explicitly.
  5. **Batik loader:** add an option that returns the MusicXML-based performed score (with markings)
     plus the phrase and cadence tables (ticket D-11).
  6. **Minimum length:** structural-coherence R² counts as defined only with `n_blocks >= 3`
     (12 written bars at the default block size). R-04's short segments fall below this.
- **2026-09-27, lead: after R-06 (Provisional, under audit).**
  - **Raw expression-model likelihood is never used as a typicality or quality score.** Both
    models rank deadpan renditions above every expert (AUC 0.00). Any tier D typicality must be
    two-sided and penalize low expressiveness. F-06 was told to add a "too flat" flag and a deadpan
    known-answer test.
  - ~~R-07 / R-10 keep both models~~ *Superseded 2026-09-28 by the entry below (post-audit).*
  - **R-07's likelihood needs a correction:** score only the expressive deviation, or use a
    likelihood ratio against a flat-playing model.
- **2026-09-28, lead: R-06 is Confirmed with caveats. The pre-registered rule is followed: SyMuPe
  EncDec-base is the primary expression model for R-07 / R-10.** The earlier "keep both" departed
  from the rule and is withdrawn.
  - The tie-break is procedural: +0.0075 jitter AUC, CI [0.0027, 0.0129] with two-way resampling.
    It is not a quality difference.
  - **Pianist Transformer is kept only as a documented secondary**, for reasons the rule does not
    cover:
    - an Apache-2.0 license (BL-01 productization);
    - better articulation (paired -0.053 [-0.094, -0.015]);
    - a better mean velocity curve (H1b velocity 0.30, inconclusive, vs SyMuPe 0.096 at the
      falsification level);
    - it wins on D960 mv3.
  - PT enters R-10 as a pre-registered secondary arm, not as a replacement.
  - The speed figure is corrected: SyMuPe generation is 5.7x faster on an idle machine and 2.1x
    under 4 parallel jobs, not "6x".
  - **Any corrected likelihood (a ratio against a flat model, or deviation-only scoring) must pass
    the auditor's deadpan variants before use.** Those variants are: shifted velocity, 15% slower
    tempo, deadpan plus noise, and half-deadpans. Raw likelihood lost to all of them (AUC 0.00-0.08).
- **2026-09-28, lead: after D-11 / F-05c.**
  1. **The secondary tempo channel for H4/R-09 is `phrase_tempo_shaping` `concave_excess`**
     (concave-arc share above the ±2-bar shifted null), computed with cadence-derived boundaries.
     It was positive on held-out Batik (+0.21, 17/21) and Vienna (+0.51), so it is the most robust
     unannotated option across both. Proxy boundaries do comparably on Batik but poorly on Vienna.
     Coherence tempo R² stays limited to annotated phrases.
  2. **R-08 is changed into a bounded pilot rather than a full go.** The cadence route reaches 0.46
     F1, against the 0.7 bar. The LLM gets one cheap, pre-registered chance to beat it on the same
     held-out Batik movements before any API spend (R-08a). Its main target is half cadences, where
     the rule-based detector fails (HC recall 32%).
  3. **`phrase_source="cadence"` stays opt-in,** with its warning against using it for coherence.
- **2026-09-28, lead: after F-06.**
  1. **Two component counts, kept deliberately separate.**
     - H1b / R-10 uses the R-02 audit procedure exactly: whole piece, envelope-preserving surrogate,
       parallel analysis at the 95th percentile of 20 surrogates, n = 50. This gives 3-5.
     - F-06 (product) keeps Horn at 50 references per 16-bar window, which gives about 1-2. It is
       stable, and the report does not depend on the exact count.
     - Neither number is substituted for the other.
  2. **The report shows the per-bar *total-deviation* flag.** The shared-component flag is
     informational only.
  3. **No joint tempo+velocity decomposition for now.** The reference sets differ by channel
     (velocity uses Disklavier/sensor only).
  4. **Two severity tiers for the practice report:**
     - "notable": beyond the 95th percentile of leave-one-out expert deviation;
     - "strong": beyond the 99th.
     - About 5% of genuine expert bars are notable and about 1% strong. Only "strong" is highlighted.
     - Too-flat uses the same two tiers.
  5. Citations for Horn 1965, Ledoit and Wolf 2004 and Green et al. 2012 go to lit-scout.
- **2026-09-28, lead: R-08a annotation run.**
  - Confirmed before annotation: the `cadence` event type (cadences that do not end a phrase) and
    the DCML "phrase end = cadential arrival" convention in the instructions.
  - **Blinding:** `blind_input/` was copied outside the repo, to the session scratchpad
    `r08a_blind/`. The Batik MusicXML embeds the DCML labels in `<harmony>` elements, so annotators
    never get a repo path.
  - **Protocol deviation, disclosed:** five independent annotator agents, one movement each, instead
    of one agent reading all five. This keeps each context clean. INSTRUCTIONS.md still says "five
    files", and each agent was told to annotate only its own.
  - Enforcement is by instruction, not sandbox. The annotators' transcripts can be audited for file
    access.
  - The leakage grep's one hit is "a piacere" (M5), a tempo word containing "iac". It is harmless.
- **2026-09-28, lead: R-08a is Confirmed with caveats, so R-08 is GO, but conditional.**
  - **Result:** LLM phrase-end F1 0.817 vs detector 0.565.
    - Paired difference +0.252 [+0.118, +0.382]. The LLM is ahead on all 5 movements.
    - Exact onset: 0.793. Shifted and random nulls: 0.05-0.12.
  - **Blinding was clean** in all five transcripts.
  - **The t-interval [0.696, 0.938] replaces the optimistic percentile CI.** "CI entirely above 0.70"
    is NOT claimed.
  - **Memorisation is not excluded.** 4 of 5 pieces were recognised, and every large gain was on a
    recognised piece.
  - **The first pre-registered step of R-08 is therefore a memorisation control (R-08b)**, before any
    API spend or pipeline use:
    1. a disguised rerun of the same movements: transposed and respelled, tempo words and dynamics
       removed, bar numbers offset;
    2. run-to-run variance (2-3 reruns);
    3. lesser-known DCML-style-labelled repertoire, if a corpus exists.
  - LLM phrase boundaries may feed tempo coherence only if R-08b holds.
- **2026-09-28, lead: after R-09 (Provisional: inconclusive, under audit).**
  - **Articulation coherence is dropped from H4's primary channels on transcribed MIDI.** Its
    transcription noise (Aria-AMT median change 0.08, rank ρ 0.36) exceeds the entire effect of
    interest.
  - **H4 on transcribed data now rests on timing-residual coherence alone.** It survives
    transcription: change 0.008, ρ 0.95.
  - Articulation coherence stays valid on Disklavier/sensor input.
  - **Coherence minimum length: `n_blocks >= 3` AND at least 12 distinct written bars.** R-09 found
    8-bar études numbered 0-8 counted as 3 blocks, giving velocity R² as low as -80. The fix goes to
    the next feature-engineer ticket that touches `shaping.py` (F-05d).
  - **H4 cannot be settled on MAJEPPA.** The matched-context sample has no virtuosos and only 9
    teacher clips. A clean H4 test needs context-matched data across the full range, ideally
    Disklavier/sensor: Henry's takes (O-01) plus the Phase 4 stimulus set, or BL-13.
- **2026-09-28, lead: after F-08 (report card).**
  1. **Timing flags are labelled experimental** until F-08b checks for a reference-provenance
     mismatch. In sample (a), a Disklavier target was flagged on 20% of bars against transcribed
     references, while references scored as targets show 6.7%. F-08b will score each Disklavier
     performance against transcribed references, using the D-10 same-performance pairs.
  2. **A single wrong note stays untiered** (7.1% of expert bars have one). But **errors that recur
     in the same bar across repeated takes are promoted to "strong"**. Across takes, a recurring
     error is a learned mistake, not a slip, which is what a student needs to see.
  3. **"What to practise" ranks correctness first within each tier, then control and shaping.**
     This is the pedagogical order: notes first, then the music.
  4. **Confirmed:**
     - the ±20% note-rate window for comparing with published evenness values;
     - at least 10 references before any tier-D tiering;
     - strict (not broad) evenness runs in the report.
- **2026-09-28, lead: R-09 is Confirmed with caveats (H4 inconclusive).** Corrections to earlier entries:
  - The "articulation fails transcription, timing survives" finding holds **for Aria-AMT** (59 pairs).
    For Transkun, MAJEPPA's own transcriber, the 6 pairs cannot settle either claim. Timing's
    robustness there rests on D-10's onset check.
  - **R-09's pooled-vs-matched contrast also drops the top two skill levels.** "It vanishes once
    context is fixed" cannot be separated from "it needs the top of the scale". The same caveat
    applies to D-10's tier-B conclusion. The honest reading for both is **"not shown within beginner
    to advanced-student levels; the top levels are confounded with concert/demo context."**
  - R-09's "coherence makes prediction worse" came from 3 short Czerny rows. The honest version is
    "coherence adds nothing" (-0.032 [-0.074, +0.012] with at least 12 bars).
  - R-09's design had roughly an 8-16% chance of reaching "falsified" even with a true slope of 0, so
    inconclusive was the expected outcome. Lesson promoted to the rules.
- **2026-09-28, lead: R-08b annotation run.** 15 blind annotators were launched from folders outside
  the repo (scratchpad `r08b_A`, `r08b_B1`, `r08b_B2`).
  - The D4/D5 double accidentals are kept as pre-registered; this is disclosed.
  - Annotator agent ids, for the transcript blinding audit:
    - A (D1-D5): ad7bc4991a6abc637, a1532152e107cdf79, ae87a353f54f7d420, a6c609642183b5623, aa6b5e29f9b8f8a54
    - B1 (M1-M5): ad92050f8a418271a, acdfd2faff88b19d3, a81409ee8024ddf89, a83da2b646e7504a0, a92a7ced7c3e48a86
    - B2 (M1-M5): a910e1f8fc9fc618f, a985f1314699bf4b1, a5204ac38e626689a, a222b843373567bed, ad4779e9cf1012fe3
  - Transcripts live under the session tasks dir and may not survive a new session. Copy the
    annotations into `annotations_A/`, `annotations_B1/` and `annotations_B2/` as soon as each run
    finishes.
- **2026-09-28, lead: after R-07 job prep.**
  - R-10 (H1b) takes its unseen pieces from R-07's **R10u** set: 76 R-02 pieces with no
    score-paired PERiScoPe performance. The split file is `experiments/2026-09-28-R-07-symupe-finetune/split/pieces.csv`.
  - The R-07 split is frozen. The disclosed toy dry-run AUCs on 2 R10u pieces do not change it.
  - The PERiScoPe v1.0 metadata CSV (HF `SyMuPe/PERiScoPe` @ 5a637bd9) is registered in DATASETS.md.
  - Committing `split/pieces.csv` (derived ids only) goes with Henry's baseline commit decision.
  - If `calibrate` on the 5080 projects more than about 24 h, a cloud run needs O-04.
- **2026-09-28, lead: R-08b is Confirmed with caveats.**
  - **LLM phrase boundaries are approved for use on Classical-period keyboard repertoire** (the
    Mozart-sonata style validated here). They may feed tempo coherence (H4 secondary) and the report.
  - **The disguise rules out explicit recall** (naming the piece and recalling an analysis), not
    familiarity with the structure.
  - **Before LLM boundaries are used on other repertoire, or described as a general phrase
    annotator, the unfamiliar-repertoire test (R-08c on `jc_bach_sonatas`) is required.**
  - The pooled "recognised runs score lower" claim is withdrawn: it is a mix-of-movements artifact.
- **2026-09-28, lead: after S-01 / S-03 (the study is built, not run).**
  - **Provisionally confirmed:** the H6 axis (cost per detection-threshold unit) and the margin of 2.
    Final once the pilot freezes the protocol.
  - **E2, E5 and E7 are kept for the pilot.** Whether to replace them is decided after the pilot,
    since sparse harmony changes mean no pedal detection trials in those excerpts.
  - **OWNER decisions pending (O-02):** N and format (96 / 160 / design B2), sessions,
    in-person or online hosting, consent fields and payment, ethics review, and the Henry pilot date.
  - Lead recommendation: pilot on Henry first, then the internal pilot on 12 listeners to
    re-estimate variances, then choose N. B2 (96 listeners doing each part twice) is the most
    listener-efficient way to also be able to falsify H6.
- **2026-09-28, lead: after F-05d.**
  1. **Keep the `extract.py` override:** R-04-style 8-bar segments use 1-bar blocks and at least 8
     bars. That output is labelled "short-segment coherence". It is a descriptive feature, **not the
     H4 measure**, and H4 claims use the 12-bar rule only. (R-04's coherence features had about zero
     importance anyway.)
  2. **R-04's audited `features.parquet` is NOT regenerated.** It reflects the code state before
     `clip_to_train` became the default, and it reproduces exactly with `clip_to_train=False`.
     Reproducing R-04 requires that flag, and the R-04 README is annotated accordingly.
     F-05d's impact on R-04 is at the 3rd-4th decimal; H3 is still supported.
  3. **R-09 under the new rule:** still inconclusive. The old velocity secondary estimate
     (0.142) was driven by short Czerny études; it is 0.019 [-0.005, 0.039] under the new rule.
  4. F-07 (`takes.py`) was told to adopt the same `n_blocks` definition.
- **2026-09-28, lead: correction after the L-03 methods pass.** The "12-17 comparisons per item give
  reliability .70-.80" figure (from the first research pass, repeated to Henry) is unsupported by
  its cited sources. The new target for the Phase 4 pairwise study: **at least 20 comparisons per
  item** (total judgements at least 10 x items), SSR at least .8, plus split-half reliability
  (Kinnear et al. 2025; Verhavert et al. 2019: 10-14 for .70 and 26-37 for .90).
  `rules/study.md` and the plan are updated. Stale citation notes in the code docstrings are fixed.
- **2026-09-28, lead: after D-12. The R-08c design is fixed now, before any annotation.**
  1. **Exclude op. 5 nos. 2-4.** Mozart arranged them as the K.107 concertos, so they add a
     familiarity risk.
  2. **Stratify by rendered size (characters) rather than bar count**, so the middle stratum
     has candidates. Keep R-08a's 5-strata idea with a seeded draw.
  3. **Disclose that the renderings lack fermatas and printed rests** (they are derived), unlike Batik.
  4. **`tempo_word=False`.** Drop the movement-title tempo word, consistent with the R-08b disguise.
  5. The detector comparator on this corpus is 0.427 (29 movements); the go bar stays 0.70.
- **2026-09-28, lead: after F-08b.**
  - **The recurring-error promotion is narrowed** (it supersedes the F-08 decision item 2). Only a
    *wrong pitch* at the same score note in 2 or more takes counts, and it must pass the expert
    filter (not reported for any expert recording of the score) with at least 2 experts checked.
  - The broad rule would have marked 24-31% of expert bars strong. The narrowed rule marks 0.2-1%.
  - **Timing flags are no longer "experimental" with respect to reference provenance.** Disklavier
    targets are not over-flagged (paired difference -0.5 [-1.0, +0.0] points). Skill validity stays
    unproven (D-10 / R-09). Spec: `docs/specs/report-validation.md`.
- **2026-09-28, lead: after F-07 (H5 Provisional, under audit).**
  - Timing R²: the take-consistent part 0.123 vs the take-specific part 0.005, across 1,390
    same-pianist groups. A Disklavier check on 40 groups gives a smaller but positive difference
    (0.075).
  - Tier B/D does not switch to "take-consistent = intent" until the audit passes AND it is tested
    on real same-day practice takes (O-01, or BL-16 Rach3).
  - **BL-16:** split the Rach3 Hanon sessions into takes and align them, as a same-day practice test
    of H5.
- **2026-09-28, lead: R-08c.** The detector's pass-inconsistency on the J.C. Bach repeats is recorded
    and disclosed. The comparator remains the detector's own score (0.437).
- **2026-09-28, lead: R-08c annotation run.** 10 blind annotators were launched from `r08c_R1` / `r08c_R2`
  in the scratchpad, outside the repo. Agent ids, for the transcript blinding audit:
  - R1 (Q1-Q5): a90c5b9749e4f4bd1, a2de5b115ee75d025, a64f9844ce6b3beb1, a60d2685204f082d2, a01344795ddd28e99
  - R2 (Q1-Q5): a84454ce70dd5d18d, a14ac68367a7b2883, aeac12b86ca91ab05, ab3da0e0c78f95c4a, ab6c9a0a1b25306be
- **2026-09-28, lead: F-07 / H5 is Confirmed with caveats, and reinterpreted.**
  - H5 passes its pre-registered test, but the auditor's cross-pianist control (post-hoc) shows two
    takes by *different* pianists pass too: delta 0.097, against 0.121 for the same pianist.
  - **So the take-consistent part is timing that any two performances of the piece share.** It is not
    a pianist's personal intent. The test was nearly guaranteed to pass once single-take R² > 0.
  - **What F-07 does support:** a pianist's own take-to-take variation is mostly unstructured
    (R² 0.011 vs 0.049 between pianists; paired gap 0.038 [0.030, 0.046]). It therefore can be read
    as noise.
  - **Tier B/D must NOT adopt "take-consistent = intent"** on F-07's evidence. Take-to-take variation
    as a noise estimate is supported, and remains subject to O-01 / BL-16.
- **2026-09-28, lead: R-08c is Confirmed with caveats.**
  - **Headline wording:** "GO by the point-estimate rule; primary 0.750, t [0.588, 0.912]; beats the
    detector by +0.313".
  - **Scope:** LLM phrase boundaries are approved for Classical / galant sonata-type movements in
    simple meters, including unrecognised pieces.
  - DCML label exposure in training is not excluded.
  - **Before LLM boundaries feed PianoLens's target repertoire** (Romantic: Schubert, Chopin, and the
    MAJEPPA practice pieces) or H4/R-09, a Romantic-repertoire test is required (R-08d). The data
    options, in order:
    1. DCML Romantic corpora with phrase labels, if any exist;
    2. phrase labels made after the model's cutoff (OWNER: Henry or a teacher annotates about 5
       passages).
- **2026-09-28, lead: the R-08d design.**
  - **Pool:** a 5-corpus mix (chopin_mazurkas, grieg_lyric_pieces, tchaikovsky_seasons,
    schumann_kinderszenen, liszt_pelerinage). One movement per corpus by seeded draw, stratified by
    rendered size; exclude movements with fewer than 5 phrase ends. This favours breadth over depth.
    A mazurkas-only follow-up is optional.
  - **Pre-cutoff DCML labels are acceptable, with the same caveat as R-08c** (exposure not excluded).
  - Henry's post-cutoff labels (OWNER) remain the gold-standard option. They are not a blocker.
  - Meters: simple meters preferred. Any compound meter is disclosed and analysed separately.
- **2026-09-28, lead: R-08d draw details (after D-13).**
  - Size strata are *within each corpus* (tertiles of rendered characters), not R-08a's absolute
    window. Kinderszenen pieces are all small.
  - **Simple meter only** for the primary draw (Liszt has 8 eligible). Movements that render to
    more than 120k characters are excluded, for annotator context and consistency with R-08a-c.
  - Blind ids only. Stems contain titles.
  - Disclose the "Tempo primo" / "una corda" text rewrites and the 4 hand-unfolded mazurkas
    (`unfold_validated=False`). Those 4 mazurkas are excluded from the draw.
  - Two annotator runs per movement, as in R-08c.
- **2026-09-28, lead: R-08d annotation run.** 10 blind annotators were launched from `r08d_A` / `r08d_B`
  in the scratchpad, outside the repo. Agent ids:
  - A (R1-R5): af78638f3a2b4fa6f, a4bfa3db1fc3ceac5, a3f3d81e34ce7789b, a78c9c4c81d0ef593, a73e4b56f8720e63c
  - B (R1-R5): a02e231e05addd526, ae2c980f51a63ff30, a1e990af1d9d0e583, ac8bb7be350e0ca55, af372660bf2fcce3e
  - The pre-registration dropped the period wording from INSTRUCTIONS, which is accepted.
- **2026-09-28, lead: R-08d is Confirmed with caveats.**
  - **Scope:** "GO by point estimate, fragile. Licensed for Romantic character pieces in simple
    meters at the mean level, with per-piece risk (0.33-0.94) and finer-than-DCML segmentation.
    It beats the detector clearly (+0.35)."
  - Not licensed: per-composer claims, compound meters, long Chopin forms, or transcribed-MIDI input.
  - **Consequence for H4/R-09:** any phrase-based measure fed by LLM boundaries must be robust to
    over-segmentation. For example, compute `concave_excess` on merged adjacent phrases, or require
    nested-boundary robustness. The per-phrase arc measure must be re-validated with LLM boundaries
    (ticket F-05e) before use.
  - **The LLM phrase line (R-08a-d) is closed for now.** A larger follow-up (mazurkas only, more
    movements, compound meters, or post-cutoff OWNER labels) is BL-17.
