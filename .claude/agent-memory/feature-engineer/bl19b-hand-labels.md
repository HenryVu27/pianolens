---
name: bl19b-hand-labels
description: BL-19b (2026-10-10) staff-vs-hand on PianoVAM video labels - practice-session take splitting traps, catalogue Italian Concerto trap, parangonar duplicate matches, measured rates and where they live
metadata:
  type: project
---

BL-19b (`experiments/2026-10-10-BL-19b-hand-proxies/`, Confirmed with caveats, prereg anchor sha256 a2b4f597...0577).
Related: [[bl19-bl20-density-staff]], [[bl23-df09-df10]], [[partitura-parangonar-traps]].

## Practice-session take splitting (`pianolens.data.session_takes`)
- Pauses do not split PianoVAM sessions: many have no gap > 4 s, and restarts happen after short
  hesitations. Plain Smith-Waterman also fails: it swallows restarts as gap runs (a Schumann
  session came out as one take, onsets 0-1922, consensus 0.82). Cut the path at > 6 consecutive
  one-sided steps and re-search the leftovers; that gave 15 takes there.
- Wrong-score null: null takes always have 0 exactly matched onsets (partial matches score +1, so
  they still reach dp 30). QC used: Dice >= 0.6, exact share >= 0.3, consensus >= 0.5. 518 of
  560 real takes and 0 of 6 null takes pass.
- SW vs parangonar disagreements are mostly SW's event grouping: a split chord gives an unpaired
  event, or an onset +-1 away. The consensus-only subset gave the same mismatch rate.
- parangonar DualDTW on cropped score arrays returned duplicate matches: one performed note
  matched to two score notes, 194 rows in 146k. Drop every row in such a group.
- A synthetic score array for DualDTW needs onset_div/duration_div, onset_beat/duration_beat,
  onset_quarter/duration_quarter, pitch, voice, id and is_grace, or it raises `no field is_grace`.

## Catalogue trap
- Both "Italian Concerto" scores in the app catalogue are the 2nd movement only (49 bars of 3/4,
  1,085 notes): ASAP `asap:Bach/Italian_concerto` and PianoCoRe `bach_bwv971`. The
  `pianovam.SCORE_CANDIDATES` comment that calls the PianoCoRe file the whole concerto is wrong.
  The PianoVAM mvt 1 and mvt 3 recordings have no score. Reported to the lead, not fixed.

## Measured (summary.json, per_piece.csv, posthoc.json in the artifacts)
- STAFF mismatch is 6.66% [3.51, 9.00] pooled and 3.35% for the median piece; the label noise e
  is 0.76%; the pitch split gives 23.4%. VOICE (modal staff of the voice) does no better.
- The tail pieces are Tombeau Toccata 21.8%, Appassionata i 13.8%, Debussy Mouvement and
  Schumann Op. 17 i 11.1%.
- BL-19 at-risk flags: precision 42%, recall 39%, lift 6.3. P1 has the highest precision (57%).
- The audit corrected my reading. Mismatches are SYSTEMATIC per score note: on another pass a
  mismatch recurs at the same note 90% of the time, against a base rate of 6.8%. They are not
  single-note redistribution. In Op. 17 i (a PianoCoRe engraving), mm. 41-49 put voice 2 on
  staff 1 and the left hand plays it (m. 48: all 148 labelled notes are L in 7 of 7 recordings);
  P1 cannot see this. My run-length check in performance order could not show it, because the
  other hand's notes interleave and break the runs. Use recurrence at the same score note plus
  concentration per measure instead.
- In the Tombeau Toccata, 86% of mismatches are same-pitch hand alternation; outside those
  notes the rate is 4.5%.
- D2 passed exactly at the bar (3/30) and is not stable: it fails if any one sub-20% piece is
  dropped, and the bootstrap gives P(pass) 0.59. Before registering a share-of-units-above-X
  rule on about 30 units, compute which counts pass.
- Audit verdict: Confirmed with caveats, 2026-10-10. In posthoc.py, sort with kind="stable"
  (n_runs was 4,251 or 4,252 depending on chord-tie order; 4,249 with the stable sort).
- On the matched opening notes with manual labels, the video disagrees with manual 1.7% (9/532)
  and STAFF disagrees with manual 0.3% (2/636), so the noise floor may be above 0.76% there.
- `Noinfo` is 17.6% of matched notes, 24% on at-risk notes against 17% on the rest.
