# Expression models for R-06 (survey)

Checked 2026-09-27 by `lit-scout`. For each model I opened the repo (cloned at HEAD), the licence
file and the Hugging Face model API. Parameter counts are from the Hugging Face safetensors
metadata, not from the papers. [V] means I opened the primary source.

## 1. Bottom line

- **Best fit for R-07: SyMuPe EncDec-base.**
  - It is the successor to ScorePerformer, from the same author as PianoCoRe.
  - It is a 25M-parameter encoder-decoder that outputs categorical distributions over
    per-note performance tokens given the score. So log p(performance | score) is a teacher-forced
    forward pass.
  - Weights are on Hugging Face under CC BY-NC-SA 4.0, which matches our research-only data.
  - It shares tokenisation and alignment tooling (RAScoP, built on parangonar) with PianoCoRe, our
    Phase 5 training data.
  - Fine-tuning it on PianoCoRe-A is small on a 16 GB card.
- **Runner-up: Pianist Transformer.**
  - ICML 2026, Apache-2.0 code and weights, 136M parameters.
  - It is also a seq2seq model with per-note tokens, so it can compute likelihoods the same way.
  - Its strengths are scale (10B-token pretraining) and a permissive licence.
  - Its weaknesses: only ASAP for supervised training, and it needs Nakamura's aligner to
    fine-tune.
  - Worth a head-to-head likelihood test against SyMuPe on held-out (n)ASAP pieces.
- **Not suitable as the likelihood model:**
  - **DExter** (diffusion): a likelihood only via an ELBO, and no published weights I could find.
  - **VirtuosoNet**: no licence, and a deterministic/VAE design.
  - **Aria**: not score-conditioned. It works as a pretrained encoder or as an unconditional
    "is this a plausible piano performance" prior.
- **Keep Basis Mixer** (GPL-3.0) as the interpretable baseline. Train our own linear or small
  models on basis functions. This is exactly the H4 "structural coherence" regression.
- **Every model trained on these corpora carries a non-commercial licence in practice,** whatever
  the code licence says:
  - Pianist Transformer pretrains on Aria-MIDI (CC BY-NC-SA) and fine-tunes on ASAP (CC BY-NC-SA).
  - Aria's weights are Apache-2.0, but its training data is CC BY-NC-SA.

## 2. Comparison table

| Model | Code / licence | Weights | Size | Training data | Likelihood of a given performance given a score? | 16 GB 5080 fine-tune |
|---|---|---|---|---|---|---|
| **SyMuPe** (PianoFlow, EncDec, MLM) (Borovik, Gavrilev, Viro, ACM MM 2025, Outstanding Paper) | github.com/ilya16/SyMuPe, Apache-2.0 code; `pip install symupe` [V] | HF `SyMuPe/PianoFlow-base`, `EncDec-base`, `MLM-base`, CC BY-NC-SA 4.0 [V] | 24.5M / 25.1M / 24.6M [V] | PERiScoPe v1.0: 35,815 score-performance pairs, 1,163 scores, 66 composers, about 2,848 h (from (n)ASAP, ATEPP, web) [V] | **EncDec: yes, exact** (causal LM over per-note tokens: velocity, time shift, duration, sustained duration). MLM: pseudo-likelihood. PianoFlow: flow matching, likelihood only via ODE, expensive | Yes, easily (25M params) |
| **Pianist Transformer** (You et al., ICML 2026; arXiv 2512.02652 v2, 2026-06-25) | github.com/yhj137/PianistTransformer, Apache-2.0 [V] | HF `yhj137/pianist-transformer-base` (pretrained) and `-rendering` (fine-tuned), Apache-2.0 [V] | 135.7M [V] (T5-Gemma-style, 10-layer encoder with 8x note compression, 2-layer decoder per the paper) | Pretraining on 10B tokens: Aria-MIDI (quality > 0.95), GiantMIDI, PDMX, POP909, Pianist8. SFT on ASAP only, with 10% of scores held out; aligned with Nakamura's HMM aligner [V] | **Yes**: seq2seq, 8 tokens per note (pitch, IOI, velocity, duration, 4 pedal samples), teacher-forced cross-entropy. Tempo normalised to 120 BPM in the tokeniser | Yes. Tested with torch 2.7.1 and a cu128 wheel, which supports Blackwell. The authors trained on 4x A800 / recommend 4x 4090; a 136M bf16 fine-tune fits 16 GB with a smaller batch |
| **ScorePerformer** (Borovik and Viro, ISMIR 2023) | github.com/ilya16/ScorePerformer, CC BY-NC-SA 4.0 [V]. Alignment and preprocessing code "deliberately not made available" | Only through the Colab demo; no Hugging Face repo found | Not stated | Author's own aligned set (the PERiScoPe predecessor) | Partly: a transformer plus hierarchical MMD-VAE style encoder; token likelihood given a style latent | Yes, but **superseded by SyMuPe**; skip |
| **DExter** (Zhang, Chowdhury, Cancino-Chacón, Liang, Dixon, Widmer; arXiv 2406.14850) | github.com/anusfoil/DExter, MIT [V]; last push 2026-05 | **Not found.** The README's Zenodo weights link is commented out; the Colab may host one [U] | Not stated; checkpoint names suggest a 15-layer, 512-channel denoiser | ATEPP (parangonar-aligned), ASAP, Vienna 4x22; partitura performance codec | Only an ELBO / denoising-loss proxy (diffusion) | Probably yes (small), but you would train from scratch |
| **VirtuosoNet** (Jeong et al., ISMIR 2019 / ICML 2019) | github.com/jdasam/virtuosoNet, **no licence file** (GitHub reports none) [V] | HF `dasaem/virtuosonet` (HAN+GRU checkpoint, 180 MB), no licence in the card [V] | Not stated | The authors' Yamaha e-Competition-derived aligned set; 16 composers listed | Not natively. Deterministic output plus a performance-style latent; would need a Gaussian head | Yes (small). But no licence means all rights reserved |
| **Basis Mixer** (Cancino-Chacón, Grachten et al.) | github.com/CPJKU/basismixer, GPL-3.0 [V]; last push 2024-04 | Demo model on Vienna 4x22 only ("not intended to represent the state-of-the-art") [V] | Tiny (linear / small NN on basis functions) | Train it yourself | Yes if the output model is Gaussian (linear-Gaussian basis model) | CPU is enough |
| **Aria** (Bradshaw et al., ISMIR 2025) | github.com/EleutherAI/aria, Apache-2.0 [V] | HF `loubb/aria-medium-base` 658.5M, `aria-medium-embedding` 632.1M, Apache-2.0 [V] | About 650M (LLaMA 3.2 1B-style architecture; **not 1B parameters**) | Aria-MIDI, about 60k h of transcribed solo piano | **Not score-conditioned.** Unconditional performance log-likelihood only, or embeddings | Frozen inference fits. LoRA fine-tuning fits in bf16; a full fine-tune does not |

Related, not an expression renderer:

- **MAJEPPA** (ISMIR 2026): Aria-medium plus LoRA trained with a joint-embedding (JEPA) plus
  contrastive objective across six expertise levels.
  - Weights: HF `anusfoil/majeppa`, Apache-2.0, 2.9 GB [V].
  - It could serve as a skill-aware embedding baseline for R-04 and H4.
- **RenCon 2025** (arXiv 2605.02059) [V], relevant to model choice:
  - Rule-based Director Musices ranked 1st in the preliminary round (4.33/5).
  - VirtuosoNet won the live round (3.62/5).
  - The human reference scored 4.40/5 and was identified by 75% of 48 respondents.
  - Pianist Transformer and SyMuPe did not enter.

## 3. What "score the likelihood of a performance" needs, and the traps

- **Alignment first.** Every candidate expects a note-aligned score and performance. Wrong,
  missing and extra notes must be handled before scoring:
  - Pianist Transformer interpolates small gaps and drops large unaligned blocks.
  - RAScoP fills "holes".
  - So likelihood scoring is only meaningful after our tier-A correctness pass. It should be
    reported on matched notes only, with the error count reported separately.
- **Normalisation.**
  - Pianist Transformer normalises tempo to 120 BPM and tokenises IOI.
  - SyMuPe uses time shift and duration tokens, with velocity and tempo conditioning tokens.
  - A likelihood is therefore partly a function of these choices: global tempo is conditioned
    away in SyMuPe and not in Pianist Transformer.
  - Report per-note and per-feature log-likelihoods (timing, velocity, articulation, pedal), not
    one total.
- **Typicality is not quality.**
  - Repp 1997 found that the average performance is rated high in quality but low in
    individuality.
  - A likelihood under an expert model rewards the typical. H7 in the plan exists to test
    whether it rewards more than that.
- **Data overlap.** Pianist Transformer's SFT and test pieces come from ASAP. PERiScoPe and
  PianoCoRe also include (n)ASAP. Any held-out evaluation must de-duplicate pieces across these
  corpora, or it will leak.

## 4. Recommendation for R-06 and R-07

1. Start R-07 with **SyMuPe EncDec-base**, frozen. Compute per-note log p(perf | score) on (n)ASAP
   pieces held out from PERiScoPe. Check that experts score higher than perturbed versions (S-01
   degradations) and than amateur takes.
2. Run **Pianist Transformer** (`-rendering`) through the same harness. Pick the model whose
   likelihood separates degradations best per feature.
3. Fine-tune the winner on PianoCoRe-A* with a piece-disjoint split. Both fit on the 5080.
4. Keep a **Basis Mixer-style linear-Gaussian model** as the interpretable baseline in the same
   table.

## 5. Could not verify

- DExter weights (the Colab notebook was not opened).
- ScorePerformer weights location (Colab only).
- VirtuosoNet's training corpus details for the RenCon checkpoint.
- Exact VRAM for a Pianist Transformer fine-tune at sequence length 4096. This is an estimate from
  parameter count, not a measurement.
