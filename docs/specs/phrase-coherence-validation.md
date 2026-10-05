# Phrase boundaries and tempo coherence (F-05b)

Measured 2026-09-27 by `feature-engineer`. Code: `src/pianolens/features/score_basis.py`
(new opt-in `phrase_detail` and `cadence` groups), `src/pianolens/features/shaping.py` (new
`ShapingConfig.clip_to_train`, opt-in at the time and the default since DECISIONS 2026-09-27
after F-05b, item 4), script `scripts/check_phrase_f05b.py`. Rerun:

```
OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05b.py batik lomo   # ~15 min on a busy Mac
OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05b.py transfer     # ~5 min
```

Outputs (gitignored) in `data/interim/phrase_f05b/`: `batik_boundaries.csv`,
`batik_coherence.csv`, `batik_arcs.csv`, `batik_lomo.csv`, `transfer_coherence.csv`,
`transfer_boundaries.csv`, and the logs `run_batik.log`, `run_transfer.log`.

## Answer

Near-zero tempo coherence is **both** a phrase-boundary problem and a model problem. Neither fix
works alone.

- Tempo does follow the annotated phrases. 81% of annotated Batik phrases have a concave tempo
  arc (slower at both edges). With the same boundaries shifted by two bars, only 44% do.
- Swapping the proxy boundaries for the annotated ones, with the F-05 features unchanged, barely
  helps. Tempo R² goes from 0.070 to 0.090 (not significant).
- Annotated boundaries plus the new phrase-end features double tempo R², from 0.070 to 0.141
  (p = 0.007). The same features on the proxy boundaries give nothing (0.065). On shifted
  boundaries they give 0.074.
- Even then, tempo R² stays well below velocity (0.37). A model trained on other movements does
  not transfer (leave-movement-out R² about 0). How a phrase is shaped in time varies from phrase
  to phrase and movement to movement. One global linear map from score features does not capture
  that.

**Recommendation.** R-08 (LLM phrase analysis) is worth doing only together with the
`phrase_detail` features, and only if it gets close to the annotated boundaries. The proxy's F1
of 0.34 at ±1 beat is too low: the richer features gave no gain on the proxy. Until then, tempo
stays out of H4's primary measure. Velocity and articulation remain the primary channels (as in
the F-05 follow-ups). For tempo, add a per-phrase measure that does not assume a shared arc
shape. Details are under "Recommendations" below.

## Data

- **Batik-plays-Mozart**, 36 movements, one pianist, ground-truth match alignments.
  - DCML annotations: `score_parts_annotated/<stem>_spart_{phrases,cadence}.csv`. Each label
    sits on one score note. Its `id` is the match-file id with the repeat suffix, and all
    phrase and cadence ids resolve.
  - Phrase starts are the `{` and `}{` labels; ends are `}` and `}{`. The `}` sits on the
    cadential arrival.
  - Counts over the performed scores: 1,068 annotated phrase starts, 1,144 cadences
    (PAC 547, HC 410, IAC 75, EC 65, DC 47).
- **The loader's match-file score has no markings.** It carries no slurs, dynamics or barlines,
  so the proxy would lose half of its cues. The script unfolds `scores_edited/<stem>.musicxml`
  to the repeat path whose note ids equal the match ids. Every match id resolves in all 36
  movements (D-11 recheck: id Jaccard 1.0 in 35, 0.9996 in kv281_3, which has one extra
  MusicXML note), so the ground-truth alignment still applies and the markings are present.
- **Vienna 4x22 K.331/1**: the theme only, 22 pianists, match alignments.
  - Its MusicXML starts at Batik's beat 0 and numbers bars in performed order (1-36), so
    boundaries are mapped by beat.
  - The onset pitch sets agree at all mapped boundaries.
  - Bars are renumbered to the written bars (1-18) so that the two passes of a repeat share a
    CV fold. Without the renumbering, repeats leak and every R² is inflated: the proxy's
    pooled tempo R² was 0.19 instead of -0.27.
- **ASAP**: K.332/1 (4 performances), K.332/2 (2), K.332/3 (3) and K.331/3 (1), aligned with
  parangonar. Batik has no K.310.
  - Boundaries are mapped by (written bar, beat in bar), with a bar offset of 0 in every case.
  - The onset pitch sets agree at 100%, 92%, 100% and 71% of the mapped boundaries.

## 1. Proxy boundaries against the annotations

The proxy is F-05's cue-based phrase-boundary detector. Matching is one-to-one, closest pairs
first, and the first onset is excluded. `proxy` is the proxy's own boundaries. `proxy_split`
adds the even splits of phrases longer than 8 bars. `grid4` and `grid2` put a boundary on every
4th or 2nd downbeat. Values are means over the 36 Batik movements.

| Method | P ±1 beat | R ±1 beat | F1 ±1 beat | P ±1 bar | R ±1 bar | F1 ±1 bar |
|---|---|---|---|---|---|---|
| proxy | 0.284 | 0.474 | 0.337 | 0.429 | 0.711 | 0.507 |
| proxy_split | 0.277 | 0.492 | 0.340 | 0.422 | 0.746 | 0.517 |
| grid4 | 0.216 | 0.341 | 0.256 | 0.412 | 0.674 | 0.495 |
| grid2 | 0.183 | 0.598 | 0.274 | 0.302 | 1.000 | 0.453 |

- Pooled counts give the same picture. At ±1 beat the proxy has 493 of 1,810 predicted
  boundaries correct and recovers 493 of 1,032 true ones.
- At bar tolerance the proxy is no better than a 4-bar grid (F1 0.51 vs 0.50). Its cues add
  about 0.08 F1 only at beat precision.
- It fires about 1.75 times as often as a phrase starts.
- Per-movement proxy F1 (±1 beat) for the other sets:
  - Vienna K.331/1: 0.46.
  - ASAP: 0.58 (K.331/3), 0.33 (K.332/1), 0.11 (K.332/2), 0.14 (K.332/3).
- The per-movement rows are in `batik_boundaries.csv` and `transfer_boundaries.csv`.

## 2. Structural coherence: proxy vs annotated phrases

Coherence uses the F-05 ridge with the same written-bar CV (4-bar blocks, 5 folds, 1-bar
buffer). Every variant here adds `clip_to_train=True` (see "Code changes"). Clipping moves the
F-05 variants by at most 0.001 on average: proxy tempo is 0.069 unclipped, 0.070 clipped.

The variants:

- `proxy`: the F-05 default.
- `no_phrase`: the phrase group dropped.
- `ann`: annotated starts, still split at 8 bars.
- `ann_nosplit`: annotated starts, no splitting.
- `ann_detail`: annotated starts and ends, plus the `phrase_detail` group.
- `ann_detail_cad`: `ann_detail` plus the DCML `cadence` group.
- `proxy_detail`: `phrase_detail` on the proxy phrases.
- `shift_detail_cad`: `ann_detail_cad` with all boundaries and cadences circularly shifted by
  2 bars. This is the null: same counts and spacing, wrong places.

`tempo_seg` is the smooth tempo centred within each marked-tempo segment. It removes
section-level tempo changes.

### Batik, R² without markings (H4 primary), mean over 36 movements

| Channel | proxy | no_phrase | ann | ann_nosplit | proxy_detail | ann_detail | ann_detail_cad | shift_detail_cad |
|---|---|---|---|---|---|---|---|---|
| velocity | 0.376 | 0.373 | 0.368 | 0.373 | 0.372 | 0.372 | 0.369 | 0.358 |
| timing | 0.122 | 0.121 | 0.123 | 0.125 | 0.127 | 0.126 | 0.126 | 0.123 |
| tempo | 0.070 | 0.046 | 0.090 | 0.100 | 0.065 | 0.143 | 0.141 | 0.074 |
| tempo_seg | 0.067 | 0.042 | 0.093 | 0.100 | 0.053 | 0.133 | 0.149 | 0.081 |
| articulation | 0.195 | 0.197 | 0.194 | 0.195 | 0.183 | 0.191 | 0.184 | 0.179 |

- With markings the pattern is the same. Tempo R² is 0.092 for proxy, 0.175 for `ann_detail`
  and 0.167 for `ann_detail_cad`.
- Tempo medians: 0.063 for proxy and 0.161 for `ann_detail_cad`.

Paired comparisons of tempo R² across the 36 movements (Wilcoxon signed-rank):

| Comparison | Mean diff | Median diff | Movements better | p |
|---|---|---|---|---|
| ann - proxy | +0.020 | +0.002 | 20/36 | 0.28 |
| ann_nosplit - proxy | +0.030 | +0.013 | 22/36 | 0.088 |
| proxy_detail - proxy | -0.005 | -0.018 | 14/36 | 0.098 |
| ann_detail - proxy_detail | +0.078 | +0.038 | 25/36 | 0.0044 |
| ann_detail_cad - proxy | +0.071 | +0.047 | 24/36 | 0.0074 |
| ann_detail_cad - shift_detail_cad | +0.067 | +0.052 | 25/36 | 0.0031 |

- Only tempo moves. Velocity, timing and articulation change by 0.01 or less in every variant.
  The proxy's phrase features were not holding those channels back.
- The DCML cadence types add nothing to tempo on top of the phrase ends (0.143 vs 0.141).
  Knowing where phrases end matters. Knowing the cadence type does not.
- The annotation effect varies a lot across movements. Tempo R² for `ann_detail_cad` ranges
  from -0.26 (K.283/2) to 0.44 (K.331/2). Twelve movements get worse than with the proxy.

### Flexible model (gradient boosting), same folds, tempo R² without markings

| Channel | proxy | ann_detail_cad | shift_detail_cad |
|---|---|---|---|
| tempo | 0.182 | 0.238 | 0.177 |
| tempo_seg | 0.164 | 0.205 | 0.153 |

A nonlinear model gains about 0.1 over ridge whatever the boundaries. On top of that, annotated
phrases add about 0.06 and shifted ones add nothing. Part of the ceiling is the linear form.

### Per-phrase tempo arcs (F-03 `phrase_arcs`), mean over movements

| Boundaries | Phrases | Between-phrase share of tempo variance | Parabola R² within phrases | Share of concave arcs (c2 < 0) |
|---|---|---|---|---|
| annotated | 29.6 | 0.316 | 0.512 | 0.813 |
| shifted 2 bars | 29.6 | 0.320 | 0.397 | 0.440 |
| proxy (with splits) | 55.5 | 0.449 | 0.691 | 0.687 |
| 4-bar grid | 52.4 | 0.444 | 0.629 | 0.558 |

- Compare annotated with shifted: both have the same number of phrases and parameters. With the
  annotated boundaries, a parabola per phrase fits better (0.51 vs 0.40), and most arcs have the
  expected slow-fast-slow shape (81% vs 44%).
- The proxy and grid rows have about twice as many phrases, so their in-sample R² is not
  comparable. Their concave share still shows the gap: 69% for the proxy and 56% for the grid.

### One model for all Batik movements (leave-movement-out, 6 folds)

Tempo is centred per movement, and the features have no markings.

| Variant | Ridge pooled R² | Ridge median per movement | GBM pooled R² |
|---|---|---|---|
| proxy | 0.002 | -0.060 | -0.012 |
| proxy_detail | -0.004 | -0.087 | -0.083 |
| ann_detail_cad | 0.004 | -0.023 | -0.161 |
| shift_detail_cad | -0.005 | -0.101 | -0.131 |

- Nothing transfers across movements, even for one pianist and one composer.
- Within a movement, tempo coherence of 0.14 means a model fitted on other bars of the same
  movement predicts the arcs. The shape and depth of the arcs are movement-specific.
- The ridge penalty here is picked by leave-one-row-out, which favours weak penalties. The GBM
  was not tuned. Treat this table as a floor, not a final answer.

### Other sets (performances of the same movement pooled into one model, R² without markings)

| Set | Channel | proxy | ann | ann_detail_cad | proxy_detail |
|---|---|---|---|---|---|
| Vienna K.331/1 (22) | tempo | -0.272 | 0.125 | 0.417 | -0.167 |
| Vienna K.331/1 (22) | timing | 0.335 | 0.429 | 0.429 | 0.352 |
| Vienna K.331/1 (22) | velocity | 0.379 | 0.279 | 0.391 | 0.350 |
| Vienna K.331/1 (22) | articulation | -0.002 | -0.034 | -0.031 | -0.004 |
| ASAP K.332/1 (4) | tempo | 0.201 | 0.174 | 0.224 | 0.205 |
| ASAP K.332/2 (2) | tempo | -0.029 | -0.034 | -0.035 | -0.017 |
| ASAP K.332/3 (3) | tempo | 0.274 | 0.272 | 0.272 | 0.297 |
| ASAP K.331/3 (1, single) | tempo | 0.097 | 0.135 | 0.207 | 0.162 |

- **Vienna.** This is the strongest multi-performer evidence: 22 pianists on one theme. Pooled
  tempo R² goes from -0.27 with the proxy to 0.42 with annotated phrases and phrase-end
  features. Timing rises from 0.34 to 0.43. The mean per-pianist R² follows the same pattern:
  -0.31, 0.06, 0.33.
  - Caveat: the theme is 18 written bars, so there are only 5 CV blocks.
  - Without `clip_to_train`, the `ann_detail_cad` variant blew up here (R² about -70). One
    cadence type fell in a single block.
- **ASAP.** The annotations change little on the K.332 movements. These are short sets (2-4
  performances), and the proxy already scores 0.20-0.30 on K.332/1 and /3. K.332/2 is negative
  in every variant.

## Conclusion

1. **Is it a boundary problem? Partly.** Tempo arcs are real, and they sit on the annotated
   phrases. Two results show this.
   - The concave-arc share is 81% for annotated phrases and 44% for shifted ones.
   - Annotated phrase ends double the within-movement tempo R² (Batik 0.07 to 0.14; Vienna
     -0.27 to 0.42).

   The proxy cannot deliver this. Its boundaries are right about half the time at beat
   precision, and the same richer features gain nothing on it.
2. **Is it a model problem? Also yes.**
   - Plugging the annotated boundaries into the F-05 arc features (a position in the phrase and
     its square, shared by all phrases) gains only 0.02.
   - The gain needs features anchored on the phrase end (final lengthening, recovery after the
     boundary).
   - Even the best within-movement tempo R² (0.14 ridge, 0.24 boosting) stays far below
     velocity. It does not transfer across movements.
   - Arc depth and shape vary from phrase to phrase. A global linear basis can only learn the
     average arc.

## Recommendations

1. **H4 / R-09.**
   - Keep velocity and articulation as the primary channels.
   - Report tempo coherence as secondary, and only with annotated or validated phrases plus
     `BasisConfig(phrase_detail=True)` and `ShapingConfig(clip_to_train=True)`.
   - With proxy phrases, do not use tempo R² as evidence either way.
2. **Add a tempo measure that does not assume a shared arc** (a proposed follow-up ticket).
   Examples:
   - the share of phrases with a concave arc;
   - the within-phrase parabola R² from `phrase_arcs`, relative to the shifted-boundary null
     for the same performance.

   These read "does this player shape phrases in time" without asking every phrase to have the
   same shape. On Batik they separate true from shifted boundaries clearly.
3. **R-08 (LLM phrase analysis).**
   - Worth doing only if its boundaries reach at least about 0.7 F1 at ±1 beat on the Batik
     DCML set. It must be validated there first: the harness and the ground truth now exist in
     `scripts/check_phrase_f05b.py`.
   - At the proxy's 0.34, the richer features gave no gain.
   - A cheaper route to test first: phrase ends from cadence detection on the harmony
     (F-04b), since the ends drive the gain.
4. **Data engineering (optional).** Give `pianolens.data.batik_mozart` an option that returns
   the MusicXML-based performed score (with markings) and a phrase / cadence loader. The helper
   is `batik_performance` / `batik_annotations` in the script.

## Code changes (backward compatible; the defaults reproduce F-05)

- **`score_basis`** has two new keyword arguments, `phrase_ends_beats` and `cadences`, and a new
  config flag, `BasisConfig.phrase_detail` (default False).
  - The new groups are listed in `OPTIONAL_GROUPS`. `phrase_detail` has phrase-end kernels at
    0.5, 1 and 2 bars, a kernel after the phrase end, a kernel after the phrase start, the log
    phrase length, and the phrase length times the arc.
  - `cadence` has an approach kernel for each cadence type (PAC, HC, other) and a kernel after
    each cadence.
- **`ShapingConfig.clip_to_train`** clips held-out features to the training range, which stops
  the ridge from extrapolating wildly on sparse features. It was added with default False; it
  defaults to True since DECISIONS 2026-09-27 (after F-05b, item 4).
- **`voicing`** (coordinator request, R-04). A zero or non-finite smooth beat period used to
  raise ZeroDivisionError. That onset's `lead_beats` is now NaN, and the summary counts such
  onsets in `n_lead_beats_undefined`.
- **Coherence summaries** gain `n_blocks`, the number of distinct written-bar CV blocks. The
  module docstring now states a minimum-length rule: treat R² as defined only for
  `n_blocks >= 3` (12 written bars at the default block size).
- **Tests** in `tests/features/test_shaping.py`:
  - the column values of the new groups, and that they are off by default;
  - a synthetic phrase-final ritardando over irregular phrases: tempo R² is 0.77 with the
    phrase-end features and 0.50 without;
  - the clipping case (unclipped R² below 0, clipped above 0.8);
  - the zero beat period in `voicing`;
  - `n_blocks`.

## Not verified

- Batik is one pianist. The paired tests treat the movements as independent, but they share
  that pianist's style.
- The Vienna excerpt is short (5 CV blocks). The ASAP sets have 1-4 performances.
- The DCML phrase annotations are one reading of the phrase structure. Their agreement with
  other analysts was not measured here.
- The GBM and leave-movement-out models were not tuned.

# F-05c: cadence-derived phrase ends and per-phrase tempo shaping

Measured 2026-09-27 by `feature-engineer`. Code: `src/pianolens/features/cadence.py` (new),
`src/pianolens/features/shaping.py` (`phrase_tempo_shaping`), `src/pianolens/features/score_basis.py`
(opt-in `BasisConfig.phrase_source="cadence"`), Batik loader `pianolens.data.batik_mozart`
(D-11: `iter_aligned(musicxml_score=True)`, `phrase_annotations`). Script
`scripts/check_phrase_f05c.py`. Rerun:

```
OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05c.py cands fit eval
OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05c.py coherence
OMP_NUM_THREADS=1 uv run python scripts/check_phrase_f05c.py vienna
```

Outputs (gitignored) in `data/interim/phrase_f05c/`: `cands.pkl`, `fit.json`,
`boundaries.csv`, `coherence.csv`, `phrase_tempo.csv`, `vienna.csv`,
`vienna_phrase_tempo.csv`.

## Answer

- **Cadence detection finds phrase ends clearly better than the proxy, but not well enough.**
  On the 21 held-out Batik movements, phrase-end F1 is 0.46 at ±1 beat, against 0.29 for the
  proxy's phrase ends and 0.18 for a 4-bar grid. That is far below the ~0.7 set for R-08.
- **It does not make tempo coherence usable without annotations.** With cadence-derived
  boundaries plus `phrase_detail`, held-out tempo R² is 0.067: below the proxy (0.097), well
  below annotated phrases (0.149), and barely above its own shifted null (0.052). On Vienna
  K.331/1 (22 pianists) pooled tempo R² is -0.40, against -0.27 for the proxy and 0.375 for the
  annotations. The phrase-end kernels need ends at beat precision; wrong ends put a
  ritardando where there is none.
- **The per-phrase tempo measure works with any reasonable boundaries.** Its excess over the
  shifted null is positive and significant for annotated, cadence and proxy boundaries, and
  zero for a 4-bar grid. Annotated boundaries give the largest excess.
- **Recommendation.** Tempo stays secondary in H4, and structural-coherence tempo R² still needs
  annotated phrases. For annotation-free tempo shaping use `phrase_tempo_shaping`'s
  `concave_excess`, which does not need beat-precise boundaries. `phrase_source="cadence"` is
  offered as an opt-in boundary source (its boundaries are more accurate), but the default
  stays `proxy`. R-08 is still worth running only if it can reach ~0.7 F1; cadence detection
  got to 0.46.

## Cadence detector

One row per score onset with 21 interpretable cues (bass motion into the onset, triad quality
and dominant preparation in 1-quarter windows before and after, the F-04b harmony-change rule,
metrical strength, melody and IOI lengthening, rests, density drop, melodic step down, bass on
tonic / dominant). A logistic model scores each onset. The weights were fitted on K.279-K.283
(15 movements, 21,006 onsets, 397 annotated ends; label = the onset carries a DCML `}` or `}{`).
The ends are picked greedily by probability (threshold 0.2, at least 1.5 bars apart). Starts
follow each end: the onset after the longest silence or IOI within 2 bars. All four settings
were chosen on the training movements; the other 21 movements are held out. The largest
weights: metrical strength +3.2, bass on the dominant +1.4, bass down a fifth +1.2, melody
step down +1.1. Full list in `cadence.DEFAULT_WEIGHTS`.

Baselines for ends: `proxy_last_onset` is the last onset before each proxy phrase start (what
`phrase_detail` uses when no ends are given). `proxy_prev_downbeat` is the downbeat one bar
before each proxy start. `grid4` is every 4th downbeat, from the 4th. Matching is one-to-one
as in F-05b.

### Batik, mean over movements (P / R / F1)

| Target | Tol | Method | Train (15) | Held out (21) |
|---|---|---|---|---|
| phrase end | ±1 beat | cadence | 0.52 / 0.56 / **0.53** | 0.46 / 0.48 / **0.46** |
| phrase end | ±1 beat | proxy_last_onset | 0.19 / 0.35 / 0.24 | 0.26 / 0.39 / 0.29 |
| phrase end | ±1 beat | proxy_prev_downbeat | 0.21 / 0.37 / 0.26 | 0.18 / 0.33 / 0.22 |
| phrase end | ±1 beat | grid4 | 0.17 / 0.27 / 0.21 | 0.15 / 0.26 / 0.18 |
| phrase end | ±1 bar | cadence | 0.64 / 0.69 / **0.65** | 0.60 / 0.62 / **0.59** |
| phrase end | ±1 bar | proxy_last_onset | 0.39 / 0.69 / 0.48 | 0.43 / 0.67 / 0.49 |
| phrase end | ±1 bar | grid4 | 0.44 / 0.71 / 0.53 | 0.44 / 0.71 / 0.53 |
| phrase start | ±1 beat | cadence | 0.45 / 0.50 / **0.46** | 0.44 / 0.46 / **0.44** |
| phrase start | ±1 beat | proxy | 0.26 / 0.47 / 0.32 | 0.30 / 0.48 / 0.35 |
| phrase start | ±1 bar | cadence | 0.54 / 0.60 / 0.56 | 0.55 / 0.57 / 0.54 |
| phrase start | ±1 bar | proxy | 0.41 / 0.71 / 0.50 | 0.44 / 0.71 / 0.51 |
| DCML cadence | ±1 beat | cadence | 0.46 / 0.50 / 0.47 | 0.49 / 0.47 / 0.47 |

- Pooled counts, held out, ends at ±1 beat: 324 of 718 predicted correct, 324 of 671 true
  ends found (P 0.45, R 0.48). The detector predicts about as many ends as there are.
- At bar tolerance the gain over a 4-bar grid is small for ends (0.59 vs 0.53) and starts
  (0.54 vs 0.48 for grid, 0.51 proxy). The gain is in beat precision.
- Recall of the DCML cadences by type (held out, ±1 beat): PAC 65% (226/349), IAC 35%
  (22/63), HC 32% (86/271), EC 19% (5/27), DC 0% (0/24). Half cadences are the main miss:
  the arrival on V has no V-I bass, and deceptive cadences are not V-I by definition.
- Vienna K.331/1 (held out, detector run on the Vienna score itself, 6/8): 7 ends found for 10
  annotated. F1 is 0.82 at ±1 bar but 0.12 at ±1 beat (one beat is an eighth note here).

## Structural coherence with cadence boundaries (recomputes the F-05b rows)

Same ridge, written-bar CV and `clip_to_train=True` as F-05b. `cad_detail`: cadence starts and
ends with `phrase_detail` and no 8-bar split. `cad_detail_split`: the same with the split.
`shift_cad_detail`: `cad_detail` shifted by 2 bars (null). `proxy` and `ann_detail` reproduce
F-05b: tempo 0.070 and 0.143.

### Batik R² without markings, mean over movements

| Channel | Split | proxy | proxy_detail | ann_detail | cad_detail | cad_detail_split | shift_cad_detail |
|---|---|---|---|---|---|---|---|
| tempo | all 36 | 0.070 | 0.065 | 0.143 | 0.045 | 0.033 | 0.029 |
| tempo | train 15 | 0.032 | 0.021 | 0.135 | 0.015 | 0.003 | -0.003 |
| tempo | held out 21 | 0.097 | 0.097 | 0.149 | 0.067 | 0.054 | 0.052 |
| velocity | all 36 | 0.376 | 0.372 | 0.372 | 0.358 | 0.359 | 0.350 |
| timing | all 36 | 0.122 | 0.127 | 0.126 | 0.125 | 0.124 | 0.121 |
| articulation | all 36 | 0.195 | 0.183 | 0.191 | 0.190 | 0.187 | 0.191 |

Paired tempo R² (Wilcoxon, held out, 21 movements):

| Comparison | Mean diff | Better | p |
|---|---|---|---|
| cad_detail - proxy | -0.030 | 5/21 | 0.046 |
| cad_detail - shift_cad_detail | +0.015 | 13/21 | 0.12 |
| ann_detail - cad_detail | +0.083 | 18/21 | 0.0049 |
| cad_detail_split - proxy | -0.043 | 5/21 | 0.010 |

Over all 36: cad_detail - proxy -0.025 (10/36 better, p 0.021); ann_detail - cad_detail +0.098
(29/36, p 0.0003). With markings the ranking is the same (held out tempo: proxy 0.127,
ann_detail 0.177, cad_detail 0.084). The other channels move by 0.02 or less.

### Vienna K.331/1, 22 pianists pooled, R² without markings

| Channel | proxy | ann_detail | cad_detail | shift_cad_detail |
|---|---|---|---|---|
| tempo | -0.272 | 0.375 | -0.401 | -0.160 |
| timing | 0.335 | 0.432 | 0.351 | 0.338 |
| velocity | 0.379 | 0.374 | 0.346 | 0.366 |
| articulation | -0.002 | -0.019 | -0.012 | -0.038 |

(`ann_detail` here has no cadence group, so it differs from F-05b's `ann_detail_cad`, 0.417.)

## Per-phrase tempo shaping (`phrase_tempo_shaping`)

For each phrase, a parabola in phrase position is fitted to the F-03 smooth log tempo on the
beat grid. No shape is shared between phrases. Outputs:

- `concave_share`: the share of phrases slower at both edges.
- `arc_r2_within`: the pooled in-sample R².
- The same two after circularly shifting the boundaries by ±2 bars (the null).
- `concave_excess` / `arc_r2_excess`: observed minus the null.
- Per-phrase and per-bar tables.

The +2-bar null reproduces F-05b (annotated 0.813 concave vs 0.440 shifted; arc R² 0.512 vs
0.397).

### Batik, mean over movements (null = mean of the -2 and +2 bar shifts)

| Boundaries | Split | Phrases | Concave | Null | Concave excess | Arc R² | Null | Arc R² excess |
|---|---|---|---|---|---|---|---|---|
| annotated | all 36 | 29.6 | 0.813 | 0.453 | +0.360 | 0.512 | 0.411 | +0.101 |
| cadence | all 36 | 32.1 | 0.685 | 0.510 | +0.175 | 0.440 | 0.393 | +0.048 |
| proxy (split) | all 36 | 55.5 | 0.687 | 0.471 | +0.216 | 0.691 | 0.603 | +0.088 |
| 4-bar grid | all 36 | 52.4 | 0.558 | 0.533 | +0.025 | 0.629 | 0.615 | +0.015 |
| annotated | held out 21 | 31.9 | 0.847 | 0.428 | +0.418 | 0.530 | 0.410 | +0.120 |
| cadence | held out 21 | 33.8 | 0.698 | 0.492 | +0.207 | 0.442 | 0.393 | +0.049 |
| proxy (split) | held out 21 | 56.5 | 0.714 | 0.471 | +0.243 | 0.704 | 0.611 | +0.093 |
| 4-bar grid | held out 21 | 55.5 | 0.544 | 0.552 | -0.009 | 0.658 | 0.630 | +0.028 |

The excess is tested against 0 over movements (Wilcoxon, held out):

- annotated: concave 21/21 movements positive, p 1e-6.
- cadence: 17/21, p 0.002.
- proxy: 20/21, p 1e-5.
- grid: 11/21, p 0.61.

Vienna K.331/1, mean over the 22 pianists:

| Boundaries | Concave | Null | Concave excess | Arc R² excess |
|---|---|---|---|---|
| annotated | 0.955 | 0.220 | +0.734 | +0.273 |
| cadence | 0.916 | 0.410 | +0.505 | +0.112 |
| proxy (split) | 0.737 | 0.631 | +0.106 | +0.087 |

- The per-phrase measure separates real boundaries from shifted ones for every boundary source
  except the grid. Unlike structural coherence, it tolerates boundaries that are off by a beat
  or two.
- The raw `concave_share` and `arc_r2_within` are not comparable across boundary sources: they
  depend on the number of phrases (the proxy has twice as many, so its in-sample arc R² is
  higher). Compare the excesses.
- On Batik the proxy and cadence boundaries give similar excesses. On Vienna the cadence
  boundaries are much closer to the annotations.

## Conclusion

1. Cadence-derived ends are the best annotation-free boundary source measured here (end F1
   0.46 vs 0.29 held out at ±1 beat; starts 0.44 vs 0.35). That is still half of the errors,
   and half cadences are mostly missed.
2. Structural-coherence tempo R² needs beat-precise ends, which this detector does not give:
   it falls below the proxy on Batik (held out) and on Vienna. **Tempo coherence is not usable
   without annotations.**
3. The per-phrase tempo measure (`concave_excess` against the shifted null) does not need that
   precision. It is positive with annotated, cadence and proxy boundaries and null with a grid.
   It is the annotation-free tempo-shaping measure to carry into H4 / R-09 as a secondary
   channel.

## Code changes

- `features/cadence.py` (new): `cadence_candidates`, `cadence_phrase_ends` (ends, starts,
  per-bar table), `pick_ends`, `starts_from_ends`, `CadenceConfig`, fitted `DEFAULT_WEIGHTS`.
- `features/shaping.py`: `phrase_tempo_shaping` / `PhraseTempoResult` (per-phrase, per-bar,
  null and summary). `shaping()` is unchanged.
- `features/score_basis.py`: `BasisConfig.phrase_source` (`proxy` default, `cadence` opt-in).
- `data/batik_mozart.py` (D-11): `iter_aligned(musicxml_score=True, stems=...)`,
  `load_aligned`, `performed_score`, `phrase_annotations` / `PhraseAnnotations`.
  `scripts/check_phrase_f05b.py` now uses them.
- Tests: `tests/features/test_cadence.py` (cue values at a V-I arrival, PAC and HC detection on
  a synthetic chorale, picking, start rules, the opt-in source) and two tests in
  `tests/features/test_shaping.py`:
  - concave arcs over 3-5-bar phrases give a share of 1.0 and a positive excess;
  - convex arcs give 0, with unmatched notes present.

  Also `tests/data/test_batik_mozart.py`: ids, beats, markings and label mapping.

## Not verified

- One pianist, one composer. Held-out movements share the training pianist's style and the
  composer's cadence idiom. The detector's weights are Mozart-specific (e.g. bass on the
  dominant). They were not tested on Romantic repertoire.
- Vienna is one 18-bar theme, and its ±1-beat F1 rests on 10 annotated ends.
- The ±2-bar null is one choice. For phrases of 4 bars, a 2-bar shift is maximally out of phase;
  for 8-bar phrases it is not.
- The Wilcoxon tests treat movements as independent.

# F-05e: phrase measures with LLM boundaries

Measured 2026-09-28 by `feature-engineer`. Pre-registered experiment
`experiments/2026-09-28-F-05e-llm-phrase-measures/` (README has the rule, all tables, the run
record and one disclosed deviation). Code: `shaping.merge_short_phrases` (new) and the one-off
`run.py`. Status: Confirmed with caveats (`eval-auditor`, 2026-09-28; see the EXPERIMENTS.md
row for the caveats: pooled level only, carried by Batik, Romantic placement loss).

## Answer

- **Yes, on average, LLM boundaries recover most of the tempo-shaping signal that DCML
  boundaries give.** Over the 8 movements that have both blind LLM annotations (R-08a/b/d) and
  aligned performances, mean `concave_excess` is 0.418 with LLM phrase starts against 0.473 with
  DCML starts: a paired difference of −0.055 (t [−0.138, +0.027]), within the pre-registered
  −0.10 margin by point estimate. LLM beats the F-05c cadence detector in all 8 (+0.221,
  t [+0.068, +0.374]).
- **On Batik Mozart they match DCML** (0.437 vs 0.452, 5 movements, 4 LLM runs each). F-05c's
  held-out reference (+0.42 annotated vs +0.21 detector) is reproduced on these 5: 0.452 DCML,
  0.293 detector.
- **On the 3 Romantic pieces with performances, LLM boundaries lose 0.124** (0.385 vs 0.508;
  Tchaikovsky op. 37a/6 −0.147, Chopin op. 7/4 −0.210, Träumerei −0.015), more than the margin,
  though still far above the detector (0.036). n = 3, transcribed PianoCoRe performances: a
  warning, not a result.
- **The over-segmentation fix is not needed on this evidence, and merging hurts on Romantic
  pieces.** Merging LLM phrases shorter than 4 bars leaves Batik unchanged (+0.011) but lowers the
  Romantic mean by 0.111; merging to 8 bars destroys the signal (−0.265 vs DCML). Two reasons:
  - Half of a parabola has the same curvature sign, so marking a concave arc as two halves does
    not make the halves convex. `concave_excess` is already fairly tolerant of a split phrase
    (synthetic test `test_merge_short_phrases_restores_concave_share`).
  - The LLM's losses are not about level. The oracle grouping (for each DCML start, the nearest
    LLM start within a bar) recovers DCML's value almost exactly (−0.009). What costs signal is
    where the LLM puts its extra and missing boundaries, which a length rule cannot find.
  - Caveat: R-08d's clearly over-segmented piece (Liszt S.160/2, predicted/DCML ≈ 2.7) has no
    aligned performances, so the case the merge was designed for was not tested.
- **Phrase-aware coherence (tempo R² without markings) cannot be validated here.** On these 8
  units DCML boundaries do not beat the proxy (+0.015, 4/8), so there is no signal to recover;
  LLM − DCML is −0.017.

## Recommendation

1. For the H4 / R-09 secondary tempo channel, LLM phrase starts may replace the cadence
   detector's (DECISIONS 2026-09-28, after F-05c) on Classical sonata movements: there they match
   DCML. Use them raw, **without** `merge_short_phrases`.
2. On Romantic repertoire, expect a loss of about a quarter of the DCML excess (0.12 of 0.51 on 3
   pieces). LLM boundaries are still much better than the detector there. Report the boundary
   source with every value, and do not compare excesses across boundary sources.
3. `merge_short_phrases` stays available as an opt-in tool; it is not a default. A piece that is
   clearly over-segmented (predicted/DCML phrase count above about 2) was not tested.
4. Structural-coherence tempo R² stays limited to annotated phrases (F-05b/c), and F-05e adds no
   evidence for LLM boundaries there.

## Data and method (short)

- LLM phrase events: R-08a (M1-M5), R-08b B1, B2 and the disguised run A (Batik, 4 runs), R-08d
  A and B (R1-R3). Mapped with the scorers' own `map_events`. R-08c (J. C. Bach) has no
  performances.
- Performances: Batik (1 per movement); PianoCoRe tier A on the full refined score, 30 drawn per
  piece (seed 20261002; Chopin op. 7/4 has 18). Grieg op. 57/1 and Liszt S.160/2 have no tier A
  performances. MazurkaBL has no op. 7/4.
- PianoCoRe boundaries are mapped by DTW over unique onsets (pitch-set Jaccard). Boundary
  pitch-set agreement: 0.94-0.97 on the Romantic pieces.
- Harness: the Batik DCML, detector, proxy and grid rows equal F-05c's exactly.

## Code changes

- `features/shaping.py`: `merge_short_phrases(starts, min_bars, beats_per_bar, end_beat)`,
  which merges the shortest phrase with its shorter neighbour until every phrase is at least
  `min_bars` bars long.
- `tests/features/test_shaping.py`: a known-answer test of the merge rule, and a synthetic
  split-arc test (halves keep a concave sign; merging restores the true phrases).

## Not verified

- n = 8 units; 5 are one pianist. Romantic n = 3, transcribed. Run-to-run variation of the LLM
  excess reaches 0.2 in some movements (K.533/1, Tchaikovsky).
- Over-segmented pieces (R-08d R5-like) are untested for tempo.
- The ±2-bar null is weaker for long phrases, which partly explains the 8-bar merge loss.
