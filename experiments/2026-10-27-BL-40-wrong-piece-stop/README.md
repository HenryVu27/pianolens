# BL-40: wrong-piece stop with partial alignment
Ticket: BL-40 (from the BL-37 audit)    Hypothesis: none from the plan (app rule)    Status: Provisional

## Question
The local app aligns the first take to the chosen score once (the quick check) and stops with
"probably another piece" when the Dice match ratio is below 0.5 (DF-05). With
`align(..., partial=True)` (BL-36) the score is trimmed to the span the recording covers, so a
right-piece excerpt scores 0.81-1.0 instead of its share of the piece. A wrong score is trimmed
too, and in the BL-37 audit 2 of 1,376 short (4-7 bar) wrong-score excerpts reached 0.5 (max
0.524); 28 were at or above 0.40.

Which quick-check rule for a trimmed span (a stop, possibly with a minimum length below which
the app asks the learner to confirm the piece) stops wrong-piece uploads, does not stop
right-piece excerpts or whole takes, and leaves whole recordings as today or better? Partial
alignment goes on in the app only if a rule chosen on dev passes a fresh held-out draw.

## Pre-registration

Written 2026-10-27 after the dev run on 32 seen pieces, before any BL-40 held-out piece was
drawn or aligned. The anchor hash is recorded in "Falsified if".

**The quick check measured.** Exactly the app's step 2 (`app/pipeline.py`): `report.io.
load_score` of a score file, `align_performance(score, performance, partial=...)` (which
re-reads the file), `correctness(ap).summary["match_ratio"]` (Dice: 2 * correct / (graded score
notes + performed notes)), and `score.meta["recorded_span"]["whole"]`. The performance is a
PianoCoRe transcription loaded as a transcribed upload (`report.io.load_performance(...,
"transcribed")`); an excerpt keeps the notes with onsets inside the window (times not shifted;
as in the BL-37 probe). A failed alignment counts as ratio 0 (in the app it fails the run, so it
is never a silent pass).

**Takes.** Per piece and transcriber family (Transkun V2, Aria-AMT): the first candidate
transcription whose whole take has ratio >= 0.8 on its own score with `partial=False` (up to 3
candidates); then one excerpt per length band, cut at graded bar boundaries of that alignment
(BL-36 `_graded_first_last` / `_bar_boundary`; seed `[40, crc32(id)]`, length uniform in the
band, start uniform in bars 1 .. n - length - 1):

| Band | Graded bars |
|---|---|
| 2-4 | 2 to 4 |
| 5-8 | 5 to 8 |
| 9-16 | 9 to 16 |
| 17-32 | 17 to 32 |
| whole | the whole take |

A band is skipped for a piece with fewer than length + 2 graded bars.

**Probes.** Every take of a pool is aligned to every score of the same pool (all ordered pairs,
both families) with `partial=True`. Whole takes are also aligned with `partial=False` (today's
path) to their own score and to the wrong scores they are probed on. On held-out every whole
take goes to every wrong score; on dev to a seeded sample of 8 (machine time, run record).
Hard cases are the pairs inside the pool: sibling movements (same PianoCoRe work folder, e.g.
`12_Études,_Op.10`) and same key signature, reported separately as information.

**Decision** (`pianolens.app.quick_check.decide`). `partial` off, or a span the aligner takes as
whole: today's rule, stop below 0.5. Trimmed span: a take with fewer than `n_min` performed
notes is asked to confirm the piece; otherwise stop below `t`, pass at or above.

**The registered rule: `t = 0.625`, `n_min = 75`, mode "all"** (a trimmed take under 75 notes
is asked to confirm whatever its ratio). How it was chosen on dev:
- Below about 75 notes the ratio does not separate the two sets: wrong-score excerpts reach
  0.748 (49 notes, Debussy Jardins sous la pluie on Chopin Op. 10 No. 7) and 0.647 (54 notes),
  right-score excerpts go down to 0.733 (11 notes).
- `n_min` is the smallest value on the grid (0, 25, 50, 75, 100, 150) at which the highest
  wrong-score ratio among takes with at least `n_min` notes lies at least 0.10 below the lowest
  right-score ratio: at 75, wrong max 0.578 (76 notes, Chopin Op. 10 No. 8 on Schumann Op. 17
  ii), right min 0.687 (545 notes, Aria-AMT, Schumann Op. 17 iii). At 50 the gap is 0.040.
- `t` is the midpoint of that gap rounded to the 0.025 grid (0.633 -> 0.625): margins 0.047 to
  the highest wrong ratio and 0.062 to the lowest right one.
- Mode "all" rather than "high": below 75 notes a low ratio says as little as a high one (right
  excerpts at 0.733); a confirm request is the honest message either way.

Considered and not registered (dev, means over pieces): `t = 0.65` with no minimum passes every
row (one wrong 2-4-bar excerpt passes, 0.05%; no confirm cost) but with margins of 0.003 to the
next wrong ratio and 0.037 to the lowest right one; today's stop of 0.5 with partial on passes
1.86% (2-4 bars), 0.15% (5-8), 0.05% (9-16) of wrong-score excerpts.

**Registered rows** (held-out, the registered rule; excerpt rows are means over source pieces of
per-piece shares, both families pooled within a piece):

| Row | What | Bar |
|---|---|---|
| H 2-4, H 5-8, H 9-16, H 17-32 | wrong-score excerpts passed silently (the harm; a confirm request is not a pass) | at most 0.25% each |
| F 2-4, F 5-8, F 9-16, F 17-32 | right-score excerpts stopped | at most 2.5% each |
| C 9-16, C 17-32 | right-score excerpts of 9 or more bars asked to confirm (cost) | at most 5% each |
| W1 | right whole takes whose decision is worse than today's (today pass, now stop or confirm) | 0 takes |
| W2 | wrong-score whole takes passed silently with `partial=True` | 0 alignments |

Scale: with 24 held-out pieces, one wrong pass in a piece is about 0.09 pt of H (46 wrong
alignments per piece and band), so H allows 2 and fails at 3 passes in a band if spread over
pieces; one false stop in a piece is about 2.1 pt of F, so F allows one per band.

**Bite check (dev; each row fails under some rule, so each can bite):**

| Rule (dev) | Rows that fail |
|---|---|
| stop 0.55, no minimum | H 2-4 (0.81%) |
| stop 0.80, no minimum | F 2-4 (4.69%), F 5-8 (4.69%), F 9-16 (3.12%) |
| registered with minimum 300 notes | C 9-16 (62.5%), C 17-32 (6.45%) |
| sabotage: stop 0.96 on every span, whole included | W1 (33 of 64 takes), all F rows |
| sabotage: stop 0.30 on every span, whole included | W2 (6 of 512), all H rows |

**Information, not deciding:** C 2-4 and C 5-8 (the cost of the minimum; dev 75.0% and 15.6%),
the wrong-score confirm shares, today's whole-take decisions with `partial=False`, the
hard-case table (sibling, same key, other) with the highest ratios, the same rows for today's
stop (0.5) with partial on and for neighbours of the rule (`t` 0.60 / 0.65, `n_min` 50 / 100),
the ratio quantiles per band and relation, and failed alignments.

**Statistics.** Per-piece means; 95% piece bootstrap (2,000 resamples of source pieces, scores
fixed); leave-one-piece-out (the piece dropped as source and as score), reporting which rows
flip; the share of bootstrap resamples that meet each bar.

**Verdict.** PASS if every registered row meets its bar on held-out (point estimates); else
FAIL. **If FAIL, partial alignment stays off in the app** (`PARTIAL_DEFAULT` unchanged, the
rule unused) and no other rule is tried on this draw. If PASS, the rule is wired in behind
`partial` (already in code, unused while `PARTIAL_DEFAULT` is False); switching the app to
`partial=True` is the lead's call after the audit.

**Dev (design data; disclosed).** 32 pieces of the BL-37 and BL-39 held-out draws; the first
candidate was accepted for all 64 piece-families; 318 takes (the 17-32 band is missing for one
short piece); 9,280 alignments, 3.6 worker-hours. The
BL-36 dev and held-out pieces (28 more) were planned but dropped for machine time (all ordered
pairs of 60 pieces ran at about 9 min per score-family job, 3.6 h projected for dev alone);
their takes were cut and are not probed. Dev whole takes went to 8 sampled wrong scores each.
On dev under the registered rule every row is 0 (no wrong pass, no false stop, no confirm on
9+ bars, W1 0 of 64, W2 0 of 512) and no leave-one-piece-out drop flips a row. Dev
reachability (500 draws of 24 dev pieces) is 1.0 for every row and says nothing about tails dev
does not have (DF-13 lesson); the margins above are the honest dev statement. 12 dev
alignments failed (IndexError in `correctness` when partial alignment trims a wrong score to a
span with no notes; all wrong-score: 11 on Debussy's "The Little Shepherd", 1 on "Reflets dans
l'eau"); counted as ratio 0. The crash is fixed for held-out (`correctness` handles an empty
score; 3 of the 12 re-run with the fix give ratio 0.0).

**Held-out.** A new draw, seed 4040, from the app catalogue's PianoCoRe pieces (not four-hands,
one score file, at least 3 unused transcriptions per family), disjoint from every earlier draw
(the BL-39 exclusion list plus the BL-39 held-out pieces and ids) and from
`piece_ids.SCORE_VERSION_MISMATCH`: 8 works with two eligible movements each (8 sibling pairs,
two movements drawn per work) plus 8 pieces of other works, 24 pieces; up to 3 candidate
transcriptions per family in seeded order; `pianocore.guard_jobs` after the draw. All ordered
pairs, one excerpt per band, every whole take on every wrong score with `partial` on and off.

**Code.** HEAD 472f5fe plus the uncommitted BL-40 diff (hashes in "Falsified if"). The held-out
run uses `scripts/eval_wrong_piece_bl40.py` with `REGISTERED`, `BARS` and `BITE_RULES` as
committed to this registration.

## Falsified if
Any registered row misses its bar on the held-out draw (see Verdict). The registered reading is
the point estimate; intervals, leave-one-out and resample shares are disclosed next to it.

End of the BL-40 pre-registration.

`awk '/^## Pre-registration$/{f=1} f{print} /^End of the BL-40 pre-registration\.$/{exit}' README.md | shasum -a 256`:
`bab3e6e35bfa62b790af836350fa3dae183a8f8a6ed2c60a84ea23932f24d656` (also in `artifacts/prereg_sha256.txt`), recorded 2026-10-28 02:24 UTC, before any BL-40 held-out piece was drawn or aligned. Code: HEAD 472f5fe plus the uncommitted BL-40 diff: `git diff HEAD -- src/pianolens` sha256 prefix 30526ab7bba56ef4; untracked `src/pianolens/app/quick_check.py` e79f95a38044dd28, `scripts/eval_wrong_piece_bl40.py` b1a77ae82d90b633.

## Data
- PianoCoRe transcriptions (Transkun V2 and Aria-AMT families) and PianoCoRe MusicXML scores
  from the raw zip (`DATASETS.md`, PianoCoRe; CC BY-NC-SA, research use). Nothing is committed.
- Dev: the 32 pieces of the BL-37 and BL-39 held-out draws and their earlier targets.
- Held-out: seed 4040, 24 pieces (above), 1 guarded candidate (`PianoCoRe_033696`).

## Splits
Dev (32 seen pieces) chooses the rule and the bars; held-out (24 new pieces, disjoint from every
earlier draw) only checks them. Pairs never cross the two pools.

## Baselines
- Today's app: `partial=False`, stop below 0.5. Right-piece excerpts score 0.006-0.57 there
  (BL-37 probe), so most are stopped; not re-measured here for excerpts.
- `partial=True` with today's stop of 0.5 unchanged (the trivial rule), on every row.

## Method
`scripts/eval_wrong_piece_bl40.py` (stages pool, takes, probe, readout; per-job CSVs under
`data/interim/bl40/<set>_probe/`, resumable). The readout applies candidate rules to the stored
ratios (`decisions`, checked equal to `quick_check.decide` on every row: dev 9,280 of 9,280).

## Command
```
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run python scripts/eval_wrong_piece_bl40.py --set dev --stage pool
uv run python scripts/eval_wrong_piece_bl40.py --set dev --stage takes --workers 5
uv run python scripts/eval_wrong_piece_bl40.py --set dev --stage probe --workers 5
uv run python scripts/eval_wrong_piece_bl40.py --set dev --stage readout
# held-out: the same four stages with --set heldout
```

## Run record
- 2026-10-27, dev. Takes stage on the planned 60 pieces (120 piece-families, about 40 min).
  The first probe launches (all pairs of 60 pieces; then with whole takes sampled) ran at about
  9 min per score-family job; stopped after about 30 min, the dev pool cut to 32 pieces (lead
  told by message), earlier probe CSVs discarded. A further change before the 32-piece run: the
  score is loaded once per job (the app path is unchanged: `align_performance` re-reads the
  file on every call). Dev probe: 64 jobs, 44 min wall, 5 workers.
- The rule, bars and bite rules were set from the dev readout and the pre-registration hashed
  (02:24 UTC). After the hash, before the held-out draw: `quick_check` constants set to the
  registered values (they were placeholders; the readout evaluates the script's `REGISTERED`,
  so no registered number depends on them) and the `decide_agrees` plumbing check added. New
  hashes: `quick_check.py` e09e261c6f72b9af, script d0c83463fa08ea82; `git diff HEAD --
  src/pianolens` unchanged (30526ab7bba56ef4; `quick_check.py` is untracked).
- Held-out drawn 02:25 UTC (seed 4040): 409 eligible pieces, 88 works with two or more
  eligible movements.
- Held-out takes: the first candidate accepted for 47 of 48 piece-families (Beethoven Op. 2
  No. 1 iii Aria-AMT: the first candidate scored 0.750, the second 0.825); 238 takes (no 17-32
  band for Chopin's Cantabile B. 84, too short for the drawn length). Probe: 48 jobs, 35 min
  wall, 6,864 alignments, 2.8 worker-hours. Dev plus held-out machine time about 2.7 h wall (dev takes 40 min, aborted
  dev starts about 35 min, dev probe 44 min, held-out takes 6 min, held-out probe 35 min).
- 1 held-out alignment failed (Rachmaninoff Op. 16 No. 5 Aria-AMT 2-4 bars on Schumann Op. 12
  No. 1): a second empty-span crash, this time in parangonar (`join_by` on an empty score
  array) inside `_align_partial`. Counted as ratio 0 as registered. Fixed after the held-out run
  in `align.core.align_note_arrays` (an empty score array gives all insertions); the re-run
  gives ratio 0.0, the same decision.
- `decide_agrees`: the vectorised rule equals `quick_check.decide` on all 6,864 held-out rows.
- **Henry's takes (after the held-out run).** His 10 A-01 transcriptions (5 takes x Transkun /
  Aria-AMT) through the quick check on their own and the 4 other scores, `partial` off and on
  (100 alignments): all 10 right alignments are whole spans with identical ratios (0.816-0.940)
  and pass either way; the 40 wrong pairs stop either way (at most 0.280 off, 0.261 on; all 40
  trimmed under `partial`); `decide` equals today's rule on all 100. His 10 A-01 reports
  (`scripts/a01_henry_reports.py`, partial off) from HEAD 472f5fe and from the BL-40 tree differ
  only in the recorded input paths (numbers compared at relative 1e-6).
- Gates: `uv run pytest -q` 681 passed, 8 skipped; `uv run ruff check src tests` clean.
- Artifacts: `artifacts/dev_readout.json`, `dev_grid.csv`, `heldout_readout.json`,
  `heldout_hard_cases.csv`, `prereg_sha256.txt`; per-alignment CSVs in `data/interim/bl40/`.

## Results

**Held-out, registered rule (`t = 0.625`, `n_min = 75`, mode "all"); 24 pieces, means over
source pieces, 95% piece bootstrap:**

| Row | Bar | 2-4 bars | 5-8 bars | 9-16 bars | 17-32 bars |
|---|---|---|---|---|---|
| H wrong-score passed silently | <= 0.25% | 0 of 1,104 | 0 of 1,104 | 0 of 1,104 | 0 of 1,058 |
| F right-score stopped | <= 2.5% | 0 of 48 | 0 of 48 | 0 of 48 | 2.17% [0, 6.52] (1 of 46) |
| C right-score asked to confirm | <= 5% (9+ bars) | 85.4% (41 of 48; information) | 33.3% (16 of 48; information) | 2.08% [0, 6.25] (1 of 48) | 0 of 46 |

| Row | Bar | Result |
|---|---|---|
| W1 right whole takes worse than today | 0 | 0 of 48 (0 better) |
| W2 wrong whole takes passed with partial on | 0 | 0 of 1,104 |
| W3 wrong whole: today stops, rule passes (information) | - | 0 of 1,104 |

**Verdict by the registered rule: PASS** (every row). No leave-one-piece-out drop flips a row.
Share of piece-bootstrap resamples meeting the bar: 1.0 for every row except F 17-32 (0.738)
and C 9-16 (0.933).

**Fragile row: F 17-32.** Its one false stop (0.610, 231 notes) and the next-lowest right
excerpt of 75+ notes (0.713, 9-16 bars) are both from one take (Beethoven Op. 49 No. 2 i,
Aria-AMT, whole take 0.885). Both units classified: the partial span ends early. The 21-bar
excerpt starting at graded bar 3 is given rows 3-12 (10 bars), leaving 125 of its 231 notes
extra; the 16-bar excerpt is given rows 3-15 (13 of 16). So the residual is the BL-36 span
detection cutting a real excerpt short on this take, not the stop. A second such take in a
24-piece draw would fail F 17-32. The third-lowest right excerpt of 75+ notes is 0.838.

**Margins on held-out.** Among takes of 75 notes or more: wrong-score max 0.576 (Schumann Op. 12
No. 6, 4 bars, 102 notes, on Chopin Op. 17 No. 4), 0.049 below the stop; right-score min 0.610
(above). Below 75 notes the sets overlap again: wrong up to 0.686 (18 notes), right down to
0.286 (22 notes, the same Op. 49 No. 2 take).

**Cost of the minimum (disclosed).** On held-out 85.4% of 2-4-bar and 33.3% of 5-8-bar
right-piece excerpts are under 75 notes and are asked to confirm (dev 75.0% and 15.6%); the
held-out pieces are sparser (nocturnes, mazurkas, a Gymnopédie). Wrong-piece excerpts under 75
notes get the same request (85.4% and 33.3%).

**Baseline: `partial=True` with today's stop of 0.5 (held-out):** wrong-score excerpts passed
3.71% (2-4 bars, 41), 1.54% (5-8, 17), 0.18% (9-16, 2), 0 (17-32); right-score stopped 2.08%
(2-4) and 0 elsewhere; whole rows as the registered rule. It fails H 2-4, H 5-8 (and passes
H 9-16 narrowly). On dev it passed 1.86%, 0.15%, 0.05%, 0.

**Hard cases (held-out, wrong-score excerpts with partial on):**

| Pair kind | Band | n | Highest ratio | Passed at 0.5 | Passed, registered |
|---|---|---|---|---|---|
| sibling movement | 2-4 | 32 | 0.623 | 5 | 0 |
| sibling movement | 5-8 | 32 | 0.511 | 2 | 0 |
| sibling movement | 9-16 / 17-32 / whole | 32 each | 0.403 / 0.380 / 0.368 | 0 | 0 |
| same key | 2-4 | 144 | 0.606 | 17 | 0 |
| same key | 5-8 | 144 | 0.625 | 8 | 0 |
| same key | 9-16 / 17-32 / whole | 144 each | 0.470 / 0.481 / 0.406 | 0 | 0 |
| other | 2-4 | 928 | 0.686 | 19 | 0 |
| other | 5-8 | 928 | 0.540 | 7 | 0 |
| other | 9-16 / 17-32 / whole | 928 / 882 / 928 | 0.537 / 0.404 / 0.351 | 2 / 0 / 0 | 0 |

Sibling and same-key pairs pass the old stop more often per pair than other pairs (2-4 bars:
16%, 12% vs 2%) but are not the highest ratios. Their highest ratios (0.623, 0.625) are on
takes of 38 and 54 notes, which the rule asks to confirm. Theme-and-variation pairs are not in
either draw.

**Neighbours of the rule (held-out, information):** `t` 0.60 or 0.65 with `n_min` 75, and
`n_min` 50, also pass every row; `n_min` 100 fails C 9-16 (14.6%). The rejected dev
alternative, `t = 0.65` with no minimum, would also have passed (H 2-4 0.18%, F 2-4 2.08%, F
17-32 2.17%) with no confirm requests.

**Bite check on held-out:** each registered row fails under its bite rule here too (stop 0.55:
H 2-4; stop 0.80: F 2-4; minimum 300 notes: C 9-16 and C 17-32; sabotage 0.96: W1 and all F;
sabotage 0.30: W2 and all H).

**Whole takes.** Today's path (`partial=False`): right takes 0.825-0.996, wrong takes at most
0.388. With `partial=True` 44 of 48 right whole takes are whole spans (identical decision by
construction of `align`), 4 are trimmed (Chopin Op. 42 Transkun, Op. 63 No. 3 Aria-AMT, Op. 55
No. 1 both families; ratio within 0.013 of `partial=False`) and pass under the trimmed rule;
71 of 1,104 wrong whole alignments are whole spans, the rest trimmed; the highest is 0.406.

## Verdict: PASS by the pre-registered rule (Provisional, awaiting eval-auditor)
The registered rule passes every row on 24 fresh pieces: no wrong-score excerpt passes
silently in any band (0 of 4,370), one right-score excerpt of 190 is stopped (17-32 bars,
2.17% against 2.5%), whole recordings decide as today (0 of 48 worse, 0 of 1,104
wrong whole takes passed). The cost is that short recordings (under 75 notes; most 2-4-bar and
a third of 5-8-bar excerpts here) are asked to confirm the piece instead of being checked.

The rule is wired in (`app/quick_check.py`, `app/pipeline.py` step 2) but only acts when the
quick check runs with `partial=True`; `PARTIAL_DEFAULT` stays False, so the app is unchanged
until the lead switches it after the audit.

## Threats to validity
- **Synthetic excerpts.** Excerpts are cut from transcriptions of whole performances (onsets
  kept, not re-transcribed, not shifted to 0). A transcriber run on a short clip has its own
  edge effects. No real excerpt upload was tested.
- **Source quality.** PianoCoRe transcriptions come from concert and studio recordings. Henry's
  phone takes scored 0.818-0.939 on their own score as whole takes (DF-05), below most held-out
  right whole takes (0.825-0.996). Excerpts of phone takes may fall nearer the 0.625 stop;
  untested.
- **F 17-32 rests on one take.** Its false stop is a span-detection miss (the DTW span ends
  10 bars early on one Aria-AMT take of Op. 49 No. 2 i), so the row measures BL-36's span
  detection as much as the stop; 74% of resamples pass.
- **Dev was cut** to 32 pieces (28 planned pieces not probed) and dev whole takes on wrong
  scores were sampled (8 per take); held-out had all pairs.
- **The bootstrap resamples source pieces only**; wrong scores stay fixed. Leave-one-out drops a
  piece on both sides.
- **The two dev-chosen candidates are not separated by held-out**: the rejected `t = 0.65` with
  no minimum also passes. The registered rule trades a confirm request on short recordings for
  margin (held-out: 0.049 between the highest wrong ratio and the stop at 75+ notes).
- **Scores.** Only PianoCoRe catalogue scores; ASAP catalogue scores and uploaded scores were not
  probed. Theme-and-variation pairs are absent from both pools.
- **Code changed during the run.** The empty-span crash fix in `correctness` landed between dev
  and held-out; the `align_note_arrays` empty-score fix after held-out. Both act only when the
  trimmed score has no notes; the failed alignments (12 dev, 1 held-out) were counted as ratio 0,
  which the fixed code also gives where re-run (3 dev, 1 held-out).

## For the lead
1. Switching the app to `partial=True` (`PARTIAL_DEFAULT`, or an app-only default) also turns
   on partial alignment for the app's reports, the k = 0 configuration the CLI already uses
   (DECISIONS 2026-10-12). This experiment only covers the quick-check stop.
2. Confirm cost vs margin: the registered rule asks to confirm under 75 notes (held-out 85% of
   2-4-bar and 33% of 5-8-bar right excerpts); `t = 0.65` without a minimum also passed
   held-out with no confirms but thinner dev margins. The data cannot choose between them.
3. A span-detection miss on a real excerpt (Op. 49 No. 2 i, Aria-AMT: a 21-bar excerpt given
   10 bars) is new evidence for BL-36's span detection on transcribed input; worth a backlog
   item.
4. Two crash fixes outside the app (`features/correctness.py`, `align/core.py`) for a partial
   alignment trimmed to an empty span, each with a regression test.
