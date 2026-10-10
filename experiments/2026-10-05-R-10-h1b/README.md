# H1b: is the shared part of expert expression predictable from the score? (fresh pieces)
Ticket: R-10    Hypothesis: H1b    Status: Provisional (pre-registered 2026-10-05; job prepared, not run)

Pre-registered 2026-10-05, before any model output on the fresh pieces existed. The model, the
primary statistic and its thresholds, and the fresh-piece requirement are fixed by DECISIONS
2026-10-05 ("R-07 after audit"); this file fixes everything else. The run waits for Henry's RTX
5080 box (job in `job/`). Everything below the line `## Run record` is added later; the hash in
`artifacts/prereg_sha256.txt` covers the lines above it.

What had been seen when this was written:
- all R-06 and R-07 results and the R-07 audit (`../2026-09-28-R-07-symupe-finetune/AUDIT.md`),
  including R-07's R10u and R10s H1b preview tables (development data, see Baselines);
- on the **fresh pieces, expert renditions only** (no model, no baseline prediction): the
  selection counts, rendition counts, curve reliability, the K-matched expert oracles, the
  parallel-analysis k, and the 16-expert captured share and its random floor (section
  "Pre-registration checks"). These are properties of the target, not of any predictor;
- on the R10u development set, expert renditions only: the same quantities, used for the
  reachability simulation;
- the pipeline dry run on 2 R10u development pieces (frozen SyMuPe and Pianist Transformer
  samples, ridge predictions; section "Dry run"). Those numbers are pipeline checks. The
  thresholds were written before it. One choice was made after it: the dry run exposed that
  SyMuPe ignores the `lm_top_p` argument (Method, "Sampling trap"), and only then was the
  top-p of the primary arm fixed at 0.95 (Method, "Which samples decide"). That choice used the
  sample spread seen on the two development pieces, not any R²c.

## Question

1. **H1b-consensus (primary).** Given only the score, does frozen SyMuPe EncDec-base predict the
   across-performer mean expression curve (velocity; log IOI ratio) of PianoCoRe pieces it has
   never seen, as measured by centered R² of its mean curve (16 samples) against the expert
   mean curve?
2. **H1b-axes (secondary).** Do the model's samples span the directions in which experts differ
   from each other (the shared components), as well as 16 held-out real experts do?
3. **Exploratory.** Given part of one performance, do the shared components predict the rest of
   it better than the performer's mean deviation (the individual part)? Does the model's sample
   basis do as well as the experts' basis?

## Falsified if

The plan's H1b row: "a score-conditioned expression model explains at least 50% of the held-out
variance in the shared expert components ... on unseen pieces"; falsified if "explains 20% or
less on unseen pieces". DECISIONS 2026-10-05 fixes the primary statistic (mean-curve R²c, R-06
formula, per target) and applies these thresholds to it as written. Refined here (fixed before
results):

**Primary: H1b-consensus.** Per target t in {velocity, log IOI}: the median over the primary
pieces of the per-piece R²c of frozen SyMuPe (arm `frozen_p95`: K = 16 samples at top-p 0.95),
with a 95% CI from a work-cluster bootstrap (2,000 resamples, seed 0).
- **consistent with H1b** for t: median >= 0.50 **and** CI lower bound > 0.20;
- **falsified** for t (at or below the H1b falsification level): median <= 0.20 **and** CI upper
  bound < 0.50;
- **inconclusive** for t otherwise.
- Joint reading: both targets consistent -> "H1b-consensus consistent"; both falsified ->
  "H1b-consensus falsified"; otherwise "mixed", reported per target (e.g. "velocity consistent,
  timing falsified"). The point decides the side; the CI only has to exclude the opposite
  threshold. With 59 pieces the CI half-width is about 0.10-0.13 (reachability below), so all
  three readings are reachable.
- Scope of the verdict: it is about frozen SyMuPe EncDec-base, the model R-06 / R-07 selected
  (DECISIONS 2026-10-05). "Falsified" means the best available score-conditioned model does not
  reach the H1b level on unseen pieces, not that no model could.
- Reported next to it, not deciding: the K-matched expert oracle (analytic for all pieces;
  empirical for pieces with n >= 36), the ratios R²c / oracle, and the Spearman-Brown
  reliability of the expert mean curve.

**Secondary: H1b-axes** (pieces with n >= 36 and k > 0). Statistic: median over pieces of the
per-piece ratio cap_model / cap_oracle (definitions in Method) for arm `frozen_p100` (K = 16
samples at top-p 1.0, DECISIONS 2026-10-05), work-cluster bootstrap CI.
Thresholds, set after the reachability check below:
- **consistent**: median ratio >= 0.80 **and** CI lower bound > 0.40;
- **at the floor**: median ratio <= 0.40 **and** CI upper bound < 0.80;
- **inconclusive** otherwise.
- Meaning of the scale (measured on the fresh pieces, expert data): K' held-out experts reach,
  relative to 16, 0.09 (K' = 2), 0.24 (4), 0.56 (8), 0.80 (12). So 0.80 = "the model's 16
  samples span the shared axes as well as about 12 real experts"; 0.40 = "as well as about 6";
  a random 15-dimensional subspace scores 0.064.
- H1b-axes does not change the H1b verdict; it is reported as a separate finding. If it is
  consistent while H1b-consensus is falsified (or the reverse), that is reported as such.

**Secondary, not deciding.** Frozen SyMuPe minus the score-feature ridge, per target, median of
per-piece paired differences in R²c with a work-cluster bootstrap CI: "beats the score-only
baseline" if the CI is above 0, "worse" if below, else "no detectable difference".

**Exploratory (no thresholds).** Conditional component prediction (Method); per capture model;
per composer and leave-one-composer-out; each statistic on the other arm's samples (primary on
top-p 1.0, axes on top-p 0.95); Pianist Transformer; disattenuated R²c; Pearson r of the
curves.

## Data

- **PianoCoRe v1.0** (Zenodo 19186016; D-03; CC BY-NC-SA 4.0; research only): `metadata.csv`
  sha256 `b26abcd1...5a70`, `PianoCoRe-1.0-refined.zip` `68f1b182...ef0f`, tier A, loaded with
  `pianolens.data.pianocore`. Almost all renditions are audio transcriptions.
- **R-07 split** `../2026-09-28-R-07-symupe-finetune/split/pieces.csv` (sha256 `3341bfa5...6b86`):
  PERiScoPe v1.0 pairing (`n_periscope_paired`, `periscope_possible`), R-07 roles and work keys,
  R-02 membership.

**Fresh pieces** (`select_pieces.py`, run once on the Mac; output committed in `pieces/`):

| Step | Rule | Pieces left |
|---|---|---|
| 1 | Tier A, source not ASAP, at least 20 performances on the majority refined score (20 = R-07 (b) minimum) | 1,023 |
| 2 | Unseen by SyMuPe pretraining as R-07 determined it: `n_periscope_paired == 0` and not `periscope_possible` | 158 |
| 3 | No work-mate (same R-07 work key) paired or possibly paired in PERiScoPe (16 dropped, `pieces/dropped_workmate.csv`) | 142 |
| 4 | No catalogue alias (`expression_split.alias_conflicts`) of any PERiScoPe-paired piece or any R-06 / R-07 evaluation piece (15 dropped, `pieces/dropped_alias.csv`) | 127 |
| 5 | Not evaluated in R-06 / R-07 (roles P, V, A, R10u, R10s), not quarantined, not an R-02 piece (62 dropped) | **65** |

- 65 pieces in 63 works by 28 composers (`pieces/fresh_pieces.csv`, sha256 `8303382c...37ca`,
  `pieces/summary.json`). All qualifying pieces are used; the seeded part (seed 20261005) is
  only the order of the list. In R-07 they were train (62) or validation (3) pieces. That
  matters only for R-07's fine-tuned arms, which R-10 does not use: the frozen weights never saw
  them.
- **Renditions** (`job/build_set.py`, R-07's item rules): the piece's majority refined score
  (by metadata) first, then at most 50 performances per piece (R-07's per-piece seed),
  interchange items with matched share >= 0.8 (80 dropped), first 3,000 distinct score notes,
  at least 16 notes per rendition. Result: 1,895 renditions of 65 pieces (digest
  `pieces/fresh_digest.json`; the box rebuild must match it).
  - R-07 drew the cap over all scores and took the majority score afterwards, which can leave
    fewer than 50 majority-score renditions; R-10 restricts to the majority score first (R-02
    rule).
- **Primary set: the 59 pieces with at least 20 usable renditions** (57 works; 1,788
  renditions; median 28 per piece, median 445 score onsets). The other 6 (14-19 renditions) are
  generated but not analysed.
  - Empirical oracle subset: 15 pieces with n >= 36 (16 held out + at least 20 reference;
    R-07 audit B2).
  - H1b-axes subset: 12 of those 15 with k > 0 (12 works).
- **Capture model** of the primary renditions: Aria-AMT 1,647, Transkun V2 80, ATEPP 49,
  ByteDance (GiantMIDI) 12. No piece has 10 or more renditions from any source other than
  Aria-AMT, so per-source results are: Aria-AMT-only expert curves (piece level, 59 pieces),
  and a rendition-level table by source (Method).
- **Development sets** (disclosed; not confirmation data): R10u (R-07 role R10u, 91 pieces with
  items, `job/dev_pieces_r10u.csv`) and R10s (R-07 role R10s, `job/dev_pieces_r10s.csv`), built
  with the same rules. They train the ridge baseline and carry the development numbers.

## Splits

- **Leave-piece-out by construction.** The frozen model has never seen these pieces (steps 2-5).
  The ridge baseline is trained on the R10u and R10s development pieces only, which share no
  piece, work or catalogue alias with the fresh set. Nothing is tuned on the fresh pieces: there
  is no hyperparameter in the model arm, and the ridge alpha is chosen by GroupKFold (by work)
  inside its training pieces.
- Leave-performer-out does not apply: no predictor is fitted to performers.
- Bootstrap unit: the R-07 work key (57 works for 59 pieces; Bach preludes and fugues of one
  number share a work).
- Seeds: selection order 20261005; per-piece cap 20260928 + crc32(piece) mod 100,003 (R-07);
  generation seed 0 per item (R-06 / R-07); oracle draws 1 + crc32(piece) mod 1,000,003; parallel
  analysis 0; bootstrap 0.

## Baselines

- **Flat curve** (predict the performance is deadpan): R²c = 0 by construction (both curves
  centered; a constant prediction leaves the full variance). Stated, not computed.
- **Score-feature ridge** (`job/train_ridge.py`): the R-06 baseline features (pitch, chord role
  and size, durations, IOIs, metrical phase, position, local density and register), computed on
  the score only, trained on the R10u + R10s development pieces' mean curves; alpha per target by
  5-fold GroupKFold by work. This is the "mean curve of other pieces mapped by score position
  features" baseline.
- **Development numbers (R10u; disclosed, not confirmation):**
  - R-07 as committed (`results/R10u/h1b.csv`, frozen SyMuPe, top-p 0.95, K = 16, 74 unseen
    pieces): median R²c velocity **0.328**, log IOI **0.127**. The log IOI value uses R-07's
    formula, which does not center the predicted curve (R-07 audit section 4); it is a lower
    bound of the R-06 formula.
  - The job recomputes them with this experiment's code and the R-06 formula from R-07's own
    R10u samples on the box (stage `dev_r07`), and can generate top-p 1.0 samples for R10u
    (optional stage `dev_gen`).
- **Ceiling: the K-matched expert oracle** (no per-rater labels exist, so this is the performer
  analogue of rater parity): what 16 real experts' mean curve scores against the panel's mean
  curve. Measured before registration (expert data only): median analytic oracle velocity
  **0.878** [0.847, 0.902], log IOI **0.882** [0.859, 0.911] (59 pieces); empirical oracle
  (15 pieces) 0.883 / 0.856. Reliability of the expert mean curve 0.960 / 0.963.

## Method

**Model.** Frozen SyMuPe EncDec-base (HF `SyMuPe/EncDec-base` at `1b942f28`, symupe 1.1.0 at
`13cc57d`), the R-06 adapter (`../2026-09-27-R-06-expression-model-h2h/adapters/
symupe_adapter.py`) with the sampling threshold exposed (`job/symupe_gen.py`). Per piece, one
generation item: the union of matched score notes over the renditions (first 3,000), score
tempo = the median conditioning seconds-per-quarter over the piece's renditions, score velocity =
the median conditioning velocity (R-07 generation-item rule). Two sample sets per piece, both
**K = 16, temperature 1, seed 0**: arm `frozen_p95` (top-p 0.95) and arm `frozen_p100` (top-p
1.0).

**Which samples decide.** H1b-consensus is read on `frozen_p95`; H1b-axes on `frozen_p100`
(DECISIONS 2026-10-05: K >= 16, top-p 1.0 for the axes statistic). Each statistic is also
reported on the other arm as a sensitivity analysis. Reasons for 0.95 on the primary: it is the
package's default for this model and the setting of every R-06 / R-07 sample, so the
development numbers and the reachability simulation describe it; the audit's case for top-p 1.0
is about sample diversity, which is the axes statistic; and top-p 1.0 adds tail spread that a
mean of only 16 samples carries into the consensus estimate. On the two dry-run (development)
pieces the per-note s.d. of log IOI across samples was 1.6x larger at top-p 1.0 (0.157 vs 0.096;
0.554 vs 0.349).

**Sampling trap (found in the dry run).** `perform_score(lm_top_p=...)`, which R-06 and R-07
used, is ignored by EncDec-base: the seq2seq generator reads `top_p` (or `mlm_top_p`) and
defaults to 0.95. Every R-06 / R-07 SyMuPe sample was therefore drawn at top-p 0.95, including
R-07's S-TYP reference samples that were registered as top-p 1.0. `job/symupe_gen.py` passes
`top_p` explicitly and refuses to start if the generator would not receive it. Check: with the
fix, top-p 0.95 reproduces the old default samples exactly (maximum difference 0 on both dry-run
pieces); top-p 1.0 differs (per-note velocity s.d. across samples 11.1 vs 8.6 on scarlatti K.
32).

**Curves.** For each rendition and each score onset of the generation item: mean velocity and
log IOI ratio (`expression_io.note_expression`, the rendition's own global tempo). Onsets kept if
observed in at least half of the renditions, for both targets. Velocity curves are centered per
rendition (and per sample). Mean curves are nan-aware means over renditions (experts) or over
the 16 samples (model). This is R-06 `analyze.py` (b).

**Primary statistic (R-06 formula).** Per piece and target, over the onsets where both curves
are finite: mc = m - mean(m), pc = p - mean(p), R²c = 1 - sum((mc - pc)²) / sum(mc²). No refit.
Summary: median over the primary pieces; work-cluster bootstrap CI.

**Oracles.**
- Analytic K-matched oracle (all pieces): the expected R²c of the mean of 16 new exchangeable
  experts against this piece's n-expert mean curve, from the per-onset between-performer variance
  s²_j and count n_j: 1 - sum_j s²_j (1/16 + 1/n_j) / sum_j mc_j². Validated before
  registration against the empirical hold-out oracle at the same target size: median absolute
  difference 0.0045 (velocity) and 0.0090 (log IOI) on the 15 fresh pieces, 0.0032 / 0.0032 on
  79 R10u pieces; correlation 0.989-0.998 (`artifacts/reachability/a_oracle_validation.csv`).
- Empirical oracle (n >= 36): 20 draws of 16 held-out experts; R²c of their mean curve against
  the mean of the other n - 16; averaged over draws. The model is scored against the same
  reference means in the same draws (`r2c_vs_rest`), giving the matched ratio.
- Ratios reported: per-piece R²c / analytic oracle (median), median R²c / median oracle, and the
  matched empirical ratio.
- Disattenuated R²c (descriptive): the model's agreement with the noise-free consensus,
  1 - (SSE - noise) / (SS - noise), noise = sum_j s²_j / n_j.

**H1b-axes (R-07 audit script B2, unchanged).**
- k = number of shared components of the joint deviation matrix (velocity and log IOI blocks
  scaled to unit s.d.), by parallel analysis against an envelope-preserving surrogate (row phase
  randomisation, columns rescaled to the real s.d.; 100 surrogates, 95th percentile; R-02 audit).
- Per draw (20 draws): 16 experts held out; the k-dimensional subspace is estimated from the
  other n - 16; cap_oracle = share of that reference group's k-component variance lying in the
  span of the 16 held-out experts' deviations; cap_model = the same with the model's 16 samples.
- Per piece: ratio = mean cap_model / mean cap_oracle over draws. Random floor: a random
  15-dimensional subspace (50 draws).

**Exploratory: conditional component prediction.** Per piece with k > 0, leave one performer
out: basis = top k components of the other performers' deviations (expert basis) or of the
model's 16 sample deviations (model basis); the held-out performer's component scores are fitted
on the first half of the onsets and predict the second half. Compared with predicting zero (the
consensus) and with the performer-mean baseline (the performer's mean deviation per target on
the first half). Statistic: R² on the second half, mean over performers, median over pieces.

**Per capture model (R-07 lesson).** (i) R²c against the Aria-AMT-only expert mean curve, with
its own analytic oracle (pieces with >= 10 Aria-AMT renditions). (ii) Rendition level, by source:
Pearson r of each rendition's curve with the model's mean curve and with the leave-one-out
expert mean curve; median by source (Transkun V2 80, ATEPP 49, ByteDance 12 renditions).

**Sensitivity and secondary arms (not deciding).**
- The primary statistic on `frozen_p100` and the axes statistic on `frozen_p95`.
- Pianist Transformer, frozen released weights, top-p 1.0, K = 16 (`job/pt_gen.py`), if run.
  Its pretraining corpus is not known to exclude these pieces; it has no deciding role
  (DECISIONS 2026-10-05).
- Per composer and leave-one-composer-out ranges of the median (Prokofiev Op. 22 contributes 7
  primary pieces and J. S. / C. P. E. Bach 16).
- R-07's log IOI formula (only the target centered), for continuity with R-07.

## Pre-registration checks (expert data only, measured 2026-10-05)

`reachability.py` and `job/summarize_h1b.py --experts-only`; outputs in
`artifacts/prereg_experts/` and `artifacts/reachability/` (gitignored; the numbers are here).

**Expert side of the fresh primary set (59 pieces):** k median 4 (shared variance 0.369);
16-expert captured share cap_oracle median 0.196 (12 pieces); random floor 0.011 (ratio to the
oracle 0.064).

**Primary reachability.** Per-piece R²c values were drawn from the R10u development
distribution of frozen SyMuPe (74 pieces; IQR velocity [0.036, 0.493], log IOI [-0.219,
0.325]), shifted to a true median mu, 59 pieces per replicate, 400 replicates, 1,000-resample
piece bootstrap. Probability of each reading:

| Target | true median mu | consistent | inconclusive | falsified | CI half-width |
|---|---|---|---|---|---|
| velocity | 0.10 | 0.00 | 0.01 | 0.99 | 0.13 |
| velocity | 0.15 | 0.00 | 0.14 | 0.86 | 0.13 |
| velocity | 0.20 | 0.00 | 0.52 | 0.48 | 0.12 |
| velocity | 0.30 | 0.00 | 0.98 | 0.03 | 0.13 |
| velocity | 0.40 | 0.02 | 0.95 | 0.04 | 0.13 |
| velocity | 0.50 | 0.48 | 0.53 | 0.00 | 0.13 |
| velocity | 0.55 | 0.83 | 0.17 | 0.00 | 0.12 |
| velocity | 0.60 | 0.95 | 0.05 | 0.00 | 0.13 |
| log IOI | 0.10 | 0.00 | 0.01 | 0.99 | 0.10 |
| log IOI | 0.15 | 0.00 | 0.19 | 0.81 | 0.10 |
| log IOI | 0.20 | 0.00 | 0.51 | 0.49 | 0.10 |
| log IOI | 0.30 | 0.00 | 0.98 | 0.02 | 0.10 |
| log IOI | 0.50 | 0.50 | 0.50 | 0.00 | 0.10 |
| log IOI | 0.55 | 0.88 | 0.12 | 0.00 | 0.10 |
| log IOI | 0.60 | 0.99 | 0.01 | 0.00 | 0.10 |

- Every branch is reachable: with a true median at or below 0.15 the reading is "falsified"
  with probability >= 0.81, and at 0.55 or above "consistent" with probability >= 0.83. With
  the spread inflated 1.5x (fresh pieces have fewer performers), the same holds with
  probabilities >= 0.68 and >= 0.70 (`b_primary_oc.csv`).
- **Expected outcome if the fresh pieces behave like R10u:** velocity (development median 0.328)
  -> **inconclusive** (about 0.96); log IOI (development 0.127 under R-07's formula, a lower bound)
  -> falsified (about 0.9) under that formula; under the R-06 formula the development value is
  not yet known (box check B2 / stage `dev_r07`), so the expected log IOI reading is open.
  The oracle (about 0.88) is far above 0.50, so "consistent" is reachable for a model that
  matches experts.

**H1b-axes reachability** (12 pieces). Two spreads for the per-piece ratio: expert-as-model
(16 experts as the "model", 16 as the oracle, 18 reference; 32 R10u pieces with n >= 50:
median 1.013, IQR [0.963, 1.074], log-scale s.d. 0.085) and a realistic model spread (the
log-scale s.d. of frozen SyMuPe's captured share across R10u pieces, 0.543):

| true median ratio | spread | consistent | inconclusive | floor | CI half-width |
|---|---|---|---|---|---|
| 0.3 | realistic | 0.00 | 0.12 | 0.88 | 0.12 |
| 0.4 | realistic | 0.00 | 0.51 | 0.49 | 0.15 |
| 0.5 | realistic | 0.00 | 0.91 | 0.09 | 0.19 |
| 0.7 | realistic | 0.27 | 0.74 | 0.00 | 0.26 |
| 0.8 | realistic | 0.54 | 0.46 | 0.00 | 0.32 |
| 1.0 | realistic | 0.93 | 0.07 | 0.00 | 0.39 |
| 1.0 | expert-as-model | 1.00 | 0.00 | 0.00 | 0.06 |

- Both outer branches are reachable: a model as good as 16 experts reads "consistent" with
  probability 0.93 even at the realistic spread; one at or below 0.3 reads "at the floor" with
  0.88.
- Development value: the R-07 audit measured a median per-piece ratio of 0.52 for frozen
  SyMuPe at top-p 0.95 on R10u (B2 method, 5 draws). At that value the expected reading here is
  inconclusive (0.91). Top-p 1.0 widens the model's spread, so the fresh value may be higher.
  The thresholds were set knowing this development value; they were chosen from the
  equivalent-experts scale above, not from it.

## Command

On the RTX 5080 box (details, VRAM and runtime in `job/README.md`):
```
cd experiments/2026-10-05-R-10-h1b/job
bash setup.sh                       # reuses the R-07 venv under ~/r07; reinstalls pianolens
bash fetch_data.sh                  # no download if R-07's PianoCoRe copy is present
bash run.sh                         # meta sets ridge gen_frozen_p95 gen_frozen_p100 dev_r07 summarize
STAGES="gen_pt summarize" bash run.sh       # optional secondary arm (bash setup.sh pt first)
STAGES="dev_gen summarize" bash run.sh      # optional: top-p 1.0 development numbers on R10u
```
Piece selection and pre-registration checks (Mac, already run):
```
uv run python experiments/2026-10-05-R-10-h1b/select_pieces.py
uv run python experiments/2026-10-05-R-10-h1b/job/build_set.py \
  --pieces experiments/2026-10-05-R-10-h1b/pieces/fresh_pieces.csv --pianocore data/raw/pianocore \
  --out experiments/2026-10-05-R-10-h1b/artifacts/sets/fresh --workers 10
uv run python experiments/2026-10-05-R-10-h1b/job/summarize_h1b.py --experts-only \
  --set experiments/2026-10-05-R-10-h1b/artifacts/sets/fresh \
  --out experiments/2026-10-05-R-10-h1b/artifacts/prereg_experts/fresh
uv run python experiments/2026-10-05-R-10-h1b/reachability.py --r07-h1b <R-07 results/R10u/h1b.csv>
```

## Dry run (Mac CPU, 2026-10-05; pipeline check, not results)

`DRY_RUN=1` (`job/README.md`): `setup.sh` for both envs with `TORCH_INDEX=pypi` (torch 2.7.1
CPU), then every stage, on the 2 R10u development pieces that R-07's dry run used (`scarlatti_k32`
and the Anna Magdalena Notebook minuet in D minor, BWV Anh. 132; 98 renditions). No fresh piece
was touched by any model or baseline.
- `sets`: dry-run set 98 renditions; R10s development set 48 pieces, 1,931 renditions (41 s).
- `ridge` (trained on R10s only in the dry run): 48 pieces, 24 works; GroupKFold r velocity
  0.498, log IOI 0.146.
- Generation, K = 16, one CPU thread: SyMuPe 130-175 ms per note at either top-p; Pianist
  Transformer (K = 4 in the dry run) 148-186 ms per note.
- `dev_r07` ran on R-07's own dry-run outputs (3 renditions per piece); `summarize` produced
  every table (oracles, axes ratio, conditional prediction, per source, per composer, paired
  differences, readings).
- The first pass exposed the sampling trap (Method): the top-p 1.0 and 0.95 sample sets were
  identical. After the fix, 0.95 reproduces the earlier samples exactly and 1.0 differs.
- Disclosure: the summaries printed R²c, ratios and readings for the 2 development pieces. They
  were seen after the thresholds were written and changed none of them; the top-p assignment
  (Method) used only the sample spread.

## Box runtime estimate

Work: 74,262 score notes in the 65 fresh generation items; 131,674 in the R10u development set.
- SyMuPe generation on the 5080 has no logged rate (R-07's committed run record has none).
  Upper bound: the Mac CPU rate above, 130-175 ms per note, i.e. 2.7-3.6 h per fresh sample
  set. Lower estimate: Pianist Transformer generated R10u on the box in 4.1 h (R-07 run record,
  pt_E retry, 91 items, K = 16, alone on the GPU), about 113 ms per note; R-06 measured SyMuPe
  5.7x faster than Pianist Transformer on CPU, giving about 20 ms per note, about 25 min per
  set.
- Default run (sets, ridge, two SyMuPe sample sets, summaries): about 1-7 h. Optional `gen_pt`
  about 2.3 h; optional `dev_gen` 0.7-6.5 h. Every item logs its own ms per note, so the first
  items give the real rate.
- VRAM: SyMuPe needs little (its R-07 training peak was 2.8 GB). Pianist Transformer generation
  reached 14.5 GB in R-07 while sharing the card and ran out of memory while a game held about
  5 GB: run `gen_pt` alone.

## Threats to validity

- **Transcribed MIDI.** 92% of the primary renditions are Aria-AMT transcriptions of YouTube
  audio; transcribed velocity is compressed and noisy (D-10). Every R²c is against a
  transcription-based consensus, and the source cannot be separated from the corpus (BL-18
  lesson). The Aria-AMT-only and rendition-level tables are the only per-source evidence.
- **Unseen is "not paired in PERiScoPe v1.0, by our matching".** 80 primary renditions are
  Transkun V2 transcriptions that come from the PERiScoPe corpus without a score pairing.
  SyMuPe's description says it trains on score-performance pairs only; if it also used unpaired
  performances, these pieces' performances (not their scores) may have been seen. Aliases are
  caught by catalogue tokens, not necessarily all (arrangements, titles without numbers).
- **Fresh pieces are less-played repertoire.** They are the pieces left after removing
  everything popular enough to be in PERiScoPe's pairs or in R-02 (>= 50 performances): fewer
  performers (median 28), shorter pieces, many pedagogical or baroque pieces. Generalisation to
  the canon is shown by R10u (development) only.
- **Repertoire clustering.** Prokofiev Op. 22 (7 primary pieces) and the Bach families (16) are
  large shares; the per-composer and leave-one-composer-out tables show their weight.
- **Target noise.** With 20-49 performers the expert mean curve is noisy; R²c is attenuated by
  it (analytic oracle 0.878 / 0.882). The thresholds apply to the raw R²c as DECISIONS
  specifies; the disattenuated value is descriptive.
- **K = 16 samples.** The model's mean curve carries sample noise; the K-matched oracle carries
  the same amount from 16 experts, which is why it is the comparison.
- **H1b-axes power.** 12 pieces; the CI is wide at a realistic spread (half-width about 0.3 at a
  ratio of 0.8).
- **Platform.** Items rebuilt on the Windows box must match the Mac digest
  (`pieces/fresh_digest.json`); the job stops if they differ.

## Run record

- Pre-registration hash (2026-10-05): `head -n 409 README.md` sha256
  `d679394f6622275218d5a5f9a219d519d75ea5ca633603a5420d7e2f25d75f09`
  (`artifacts/prereg_sha256.txt`, copy in `artifacts/prereg_README.md`).
- Not run yet. Entries below are added by the run.
- **2026-10-06, RTX 5080 box (Windows), lead session: default run complete.** Checkout at
  `28c5a01` (contains the pianocore Windows fix 881f9f9); `run_meta.json` records HEAD, diff hash,
  torch 2.7.1+cu128, CUDA, RTX 5080. Driver started 01:51:49 UTC; `setup.sh` and `fetch_data.sh`
  (PianoCoRe checksums OK) passed; default `run.sh` finished 02:32:06 UTC with exit 0 (meta, sets,
  ridge, gen_frozen_p95, gen_frozen_p100, dev_r07, dev_r07_no_overlap, summarize,
  summarize_as_registered). Pre-registration hash re-checked: unchanged.
  - **Digest checks (01:56 UTC):** fresh set digest MATCHES the Mac pre-registration copy; R4:
    r10u_dev and r10s_dev digests MATCH the Mac references.
  - Generation: frozen_p95 65 / 65 and frozen_p100 65 / 65 fresh items; no errors in the logs.
  - Pieces: 62 total, 56 primary (54 works) after the pre-run amendment A1 / A2 exclusions
    (3 pieces for content overlap, 25 duplicate renditions); 15 oracle-eligible, 12 axes-eligible.
  - **Headline (`results/fresh/summary.json`), provisional, not audited:** "H1b-consensus
    (frozen_p95, registered): velocity falsified, log IOI falsified. H1b-axes (frozen_p100,
    registered): inconclusive".
    - H1b-consensus, frozen SyMuPe top-p 0.95, median per-piece R²c over 56 pieces:
      velocity **0.150 [0.022, 0.283]**, log IOI **0.073 [0.032, 0.180]**: both "falsified"
      (median ≤ 0.20 and CI upper < 0.50). Composer-cluster CIs: velocity [−0.006, 0.283],
      log IOI [0.032, 0.137]. Ratio of medians to the analytic oracle: 0.171 / 0.082.
    - H1b-axes, frozen top-p 1.0, 12 pieces: 0.437 [0.383, 0.610] → inconclusive (thresholds
      0.8 / 0.4).
    - vs the score-feature ridge (secondary): frozen_p95 − ridge velocity −0.059 [−0.203,
      0.022], log IOI +0.037 [−0.081, 0.082]: no detectable difference on either target.
    - `fresh_as_registered` (no exclusions, sensitivity): same headline.
  - Small outputs copied to `results_box/` (results for fresh, fresh_as_registered, r10u_r07,
    r10u_r07_no_overlap; run_meta.json; logs; ridge.json; *.json / *.csv of the sets). Not copied:
    generated samples (`gen/*.npz`) and ridge weights (`ridge.npz`), which stay on the box.
  - Still running on the box: `gen_pt` (Pianist Transformer, secondary), then `dev_gen`. The box
    pushes again when those finish.
  - Post-audit (2026-10-06): the headline above, the `results_box/` logs line and the amendment
    hash command are corrected in `## Post-audit corrections (2026-10-06)` at the end of this
    file. The lines above are left as written.
- **2026-10-10, RTX 5080 box, lead session: secondary stages complete (ALL DONE).**
  - Timeline: `gen_pt` started 02:32:11 UTC 2026-10-06 and was paused (processes suspended) at
    Henry's request at 03:13:46 UTC (11 of 65 items counted at the last check before the pause; 12
    on disk at the restart). The box rebooted at 15:09 UTC 2026-10-06, which killed the suspended job. On Henry's
    request the remaining stages were restarted at 04:36:57 UTC 2026-10-10 with the same `run.sh`
    (`STAGES="gen_pt summarize"`, then `STAGES="dev_gen summarize"`); finished items were skipped,
    so only the item in progress at the pause was regenerated. `gen_pt` exit 0 at 05:53:10 UTC,
    `dev_gen` exit 0 at 06:24:34 UTC. Pre-registration hash re-checked: unchanged.
  - Generation: pt_frozen_p100 65 / 65 fresh items, frozen_p100 91 / 91 R10u dev items; 0 errors
    in every `_log_gen.json`; no tracebacks or out-of-memory errors in the logs.
  - **Headline unchanged** (`results/fresh/summary.json`; the primary reading is the one audited
    2026-10-06, the secondary numbers below are not audited): "H1b-consensus
    (frozen_p95, registered): velocity falsified, log IOI falsified. H1b-axes (frozen_p100,
    registered): inconclusive". Primary numbers identical to the 2026-10-06 entry: velocity
    0.150 [0.022, 0.283], log IOI 0.073 [0.032, 0.180]; H1b-axes 0.437 [0.383, 0.610] (12 pieces).
  - Pianist Transformer (frozen, top-p 1.0; secondary, not deciding), 56 primary pieces: median
    R²c velocity 0.061 [−0.127, 0.273], log IOI −0.045 [−0.176, 0.078]; axes ratio 0.467
    [0.369, 0.655] (12 pieces). Paired: frozen_p95 − pt_frozen velocity −0.018 [−0.101, 0.110],
    log IOI +0.078 [−0.056, 0.197]; pt_frozen − ridge velocity −0.125 [−0.260, −0.020], log IOI
    −0.098 [−0.220, 0.059]. Shape and amplitude: r velocity 0.650 [0.569, 0.701], b 1.073
    [1.017, 1.157]; r log IOI 0.391 [0.316, 0.492], b 0.830 [0.676, 0.939].
  - Development (R10u, frozen SyMuPe top-p 1.0, `dev_gen`; not deciding): 85 primary pieces,
    R²c velocity 0.324 [0.254, 0.445], log IOI −0.173 [−0.304, −0.061]; axes ratio 0.347
    [0.309, 0.384] (79 pieces); r velocity 0.679 [0.620, 0.704], b 0.974 [0.935, 1.016]; r log
    IOI 0.524 [0.479, 0.555], b 1.124 [1.015, 1.238]. Without the R3 overlap pieces (80 primary): velocity 0.324
    [0.254, 0.445], log IOI −0.182 [−0.336, −0.062]; axes 0.347 [0.309, 0.384] (75 pieces).
  - `results_box/` refreshed (fresh and fresh_as_registered now include the pt_frozen arm; new
    r10u_dev and r10u_dev_no_overlap). Box run logs added under `results_box/logs/` (`*.log` is
    gitignored, so they are force-added; this answers post-audit correction 3), and the
    per-item generation logs under `results_box/gen_logs/`. Generated samples and ridge weights
    stay on the box. Post-audit correction 6 (r / b / R²c-at-b = 1 columns for these arms) is
    left to the author; r and b above are read from `summary.json`.

## Pre-run amendments (2026-10-05, after the eval-auditor pre-run review, PRERUN_REVIEW.md)

Written before any model or baseline output on the fresh pieces existed. No threshold, model,
statistic or arm assignment changes.

A1. Content overlap (review F1). Steps 2-4 match PERiScoPe pairs by performance id and catalogue
tokens; R-07's work key separates a whole-set piece id from its movements, so a whole-set piece
passes even when its movements are paired. Added step 6: no fresh piece may share 10 or more
12-onset pitch-set n-grams (first 1,500 onsets of its majority refined score) with any refined
score of a PERiScoPe-paired, possibly paired, or R-06 / R-07 evaluation piece. It drops 3 pieces
(every other fresh piece shares at most 3), listed in pieces/excluded_content_overlap.csv:
- pianocore:Debussy,_Claude/2_Arabesques (contains Arabesque No. 1, 48 score-paired PERiScoPe
  v1.0 performances; was primary);
- pianocore:Ravel,_Maurice/Le_Tombeau_de_Couperin,_M.68 (whole suite; Prelude and Fugue paired
  22 and 29 times; was not primary);
- pianocore:Bartók,_Béla/Romanian_Folk_Dances,_Sz.56/3._Pe_loc (contained in the R-07 R10u piece
  pianocore:Bartók,_Béla/Romanian_Folk_Dances,_Sz.56; was primary).
They are excluded from every statistic. Their generation items may still be produced (the set
digest is unchanged); their outputs are not read.

A2. Near-duplicate renditions (review F2). Within a piece, two renditions whose deviations from
the expert mean curve (columns mean-filled, rows demeaned) correlate above 0.9 in log IOI or in
centered velocity are treated as one performance; the later one in manifest order is dropped.
This removes 25 renditions in 15 primary pieces (pieces/duplicate_renditions.csv, by
performance_id) and applies to every statistic (expert curves, oracles, k, captured shares,
conditional prediction, per-source tables). bach_bwv913 drops to 17
renditions and leaves the primary set.
Primary set after A1 and A2: 56 pieces, 54 works, 1,691 renditions (median 28). Expert-side
values (measured before any model output): analytic oracle velocity 0.877 [0.847, 0.901], log IOI
0.881 [0.845, 0.905]; empirical oracle (15 pieces) 0.883 / 0.856; reliability 0.958 / 0.958;
H1b-axes subset 12 pieces, 16-expert captured share 0.189; equivalent-experts scale 0.08 / 0.24 /
0.55 / 0.80 (K' = 2 / 4 / 8 / 12), so the 0.80 / 0.40 thresholds keep their meaning.
The as-registered set (59 pieces, no exclusions) is summarised as well, as a sensitivity
analysis (results/fresh_as_registered).

A3. Top-p record (review F3). Correction to "What had been seen" and to the dry-run disclosure:
the first draft of this README (16:46:59Z) registered the primary on top-p 1.0 samples, with top-p
0.95 exploratory. After the sampling fix, the dry-run summary (16:56:49Z) printed R²c for both
arms on the 2 development pieces (log IOI p95 vs p100: 0.295 vs 0.063 and -1.62 vs -2.04;
velocity 0.527 vs 0.690 and 0.568 vs 0.533), and the primary was then switched to top-p 0.95
(16:58:18Z). The stated reasons (development numbers and the reachability simulation are at
0.95) stand, and the lead confirmed the assignment (DECISIONS 2026-10-05), but the R²c were
visible when the switch was made. Added reporting rule: the headline gives the registered reading
(frozen_p95); if the frozen_p100 reading differs for either target, the same sentence states it.

A4. Scope (review F4). "Given only the score" means the score plus two global scalars from the
panel: the median conditioning tempo and velocity of the piece's renditions (R-06 / R-07 rule);
the targets do not contain them, the ridge does not use them. "Unseen" means: no score-paired
performance in PERiScoPe v1.0 (the EncDec-base model card states training on v1.0), checked by
performance id, catalogue alias, title search and score content (A1). About half of the primary
pieces have another number of the same opus or collection that is paired (WTC, Bach toccatas,
Visions fugitives Op. 22, Schumann Op. 68, Chopin Op. 33, Grieg Op. 54, Clementi Op. 36,
C. P. E. Bach H. 1, the Anna Magdalena Notebook, Mozart K. 2). Exploratory table: the primary
statistic split by a sibling flag (another piece with the same opus number, or the same PianoCoRe
collection title, is PERiScoPe-paired or possibly paired), the flag committed as
pieces/sibling_flag.csv before the run. The verdict sentence names the scope: frozen SyMuPe
EncDec-base, less-played repertoire, consensus of mostly Aria-AMT transcriptions of YouTube
recordings, conditioned on the panel's median tempo and loudness.

R1. Amplitude decomposition (review F5): per piece, arm and target, also report r², the amplitude
ratio b = sd(pc) / sd(mc) and the identity R²c = 2 r b - b²; the same for the empirical K-matched
oracle (16 held-out experts). Medians with work-cluster CIs. Descriptive only.
R2. Composer-cluster bootstrap CI (25 composers) for the primary medians, next to the
work-cluster CI. Descriptive only.
R3. Development numbers (review F7): the R10u "unseen" development medians are also given without
the 5 pieces whose scores contain PERiScoPe-paired music (bach_bwv856, bach_bwv857, bach_bwv862,
mozart_k545, clementi_op36_no1): frozen, R-07 formula, 0.330 / 0.142 on 69 pieces (0.328 / 0.127
on 74).
R4. Development sets: run.sh compares the r10u_dev and r10s_dev digests with the Mac's
(artifacts/sets/r10u_dev/digest.json; r10s from a Mac build) and logs a mismatch (not fatal);
ridge.json is compared with the Mac reference (138 pieces, 97 works, alpha 1000 / 1, CV r 0.516 /
0.167).
R5. symupe_gen.py docstring: the primary arm is top-p 0.95, the axes arm top-p 1.0.

Implementation (lead decisions 2026-10-05; author, before the box run):
- `amend_pieces.py` (Mac, scores and expert data only) writes the committed lists:
  `pieces/content_overlap.csv` (A1 check for every fresh piece), `excluded_content_overlap.csv`
  (A1, 3 pieces), `duplicate_renditions.csv` (A2, 25 rows, identical to the review appendix),
  `sibling_flag.csv` (A4), `r10u_content_overlap.csv` and `r10u_dev_content_overlap_exclude.csv`
  (R3), `amendment_summary.json`. The A1 check reproduces the review: hits 653 / 628 / 114 for
  the three pieces; every other fresh piece shares at most 3 n-grams with any single held piece
  (4 over all held pieces combined, Boulanger Cortège). Sibling flag: same PianoCoRe composition
  title or same composer and opus number as a paired or possibly paired piece, plus one hand rule
  (Mozart K. 1-5 as one collection, since K. 2 is paired and the numbers carry separate titles);
  28 of the 56 primary pieces are flagged. The R3 list adds the Bartók whole set (paired
  movements 1-2), which has 3 renditions and never enters the H1b statistics.
- `job/summarize_h1b.py`: `--exclude-pieces` (A1), `--exclude-renditions` (A2, by piece and
  performance id), `--sibling-flag` (A4 split), r² and b next to every R²c and for the empirical
  oracle (R1), composer-cluster CI (R2), per-piece H1b-axes ratios, and the A3 headline
  (`summary.json` "headline").
- `job/run.sh`: `summarize` writes `results/fresh` (A1 + A2 applied; registered reading) and
  `results/fresh_as_registered` (no exclusions); `dev_r07` and `summarize_dev` also write a
  `_no_overlap` version (R3); `sets` and `ridge` log the R4 checks against
  `pieces/dev_reference.json`. The fresh-set digest and its fatal check are unchanged.
- Checks run on the Mac after the change (no fresh-piece model or ridge output):
  `summarize_h1b.py --experts-only` with the A1 + A2 lists reproduces every expert number in A2
  (56 pieces, 54 works, 1,691 renditions; 0.877 [0.847, 0.901] / 0.881 [0.845, 0.905]; 0.883 /
  0.856; 0.958 / 0.958; 12 axes pieces, 0.189); the R3 medians (0.330 / 0.142 on 69) reproduce
  from R-07's committed `h1b.csv`; a full rebuild of the fresh, R10u and R10s sets into a scratch
  folder matched the fresh digest and both development digests, and the ridge matched the
  reference; the dry run on the 2 R10u pieces ran every stage with the new flags.

- Pre-run amendment hash (2026-10-05): `sed -n '417,517p' README.md` sha256
  `6215a0577f79d72fae1d6fb45d8324683388bf6bb94f95f8fb6bbd8b22dc4089` (`artifacts/prereg_amendment_sha256.txt`, with the hashes of the committed lists).
  Superseded command (the run record moved the block): use the anchor form in
  `## Post-audit corrections (2026-10-06)`; the hash is unchanged.

## Audit (2026-10-06, eval-auditor)

**Verdict: Confirmed with caveats (scoped).** The registered reading follows the rule exactly:
**H1b-consensus is falsified on both targets** for the sampled mean curve of frozen SyMuPe
EncDec-base at top-p 0.95. Top-p 1.0 gives the same reading. Order, blindness, data and code
integrity check out, and every headline number reproduces from the committed CSVs.

The caveats concern what "falsified" means, not whether the rule was applied:
- Shape agreement is unchanged from development to fresh pieces. The velocity drop from 0.33 to
  0.15 is amplitude: the expert consensus is flatter on the fresh pieces and the model does not
  flatten with it.
- One amplitude scale chosen on the development pieces moves both targets to **inconclusive**.
- No scaling reaches 0.50.
- H1b-axes "inconclusive" sits only slightly above a structure-free sampler.

Everything below the verdict line is post hoc and non-deciding unless it says "registered".
Script: `audit_checks.py` (Mac, about 2 min; output reproduced below).

### 1. Order and blindness

- **Pre-registration.** `head -n 409 README.md` = d679394f...5f09, and the 101-line block from
  `## Pre-run amendments` (now lines 445-545) = 6215a057...4089. Both are identical in 4047183
  (committed 2026-10-05 18:25 UTC, where the block was at 417-517) and in the current file.
  `artifacts/prereg_amendment_sha256.txt` still names `sed -n '417,517p'`. The run record was
  inserted above the block, so that command now hashes the wrong lines (fix 2).
- **Checkout.** 28c5a01 was committed at 01:51:25 UTC on 2026-10-06; the driver started at
  01:51:49.
  - `run_meta.json` (01:53:07): HEAD 28c5a01; `git_diff_sha256` e3b0c442... is the hash of
    empty input, i.e. a clean tree.
  - All 11 `job_files_sha256` equal the 28c5a01 files and the current Mac files.
  - All 13 `pieces_sha256` equal the committed lists. For `r10u_dev_content_overlap_exclude.csv`
    this is the LF hash noted in `prereg_amendment_sha256.txt`.
- **Changes between the prereg commit and the run.** The R-10 folder is unchanged from 4047183
  to 28c5a01. The only code change between them is the Windows tempfile fix in
  `src/pianolens/data/pianocore.py`, which does not touch the data. The box digests of fresh,
  r10u_dev and r10s_dev equal the Mac references, and `ridge.json` equals `dev_reference.json`
  (alpha 1000 / 1, CV r 0.516 / 0.167, 138 pieces, 97 works).
- **Nothing from the fresh pieces was seen before the run.** The Mac `artifacts/` holds no model
  or ridge output on any fresh piece. Its only sample files are the dry-run outputs on 2 R10u
  pieces; `sets/fresh/gen_items` are score-side inputs. The ridge training pieces (170 R10u +
  R10s ids) share no piece or work with the fresh set.
- **R-10b (withdrawn duplicate) did not touch the fresh pieces and could not have shaped R-10.**
  - All 82 of its pieces are R-02 pieces: 42 R10u decision, 40 calibration from R-07 train/val,
    and 2 dry-run pieces. They share no piece id and no work with the 65 fresh pieces (step 5 of
    the selection excludes R-02 and R10u).
  - Its `prep.py` and `run.sh` read only that list.
  - R-10's thresholds and amendments were committed about 7.5 h before R-10b entered the shared
    history (28c5a01), and are unchanged.
  - What R-10b produced (frozen and E samples on R10u pieces, a simulation on expert data) is
    development-type data. Its one transferable result, a structure-free floor for
    captured-share statistics, is used in section 8 below as an audit caveat, not as a reading.
  - I could not inspect its `job/outputs/` (box only).
- **Run record.** It says logs were copied to `results_box/`; no log file is there (fix 3).

### 2. The statistic and the reproduction

- `summarize_h1b.r2c` is the R-06 formula with both curves centered over the onsets where both
  are finite.
- The model arms and the ridge go through the same `mean_curves` (velocity centered per
  rendition or sample) and `r2c` against the full n-expert mean.
- The empirical oracle and `r2c_vs_rest` use the same n - 16 reference means in the same draws.
- The analytic oracle is the registered expectation formula.
- Per piece, R²c = 2rb - b² holds to 2e-15, and the r² column equals r².
- Every arm median and CI in `summary.json` (r2c, r, r², b; both targets; three arms) reproduces
  exactly with the summariser's `cluster_boot_median`, and so does each reading.
- The A1/A2 primary set is 56 pieces, 54 works, 1,691 renditions, median 28.

| Arm (56 pieces) | velocity R²c | log IOI R²c | reading (registered rule) |
|---|---|---|---|
| frozen_p95 (**registered**) | 0.150 [0.022, 0.283] | 0.073 [0.032, 0.180] | falsified / falsified |
| frozen_p100 (sensitivity) | 0.098 [0.009, 0.215] | -0.178 [-0.384, 0.007] | falsified / falsified |
| score-feature ridge | 0.246 [0.198, 0.299] | 0.054 [0.027, 0.122] | **inconclusive** / falsified |
| fresh_as_registered, p95 (59 pieces) | 0.173 [0.054, 0.293] | 0.072 [0.032, 0.157] | falsified / falsified |

- The top-p 1.0 reading equals the registered one, so the A3 headline rule adds nothing, and the
  headline is correct.
- Composer-cluster CIs reproduce: velocity [-0.006, 0.283], log IOI [0.032, 0.137].
- Disattenuated R²c is 0.163 / 0.077, so target noise does not explain the result.
- Matched empirical ratio (15 pieces): 0.314 [0.151, 0.505] / 0.204 [0.075, 0.463].

### 3. Shape or amplitude (R1)

Medians with work-cluster CIs. "R²c at b = 1" is what a sampler with the experts' own amplitude
would score (the 16-expert oracle has b = 1.016 / 1.014). r² is the ceiling under the best
per-piece scale, which uses the target and is not a prediction.

| | r | b | R²c | R²c at b = 1 | r² (best scale) |
|---|---|---|---|---|---|
| velocity, fresh p95 | 0.672 [0.567, 0.709] | 1.100 [0.999, 1.196] | 0.150 | 0.344 [0.135, 0.419] | 0.452 [0.322, 0.503] |
| log IOI, fresh p95 | 0.553 [0.512, 0.607] | 0.926 [0.750, 1.057] | 0.073 | 0.106 [0.023, 0.215] | 0.306 [0.262, 0.369] |
| velocity, fresh p100 | 0.652 | 1.089 | 0.098 | 0.303 | 0.425 |
| log IOI, fresh p100 | 0.520 | 1.214 [1.045, 1.298] | -0.178 | 0.041 | 0.271 |
| velocity, 16-expert oracle (15 pieces) | r² 0.895 | 1.016 | 0.883 | | |
| log IOI, 16-expert oracle (15 pieces) | r² 0.875 | 1.014 | 0.856 | | |

- **Log IOI is a shape failure.** With r = 0.55, even a sampler at the experts' amplitude would
  score 0.11, and the best possible scaling reaches only 0.31.
- **Velocity is both.**
  - The shape is moderate (r² 0.45, against 0.89 for 16 experts).
  - The registered "falsified" also needs the overshoot. At b = 1 the reading would be
    inconclusive (0.344).
  - Overshoot is largest where the expert consensus is flattest: Spearman ρ(target s.d., b) =
    -0.54. Composer medians of b are CPE Bach 1.68 and Rameau 1.69, against a target s.d. of
    3.8-6.1 velocity units.
- At top-p 1.0, log IOI overshoots too (b 1.21). This is why that arm is negative.
- 36% of pieces have negative R²c on each target (p95).

### 4. Development vs fresh pieces; B2

Development set: R10u "unseen" (74 pieces), R-07's own samples (top-p 0.95), rescored with this
code.

| | fresh (56) | R10u unseen (74) | difference (Mann-Whitney p) |
|---|---|---|---|
| velocity r | 0.672 | 0.665 | p 0.67 |
| velocity b | 1.100 | 0.943 | p 0.002 |
| velocity R²c | 0.150 | 0.329 | p 0.015 |
| velocity target s.d. (expert mean curve, per onset) | 7.34 | 9.32 | p 4e-5 |
| velocity model s.d. | 7.92 | 8.95 | p 0.049 |
| log IOI r / b / R²c | 0.553 / 0.926 / 0.073 | 0.516 / 0.824 / 0.144 | p 0.72 / 0.36 / 0.36 |
| log IOI target s.d. / model s.d. | 0.187 / 0.150 | 0.254 / 0.202 | p 7e-4 / 6e-4 |
| renditions per piece / reliability / analytic oracle | 28 / 0.958 / 0.877 | 48 / 0.981 / 0.922 | |
| Aria-AMT share of renditions | 92.1% | 93.1% | |

- **The fresh set is not harder in shape.** The model's correlation with the consensus is the
  same on both sets.
- **It is flatter.** Its expert consensus has about 20-25% less amplitude in both targets. Fewer
  performers would add noise and inflate the target s.d., not shrink it, so the flatness is real.
  Pedagogical and baroque pieces dominate the fresh set.
- **The model only partly adapts.** Its velocity amplitude drops 12% while the target's drops
  21%. That produces b > 1 and halves R²c.
- **What does not explain the drop:**
  - The source mix is the same on both sets.
  - Reliability tracks R²c (ρ = 0.55) but not r (ρ = 0.22, p 0.10), so it acts through
    amplitude.
- **Log IOI** does not differ significantly between the sets.
- **B2 (R-07 audit).** On the 74 unseen dev pieces:
  - log IOI R²c is 0.144 [0.098, 0.226] with the R-06 formula, against 0.127 [0.050, 0.221]
    with R-07's uncentered formula;
  - on all 85 R10u primary pieces it is 0.146 against 0.142;
  - velocity is identical by construction (0.329).

  The centering bug cost about 0.02. At the corrected dev value, the reachability table already
  expected "falsified" for log IOI. Velocity was expected inconclusive (about 0.96) and came out
  falsified, because of the amplitude shift above.
- **Spread.** The observed fresh IQR of velocity R²c is [-0.224, 0.413], 1.4x the development
  IQR used in the reachability check. That is within the registered 1.5x stress case, so the
  CIs were as informative as planned.

### 5. Frozen SyMuPe vs the score-feature ridge

Registered secondary: no detectable difference (velocity -0.059 [-0.203, 0.022], log IOI +0.037
[-0.081, 0.082]). It reproduces. On shape, though, the 25M-parameter model clearly beats the
ridge (paired, work-cluster):
- r: velocity +0.129 [0.083, 0.164]; log IOI +0.245 [0.139, 0.296];
- the model's r is higher on 80% / 86% of pieces.

The ridge ties on R²c only because a regression shrinks its predictions (b = 0.44 / 0.29), which
is the least-squares choice when r is moderate. The sampler instead reproduces full expressive
amplitude.

With the development-chosen scale (section 6), the model beats the ridge on both targets:
+0.152 [0.076, 0.203] and +0.186 [0.127, 0.240].

So the model does learn score-to-expression structure that a linear score-feature model lacks,
especially in timing. The registered statistic does not show it.

Note also that the ridge's own velocity reading is inconclusive (0.246), not falsified. The
registered scope sentence ("the best available score-conditioned model does not reach the H1b
level") must not be read as "no score-conditioned predictor clears 0.20".

### 6. One amplitude scale chosen on development data (post hoc)

A single multiplier s was fitted to maximise the median R²c on the 74 R10u unseen pieces and
applied unchanged to the fresh pieces. It is exact through R²c(s) = 2rbs - (bs)² and uses no
fresh-piece information.

| | s (dev) | dev median | fresh median | reading by the registered rule |
|---|---|---|---|---|
| velocity | 0.627 | 0.414 | 0.362 [0.260, 0.456] | inconclusive |
| log IOI | 0.638 | 0.235 | 0.271 [0.233, 0.321] | inconclusive |

This is exploratory, chosen after the results, and it does not change the registered verdict.
It shows that "falsified" is a property of the raw sampled mean curve, not of SyMuPe's
score-to-expression mapping. Under any scaling, including the in-sample best per piece (r² 0.45
/ 0.31), neither target reaches "consistent".

### 7. Robustness

- **Leave one composer out.** The velocity reading stays falsified for 22 of 23 composers.
  Dropping J. S. Bach (12 of 56 pieces, velocity r 0.44) gives 0.205 [0.093, 0.314], which is
  inconclusive. The log IOI reading stays falsified for all 23 (range 0.065-0.074).
- **A4 sibling split (exploratory).**
  - Velocity R²c is 0.268 [0.123, 0.385] for the 28 unflagged pieces and -0.109 [-0.280, 0.173]
    for the 28 flagged ones. Log IOI is 0.065 against 0.089.
  - The flagged pieces score lower, the opposite of what leakage would do. The cause is shape
    (r 0.565 vs 0.705), not amplitude (b 1.10 vs 1.10), and the flag is confounded with
    repertoire: all J. S. Bach WTC and toccata pieces and all 7 Prokofiev Op. 22 pieces are
    flagged.
  - There is no sign that paired siblings leaked into SyMuPe's predictions.
- **Per source (rendition level).** The model's correlation with each rendition, minus the
  leave-one-out expert curve's correlation, does not differ from Aria-AMT within pieces for any
  source:
  - Transkun V2: -0.004 [-0.031, 0.047] velocity, +0.024 [-0.022, 0.034] log IOI (22 pieces);
  - ATEPP: +0.004 / -0.018 (16 pieces);
  - ByteDance: +0.054 / -0.004 (10 pieces).

  The Transkun V2 renditions come from the PERiScoPe corpus, unpaired. They show no extra model
  agreement, so there is no sign that their performances were seen. The Aria-AMT-only piece
  level (56 pieces) gives the same medians (0.152 / 0.073).
- **Conditional prediction (exploratory).**
  - Expert basis: 0.039 [0.014, 0.062].
  - Model-sample basis: -0.041 [-0.050, -0.014], i.e. worse than predicting the consensus.
  - Performer mean: -0.075.

### 8. H1b-axes and a structure-free floor (post hoc)

The registered reading is right: frozen_p100 gives 0.437 [0.383, 0.610] (inconclusive; at p95,
0.528 [0.469, 0.700]). The registered floor, however, was a random 15-dimensional subspace
(ratio 0.064), which is the weak-null trap from the R-02 audit.

I scored a structure-free sampler with the registered code: 16 envelope surrogates of the
held-out experts' own deviations (per-row phase randomisation, per-onset s.d. restored), 5 per
draw, on the 12 axes pieces. The Mac rebuild reproduces k and cap_oracle exactly (max |diff| 2e-16).
- Envelope-surrogate ratio to the 16-expert oracle: **0.363 [0.277, 0.461]**.
- Model, null-adjusted (cap - cap_env) / (cap_oracle - cap_env):
  - p100: 0.156 [0.007, 0.330];
  - p95: 0.299 [0.094, 0.454].
- On 3 of 12 pieces the p100 samples capture no more than the surrogates.

So the "at the floor" threshold of 0.40 was barely above a structure-free sampler. The model's
samples span the experts' shared axes only a little better than curves with the right per-onset
spread and no cross-performer structure. The registered "inconclusive" stands. It should be
described as "near a structure-free floor", not "as well as about 6-8 experts".

### 9. Does "falsified" follow, and its scope

Yes, word for word:
- the point is at or below 0.20 and the CI upper bound is below 0.50 for both targets, on the
  registered arm;
- the same holds at top-p 1.0, on the as-registered 59 pieces, and with the composer-cluster CI.

The claim is scoped as A4 requires:
- the model is frozen SyMuPe EncDec-base;
- the curve is the mean of 16 samples at top-p 0.95 (1.0 as sensitivity), not rescaled;
- the model is conditioned on the panel's median tempo and loudness;
- the pieces are 56 less-played PianoCoRe pieces unseen in PERiScoPe v1.0 pairs;
- the consensus is of mostly Aria-AMT transcriptions of YouTube recordings (median 28 per piece).

The statistic is the mean-curve consensus (DECISIONS 2026-10-05). It is not the plan's "shared
components" literally; that is the H1b-axes line.

**Required fixes (text only; the verdict stands):**
1. The headline and EXPERIMENTS must state, next to "falsified":
   - shape vs amplitude: velocity r 0.67 (r² 0.45), log IOI r 0.55 (r² 0.31), against oracle r²
     0.89 / 0.88;
   - that a development-chosen amplitude scale gives inconclusive on both targets (0.36 / 0.27);
   - that no scaling reaches 0.50.

   Without this, "falsified" reads as "no shape", which is wrong for velocity.
2. `artifacts/prereg_amendment_sha256.txt` and the README hash line must name the current lines
   (445-545) or an anchor-based command, for example
   `awk '/^## Pre-run amendments/{f=1} f&&n<101{print;n++}' README.md | shasum -a 256`.
3. The run record must correct "logs copied to `results_box/`" (none are there), or copy the
   logs.
4. H1b-axes must be reported with the envelope floor (section 8), and the "6-12 experts" scale
   must not be used to describe 0.44.
5. The scope sentence in the verdict must say that the score-feature ridge reads inconclusive
   on velocity (0.246), so "falsified" applies to the registered model statistic, not to
   score-only prediction in general.
6. When `gen_pt` and `dev_gen` arrive, report them with the same r / b / R²c-at-b = 1 columns.
   They do not decide.

### 10. Checks that need the box

1. **Sampling noise in b.** Split each piece's 16 samples into 8 + 8 and estimate how much of b
   > 1 is K = 16 sample noise and how much is systematic amplitude. Then extrapolate R²c and b to
   the K -> infinity mean curve. This needs `gen/*.npz`.
2. **Calibrated predictors.** Fit model + ridge stacking, and a per-piece scale predicted from
   score features (both fitted on R10u/R10s only), then score them on the fresh pieces. This
   needs the curves; the global scale in section 6 is exact from r and b and needs no box.
3. **Run-order evidence.**
   - mtimes of every file under `job/outputs/gen/` and `job/outputs/results/`, to show that all
     are after 01:51:49 UTC on 2026-10-06;
   - that no other R-10 output folder exists;
   - the per-item generation logs (0 errors, ms per note).
4. **R-10b outputs.** List `experiments/2026-10-05-R-10b-h1b-captured-share/job/outputs/gen/*`
   to confirm that only its 42 decision pieces were generated, and that no `analyze` output
   exists.
5. **Determinism.** Regenerate 2 fresh items at top-p 0.95 and 1.0 (seed 0) and compare them
   with the stored samples, since GPU sampling may not be bit-stable.
6. **Velocity overshoot vs conditioning.** Does b depend on the conditioning velocity or on
   tempo? This needs `gen_items` plus the samples.

### 11. Proposed EXPERIMENTS.md row (for the lead)

| [2026-10-05-R-10-h1b](experiments/2026-10-05-R-10-h1b/README.md) | 2026-10-05 | R-10 | H1b | Run 2026-10-06 on the RTX 5080 from 28c5a01 (clean tree; digests and ridge match the Mac). Frozen SyMuPe EncDec-base, K = 16, on 56 fresh PianoCoRe pieces (54 works, 1,691 renditions, 92% Aria-AMT) unseen by its pretraining. **H1b-consensus (registered, top-p 0.95): median mean-curve R²c velocity 0.150 [0.022, 0.283], log IOI 0.073 [0.032, 0.180] = falsified on both**; top-p 1.0 0.098 / -0.178 (same reading); as-registered 59 pieces the same. Analytic 16-expert oracle 0.877 / 0.881 (ratio 0.17 / 0.08). Shape vs amplitude: r 0.67 / 0.55 (r² 0.45 / 0.31, oracle 0.89 / 0.88), b 1.10 / 0.93. Score-feature ridge 0.246 / 0.054 (velocity inconclusive); frozen - ridge no detectable R²c difference, but the model's r is higher by 0.13 / 0.25. H1b-axes (top-p 1.0, 12 pieces) 0.437 [0.383, 0.610], inconclusive. R10u dev (74 unseen, R-06 formula) 0.329 / 0.144 (R-07 formula log IOI 0.127). | Confirmed with caveats (scoped): the registered reading follows exactly and reproduces from the committed CSVs; order, blindness and the R-10b separation verified. Caveats (auditor, post hoc): shape is the same as on dev (velocity r 0.672 vs 0.665); the velocity drop is amplitude on a flatter consensus (target s.d. 7.3 vs 9.3, b 1.10 vs 0.94). A single dev-chosen scale gives 0.362 [0.260, 0.456] / 0.271 [0.233, 0.321], inconclusive on both, so 'falsified' is a property of the raw sampled mean curve; no scaling reaches 0.50 (best per-piece r² 0.45 / 0.31). Velocity falsified flips to inconclusive without J. S. Bach (0.205). H1b-axes is near a structure-free envelope sampler (0.363 of the oracle; null-adjusted 0.16 [0.01, 0.33]). No sign of leakage (sibling split runs the other way; Transkun V2 renditions no closer). | eval-auditor 2026-10-06 |

### 12. Proposed DECISIONS text (for the lead)

- **2026-10-06, lead: R-10 after audit (eval-auditor, Confirmed with caveats, scoped).**
  - **H1b, as operationalised on 2026-10-05, is falsified for frozen SyMuPe EncDec-base.** The
    raw mean of 16 samples (top-p 0.95, conditioned on the panel's median tempo and loudness)
    explains 0.15 of the velocity and 0.07 of the log IOI consensus variance on 56 unseen,
    less-played PianoCoRe pieces. Sixteen experts reach about 0.88.
  - Recorded with it:
    - The score alone gets the shape of the consensus partly right: r 0.67 / 0.55.
    - Even a perfectly calibrated amplitude would explain at most 0.45 / 0.31, below the plan's
      0.50.
    - A development-chosen amplitude scale gives 0.36 / 0.27, which is between the bars.
  - The plan's H1b row is marked "falsified (R-10, scoped); score-predictable share of the
    expert consensus about 0.3-0.45 of variance at best". The wording of the hypothesis is
    unchanged.
  - **H1b-axes**: inconclusive as registered, and near a structure-free floor (post hoc). It is
    not evidence that a model's samples span the expert axes.
  - **For the scorer:**
    - Interpretation stays anchored to expert performances of the same piece: the R-02 basis
      and the expert band.
    - No model-predicted consensus replaces expert references where they exist.
    - For pieces without references, a model-predicted curve may serve at most as a
      low-confidence prior, shrunk by about 0.63 (the development scale), and is labelled as
      such. It is not a scoring reference.
  - **For the research bet** (CLAUDE.md: "piano performance quality is a low-dimensional
    function of a low-dimensional, score-conditioned expressive space"):
    - R-10 tests predictability from the score, not dimensionality. R-01 (quality is
      low-dimensional) and R-02 (3-5 shared components per piece) are untouched.
    - What fails is the strong reading that the score determines the shared expressive
      consensus. A 25M-parameter score-to-performance model recovers at most about half of it.
    - "Score-conditioned" should therefore mean "conditioned on the piece through expert
      performances of it", not "predicted from the score alone".
    - Proposed CLAUDE.md edit, for Henry: "... a low-dimensional, piece-conditioned expressive
      space (anchored by expert performances of the piece; R-10: the score alone predicts only
      part of the expert consensus)".
  - **Pianist Transformer (`gen_pt`) and `dev_gen`** are reported when they arrive, with the
    same decomposition. They cannot change the reading, and giving either a deciding role needs
    a new pre-registration.
  - **No R-10 follow-up chasing the 0.50 bar** on the same statistic. The fresh pool is used up
    (all 65 qualifying pieces), and the best-scale ceiling is below 0.50.
    - If calibrated predictors (dev-chosen shrinkage, model + ridge stacking) matter for the
      product, they are a new pre-registered ticket on new pieces: another corpus or a
      leave-composer-out design.
    - Any captured-share statistic must report an envelope-surrogate sampler floor.

Reproduce (Mac): `uv run python experiments/2026-10-05-R-10-h1b/audit_checks.py`. It needs
`artifacts/sets/fresh`, the expert items rebuilt on the Mac, for section 8; pass
`--skip-envnull` without them.

### Addendum (secondary arms, 2026-10-10)

Scope: `gen_pt` and `dev_gen` from 9a1e9cb. All non-deciding. **The verdict above stands.**
Script: `audit_addendum.py` (Mac, seconds). `audit_checks.py` section 8 now also scores
pt_frozen, and its earlier output is unchanged on the refreshed files.

**1. The gen_pt restart is clean.**
- `logs/gen_pt.log` lists 65 completions with 65 distinct items, exactly the fresh item list,
  each with the same note count as in the p95 log.
  - Before the pause: 12 items, `bach_bwv852_fugue` to `chaminade_op61`. The 13th,
    `chopin_op33_no3`, had started ("0/2"), and the log breaks off there.
  - After the restart at 04:37:06 UTC 2026-10-10: the other 53, starting with
    `chopin_op33_no3`, in sorted order, none repeated.
- `pt_gen.py` skips any item whose output exists. It writes each output to `.tmp.npz` and
  renames it only once the item is finished. So the killed item left no partial file, and no
  item mixes samples from the two sessions.
- No FAIL, Traceback or out-of-memory line appears in any log. stderr is captured, because
  `gen_stage` pipes `2>&1` through tee.
- None of the 4 per-item JSONs has an `error` entry. Their counts are p95 65, p100 65, dev 91
  and pt 53.
- Summary rows: pt_frozen has 65 rows in fresh_as_registered and 62 in fresh (3 pieces
  excluded under A1).
- The refresh left every primary arm unchanged. The frozen_p95, frozen_p100 and ridge rows, the
  summary arms, the experts block and the headline all equal 2e90db7 exactly.
- Checkpoint: the JSON records `C:/Users/Vuduc/r07/models/pianist-transformer-rendering`, K 16,
  top-p 1.0, seed 0. That is the `run.sh` default. Job files and pieces are unchanged from
  28c5a01 to 9a1e9cb.
  - The JSON covers only the restart session (see 4).
  - The progress bars are ASCII before the pause and Unicode after it, so the two sessions ran
    under different console encodings.
  - The time per batch is the same in both sessions, about 25-26 s.
  - Nothing committed records the 12 pre-pause items' model, or the HF revision of the box
    checkpoint (the Mac dry run used 8f156820). This is a box-only check.
- Dev: 91 of 91 items were generated, and 90 are scored. Bartók Sz.56 is not scored because it
  keeps 3 renditions after the match_share filter. 85 pieces are primary (80 without R3).

**2. Reproduction and fix 6.** Every pt and dev median, CI, n, reading and paired difference in
the run record reproduces exactly from the CSVs, and R²c = 2rb - b² holds per piece. Medians
are given with work-cluster CIs.

| Arm (pieces) | target | r | b | R²c | R²c at b = 1 | r² (best scale) |
|---|---|---|---|---|---|---|
| PT, fresh (56) | velocity | 0.650 [0.569, 0.701] | 1.073 [1.017, 1.157] | 0.061 [-0.127, 0.273] | 0.301 [0.139, 0.402] | 0.423 [0.324, 0.491] |
| PT, fresh (56) | log IOI | 0.391 [0.316, 0.492] | 0.830 [0.676, 0.939] | -0.045 [-0.176, 0.078] | -0.218 [-0.367, -0.016] | 0.153 [0.100, 0.242] |
| PT, as registered (59) | velocity / log IOI | 0.617 / 0.370 | 1.072 / 0.824 | 0.050 / -0.071 | 0.234 / -0.261 | 0.381 / 0.137 |
| dev_gen, R10u (85) | velocity | 0.679 [0.620, 0.704] | 0.974 [0.935, 1.016] | 0.324 [0.254, 0.445] | 0.357 [0.239, 0.409] | 0.461 [0.384, 0.496] |
| dev_gen, R10u (85) | log IOI | 0.524 [0.479, 0.555] | 1.124 [1.015, 1.238] | -0.173 [-0.304, -0.061] | 0.049 [-0.041, 0.109] | 0.275 [0.230, 0.308] |
| dev_gen, no R3 overlap (80) | velocity / log IOI | 0.681 / 0.526 | 0.977 / 1.128 | 0.324 / -0.182 | 0.362 / 0.053 | 0.463 / 0.277 |
| dev_gen, unseen 74 | velocity / log IOI | 0.681 / 0.518 | 0.962 / 1.074 | 0.330 / -0.104 | 0.362 / 0.036 | 0.463 / 0.268 |

- **PT velocity: same shape as SyMuPe, and also an overshoot.** Paired against frozen_p95, r
  differs by -0.008 [-0.043, 0.036]. At b = 1 it would read 0.301, which is inconclusive.
- **PT log IOI: a pure shape failure.** r is 0.39, against 0.55 for SyMuPe (paired +0.127
  [0.073, 0.162] for SyMuPe). Even at the experts' amplitude R²c would be -0.22, and the best
  scale reaches only 0.15.
- **"PT below the ridge on velocity" (-0.125 [-0.260, -0.020]) is the shrinkage artefact from
  section 5.** On shape, PT beats the ridge: r +0.129 [0.074, 0.151] on velocity and +0.162
  [0.075, 0.180] on log IOI, higher on 82% / 70% of pieces.
- **PT H1b-axes.** The ratio is 0.467 [0.369, 0.655]. Null-adjusted against the envelope
  sampler it is 0.20 [0.01, 0.30], and on 3 of 12 pieces PT is at or below the envelope.
- **PT unseen-ness was not checked.** The fresh set was screened against PERiScoPe v1.0 pairs
  (SyMuPe), not against PT's training data.
- **The dev summary headline says "(frozen_p100, registered)".** That is the summariser's
  template. The dev readings are not registered readings and must not be quoted as such.

**3. The frozen-model statement holds at top-p 1.0, with a small shape share.**
Here both sets use the same model and top-p: fresh p100 (56) against dev_gen on the unseen 74.

| | fresh | dev | Mann-Whitney p |
|---|---|---|---|
| velocity r | 0.652 | 0.681 | 0.10 |
| velocity b | 1.089 | 0.962 | 0.005 |
| velocity target s.d. | 7.34 | 9.39 | 4e-5 |
| velocity model s.d. | 7.84 | 9.23 | 0.008 |
| velocity R²c | 0.098 | 0.330 | 0.001 |
| log IOI r | 0.520 | 0.518 | 1.0 |
| log IOI b | 1.214 | 1.074 | 0.32 |

- **Velocity.**
  - The target flattens by 22% and the model only by 15%.
  - At b = 1 the gap is 0.303 against 0.362, so about 0.06 of the 0.23 drop is shape. The
    shape difference is not significant.
  - "Same shape, the velocity drop is amplitude" therefore holds. Word it as "mostly amplitude"
    at top-p 1.0.
- **Section 6 replicates with the box's own dev samples.**
  - One scale chosen on dev_gen (velocity 0.625, the same as the 0.627 from the R-07 samples;
    log IOI 0.456) gives fresh p100 0.350 [0.240, 0.444] and 0.242 [0.183, 0.302].
  - Both are **inconclusive**.
- **The negative log IOI at top-p 1.0 is a sampling effect, not a fresh-set effect.**
  - On the same pieces, top-p 1.0 minus 0.95 raises log IOI b by 0.19 [0.16, 0.23] on dev and by
    0.235 [0.191, 0.277] on fresh, while r falls by 0.02.
  - Dev log IOI is therefore negative too (-0.17), against +0.144 at top-p 0.95 (R-07
    samples).
  - The dev_gen log IOI value is not comparable with R-07's 0.127 / 0.144.

**4. Run record accuracy.**
- **Accurate:**
  - the timeline (02:32:11 start; 12 done at the pause, the 13th started; the 03:13:46 pause
    fits the item durations summed from the log);
  - the restart (04:36:57, against the log header at 04:37:06, the time `run.sh` takes to start);
  - "only the item in progress was regenerated";
  - 65 / 65 and 91 / 91;
  - the primary numbers being unchanged.
- **Imprecise:**
  - "0 errors in every `_log_gen.json`" is true, but the PT JSON lists only the 53 items
    generated after the restart. `pt_gen.py` writes its log at exit, and the killed process
    never exited. The 12 pre-pause items are documented only by `logs/gen_pt.log`.
  - Exit codes and `gen_complete` counts are not in any log, because `gen_stage` does not tee
    them.
  - `meta` was not re-run at the restart, so the box tree state (HEAD, diff) on 2026-10-10 is
    not recorded.
  - The reboot time cannot be verified from the logs.
  - Post-audit correction 2 says the amendment block is at "lines 448-548". It now starts at
    line 480. The anchor hash still gives 6215a057...4089, and `head -n 409` still gives
    d679394f...5f09.

**5. Post-audit correction 3 is closed.** `results_box/logs/` now holds every stage log:
- meta, sets, ridge;
- gen_frozen_p95 (header 01:56:55 UTC) and gen_frozen_p100 (02:12:31), both after the 01:51:49
  driver start;
- dev_r07 (with and without overlap);
- summarize and summarize_as_registered (3 appended runs each, with identical piece lines);
- gen_pt, dev_gen and the two summarize_dev logs.

`gen_logs/` holds the per-item JSONs (ms per note). This also covers the per-item part of
section 10.3. The output mtimes remain box-only. `summarize.log` is not valid UTF-8; read it as
latin-1.

**Still box-only:**
- the model, k, top-p and seed stored in the 12 pre-pause PT `.npz` files, and the HF revision
  of the PT checkpoint;
- the other section 10 items.

**Proposed addition to the EXPERIMENTS.md R-10 row (for the lead):** "Secondary, non-deciding,
audited 2026-10-10: Pianist Transformer (top-p 1.0, 56 pieces) R²c 0.061 / -0.045, r 0.65 /
0.39, b 1.07 / 0.83, R²c at b = 1 0.30 / -0.22: SyMuPe's velocity shape, a worse log IOI shape;
it beats the ridge on r, +0.13 / +0.16. dev_gen (SyMuPe top-p 1.0, R10u 85): 0.324 / -0.173,
r 0.68 / 0.52, b 0.97 / 1.12. Fresh vs dev at top-p 1.0: velocity r 0.65 vs 0.68 (p 0.10),
b 1.09 vs 0.96, so the drop is mostly amplitude. A dev_gen scale gives 0.350 / 0.242
(inconclusive). The gen_pt restart is clean (65 items, each once)."

## Post-audit corrections (2026-10-06)

Text fixes 1-5 from `## Audit (2026-10-06, eval-auditor)`, section 9 (author, ml-researcher). The
hashed header, the amendment block and the Audit section are unchanged; the registered verdict
stands. Every number below was re-run on the Mac with `audit_checks.py` (with the envelope null)
from the committed `results_box/` CSVs and matches the Audit. All are post hoc and non-deciding
except the registered readings.

**1. Headline (replaces the provisional headline in the run record).** H1b-consensus, registered
(frozen SyMuPe EncDec-base, mean of 16 samples at top-p 0.95, 56 pieces): **falsified on both
targets**, velocity R²c 0.150 [0.022, 0.283], log IOI 0.073 [0.032, 0.180]; top-p 1.0 gives the
same reading (0.098 / -0.178). Read it as a calibration-and-shape result, not as "no shape":

| Target | r (shape) | b (amplitude) | R²c (registered) | R²c at b = 1 | best per-piece scale (r²) | one dev-chosen scale | 16-expert oracle |
|---|---|---|---|---|---|---|---|
| velocity | 0.672 [0.567, 0.709] | 1.100 [0.999, 1.196] | 0.150 | 0.344 [0.135, 0.419] | 0.452 [0.322, 0.503] | 0.362 [0.260, 0.456], inconclusive | r² 0.895, b 1.016, R²c 0.883 |
| log IOI | 0.553 [0.512, 0.607] | 0.926 [0.750, 1.057] | 0.073 | 0.106 [0.023, 0.215] | 0.306 [0.262, 0.369] | 0.271 [0.233, 0.321], inconclusive | r² 0.875, b 1.014, R²c 0.856 |

- The model gets part of the consensus shape (r 0.67 / 0.55, r² 0.45 / 0.31 against about 0.89 /
  0.88 for 16 experts). Velocity "falsified" also needs the amplitude overshoot (b 1.10): at b = 1
  it would read inconclusive (0.344).
- One amplitude scale fitted on the R10u development pieces (s 0.627 / 0.638) and applied
  unchanged gives 0.362 / 0.271: **inconclusive on both targets**.
- **No scaling reaches 0.50**: even the in-sample best scale per piece gives 0.452 / 0.306.
- So "falsified" is a property of the raw sampled mean curve; the score-predictable share of the
  expert consensus is about 0.3-0.45 of its variance at best.

**2. Amendment hash command.** The run record was inserted above the amendment block, so
`sed -n '417,517p'` now hashes the wrong lines. The anchor form, which does not depend on line
numbers, is:
`awk '/^## Pre-run amendments/{f=1} f&&n<101{print;n++}' README.md | shasum -a 256`
= `6215a0577f79d72fae1d6fb45d8324683388bf6bb94f95f8fb6bbd8b22dc4089` (re-checked 2026-10-06; the
block is now lines 448-548, after the run record and its post-audit pointer, and unchanged). Appended to `artifacts/prereg_amendment_sha256.txt`.

**3. Box logs.** The run record says the logs were copied to `results_box/`. None are there:
`results_box/` holds `run_meta.json`, `ridge/ridge.json`, `results/` (fresh,
fresh_as_registered, r10u_r07, r10u_r07_no_overlap) and the sets' json / csv files, and no `*.log`
file. The logs (and the per-item generation logs) are still on the box; the box can push them
with the `gen_pt` / `dev_gen` outputs.

**4. H1b-axes against a structure-free floor.** Registered reading: inconclusive (frozen_p100
ratio 0.437 [0.383, 0.610], 12 pieces; top-p 0.95: 0.528 [0.469, 0.700]). The registered floor
was a random 15-dimensional subspace (0.064 of the oracle), which is a weak null. A
structure-free sampler (16 envelope surrogates of the held-out experts' own deviations: per-row
phase randomisation, per-onset s.d. restored) scores **0.363 [0.277, 0.461]** of the 16-expert
oracle. Null-adjusted, (cap - cap_env) / (cap_oracle - cap_env): top-p 1.0 **0.16 [0.01, 0.33]**,
top-p 0.95 0.30 [0.09, 0.45]; on 3 of 12 pieces the top-p 1.0 samples capture no more than the
surrogates. The model's samples are near a structure-free floor; the "6-12 experts" scale in the
pre-registration does not describe 0.44 and is withdrawn as a description of the result.

**5. Scope.** "Falsified" applies to the registered model statistic (the raw mean curve of frozen
SyMuPe EncDec-base's samples, conditioned on the panel's median tempo and loudness, on 56
less-played PianoCoRe pieces unseen in PERiScoPe v1.0 pairs, against a consensus of mostly
Aria-AMT transcriptions, median 28 per piece). It is not a statement about score-only prediction
in general: the score-feature ridge's own velocity reading is **inconclusive (0.246 [0.198,
0.299])** (log IOI 0.054, falsified), because a regression shrinks its predictions (b 0.44 /
0.29). On shape the model beats the ridge (r +0.129 [0.083, 0.164] / +0.245 [0.139, 0.296]).

**6. Pending.** `gen_pt` (Pianist Transformer) and `dev_gen` are reported with the same r / b /
R²c-at-b = 1 columns when the box pushes them. They do not decide.

**6, closed (2026-10-10).** The box pushed `gen_pt` and `dev_gen` (9a1e9cb). The r, b, R²c, R²c
at b = 1 and best-scale r² of both arms, with work-cluster CIs, are in the Audit's
`### Addendum (secondary arms, 2026-10-10)`, table in item 2; I re-ran `audit_addendum.py` on the
Mac and every number matches. Neither arm decides anything.
- Pianist Transformer (frozen, top-p 1.0, 56 pieces): R²c velocity 0.061, log IOI -0.045; r 0.65 /
  0.39.
- dev_gen (frozen SyMuPe, top-p 1.0, R10u, 85 pieces): R²c velocity 0.324, log IOI -0.173.
- **Fresh vs development at top-p 1.0 (same model, same top-p).** The velocity drop is mostly
  amplitude: R²c falls by about 0.23 (0.330 on the 74 unseen dev pieces to 0.098 on fresh), and
  at b = 1 the gap is 0.362 vs 0.303, so about 0.06 of it is shape (r 0.681 vs 0.652, p 0.10).
  One scale chosen on dev_gen gives fresh 0.350 / 0.242, inconclusive on both targets.
- **dev_gen's negative log IOI is a top-p effect.** On the same pieces top-p 1.0 raises log IOI b
  by about 0.2 against top-p 0.95 (dev +0.19 [0.16, 0.23], fresh +0.235 [0.191, 0.277]) with r
  almost unchanged. So dev_gen's -0.173 is not comparable with R-07's 0.144 (R-06 formula) or
  0.127 (R-07 formula), which are top-p 0.95.
- **Pianist Transformer vs the ridge.** Its R²c is below the ridge on velocity (-0.125 [-0.260,
  -0.020]), but that is the ridge's shrinkage (b 0.44), as in correction 5. On shape it beats
  the ridge: r +0.13 [0.07, 0.15] velocity, +0.16 [0.08, 0.18] log IOI. Its unseen status was
  checked only against SyMuPe's pretraining pairs, not against Pianist Transformer's training
  data.
- **Dev summary headline.** `results_box/results/r10u_dev*/summary.json` say "H1b-consensus
  (frozen_p100, registered): ...". "registered" there is the summariser's template wording. The
  development readings are not registered readings; quote them as "dev_gen, frozen_p100:
  velocity inconclusive, log IOI falsified". The run record does not quote them; the fresh
  headline it quotes is registered.
- **Run-record imprecisions** (Addendum item 4):
  - "0 errors in every `_log_gen.json`" is true, but the Pianist Transformer JSON covers only
    the 53 items generated after the restart. The 12 pre-pause items are documented only by
    `logs/gen_pt.log`.
  - Exit codes, `gen_complete` counts and the box git state at the 2026-10-10 restart are not
    recorded (`meta` was not re-run).
  - The amendment block now starts at line 480, not 448 as correction 2 says. The anchor-form
    hash is unchanged (below).
- Hashes re-checked 2026-10-10: `head -n 409 README.md` = d679394f...5f09; anchor form
  `awk '/^## Pre-run amendments/{f=1} f&&n<101{print;n++}' README.md | shasum -a 256` =
  6215a057...4089.
