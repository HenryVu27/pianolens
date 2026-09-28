# R-09 (H4 coherence vs MAJEPPA skill) audit facts, 2026-09-28

- Prereg check: `head -191 README.md` sha c44a4b74...8517. It equals the ml-researcher Write at
  04:05:05Z (the transcript content has one extra trailing blank line, so whole-content sha differs;
  compare with `diff`, not the hash). Transcript: session 9591b65d.../subagents/agent-a5302547fe3cf0135.jsonl.
  Undisclosed after the prereg: a 2-score build test and an `analyze --boot 20` smoke test (crashed, empty).
- Rerun recipe: copy coherence.csv + noise_pairs.csv to scratch, sed `ART = HERE / "artifacts"` to the
  scratch path, run it as r9.py (~3 min at 2,000 boots). All 9 CSVs are byte-identical.
- MAJEPPA recording_id = one YouTube video (3,946 = 3,946); in A1, 388 rows = 388 recordings, so the
  "cluster" bootstrap is a row bootstrap. There is no channel/uploader field, so performer repeats cannot
  be checked. Piece clustering gives similar or narrower CIs.
- n_score_bars < 12: 24 gated rows, all Czerny Op. 101 (No. 70/13/12/47/71); 3 in A1 (two No. 70 child
  beginners, articulation R² -2.75, -0.96). They move articulation b 0.008 -> 0.003 and **create** the S8
  "coherence hurts" result (-0.061 -> -0.032 [-0.074, +0.012]).
- Pooled timing adv-beg +0.037 comes from teachers + virtuosos only (levels 1-4 alone: +0.018 [-0.020,
  0.062]). Context and the top levels are collinear, so "vanishes with context" is not identifiable.
  Ask the same question of any MAJEPPA A3-vs-A1 contrast (D-10 has the same structure).
- Power trap: the 97.5% half-widths (0.027 / 0.018) exceed the SESOI of 0.01, so falsification under a null
  had P of about 0.08 / 0.16. Check the reachability of each verdict branch in any SESOI design.
- Noise pairs: 65 pairs = 54 ASAP performances, 44 pieces. Aria within-piece rho: articulation 0.07,
  timing 0.89 (18 pairs, 7 pieces). Transkun n=6 bootstrap: timing 0.58 [0.00, 1.00], articulation
  0.88 [0.49, 1.00]. Such claims hold for Aria, not Transkun.
- A1 composition: 85/117/99/78/9/0 (levels 1-6); 57/106 pieces span only one level step.
