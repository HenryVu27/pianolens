# BL-40: wrong-piece stop with partial alignment
Ticket: BL-40 (from the BL-37 audit)    Hypothesis: none from the plan (app rule)    Status: Confirmed with caveats (eval-auditor 2026-10-27)

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
  gives ratio 0.0. The take has 49 notes, so the registered rule asks to confirm whatever its
  ratio: the decision is "confirm" with or without the fix.
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
Aria-AMT, whole take 0.885). The partial span does end early (the 21-bar excerpt is given rows
3-12), but that is not why it is stopped (corrected after the audit, section 8): with the true
span the excerpt's ratio is 0.576 (oracle span: the whole-take alignment over the excerpt's
notes and bars), also below the stop, because 76 of its 231 notes (33%) are unmatched extras in
the whole-take alignment, many 2-3.5 octaves below the nearest matched note (the whole take
has 9.9% extras). The stop fires on a noisy transcribed passage; the short span even raises the
ratio. Over all 190 right excerpts, partial minus oracle ratio has median 0.000; 3 are below
-0.05 (lowest -0.109, a 2-4-bar excerpt at 0.847), none near the stop. A second such take in a 24-piece draw would fail F 17-32. The
third-lowest right excerpt of 75+ notes is 0.838.

**Margins on held-out.** Among takes of 75 notes or more: wrong-score max 0.576 (Schumann Op. 12
No. 6, 4 bars, 102 notes, on Chopin Op. 17 No. 4), 0.049 below the stop; right-score min 0.610
(above). Below 75 notes the sets overlap again: wrong up to 0.686 (18 notes), right down to
0.286 (22 notes, the same Op. 49 No. 2 take). The gap between the lowest right and the highest
wrong ratio at 75+ notes was 0.109 on dev and is 0.034 on held-out, a third of it (audit
section 3). A MIDI round trip (an excerpt written to a file with its first onset at 0, as an
upload) moved 3 of 37 sampled wrong-score ratios by 0.02-0.15 (0.576 -> 0.424, 0.128 -> 0.238,
0.543 -> 0.533) and no right-score ratio (audit section 7d): the same order as the 0.049
margin, so the margins here are not those of real uploads.

**Cost of the minimum (disclosed).** On held-out 85.4% of 2-4-bar and 33.3% of 5-8-bar
right-piece excerpts are under 75 notes and are asked to confirm (dev 75.0% and 15.6%); the
held-out pieces are sparser (nocturnes, mazurkas, a Gymnopédie). Wrong-piece excerpts under 75
notes get the same request (85.4% and 33.3%).

**Confirm mode (added after the audit, section 6).** H counts silent passes only, and mode
"all" never passes a trimmed take under 75 notes, so H for those takes is 0 by construction;
the registered rows cannot tell "all" from "high" (confirm only at or above the stop, stop
below). Decisions on wrong-score excerpts:

| | stop | confirm | pass |
|---|---|---|---|
| held-out, "all" (registered) | 3,036 | 1,334 | 0 |
| held-out, "high" | 4,367 | 3 | 0 |
| dev, "all" (registered) | 6,076 | 1,798 | 0 |
| dev, "high" | 7,871 | 3 | 0 |

Of the 1,334 held-out wrong excerpts asked to confirm, 965 have a ratio below 0.3 and 3 are at
or above 0.625. Under "high" the registered rows still pass on held-out, with one more false
stop (F 2-4 2.08%, the Op. 49 No. 2 i take at 0.286). The pre-registration's reason for "all"
("below 75 notes a low ratio says as little as a high one") is not what dev showed: the lowest
dev right excerpt under 75 notes was 0.733, so on dev every short take below 0.625 was a wrong
piece and only a high ratio was uninformative (held-out: 1 of 58 short right excerpts below
0.625; Henry's excerpts: 1 of 29).

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

## Verdict: PASS by the pre-registered rule; Confirmed with caveats (eval-auditor 2026-10-27); app flag stays off until the repeat-path guard (Audit, section 7c)
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
- **Source quality.** PianoCoRe transcriptions come from concert and studio recordings. On
  Henry's room-audio takes cut into excerpts (audit section 7b: 120 excerpts of his 10
  transcriptions, 600 alignments), 1 of 120 right excerpts is stopped (Nocturne in C-sharp
  minor, Transkun, bars 40-44, 82 notes, 0.539: a noisy passage, oracle span also 0.539) and
  the lowest right ratios at 75+ notes are 0.539, 0.648, 0.73 (PianoCoRe held-out: 0.610);
  wrong scores pass 0 times (highest 0.545 under 75 notes, 0.452 at 75+). On this source the
  false-stop side is the risk.
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
  probed (the audit added 11 ASAP scores as wrong scores: 0 passes in 2,090 alignments).
  Theme-and-variation pairs are absent from both pools.
- **Repeat paths (added after the audit, section 7c).** Both pools had at most 16 repeat paths
  per score. `align(..., partial=True)` built every path, and the catalogue (804 scores) has 588
  with 1 path, 168 with 2-4, 30 with 5-16, 11 with 17-64, 2 with 65-256 and 4 with more (Handel
  HWV 432/6 65,536; Mozart K. 331 i 8,192; Schubert D. 935/3 2,048; K. 331 iii 512), and Mozart
  K. 265, whose enumeration alone passed 3 GB in 23 s even with partial off. One 21-note
  excerpt took 157 s and 2.5 GB on K. 331 iii and did not finish on K. 331 i or D. 935/3. Fixed
  after the audit (DF-16, DF-17; "Corrections after the audit"); the BL-40 result covers scores
  of at most 16 paths, where partial alignment still searches every path.
- **H under 75 notes is 0 by construction** of mode "all" (see Results, confirm mode).
- **Code changed during the run.** The empty-span crash fix in `correctness` landed between dev
  and held-out; the `align_note_arrays` empty-score fix after held-out. Both act only when the
  trimmed score has no notes; the failed alignments (12 dev, 1 held-out) were counted as ratio 0,
  which the fixed code also gives where re-run (3 dev, 1 held-out).

## For the lead
**Lead decision (2026-10-28, DECISIONS):** the registered mode "all" is kept as registered, with
no deviation; a wrong excerpt under 75 notes gets "confirm the piece", which is not a silent pass.
Mode "high" and `t = 0.65` are not adopted. `PARTIAL_DEFAULT` stays False until the lead accepts
the repeat-path fixes (DF-16, DF-17; "Corrections after the audit").

Remaining points:
1. Switching the app to `partial=True` (`PARTIAL_DEFAULT`, or an app-only default) also turns
   on partial alignment for the app's reports, the k = 0 configuration the CLI already uses
   (DECISIONS 2026-10-12). This experiment only covers the quick-check stop.
2. On the 18 catalogue scores with more than 16 repeat paths, partial alignment is now not
   applied (DF-17): an excerpt is aligned whole and stopped by the 0.5 rule, as today.
3. The early span end on Op. 49 No. 2 i (Aria-AMT) did not cause the false stop (audit section
   8); a backlog note, not a ticket.
4. Two crash fixes outside the app (`features/correctness.py`, `align/core.py`) for a partial
   alignment trimmed to an empty span, each with a regression test.

## Audit (eval-auditor, 2026-10-27)

**Verdict: Confirmed with caveats.** PASS by the pre-registered rule is the correct reading.
Every registered number reproduces exactly from the cache. There is no pre-registration drift,
no leakage between dev and held-out, and nothing was re-selected after the held-out results.
The caveats concern what the result covers, and they bear on the lead's decision to switch the
app to `partial=True`:
- Under mode "all", "0 wrong excerpts passed" for takes under 75 notes holds by construction.
- The F 17-32 mechanism is misnamed.
- Some catalogue scores make the partial quick check hang (section 7c). This blocks switching
  the app flag until it is guarded.

**1. Pre-registration, timeline, drift.**
- **Anchor.** It recomputes to `bab3e6e3...d656`, as in `artifacts/prereg_sha256.txt`.
- **Code.** `git diff 472f5fe 8134800 -- src/pianolens ':!src/pianolens/align/core.py'
  ':!src/pianolens/app/quick_check.py' | shasum -a 256` gives `30526ab7bba56ef4`, the hashed
  value. So the only tracked change under `src/pianolens` after the hash is the
  `align_note_arrays` guard.
- **Post-hash edit (transcript 02:25:04Z).** Reversing it gives `quick_check.py` `e79f95a3...`
  and the script `b1a77ae8...`, the hashed values. The committed files give `e09e261c...` and
  `d0c83463...`, as in the run record. That edit only:
  - set the three constants;
  - added `decide_agrees`.

  `rule_rows` / `verdict` use `REGISTERED` and `decisions()`, not the module constants. No
  registered number depends on them.
- **Timeline** (author transcript `subagents/agent-a3d462ef8a1d4f09c.jsonl`, UTC):
  - 02:19:27 dev readout;
  - 02:21:51 `correctness` empty-span fix (before the hash, inside `30526ab7`);
  - 02:23:54-02:24:39 pre-registration written;
  - 02:24:51 hash;
  - 02:25:04 constants set;
  - 02:25:24 held-out pool drawn;
  - 02:25:41 takes and probe launched;
  - 03:02:05 held-out readout;
  - 03:03:28 `align_note_arrays` guard added;
  - 03:04:08 Henry whole-take check.

  No earlier call uses seed 4040 or reads a held-out file. An earlier BL-40 attempt
  (`agent-a70a92dbfd7594c83`, 2026-10-12) only timed dev pieces and drew no held-out pieces.
- **The rejected alternative** (`t = 0.65`, no minimum) is in the hashed text. So the choice
  between the two was made before the held-out run.
- **The dev cut** from 60 to 32 pieces happened before the dev probe whose numbers chose the
  rule. The lead was messaged at 01:35:25Z.

**2. Held-out draw.**
- 24 pieces and 143 candidate ids.
- None of them is in `SCORE_VERSION_MISMATCH`. `guard_jobs` dropped `PianoCoRe_033696`.
- **Disjointness.** I scanned every `data/interim/*/{pkl,json,csv}` outside `bl40` for the 24
  piece ids and the 143 transcription ids.
  - Ids: 0 hits.
  - Piece ids appear only in lists that are not draws:
    - BL-36 / BL-37 `heldout_repeat_flags.json` (repeat flags over all 209 / 193 eligible
      pieces);
    - the app catalogue;
    - the DCML Romantic piece list;
    - MAJEPPA features.
  - No earlier PianoCoRe draw overlaps.

**3. Rule selection (dev, reproduced).** Gap = lowest right ratio minus highest wrong ratio,
among takes with at least `n_min` notes:

| `n_min` | dev gap | held-out gap |
|---|---|---|
| 0 / 25 | -0.061 / -0.061 | -0.400 / -0.046 |
| 50 | +0.040 | -0.015 |
| 75 | +0.109 | +0.034 (wrong 0.576, right 0.610) |
| 100 / 150 | +0.113 / +0.184 | +0.034 / +0.129 |

On dev, 75 is the smallest grid value with a gap of 0.10 or more. `t` is the midpoint
(0.6325), rounded to 0.625. The rule followed its stated procedure. The held-out gap at 75 is a
third of the dev gap.

**4. Reproduction.**
- **Read-only recompute.** I imported the script and ran `load_probe`, `rule_rows`, `verdict`,
  `resample_pass`, `loo` and the bite rules on the cached probe CSVs, without running the
  readout stage.
  - Differences in any row statistic: 0 on held-out (6,864 rows) and 0 on dev (9,280).
  - Resample shares: F 17-32 0.738, C 9-16 0.933.
  - Leave-one-out flips: none.
  - Every bite rule fails its row on held-out.
  - `decide_agrees`: 0 rows differ in either set.
- **Counts by band** (held-out, registered rule):

| Band | H wrong passed | Hc wrong asked to confirm | F right stopped | C right asked to confirm |
|---|---|---|---|---|
| 2-4 | 0 / 1,104 | 943 / 1,104 | 0 / 48 | 41 / 48 |
| 5-8 | 0 / 1,104 | 368 / 1,104 | 0 / 48 | 16 / 48 |
| 9-16 | 0 / 1,104 | 23 / 1,104 | 0 / 48 | 1 / 48 |
| 17-32 | 0 / 1,058 | 0 / 1,058 | 1 / 46 | 0 / 46 |

  The whole-take rows reproduce too:
  - W1: 0 of 48 worse.
  - W2: 0 of 1,104 wrong whole takes passed.
  - W3: 0 of 1,104.
- **App-path re-run** (current code, 5 workers). I re-ran 45 held-out alignments:
  - every right excerpt below 0.8;
  - the 15 highest wrong ratios;
  - the 5 highest wrong ratios at 75 notes or more;
  - the failed alignment;
  - 20 random rows.

  45 of 45 have the same ratio and span flag as the cache. The failed row now gives 0.0.
- **Henry's whole takes** (the author's `henry_quick.json`): 100 rows.
  - Right takes are whole spans with partial on and off, 0.816-0.940.
  - Wrong takes go up to 0.280 with partial off and 0.261 with it on.
  - `decide` equals today's rule on all 100.

**5. Crash guards.**
- **The held-out crash.** Removing the `align_note_arrays` guard in-process reproduces the
  recorded error: parangonar `join_by`, `IndexError: boolean index did not match`. With the
  guard the ratio is 0.0.
  - That take has 49 notes, so the registered rule asks to confirm whatever its ratio.
  - No held-out decision depends on the fix.
- **`correctness`, old (472f5fe) vs new.** I compared 48 full alignments: 6 held-out pieces,
  whole takes and 9-16-bar excerpts, partial on and off. All 48 are identical in summary,
  per-note and per-score-note tables.
- **When the guards fire.**
  - The `core.py` guard fires only when `len(score_na) == 0`.
  - `_at` is the old positional gather whenever the array is non-empty. `sn` is a structured
    numpy array, so `np.asarray` does not change the indexing.

**6. The "confirm" outcome and the harm row.**
- **What H can see.** H counts only silent passes, and mode "all" never passes a trimmed take
  under 75 notes. So H for those takes is 0 by construction (BL-23 lesson). The registered
  rows cannot tell mode "all" from mode "high" (confirm only at or above the stop, stop below
  it).
- **Decisions on wrong-score excerpts:**

| | stop | confirm | pass |
|---|---|---|---|
| held-out, "all" (registered) | 3,036 | 1,334 | 0 |
| held-out, "high" | 4,367 | 3 | 0 |
| dev, "all" (registered) | 6,076 | 1,798 | 0 |
| dev, "high" | 7,871 | 3 | 0 |

  Of the 1,334 held-out wrong excerpts asked to confirm, 965 have a ratio below 0.3, 1,188
  below 0.4, and 3 at or above 0.625.
- **Mode "high" on the registered rows.**
  - On dev every registered row is still 0.
  - On held-out it still passes. It adds one false stop, F 2-4 2.08%: the Op. 49 No. 2 i Aria
    take at 0.286.
- **The pre-registration's reason for "all" is not what dev shows.** The reason given was
  "below 75 notes a low ratio says as little as a high one". But the lowest dev right excerpt
  under 75 notes was 0.733. So on dev, every short take below 0.625 was a wrong piece. Only a
  high ratio was uninformative there.
  - Held-out: 1 of 58 short right excerpts was below 0.625.
  - Henry's takes (7b): 1 of 29.
- **Is "passed silently" the right harm?** It is the right lower bound, but not the whole
  harm.
  - The confirm message gives the learner no evidence: "too short to check that it is the
    chosen piece. If it is, choose Analyse anyway".
  - A learner who chose the wrong score in good faith will click.
  - "Analyse anyway" calls `_retry(ignore_wrong_piece=True)`. The job re-runs from the start,
    the decision is again "confirm", and the run continues with the note "the piece was
    confirmed". The learner gets a full report against the wrong score.
- **Against today's app** (partial off): short excerpts score 0.006-0.57 on their own score
  (BL-37). So today the app already stops nearly every short take, right or wrong, with
  "probably another piece" and the same button. For takes under 75 notes, the registered rule
  changes the wording, not the information. The gain is for takes of 75 notes or more.

**7. Coverage probes.** These are information, not registered rows. Scripts were in scratch and
are not kept. Partial alignment was on, decisions by the registered rule.

- **a. ASAP catalogue scores as wrong scores.** All 190 held-out right excerpts went against 11
  ASAP scores: `beethoven_op2_no1_mv1` (a sibling of two held-out movements), `liszt_s141_no6`
  (a theme and variations, 2 repeat paths) and 9 seeded others. That is 2,090 alignments.
  - Silent passes: 0.
  - Highest ratio at 75 notes or more: 0.549 (margin 0.076). Under 75 notes: up to 0.740,
    asked to confirm.
  - Today's 0.5 stop with partial on would pass 20 of them.
  - **Same piece, other source's score.** The 8 Liszt Rhapsody No. 6 PianoCoRe excerpts on the
    ASAP S. 244/6 score: 6 pass, 2 are asked to confirm, lowest 0.714.
  - A 12th score, Schubert D. 935/3, did not finish (see c).
- **b. Henry's takes, cut into excerpts.** The 10 A-01 transcriptions were cut into 3
  excerpts per band (seeded, same cutter): 120 excerpts against their own and the 4 other
  scores, 600 alignments.
  - **Wrong scores.** 0 passes. Highest 0.545 (under 75 notes); 0.452 at 75 notes or more.
  - **Right scores.** 1 stop: Nocturne in C-sharp minor (04), Transkun, bars 40-44, 82 notes,
    0.539.
    - By band, stopped: 0, 1, 0 and 0 of 30 (2-4, 5-8, 9-16, 17-32). Asked to confirm: 23, 6,
      1 and 0 of 30.
    - Lowest right ratios at 75 notes or more: 0.539, 0.648, 0.73. On PianoCoRe held-out the
      lowest was 0.610.
  - **What causes that stop.** Not span detection: the span is exactly bars 40-44, and the
    oracle-span ratio (Dice of the whole-take alignment over the excerpt's notes and bars) is
    also 0.539. 62% of the excerpt's notes are unmatched extras in the whole-take alignment.
  - **Reading.** Room-audio transcription noise is local. Whole takes at 0.816-0.939 hide
    passages where a right excerpt falls below the stop. This is one event on 5 pieces by one
    pianist. On this source the false-stop side is the risk; the wrong-piece side has margin.
- **c. Repeat paths: the partial quick check hangs on some catalogue scores.**
  `align(partial=True)` builds every repeat path of the score (`core.py`, `built = {...}` over
  all variants). `partial=False` builds only the `max_candidates` closest.
  - **Catalogue** (804 scores) by number of paths:
    - 1 path: 588;
    - 2-4: 168;
    - 5-16: 30;
    - 17-64: 11;
    - 65-256: 2;
    - more than 256: 4 (Handel HWV 432/6 Passacaille 65,536; Mozart K. 331 i 8,192; Schubert
      D. 935/3 2,048; Mozart K. 331 iii 512);
    - not counted: Mozart K. 265, where enumerating the paths alone passed 3 GB in 23 s.
  - BL-40's dev and held-out pieces have at most 16 paths.
  - **Cost of one 21-note wrong excerpt, partial off vs on:**

| Score | Paths | partial off | partial on |
|---|---|---|---|
| K. 331 iii | 512 | 0.9 s | 157 s, peak 2.5 GB |
| K. 331 i | 8,192 | 2.6 s | not finished after 300 s, killed at 3.1 GB |
| D. 935/3 | 2,048 | 2.5 s | not finished after 400 s, killed at 3.9 GB |

  - In the batch probe, one worker on D. 935/3 reached 11 GB, and one on a PianoCoRe theme and
    variations (K. 331 i or K. 265) reached 25 GB before I stopped them.
  - K. 265 also fails with partial off: path enumeration alone passed 3 GB in 23 s. That is a
    defect of today's app, outside BL-40.
  - K. 331 iii, the Rondo alla Turca, has 707 references in the catalogue.
  - **Consequence.** With partial on, the app's quick check would sit for minutes and use
    gigabytes on these scores. BL-40's pools could not show this, because they had no such
    score.
- **d. A real upload is a file.** I wrote 37 sampled excerpts to MIDI with the first onset at 0
  and loaded each as an upload.
  - 34 ratios were identical. 3 wrong-score ratios moved: 0.576 -> 0.424, 0.128 -> 0.238,
    0.543 -> 0.533.
  - **The 0.576 case** (the held-out wrong maximum at 75 notes or more):
    - shifting in memory changes nothing;
    - an unshifted file gives 0.598;
    - a shifted file gives 0.424.
  - So a MIDI round trip moves wrong-score ratios by 0.02-0.15. That is the order of the 0.049
    margin to the stop. Right-score ratios in the sample did not move.
- **e. Theme and variations, right score.**
  - Beethoven Op. 57 ii (1 path): 24 excerpts, all pass or are asked to confirm; lowest 0.899
    at 75 notes or more.
  - Schumann Op. 1 had no candidate at 0.8 or more.
  - K. 331 i and K. 265 cannot run (c).

**8. F 17-32: the residual is a noisy passage, not span detection.**
- **The take:** Op. 49 No. 2 i, Aria-AMT. Re-running it confirms the author's span readings:
  - 21-bar excerpt (graded bars 3-23): DTW span rows 3-17, refined span 3-12, 125 of 231
    notes extra.
  - 16-bar excerpt (bars 3-18): DTW span 3-15.
  - 2-4-bar excerpt (bars 20-22): span row 16.
- **But the ratio is low because of the passage, not the span.** The oracle-span ratio of the
  21-bar excerpt is 0.576, below both its partial ratio (0.610) and the stop.
  - In the whole-take alignment (partial off), 76 of the excerpt's 231 notes (33%) are
    unmatched extras. Many lie 2-3.5 octaves below the nearest matched note. The whole take
    has 9.9% extras.
  - Oracle vs partial for the other two: 16-bar 0.654 vs 0.713; 2-4-bar 0.237 vs 0.286.
  - The short span helps here: it drops part of the noise.
- **The stated mechanism is wrong.** The README says "the residual is the BL-36 span detection
  cutting a real excerpt short, not the stop". With the right span this excerpt is stopped
  too. This is the BL-39 lesson again: classify the unit before naming the mechanism.
- **Across all 190 held-out right excerpts,** partial ratio minus oracle ratio:
  - median 0.000;
  - 5th percentile -0.004;
  - 3 below -0.05, the lowest -0.109 (a 2-4-bar Liszt excerpt, 0.847 vs 0.956).

  Span detection costs ratio rarely, and never near the stop.
- **Ticket?** The early span end on a noisy passage is real, but it did not cause a wrong
  decision here. A backlog note is enough, not a ticket. F 17-32 measures source noise
  (Aria-AMT on one passage), and section 7b shows the same failure mode on Henry's room audio.

**9. Statistics.**
- The bootstrap resamples source pieces with wrong scores fixed. n (pieces, alignments) is
  reported per row.
- 16 of the 24 held-out pieces are 8 sibling pairs, resampled as independent pieces. A work
  bootstrap would be somewhat wider. That changes no reading, because the verdict is on point
  estimates and only F 17-32 and C 9-16 are below a resample share of 1.0.

**Required fixes (author)**
1. Results / Threats: add the mode table from section 6. State that H for takes under 75 notes
   is 0 by construction of mode "all". State that dev did not support the "all" rationale (no
   dev right excerpt under 75 notes below 0.733).
2. Fragile row: replace "the residual is the BL-36 span detection ... not the stop" with the
   oracle reading from section 8: true span 0.576, 33% extras, so the stop fires on a noisy
   passage.
3. Threats: add the repeat-path hazard (section 7c), with the catalogue counts and timings,
   and the pool's maximum of 16 paths.
4. Threats: replace "Excerpts of phone takes ... untested" with the section 7b numbers
   (1 of 120 right excerpts stopped, lowest 0.539 at 75 notes or more; wrong at most 0.545).
5. Margins: give the dev and held-out gaps (0.109 vs 0.034) and the MIDI round-trip movement
   (section 7d).
6. Run record: the failed held-out alignment had 49 notes, so its decision is "confirm" with or
   without the fix.
7. BACKLOG: open DF items for:
   - the repeat-path enumeration and build cost under `partial=True`;
   - the K. 265 enumeration blow-up with partial off. This one affects today's app.

**Note for the lead**
- **Is switching the app to `partial=True` supported?** Not yet; BL-36, BL-37, BL-39 and BL-40
  together support it only with one engineering guard first.
  - **The stop works.** BL-40 shows it works on PianoCoRe-like scores and transcriptions. It
    also held on 11 ASAP scores and on Henry's excerpts on the wrong-piece side (0 passes).
  - **Reports.** The app would get the CLI's k = 0 partial reports (DECISIONS 2026-10-12). Their
    basis is unchanged: whole recordings are identical; mid-bar starts are strong about 20% vs
    1.3% (disclosed).
  - **The guard.** The partial quick check is unbounded on scores with many repeat paths
    (section 7c): K. 331 iii took 157 s and 2.5 GB for one 21-note excerpt; K. 331 i and
    D. 935/3 did not finish. Before the flag goes on, cap the paths `partial=True` builds, or
    fall back to `partial=False` above the tested range (16 paths). A cap is a code change
    outside BL-40's registration. Confirm on the 17 counted catalogue scores above 16 paths, and on
    K. 265, that the quick check finishes and that whole recordings are unchanged.
- **Confirm mode.** Registered "all" vs "high" is a product call. The registered rows cannot
  separate them (section 6).
  - "high" turns about 1,330 held-out "too short to check" messages for wrong-piece excerpts
    into "probably another piece" stops.
  - Its cost is about one false stop per 30-60 short right excerpts (Op. 49 No. 2 i 0.286;
    Henry 0.600).
  - Either way the learner can override.
  - Switching to "high" is a deviation from the registration and should be recorded as such
    in DECISIONS, with these numbers.
  - The same applies to `t = 0.65` with no minimum, which also passed held-out.
- **What to tell the learner:**
  - Recordings under 75 notes (most 2-4-bar and a third of 5-8-bar excerpts) are not checked
    against the score.
  - For an excerpt, the first and last bars are less reliable (BL-36 / BL-39 caveat, k = 0).
  - "Analyse anyway" on a "probably another piece" stop is expected for some phone-audio
    excerpts of the right piece (section 7b: 1 of 120).

### Corrections after the audit (2026-10-28, author)
Fixes 1-6 are applied in place above (pre-registration untouched; its hash still verifies):
1. Results "Confirm mode" (the section 6 table; H under 75 notes is 0 by construction; dev did
   not support the "all" rationale) and a Threats line.
2. "Fragile row": the oracle reading (true span 0.576, 33% extras: a noisy passage).
3. Threats "Repeat paths": catalogue counts, timings, the pools' maximum of 16 paths.
4. Threats "Source quality": Henry's excerpts (section 7b) replace "untested".
5. Margins: dev vs held-out gap (0.109 vs 0.034) and the MIDI round trip (section 7d).
6. Run record: the failed held-out alignment had 49 notes, so "confirm" either way.
7. The two defects are fixed rather than ticketed (DEFECTS DF-16, DF-17; BACKLOG BL-40):

**DF-16, repeat-path enumeration bounded (`align/core.py`).** `_variants_info` runs
partitura's own `unfold_paths` into a list that stops past `MAX_REPEAT_PATHS` (65,536, the
catalogue maximum apart from K. 265), so no score lists every path. At or under the cap the list
is exactly `get_paths` in its order; above it, the score gets the fully repeated and the
shortest reading. Measured on all 804 catalogue scores (`scripts/check_repeat_paths_df16.py
count`, 9.5 min, peak RSS 0.97 GB): 588 have 1 path, 168 2-4, 30 5-16, 11 17-64, 2 65-256, 4
more (largest 65,536 in 1.2 s); K. 265 stops at the cap in 3.2 s (it passed 3 GB before).
Identity: `repeat_variants` old (HEAD 581c2a9) vs new on 824 scores (every catalogue PianoCoRe
score but K. 265, every ASAP score): 0 differ.

**DF-17, partial alignment capped (`align/core.py`, `align/partial.py`, `report/`).** A score
with more than `PARTIAL_MAX_PATHS` (16, the tested range) repeat paths, or over the enumeration
cap, is aligned as with `partial=False` (the safer of the two options: no span search the
BL-36-40 evidence does not cover). `recorded_span` is whole and carries `fallback` ("512 repeat
paths") and a `method` saying partial alignment was not applied; the report copies `fallback`
and adds one confidence note ("This score has 512 repeat paths, too many to search for the part
a recording covers ..."). Scores with at most 16 paths are searched as before.

Checks (one score at a time, 4 GB / 900 s watch; a 21-note deadpan excerpt from the middle of
each score, partial on; quick check = the app's step 2, report = `report_from_files` as the CLI):

| Score | Paths | Quick check | CLI report |
|---|---|---|---|
| Mozart K. 265 | more than 65,536 (capped) | 4.7 s, 0.81 GB | 10.4 s, 1.03 GB |
| Beethoven Op. 101 ii | 21 | 1.1 s, 0.55 GB | 49.6 s, 0.95 GB |
| Beethoven Op. 27 No. 2 ii | 24 | 0.4 s, 0.50 GB | 1.8 s, 0.72 GB |
| Mozart K. 545 | 32 | 3.0 s, 0.91 GB | 9.9 s, 1.16 GB |
| Mozart K. 570 iii | 32 | 1.1 s, 0.66 GB | 3.9 s, 0.88 GB |
| Albéniz Op. 47 i | 32 | 1.1 s, 0.62 GB | 3.5 s, 0.84 GB |
| Beethoven Op. 2 No. 2 iii | 42 | 0.5 s, 0.51 GB | 1.9 s, 0.72 GB |
| Chopin Op. 7 No. 2 | 52 | 0.5 s, 0.50 GB | 1.9 s, 0.72 GB |
| Beethoven Op. 26 ii | 52 | 0.5 s, 0.51 GB | 2.1 s, 0.72 GB |
| Mozart K. 570 ii | 64 | 1.0 s, 0.62 GB | 3.2 s, 0.83 GB |
| Haydn Hob. XVI:39 i (ASAP) | 64 | 1.0 s, 0.57 GB | 36.0 s, 0.87 GB |
| Beethoven Op. 31 No. 3 iii | 64 | 0.6 s, 0.47 GB | 16.5 s, 0.75 GB |
| Beethoven Op. 22 iii | 70 | 0.6 s, 0.47 GB | 18.5 s, 0.80 GB |
| Bach BWV 826 | 256 | 5.2 s, 1.04 GB | 15.3 s, 1.31 GB |
| Mozart K. 331 iii | 512 | 1.1 s, 0.56 GB | 32.2 s, 0.94 GB |
| Schubert D. 935/3 | 2,048 | 2.9 s, 0.86 GB | 1,009 s, 1.51 GB (partial off: 1,007 s, 1.76 GB) |
| Mozart K. 331 i | 8,192 | 3.0 s, 0.83 GB | 8.3 s, 1.08 GB |
| Handel HWV 432/6 | 65,536 | 2.3 s, 0.77 GB | 4.2 s, 0.84 GB |

(Peak = the process's maximum RSS, including about 0.5 GB of imports.) K. 265 with partial off,
which failed before DF-16: quick check 4.4 s, 0.80 GB; report 9.9 s, 1.03 GB. All 18 finish; every
record is whole with the fallback and its confidence note. D. 935/3's report is slow with
partial off as well: the time is the per-bar expert check aligning its references
(`report.io.expert_bar_tables`, stack sampled at 120 s), a cost today's app already has; it
first hit the 900 s watch and was re-run with 3,600 s. These excerpts are of the right piece,
and with the fallback they score 0.006-0.101, so the quick check stops them as today.

**Identity, scores of at most 16 paths (HEAD 581c2a9 vs the fixed tree):**
- Henry's 10 A-01 reports with partial off and with partial on: 9 of 10 byte-identical
  apart from input paths in each mode; 03 Aria-AMT differs only in floats (at most 1.4e-10
  relative, 301 / 302 values, no label or tier), the known run-to-run noise of that report (the
  old code alone differs as much between its two runs).
- 35 ASAP performances (30 seeded scores plus 6 with 21-2,048 paths): variant, alignment, match
  ratio and recorded span identical with partial off (35 of 35) and on (29 of 29; the 6 scores
  over 16 paths are skipped with partial on, since the old code would build every path).
- `repeat_variants` on 824 scores: identical (DF-16 above).
- Gates: `uv run pytest -q` 686 passed, 8 skipped; `uv run ruff check src tests` clean. New
  tests in `tests/align/test_partial.py`: enumeration cap (full list at and under the cap, two
  readings over it), "auto" over the cap, the fallback at 32 paths with and without the cap
  (alignment equal to `partial=False`, record, report field and note), still searched at 16.
