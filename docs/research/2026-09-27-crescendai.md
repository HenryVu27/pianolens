# CrescendAI deep dive (L-02)

Checked 2026-09-27 by `lit-scout`. Sources opened:

- Paper: Jai Dhiman, "Audio Foundation Models Outperform Symbolic Representations for Piano
  Performance Evaluation", arXiv:2601.19029 **v1 only** (26 Jan 2026), 6 pages, independent
  researcher, no venue. The repo's `model/README.md` calls it an "ISMIR 2026 submission"; I found
  no acceptance record. [V]
- Repo: https://github.com/Jai-Dhiman/crescendai at HEAD `b9d81c4` (2026-08-16) and at the
  paper-era commit `d8b603fd` (2026-01-26, "updated readme, addded paper"), which holds the
  notebooks and result JSONs behind the paper's tables. [V]
- PercePiano paper (Park et al., Sci. Rep. 14:23002, 2024), https://pmc.ncbi.nlm.nih.gov/articles/PMC11450231/,
  and the PercePiano code in `data/raw/percepiano`. [V]

## 1. Bottom line

1. **The 0.537 vs 0.347 comparison does not support "audio beats symbolic" as a statement about
   modality.** It shows that a frozen, large pretrained audio encoder plus an MLP beats a small
   symbolic network trained from scratch on about 750 examples per fold. PercePiano audio is a
   deterministic rendering of the MIDI, so the audio contains no performance information that the
   MIDI lacks. The author says as much in section 6.3. The fair comparison is pretrained against
   pretrained, or strong features against strong features. Neither was run for the paper.
2. **The paper's split is leave-passage-out, not leave-piece-out.** It uses PercePiano's own
   "composition" folds. A held-out unit is one 4/8/16-bar passage, and all its performers go
   together. Other passages of the same movement stay in training: Schubert D960 mv2 and mv3 are in
   all four folds. By our hard rule 1 this is not a leave-piece-out result.
3. **Several reporting problems** (all checked against the repo's own result files, section 5):
   - The headline 0.537 averages **3 of 4 folds**.
   - Its "95% CI [0.465, 0.575]" is the spread of a *different* experiment, the cross-soundfont
     run, which used a single fold.
   - The p < 10^-25 test compared **MERT**, not MuQ, with the symbolic model.
   - The per-dimension figure averages 0.601, not 0.537.
   - Model selection used the evaluation fold, with no inner validation split.
   - The paper describes PercePiano's raters and rendering wrongly.
4. **The later "fold-leak fix" in the repo made the split worse, not better.** In March 2026 the
   author replaced the paper's folds with "clean piece-stratified" folds and declared all earlier
   numbers invalid. The new folds group by *performer recording*, because the filename tokens were
   read in the wrong order. So every passage in the new validation folds also appears in training,
   played by other performers. The new folds also drop all Beethoven segments (964 of 1,202 kept).
   Every post-March CrescendAI number (79.85% pairwise, R² 0.336, the Aria vs MuQ probe) sits on
   these folds. See section 4.
5. **What is released:**
   - Code under CC BY-NC 4.0.
   - The paper-era fold file and result JSONs are in git history.
   - **I found no public weights**, even though the abstract says "I release ... pretrained
     models". The serving loader reads fold checkpoints from a local or private directory, and
     Hugging Face has no models under the author's names I tried.
   - The Pianoteq renders are gone. The repo's `docs/model/01-data.md` says "the original Pianoteq
     audio is gone".
6. **Product:** crescend.ai is a live practice-companion web app (iOS app in the repo). By
   2026-08 the MuQ/Aria training program was closed. The repo now focuses on a benchmark-first
   "teacher" pipeline (issue #139) and a MIREX 2026 Track A difficulty entry that uses the
   MoonBeam-839M symbolic encoder.

For PianoLens: H3 is untouched by this paper and remains open. R-03 should reproduce the
paper-era setup exactly, which is feasible (section 6). It should then add the comparison the
paper lacks: leave-work-out and within-passage metrics, and pretrained symbolic encoders and
engineered features on the same folds.

## 2. What the paper did

| Item | Paper text | What the code shows |
|---|---|---|
| Task | Regress the 19 PercePiano mean labels, R² averaged over dimensions | Same. Labels file `label_2round_mean_reg_19_with0_rm_highstd0.json` |
| Audio | "rendered via Pianoteq", 6 presets as augmentation | Main ablations (layer, pooling, fold method) used **Salamander** renders. Pianoteq ensemble only for A2/B-series. Presets: HB Steinway D, YC5 Vintage, K2 Basic, NY Steinway D Honky-Tonk, NY Steinway D Worn Out, U4 Small |
| Encoder | MuQ, layers 9-12 **concatenated** to 4096-d | Hidden states 9-12 **averaged** to 1024-d (`torch.stack(...).mean(0)`), truncated to 1000 frames (`max_frames`; corrected 2026-09-27 by R-03 from the code at d8b603fd) |
| Pooling | mean pooling | `pooling_stats: 'mean_std'` in the config the main runs use |
| Head | 2-layer MLP, hidden 512, dropout 0.3, MSE, Adam 1e-4, early stop patience 15 | hidden 512, dropout 0.2, lr 1e-4, wd 1e-5 |
| Split | "4-fold piece-split CV: all segments from a given piece appear in the same fold" | PercePiano composition folds (`audio_fold_assignments.json`): 4 folds of 263/234/255/269 segments plus a 181-segment test set that the paper never reports. The fold unit is the passage (details in section 4) |
| n | 1,202 segments | `n_samples: 1005` in the A1 results (CV folds only, minus missing audio) |
| Model selection | early stopping on validation R² | The checkpoint with the best validation R² is reported **on that same fold**. No inner split, so the numbers are optimistically biased. The symbolic reproduction was selected the same way |

### Symbolic baseline (how strong is it?)

- The baseline is PercePiano's own model, retrained by Dhiman with PercePiano's code: VirtuosoNet
  features into the hierarchical attention network (HAN), config
  `han_measnote_nomask_bigger256.yml`.
  - Folds from `m2pf_dataset_compositionfold.py`, 100 epochs, best epoch kept.
  - Result: R² 0.347 (bootstrap CI 0.315-0.375).
- PercePiano reports 0.397 for this model on its held-out piece-split *test set*. Dhiman reads
  that as "the best single fold", which is wrong: the PercePiano paper reports it on the test set.
- **Strength.** It is the published state of the art for symbolic input on this dataset. It is not
  a straw man in that sense. But it is weak for this comparison:
  - It is trained from scratch on about 750 segments per fold.
  - It has no pretraining.
  - Its per-dimension R² is uneven: timing 0.12, pedal clarity 0.24, timbre brightness 0.24
    (`A4_dimension_breakdown.json`).
- No trivial baseline appears anywhere. There is no passage-mean predictor and no linear model on
  simple features.
- No pretrained symbolic encoder was compared for the paper. After the paper, the repo ran a
  frozen Aria linear probe against a frozen MuQ linear probe: 59.6% vs 62.2% pairwise, on the
  flawed March folds. That gap is far smaller than the paper's headline gap.

## 3. Headline numbers as the repo records them

All numbers are from paper-era result JSONs at `d8b603fd:model/data/results/`. Not measured here.

| Experiment | R² | Note |
|---|---|---|
| A1a MuQ L9-12, Salamander, passage folds | 0.536, pooled R² over all four folds' out-of-fold predictions, not the mean of the fold scores (corrected by R-03) (folds 0.51/0.54/0.48/0.58) | This, not the Pianoteq run, is the clean 4-fold number |
| A1b same, performer folds | 0.536 | |
| A1c same, "stratified" folds | 0.523 | |
| A2 MuQ + Pianoteq 6-preset ensemble | 0.537 | `status: completed_partial`, folds 0-2 only, "Manually marked complete with 3/4 folds" |
| B2 cross-soundfont (train on 5 presets, test on the 6th) | 0.534 ± 0.075 | Fold 3 only. Honky-Tonk held out: 0.368. Its bootstrap CI [0.465, 0.575] is what the abstract attaches to 0.537 |
| MERT L7-12 | 0.487 (CI 0.460-0.510) | |
| Symbolic HAN reproduction | 0.347 (CI 0.315-0.375) | |
| Paired t-test p = 2.1e-25, Cohen's d = 0.31 | | From `aligned_fusion/S1_paired_tests.json`, which compares the **MERT** model's per-sample MSE with the symbolic model's. Samples within a passage are not independent, so the p-value is overstated even for MERT |
| Error correlation audio vs symbolic | r = 0.738 | |
| Fusion MuQ + symbolic | 0.524 | Fusion weights were tuned per dimension, apparently on the same predictions |

Per-dimension R² (A4; MuQ vs symbolic):

- **Largest gaps:** timing 0.49 vs 0.12; timbre brightness 0.62 vs 0.24; dynamic range 0.69 vs
  0.39; pedal clarity 0.52 vs 0.24.
- **Smallest gap:** space 0.65 vs 0.52.
- These MuQ values average 0.600, which is inconsistent with the 0.533/0.537 headline. The paper
  prints both.

Other claims in the paper:

- **PSyllabus difficulty ρ = 0.623 (n = 508):** a correlation between predicted "quality"
  dimensions and piece difficulty. It shows the model responds to piece content, not that it
  measures performance quality.
- **ASAP/MAESTRO multi-performer analysis:** the mean within-piece standard deviation across
  performers is 0.020. The paper concedes that the model "captures piece characteristics more
  strongly than performer-specific expression".
- **Later negative result in the repo** (2026-03-18, `docs/model/00-research-timeline.md`): the
  A1-Max model showed "zero skill-level discrimination across 5 human-labeled skill buckets".
  Beginner 0.558 vs professional 0.565.
- **Chopin 2021 competition** (repo `03-encoders.md`, 11 performers): the per-dimension
  correlation with placement for *dynamics* is ρ = -0.917. The authors read this as the model
  measuring "amount", not "appropriateness".

## 4. Splits: the filename trap

PercePiano filenames are `<work>_<N>bars_<A>_<B>`.

- **PercePiano's README says** A is the segment number and B is the player.
- **PercePiano's code** (`get_performer_id` in `m2pf_dataset_compositionfold.py`) **and the data
  itself say the opposite.** A is the player; B is the segment.
  - Every Beethoven variation has 14 distinct A values, which match `BEETHOVEN_PERFORMER_IDS`
    plus `Score`, and exactly one B value per variation.
  - Schubert D935 has 9 distinct A values (performers) and 13 B values (segments).

I recomputed which groups straddle folds, with a throwaway script in the lit-scout session. It is
not committed; it takes about 20 lines to redo.

| Fold file | Groups by passage (work, bars, B): straddling folds | Groups by performer recording (work, bars, A): straddling folds | Works in >1 fold |
|---|---|---|---|
| Paper-era `audio_fold_assignments.json` (= PercePiano composition folds) | 0 of 83 | 61 of 285 | 3 of 19 (D960 mv2, D960 mv3, D935) |
| March 2026 "clean" `folds.json` | **82 of 82** | 0 of 61 | 3 of 3 |

So:

- The paper's folds are honest leave-passage-out folds.
- The March 2026 folds are leave-performer-recording-out folds, with every validation passage
  present in training. That is a within-piece split.
- Neither is leave-work-out.

PercePiano has only four works (Schubert D960 mv2, D960 mv3, D935 no.3, Beethoven WoO 80), so a
4-fold leave-work-out split is natural. Nobody has reported it.

**Why this matters for H3.** I measured how much label variance passage identity explains, from
`data/raw/percepiano` (1,202 segments, 99 passages; passage means fitted in-sample, so these are
inflated by roughly 98/1201 ≈ 0.08):

- Across the 19 dimensions, passage identity explains 0.41 of label variance on average. The range
  runs from 0.22 (timing) to 0.76 (timbre brightness) and 0.77 (mood valence).
- Work identity alone explains 0.12. Performer identity explains 0.23.

So a large part of what "R² on PercePiano" rewards under a passage split is predicting how an
unseen *passage* tends to be rated: its register, mood, tempo. That is content description, which
audio foundation models are good at, and not performance quality.

I checked whether MuQ's advantage over symbolic tracks this passage share across dimensions. It
does not: Spearman -0.05 over 19 dimensions. So I cannot claim the passage effect *explains* the
gap. I can only say that R² on this dataset mixes the two things and that a within-passage metric
is needed.

## 5. Does 0.537 vs 0.347 support "audio beats symbolic"?

No, for four reasons.

1. **No information advantage.** The audio is a deterministic function of the MIDI. The paper
   concedes this in 6.1 and 6.3. Any gain is inductive bias from about 160k hours of audio
   pretraining. The claim that holds is "pretrained encoder > from-scratch model with about 750
   examples per fold".
2. **Unmatched capacity and pretraining.** The paper compares a frozen MuQ-large plus MLP against
   a from-scratch HAN. The matched test (a pretrained symbolic encoder such as Aria or MoonBeam,
   or engineered features, on the same folds) was not run for the paper. The later frozen-probe
   comparison in the repo is close: 59.6% vs 62.2% pairwise.
3. **The renderer differs from what raters heard.** PercePiano raters heard Logic Pro's "Yamaha
   Grand Piano". CrescendAI used Salamander and Pianoteq.
   - This is not a leak.
   - It does mean timbre dimensions (brightness, depth) are rated on a sound the model never
     hears.
   - The Honky-Tonk hold-out drops to 0.37, so predictions depend on the renderer.
4. **Statistics.**
   - The headline number uses 3 of 4 folds, and its CI belongs to a different experiment.
   - The significance test is for MERT, not MuQ, and treats about 1,000 non-independent segments
     as independent.
   - The evaluation fold doubles as the early-stopping and checkpoint-selection set, for both
     models.
   - The per-dimension table and the headline disagree (0.600 vs 0.537).

What the paper does support:

- On PercePiano passage-held-out folds, frozen MuQ plus a small head reaches R² of about 0.53 to
  0.54 with a free piano (Salamander).
- That is well above PercePiano's own symbolic HAN.
- It is a solid, reproducible **target number for R-03**.

## 6. What R-03 needs to reproduce the number

1. **Data:**
   - PercePiano MIDI and labels (already in `data/raw/percepiano`).
   - Labels: `label_2round_mean_reg_19_with0_rm_highstd0.json`, first 19 values. The 20th value
     is a player id.
2. **Folds:**
   - Copy `model/data/cache/audio_fold_assignments.json` from CrescendAI commit `d8b603fd`, or
     regenerate with PercePiano's `m2pf_dataset_compositionfold.py` (`random.seed(42)`).
   - Keep the 181-segment `test` set separate, and report it too. The paper ignored it.
   - I have a copy in the scratchpad only. The data-engineer should fetch it properly.
3. **Render:** Salamander Grand Piano. This matches A1a (0.536), which needs no Pianoteq licence.
   - Pianoteq is optional and needs a paid licence (OWNER).
   - Logic Pro's Yamaha Grand, which the raters actually heard, would need a Mac with Logic Pro
     and its stock instrument. If Henry has Logic, this is the best-matched render.
   - Render at 24 kHz mono.
4. **Features:**
   - `OpenMuQ/MuQ-large-msd-iter`, fp32, `output_hidden_states=True`.
   - Average hidden_states[9:13] (transformer layers 9-12).
   - Truncate to 1000 frames (not 300; corrected by R-03).
   - Mean+std pooling.
5. **Head:** a 2-layer MLP (hidden 512, dropout 0.2), MSE, Adam 1e-4, weight decay 1e-5, batch
   64, early stopping with patience 15 on validation R².
6. **Evaluation:** report both of these.
   - (a) The paper protocol: best checkpoint on the validation fold, which reproduces 0.536.
   - (b) An honest protocol: an inner validation split for early stopping, then scoring on the
     outer fold.
   - Then add leave-work-out (4 folds), leave-performer-out, and a **within-passage** metric.
     Within-passage means R² or Spearman after subtracting passage means, or pairwise accuracy
     among performers of the same passage.
   - Add a passage-mean trivial baseline and rater parity.
7. **Compute:** MuQ embedding of about 1,200 clips of 10-30 s each is a small job. It fits MPS
   on the Mac or the 5080. The head trains on CPU.

## 7. Where PianoLens differs

- **Evaluation.** We hold out works and report within-passage (performer-level) accuracy.
  CrescendAI never measured whether its scores separate performers of the same passage. Its own
  ASAP analysis and skill-bucket test suggest they barely do.
- **Baselines.** We compare against pretrained symbolic encoders and engineered, score-aligned
  features, with a trivial baseline and rater parity in the same table.
- **Score conditioning.** CrescendAI found dynamics inverted against competition placement. It
  planned to fix this by conditioning on the score (Aria delta) but never evaluated that. Our
  tier C/D features are score-relative from the start.
- **Product overlap.** CrescendAI is the closest shipped prior art: MuQ scores, Transkun
  transcription, score following and an LLM teacher. It is non-commercial (CC BY-NC 4.0), so we
  can read and cite it but not reuse its code in a commercial product.

## 8. Could not verify

- Whether Hugging Face hosts CrescendAI weights under a name I did not try. There are none under
  `Jai-Dhiman`, `jai-dhiman`, `JaiDhiman`, `jaidhiman` or `jdhiman`, and none in a "crescend"
  search.
- Whether crescend.ai charges or is open to the public. The landing page has a "Start Practicing"
  link; I did not sign up.
- The source of the 0.601 per-dimension average in `A4_dimension_breakdown.json`. The notebook
  that wrote it (`02_muq_fusion_experiments.ipynb`) was not traced cell by cell.


## Reproduction result (R-03, 2026-09-27, Provisional)

- We got 0.509 under their protocol, against their 0.536.
- Under leave-work-out the pooled R² is -0.087.
- Details: `experiments/2026-09-27-R-03-muq-percepiano/`.
