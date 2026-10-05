# BL-19: staff is not hand, a score-only estimate

Ticket: BL-19    Hypothesis: none (measurement)    Status: Provisional

## Question

Hand synchrony (`control.hand_synchrony`) and any future per-hand feedback treat the upper
staff as the right hand and the lower staff as the left. How often might that be wrong in the
repertoire PianoLens uses? Is there a dataset with real hand labels that could check the
estimate?

**Everything below is a proxy.** No note here has a known hand. The proxies mark notes whose
hand *may* differ from their staff. Some are likely misassignments, some are only uncertain.

## Pre-registration

Written and hashed before any proxy was computed: `docs/specs/correctness-validation.md`,
section "Pre-registration BL-19". sha256 of the section (from its header line to end of file at
the time) is `14d27bb5610f15224ff5e6e0f288d5b56501c91ec816468da8f31fb1d1a93c54`, hashed
2026-09-29 15:44 CDT. The copy and hash are in `artifacts/prereg_section.md` and
`artifacts/prereg_sha256.txt`.

Proxies (per non-grace note on staff 1 or 2):

- **P1, cross-staff voice.** The note's staff differs from the most common staff of its
  MusicXML voice. This catches cross-staff beaming, such as the right-hand arpeggios of Chopin
  Op. 10/1 dipping into the bass staff. Likely misassigned.
- **P2, pitch crossing (strict).** An upper-staff note below every lower-staff note sounding at
  its onset, or the reverse. The direction of the error is uncertain: in a true hand crossing,
  each hand may still stay on its own staff. Loose variant (sensitivity): below the highest /
  above the lowest.
- **P3, one-hand capacity.** A staff starts more than 5 notes at once, or spans more than 16
  semitones (wider than a major tenth). The other hand likely takes one, unless the chord is
  rolled. Rolls are not detected.
- **At risk** = P1, P2 strict or P3.
- **Hand words** (m.d., m.s., m.g., r.h., l.h., sopra, sotto, ...) from the MusicXML directions,
  with their staff. Counted, not mapped to notes. A word is "contradicting" when it names the
  hand of the other staff.

Hand-sync events are score onsets where staff 1 and staff 2 both start a note, the pairs
`hand_synchrony` uses. An event is affected when any of its notes is at risk.

Concern if the median piece has more than 5% of events affected, or if more than 10% of pieces
have more than 20% affected.

## Data

The app catalogue `data/interim/app/catalog.json` (the repertoire the report and app use):

- 221 ASAP MusicXML scores;
- 584 PianoCoRe tier A MusicXML scores with at least 50 references, read from
  `PianoCoRe-1.0-raw-midi.zip`. These are mostly PDMX / MuseScore user engravings.

All 805 were loaded (0 failures after a fix for 4 PianoCoRe `.mxl` files that are plain XML).
802 have notes on staves 1 and 2. The other 3 number their staves 3 and 4 (see "Staff numbering"
below).

## Method

`scripts/staff_hand_proxies.py` (new): partitura 1.9.0 `load_score` then `load_score_part`
(parts merged, folded), `note_array(include_staff=True, include_grace_notes=True)`, grace notes
dropped, ties merged by partitura. Hand words are parsed from the MusicXML directly, because
partitura's `Words` drops the direction's staff. Synthetic tests for every proxy and the words
classifier are in `tests/features/test_bl19_bl20_helpers.py`. The 95% intervals are a piece
bootstrap (2,000 resamples, seed 20260929).

## Command

```
OMP_NUM_THREADS=1 uv run python scripts/staff_hand_proxies.py --workers 12
```

## Run record

- 2026-09-29, M4 Pro, 189 s. Code: git `dd13ab2` plus uncommitted work.
  `scripts/staff_hand_proxies.py` sha256 prefix `0f21a86beb4591a7`.
- A first full run had 4 load failures (plain-XML `.mxl`). The fix only changes file handling,
  and the rerun replaced every output.
- Outputs (gitignored) in `artifacts/`: `per_piece.csv`, `per_composer.csv`, `hand_words.csv`,
  `summary.json`, `tables.txt`, `staff_numbering.txt`, `run.log`.

## Results

### Corpus level (802 pieces, 1,627,592 notes, 297,495 hand-sync events)

| | Notes | Hand-sync events |
|---|---|---|
| P1 cross-staff voice | 2.8% | 1.5% |
| P2 pitch crossing, strict | 1.2% | 1.8% |
| P2 pitch crossing, loose | 2.5% | 3.7% |
| P3 capacity | 1.5% | 0.8% |
| **At risk (P1, P2 strict or P3)** | **5.2%** [4.7, 5.8] | **3.9%** [3.3, 4.5] |

Per piece, the share of events affected is very skewed:

- median 0.9% [0.6, 1.1];
- 75th percentile 4.7%, 90th 11.3%, 95th 18.6%, 99th 49.1%;
- 4.2% of pieces have more than 20% of events affected.

The median piece has 2.3% of its notes at risk.

| Source | Pieces | Notes at risk | Events at risk | Median piece, events | Pieces > 20% events | Pieces with hand words (contradicting) |
|---|---|---|---|---|---|---|
| ASAP | 220 | 5.1% | 3.6% | 1.3% | 2.7% | 17 (8) |
| PianoCoRe | 582 | 5.3% | 4.1% | 0.6% | 4.8% | 99 (65) |

### Per composer (both sources, composers with at least 5 pieces; pooled over notes and events)

| Composer | Pieces | P1 notes | P2 notes | P3 notes | Notes at risk | Events at risk | Median piece, events |
|---|---|---|---|---|---|---|---|
| Albéniz | 15 | 4.9% | 4.3% | 0.6% | 9.5% | 14.9% | 4.5% |
| Ravel | 31 | 5.5% | 3.8% | 1.8% | 10.8% | 9.0% | 8.8% |
| Debussy | 58 | 6.2% | 3.0% | 1.4% | 10.4% | 7.7% | 4.6% |
| Schumann | 38 | 5.0% | 1.3% | 1.7% | 7.3% | 7.5% | 0.9% |
| Haydn | 16 | 2.3% | 0.5% | 0.1% | 2.9% | 5.4% | 0.7% |
| Brahms | 9 | 1.9% | 0.8% | 2.7% | 4.8% | 4.5% | 4.3% |
| Scriabin | 12 | 0.7% | 0.8% | 2.0% | 3.5% | 3.8% | 2.3% |
| Beethoven | 110 | 2.9% | 1.2% | 1.6% | 5.1% | 3.3% | 1.0% |
| Bach | 121 | 2.1% | 0.1% | 1.8% | 3.9% | 3.3% | 1.0% |
| Rachmaninoff | 37 | 1.8% | 1.8% | 2.4% | 5.7% | 3.2% | 2.8% |
| Liszt | 34 | 3.1% | 0.9% | 1.6% | 5.3% | 2.8% | 1.8% |
| Mozart | 41 | 0.6% | 0.3% | 0.2% | 1.1% | 2.5% | 0.0% |
| Schubert | 26 | 1.1% | 1.0% | 0.9% | 2.9% | 2.2% | 0.1% |
| Chopin | 140 | 1.4% | 0.3% | 1.3% | 2.8% | 1.9% | 0.2% |
| Scarlatti | 11 | 0.8% | 0.8% | 0.1% | 1.7% | 1.5% | 0.0% |
| Tchaikovsky | 13 | 1.0% | 0.7% | 0.2% | 1.9% | 1.1% | 0.4% |
| Satie | 10 | 6.2% | 0.0% | 4.1% | 9.2% | 1.0% | 0.0% |
| Grieg | 8 | 1.8% | 1.2% | 0.0% | 3.0% | 0.8% | 0.0% |
| Mussorgsky | 12 | 2.0% | 0.0% | 0.8% | 2.9% | 0.7% | 0.0% |
| Mendelssohn | 12 | 2.9% | 0.0% | 0.1% | 3.0% | 0.3% | 0.0% |
| Joplin | 6 | 0.7% | 0.0% | 0.0% | 0.7% | 0.1% | 0.0% |
| Burgmüller | 7 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

A further 35 pieces by 25 composers with fewer than 5 pieces each are in
`artifacts/per_piece.csv`. Per-source composer rows are in `artifacts/per_composer.csv`.

Most affected pieces by event share, with at least 40 events:

| Piece | Source | Events | Events at risk | Main proxy |
|---|---|---|---|---|
| beethoven_op10_no3_mv3 | ASAP | 90 | 83% | P1 (26% of notes) |
| faure_op56_mv1 | PianoCoRe | 232 | 68% | P3 (47% of notes) |
| dvorak_op72_no2 | PianoCoRe | 366 | 68% | P3 / P2 |
| beethoven_op2_no3_mv2 | ASAP | 199 | 59% | P2 (23% of notes) |
| Ravel, Ma mère l'Oye 5 | PianoCoRe | 134 | 52% | P3 |
| schumann_op6_no14 | PianoCoRe | 52 | 48% | P1 |
| chopin_op28_no20 | PianoCoRe | 48 | 44% | P3 (chords) |
| beethoven_op27_no2_mv1 | PianoCoRe | 99 | 41% | P1 |
| debussy_l136_no6 | PianoCoRe | 143 | 41% | P1 |
| Albéniz, Iberia 8 El polo | PianoCoRe | 761 | 39% | P2 |
| chopin_op10_no11 | PianoCoRe | 306 | 38% | P3 (spread chords) |

Some of these are caught by P3 on chords that are written as arpeggiated or rolled (Chopin Op.
10/11 is an étude in rolled chords). The proxy cannot see the roll there, so these are
over-counts.

**Hand words.** 116 of 802 pieces carry at least one hand word (ASAP 17, PianoCoRe 99). In 73
pieces at least one word names the other staff's hand: 284 contradicting words, e.g. "m.g."
written in the upper staff. There are also 28 sopra / sotto words. Most frequent texts: m.d.
212, m.g. 141, m.s. 74, R.H. 37, L.H. 35.

### Staff numbering: a separate coverage problem found on the way

Hand synchrony only compares staves 1 and 2. In this catalogue:

- 3 scores put every note on staves 3 and 4: ASAP `liszt_s162_no1`, PianoCoRe `liszt_s173_no7`
  and `albeniz_op47_mv1`.
- 14 PianoCoRe scores have a single staff after merging parts, e.g. the Minute Waltz and several
  Bach inventions. Their parts are separate, one staff each, and merge onto staff 1.
- 52 scores (50 PianoCoRe, 2 ASAP) have notes on other staves. In 43 of them, more than 10% of
  notes are on other staves, e.g. several Mozart sonatas numbered 1 and 3.
- In total, 25 scores give hand synchrony zero events, and more give only a partial set.

This is a silent gap in tier B for those pieces, not a staff-versus-hand question. On the 736
"clean" two-staff pieces, the at-risk numbers barely change: events at risk 3.6% pooled, median
piece 0.8%, pieces above 20% 3.7%.

### Can PianoVAM validate this? Yes, in principle; the labels are not downloaded

The PianoVAM v1.2 dataset card (`data/raw/pianovam/README.md`) describes:

- **`Fingering/`**: per-note hand (`L` / `R` / `Noinfo`) and finger labels for 106 of 107
  recordings. They were made automatically from MediaPipe hand landmarks matched to the MIDI.
  The card reports 19.9% `Noinfo`, and 99.2% correct hand on the labelled notes, against 1,800
  manually annotated notes.
- **`Fingering_GT/`**: manual hand and finger labels for 1,800 notes of 11 recordings.
- **`Handskeleton/`**: the 3D hand landmarks.

Our local copy has only `MIDI/`, `metadata.json`, `README.md` and part of `Audio/` (DATASETS.md,
D-10). None of the hand files is here, and PianoVAM has no scores. So the validation needs:

- the `Fingering/` TSVs (small; a data-engineer fetch);
- PianoVAM recordings of pieces that have a catalogue score;
- alignment of the practice-session MIDI (take splitting first).

Candidates by title (not checked note by note):

| PianoVAM recording | Catalogue score |
|---|---|
| Bach, Prelude I in C | bach_bwv846_prelude (ASAP) |
| Mozart, K.545 mvt 1 (3 takes) | mozart_k545_mv1 |
| Mozart, Sonata K.310 | mozart_k310_mv1 (ASAP) |
| Chopin, Grande Valse Brillante Op. 18 | chopin_op18 |
| Chopin, Nocturne Op. 9 No. 3 | Nocturne No. 3 in B major |
| Rachmaninoff, Moment musical Op. 16 No. 4 | rachmaninoff_op16_no4 |
| Rachmaninoff, Prelude Op. 32 No. 10 (2 takes) | rachmaninoff_op32_no10 (ASAP) |
| Rachmaninoff, Étude-tableau Op. 39 No. 8 (2 takes) | rachmaninoff_op39_no8 |
| Ravel, Jeux d'eau (4 takes) | Jeux d'eau |
| Ravel, Ondine | Gaspard de la nuit, Ondine |
| Ravel, Sonatine mvt 1 | Sonatine, 1. Modéré |
| Satie, Gymnopédie No. 1 (3 takes) | Gymnopédie 1 |
| Schumann, Fantasie Op. 17 (7 takes, movement unknown) | schumann_op17_mv1-3 |

That is about 20 recordings. Jeux d'eau and Ondine sit in the most affected composer group, so
they would test the proxies where they matter. With video hand labels, each proxy gets a
precision (the share of flagged notes actually played by the other hand) and a recall (the
share of real staff-hand mismatches flagged). That turns this proxy estimate into a measured
rate.

## Verdict (Provisional): pass for pooled hand synchrony; not validated

Pre-registered rule:

- median piece 0.9% of events affected (threshold 5%);
- 4.2% of pieces above 20% (threshold 10%).

Result: **pass**. Both hold within their bootstrap intervals (median [0.6%, 1.1%]).

What this supports: across the catalogue, staff-for-hand error can touch only a small share of
the onsets that hand synchrony averages. The robust spread it reports should be little affected
for most pieces.

What it does not support:

- **Per-hand feedback.** 5.2% of notes are at risk overall and 10-11% for Debussy and Ravel.
- **Hand synchrony in the tail.** In about 1 piece in 10, more than 11% of events are
  affected, and there the measure mixes hands.
- **Any claim that the proxy rate is the true rate.** It is not validated.

## Recommendations (not done here)

1. **Cheap hygiene in `control.hand_synchrony`.** Drop events whose notes are flagged P1 or P3,
   and report the number dropped. This is a proposal for the feature-engineer's code, not
   changed in this ticket. It removes the most likely misassigned events at a cost of at most
   2.3% of events (P1 flags 1.5% of events, P3 0.8%).
2. **Staff numbering (new defect).** Normalise the two staves of a merged piano part to 1 / 2
   (lowest two staff numbers, or by part order for one-staff-per-part scores), so that 25+
   catalogue pieces stop giving empty or partial hand synchrony. Belongs in `_score_utils` or
   the loaders.
3. **PianoVAM validation (new ticket).** Data-engineer fetches `Fingering/` and `Fingering_GT/`.
   Feature-engineer aligns the recordings above to their scores and measures proxy precision
   and recall and the true staff-hand mismatch rate.
4. **Per-hand feedback** stays off until (3) exists. The report already says nothing per hand.

## Threats to validity

- **The proxies are not ground truth.** Each can miss real cases and flag false ones:
  - P1 depends on engraving conventions. Voices renumbered mid-piece would inflate it.
  - P2 flags hand crossings in which each hand keeps its staff.
  - P3 flags rolled chords.
  - Pianists' own redistribution, which scores do not show, is invisible to every proxy.
- **PianoCoRe scores are user engravings of variable quality.** Proxies P1 and P3 respond to
  engraving choices, so PianoCoRe and ASAP numbers for the same piece can differ.
- **Folded scores.** Repeats are counted once. Hand synchrony runs on the unfolded performed
  path, so repeated sections weigh more there.
- **Events here come from the score.** Production pairs only matched notes, so the affected
  share among real events can differ slightly.
- **The catalogue** is weighted to pieces with many PianoCoRe references, which leans to
  popular repertoire.

## Audit (2026-09-29)

Auditor: eval-auditor. **Verdict: Confirmed with caveats.** The pre-registered rule gives
"pass", and the pass is robust to every over-count check below. But it is a pass *on the proxy*.
Against the engravers' own hand marks, the proxies flag most marked measures not at all. So the
true staff-hand mismatch rate is not bounded by these numbers, and the sentence "staff-for-hand
error can touch only a small share of the onsets" must be reworded (correction 1).

### What was checked

- **Pre-registration.** The section hash `14d27bb5...a93c54` recomputes from
  `docs/specs/correctness-validation.md` lines 229-264 (then end of file) and equals
  `artifacts/prereg_section.md`. It was written at 20:44:00 UTC and hashed at 20:44:06, before
  the script existed (first `Write` 20:48:44).
- **Exploration before the hash** (disclosed here, not in the README):
  - staff and voice counts on 14 random catalogue scores;
  - a grep of ASAP hand-word frequencies;
  - a check of partitura `Words`.
  No proxy rate was computed. Hand words are not part of the verdict rule.
- **Reproduction.** A rerun to scratch reproduces `per_piece.csv` and `per_composer.csv`
  exactly (`per_piece` row order differs), 656 hand words, the verdict, and the median-piece
  CI. The pooled CIs differ in the 4th decimal, because the bootstrap draws rows in
  `as_completed` order: notes at risk [4.7, 5.7] in the rerun vs [4.7, 5.8] in the README. An
  independent recomputation of all proxies with the script's functions matches
  `ev_at_risk` and `n_events` for all 802 pieces.
- **Bootstrap unit.** Pieces, which is correct here.

### Findings

1. **Under-count: low recall against the engravers' hand marks.**
   - Setup: single-part scores, 68 pieces, 248 measures carrying a "contradicting" hand word
     (for example "m.g." on staff 1). The check takes the notes of the marked staff in that
     measure.
   - In 57% of those measures, no note is at risk. The median share is 0; the note-weighted
     share is 15%.
   - The same staff's piece-wide baseline has a median of 7.0%, so the proxies do not respond to
     marked hand swaps.
   - A likely reason: when a hand takes notes on the other staff while its own staff rests or
     holds, no proxy fires (no voice change, no crossing, no capacity breach).
   - Caveat: word placement was not verified by eye. Some words may be attached to the staff
     they sit next to rather than the one they govern.
   - Other expected under-counts: Bach-style polyphony, where an inner voice on the upper staff
     is taken by the left hand without crossing, and pianists' own redistribution (already
     listed in Threats).
2. **Over-count checks: "pass" survives them all.** Event shares over the 777 pieces with events:

   | Variant | Median piece | Pieces > 20% |
   |---|---|---|
   | As run | 0.88% | 4.4% |
   | P1 dropped for voices split heavily across staves (> 25% of the voice's notes, and at least 20, on the minority staff; 17.8% of P1 notes, 39 pieces) | 0.85% | 3.5% |
   | P3 dropped on chords with a MusicXML `<arpeggiate>` mark (2,248 of 24,297 P3 notes) | 0.83% | 4.1% |
   | Both | 0.79% | 3.2% |
   | P2 loose instead of strict | 1.36% | 7.2% |

   - The heavy split voices are ambiguous in direction. They include cross-staff figures played
     by one hand, where P1 is right (as in Op. 10/1). They also include figures shared between
     the hands with each note on its hand's staff, where P1 is wrong (for example Mendelssohn
     Op. 19/1). They may also include voice-number collisions after merging parts.
   - Marked rolls are a small part of P3 overall. They explain the Chopin Op. 10/11 case
     entirely: 116 affected events fall to 1 without the arpeggiated chords, which confirms the
     README's remark. Unmarked rolls cannot be seen.
   - Ornaments: grace notes are dropped and trills are single notes, so no ornament effect is
     expected.
3. **DF-09 (odd staff numbering) adds noise to the tail and removes notes. It does not change
   the verdict.**
   - The 25 zero-event pieces have a NaN share. They drop out of the median but count as "not
     above 20%" in the tail share, whose denominator is 802 instead of 777. Corrected, the tail
     share is 4.38% instead of 4.24%.
   - The 52 pieces with notes on other staves have a median of 4.5% and 13.5% above 20%. They
     put 7 pieces into the 34-piece tail. Three are Mozart scores numbered 1/3 whose "events"
     are 2-13 stray staff-1/staff-2 coincidences:
     - K.331/2: 2 events, 100% affected;
     - K.281/3: 5 events, 100%;
     - K.311/3: 13 events, 31%.
   - In three-staff scores (Albéniz *Iberia*, Ravel, Debussy *Préludes*), staff-3 notes are
     excluded from every proxy. This is exactly where staff-to-hand mapping is most ambiguous, so
     these pieces under-count.
   - On single-part pieces with no other-staff notes (723 with events): median 0.79%, 3.3%
     above 20%. With at least 40 events (746 pieces): median 0.93%, 3.9% above 20%. So DF-09
     slightly inflates the tail through tiny denominators, and under-counts three-staff
     passages. Per-event pooled shares barely move.

### Required corrections (append as "Post-audit corrections"; do not edit the sections above)

1. Reword the verdict:
   - "pass for pooled hand synchrony *on the score proxies*";
   - the proxies miss most engraver-marked hand swaps (finding 1), so the true rate is
     unbounded until the PianoVAM check.
   - Replace "staff-for-hand error can touch only a small share of the onsets" with "the
     proxies flag only a small share of the onsets".
2. Add the over-count sensitivity table (finding 2), including the P2-loose row. It supports the
   remark that P3 over-counts on rolled chords.
3. Compute the tail share over pieces with at least one event (4.38%). Add a minimum-events
   filter or report `n_events` next to tail pieces, so that DF-09 pieces with 2-13 stray events
   are not read as affected (finding 3).
4. Make the bootstrap reproducible: sort `pp` by `piece_id` before `summarise`.
5. Add the hand-word recall check to the PianoVAM ticket as a free, score-only precursor: once
   PianoVAM hand labels exist, report proxy precision and recall on the marked measures too.
