# BL-19b: is score staff the playing hand? Checked against PianoVAM video hand labels

Ticket: BL-19b (from BL-19 and BL-24)    Hypothesis: none from the plan (measurement)    Status: Provisional

## Question

Hand synchrony (`control.hand_synchrony`) and any per-hand feedback treat the upper staff as
the right hand and the lower staff as the left. BL-19 estimated from score-only proxies that
5.2% of notes and 3.9% of hand-sync events are at risk, but its audit found that the proxies
flag no note in 57% of the measures where the engraver wrote a hand word naming the other
staff's hand, so the true rate was unbounded. PianoVAM v1.2 has per-note hand labels from video
(BL-24). On the PianoVAM recordings of catalogue pieces:

1. How often is the staff hand not the hand that played the note (per note, per hand-sync
   event, per piece)?
2. Is staff better than a plain pitch split, and does the voice-based correction help?
3. Do the BL-19 proxies (P1 cross-staff voice, P2 pitch crossing, P3 one-hand capacity) find
   the notes where staff and hand differ (precision, recall)?

## Data

- PianoVAM v1.2 (DATASETS.md, HF commit 1f039ab9, CC BY-NC-SA 4.0): `MIDI/` (Disklavier, daily
  practice of 10 amateur pianists) and the BL-24 hand labels, `Fingering/` (video, automatic,
  `pianovam.hand_labels(perf, "video")`) and `Fingering_GT/` (manual, 1,800 notes of 11
  recordings, `"manual"`). Labels are joined per performance note inside the loader (pitch and
  onset within 0.5 ms), never by row position.
- Scores: the app catalogue (`data/interim/app/catalog.json`): ASAP MusicXML or the PianoCoRe
  raw-zip MusicXML, loaded folded and parts-merged with `pianolens.align.load_score_part`, so
  staves are numbered 1 (upper) / 2 (lower) by the DF-09 rule (`normalise_piano_staves`).
- Recordings: the 44 with a title-level catalogue candidate (`pianovam.SCORE_CANDIDATES`): 29 with
  an unambiguous unit, 15 ambiguous.

## Development (done before any hand label was read)

Everything in this section used the MIDI and the scores only. No hand label, `Noinfo` flag or
manual label was loaded (the `align` stage of `run.py` never imports `hand_labels`).
[Corrected after the audit: see "Corrections after the audit", item 6.]

**Take splitting and alignment** (`src/pianolens/data/session_takes.py`, new):

1. Score notes are grouped into onsets, performed notes into events (50 ms), each a pitch set;
   similarity +2 for equal sets, +1 for a shared pitch, -2 otherwise, gap -1 (the BL-16 values).
2. A local alignment (Smith-Waterman) finds the best pair of a score region and a session region;
   the path is cut where more than 6 consecutive steps skip one side (a restart or a jump); each
   piece that keeps at least 30 DP points is a take; the search repeats on the session parts left
   over. Several candidate scores compete for each region (highest DP points wins).
3. Each take's performed notes are aligned with parangonar `DualDTWNoteMatcher`
   (`pianolens.align.align_note_arrays`, ornaments off) to the score notes between the take's
   first and last paired onset. Only pitch-equal matches are kept.

**Candidate scores** (decided on content and catalogue structure, no labels):

- Whole-work duplicates dropped where movement scores exist: K. 545 uses `mozart_k545_mv1/2/3`;
  Clementi Op. 36 uses `clementi_op36_no1` and `clementi_op36_no3` (the No. 1 first-movement file
  duplicates part of the No. 1 file).
- The ASAP "Italian concerto" score is the 2nd movement (49 bars of 3/4); PianoVAM has the 1st
  and 3rd, so `bach_bwv971` (PianoCoRe, the whole concerto) is the only candidate.
- Ondine uses the ASAP score only (one engraving per piece).
- The ambiguous recordings are resolved per take by alignment, not per recording: Schumann Op. 17
  (7 recordings) -> takes of mv1 and mv2 (no mv3 take found); K. 545 (2 ambiguous + 1 unit) ->
  mv1 only; K. 310 -> mv1 only (mv2 has no catalogue score; any mv2 playing finds no take and is
  excluded); Clementi Op. 36 (2) -> No. 1; Tombeau (1) -> all six movements; Italian Concerto
  (2) -> BWV 971. No recording is excluded as a whole. Session notes outside every accepted take
  (other movements, improvising, warm-ups, unaligned stumbles) are excluded.
- **Correction (found after the `score` stage, from the take table, not from labels):** the two
  Italian Concerto recordings got no take at all. The PianoCoRe `bach_bwv971` MusicXML is also
  the 2nd movement only (49 bars, 3/4, one flat, 1,085 notes, the same as the ASAP file), not the
  whole concerto. So neither catalogue score holds the movements PianoVAM recorded, and both
  recordings are excluded by content. The analysis therefore has 42 recordings, not 44.

**Take QC** (fixed from the null run and the take distribution, before labels):

- Null: each recording run against the candidate scores of another title (7 places further in
  the sorted title list, skipping titles with a shared candidate). 6 null takes over 44
  recordings, all with 0 exactly matched onsets, Dice 0.22-0.30, consensus 0.03-0.16.
- Rule: a take is kept if parangonar Dice inside its crop >= 0.6, the share of exactly matched
  onsets on the local path >= 0.3, and the consensus (share of parangonar matches that the local
  path paired to the same score onset) >= 0.5. Real takes: 518 of 560 kept; null takes: 0 of 6.
- Kept: 143,415 matched notes, 142,554 non-grace, all on staff 1 or 2, in 31 score pieces, 8
  performers. Consensus notes (both aligners agree) 124,147.
- Parangonar returned 97 duplicate matches (one performed note matched twice within a take);
  every row of a duplicate group is dropped (rule fixed here).

Run record of the `align` stage: 88 jobs (44 real, 44 null), 105 s on 10 workers, git `f5761c9`
plus uncommitted work; `session_takes.py` sha256 prefix `a724d41527c9f1cf`, `run.py`
`bc72ad4769ca0ef1` at the time of the run.

## Pre-registration

Written after the development above and before any hand label was joined to an aligned note.
Hashed by anchor (see "Pre-registration hash" below the end marker).

**Note set N (primary).** Matched notes (parangonar, pitch-equal) in QC-kept takes, non-grace,
staff 1 or 2, not in a duplicate-match group, whose video label is `L` or `R`. `Noinfo` notes
are excluded from N (policy below).

**Hand rules scored against the video label.**

- **STAFF (the deployed proxy):** staff 1 -> R, staff 2 -> L.
- **VOICE (BL-19 P1 turned into a rule):** the hand of the most common staff of the note's
  MusicXML voice (ties: the note's own staff).
- **PITCH (baseline):** pitch >= 60 (middle C) -> R, else L.
- **Ceiling (label noise):** the video label's own hand error against `Fingering_GT/`, e =
  errors / labelled manual notes (BL-24: about 0.8%), with a Wilson 95% interval. A perfect rule
  would show a mismatch of about e. The noise-corrected rate is (M - e) / (1 - 2e), reported next
  to the observed rate M.

**Flags scored as detectors of staff != hand.** P1 `cross_voice`, P2 `cross_pitch` (strict),
P2 loose (sensitivity), P3 `capacity`, and `at_risk` = P1 or P2 strict or P3, all computed by the
BL-19 functions (`scripts/staff_hand_proxies.note_flags`) on the folded, DF-09-numbered score.

**Statistics.** Pieces are the score piece ids (31 after QC; recordings of one piece pool). The
bootstrap resamples pieces (2,000, seed 20261010); a t-interval over pieces is reported next to
it. Per-piece statistics need at least 200 notes in N (notes) or 50 events (events).

- **S1 (primary): note mismatch of STAFF**, M = share of N where STAFF != video hand. Pooled over
  notes (piece-bootstrap CI), unweighted mean over pieces (bootstrap and t CIs), median piece,
  share of pieces with M > 10%.
- **S2: hand-sync event mismatch.** An event is one performed pass of a score onset where staff
  1 and staff 2 both start a note (BL-19 definition), with at least one N note on each staff in
  the same take. It is affected if any of its N notes has STAFF != video hand. Pooled, median
  piece, share of pieces > 20%.
- **S3: baseline and correction.** M(PITCH) - M(STAFF) and M(VOICE) - M(STAFF), pooled with a
  paired piece bootstrap, and per piece.
- **S4: proxy detection.** For each flag: precision = P(staff != hand | flag), recall =
  P(flag | staff != hand), lift = precision / M. Pooled with piece-bootstrap CIs.
- **S5: engraver hand marks (BL-19 audit recall check).** Notes in N on the staff that a
  contradicting hand word governs (single-part scores; word staff mapped by DF-09; the word's
  measure): mismatch rate there, and the share of those mismatched notes that `at_risk` flags.
  Descriptive (13 contradicting words in the matched scores, found in development).
- **S6: `Noinfo` policy and missing-not-at-random check.** Primary: `Noinfo` excluded. Check:
  the `Noinfo` rate of matched notes flagged `at_risk` vs not flagged (ratio, piece-bootstrap CI),
  and in S5 measures. Sensitivity: M re-weighted by 1 / P(labelled | piece, at_risk, staff).
- **S7: manual labels.** On matched notes that have a manual label: M against the manual label,
  and the video-vs-manual hand agreement on the same notes. Descriptive (at most 750 notes).

**Decision rules.**

- **D1 (per-note hand from staff), on pooled S1 with its piece-bootstrap CI,** at two bars:
  - 2% (per-note feedback): "below" if the upper bound < 2%, "above" if the lower bound > 2%,
    else "inconclusive";
  - 5% (per-hand aggregates): the same reading at 5%.
- **D2 (hand synchrony, the BL-19 rule on real labels):** pass if the median piece has at most
  5% of events affected and at most 10% of pieces have more than 20%; else concern.
- **D3 (staff vs pitch baseline):** staff beats the pitch split if the paired CI of
  M(PITCH) - M(STAFF) lies above 0.
- **D4 (BL-19 proxies as a filter):** `at_risk` is "useful" if the lower bound of its lift is
  above 2 and its pooled recall is at least 0.5; else "not useful".
- **D5 (missing not at random):** if the `Noinfo` ratio (at_risk vs not) has its lower bound
  above 1.5, S1 and D1 are reported as lower bounds on the true mismatch.

**Subsets (descriptive, no decision).** Per flag (P1, P2, P3); notes on hand-sync events;
Ravel and Debussy pieces vs the rest; by skill level and by performer; the alignment
sensitivity on consensus notes only and on takes with an exact share >= 0.7; a
performer-cluster bootstrap of S1 (8 performers, with a t-interval).

**Reachability.** The observed rate cannot go much below e (about 0.8%) even for a perfect rule.
"Below 2%" is reachable only if the pooled rate is near the noise floor with a tight interval;
"below 5%" needs a pooled rate under about 3-4% given a CI half-width of 1-2 points, which the
piece count (31, very unequal sizes: one piece holds about a quarter of the notes) makes
plausible but not certain. With 31 pieces, D2's "10% of pieces" is 3 pieces.

**Threats named in advance.** The video label is automatic; its 0.8% error comes from the opening
150 notes of 11 recordings, not from crossing passages, so the noise floor may be higher where
mismatches occur. Amateur practice sessions: one performer holds most of Schumann Op. 17; 8
performers in all, so performer and piece are confounded. The alignment is checked only by
agreement between two aligners and the null, not against a ground-truth alignment.

<!-- end pre-registration -->

### Pre-registration hash

SHA-256 of the section from `## Pre-registration` to the end marker, computed with

```
awk '/^## Pre-registration$/{f=1} f{print} /^<!-- end pre-registration -->$/{exit}' README.md | shasum -a 256
```

is `a2b4f5976d90e51e8baee2e5e69378393563eff4d54a9267b1bb0faa67270577`, recorded
2026-10-10T21:52:50Z (copy and hash in `artifacts/prereg_section.md`, `artifacts/prereg_sha256.txt`),
before the `score` stage existed and before any label was joined to an aligned note.

## Command

```
OMP_NUM_THREADS=1 uv run python experiments/2026-10-10-BL-19b-hand-proxies/run.py align --workers 10
OMP_NUM_THREADS=1 uv run python experiments/2026-10-10-BL-19b-hand-proxies/run.py score
uv run python experiments/2026-10-10-BL-19b-hand-proxies/posthoc.py   # not pre-registered
```

Outputs (gitignored) in `artifacts/`: `takes.parquet`, `null_takes.parquet`, `matched.parquet`,
`score_notes.parquet`, `hand_words.parquet`, `notes_labelled.parquet`, `per_piece.csv`,
`summary.json`, `posthoc.json`, `prereg_section.md`, `prereg_sha256.txt`.

## Run record

- `align`: 2026-10-10, M4 Pro, 105 s on 10 workers (88 jobs), git `f5761c9` plus uncommitted
  work. `session_takes.py` sha256 prefix `a724d41527c9f1cf`, `run.py` `bc72ad4769ca0ef1`.
- `score`: started 2026-10-10T21:55:45Z, after the hash (21:52:50Z), 52 s.
  `score_stage.py` `88801a2d721e05f8`, `hand_proxies.py` `2f048b351b6b73a4`. This was the first
  join of any label to an aligned note. Before it, only the synthetic unit tests ran.
- `posthoc.py`: written after reading the `score` outputs. It is disclosed as post-hoc below.
- Seeds: bootstrap 20261010 (2,000 resamples). The take finder and parangonar are deterministic.
- Data: PianoVAM v1.2 at HF commit 1f039ab9 (MIDI, Fingering, Fingering_GT); ASAP and the PianoCoRe
  raw zip as in DATASETS.md; the app catalogue `catalog.json` (version 1).

## Results

### Sample

- Takes: 518 of 560 pass QC; 0 of 6 null takes pass.
- Recordings: 42, after the two Italian Concerto recordings were excluded (see Development).
- Matched notes after QC, without grace notes and duplicate groups (194 rows dropped): 142,360
  in N0. Of these, 117,238 have a video L / R label (N), which is 82.4% of N0.
- N covers 31 pieces and 8 performers. Every piece has at least 522 notes in N.
- Label noise: video against manual hand on all 1,800 manual notes is 12 errors of 1,588
  labelled, so e = 0.76% [0.43, 1.32] (Wilson). This reproduces BL-24.

### S1 and S3: note mismatch by rule (share of N whose rule hand differs from the video hand)

| Rule | Pooled [piece bootstrap] | Mean over pieces [bootstrap; t] | Median piece | Pieces > 10% |
|---|---|---|---|---|
| PITCH, middle-C split (baseline) | 23.4% [19.8, 27.3] | 24.4% [21.5, 27.4; 21.4, 27.5] | 23.8% | 28 / 31 |
| **STAFF (deployed)** | **6.66% [3.51, 9.00]** | 4.84% [3.41, 6.60; 3.12, 6.56] | 3.35% [2.51, 5.60] | 4 / 31 |
| VOICE (P1 as a rule) | 6.19% [4.00, 8.05] | 5.76% [3.81, 8.01; 3.48, 8.05] | 3.41% | 7 / 31 |
| Ceiling: label noise e | 0.76% [0.43, 1.32] | | | |

- Corrected for label noise, the pooled STAFF rate is 6.00% [2.79, 8.37].
- PITCH minus STAFF, paired: +16.7 pt [13.8, 21.4]. STAFF is better in 31 of 31 pieces.
- VOICE minus STAFF, paired: -0.47 pt [-2.29, +1.96]. VOICE is better in 9 pieces, worse in 14,
  and equal in 8.
- A performer-cluster bootstrap (8 performers) gives a pooled interval of [3.35, 9.28].
- Per performer, the rate runs from 0.26% (one performer, Chopin Op. 9/3, 8,039 notes) to 10.9%
  (one performer: Appassionata i and iii, Op. 18, Clair de lune).

Pieces, sorted by STAFF mismatch (`artifacts/per_piece.csv`). Each piece has one performer
unless the table says otherwise.

| Piece | Notes in N | Recordings (performers) | STAFF | VOICE | Events | Events affected | BL-19 at risk | Noinfo |
|---|---|---|---|---|---|---|---|---|
| Ravel, Tombeau 6 Toccata | 1,915 | 1 | 21.8% | 30.1% | 213 | 44.6% | 22.2% | 47.0% |
| Beethoven Op. 57 i | 6,844 | 2 | 13.8% | 11.2% | 519 | 28.7% | 7.5% | 21.5% |
| Debussy Images 1/3 Mouvement | 2,743 | 1 | 11.1% | 11.2% | 498 | 34.3% | 7.7% | 15.0% |
| Schumann Op. 17 i | 33,209 | 7 | 11.1% | 7.1% | 4,654 | 2.8% | 7.8% | 11.2% |
| Ravel, Tombeau 2 Fugue | 753 | 1 | 8.4% | 9.0% | 158 | 8.2% | 11.2% | 17.2% |
| Chopin Op. 18 | 2,931 | 1 | 8.2% | 8.2% | 603 | 16.6% | 0.0% | 17.7% |
| Debussy Clair de lune | 1,525 | 1 | 6.8% | 16.3% | 192 | 6.8% | 10.6% | 11.0% |
| Ravel Ondine (ASAP) | 3,108 | 1 | 6.7% | 10.7% | 307 | 7.2% | 12.2% | 21.2% |
| Ravel Jeux d'eau | 11,086 | 4 (2) | 6.2% | 10.8% | 1,320 | 5.5% | 14.4% | 21.7% |
| Ravel, Tombeau 1 Prélude | 1,437 | 1 | 5.9% | 9.2% | 222 | 4.1% | 5.1% | 30.1% |
| Beethoven Op. 101 iv | 2,374 | 1 | 5.6% | 3.4% | 373 | 8.6% | 4.1% | 37.9% |
| Beethoven Op. 57 iii | 1,031 | 1 | 5.4% | 5.4% | 151 | 9.3% | 1.8% | 14.4% |
| Ravel Sonatine i | 1,591 | 1 | 4.8% | 4.8% | 259 | 5.8% | 2.3% | 9.3% |
| Ravel, Tombeau 4 Rigaudon | 903 | 1 | 4.1% | 10.5% | 164 | 4.9% | 9.7% | 46.0% |
| Chopin Ballade 1 | 2,543 | 1 | 3.5% | 3.0% | 346 | 2.9% | 1.2% | 46.6% |
| Satie Gymnopédie 1 | 775 | 3 (3) | 3.4% | 3.4% | 106 | 0.0% | 0.8% | 12.4% |
| Rachmaninoff Op. 32/10 | 4,799 | 2 | 3.2% | 1.4% | 870 | 3.4% | 2.6% | 3.9% |
| Ravel, Tombeau 5 Menuet | 1,084 | 1 | 3.0% | 3.1% | 170 | 2.4% | 5.3% | 22.0% |
| Scriabin Op. 19 | 1,980 | 1 | 2.8% | 2.6% | 263 | 1.9% | 3.2% | 33.0% |
| Mozart K. 310 i | 5,458 | 1 | 2.6% | 3.8% | 910 | 0.2% | 6.3% | 13.5% |
| Rachmaninoff Op. 3/2 | 1,274 | 1 | 2.5% | 4.9% | 208 | 6.2% | 7.3% | 11.4% |
| Ravel, Tombeau 3 Forlane | 1,630 | 1 | 1.8% | 1.9% | 311 | 3.9% | 3.0% | 27.1% |
| Rachmaninoff Op. 39/8 | 3,161 | 2 | 1.6% | 1.9% | 696 | 1.6% | 3.2% | 12.8% |
| Schumann Op. 17 ii | 6,641 | 3 | 1.6% | 0.9% | 1,487 | 1.4% | 2.2% | 11.3% |
| Beethoven WoO 59 | 818 | 1 | 1.5% | 1.5% | 96 | 0.0% | 0.0% | 12.3% |
| Bach WTC I Prelude 1 | 522 | 1 | 1.1% | 0.2% | 1 | n/a | 1.3% | 4.7% |
| Rachmaninoff Op. 16/4 | 2,133 | 1 | 0.7% | 1.2% | 501 | 1.2% | 0.6% | 21.1% |
| Chopin Waltz A minor B. 150 | 757 | 1 | 0.5% | 0.5% | 134 | 1.5% | 0.0% | 10.6% |
| Chopin Nocturne Op. 9/3 | 8,039 | 1 | 0.3% | 0.3% | 1,303 | 0.5% | 0.0% | 9.0% |
| Mozart K. 545 i | 2,999 | 3 (2) | 0.2% | 0.2% | 435 | 0.9% | 0.0% | 9.7% |
| Clementi Op. 36/1 | 1,175 | 2 | 0.2% | 0.2% | 199 | 0.5% | 0.0% | 11.7% |

Across pieces, the BL-19 at-risk share and the STAFF mismatch have a Spearman correlation of
0.72.

### S2: hand-sync events (17,669 events in 30 pieces with at least 50 events)

| | Value |
|---|---|
| Events with any STAFF != hand note, pooled | 5.49% [3.19, 9.62] |
| Median piece | 3.65% [1.74, 6.02] |
| Pieces above 20% | 3 of 30 = 10.0% [0, 20.1]: Tombeau Toccata 44.6%, Debussy Mouvement 34.3%, Appassionata i 28.7% |
| Notes on hand-sync events, STAFF mismatch | 2.56% [1.57, 4.34] (other notes 11.2% [5.3, 15.3]) |

### S4: the BL-19 proxies as detectors of STAFF != hand (base rate 6.66%)

| Flag | Share of N flagged | Precision | Recall | Lift |
|---|---|---|---|---|
| P1 cross-staff voice | 3.6% | 56.5% [21.1, 78.9] | 30.6% [13.6, 38.2] | 8.5 [4.3, 12.4] |
| P2 pitch crossing, strict | 1.6% | 16.3% [10.6, 31.9] | 3.9% [1.4, 10.3] | 2.4 [1.6, 5.7] |
| P2 loose (sensitivity) | 3.6% | 18.2% [11.3, 25.2] | 9.9% [3.5, 26.9] | 2.7 [1.8, 5.2] |
| P3 one-hand capacity | 1.4% | 45.7% [30.3, 49.5] | 9.4% [2.9, 12.8] | 6.9 [5.1, 11.7] |
| **at risk (P1, P2 strict or P3)** | 6.2% | 42.2% [17.9, 61.4] | **39.4% [24.2, 47.1]** | 6.3 [3.6, 9.6] |

- Notes not at risk: STAFF mismatch 4.30% [2.45, 5.62].
- Notes at risk: 42.2%.

### S5: engraver hand marks (the BL-19 audit's recall check)

- The matched scores carry 13 contradicting hand words (Debussy 1, Jeux d'eau 1, Tombeau Fugue 2,
  Rachmaninoff Op. 32/10 2, Scriabin Op. 19 7). All 13 marked measures were played.
- On the marked staff in those measures there are 353 matched notes. 245 of them have a label;
  the `Noinfo` share there is 30.6%.
- 58 of the 245 labelled notes (23.7%) are played by the other hand. On the same staves, the
  pieces' base rates are 3.0-10.4%.
- `at_risk` flags 37.9% of those 58 notes, and 20.4% of all labelled notes in the marked measures.
- Per measure the mismatch runs from 0% (4 of 13 measures, for example Debussy m. 17 and
  Scriabin mm. 71 and 73) to 75% (Scriabin m. 64, 8 notes). A hand word governs only part of a
  measure, or the player did not follow it.

### S6: `Noinfo` (missing labels)

- `Noinfo` covers 17.6% of N0: 24.2% of at-risk notes and 17.2% of the others. The ratio is
  1.41 [1.04, 1.93].
- By staff: staff 1 17.1%, staff 2 18.2%.
- Re-weighted by 1 / P(labelled | piece, at risk, staff), the pooled STAFF mismatch is 6.84%
  (6.66% unweighted).

### S7: manual labels (5 matched recordings, 636 matched notes, all from the openings)

- STAFF against the manual hand: 2 mismatches in 636 notes (0.31%).
- The video labels 532 of the 636 notes and disagrees with the manual hand on 9 of them (1.7%).
- On those 532 notes, STAFF against video gives 1.69%. So in these openings, the video-vs-staff
  mismatch is mostly label error, and the video error there is about twice e.

### Subsets (descriptive)

| Subset | Notes | STAFF mismatch, pooled | Median piece |
|---|---|---|---|
| Ravel and Debussy (11 pieces) | 27,775 | 7.34% [5.32, 11.0] | 6.2% |
| Other composers (20 pieces) | 89,463 | 6.45% [1.90, 9.16] | 2.6% |
| Advanced (24 pieces) | 56,642 | 4.70% [3.03, 6.61] | 3.1% |
| Intermediate (8 pieces, 4 performers) | 60,526 | 8.51% [1.91, 11.2] | 6.1% |
| Consensus notes only (alignment sensitivity) | 102,348 | 6.66% [3.33, 9.24] | 3.5% |
| Takes with exact share >= 0.7 | 92,750 | 6.44% [2.57, 9.46] | 3.2% |

One beginner recording contributes 70 notes (Gymnopédie, 1 mismatch). Skill, performer and
piece are confounded: most pieces have one performer.

### Post-hoc (not pre-registered; `posthoc.py`)

1. **Are the mismatches label artefacts?** Mostly not, on three checks.
   - Hand-identity swaps: 17 of 8,309 measure passes have both staves mostly labelled with the
     other hand. They hold 109 of the 7,810 mismatches (1.4%).
   - Hand order: 2.9% of mismatched notes have L above every simultaneous R note (or R below
     every L), against 0.65% of agreeing notes. The most come from Appassionata i (47) and
     Jeux d'eau (41).
   - The 7,810 mismatches split into 4,819 upper-staff notes played by L and 2,991 lower-staff
     notes played by R.
   - Runs of consecutive mismatches in performance order: median 1 note, maximum 24.

   The pattern is single notes moved to the adjacent hand (redistribution), not mislabelled
   passages. Isolated video errors cannot be excluded, though: S7 shows that they exist at
   about 1.7% in the openings.
2. **BL-19 recommendation 1 (drop events with a P1 or P3 note) on real labels.**
   - It removes 370 of 17,669 events. The affected share goes from 5.49% to 5.34% [3.14, 9.52].
   - Dropping every event with an at-risk note removes 750 events and gives 4.49% [2.65, 7.75].
   - The proxies predict 4.24% of these events at risk; 5.49% are affected.

## Verdict (Provisional)

By the pre-registered rules:

- **D1, per-note hand from staff.**
  - At the 2% bar: **above**. The lower bound, 3.5%, exceeds 2%, so staff is not a per-note
    hand label.
  - At the 5% bar: **inconclusive**. The pooled rate is 6.66% [3.51, 9.00], 6.0% after noise
    correction.
- **D2, hand synchrony: pass, at the threshold.**
  - The median piece has 3.65% of events affected (bar 5%).
  - 3 of 30 pieces (10.0%) exceed 20% (bar "at most 10%"). One more such piece would turn it
    into a concern.
- **D3: staff beats the pitch split.** +16.7 pt [13.8, 21.4], better in 31 of 31 pieces.
- **D4: the BL-19 proxies are "not useful" as a filter by the registered rule.** Recall is 0.39,
  below the 0.5 bar. They are informative: lift 6.3 [3.6, 9.6], above the 2 bar.
- **D5: no lower-bound adjustment.** The `Noinfo` ratio is 1.41 [1.04, 1.93], with a lower bound
  under 1.5. `Noinfo` is still somewhat more common on at-risk notes, and re-weighting moves the
  pooled rate only from 6.66% to 6.84%.

What this answers for BL-19 and its audit:

- **The true rate is now bounded on these pieces.** About 1 note in 15 is played by the other
  staff's hand (pooled; the median piece is 1 in 30). In the BL-19 tail pieces it is 1 in 5 to
  1 in 10.
- **The size of the BL-19 proxy rate was about right, but the notes are not.**
  - The proxies flag 6.2% of notes; 6.7% are mismatched.
  - Only 42% of flagged notes are mismatched, and the flags find 39% of the mismatched notes.
- **The VOICE correction does not help on balance.** P1 notes are only 57% mismatched, so
  flipping them breaks almost as many notes as it fixes.

Hand synchrony as deployed passes the BL-19 rule on real labels, but only just. In its tail
(Toccata, Debussy Mouvement, Appassionata i), 29-45% of events pair notes of one hand.

Per-hand feedback stays off. A hand-assignment model would be needed, for example trained on
PianoVAM labels with pieces held out. That is a lead decision.

## Threats to validity

- **Label noise in the passages that matter.** e = 0.76% comes from the openings of 11
  recordings. On the 532 opening notes matched here, the video disagrees with the manual hand
  1.7% of the time, while staff disagrees with it 0.3% of the time. The video error may be
  higher in dense or crossing passages, where most mismatches sit. The post-hoc checks argue
  against systematic swaps, not against isolated errors. Without manual labels in hard passages,
  the split between "label error" and "redistribution" is not identified.
- **Who played.** Amateur practice sessions by 8 performers; most pieces have one performer, and
  one performer holds 34% of N (Schumann Op. 17). Redistribution is a performer choice, so these
  rates describe these players. Experts may redistribute more (more fluent hand sharing) or
  less. No leave-performer-out estimate is possible with one performer per piece.
- **Alignment** has no ground truth here. It is checked by agreement between two aligners
  (consensus notes give the same 6.66%), stricter takes (6.44%), and a wrong-score null (0 of 6
  null takes kept). A wrong same-pitch match moves a note's staff only where both staves hold
  that pitch nearby.
- **Missing labels.** 17.6% of matched notes are `Noinfo`, and somewhat more on at-risk notes.
  Re-weighting moves the rate by 0.2 pt, but `Noinfo` caused by occlusion could hide mismatches
  that the re-weighting cannot see.
- **Engravings.** PianoCoRe scores are user engravings. A different engraving of the same piece
  (another voice or staff split) would change STAFF, VOICE and the proxies. Ondine was run on the
  ASAP score only.
- **Coverage.** 31 pieces, Ravel-heavy (Tombeau counts as 6 pieces from 1 recording), and only
  the passages players practised.

## Audit (eval-auditor, 2026-10-10)

**Verdict: Confirmed with caveats.** Every pre-registered decision is applied as registered and
reproduces exactly. D2 is a boundary result that one piece more or less would change, and two
post-hoc readings in "Post-hoc" and "What this answers" overreach. The fixes below are wording
and disclosure. None of them changes D1-D5.

### What was checked

1. **Pre-registration.** The anchor command at line 175 gives `a2b4f597...70577`, the same as
   `artifacts/prereg_sha256.txt`, and the section is byte-identical to
   `artifacts/prereg_section.md`. The author transcript (subagent `a9cb3724bc0fa75cc`) shows this
   order: QC thresholds 0.6 / 0.3 / 0.5 applied to the take table at 21:51:11Z, README with the
   pre-registration written at 21:52:44Z, hash at 21:52:50Z, `hand_proxies.py` at 21:53:37Z,
   `score_stage.py` at 21:54:48Z, the first and only `score` run at 21:55:44Z (log time) and
   `posthoc.py` at 21:58:03Z. File mtimes agree. The sha256 prefixes of `run.py`,
   `session_takes.py`, `score_stage.py` and `hand_proxies.py` match the run record. Before the
   hash, no per-note L / R label was read. One pre-hash call (21:41:41Z) printed
   `pianovam.hand_label_summary()`: per recording, `n_noinfo` and `n_manual` counts. These are
   totals per recording, cannot show staff against hand, and are the BL-24 figures. The
   Development sentence "No hand label, `Noinfo` flag or manual label was loaded" is therefore
   slightly too strong (fix 6). The QC thresholds were fixed from the null takes and the
   distribution of exact share and Dice, with no labels. They sit in the unhashed Development
   section, but the transcript shows them in place before the hash.
2. **Reproduction.** In scratch, with `ART` and `ROOT` patched in copies of the scripts:
   - `align` (88 jobs, 101 s): `takes`, `null_takes`, `matched`, `score_notes` and `hand_words`
     identical to the committed artifacts, row for row.
   - `score`: `summary.json` identical except the row order of `S5_words.piece_staff_base`,
     which comes from iterating a Python set. `per_piece.csv` is byte-identical.
   - `posthoc.py`: identical except `mismatch_runs.n_runs`, 4,252 against 4,251. The cause is
     `sort_values("perf_onset_sec")` with the default unstable sort, applied to chord ties. Median
     and max are unchanged (fix 7).
   - Every README number I compared with `summary.json` / `posthoc.json` matches: S1-S7, the
     subsets, the per-piece table and the post-hoc figures. The pooled STAFF interval with other
     bootstrap seeds (5,000 resamples) is [3.32-3.43, 8.88-9.02].
3. **Label join.** `pianovam.hand_labels` maps label rows to notes by pitch and nearest onset
   within 0.5 ms. It raises on any unmatched row, double match or velocity mismatch. The score
   stage then indexes the returned array by `perf_idx`, a row in the same `perf.notes` array, and
   first asserts that note id and pitch agree with the align-stage load for all 142,360 rows. No
   join uses label-file row order.
4. **Does misalignment drive the mismatch?** Mostly not, except in the Toccata. All on N, in
   scratch:
   - Crossed matches: in no take does a same-pitch pair come out in the reverse performance
     order of its score order.
   - Same pitch on both staves at the same onset: 0.07% of N.
   - Timing outliers: the performed onset is compared with a local linear fit from the
     neighbouring score onsets. The mismatch rate is the same for outliers and inliers at every
     threshold: 6.9% vs 6.6% at 0.15 s, 6.4% vs 6.7% at 0.6 s.
   - Strictest subset (consensus notes, no same-pitch note on the other staff within one
     quarter, no crossing): pooled 6.11% [2.66, 8.82]. D1 reads the same.
   - **Recurrence.** Mismatches recur at the same score note. Over 22,865 score notes with at
     least two labelled passes, P(mismatch on another pass | mismatch) = 0.90, against a base rate
     of 0.068. Across different recordings it is 0.90 against 0.081. Random video errors or
     random misalignment would recur near the base rate. These mismatches are systematic per
     score note: redistribution, engraving, or a systematic error of the video labeller at
     particular passages.
   - Worst pieces, all against the strict subset:

     | Piece | All N | Strict subset | Mismatches with a same-pitch other-staff note within 1 quarter |
     |---|---|---|---|
     | Appassionata i | 13.8% | 14.3% | 3.8% |
     | Debussy Mouvement | 11.1% | 10.9% | 9.2% |
     | Op. 17 i | 11.1% | 11.4% | 4.9% |
     | **Tombeau Toccata** | 21.8% | **4.5%** | **86%** |

     The Toccata's tail value sits in its same-pitch hand-alternation texture. There, which
     staff a performed repeated pitch belongs to is ambiguous for the aligner when a note is
     omitted, and the video labeller sees both hands on the same keys. That piece also has 47%
     `Noinfo`.
   - **Op. 17 i** holds 28% of N, in a PianoCoRe user engraving. Half of its 3,680 mismatches
     sit in 18 of 311 measures. In m. 48, all 148 labelled staff-1 notes are played by L, in all
     7 recordings. In the raw MusicXML, mm. 41-49 have voice 2 (16 notes per bar) on staff 1,
     with 0-1 notes on staff 2. This is a figuration notated on the upper staff and played by the
     left hand: staff != hand at passage level, by engraving. P1 cannot flag it, because voice 2
     is mostly a staff-1 voice across the score.
5. **D2.** The count is right: 3 of the 30 pieces with at least 50 events exceed 20%, and the
   share is exactly 0.10. Bach WTC I/1 has 1 event and is the only piece below the minimum. The
   registered "at most 10%" matches BL-19's "concern if more than 10%", so a tie passes as
   registered. The reading is unstable:
   - Leaving out any one of the 27 pieces under 20% gives 3/29 = 10.3%, a concern. Leaving out
     any one of the 3 tail pieces still passes.
   - A minimum of 100 events (Beethoven WoO 59 has 96) gives 3/29, a concern. A minimum of 1
     gives 3/31 = 9.7%, a pass.
   - The share of piece-bootstrap resamples that pass is 0.59.
   - Tombeau as one piece: 2/25, pass. Piece x recording as the unit: 4/46, pass.
     Complete-case events (every note of the event labelled): 3/30, median 2.9%.
   - Label noise alone (e = 0.76%, 2.96 N notes per event) would affect about 2.1% of events in
     the median piece. Noise therefore pushes toward "concern", so it does not explain the pass.
   - The Italian Concerto exclusion cannot move D2 or any other decision: those recordings
     produced no take, so there was nothing to score.
   - D2 is "pass at the boundary, not stable to one piece".
6. **Exclusions.** None uses labels:
   - Italian Concerto: no take against a 2nd-movement-only score, found from the take table.
   - Duplicate groups: 194 rows, all in QC-kept takes.
   - Grace notes: 861.
   - QC: 42 failing takes, 3,242 matched notes.

   Even if all 3,242 notes in the failing takes were labelled mismatches, the pooled rate would
   rise by at most 2.5 pt, to 9.2%.
7. **Statistics.**
   - The piece cluster bootstrap and the t-interval are as registered.
   - Leave-one-piece-out pooled STAFF ranges 4.91-7.13%. Without Op. 17 i it is 4.91%
     [3.01, 7.13], and without its performer (Op. 17 i and ii, 34.0% of N) 5.20% [3.19, 7.53].
     D1 reads the same in both cases (above 2%, inconclusive at 5%).
   - Tombeau as one cluster: [3.30, 8.98]. Work-level clusters (24): [3.50, 8.36].
   - The performer bootstrap has 8 clusters, 3 of them under 310 notes. The registered
     performer t-interval is in `summary.json` but missing from the README: mean over the 6
     performers with at least 200 notes, 5.32% [0.68, 9.96] (fix 4).
   - Wilson e = 12/1588 = 0.76% [0.43, 1.32] is correct.
   - **The noise correction carries the D1 2% reading only under the assumed e.** The
     noise-corrected lower bound reaches 2% at e = 1.57%. The video error measured on the 532
     matched opening notes (S7) is 1.69%. The registered D1 is on the observed rate, so "above"
     stands. The recurrence result (item 4) argues against random label error, but not against
     systematic labeller error in hard passages.
   - **`Noinfo` and mismatch rise together across pieces:** Spearman 0.43 for notes and 0.44
     for events. Inverse-probability weighting inside (piece, at_risk, staff) cells cannot see
     this. It supports the README's warning that the observed rate may understate the true one.
     D5 is applied correctly: the lower bound 1.04 < 1.5.
   - D3 is robust: 31 of 31 pieces. D4 is robust: the recall upper bound, 47.1%, is below 50%.
8. **Gates.**
   - `uv run pytest -q`: 591 passed, 8 skipped.
   - `uv run ruff check src tests`: all checks passed.
   - The new tests (14) pass.
   - `ruff check` on the experiment folder reports 10 E501 lines (not a gate).

### Required author fixes (wording and disclosure; no decision changes)

1. **D2 wording** (Verdict, EXPERIMENTS row, WORKBOARD / BACKLOG lines): say "pass at the
   boundary, not stable". Removing any one of the 27 non-tail pieces, or raising the event
   minimum to 100, turns it into a concern. Under the piece bootstrap it passes in 59% of
   resamples. "One more such piece would turn it into a concern" states only half of this.
2. **Post-hoc 1, last paragraph.** Replace "single notes moved to the adjacent hand
   (redistribution), not mislabelled passages". The runs statistic in performance order cannot
   see passage-level patterns, because the other hand's notes break the runs. The largest
   contributor is passage-level and engraving-driven (Op. 17 i mm. 41-49, item 4). Add the
   recurrence result (0.90 vs 0.068) as the evidence against random label noise.
3. **Tombeau Toccata.** In the per-piece discussion and the "tail" sentence of the Verdict, note
   that 86% of its mismatches are same-pitch hand-alternation notes, and that its rate is 4.5%
   outside them. Its 44.6% event share is the least certain of the three tail values.
4. **Performer cluster.** Report the registered t-interval: 5.32% [0.68, 9.96] over 6 performers
   with at least 200 notes. Note that 3 of the 8 performers have fewer than 310 notes.
5. **"What this answers".**
   - "The true rate is now bounded" should read "measured against the video labels".
   - Name the two directions of uncertainty that remain:
     - labeller error: the D1 2% reading would be lost at e of about 1.6%;
     - piece-level `Noinfo` rising with mismatch (Spearman 0.43).
   - "The size of the BL-19 proxy rate was about right" compares the corpus at-risk share with
     this sample. Restrict it to "on these notes".
6. **Development.** Change "No hand label, `Noinfo` flag or manual label was loaded" to say that
   only the per-recording `hand_label_summary` counts (`n_noinfo`, `n_manual`) were printed, at
   21:41Z, and that no per-note label was read.
7. **`posthoc.py`.** Use `kind="stable"` (or sort by onset and pitch) in the run-length sort.
   `n_runs` is 4,251 or 4,252 depending on tie order.

### What I could not verify

- Whether the Op. 17 i mm. 41-49 notation matches a printed edition (the engraving is a PianoCoRe
  user file).
- Whether the Toccata and other mismatches in dense passages are video errors. No manual
  labels exist outside the openings.
- Whether the Spearman link between `Noinfo` and mismatch is causal (occlusion hiding
  mismatches) or a shared effect of difficulty.

### Rule lessons (for `rules/experiments.md`, lead's call)

- **A "share of units above X" criterion on about 30 units can sit exactly on the bar.**
  Before registering, compute the counts that pass: 3/30 passes and 3/29 fails. After the run,
  report a leave-one-unit-out reading and the share of bootstrap resamples that pass, not only
  "one more tail unit would flip it".
- **Ground-truth disagreements need a recurrence check before they are called noise or
  signal.** Compute P(disagree on another pass | disagree) at the same score note, against the
  base rate. Random label noise and random misalignment recur at about the base rate. BL-19b:
  0.90 against 0.068.
- **A run-length statistic in performance order cannot show passage-level structure** when the
  other hand's notes interleave. Count concentration per measure instead: what share of
  mismatches sits in the top measures, and how often a whole staff in a measure is played by
  the other hand.

### Corrections after the audit (2026-10-10)

Author fixes required by the audit above. They correct wording and disclosure only. No
registered decision changes (D1-D5 read as before). Numbers marked "audit" were measured by the
eval-auditor (section above, scratch `bl19b/`); the others come from `summary.json` /
`posthoc.json`.

1. **D2 is a pass at the boundary, and it is not stable to one piece.** This replaces "pass, at
   the threshold" and "one more such piece would turn it into a concern".
   - The registered count gives a pass: 3 of 30 pieces above 20% equals the 10% bar.
   - Leaving out any one of the 27 pieces under 20% gives 3/29 = 10.3%: a concern (audit).
   - Raising the event minimum from 50 to 100 also gives a concern, 3/29 (audit).
   - The rule passes in 59% of piece-bootstrap resamples (audit).
   - With Tombeau counted as one piece, it passes at 2/25 (audit).

   Hand synchrony therefore has no stable pass on real labels.
2. **Post-hoc 1: the mismatches are systematic, not single notes.** This replaces the reading
   "single notes moved to the adjacent hand (redistribution), not mislabelled passages". The
   run-length statistic cannot show passage-level structure, because the other hand's notes
   interleave and break the runs. Two audit findings:
   - **Recurrence.** On 22,865 score notes with at least two labelled passes, a mismatch recurs
     at the same score note on another pass 90% of the time, against a base rate of 6.8%. Across
     different recordings it is 90% against 8.1%. Random label noise or random misalignment would
     recur near the base rate. These mismatches belong to the score note: redistribution,
     engraving, or a systematic error of the video labeller in particular passages.
   - **Engraving.** In Schumann Op. 17 i (a PianoCoRe user engraving, 28% of N), half of the
     3,680 mismatches sit in 18 of 311 measures. In mm. 41-49, voice 2 (16 notes per bar) is
     engraved on staff 1, with 0-1 notes on staff 2, and is played by the left hand. In m. 48,
     all 148 labelled staff-1 notes are played by L, in all 7 recordings. P1 cannot flag this,
     because voice 2 is mostly a staff-1 voice across the score.

   The swap and hand-order checks still stand: few whole-measure two-staff swaps, few order
   violations.
3. **Tombeau Toccata caveat.** 86% of its mismatches are same-pitch hand-alternation notes, where
   a performed repeated pitch is ambiguous for the aligner and the video labeller sees both hands
   on the same keys (audit). Outside those notes its rate is 4.5% (audit), against 21.8% overall.
   Its 44.6% event share is the least certain of the three D2 tail values, and the piece has 47%
   `Noinfo`.
4. **Performer cluster, registered t-interval.** The mean over the 6 performers with at least
   200 notes is 5.32% [0.68, 9.96]. 3 of the 8 performers have fewer than 310 notes (70, 152 and
   306). The performer-cluster bootstrap interval above rests on few, very unequal clusters.
5. **"What this answers", reworded.**
   - "The true rate is now bounded on these pieces" should read: the staff-vs-hand mismatch is
     now measured against the video labels on these pieces.
   - Two uncertainties remain, and they act in opposite directions:
     - **Label error in hard passages.** The noise floor e = 0.76% comes from easy openings. The
       D1 "above 2%" reading, after noise correction, holds only while e stays below about 1.57%
       (audit). The video error measured on the 532 matched opening notes here is 1.69% (S7). The
       registered D1 is read on the observed rate, so it stands. A labeller that errs
       systematically in dense passages could still explain part of the mismatch, and the
       recurrence result (item 2) does not rule that out.
     - **`Noinfo`.** Across pieces, the `Noinfo` share rises with mismatch (Spearman 0.43 for
       notes, 0.44 for events; audit). Re-weighting within (piece, at_risk, staff) cells cannot
       see this. The observed rate may understate the true one.
   - "The size of the BL-19 proxy rate was about right" holds only **on these notes**: the
     proxies flag 6.2% and 6.7% are mismatched. It says nothing about the BL-19 catalogue-wide
     5.2%.
6. **Development disclosure.** The statement "No hand label, `Noinfo` flag or manual label was
   loaded" before the hash is too strong.
   - At 21:41Z (before the hash at 21:52:50Z), `pianovam.hand_label_summary()` printed per-recording
     counts, including `n_noinfo` and `n_manual`, to list the candidate recordings.
   - These are per-recording totals (the BL-24 figures), and no per-note L / R label was read.
   - Nothing that compares staff with hand was seen before the hash.
7. **`posthoc.py` sort.** Both sorts on `perf_onset_sec` now use `kind="stable"`. The default
   sort is unstable on chord ties, so `n_runs` was 4,251 in this run and 4,252 in the auditor's.
   After the change it is **4,249**, the same on two reruns. Median (1), maximum (24) and notes
   in runs of 10 or more (671) are unchanged, and so is every other `posthoc.json` value.
   `posthoc.py` is outside the pre-registration; its new sha256 prefix is `35e806a97428b81f`.
