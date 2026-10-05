# F-05e: do LLM phrase boundaries recover the per-phrase tempo-shaping signal of annotated boundaries?
Ticket: F-05e    Hypothesis: validation of the H4 / R-09 secondary tempo channel (`phrase_tempo_shaping` `concave_excess`) with LLM boundaries    Status: Provisional (pre-registered 2026-09-28; no tempo measure has been computed with LLM boundaries yet)

Prepared by `feature-engineer`. Nothing in this header may be edited after results exist.
Corrections go in new sections at the end.

## Question

F-05c found that the per-phrase tempo measure `concave_excess` (share of phrases whose smooth
tempo arc is slower at both edges, minus the same share with the boundaries shifted by ±2 bars)
is largest with DCML-annotated phrases: +0.42 on the 21 held-out Batik movements, against +0.21
for the F-05c cadence detector and +0.24 for the proxy. R-08a-d found that blind LLM annotators
recover DCML phrase ends at end F1 ≈ 0.74-0.82 (±1 beat), but that on Romantic music they often
segment finer than DCML (R-08d R5; R-08c Q3). DECISIONS 2026-09-28 (R-08d) requires that any
phrase measure fed by LLM boundaries be robust to that over-segmentation, and re-validated
before use.

**On the movements that have both blind LLM annotations and performances, does
`concave_excess` computed with LLM phrase boundaries recover the value obtained with DCML
boundaries, and does it beat the cadence detector? Does a merge rule that undoes
over-segmentation change the answer?**

Secondary: the same question for phrase-aware structural coherence (tempo R² without markings,
`phrase_detail` features, F-05b `ann_detail` style).

## Data (read-only; nothing here is an annotation)

- **LLM phrase events**, already produced and audited (Confirmed with caveats):
  - R-08a `annotations/M1-M5.json` (run "a"), R-08b `annotations_B1/`, `annotations_B2/`
    (undisguised reruns) and `annotations_A/D1-D5.json` (disguised; D ids mapped to M ids by
    `artifacts/disguise.json`, events mapped back through R-08b's disguised bar tables). Four runs
    per Batik movement.
  - R-08d `annotations_A/R1-R5.json`, `annotations_B/R1-R5.json`. Two runs per movement.
  - R-08c (J. C. Bach, Q1-Q5): **no performances exist** (0 in PianoCoRe, not in Batik; D-07
    piece-id table). Excluded from every tempo computation; stated here, not a result.
- Events are mapped to performed-score beats with the scorers' own code (`map_events` from
  R-08a `score.py`, default options: snap to the nearest onset within 0.5 beat, propagate
  pointer bars; R-08b `inputs_A` for the disguised run; R-08d `movement_inputs` for R1-R5).
- **DCML boundaries:** the same ground truth the scorers used (F-05c `cands.pkl` for Batik,
  D-13 `cands.pkl` for the Romantic pieces): starts `{`/`}{`, ends `}`/`}{`.
- **Performances:**
  - Batik-plays-Mozart (one pianist, sensor MIDI, ground-truth alignment): M1 kv330_2, M2
    kv333_1, M3 kv533_1, M4 kv330_3, M5 kv457_3. The scores are the D-11 performed scores that
    the LLM renderings were built from, so no mapping is needed.
  - PianoCoRe tier A (transcribed; RAScoP alignments to the refined score MIDI): R1
    tchaikovsky_op37a_no6 (403 tier A), R2 chopin_op7_no4 (20), R3 schumann_op15_no7 (867).
    Only performances aligned to the full `score_MS_refined.mid` (not the abridged
    `score_MS_mini_refined.mid`). At most **30 per piece**, drawn with seed 20261002 (all if
    fewer). R4 grieg_op57_no1 and R5 liszt_s160_no2 have **0 tier A** performances (no note
    alignment), and MazurkaBL has no op. 7/4: they are excluded.
  - Secondary set, PianoCoRe Mozart: the same 30-per-piece draw for mozart_k330_mv2,
    k333_mv1, k330_mv3, k457_mv3 (K.533/1 is not in PianoCoRe).
- **Score-to-score mapping for PianoCoRe.** The DCML (or Batik) score and the PianoCoRe refined
  score are aligned by DTW on the sequence of unique onsets, cost = 1 − Jaccard of the MIDI
  pitch sets (librosa `sequence.dtw`). Each boundary (a source-score onset beat, or the nearest
  onset) maps to the first PianoCoRe onset its onset is paired with. Mapping quality is reported
  as the share of mapped boundaries whose two onsets have identical pitch sets. **A movement
  whose boundary pitch-set agreement is below 0.80 is excluded** from the PianoCoRe analyses and
  reported as such.
- Tier A PianoCoRe is transcribed MIDI. R-08d did not license LLM boundaries *from* transcribed
  MIDI; here the LLM read the score only, and the transcription enters only through the tempo
  curve. Disclosed as a threat, not a licence question.

## Boundary sources (fixed now)

For every movement, `phrase_tempo_shaping(ap, starts, tempo=tempo_model(ap))` with its default
null (mean of the −2 and +2 bar circular shifts) and `min_beats=3`:

| Source | Phrase starts |
|---|---|
| `dcml` | DCML starts (reference) |
| `llm` | the LLM run's `phrase_start` events (primary LLM source) |
| `llm_m4` | `llm` after `merge_short_phrases(min_bars=4)` (primary robust variant) |
| `llm_m8` | `llm` after `merge_short_phrases(min_bars=8)` (sensitivity) |
| `llm_cad` | the first LLM start, plus each LLM start that follows (within 2 bars) an LLM `phrase_end` typed PAC or HC (cadence-level grouping; annotation-free) |
| `llm_oracle` | for each DCML start, the nearest LLM start within ±1 bar, others dropped (**oracle diagnostic**: uses DCML, not usable in the product) |
| `dcml_m4` | DCML after the same 4-bar merge (shows what the merge does to the reference) |
| `cadence` | the F-05c detector starts (Batik: `cadence_bounds` on the F-05c cache; Romantic: R-08d's `detector()`) |
| `cadence_m4` | `cadence` after the 4-bar merge |
| `proxy` | Batik: F-05c `proxy_split`; PianoCoRe: `score_basis(score)` phrases on the refined score |
| `grid4` | every 4th downbeat (null-like baseline) |

`merge_short_phrases(starts, min_bars, beats_per_bar, lo, hi)` (new, `features/shaping.py`):
while any phrase (start to next start; the last ends at the last onset + 1 beat) is shorter than
`min_bars` bars and more than one phrase remains, take the shortest phrase (earliest on ties) and
merge it with its shorter neighbour (the following one on ties) by deleting the boundary between
them. `beats_per_bar` is the score's (as `phrase_tempo_shaping` uses). The merged boundaries get
their own shifted null, as any boundaries do.

LLM values per movement are the mean over that movement's runs (4 for Batik, 2 for R1-R3);
PianoCoRe values are the mean over the drawn performances.

## Primary analysis and decision rule

- **Units:** the 8 movements M1-M5 (Batik) and R1-R3 (PianoCoRe), each counted once.
- **Primary statistic:** Δ = mean over the 8 movements of (`llm` − `dcml`) `concave_excess`.
- **Recovered:** Δ ≥ −0.10 (point estimate) **and** the mean paired (`llm` − `cadence`) > 0.
- **Not recovered:** Δ < −0.10.
- **Robust variant, same rule:** Δ_m4 = mean(`llm_m4` − `dcml`). Reported next to the
  primary. If `llm` is not recovered but `llm_m4` is, the merge is the recommended form.
- Intervals: the t-interval (7 df) and a percentile bootstrap over movements (10,000, seed
  20261002) for Δ, Δ_m4 and (`llm` − `cadence`); the Batik-only (5) and PianoCoRe-only (3)
  subsets are reported separately. The t-interval is descriptive; the point-estimate rule
  decides (as R-08a-d).
- **Why −0.10:** F-05c's annotated-minus-cadence gap on held-out Batik was +0.21. A loss of 0.10
  keeps more than half of the annotation advantage over the detector.

### Can each branch be reached?

The per-movement SD of paired differences in `concave_excess` between boundary sources is not
known here; F-05c's per-movement excesses are single-performance values that vary by about
0.15-0.2. With n = 8 the t half-width would be about 2.36 × 0.15 / √8 ≈ 0.13, larger than the
0.10 margin. So both point-estimate branches are reachable, but **no interval-based claim is
expected**: the interval will very likely straddle −0.10. The verdict will be worded as a point
estimate with an uninformative interval, as in R-08d.

## Secondary analyses (reported, not decided)

1. **Phrase-aware structural coherence**, tempo channel, R² without markings (F-05b / F-05c
   pipeline: `score_basis(..., phrase_boundaries_beats=starts, phrase_ends_beats=ends,
   BasisConfig(phrase_detail=True, phrase_max_bars=NOSPLIT))`, `channel_data`, `_cv_ridge`,
   `ShapingConfig(clip_to_train=True)`) for `dcml`, `llm`, `llm_m4`, `cadence` and the default
   proxy basis. Ends: the source's own ends (LLM `phrase_end` events; for merged sources, the
   last source end at or before each retained start plus the last end overall). Reported with
   the paired mean (`llm` − `dcml`); F-05b's reference gap (annotated − proxy) is +0.07.
2. `arc_r2_excess` for every source, same table.
3. Per-movement tables for every source, with the number of phrases, and per LLM run.
4. Over-segmentation diagnostic: per movement, the ratio of LLM to DCML phrase counts, and the
   change `llm_m4` − `llm` against it.
5. The PianoCoRe Mozart secondary set (4 movements): the same table, to see whether Batik's
   one-pianist result holds over many transcribed performers.
6. **Harness check (must pass):** on Batik, `dcml` and `cadence` `concave_excess` per movement
   must equal the F-05c `phrase_tempo.csv` rows (`ann`, `cadence`) for those 5 movements.

## Threats to validity (known before running)

- n = 8 movements, one Batik pianist for five of them, and three Romantic pieces with
  transcribed performances. No per-composer claim is possible.
- The LLM runs were not made for this purpose; their levels (and the DCML levels) are what
  they are. The merge target of 4 bars is a convention (Classical phrase norm), not tuned here;
  8 bars is a sensitivity.
- The ±2-bar shifted null is less out of phase for long phrases, so merged (longer) phrases have
  a weaker null; `concave_excess` is not strictly comparable across phrase lengths. The `dcml_m4`
  row shows the size of that effect on the reference.
- PianoCoRe boundaries go through a score-to-score DTW; errors there hit every source equally,
  but may lower all excesses.
- DCML labels predate the model cutoff (R-08c/d caveat): exposure not excluded.

## Method

`run.py` (one-off; reusable `merge_short_phrases` in `features/shaping.py` with a synthetic
test). Steps: load LLM events and map them; build every source per movement; Batik: one aligned
performance each; PianoCoRe: DTW map, draw, load, `tempo_model`, `phrase_tempo_shaping` per
source; coherence; tables; summary. Outputs in `artifacts/` (gitignored).

## Command

```
OMP_NUM_THREADS=1 uv run python experiments/2026-09-28-F-05e-llm-phrase-measures/run.py
```

## Run record (2026-09-28, feature-engineer)

- Pre-registration (the header above, up to and including "## Command") sha256
  `d7205e40...9b18` of the whole file as first written, 18:38 CDT, before any tempo measure
  with LLM boundaries was computed. Not edited since; everything below is appended.
- Code: git `3af124d` plus uncommitted changes. The F-05e diff to `src/pianolens/features/shaping.py`
  and `tests/features/test_shaping.py` (`merge_short_phrases` and two tests) hashes to
  `fe18cde0b28d` (sha256 of `git diff`, first 12). `run.py` is new. Other agents' uncommitted
  changes (report, compare) are unrelated.
- Data: Batik-plays-Mozart 9c5f700; PianoCoRe tier A (Zenodo v1.0, refined.zip); DCML Romantic
  corpora as in D-13; F-05c `data/interim/phrase_f05c/cands.pkl` and D-13
  `data/interim/dcml_romantic/cands.pkl`.
- Seed 20261002 (performance draw, bootstrap). Wall time: about 8 min (compute, 6 processes)
  twice (the second run only computed the PianoCoRe Mozart units) plus 10 s for the summary.
- Command: as registered (`run.py compute`, then `run.py summary`). Outputs:
  `artifacts/rows/*.parquet`, `artifacts/summary.txt`, `artifacts/concave_excess_per_movement.csv`,
  `artifacts/compute.log`.

### Deviation (disclosed)

- The first run crashed on the PianoCoRe Mozart units: their full refined score is called
  `score_ATEPP_refined.mid`, not `score_MS_refined.mid` as the header's filter assumed. The filter
  was changed to "any refined score except `*_mini_refined.mid`", with an assert that exactly
  one full score remains per piece. This matches the header's intent (full score, not the
  abridged one). It was made after the Batik and Romantic units had finished but before any
  PianoCoRe Mozart unit ran. The primary units are unaffected: the Romantic pieces have only
  `score_MS_*` files, and their rows are the cached first-run rows.

## Results

All numbers are from `artifacts/summary.txt`.

**Harness: PASSED.** For all 5 Batik movements, `dcml`, `cadence`, `proxy` and `grid4`
`concave_excess` equal the F-05c `phrase_tempo.csv` rows exactly.

**Score mapping (PianoCoRe).** Boundary pitch-set agreement: R1 0.942, R2 0.969, R3 0.957 (all
included). Secondary Mozart: K.330/2 0.949 and K.330/3 0.860 were included; K.333/1 (0.665) and
K.457/3 (0.757) were **excluded by the registered rule** (their refined scores cover about 69% and
91% of onsets with exact matches; the cause was not investigated).

### Primary: `concave_excess` per movement (LLM = mean over runs)

| Unit | Piece | Perfs | DCML | LLM | LLM m4 | LLM m8 | LLM cad | LLM oracle | DCML m4 | Detector | Proxy | Grid4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | K.330/2 (Batik) | 1 | 0.600 | 0.682 | 0.667 | 0.273 | 0.603 | 0.600 | 0.579 | 0.441 | -0.108 | -0.082 |
| M2 | K.333/1 (Batik) | 1 | 0.483 | 0.505 | 0.466 | 0.012 | 0.496 | 0.479 | 0.483 | 0.433 | 0.279 | 0.069 |
| M3 | K.533/1 (Batik) | 1 | 0.377 | 0.345 | 0.371 | 0.158 | 0.251 | 0.388 | 0.405 | 0.281 | 0.191 | -0.035 |
| M4 | K.330/3 (Batik) | 1 | 0.439 | 0.304 | 0.248 | 0.138 | 0.284 | 0.398 | 0.439 | 0.133 | 0.214 | 0.272 |
| M5 | K.457/3 (Batik) | 1 | 0.360 | 0.351 | 0.490 | 0.405 | 0.354 | 0.362 | 0.360 | 0.176 | 0.261 | 0.038 |
| R1 | Tchaikovsky op. 37a/6 | 30 | 0.560 | 0.413 | 0.441 | 0.314 | 0.408 | 0.537 | 0.556 | 0.340 | -0.022 | -0.117 |
| R2 | Chopin op. 7/4 | 18 | 0.368 | 0.158 | 0.048 | 0.067 | 0.018 | 0.364 | 0.281 | -0.225 | 0.225 | 0.288 |
| R3 | Schumann op. 15/7 | 30 | 0.598 | 0.583 | 0.333 | 0.294 | 0.388 | 0.583 | 0.669 | -0.006 | 0.498 | -0.480 |
| Mean, Batik (5) | | | 0.452 | 0.437 | 0.449 | 0.197 | 0.397 | 0.445 | 0.453 | 0.293 | 0.167 | 0.052 |
| Mean, Romantic (3) | | | 0.508 | 0.385 | 0.274 | 0.225 | 0.271 | 0.495 | 0.502 | 0.036 | 0.234 | -0.103 |

Paired differences over the 8 primary units (t-interval 7 df; percentile bootstrap):

| Contrast | Mean | t 95% | Bootstrap 95% | Positive | Batik (5) | Romantic (3) |
|---|---|---|---|---|---|---|
| **llm − dcml** | **−0.055** | [−0.138, +0.027] | [−0.121, +0.005] | 2/8 | −0.014 | −0.124 |
| **llm_m4 − dcml** | **−0.090** | [−0.224, +0.044] | [−0.195, +0.013] | 2/8 | −0.003 | −0.235 |
| llm_m8 − dcml | −0.265 | [−0.388, −0.143] | [−0.351, −0.161] | 1/8 | −0.255 | −0.283 |
| llm_cad − dcml | −0.123 | [−0.227, −0.019] | [−0.209, −0.047] | 2/8 | −0.055 | −0.237 |
| llm_oracle − dcml | −0.009 | [−0.023, +0.005] | [−0.021, +0.001] | 2/8 | −0.007 | −0.014 |
| **llm − detector** | **+0.221** | [+0.068, +0.374] | [+0.117, +0.351] | 8/8 | +0.145 | +0.348 |
| llm_m4 − detector | +0.186 | [+0.090, +0.283] | [+0.113, +0.263] | 8/8 | +0.156 | +0.238 |
| dcml − detector | +0.276 | [+0.098, +0.455] | [+0.148, +0.425] | 8/8 | +0.159 | +0.472 |
| llm_m4 − llm | −0.035 | [−0.130, +0.061] | [−0.111, +0.035] | 3/8 | +0.011 | −0.111 |
| dcml_m4 − dcml | −0.002 | [−0.039, +0.036] | [−0.032, +0.027] | 2/8 | +0.001 | −0.006 |

Per-movement llm − dcml: M1 +0.082, M2 +0.022, M3 −0.032, M4 −0.135, M5 −0.009, R1 −0.147,
R2 −0.210, R3 −0.015.

Near-the-bar numbers (reported, they do not change the rule):

- `llm`: SD of the paired differences 0.098; leave-one-movement-out means −0.075 to −0.033 (all
  above −0.10); worst-run variant (the lower LLM run in every movement) −0.108; best-run +0.006;
  one-sided p of mean > −0.10 is 0.121.
- `llm_m4`: SD 0.160; leave-one-out −0.122 to −0.057 (3 of 8 below −0.10); worst-run −0.122;
  one-sided p 0.433.

Run-to-run spread is sizeable in some movements (`llm` excess by run): M3 0.500 / 0.250 / 0.323 /
0.308, M5 0.329 / 0.414 / 0.412 / 0.250, R1 0.308 / 0.519, R2 0.206 / 0.109. M1 is identical in all
4 runs.

Over-segmentation: LLM / DCML phrase counts are 0.89-1.62 (M4 1.62, M5 1.38, M2 1.36; R1-R3
1.00-1.23). The 4-bar merge brings the Batik counts to DCML's level (mean 33.1 vs 33.0) but
changes the excess by only +0.011 there; on the Romantic pieces it lowers it by 0.111, mostly on
Träumerei (R3, −0.250). There the LLM phrases were already at DCML's level (ratio 1.00), yet the
merge still joins 2 of the 8 phrases (8 → 6), which are shorter than 4 bars. The same merge on the
DCML phrases of R3 (also 8 → 6) raises the excess (+0.07), so the loss depends on which short
phrases the LLM marked, not on the merge as such.

### Secondary: phrase-aware coherence (tempo R² without markings)

| Contrast (8 units) | Mean | t 95% | Positive |
|---|---|---|---|
| llm − dcml | −0.017 | [−0.097, +0.062] | 4/8 |
| llm_m4 − dcml | −0.015 | [−0.106, +0.076] | 3/8 |
| llm − proxy | −0.002 | [−0.062, +0.059] | 4/8 |
| dcml − proxy | +0.015 | [−0.025, +0.055] | 4/8 |
| llm − detector | +0.056 | [−0.036, +0.148] | 7/8 |

Means: Batik dcml 0.117, llm 0.110, detector 0.027, proxy 0.088; Romantic dcml 0.045, llm 0.010,
detector −0.000, proxy 0.052. On these 8 units even the DCML boundaries do not beat the proxy
(+0.015, 4/8), so this secondary has no signal to recover. F-05b's +0.07 (annotated − proxy) was
over 36 Batik movements.

### Secondary: PianoCoRe Mozart (many transcribed performers)

K.330/2 (30 perfs): dcml 0.648, llm 0.699, detector 0.456. K.330/3 (11 perfs): dcml 0.354, llm
0.277, detector 0.105. Same direction as the single Batik performance of each movement.

## Verdict (Provisional)

- **Primary (`llm`): RECOVERED by the pre-registered point-estimate rule.** Mean
  (LLM − DCML) `concave_excess` is −0.055 (≥ −0.10), and LLM beats the detector (+0.221, 8/8,
  t-interval excludes 0). The t-interval [−0.138, +0.027] straddles −0.10, so "within 0.10" is
  not shown by the interval; the worst-run variant (−0.108) falls just below the margin.
- **Robust variant (`llm_m4`): RECOVERED by the same rule, but only just** (−0.090; worst-run
  −0.122; leave-one-out below −0.10 in 3 of 8). It is not better than the raw LLM boundaries
  (−0.035 against them). The 8-bar merge fails (−0.265).
- **Per repertoire (not pre-registered as a decision):** on Batik Mozart the LLM matches DCML
  (−0.014); on the 3 Romantic pieces it loses 0.124 (0/3 positive), more than the margin, while
  still beating the detector by +0.348. With n = 3 this is a warning, not a result.
- **Reachability check after the run:** the observed SD of the paired differences (0.098) is
  smaller than the 0.15 assumed, so the t half-width is 0.083 rather than 0.13. It is still close to
  the margin, and only the point estimate decided, as registered.
- Phrase-aware coherence: inconclusive (no DCML advantage over the proxy on these units).

## Threats to validity

- n = 8 movements; 5 of them are one Batik pianist. The Romantic subset is 3 pieces, with
  transcribed PianoCoRe performances (18-30 each). No per-composer claim.
- The LLM boundaries are reused from R-08a/b/d, whose movements were drawn for boundary scoring,
  not for tempo. R4 (Grieg) and R5 (Liszt, the over-segmented piece) have no aligned
  performances, so the clearest over-segmentation case in R-08d could not be tested.
- `concave_excess` depends on the ±2-bar null, which is weaker for long phrases; the 8-bar merge
  result is partly this (its null concave share rises to 0.50-0.59).
- The merge rules (4 and 8 bars) and the cadence-level grouping are fixed conventions, not tuned.
  The oracle grouping uses DCML and is a diagnostic only.
- PianoCoRe boundaries pass through a score-to-score DTW; 2 of the 4 secondary Mozart pieces
  failed its quality rule. The Romantic mappings passed (0.94-0.97).
- DCML labels predate the model cutoff (R-08c/d): exposure not excluded.

## Audit (2026-09-28, eval-auditor)

**Verdict: Confirmed with caveats.** The primary (`llm`) is RECOVERED by the pre-registered
point-estimate rule, and LLM beats the detector. The measure is a fair target: random boundaries
at the LLM's density score about 0, and denser segmentation lowers `concave_excess` rather than
raising it. The claim is licensed at the pooled mean level only, and it is carried by Batik
(one pianist). On the 3 Romantic pieces the LLM loses more than the margin, and more than its
extra boundaries alone would cost. "The merge does not help" is confirmed.

Audit scripts and outputs: session scratchpad `f05e_audit/` (`repro.py`, `mapcheck.py`,
`controls.py`, `analyze.py`, `controls.parquet`). Nothing in `src/` or the experiment
artifacts was changed.

### 1. Pre-registration and timeline

- `head -n 160 README.md | shasum -a 256` (the header through the closing fence of
  "## Command", without the blank line before "## Run record") gives
  `d7205e403c71ccff857aaad8573fdc63c661eed603254f4196fce9f3ea069b18`. It matches the recorded
  `d7205e40...9b18`.
- Feature-engineer transcript (`agent-ab42b94657b26256c.jsonl`): README written 23:37:59Z and
  hashed 23:38:02Z; `merge_short_phrases` and tests added 23:38-23:39Z; `run.py` first written
  23:40:41Z; first `compute` 23:42:25Z. The only computation before `compute` (23:40:51Z) printed
  source counts and DTW onset agreement for the DCML starts. No tempo measure was computed
  before the hash.
- `git diff` of `shaping.py` + `test_shaping.py` hashes to `fe18cde0b28d...`, as recorded.
  `pytest tests/features/test_shaping.py`: 31 passed. `ruff check src tests`: clean.

### 2. The disclosed score-file deviation

Verified in the transcript and on disk. The primary rows (`batik`, `pc_R1-R3.parquet`) were
written 18:44-18:50 local; the filter edit was 18:51:13 local (23:51:13Z), after the crash on
the PianoCoRe Mozart units. For R1-R3 the old filter (`endswith("/score_MS_refined.mid")`) and
the new one (not `*_mini_refined.mid`) select the same files (R1 403 full / 0 mini, R2 18 / 2,
R3 771 / 96). My controls rerun used the new `draw_rows` and reproduced every `dcml`, `llm` and
`llm_m4` per-movement value to 1e-16. The deviation touches only the secondary Mozart set.
Minor: the Data section's "R2 ... (20)" counts 2 abridged-score performances; 18 were used,
as the results table says.

### 3. Reproduction

`summary()` rerun on a scratch copy of `artifacts/`: `summary.txt` is byte-identical. The
headline numbers match: llm - dcml -0.055, t [-0.138, +0.027], bootstrap [-0.121, +0.005],
2/8; llm - detector +0.221, t [+0.068, +0.374], 8/8; Batik -0.014, Romantic -0.124 (0/3);
RULE lines RECOVERED for `llm` and `llm_m4`. The harness passes: all 20 Batik rows equal
F-05c `phrase_tempo.csv`. The controls script recomputed `dcml`, `llm` and `llm_m4` from the
performances and boundaries, independently of the cached rows, and matched to 1e-16.

### 4. DTW mapping of boundaries to the PianoCoRe refined scores

The 0.94-0.97 agreement pools every mapped boundary of every source (starts, ends, detector).
`concave_excess` uses phrase **starts** only. For those, per source:

| Unit | DCML starts exact | LLM starts exact (A / B) | Map vs a local-offset map |
|---|---|---|---|
| R1 | 20/20 | 23/23, 18/18 | identical |
| R2 | 13/13 | 15/15, 17/17 | identical |
| R3 | 7/8 | 8/8, 8/8 | identical |

Over all exact-matched onsets, the target minus source offset is a single constant per piece
(R1 0, R2 3, R3 4 beats: a pickup or leading-rest difference). The warping path is monotone.
The one inexact DCML start (R3 beat 96) maps to the same place as the constant offset predicts
(100). So the mapping is a pure shift for every start used. It cannot bias DCML against LLM on
R1-R3.

### 5. Units, run pooling and the one-pianist issue

- The unit is right: movement-level differences (LLM mean over runs minus DCML; PianoCoRe
  values are paired on the same performances), t with 7 df over 8 movements. The unequal run
  counts (4 vs 2) only make the Batik terms less noisy. Run noise is inside the between-movement
  SD, so it is not ignored.
- Sensitivity (my computation): Batik with any 2 of its 4 runs gives Δ from -0.068 to -0.043
  (all 6 pairs); without the disguised run -0.047; weighting Batik and Romantic equally -0.069.
  All are above -0.10.
- Five of the 8 units are one pianist with one performance each. The interval covers
  movement-to-movement variation, not pianist-to-pianist. The PianoCoRe Mozart secondary is the
  only check across performers (K.330/2 +0.051, K.330/3 -0.077, same sign as Batik), and 2 of its
  4 pieces failed the mapping rule.

### 6. Is `concave_excess` a fair target? The over-segmentation question

Seeded controls (200 draws per LLM run and movement, applied to the same performances):

| Boundary set (8 units) | concave share | null share | `concave_excess` |
|---|---|---|---|
| DCML | 0.838 | 0.365 | 0.473 |
| LLM | 0.827 | 0.409 | 0.418 |
| Random onsets, LLM count per run | 0.495 | 0.528 | -0.032 |
| Random downbeats, LLM count per run | 0.531 | 0.525 | +0.006 |
| DCML, each phrase of 2 bars or more halved at its midpoint (about 2x density) | 0.754 | 0.614 | 0.140 |
| DCML plus random extra onsets up to the LLM count (random deletions if fewer) | 0.807 | 0.398 | 0.409 |
| DCML starts each moved to a random onset within 2 bars | 0.580 | 0.484 | 0.096 |

- **Density does not inflate the measure.** At the LLM's density, random boundaries score
  about 0 in every movement. The 95th percentile of the 8-unit mean over draws is +0.014
  (onsets) and +0.049 (downbeats). LLM is +0.418, and no draw reached the LLM in any movement
  except 1% of downbeat draws on R2. Across the 26 movement-runs, the random excess does not rise
  with phrase count (Spearman -0.26, p 0.20).
- **The "half parabola is still concave" point is real for the raw share, but the null catches
  it.** Halved DCML phrases stay mostly concave (0.754, against 0.50 for random boundaries). A
  2-bar shift of 2-bar phrases then lands on the true boundaries, so the null share rises to
  0.614, and the excess falls by 0.333 (0/8 up). Denser segmentation is **penalised**, not
  rewarded. So `concave_excess` cannot be gamed by over-segmenting. It is also placement-
  sensitive: a ±2-bar jitter of DCML drops it to 0.096.
- **Consequence for the reading.** The measure depends on the phrase level. A correct but
  finer segmentation scores low. "Recovered" therefore means "recovers the DCML-level signal".
  The raw share is not a usable measure on its own (random boundaries give 0.50-0.53).
- **Where the LLM loss comes from.** DCML plus random extras at the LLM's count costs -0.064
  against DCML. The LLM costs -0.055, so overall the LLM behaves like "DCML plus the same number
  of random extras" (LLM - that control +0.008, 4/8). By repertoire: on Batik the LLM beats it
  (+0.060). On Romantic it is below it (-0.078, and below every draw in R1, R2 and R3). The
  Romantic loss is therefore placement, not only density. R3 has the same count as DCML (8 vs 8)
  and loses only 0.015. R2 (-0.210) and R1 (-0.147) carry the loss.

### 7. Can each verdict branch be reached?

With the observed SD of the paired differences (0.098, SE 0.035, t with 7 df), the
point-estimate rule gives RECOVERED with probability 0.99 at a true Δ of 0, 0.90 at -0.05, 0.50
at -0.10, 0.10 at -0.15 and 0.01 at -0.20. Both registered branches were reachable, and the rule
discriminates at about ±0.05 around the margin. A third outcome (Δ ≥ -0.10 but LLM not above the
detector) has no pre-registered label; `run.py` labels it separately. It was practically out of
reach (DCML - detector is +0.276, 8/8) and did not occur. The prereg's reachability paragraph and
the post-run SD check are correct.

### 8. Claim vs evidence

| Claim | Status |
|---|---|
| `llm` RECOVERED by the point-estimate rule (-0.055) | Confirmed. The interval straddles -0.10; worst-run -0.108; one-sided p 0.121 |
| LLM beats the detector (+0.221, 8/8) | Confirmed (t excludes 0) |
| `llm_m4` RECOVERED (-0.090) | Confirmed by the rule, but marginal: LOO below -0.10 in 3/8, worst-run -0.122 |
| The merge does not help (-0.035 against raw) | Confirmed. Not recommended |
| Romantic -0.124 (0/3) | Correct and labelled "not pre-registered as a decision". Also shown here: it is beyond the cost of the extra boundaries (placement loss) |
| Coherence secondary inconclusive | Correct (DCML - proxy +0.015 on these units) |

### Caveats that go with the verdict

1. Scope: pooled mean level, DCML-level segmentation. Batik (one pianist, 5 movements)
   carries it (-0.014). On the target Romantic repertoire, 3 pieces show a loss beyond the
   margin (-0.124), and it comes from misplaced boundaries. LLM boundaries are **not** shown to
   recover the signal on Romantic music. They are shown only to beat the detector there
   (+0.348, 3/3).
2. `concave_excess` penalises correct but finer segmentation (halving costs -0.33). Any LLM
   source whose level drifts finer than DCML's will score low for that reason alone. Report the
   phrase-count ratio next to it.
3. The raw `concave_share` is not usable without the null (random boundaries give 0.50).
4. No across-pianist test of the primary on Batik movements. The Mozart secondary gives 2 usable
   pieces.

### Required fixes (text only; not blocking)

- Add the section 6 controls table (random boundaries at the LLM's density, halved DCML,
  DCML plus extras, jittered DCML) to the Verdict, with the level-dependence caveat.
- State that the Romantic loss exceeds the density-matched DCML control (placement loss).
- Note the undefined third branch (Δ ≥ -0.10, LLM not above the detector) in the Verdict.
- Data section: R2 has 18 full-score performances (2 of the 20 are abridged).

## Post-audit corrections (lead, 2026-09-28)

- **Controls** (from the Audit section; mean over 8 units):

  | Boundary set | concave_excess |
  |---|---|
  | DCML | 0.473 |
  | LLM | 0.418 |
  | Random onsets at the LLM's density | −0.032 |
  | Random downbeats at the LLM's density | +0.006 |
  | DCML with each phrase halved | 0.140 |
  | DCML plus random extras up to the LLM's count | 0.409 |
  | DCML starts jittered ±2 bars | 0.096 |

  Density does not inflate the measure. Over-segmentation is penalised.
- **The Romantic loss (Δ −0.124) is a placement loss.** The LLM scores below
  "DCML + random extras" on R1-R3.
- A third outcome (Δ ≥ −0.10 but the LLM not above the detector) had no pre-registered label. It
  was unreachable in practice.
- Data correction: R2 has 18 full-score performances, not 20. The other 2 use the abridged score.

## Doc correction (feature-engineer, 2026-09-29, DEFECTS DF-08)

- The pre-registration (Boundary sources) gives the signature
  `merge_short_phrases(starts, min_bars, beats_per_bar, lo, hi)`. The function as written and run
  is `merge_short_phrases(starts_beats, min_bars, beats_per_bar, end_beat)`: there is no `lo`
  argument, and `end_beat` (the last onset + 1 beat) ends the last phrase, as the prose already
  says. The pre-registration text is left unedited so its recorded hash still verifies.
