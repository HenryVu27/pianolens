# Alignment validation on (n)ASAP (F-01)

Measured 2026-09-27 by `feature-engineer`. Code: `src/pianolens/align/`. Rerun:

```
uv run python -m pianolens.align.validate --workers 12 [--nakamura <AlignmentTool dir>]
uv run python -m pianolens.align.validate --beat-check-below 0.9   # adds the beat check
```

Outputs (gitignored): `data/interim/alignment_validation/per_performance.csv`, `per_composer.csv`.

## Method

- Aligner: `pianolens.align.align` = parangonar 3.3.3 `DualDTWNoteMatcher` (ornament handling
  on) on a partitura 1.9.0 unfolded score.
- Repeats: every repeat path of the MusicXML score is enumerated (`get_paths`). The 6 paths whose
  note count is closest to the performance's are aligned, and the one with the highest match
  ratio 2·matches / (score notes + performed notes) is kept. 197 of 242 ASAP scores have one path;
  the largest has 2048.
- Ground truth: each performance's `note_alignment.tsv` (equal to the match file where both are
  complete). Metrics: match precision / recall / F1 over (score note, performed note) pairs,
  insertion F1, deletion F1, and the fraction of performed notes given exactly the right status.
- All 1066 performances were attempted; 1063 scored. 3 fail because the ground-truth TSV does not
  exist (Beethoven 17-2 KaszoS10, 29-4 DANILO01, Schubert D.935/1 Lisiecki10M).

**Caveat.** (n)ASAP alignments were produced semi-automatically with the same family of matchers
(Peter et al., TISMIR 2023). The `robust` column is the dataset's own flag for reliable ones.
Agreement with them is agreement with a strong reference, not with hand-checked truth.

## Results per composer (match F1, mean over performances)

| Composer | n | n robust | F1 mean | F1 median | F1 robust only | Insertion F1 | Deletion F1 | Align time median (s) |
|---|---|---|---|---|---|---|---|---|
| Bach | 169 | 169 | 0.988 | 0.994 | 0.988 | 0.890 | 0.712 | 1.3 |
| Balakirev | 10 | 10 | 0.972 | 0.972 | 0.972 | 0.924 | 0.806 | 32.3 |
| Beethoven | 268 | 198 | 0.970 | 0.989 | 0.984 | 0.796 | 0.705 | 15.6 |
| Brahms | 1 | 1 | 0.972 | 0.972 | 0.972 | 0.727 | 0.565 | 7.5 |
| Chopin | 289 | 269 | 0.978 | 0.991 | 0.986 | 0.929 | 0.831 | 7.7 |
| Debussy | 3 | 2 | 0.960 | 0.980 | 0.982 | 0.881 | 0.769 | 5.8 |
| Glinka | 2 | 0 | 0.884 | 0.884 | n/a | 0.844 | 0.656 | 6.1 |
| Haydn | 44 | 31 | 0.990 | 0.992 | 0.993 | 0.909 | 0.889 | 16.4 |
| Liszt | 121 | 68 | 0.920 | 0.939 | 0.951 | 0.807 | 0.670 | 12.9 |
| Mozart | 16 | 14 | 0.992 | 0.994 | 0.994 | 0.834 | 0.859 | 13.0 |
| Prokofiev | 8 | 0 | 0.964 | 0.962 | n/a | 0.885 | 0.825 | 10.5 |
| Rachmaninoff | 8 | 4 | 0.947 | 0.966 | 0.997 | 0.860 | 0.656 | 3.2 |
| Ravel | 22 | 2 | 0.886 | 0.912 | 0.983 | 0.821 | 0.761 | 13.6 |
| Schubert | 61 | 32 | 0.951 | 0.977 | 0.970 | 0.829 | 0.776 | 14.4 |
| Schumann | 28 | 24 | 0.938 | 0.959 | 0.953 | 0.694 | 0.667 | 19.3 |
| Scriabin | 13 | 10 | 0.782 | 0.961 | 0.961 | 0.736 | 0.657 | 27.4 |
| **All** | **1063** | **834** | **0.964** | **0.987** | **0.981** | **0.855** | **0.752** | **11.3** |

Pooled over notes (not performances), match F1 is 0.952. 81% of performances have F1 ≥ 0.95;
90% of the robust ones do. The fraction of performed notes with exactly the right status is 0.960.

**Runtime.** Median 11.3 s, 90th percentile 33 s, maximum 202 s (Schubert D.935/3, which has
2048 repeat paths, six of them aligned). About 310 performed notes per second, on one core of
this M4 Pro. These times come from the run with Nakamura running beside it on 12 workers. An
earlier run without Nakamura, same code except for the stale-path bug below, had a median of
6.8 s.

## What the low scores are

- **The ground truth is wrong, not us (checked).** For the 31 single-path performances with
  F1 < 0.9, both alignments were checked against ASAP's hand-made downbeat annotations. The test:
  does each matched note's performed onset fall inside its measure's annotated span, give or take
  0.25 s? Ours is more consistent in 16 cases, the ground truth in 5, and they tie in the rest.
  - Scriabin Sonata 5 Ko07M: ground truth 0.18, ours 0.99.
  - Liszt Sonata Yeletskiy05M: ground truth 0.74, ours 1.00.
  - Liszt Transcendental Etude 4 LeeE04M: ground truth 0.93, ours 0.99.
  - The ten Liszt Etude 4 performances at F1 ≈ 0.86 have ground-truth consistency ≈ 0.986 and
    ours ≈ 0.997. There, our lower F1 is disagreement inside correct measures (octave
    doublings, repeated notes), not lost alignment.
- **Cases where ours is worse on the beat check.** Ravel Alborada (4 performances, ours ≈ 0.973,
  ground truth ≈ 0.997) and La campanella Ali03 (0.953 vs 0.998). Fast repeated notes: DTW slips
  locally.
- **Unchecked failures, all flagged non-robust.** Chopin Scherzo 20 Wong04M (F1 0.00), Ballade 1
  MunA19M (0.01), Liszt Sonata Zuber07M (0.00) and Scriabin ChernovA06M (0.00). The beat check
  could not run because the annotation's score and performance downbeats are not one-to-one.
  Until checked, treat these as possible real failures.
- **Repeat choice.** On the 99 performances of multi-path scores, the chosen variant equals the
  ground-truth variant in 86. The 13 misses are Schubert D.935/3 (8), Schumann Arabeske (2) and
  Kreisleriana 2 (3). Forcing the ground-truth variant raises F1 by 0.01 to 0.06 in 10 of them.
  Two cases are bad either way:
  - Schubert D.935/3 SunY08M: F1 0.02 even with the ground-truth variant. The performer's
    structure matches no score path, and the ASAP beat annotation is flagged not aligned.
  - Kreisleriana 2 JohannsonP03: F1 0.46 even with the ground-truth variant.
- Da-capo scores (Beethoven 7-3, 11-3, 28-2) scored 0.38 to 0.65 in the first run. The cause was
  a partitura trap: `get_paths` reuses stale segments, so a second call returned 4 paths instead
  of 70. Fixed by rebuilding segments on every call. After the fix they align normally (run 2
  above).

## Cross-check: Nakamura's HMM aligner

The tool (AlignmentTool_v190813) builds on macOS arm64 with its own `compile.sh` in about 15 s,
with no errors. Wrapper: `pianolens.align.nakamura`. It cannot follow repeats the way partitura
does, so it was run only on single-path scores.

- It crashed (SIGABRT / SIGSEGV) on 85 of 964 of these performances.
- On the 879 where it ran, mean match F1 is 0.954 for Nakamura and 0.968 for DualDTW. Medians are
  0.990 for Nakamura and 0.988 for DualDTW. Median time is 5.4 s for Nakamura and 10.1 s for
  DualDTW.
- On the 719 robust single-path performances: DualDTW 0.982, Nakamura 0.968. DualDTW scores
  higher on 40% of them.
- Nakamura's worst composer means are Chopin 0.938, Debussy 0.802 and Mozart 0.954, against
  0.978, 0.960 and 0.994 for DualDTW.
- Reading: the two aligners are about equally good on typical performances. Nakamura has more
  catastrophic failures and crashes. DualDTW stays the default.

## Consequences for Phase 1

- Use the alignment as is for ordinary performances. Median F1 is 0.987.
- Before building features on a performance, sanity-check it. Match ratio below about 0.8, or
  many insertions, should raise a flag, not be trusted silently.
- Deletion F1 (0.75) is the weakest number: which exact score note was skipped is often
  ambiguous (repeated notes, octave doublings). Tier A "missed note" labels should be reported
  per bar, not per note, with that uncertainty in mind.
