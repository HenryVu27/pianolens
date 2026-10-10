---
name: pianovam-hands
description: PianoVAM v1.2 hand labels (BL-24) - row-order trap vs partitura notes, matching key, counts, Noinfo, catalogue candidates, what the BL-19 validation still needs
metadata:
  type: project
---

Fetched 2026-10-10 at HF commit 1f039ab9 (same as the MIDI): `Fingering/` 106, `Fingering_GT/` 11,
`TSV/` 107; 43 MB total. `snapshot_download(..., revision=<sha>, allow_patterns=[...], local_dir=data/raw/pianovam)`.

Traps:
- `Fingering/` rows equal `TSV/` rows. They also match the MIDI one to one (count, onset within
  0.12 ms, velocity), but **chord order differs** from partitura's onset-sorted note array (94 of
  107 files). Never join by position; match by (pitch, onset within 0.5 ms). (onset_tick, pitch)
  is unique in every file; the smallest gap between distinct onsets is 1.04 ms.
- `TSV/` files start with a `# onset ...` comment header; `Fingering/` has a plain header.
  Read with `keep_default_na=False` so `Noinfo` stays a string.
- Fingering_GT = the first 150 TSV rows (300 for 2024-02-17_22-33-45), openings only.

Numbers (measured): 525,483 video notes, 80.1% L/R; 1,800 GT; 88.2% labelled, 99.2% hand,
95.7% hand+finger (= card). Left-Hand Concerto: 51 R of 7,142 labelled.
Noinfo is high in Minwook's recordings (Ballade 48%, Jeux d'eau 38%, Tombeau 36%, Op.101 37%).

Catalogue: `pianovam.SCORE_CANDIDATES` (title level): 44 recordings / 29 titles, 29 / 21 "unit".
BL-19 said "about 20" and missed Clair de lune, Fur Elise, Appassionata, Op.101/iv, Ballade 1,
Images Mouvement, Italian Concerto, Scriabin Op.19, B.150 waltz, Op.3/2, Clementi, Tombeau.

**Why:** BL-19 proxy validation (feature-engineer) builds on this.
**How to apply:** use `iter_hand_labels`; the validation still needs take splitting
(rach3_takes_bl16.md has a DP), alignment, movement resolution and a Noinfo policy.
PianoVAM piece ids are still `pianovam:` prefixed; canonical ids were left to the lead.
