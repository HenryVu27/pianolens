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
