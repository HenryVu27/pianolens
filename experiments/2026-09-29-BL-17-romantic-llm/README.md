# BL-17: is the LLM phrase annotator's mean end F1 above 0.70 on Romantic piano repertoire? (24 + 6 DCML movements, disguised)
Ticket: BL-17    Hypothesis: follow-up to R-08d (gate for LLM phrase boundaries on the target repertoire; feeds H4 / R-09)    Status: Provisional (pre-registered 2026-09-29; no annotation exists yet)

Prepared and run by `ml-researcher`. The annotators are separate, blind agents with no repo
path. Nothing in this header may be edited after any annotation is produced. Corrections go in
new sections at the end.

## Question

R-08d found a mean phrase-end F1 of 0.737 (±1 beat) for the in-session Claude annotator on 5
DCML Romantic pieces (one per corpus), a GO by the point-estimate rule, but with t-interval
[0.439, 1.036]: the between-movement SD (0.241) made the interval useless, and the audit licensed
the result only "at the mean level, with per-piece risk". BL-17 asks the question R-08d could
not answer:

**Is the annotator's mean end F1 (±1 beat) above 0.70 on DCML-labelled Romantic character
pieces in simple meters, with an interval narrow enough to make or reject that claim?**

Secondary: the same on compound meters (6/8, 9/8, 12/8), reported separately; whether the
annotator beats the F-05c detector; how much R-08b's disguise costs on Romantic music (a subset
also gets an undisguised run); run-to-run variation; granularity and the uncadenced-end split.

## Verdict rule (primary: simple-meter stratum, n = 24)

- **Per-movement score:** phrase-end F1 at ±1 beat (R-08a's metric: one beat = the time
  signature's denominator; one-to-one matching, closest pairs first), averaged over the two
  disguised runs A and B of that movement.
- **Primary:** the unweighted mean of the per-movement scores over the 24 simple-meter movements.
- **Interval:** the t-interval over movements (23 df), 95%. The percentile bootstrap (10,000
  resamples over movements, seed 20261002) is reported next to it; the t-interval decides.
- **MADE** ("the mean is above 0.70"): the t-interval's lower end is above 0.70.
- **REJECTED** ("the mean is below 0.70"): the t-interval's upper end is below 0.70.
- **INCONCLUSIVE:** the t-interval contains 0.70. The interval is then reported as the range
  the data allow, and nothing is claimed about 0.70.
- **Usable interval:** t half-width ≤ 0.10. Reported as met or not met; it does not change the
  verdict.
- Reported next to the verdict, not part of it: the R-08 point-estimate label (primary ≥ 0.70
  "GO", else "NO-GO") for continuity with R-08a-d; the one-sided t-test p of mean > 0.70; the
  worst-run variant (lower of A and B per movement) with its t-interval; the best-run variant;
  the leave-one-movement-out minimum and maximum; each run alone; per-corpus means
  (descriptive, no test).
- **Beats the detector** (secondary): the paired mean (LLM − detector) over the 24 movements > 0
  and its t-interval (23 df) excludes 0 → "shown".
- The 0.70 bar is `DECISIONS.md`'s (2026-09-27 after F-05b; restated after D-12), copied.

### Can each branch be reached? (R-09 audit lesson; `power.py`, run before this header was fixed)

`power.py` reads the 15 per-movement LLM F1 values of R-08a, R-08c and R-08d from their
artifacts (between-movement SD: R-08d 0.240, R-08c 0.130, all 15 0.159; mean within-movement run
SD 0.041) and simulates the verdict for n movements × 2 runs (20,000 simulated studies per cell,
seed 20261002) under a normal model (true movement means N(μ, SD) clipped to [0, 1]) and an
empirical model (the 15 observed values, centred, resampled and shifted to μ; this keeps R-08d's
heavy lower tail). Output: `artifacts/power.txt`. For n = 24:

| true mean μ | normal SD 0.13: P(MADE) / P(REJECTED) | normal SD 0.24: P(MADE) / P(REJECTED) | empirical: P(MADE) / P(REJECTED) |
|---|---|---|---|
| 0.55 | 0.000 / 1.000 | 0.000 / 0.877 | 0.000 / 1.000 |
| 0.60 | 0.000 / 0.939 | 0.000 / 0.567 | 0.000 / 0.937 |
| 0.65 | 0.000 / 0.424 | 0.001 / 0.218 | 0.001 / 0.258 |
| 0.70 | 0.023 / 0.026 | 0.016 / 0.041 | 0.065 / 0.008 |
| 0.737 (R-08d) | 0.252 / 0.000 | 0.074 / 0.007 | 0.263 / 0.000 |
| 0.80 | 0.937 / 0.000 | 0.391 / 0.000 | 0.799 / 0.000 |
| 0.85 | 0.999 / 0.000 | 0.739 / 0.000 | 0.970 / 0.000 |
| mean t half-width | 0.055 | 0.088-0.097 | 0.065 |

Reading, fixed now:

- Both MADE and REJECTED are reachable: MADE is likely if the true mean is 0.80 or more (0.39 to
  0.94 at 0.80, depending on the spread), REJECTED if it is 0.60 or less.
- **If the true mean is near R-08d's 0.737, INCONCLUSIVE is the most likely outcome** (0.74 to
  0.92). Separating 0.737 from 0.70 would need an interval half-width of about 0.03, which with
  a between-movement SD of 0.13-0.24 means well over 100 movements. BL-17 does not try; it aims
  at an interval about ±0.06 to ±0.10 wide, which either makes or rejects the claim when the
  mean is at least about 0.10 from the bar, and otherwise bounds it.
- With the skewed empirical spread, the t-rule claims MADE at a true mean of exactly 0.70 in
  6.5% of simulated studies (nominal 2.5%). This is disclosed, not corrected: a MADE with a
  lower end within 0.02 of 0.70 is to be read with this in mind.
- Moving from 24 to 30 movements narrows the half-width only from about 0.065 to 0.057
  (empirical), so 24 was chosen to leave annotator budget for the compound stratum and the
  undisguised subset.

## Recognition and label exposure

The disguise (below) is R-08b's memorisation control. Each annotation has `recognised_piece`; I
classify each string, by reading the string only, as **correct** (right composer and right
piece: opus/number or title), **composer** (right composer, no or wrong piece), **wrong**
(another composer or piece) or **none** (null, or no named composer or piece). The hand-back text
is also read; a guess there that the string lacks is recorded as "borderline" in
`recognition.json` and does not change the class (self-report is a lower bound). Rules:

- Recognised vs unrecognised is compared only within a movement (R-08b audit), never pooled.
- If any simple-stratum movement is `correct` or `composer` in either run, the primary is also
  reported without those movements. If 8 or more of the 24 are, the verdict is worded "on
  largely recognised pieces".
- **Label exposure** (R-08c audit): DCML's Romantic labels were released on 2025-04-27, before
  the model's cutoff, so exposure is not excluded by anything here. The granularity table (P, R,
  predicted/DCML ratio per movement and run) is reported; it can argue against recall only where
  levels differ (R-08d audit: ratios near 1 are uninformative).

## Data

- DCML corpora (`DATASETS.md`, D-13; CC BY-NC-SA 4.0), sparse clones under
  `data/raw/dcml_<corpus>/` at the D-13 tags: `chopin_mazurkas` v3.2, `grieg_lyric_pieces`,
  `tchaikovsky_seasons`, `schumann_kinderszenen`, `liszt_pelerinage` v2.3. Loader
  `pianolens.data.dcml`: `load_score(corpus, stem, unfold=True, tempo_word=False)` (label-free
  `notes`, `measures`, `chords` TSVs only) and `phrase_annotations(score)` for the hidden ground
  truth (`}`, `}{` ends; `{`, `}{` starts; PAC, IAC, HC, EC, DC, PC cadences) mapped to every pass.
- Detector inputs: D-13's cache `data/interim/dcml_romantic/cands.pkl` and `comparators.csv`
  (all 146 eligible movements are in both). The F-05c detector was fitted on Batik K.279-K.283,
  so every movement is held out for it.
- Only the 5 corpora downloaded under D-13 are used. lit-scout lists 9 DCML Romantic piano
  corpora with phrase labels; fetching the other 4 is data-engineer work outside this ticket.

## Movement selection (`draw.py`, seed 20261002; fixed before any rendering is built)

**Pool:** R-08d's pool function (imported from R-08d's `draw.py`, unchanged): every labelled
movement of the 5 corpora, with at least 5 folded DCML phrase ends, `unfold_validated=True`,
and at most 120,000 rendered characters (R-08a renderer, id `X`). **R-08d's 5 movements are
excluded.** Two strata:

- **simple:** every time signature has numerator 2, 3 or 4 (R-08d's rule; a movement that changes
  between simple meters is allowed). Pool: Chopin 48, Grieg 44, Tchaikovsky 8, Schumann 9,
  Liszt 6 (115).
- **compound:** every time signature has numerator 6, 9 or 12. Pool: Grieg 7, Tchaikovsky 2,
  Liszt 3 (12). Movements that mix simple and compound meters (e.g. 6/8 + 2/4) are in neither
  stratum.

**Allocation** (fixed): simple 24 = Chopin 10, Grieg 8, Tchaikovsky 2, Schumann 2, Liszt 2
(close to proportional to the pool, 10.0 / 9.2 / 1.7 / 1.9 / 1.3, with at least 2 per corpus);
compound 6 = Grieg 3, Tchaikovsky 1, Liszt 2. So the primary estimates the mean over a
roughly pool-proportional mix, dominated by Chopin mazurkas and Grieg Lyric Pieces (18 of 24).

**Draw** (`numpy.random.default_rng(20261002)`): for each stratum in the order simple, compound,
and each corpus in the order above, `rng.choice(len(members), n, replace=False)` over the
stratum's members of that corpus sorted by stem (simple random sampling within corpus; R-08d's
size tertiles are dropped because each corpus now gives several pieces). Then blind ids
`P01`..`P30` by `rng.permutation(30)` over all picks (so an id encodes neither stratum nor
corpus); then per movement in id order the disguise draw (`s`, then `c`, below); then the U subset:
`rng.choice` of 8 of the 24 simple-stratum ids without replacement. Everything goes to
`artifacts/selection.json` (never given to an annotator) and is appended below under "Selection
outcome".

## The disguise (runs A and B; R-08b's, applied to R-08d's scores)

`build.py` renders each movement with R-08a's `common.render` inside R-08b's `disguised`
context manager (both imported, unchanged), on R-08d's score (`load` from R-08d's `build.py`:
`tempo_word=False`, identity rule for printed text). As in R-08b:

1. **Transposition** by `s` semitones, drawn uniformly from {−6..−1, +1..+6}.
2. **Consistent respelling** on the line of fifths by `k` (7k ≡ s mod 12), key signatures shifted
   by `k`; R-08b's rule picks the candidate k that minimises the largest |fifths| of the shifted
   key signatures. **Added rule:** if that k would need a triple sharp or flat for any note of
   the movement, the other candidate is used (R-08b's code raises an error there; Romantic
   scores use more accidentals than Mozart). If both fail, the build stops and this is reported
   before any annotation.
3. **No markings:** every dynamic, hairpin, tempo word and free text is removed; only double
   barlines remain (the DCML loader has no fermatas).
4. **Bar numbers offset** by `c`, drawn from 20..479 (running and numeric score bar numbers).
5. **Fresh ids** `P01`..`P30`, and R-08b's legend (bar numbers start at an arbitrary number; no
   markings lines). Pointer bars read "same notes as bars a-b".

This removes Romantic phrasing cues that R-08d's input kept (rit., a tempo, tempo changes,
dynamics). The disguised test is therefore harder than R-08d on that point; the U subset
measures by how much.

## The undisguised subset (run U; descriptive)

The 8 U-subset movements also get one undisguised run: R-08d's rendering exactly (R-08a
renderer, `tempo_word=False`, markings kept, R-08d's identity rule, bars from 1, same `P##` id)
in `blind_input_U/`. The disguise effect is U − mean(A, B) per movement, averaged over the 8,
with its t-interval (7 df), and whether U lies inside, above or below the A-B range. It is
descriptive and does not enter the verdict. (With one U run, run noise enters U but is halved in
mean(A, B); the within-movement run SD of R-08c/d, 0.041, bounds that.)

## Instructions, schema, prompt

- `INSTRUCTIONS.md` and `SCHEMA.json` are R-08d's (R-08a's with the period phrase dropped), with
  only these changes: one movement per folder ("a text rendering of one piano movement (the
  `.txt` file in this folder)" and "the one `.txt` rendering"), output named after the rendering,
  ids `P##` (schema pattern `^P[0-9]{2}$`), and, in the disguised version, the pointer wording
  "same notes as bar(s) ..." (R-08b's change). R-08d's worked example bars (4, 7) are kept in the
  disguised version (bars start at c + 1 ≥ 21, so they never exist). In the U version R-08d's
  collision rule is applied to the 8 U movements, starting from (4, 7).
- Cadence types stay R-08a's (PAC, IAC, HC, EC, DC, none); DCML PCs are reported as recall only.
- **Prompt:** R-08d's template (in its transcripts), with the folder, the one file and the output
  path filled in, the sentence "The instructions mention five movements; you are assigned ONLY
  R1" dropped (each folder holds one rendering), and one added sentence: "The rendering may be
  longer than one read; read it to the END line." (R-08d's two long renderings needed two
  reads each; this asks for the whole file and adds no content cue.) It names no composer,
  corpus, period, or that a piece is famous, disguised or transposed.

## Conditions and blinding (R-08a-d protocol and audit lessons)

- Runs A and B: one fresh annotator per movement and run on the disguised rendering (60). Run U:
  one fresh annotator per U-subset movement on the undisguised rendering (8). 68 annotators in
  all. Model: in-session `claude-opus-5-5`, `general-purpose` agent type, launched by the
  ml-researcher session in the background. Agent ids and times are recorded in the run record
  below.
- **Each annotator gets its own folder outside the repo**, in the session scratchpad
  (`bl17/<run>_<id>/`), holding only `INSTRUCTIONS.md`, `SCHEMA.json`, its one `P##.txt` and an
  empty `out/`. It never gets a repo path, `artifacts/` or `selection.json`.
- One pass, no feedback. A technical failure (no file, malformed JSON, truncated read) may be
  rerun once with a fresh agent before scoring, and is disclosed. If a run is still missing, the
  movement uses the run that exists (disclosed).
- Each JSON is copied verbatim into `annotations_A/`, `annotations_B/`, `annotations_U/` before
  scoring. Transcripts (`subagents/agent-<id>.jsonl` of this session) are checked for file access:
  every tool call must be a read of the three allowed files or a write of `out/P##.json` (or a
  read-back of it). Any other file access is reported, and that annotation is excluded and rerun
  once with a fresh agent (disclosed).

## Metrics (`score.py`)

R-08a's scoring functions and R-08d's helpers, imported unchanged. Per run and movement, as in
R-08d: end P/R/F1 at ±1 beat (primary input) and ±1 bar; start F1; DCML cadence F1; cadence recall
by type via phrase ends and via all cadence marks; confidence ≥ 0.5 variant; exact onset; ±1
quarter note (bar-by-bar conversion); each repeated passage once; cadenced vs uncadenced recall;
granularity (P, R, predicted/DCML ratio). New, from audit lessons:

- **Boundary controls (F-05e audit):** (i) random ends at the LLM's count per movement and run
  (200 draws of onsets without replacement, seeded), mean F1; random at DCML's count; (ii) the
  DCML ends plus the onset nearest the midpoint of every DCML phrase-end segment ("halved DCML",
  a correct but twice-finer segmentation), F1. Reported next to the LLM.
- **Low scorers (R-08d audit):** for every movement with LLM < 0.50, every miss and extra in each
  run with its distance in bars to the nearest DCML end (extras) or predicted end (misses).
- **Reachability after the run (R-08d audit):** the observed between-movement SD next to the
  assumed ones.

Compound stratum: the same numbers, reported separately (n = 6, 5 df); the ±1 quarter and ±1
bar sensitivities matter more there (one beat = an eighth note). All 30 pooled: descriptive.

## Comparators (same movements, computed before any annotation)

F-05c detector (`cadence_phrase_ends`, shipped defaults, `tempo_word=False` score; its own score
on the performed beats is the comparator), `proxy_last_onset`, `proxy` (starts), `grid4`,
`oracle_dcml_ends`, as in R-08d; plus the two controls above.

## Checks (must pass before any annotator runs)

`build.py --check`:
- every rendering (disguised and U): R-08d's check (R-08a banned vocabulary and Roman numerals;
  the movement's DCML label strings; composer, catalogue, stem, corpus and every title word of
  the 5 corpora; provenance words) plus no old ids (`M#`, `Q#`, `R#`);
- disguised renderings also: no `[` marking, no dynamic token; **transposition** token by token
  against the same code with s = k = c = 0 (MIDI + s, fifths + k); key-signature lines + k;
  **structure**: bar table = the plain bar table with bars + c and fifths + k; pointer map = the
  untransposed one + c;
- both `INSTRUCTIONS.md` and `SCHEMA.json`: R-08d's text check (label strings ≥ 4 of all 30
  movements, identity, old ids) plus no `R#`;
- planted cues (a label string, `V7`, `PAC`, `Chopin`, `Grieg`, `op. 68`, the stem, `R3`,
  `[p]`, the movement's own title word) fire in every disguised rendering.

`score.py --harness`:
1. DCML ends and starts written as (bar, beat) events through each rendering's bar table: F1
   1.000 (disguised, all 30; U, all 8); also reported with printed bars only plus propagation.
2. The detector through the disguised path (propagation off) equals D-13's `cadence` rows in
   `comparators.csv` for every movement; identical with `tempo_word=True`; its pass-consistency
   (propagated vs own) is reported.
3. End-to-end dry run in a temporary folder: oracle as annotation → primary 1.000; detector as
   annotation → the detector's propagated mean.

## Method

1. `power.py` → `artifacts/power.txt` (done before this header was fixed).
2. `draw.py` → `artifacts/selection.json`.
3. `build.py` → `blind_input/`, `blind_input_U/`, `artifacts/` (bar tables, ground truth,
   `disguise.json`, `render_sizes.csv`, `identity_removals.json`); `build.py --check`.
4. `score.py --comparators`; `score.py --harness`.
5. Hash this README up to `## Preparation record`, record it, then run the 68 annotators.
6. Copy the JSONs; transcript check; `score.py --llm-dir ... --run A|B|U`; fill
   `recognition.json`; `score.py --compare` → `artifacts/bl17_summary.txt`; Results below.

## Command

```
uv run python experiments/2026-09-29-BL-17-romantic-llm/power.py
uv run python experiments/2026-09-29-BL-17-romantic-llm/draw.py
uv run python experiments/2026-09-29-BL-17-romantic-llm/build.py
uv run python experiments/2026-09-29-BL-17-romantic-llm/build.py --check
uv run python experiments/2026-09-29-BL-17-romantic-llm/score.py --comparators
uv run python experiments/2026-09-29-BL-17-romantic-llm/score.py --harness
uv run python experiments/2026-09-29-BL-17-romantic-llm/score.py --llm-dir experiments/2026-09-29-BL-17-romantic-llm/annotations_A --run A
uv run python experiments/2026-09-29-BL-17-romantic-llm/score.py --llm-dir experiments/2026-09-29-BL-17-romantic-llm/annotations_B --run B
uv run python experiments/2026-09-29-BL-17-romantic-llm/score.py --llm-dir experiments/2026-09-29-BL-17-romantic-llm/annotations_U --run U
uv run python experiments/2026-09-29-BL-17-romantic-llm/score.py --compare
```

Seeds: power, draw, disguise, bootstrap and random controls 20261002 (random controls per run
20261003-20261005). Code state: uncommitted (the repo has no commits); sha256 of scripts and blind
inputs in the preparation record.

## Threats to validity (known before running)

- **Population.** 5 corpora, pool-proportional, so the primary is mostly Chopin mazurkas and
  Grieg Lyric Pieces. It says little about Liszt (2 simple pieces; R-08d's worst piece was Liszt),
  nothing about long Romantic forms (ballades, sonatas) or other composers, and the t-interval
  treats the drawn movements as a sample from this pool only.
- **Annotation standard.** DCML phrase levels in Romantic music are a judgement call; per-corpus
  annotators differ. A low score can reflect the standard as much as the annotator.
- **Disguise removes information.** Markings (rit., a tempo, dynamics, tempo changes) are gone in
  A and B; U measures the cost on 8 movements only.
- **Label exposure** is not excluded (pre-cutoff DCML labels). Recognition is self-report.
- **Compound stratum** n = 6: descriptive; one beat = an eighth note, so ±1 beat is narrow.
- **Run-to-run:** two runs per movement; the verdict uses their mean.
- **Skew:** the t-rule's false-MADE rate at a true 0.70 was 6.5% under the empirical spread
  (above).

## Selection outcome (draw.py, seed 20261002, run 2026-09-29 before any blind input was built or any annotation existed)

| Id | Stratum | Corpus | Movement (stem) | Time | Bars (performed) | Characters (disguised) | DCML ends (unfolded) | DCML cadences | Disguise s / k / c | Double-accidental tokens | U run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P01 | simple | liszt_pelerinage | 160.01_Chapelle_de_Guillaume_Tell | 4/4 | 97 | 47,788 | 17 | 17 | -5 / +1 / 241 | 0/3959 |  |
| P02 | simple | grieg_lyric_pieces | op38n05 | 3/4 | 80 | 9,836 | 11 | 2 | -4 / -4 / 283 | 0/590 |  |
| P03 | simple | chopin_mazurkas | BI77-1op17-1 | 3/4 | 102 | 16,066 | 13 | 11 | -2 / -2 / 479 | 0/1097 | yes |
| P04 | simple | schumann_kinderszenen | n08 | 2/4 | 49 | 8,826 | 10 | 10 | +1 / -5 / 331 | 6/511 |  |
| P05 | simple | chopin_mazurkas | BI145-2op50-2 | 3/4 | 186 | 26,164 | 20 | 11 | +1 / +7 / 353 | 0/1738 |  |
| P06 | simple | chopin_mazurkas | BI93-2op67-3 | 3/4 | 57 | 14,236 | 7 | 7 | -6 / -6 / 136 | 12/946 | yes |
| P07 | simple | grieg_lyric_pieces | op62n06 | 2/4 | 150 | 31,855 | 11 | 12 | +2 / +2 / 414 | 4/2186 |  |
| P08 | simple | chopin_mazurkas | BI115-3op33-3 | 3/4 | 49 | 11,609 | 10 | 6 | -5 / +1 / 392 | 0/749 |  |
| P09 | compound | liszt_pelerinage | 160.03_Pastorale | 12/8 6/8 | 49 | 21,438 | 10 | 10 | +6 / -6 / 34 | 0/1473 |  |
| P10 | compound | grieg_lyric_pieces | op54n02 | 6/8 | 159 | 38,301 | 12 | 6 | +3 / -3 / 44 | 0/2677 |  |
| P11 | simple | chopin_mazurkas | BI145-1op50-1 | 3/4 | 104 | 23,543 | 9 | 1 | -3 / +3 / 61 | 11/1628 | yes |
| P12 | simple | chopin_mazurkas | BI85 | 3/4 | 73 | 14,493 | 15 | 15 | -1 / +5 / 154 | 0/959 | yes |
| P13 | simple | liszt_pelerinage | 160.05_Orage | 2/2 | 163 | 76,624 | 17 | 11 | +3 / -3 / 220 | 76/6004 |  |
| P14 | simple | tchaikovsky_seasons | op37a11 | 4/4 | 83 | 43,455 | 17 | 11 | +2 / +2 / 357 | 80/2836 |  |
| P15 | simple | chopin_mazurkas | BI115-2op33-2 | 3/4 | 144 | 34,323 | 17 | 26 | +3 / -3 / 110 | 27/2559 |  |
| P16 | compound | grieg_lyric_pieces | op47n03 | 6/8 | 106 | 26,272 | 6 | 3 | +6 / -6 / 323 | 258/2109 |  |
| P17 | simple | tchaikovsky_seasons | op37a02 | 2/4 | 181 | 42,241 | 31 | 18 | -5 / +1 / 403 | 18/2858 | yes |
| P18 | simple | chopin_mazurkas | BI126-3op41-1 | 3/4 | 139 | 32,828 | 14 | 6 | +6 / -6 / 290 | 0/2368 |  |
| P19 | simple | grieg_lyric_pieces | op57n05 | 3/4 | 169 | 43,227 | 13 | 10 | -5 / +1 / 162 | 0/2604 |  |
| P20 | simple | grieg_lyric_pieces | op68n06 | 3/4 | 202 | 35,062 | 11 | 4 | -1 / +5 / 460 | 216/2512 |  |
| P21 | simple | grieg_lyric_pieces | op71n05 | 2/4 | 170 | 27,842 | 21 | 11 | -1 / +5 / 159 | 8/1808 | yes |
| P22 | simple | chopin_mazurkas | BI61-2op07-2 | 3/4 | 125 | 14,229 | 15 | 12 | -3 / +3 / 149 | 0/853 | yes |
| P23 | simple | grieg_lyric_pieces | op71n04 | 2/2 | 77 | 26,116 | 10 | 8 | +5 / -1 / 63 | 0/1704 |  |
| P24 | simple | schumann_kinderszenen | n04 | 2/4 | 17 | 7,311 | 8 | 6 | +1 / -5 / 220 | 0/374 |  |
| P25 | compound | liszt_pelerinage | 160.04_Au_Bord_dUne_Source | 12/8 | 66 | 63,292 | 13 | 13 | +5 / -1 / 34 | 90/4272 |  |
| P26 | simple | grieg_lyric_pieces | op38n01 | 2/4 | 86 | 19,314 | 6 | 4 | -4 / -4 / 178 | 25/1350 |  |
| P27 | compound | tchaikovsky_seasons | op37a04 | 6/8 | 87 | 26,633 | 24 | 10 | +4 / +4 / 469 | 3/1940 |  |
| P28 | simple | chopin_mazurkas | BI89-3op24-3 | 3/4 | 80 | 11,761 | 6 | 6 | +2 / +2 / 159 | 0/658 | yes |
| P29 | compound | grieg_lyric_pieces | op43n02 | 6/8 | 31 | 9,824 | 7 | 7 | -4 / -4 / 74 | 0/604 |  |
| P30 | simple | grieg_lyric_pieces | op68n03 | 2/4 | 114 | 20,930 | 5 | 3 | -2 / -2 / 114 | 10/1196 |  |

The pool, the picks, the disguise draw and the U subset are in `artifacts/selection.json`; the
k actually used per movement in `artifacts/disguise.json` (never given to an annotator). The
simple stratum is 10 Chopin, 8 Grieg, 2 Tchaikovsky, 2 Schumann, 2 Liszt; compound 3 Grieg, 1
Tchaikovsky, 2 Liszt. U subset: P03, P06, P11, P12, P17, P21, P22, P28 (5 Chopin, 2 Grieg, 1
Tchaikovsky).

## Preparation record (2026-09-29, ml-researcher; no annotation exists yet)

Everything above this section is the pre-registration. Its sha256 (the file up to, not
including, the line `## Preparation record`) is given at the end of this section.

### Edits to the header before hashing (disclosed)

- The "Selection outcome" section was appended after `draw.py`, `build.py` and the checks ran
  (as in R-08a, R-08c and R-08d). Nothing above it was changed after the draw.
- After the checks, the scripts were edited to pass `ruff` only (percent formats to f-strings in
  `score.py`, `strict=True` and a line wrap in `power.py`, a default argument binding the loop
  variable in `build.py`'s planted-cue check). `power.py` was rerun and `artifacts/power.txt` is
  byte-identical; `build.py --check` and `score.py --harness` were rerun and pass.

### Renderings and disguise

- 30 disguised renderings, 7,311-76,624 characters (R-08d's range 9,197-48,099). P13 (76,624
  characters, 1,844 lines) and P25 (63,292) are the longest; the prompt asks the annotator to
  read to the `END` line.
- The k rule never needed the added fallback (`k_rejected` is empty for all 30). Shifted key
  signatures run from 7 flats (P30: −7 and 0) to 6 sharps (P07, P14, P22). **Double
  accidentals** are more common than in R-08b's Mozart (at most 4.0% there): P16 12.2% of note
  tokens, P20 8.6%, P14 2.8%, P25 2.1%, P26 1.9%, P06 and P13 1.3%, P04 1.2%, others ≤ 1.1%;
  15 of 30 have none. Disclosed, not redrawn (the rule is R-08b's).
- Identity rule: two printed texts were removed before rendering, "Tempo di Valse" (P19) and
  "Tempo di Valse tranquillo" (P20), because "valse" is a Grieg title word
  (`artifacts/identity_removals.json`). Neither is in a U movement, and the disguise drops all
  markings anyway, so this changes no blind input.
- U renderings keep the printed markings, e.g. P12 "Poco mosso . = 52" (a metronome figure
  entered as staff text), "calando", "come sopra"; P17 "Allegro giusto", "L'istesso tempo";
  P21 "Allegro moderato e marcato", "Allegro molto(Doppio movimento)", "Tempo primo", "(segue)";
  P06 "rubato", "poco rit."; P22 "scherz.", "stretto"; P28 "l.h.", "perdendosi". None names a
  composer, piece or catalogue number.
- Labels off an onset: P01 1, P18 1; all others 0.
- The U worked example moved from R-08d's (4, 7) to **(11, 14)** by R-08d's rule (the first pair
  clear of every DCML boundary within 1 beat in all 8 U movements). The disguised
  `INSTRUCTIONS.md` keeps (4, 7). `diff` against R-08d's `INSTRUCTIONS.md`: the disguised version
  differs in the one-file wording (3 lines), the pointer wording and the example id `P01`; the U
  version differs from the disguised one only in the pointer wording and the example bars.

### Checks (all PASSED)

- `build.py --check`: all 30 disguised and 8 U renderings pass R-08d's check (no banned word,
  Roman numeral, DCML label string, identity, title or provenance word, old id); every disguised
  rendering has no `[` and no dynamic token; transposition verified token by token (for example
  P13: 6,001 note tokens, 0 bad), key signatures, bar tables (+c, +k) and pointer maps (+c) all
  match the untransposed rendering from the same code. Both `INSTRUCTIONS.md` and both
  `SCHEMA.json` pass. Every planted cue fires in every disguised rendering.
- `score.py --harness` (`artifacts/harness.txt`): DCML oracle F1 1.000 (ends and starts) through
  every disguised bar table (30) and every U bar table (8), also with printed bars only plus
  propagation; the detector through the disguised path equals D-13's `cadence` rows (12 of 12 per
  movement, 0 mismatches) and is identical with the tempo word; it is pass-consistent in 29 of 30
  movements (P12: own 0.611, propagated 0.595); dry run: oracle primary 1.000, detector 0.3070
  vs its propagated mean 0.3066.
- R-08a `common.py`, `render.py`, `score.py` and R-08d `draw.py`, `build.py`, `score.py` hash to
  the values in their preparation records (272d81dd, 82785dc0, b73b1b7e; 5f5bd518, c3db78ae,
  2dbdf97d), so they are unchanged. R-08b `disguise.py` hashes to af854024.

### Comparators (`artifacts/comparators.csv`, `comparators_summary.txt`)

Mean end F1 at ±1 beat over the stratum: F-05c detector **0.307** (simple, 24) and **0.298**
(compound, 6); `proxy_last_onset` 0.261 / 0.098; `grid4` 0.171 / 0.073; random ends at DCML's
count 0.125 / 0.072; halved DCML 0.667 in every movement (P 0.5, R 1.0 by construction).
Detector at ±1 bar: 0.439 / 0.337. The detector is weaker here than on R-08d's 5 (0.389).

### For the annotation run

- Folders `<scratchpad>/bl17/<run>_<id>/` (run A, B: all 30 ids; run U: the 8 U ids), each with
  `INSTRUCTIONS.md`, `SCHEMA.json`, its one `P##.txt` (from `blind_input/` for A and B, from
  `blind_input_U/` for U) and an empty `out/`.
- Prompt (identical for all 68 after filling the folder and id):
  "You are a music-theory annotator. Your whole world for this task is the folder <FOLDER>/ .
  Read ONLY these files there: INSTRUCTIONS.md, SCHEMA.json and <ID>.txt. Do not open, list or
  search any other file or folder on the computer, do not use the web, and do not use any tool
  other than reading those three files and writing your output. The rendering may be longer than
  one read; read it to the END line. Follow INSTRUCTIONS.md exactly: one pass, annotate from the
  rendering, name the piece in recognised_piece if you recognise it (but do not annotate from
  remembered analyses). Write your answer as valid JSON conforming to SCHEMA.json to
  out/<ID>.json in that folder. Then reply with: the number of events by type and cadence,
  whether you recognised the piece, and any difficulties with the format."

### Files and code state

- Code state: uncommitted (the repo has no commits). sha256 prefixes (`build.py --hashes`):
  `power.py` e21c5cdc, `draw.py` 5a5a66d5, `build.py` bd101392, `score.py` d5b61671;
  `blind_input/INSTRUCTIONS.md` 0c702f94, `SCHEMA.json` f963a6f5 (both folders),
  `blind_input_U/INSTRUCTIONS.md` f61a410c; `P01.txt`..`P30.txt` 7db5368d, c5f07eba, c50b005f,
  0dc3c4b7, fa2abe58, 80c80dfe, 7fe93f0c, f083009a, 6b852b6f, 41a9a5b1, eaf125ef, cafb01d8,
  c4a7863e, 41cae5a3, 81df1a9b, af243d9d, fbbf656c, 56db899c, 4a9ad905, 5dd661aa, d4cef06e,
  7aace4b1, c28e1c5b, 3b72f59a, 1da673e4, 700b7b4c, 479326e7, eb28c844, 31b92871, 3d093ca9;
  U `P03`, `P06`, `P11`, `P12`, `P17`, `P21`, `P22`, `P28`: ea43fa4c, e44de027, 2928e985,
  9da31598, a6ae38ef, b979d552, 64c1c744, 713a95ac.
- Data: DCML Romantic corpora at the D-13 tags; D-13 cache `data/interim/dcml_romantic/`.
- Pre-registration sha256 (README up to `## Preparation record`): `c3803f83bb9f23b76a5aae99b9c0c5497c14eba1f04733e2bd4f8dc3d2bb2462`. Computed before any
  annotator was launched.

## Annotation run record (2026-09-29, ml-researcher; after the hash)

- 68 blind annotators (general-purpose agents, model `claude-opus-5-5` in every transcript),
  launched from this ml-researcher session in batches as the 20-agent concurrency limit allowed.
  First annotator event 2026-09-29T21:09:56Z (16:09:56 local); the README was last modified at
  16:09:07 local, when the hash line was written, so the whole pre-registration predates every
  annotation. No technical failure, no rerun. All 68 JSON files parse, name their own id, and
  map with 0 dropped events.
- **Refused launches (added after the audit).** There were 82 `Agent` calls. 14 were refused with
  "Concurrent subagent limit reached" before any agent started (A P17-P20 and P28-P30; B P01,
  P04, P15, P22, P23, and P28 twice) and were re-issued. So exactly 68 annotators ran, one per run
  and movement: this is not a rerun, and no annotation existed twice to choose between.
- Agent ids (run/id: agent), also in `artifacts/bl17_agents.tsv`:
  - A: P01 a8170bfeceb24ad0a, P02 a6bf5a46131372942, P03 a287d7f16e86a32bd, P04 acaef7acdeb5384a9,
    P05 a32beca38e277fe88, P06 a6e7054d8d044f6b2, P07 a1d011cfe7da607cb, P08 a080f571d945fb731,
    P09 a2badff476f6397e0, P10 a7d81f2c5b98aa0aa, P11 a2811f8affe9d6ed9, P12 ab8ab514752807de8,
    P13 af9377473b1b9c91d, P14 aca2280570d1a0bcd, P15 aa161d336ae4bf2e1, P16 a0c12b2468fa9e721,
    P17 a9a493ccdf96ecb89, P18 a56183995cbbd2b30, P19 a764ad65ce680f84c, P20 aa6e7ddfc372bf0ec,
    P21 a41a65494c8c4f3c1, P22 a405eae751e53a261, P23 a1eed2277595a3522, P24 afcdb399d9e704d63,
    P25 a1ed50574c6d2a0fe, P26 a7b2dae313d8c36e2, P27 acabaa47b296af107, P28 a8646c590468a4d4f,
    P29 a00957150791a6a91, P30 a7ec9f79d79cca68f.
  - B: P01 ac8d3d271fe23c6d9, P02 acb67105cc301e79a, P03 ab3f267844d42f4a0, P04 a4a8df6358143dcdd,
    P05 a4d7d0808e58f3e5b, P06 ad2961b854d5726dc, P07 a876e2c9b4aa6fbdd, P08 a5e9c2ae1b7f4f19e,
    P09 a173daab9e436d4b7, P10 a550bca6dca09ddbe, P11 a9f662a434bb30008, P12 a0115506590801eda,
    P13 a61752c9c2271ef3d, P14 aee0b03829a5355b6, P15 aad5b8eaf9bbba094, P16 ae3417394c1cfe49e,
    P17 ade18956badbb59f8, P18 acd1ce87d606c63cd, P19 a5cadd85ec349c677, P20 abc0de391800c85ee,
    P21 a591d22826901cdbd, P22 a5d5cba5613c47ce0, P23 a4ab9d380709c091b, P24 aacfad63c726a0838,
    P25 aa647860baa374c70, P26 a52ce973a2c2ab8c2, P27 a2a38824bbe7df0e6, P28 afc2bd4d8af60838f,
    P29 a757b982f7fd5da96, P30 a3705078256b30e1a.
  - U: P03 a964cd97a59190d9a, P06 af38f01dc2703d30c, P11 a2add090133e68b34, P12 a26a68648dd53eb6f,
    P17 ad8d523d0ec1261fc, P21 ac18605a44d11ede4, P22 a780290bbf23b4d74, P28 a02550860e611704f.
- **Transcript check** (`artifacts/audit_transcripts.py`, output `artifacts/bl17_transcript_audit.json`;
  transcripts are `~/.claude/projects/-Users-vuducdung-personal/9591b65d-.../subagents/agent-<id>.jsonl`):
  - Tools used: only Read, Bash and (once) Write. Every Read targets `INSTRUCTIONS.md`,
    `SCHEMA.json` or the annotator's own `P##.txt` in its own folder (15 of 68 needed two to four
    Reads of the rendering; all 68 reached the `END` line). No web tool, no `ls`, `find` or `grep`.
  - Every Bash call is `mkdir -p <own>/out` plus a write of `<own>/out/P##.json` (heredoc `cat >`,
    or Python `json.dump`), sometimes followed by a `json.load` of that same file; the only `cd`
    targets are the annotator's own folder or its `out/`. No absolute path outside the own folder
    appears in any command. So blinding is clean in all 68.
  - **Disclosure (added after the audit).** No repo path is in the prompt or the inputs. But, as
    in R-08a-d, each annotator's harness `environment` block shows the working directory
    `/Users/vuducdung/personal/pianolens`, and its loaded auto-memory index names the PianoLens
    project. None of DCML, Chopin, Grieg, Schumann, Liszt, Tchaikovsky, mazurka, Romantic, BL-17,
    R-08 or `selection.json` appears in that context, and no annotator accessed anything outside
    its folder. The header's "It never gets a repo path" holds for the prompt and inputs only.
  - The 68 prompts reduce to 3 texts after normalising folder and id: one per run (the folder
    prefix `A_`, `B_`, `U_` differs), identical otherwise.
  - Inputs in each scratch folder are byte-identical to `blind_input/` or `blind_input_U/`; each
    folder holds only the 3 files and `out/`; the 68 repo annotations are byte-identical to the
    scratch outputs.
- **Recognition** (`recognition.json`, classified from the strings only; auditor to verify):
  4 non-null strings. A/P12 and B/P12 "possibly Beethoven, Sonata op. 79, i" (wrong; P12 is Chopin
  BI 85). B/P22 "Possibly a Chopin mazurka-type movement in F-sharp minor" (composer: right composer,
  no piece; the rendering is transposed). U/P22 "Chopin, Mazurka in A minor, Op. 68 No. 2"
  (composer: right composer and key, wrong opus; P22 is op. 7 no. 2). Hand-back or `notes` guesses
  with a null string (borderline, class unchanged): A/P05 "feels Chopin-like", A/P06 "sounds like a
  Chopin waltz", B/P03 "a Chopin-style A-flat waltz", B/P11 "possibly Chopin", U/P06 "style
  suggests a Chopin mazurka", U/P11 "could be Beethoven or Haydn".

## Results (audited 2026-09-29: Confirmed with caveats; wording corrected after the audit)

Full tables: `artifacts/bl17_summary.txt` (from `score.py --compare`); per-run rows in
`artifacts/scores_A.csv`, `scores_B.csv`, `scores_U.csv`.

### Primary (simple meters, 24 movements, mean of disguised runs A and B)

| Quantity | Value | t-interval (23 df) | Bootstrap |
|---|---|---|---|
| **LLM end F1 ±1 beat** | **0.635** | **[0.549, 0.720]** | [0.552, 0.711] |
| F-05c detector (same movements) | 0.307 | | |
| LLM − detector, paired | +0.327 | [+0.237, +0.418] | [+0.238, +0.407] |
| Random ends at the LLM's count (control) | 0.127 | | |
| Halved DCML (correct but 2x finer, reference) | 0.667 | | |

- **Verdict by the pre-registered rule: INCONCLUSIVE.** The t-interval [0.549, 0.720] contains
  0.70, so "the mean is above 0.70" is not made, and "the mean is below 0.70" is not shown
  either (upper end 0.720). The interval is usable by the pre-registered criterion (half-width
  0.085 ≤ 0.10). What the data allow: a mean end F1 between about 0.55 and 0.72 on this pool.
- **R-08 point-estimate label (continuity only): NO-GO** (0.635 < 0.70). One-sided p of mean > 0.70
  is 0.94. Worst-run variant 0.596 (t [0.516, 0.676], entirely below 0.70); best-run 0.674; run A
  alone 0.624 (t [0.534, 0.714]), run B 0.646 (t [0.558, 0.733]). Leave-one-out range 0.622-0.656.
- **Beats the detector: shown.** Paired +0.327, t [+0.237, +0.418]; ahead on 23 of 24 movements
  (the exception is P12, Chopin BI 85: 0.366 vs 0.611). LLM − random-at-same-count +0.508,
  t [+0.432, +0.583], so the score is not a density effect.
- **Reachability after the run (R-08d audit lesson):** observed between-movement SD 0.202,
  between the assumed 0.13 and 0.24; the half-width (0.085) is as planned. The interval is
  informative, and INCONCLUSIVE is not an artefact of spread: the point estimate sits 0.065
  below the bar.
- **Against R-08d (descriptive, different pieces; corrected after the audit):** the two studies
  do not differ detectably. R-08d minus BL-17 on per-movement means is +0.103, Welch t
  [-0.189, +0.394], p 0.41 (auditor's computation). Three candidate reasons, none separated from
  the others: sampling noise in R-08d's 5 movements (enough on its own), corpus weighting (R-08d
  took one movement per corpus; BL-17 is pool-proportional, and its corpus-equal simple mean is
  0.687, descriptive, three corpora with n = 2), and the disguise (+0.032, t [-0.082, +0.147],
  n = 8). R-08d's GO is not confirmed; BL-17's estimate is the better one for this pool.

Per movement (mean of A and B; `U` = the undisguised run where it exists):

| Id | Corpus | Stem | A | B | Mean | U | Detector | DCML ends |
|---|---|---|---|---|---|---|---|---|
| P03 | chopin | BI77-1op17-1 | 0.743 | 0.839 | 0.791 | 0.703 | 0.312 | 13 |
| P05 | chopin | BI145-2op50-2 | 0.525 | 0.653 | 0.589 | | 0.200 | 20 |
| P06 | chopin | BI93-2op67-3 | 0.857 | 0.857 | 0.857 | 0.857 | 0.471 | 7 |
| P08 | chopin | BI115-3op33-3 | 0.750 | 0.750 | 0.750 | | 0.720 | 10 |
| P11 | chopin | BI145-1op50-1 | 0.467 | 0.462 | 0.464 | 0.414 | 0.067 | 9 |
| P12 | chopin | BI85 | 0.348 | 0.385 | 0.366 | 0.667 | 0.611 | 15 |
| P15 | chopin | BI115-2op33-2 | 0.588 | 0.653 | 0.621 | | 0.388 | 17 |
| P18 | chopin | BI126-3op41-1 | 0.606 | 0.667 | 0.636 | | 0.077 | 14 |
| P22 | chopin | BI61-2op07-2 | 0.839 | 0.684 | 0.761 | 0.703 | 0.167 | 15 |
| P28 | chopin | BI89-3op24-3 | 0.545 | 0.545 | 0.545 | 0.706 | 0.250 | 6 |
| P02 | grieg | op38n05 | 0.600 | 0.692 | 0.646 | | 0.231 | 11 |
| P07 | grieg | op62n06 | 0.643 | 0.583 | 0.613 | | 0.538 | 11 |
| P19 | grieg | op57n05 | 0.258 | 0.357 | 0.308 | | 0.000 | 13 |
| P20 | grieg | op68n06 | 0.258 | 0.286 | 0.272 | | 0.133 | 11 |
| P21 | grieg | op71n05 | 0.800 | 0.708 | 0.754 | 0.680 | 0.410 | 21 |
| P23 | grieg | op71n04 | 0.632 | 0.762 | 0.697 | | 0.143 | 10 |
| P26 | grieg | op38n01 | 0.833 | 1.000 | 0.917 | | 0.286 | 6 |
| P30 | grieg | op68n03 | 0.143 | 0.133 | 0.138 | | 0.000 | 5 |
| P01 | liszt | 160.01 Chapelle | 0.765 | 0.743 | 0.754 | | 0.429 | 17 |
| P13 | liszt | 160.05 Orage | 0.667 | 0.667 | 0.667 | | 0.095 | 17 |
| P04 | schumann | n08 | 0.800 | 1.000 | 0.900 | | 0.900 | 10 |
| P24 | schumann | n04 | 1.000 | 0.667 | 0.833 | | 0.400 | 8 |
| P14 | tchaikovsky | op37a11 | 0.545 | 0.629 | 0.587 | | 0.190 | 17 |
| P17 | tchaikovsky | op37a02 | 0.759 | 0.772 | 0.765 | 0.833 | 0.356 | 31 |

Per corpus (descriptive, no test): Chopin 0.638 (n 10, t [0.528, 0.749]), Grieg 0.543 (n 8,
t [0.316, 0.770]), Liszt 0.710 (2), Schumann 0.867 (2), Tchaikovsky 0.676 (2). 14 of 24
movements are below 0.70; 5 are below 0.50 (P11, P12, P19, P20, P30), 3 of them Grieg.

### Compound meters (6 movements, reported separately)

Mean 0.654, t (5 df) [0.460, 0.849]; detector 0.298; paired +0.356, t [+0.104, +0.607]. Same rule,
descriptively: INCONCLUSIVE; point estimate below 0.70. ±1 quarter note 0.663, ±1 bar 0.692,
exact onset 0.633, so the narrow eighth-note beat is not what holds the score down. Per movement:
P29 Grieg op. 43/2 0.933, P09 Liszt Pastorale 0.800, P27 Tchaikovsky op. 37a/4 0.683, P25 Liszt
Au bord d'une source 0.544, P16 Grieg op. 47/3 0.483 (A 0.300, B 0.667), P10 Grieg op. 54/2 0.480.
All 30 pooled (descriptive): 0.639, t [0.565, 0.712].

### Sensitivities (simple stratum; LLM / detector)

- Exact onset 0.555 / 0.234; ±1 quarter note 0.635 / 0.307; each repeated passage once
  0.644 / 0.318; **±1 bar 0.702** (t [0.625, 0.778]) / 0.439. *Corrected after the audit:* the
  ±1 bar interval also contains 0.70, and the window is lenient in these metres. From ±1 beat to
  ±1 bar the 4-bar grid rises from 0.171 to 0.405 (+0.234), `proxy_last_onset` from 0.261 to
  0.459 and the detector from 0.307 to 0.439, while the LLM gains +0.067. A random-at-LLM-count
  control at ±1 bar was not computed. ±1 bar is not a route to the bar: adopting it would be a
  post-hoc change of metric and needs its own pre-registration with that random control.
- Confidence ≥ 0.5 filter: 0.565 (A), 0.550 (B), lower than unfiltered, so not a fix.
- Recognition sensitivity: without P22 (the only simple movement classed composer in a run),
  0.629, t [0.540, 0.718].

### Disguise effect (U subset, 8 simple movements; descriptive)

U 0.695 vs disguised mean(A, B) 0.663 on the same 8; U − disguised +0.032, t (7 df) [−0.082,
+0.147], bootstrap [−0.049, +0.129]. U lies inside the A-B range in 2 of 8, above in 3, below in 3.
No consistent cost of the disguise is shown. One movement moves a lot: P12 (Chopin BI 85) U 0.667
vs A 0.348 / B 0.385; its undisguised rendering carries "Poco mosso", "a tempo", "calando", "come
sopra". Without P12 the U − disguised mean is −0.006 (7 movements). With n = 8 the interval
cannot rule out a cost or a gain of about 0.1.

### Run-to-run

Run means A 0.623, B 0.654 (all 30); mean within-movement SD 0.057 (R-08d 0.056, R-08c 0.027);
largest |A − B| 0.367 (P16, compound), then 0.333 (P24) and 0.200 (P04), the two Kinderszenen
pieces with 8 and 10 DCML ends, where one boundary moves F1 a lot.

### Where the errors are (R-08d audit lessons)

- **Both error types are substantial (corrected after the audit).** Mean P / R over all 30:
  A 0.591 / 0.709, B 0.628 / 0.728, so recall 0.71-0.73 and precision 0.59-0.63. On the simple
  stratum (auditor's decomposition) each run misses 88 of 314 DCML ends at ±1 beat; only 26 (A)
  and 21 (B) of those misses are within ±1 bar of a predicted end, so 62-67 per run (about a fifth
  of all DCML ends) have no predicted end within a bar. Unmatched predictions: 188 of 414 (A) and
  158 of 384 (B). Extra, finer ends are the larger count, but real misses are not rare. Median
  predicted/DCML ratio 1.17 (A) and 1.15 (B); ratio > 1.5 in 10 (A) and 8 (B) of 30 movements,
  < 0.67 in 3 each: a mild tendency to finer phrases than DCML's, as in R-08c Q3 and R-08d R5.
  The halved-DCML reference (0.667, recall 1 by construction) is above the LLM's 0.635, so finer
  segmentation alone does not explain the score.
- **Cadenced vs uncadenced DCML ends** (simple, pooled): recall A 125/165 and 101/149, B 129/165
  and 97/149; detector 73/165 and 32/149. Uncadenced ends (68% / 65% recall) are harder than
  cadenced ones (76% / 78%), a smaller gap than in R-08d.
- **Low scorers (< 0.50), each miss and extra listed in `bl17_summary.txt`:**
  - *P19 (Grieg op. 57/5, 0.308): mostly a one-bar placement convention in run A; in run B,
    half the misses are that, plus finer segmentation (corrected after the audit).* In A, 7 of 9
    misses are exactly 1 bar from a predicted end (bars 170, 186, 214, 238, 266, 290, 328); the
    other two are 2 bars away. The A annotator's hand-back names the reason: the tonic bass lands
    under a dominant appoggiatura chord and the tonic chord only sounds in the next bar; DCML
    marks the bass arrival, the annotator the resolution. In B only 4 of 8 misses are 1-bar
    offsets; two are 2 bars away and two 6 bars (238, 290). Both runs add 4-5 ends 7-13 bars from
    any DCML end. At ±1 bar it still scores only 0.710 (A) and 0.643 (B).
  - *P12 (Chopin BI 85, 0.366) is the reverse level mismatch.* DCML marks 15 ends in 73 bars (two
    bar units, ends on beat 2); the annotator marks 8 (A) and 11 (B), ratio 0.53 / 0.73, P 0.50 /
    0.45, R 0.27 / 0.33. Misses are 2/3 to 2 bars from a predicted end in the theme and 6-10 bars in
    the coda. The undisguised run scores 0.667.
  - *P30 (Grieg op. 68/3, 0.138)* has 5 DCML ends in 114 bars; the annotators mark 9 and 10, hitting
    1 of 5 in each run (misses 2-6.5 bars away). Sparse ground truth plus a different reading of
    the long pedal sections.
  - *P20 (Grieg op. 68/6, 0.272)*: ratio 1.8 / 1.6, misses 0.7-3.3 bars away (HC placement within
    long dominant stretches and a beat-1 vs beat-3 arrival choice).
  - *P11 (Chopin BI 145-1, 0.464)*: ratio 2.3 / 1.9 with recall 0.78 / 0.67: finer subdivisions
    (14 extras in A, 1-14 bars from a DCML end), only 2-3 misses.
  - Compound *P10 (Grieg op. 54/2, 0.480)*: every miss is 2 or 4-4.5 bars from a predicted end in
    both runs (HC placed at the bass arrival 2 bars before DCML's, and sequence ends placed 4 bars
    off), so again placement rather than detection.
- **Label exposure:** the granularity table shows level mismatches in both directions in several
  movements (finer: P11, P28, P05, P15; coarser: P12, P08), which argues against label recall
  there. Movements with ratios near 1 and high P and R in both runs (P06, P26, P04) are uninformative
  (R-08d audit lesson).
- **Cadence recall by type via phrase ends** (all 30, A / B / detector / DCML-ends reference):
  PAC 113 / 111 / 71 / 118 of 136; HC 44 / 51 / 24 / 52 of 74; IAC 39 / 38 / 22 / 44 of 52;
  PC 5 / 4 / 0 / 14 of 14.

## Verdict (Confirmed with caveats, eval-auditor 2026-09-29; paragraph 2 corrected after the audit)

**INCONCLUSIVE by the pre-registered rule.** On 24 disguised DCML Romantic character pieces in
simple meters (10 Chopin mazurkas, 8 Grieg Lyric Pieces, 2 each Tchaikovsky, Schumann, Liszt), the
blind annotator's mean phrase-end F1 at ±1 beat is 0.635 with t-interval [0.549, 0.720]. The claim
"mean above 0.70 on Romantic repertoire" is **not made**: the interval's lower end is 0.15 below
the bar, the point estimate is below it, and the worst-run interval lies wholly below it. The
claim is not formally rejected either, because the upper end (0.720) just includes 0.70. The
R-08-style point-estimate label would be NO-GO. The annotator still beats the F-05c detector
clearly (+0.327, t [+0.237, +0.418], 23 of 24). Compound meters (n = 6) look similar (0.654,
t [0.460, 0.849]). The disguise's cost on 8 movements is not shown (+0.032, t [−0.082, +0.147]).

What this changes for R-08d's licence: R-08d's GO is not confirmed. BL-17's 0.635
[0.549, 0.720] is the better estimate for this pool, and the two studies do not differ
detectably (Welch +0.103 [-0.189, +0.394], p 0.41); sampling noise, corpus weighting and the
disguise are all candidate reasons, none separated. About a quarter to a third of the misses are
within one bar (placement convention: which onset counts as the arrival); the rest are real
misses or a different phrase level, and extra, finer ends are the larger error. At ±1 bar the
mean is 0.702, but that interval (t [0.625, 0.778]) also contains 0.70 and a 4-bar grid gains
more from the wider window than the annotator does, so ±1 bar is not a route to the bar; using
it would need a new pre-registration with a random control at that tolerance. What follows (for
example a period cue or an arrival rule in the instructions) is the lead's decision.

## Threats to validity (after the run)

- **Different input and weighting from R-08d.** R-08d's renderings kept markings and started at
  bar 1; these are disguised. The U subset shows no consistent disguise cost, but with n = 8 it
  cannot exclude one of about 0.1. R-08d also weighted corpora equally. BL-17 and R-08d do not
  differ detectably (see Results), so there is no gap that needs explaining; sampling noise,
  corpus weighting and the disguise are candidates if one is ever shown.
- **The bar offset reads as an excerpt.** Several annotators wrote that the rendering "starts
  mid-movement" (bar numbers in the hundreds). This may change how they treat the first phrase.
  It is part of R-08b's registered disguise.
- **Transposition into remote keys** (up to 7 flats, up to 12% double-accidental tokens in P16)
  makes the harmony slower to read; P16 has the largest run-to-run gap (0.300 vs 0.667).
- **Style recognition.** No piece was named correctly, but "Chopin" appears as a style guess in
  2 strings and 5 hand-backs, all on Chopin movements. Structural familiarity is not excluded;
  label exposure (pre-cutoff DCML labels) is not excluded.
- **Instructions lean on cadences and give no rule for where the arrival is when the bass and the
  chord arrive at different onsets.** Several annotators flagged exactly this (for example A/P19, B/P22, A/P27, B/P05),
  and it drives some of the ±1 beat misses.
- **Population.** 5 corpora only; 18 of 24 are Chopin or Grieg. Liszt, Schumann and Tchaikovsky
  have 2 each. The t-interval treats these as a sample from this pool, nothing wider.

## Audit (2026-09-29, eval-auditor)

**Verdict: Confirmed with caveats.** The pre-registered verdict, INCONCLUSIVE, stands, and every
headline number reproduces. The claim "mean end F1 above 0.70 on Romantic repertoire" is not
made. The annotator beats the detector (shown). Some of the text reads more into the numbers
than they support: the comparison with R-08d, the "placement convention, not missed phrases"
reading, "recall is high", and the ±1 bar figure. The corrected readings are below. They replace
the Results and Verdict wording wherever the two conflict. No number changes, so no
"Post-audit corrections" section is needed.

### What I checked

1. **Pre-registration.** `sha256` of the README up to `## Preparation record` equals
   `c3803f83...2462` (the raw bytes, with the blank line before the heading included). Timeline
   from the ml-researcher transcript (`subagents/agent-a5c313a816c9ab685.jsonl`):
   - `power.py` ran at 20:42Z, before the header. This is disclosed.
   - `draw.py` was written at 20:43Z and the README at 20:48:55Z. `draw.py` first ran at
     20:48:59Z, after the header was written. No draw or `--sizes` run came earlier.
   - Build, checks and comparators ran from 20:50Z to 21:01Z, then the ruff-only edits.
   - The Selection outcome was appended at 21:08:42Z and the hash computed at 21:09:06Z. The
     first annotator was launched at 21:09:28Z.

   The header has not changed since the hash. "Falsified if" and the verdict rule did not drift.
2. **Launch record.** There were 82 `Agent` calls. 14 of them were refused with "Concurrent
   subagent limit reached" before any agent started (A P17-P20 and P28-P30; B P01, P04, P15,
   P22, P23, and P28 twice). They were re-issued, so exactly 68 annotators ran, one per run and
   movement. No annotation was produced twice, so nothing could be selected. After normalising
   the folder and id, all 68 prompts are one template.
3. **Draw.** I re-ran the seeded draw from the stored pool. It gives the same 30 picks, ids,
   disguise draws (s, c) and U subset. The strata recompute from the pool rule. The pool counts
   match the header (simple 48/44/8/9/6, compound 7/2/3). R-08d's 5 movements are flagged
   `in_r08d` and none was drawn. Every simple pick is in 2/2, 2/4, 3/4 or 4/4. I did not re-run
   R-08d's `pool()` itself; it was audited in R-08d.
4. **Hashes.** `power.py`, `draw.py`, `build.py`, `score.py`, both INSTRUCTIONS files,
   `SCHEMA.json`, and all 30 + 8 renderings match the recorded sha256 prefixes.
5. **Blinding and access.**
   - I re-ran `artifacts/audit_transcripts.py` from a scratch copy. Its output equals the repo's
     `bl17_transcript_audit.json` except for B/P25's `end` timestamp (21:19:25Z vs 21:19:18Z):
     that agent's transcript has one trailing message after its hand-back.
   - The script's `issues` list is noisy. It flags fractions such as `/4` and the `mkdir` verb.
   - My own check over all 68 transcripts found 225 Reads, 68 Bash calls, 1 Write and 68
     hand-backs:
     - Every Read targets the annotator's own INSTRUCTIONS.md, SCHEMA.json, `P##.txt` or
       `out/P##.json`.
     - Every Bash call, with heredoc bodies stripped, uses only absolute paths inside the
       annotator's own folder. The only `cd` targets are `<own>` and `<own>/out`.
     - No annotator ran `ls`, `find`, `grep`, `git`, `uv`, a web tool or any other tool.
   - All 68 scratch inputs are byte-identical to `blind_input/` or `blind_input_U/`, and each
     folder holds exactly 4 entries. The 68 repo annotations are byte-identical to the scratch
     outputs.
   - **Disclosure fix:** "It never gets a repo path" is true of the prompt only. As in
     R-08a-d, each annotator's `environment` block shows the working directory
     `/Users/vuducdung/personal/pianolens`, and the loaded auto-memory index names the PianoLens
     project. The loaded context contains none of: DCML, Chopin, Grieg, Schumann, Liszt,
     Tchaikovsky, mazurka, Romantic, BL-17, R-08, `selection.json`. No annotator accessed any
     file outside its folder.
6. **Scoring.** I re-ran `run_llm` for A, B and U, then `compare()`, `run_comparators()` and
   `harness()`, with `ART` pointed at an absolute scratch copy.
   - `scores_A/B/U.csv`, `summary_A/B/U.txt`, `bl17_summary.txt`, `comparators.csv`,
     `comparators_summary.txt` and `harness.txt` are byte-identical to the repo files.
   - HARNESS PASSED: the oracle gives 1.000, and the detector dry run gives 0.3070 against 0.3066.
   - I recomputed the numbers independently from the per-run CSVs with scipy. All match:
     - primary 0.6346, t [0.5492, 0.7201], half-width 0.0855, SD 0.2024;
     - one-sided p(mean > 0.70) 0.936;
     - worst run 0.596 t [0.516, 0.676]; best run 0.674;
     - A 0.624, B 0.646; leave-one-out 0.622-0.656;
     - paired +0.327 t [+0.237, +0.418], 23 of 24;
     - 14 of 24 below 0.70; five below 0.50 (P11, P12, P19, P20, P30);
     - compound 0.654 t [0.460, 0.849]; all 30 pooled 0.639 t [0.565, 0.712];
     - U minus disguised +0.032 t [-0.082, +0.147], and -0.006 without P12;
     - U inside the A-B range 2 times, above 3, below 3;
     - per-corpus means; ±1 bar 0.702 t [0.625, 0.778];
     - cadenced/uncadenced recall counts; granularity counts.
7. **Verdict mapping.** The t-interval [0.549, 0.720] contains 0.70, so the result is
   INCONCLUSIVE, word for word. REJECTED would need an upper end below 0.70; the upper end is
   0.020 above it. The worst-run interval lies wholly below 0.70, but the pre-registration puts
   it next to the verdict, not in it. The observed SD (0.202) lies inside the assumed range, so
   the interval is informative as planned.

### Recognition (`recognition.json`): classes confirmed, three additions

- **P22 (Chopin op. 7/2, A minor).**
  - B/P22 "Possibly a Chopin mazurka-type movement in F-sharp minor": right composer and genre,
    no piece. The key is the transposed one (s = -3), so the annotator read it off the rendering.
  - U/P22 "Chopin, Mazurka in A minor, Op. 68 No. 2": right composer, genre and key, wrong piece.
    Op. 68/2 is the other A-minor mazurka. The hand-back says "Recognised piece: Yes", so this is
    a confident near-miss, not a style guess.

  Both are **composer** by the registered rule (right composer, wrong or no piece). Confirmed.
- **P12:** A and B "Beethoven op. 79/i" is **wrong**. Confirmed.
- **Borderline list, three additions.** The class does not change, per the pre-registration:
  - A/P05's hand-back and notes say "mazurka-like theme" and "polonaise-mazurka rhythm" as well
    as "Chopin-like". That is right composer and right genre, like U/P06.
  - U/P12 ("late-Romantic character piece writing") and B/P13 ("late-Romantic-style movement")
    are period guesses. The README's count of "Chopin" (2 strings, 5 hand-backs, all on Chopin
    movements) is correct.
  - Many mazurkas were called "waltz" (A/P03, B/P03, A/P06, B/P05, B/P06, B/P08, B/P11, B/P15).
    That is the right metre and texture but the wrong genre.
- **Within-movement comparison (R-08b rule), not in the Results:**
  - P22: A (none) 0.839, B (composer) 0.684, U (composer, undisguised) 0.703. The runs with
    recognition are not higher.
  - P12: both runs are "wrong", so there is no contrast.
- **Wider sensitivity (auditor's).** Dropping all five simple movements with any Chopin guess in
  any run (P03, P05, P06, P11, P22) gives 0.619, t [0.517, 0.722]. The verdict is the same.
- **Reading.** The disguise stopped naming the piece (0 correct in 68) but not naming the style
  or genre: "Chopin" plus "mazurka" was named on a transposed, marking-free rendering (B/P22).
  Structural familiarity and label exposure (pre-cutoff DCML) remain open, as the README says.

### The claim that R-08d's 0.737 is not confirmed: correct, but the reasons are incomplete

"Not confirmed" is right. But the README reads the gap as needing an explanation ("R-08d's
0.737 lies above this interval's upper end"; "BL-17 is lower than R-08d ... not attributable to
repertoire alone"). There is no demonstrated gap:

- **Sampling noise is enough on its own.** R-08d minus BL-17 on per-movement means is +0.103,
  Welch t [-0.189, +0.394], df 5.2, p 0.41. R-08d had 5 movements with SD 0.241. The two
  studies are statistically compatible, and 0.737 was a noisy estimate that did not replicate.
- **Corpus weighting is a second difference the README does not name.** R-08d drew one movement
  per corpus, so each corpus had equal weight. BL-17 is pool-proportional, and 18 of its 24
  movements are Chopin or Grieg. Grieg is the weakest corpus here (0.543). The corpus-equal
  mean of BL-17's simple stratum is 0.687 (descriptive; three corpora have n = 2). Weighting
  alone moves the estimate about halfway to R-08d.
- **Disguise** is the third: +0.032, t [-0.082, +0.147], n = 8.

None of the three is separated from the others, and none needs to be. The correct statement:
"R-08d's GO is not confirmed. BL-17's 0.635 [0.549, 0.720] is the better estimate for this
pool. The two studies do not differ detectably."

### Error analysis: partly confirmed, partly overstated

- **P19 (Grieg op. 57/5): confirmed for run A, weaker for run B.**
  - In A, 7 of 9 misses are exactly 1 bar from a predicted end: 170, 186, 214, 238, 266 and 290
    predicted one bar later, and 328 predicted at 327. The other two misses are 2 bars away.
  - I checked the mechanism in the rendering. Bar 170 has tonic bass G1 under a held F#-C-E
    (dominant) chord, and the G-B-D tonic chord first sounds in bar 171. The A hand-back names
    this.
  - In B only 4 of 8 misses are 1-bar offsets. Two are 2 bars away, and two are 6 bars away
    (238, 290).
  - Both runs also add 4-5 ends 7-13 bars from any DCML end, which are finer phrases.
  - At ±1 bar P19 still scores only 0.710 (A) and 0.643 (B).
  - Correct wording: "mostly a one-bar placement convention in run A; in run B, half the misses
    are that, plus finer segmentation."
- **"Recall is high, precision is the weaker side" is overstated.** On the primary stratum,
  pooled over the 24 movements, each run misses 88 of 314 DCML ends at ±1 beat (28%). Only 26
  (A) and 21 (B) of those misses fall within ±1 bar of a predicted end. The other 62-67 misses
  per run (about 20% of all DCML ends) are more than a bar from any predicted end. Unmatched
  predictions number 188 (A, 45% of 414) and 158 (B, 41% of 384). Both error types are
  substantial: extra, finer ends are the larger count, but real misses are not rare. Mean R is
  0.71-0.73, not "high". The halved-DCML reference (0.667; R = 1 by construction) is above the
  LLM's 0.635, which also shows that finer segmentation alone does not explain the score.
- **The over-segmentation ratio is confirmed as stated.** Medians are 1.17 (A) and 1.15 (B) over
  30 movements, or 1.24 and 1.15 on the simple stratum. The ratio is above 1.5 in 10 (A) and 8
  (B) movements and below 0.67 in 3 each. The tendency is mild.
- **"A visible part of the gap is placement convention and phrase level, not missed phrases"**
  (Verdict) should read: "about a quarter to a third of the misses are within one bar
  (placement convention); the rest are real misses or a different phrase level, and extra finer
  ends are the larger error."
- **±1 bar 0.702 is not a route to the bar.** Its t-interval [0.625, 0.778] also contains 0.70.
  The window is lenient in these metres: from ±1 beat to ±1 bar the 4-bar grid rises from 0.171
  to 0.405, `proxy_last_onset` from 0.261 to 0.459, and the detector from 0.307 to 0.439. The LLM
  gains less (+0.067) than the grid (+0.234). A random-at-LLM-count control at ±1 bar was not
  computed. Adopting ±1 bar now would be a post-hoc change of metric. It would need its own
  pre-registration, with the random control at that tolerance.
- **The label-exposure reading is confirmed.** Level mismatches run both ways (P11, P28, P05,
  P15 finer; P12, P08 coarser), and ratio-near-1 movements are uninformative.

### Downstream: DF-02 and F-05e

- **Using LLM boundaries in the report for Chopin pieces (DF-02) is the right choice of source,
  but the source is not validated.**
  - On Romantic character pieces, the LLM beats the cadence detector by +0.327 (23 of 24).
    Among the available sources, the LLM is the better one.
  - Its accuracy is below the project's 0.70 bar as a point estimate: 0.635, with the interval
    containing 0.70 and the worst-run interval wholly below it. Accuracy on a single piece varies
    widely, from 0.138 to 0.917, with 5 of 24 below 0.50.
- **DF-02's pieces are outside what BL-17 tested.**
  - The 5 cached pieces are 4 Chopin nocturnes and 1 waltz. BL-17's Chopin is mazurkas only,
    and no nocturne was tested.
  - 3 of the 5 are in compound or mixed metres: op. 9/1 in 6/4, op. 27/2 in 6/8, and op. 9/3 in
    2/2 + 6/8. BL-17's compound stratum is n = 6 (Grieg, Liszt and Tchaikovsky, in 6/8 and
    12/8; no 6/4, no Chopin) and descriptive only: 0.654, t [0.460, 0.849].
  - DF-02's annotators saw undisguised famous scores, and 9 of 10 recognised the piece. Nothing
    measures how remembered analyses shaped those boundaries.
- **F-05e's measure is the larger problem.** On the 3 Romantic units, `concave_excess` with LLM
  boundaries fell below the DCML level on all three (-0.124). It was also below "DCML + random
  extras at the LLM count", a placement loss. BL-17 is consistent with that: about a fifth of
  DCML ends have no predicted end within a bar. DF-02 then measured that the report value
  depends on the source: take 01 goes from -0.29/-0.25 (cadence) to +0.31 (LLM), take 05 from
  +0.08/+0.16 to +0.44/+0.38, and the A-B spread reaches 0.26. On Henry's Chopin, the sign of
  the phrase-tempo item can therefore depend on which unvalidated boundary source is used.
- **What the report should disclose,** in the shaping section and the methods footer:
  1. The source: LLM boundaries (model, date, two blind runs averaged), with the annotator having
     recognised the piece.
  2. Their measured accuracy against expert (DCML) annotations on Romantic character pieces:
     mean phrase-end agreement about 0.64 (plausible range 0.55-0.72), below the project's 0.70
     bar, and from 0.14 to 0.92 on single pieces (BL-17). They are clearly better than the rule
     detector (0.31).
  3. That nocturnes were never tested. Compound metres, including 6/4 and 6/8, are not
     validated (BL-17 n = 6, descriptive).
  4. That the phrase-tempo measure itself did not reach the expert-boundary level on Romantic
     pieces (F-05e). Show the detector-based value next to the LLM one, with the run spread.
     Where the two sources disagree in sign, report the item as undetermined.
  5. That no practice item or judgement depends on this number. DF-02 says none does, and that
     should stay so.

  The current `PHRASE_CAVEATS` text cites F-05e only for "romantic" and "R-08d" for
  "compound_meter". It should cite BL-17's boundary accuracy and BL-17's descriptive compound
  result. The methods paragraph in `report/render.py` should add the accuracy sentence.
  `docs/SCORING_MODEL.md` (the Shaping row, "Phrase ends come from a rule detector") is stale
  since DF-02. This is the lead's to fix, as DEFECTS already notes.

### Required corrections (text only; numbers unchanged)

1. **R-08d comparison** (Results "Against R-08d", Verdict paragraph 2, Threats "Different input"):
   say the two studies do not differ detectably (Welch +0.103 [-0.189, +0.394], p 0.41). Name
   three candidate reasons, none separated: sampling noise at n = 5 (sufficient alone), corpus
   weighting (corpus-equal BL-17 mean 0.687, descriptive), and the disguise (+0.032
   [-0.082, +0.147]). Drop "not attributable to repertoire alone" as the framing.
2. **"Recall is high"** becomes "recall 0.71-0.73, precision 0.59-0.63". Add the miss/extra
   decomposition above: 88 misses of 314 per run, of which only 21-26 are within ±1 bar; 158-188
   extras.
3. **Verdict "placement convention and phrase level, not missed phrases"** becomes "about a
   quarter to a third of the misses are one-bar placement; the rest are real misses or a
   different phrase level".
4. **P19:** qualify the 1-bar pattern as run A (7 of 9); in run B it holds for 4 of 8.
5. **±1 bar:** state that its interval also contains 0.70, and give the grid and proxy
   comparison at ±1 bar. Any adoption of ±1 bar needs a new pre-registration with a random
   control at that tolerance.
6. **Blinding:** replace "never gets a repo path" with "no repo path in the prompt or inputs;
   the harness environment block shows the working directory, as in R-08a-d; no access outside
   the folder".
7. **Run record:** add that 14 `Agent` calls were refused by the concurrency limit before
   starting and were re-issued, so there was no rerun and no selection.
8. **Recognition:** add A/P05 "mazurka-like" to the borderline list, the two "late-Romantic"
   period guesses, the P22 within-movement comparison, and the all-Chopin-guess sensitivity
   (0.619, t [0.517, 0.722]).

### Not verified

- R-08d's `pool()` was not re-executed; the draw was replicated from the stored pool.
- Subagent thinking is redacted, so recognition remains self-report (a lower bound).
- DCML label exposure is not excluded.
- I did not audit DF-02's build or its access audit; the DF-02 figures above are from its
  DEFECTS entry and the feature-engineer memory.

Audit scripts are in the session scratchpad (`bl17_audit/`: `rerun.py`, `rerun2.py`,
`indep.py`, `decomp.py`, `r08d_cmp.py`, `blind_check.py`, `recog_scan.py`).

## Post-audit corrections (2026-09-29, ml-researcher)

The audit says no number changes, so strictly no such section is needed. The lead asked for one
so the text edits are traceable. No number was recomputed by me; every figure below is the
auditor's or was already in the Results. The pre-registration (everything above `## Preparation
record`) is untouched; its sha256 was rechecked after these edits and still equals
`c3803f83bb9f23b76a5aae99b9c0c5497c14eba1f04733e2bd4f8dc3d2bb2462`.

Text changed in place (each marked "corrected after the audit" or "added after the audit"):

1. **R-08d comparison** (Results "Against R-08d", Verdict paragraph 2, Threats "Different input"):
   now says the two studies do not differ detectably (Welch +0.103 [-0.189, +0.394], p 0.41) and
   names three candidate reasons, none separated: sampling noise at n = 5 (enough alone), corpus
   weighting (corpus-equal BL-17 simple mean 0.687, descriptive), and the disguise (+0.032
   [-0.082, +0.147]). "Not attributable to repertoire alone" is dropped.
2. **Recall and placement** (Results "Where the errors are", Verdict paragraph 2): "recall is
   high, precision is the weaker side" became "recall 0.71-0.73, precision 0.59-0.63", with the
   decomposition: 88 of 314 DCML ends missed per run, only 21-26 within ±1 bar; 158-188 extras.
   "Placement convention and phrase level, not missed phrases" became "about a quarter to a third
   of the misses are one-bar placement; the rest are real misses or a different phrase level".
3. **P19:** the 1-bar pattern is run A's (7 of 9 misses); in run B it holds for 4 of 8, the rest
   being 2- and 6-bar misses plus finer segmentation.
4. **±1 bar:** its interval [0.625, 0.778] also contains 0.70; the window is lenient (grid4
   0.171 → 0.405, `proxy_last_onset` 0.261 → 0.459, detector 0.307 → 0.439, LLM +0.067). Adopting
   ±1 bar needs a new pre-registration with a random-at-count control at that tolerance.
5. **Run record and blinding:** added the 14 refused `Agent` launches (concurrency limit,
   re-issued; no rerun, no selection) and the working-directory disclosure. The header sentence
   "It never gets a repo path" (Conditions and blinding) is pre-registered and stays; read it as
   "no repo path in the prompt or inputs; the harness environment block shows the working
   directory, as in R-08a-d; no access outside the folder".

Also from the audit (required correction 8, recorded here rather than in the run record):
A/P05 "mazurka-like" / "polonaise-mazurka rhythm" joins the borderline list (right composer and
genre); U/P12 and B/P13 "late-Romantic" are period guesses; within P22, the runs with recognition
are not higher (A none 0.839, B composer 0.684, U composer 0.703); dropping every simple movement
with any Chopin guess in any run (P03, P05, P06, P11, P22) gives 0.619, t [0.517, 0.722], same
verdict. `recognition.json` itself was not edited.

Status line in the header (line 2) still says Provisional because the header is frozen; the
audited status is in the Verdict heading and in `EXPERIMENTS.md`.
