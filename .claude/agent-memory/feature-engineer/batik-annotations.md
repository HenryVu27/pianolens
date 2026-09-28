# Batik-plays-Mozart DCML annotations: facts (F-05b, 2026-09-27)

Shared note for any feature-engineer using Batik annotations (F-04b harmony, F-05b phrases).

- Per-note CSVs: `data/raw/batik_mozart/score_parts_annotated/<kvNNN_M>_spart_{annotated,
  cadence,harmony,phrases}.csv`. `id` = match-file score note id WITH repeat suffix (`n10-1`,
  `n10-2`): 100% of ids resolve in the match score (checked on kv331_1; all 36 load with 0
  missing phrase / cadence ids). The label sits on one note per onset (other rows NaN).
- `onset_beat` in the CSV equals the match score's `onset_beat` (partitura beats: 6/8 -> eighths).
- `phraseend`: `{` start, `}` end (placed on the cadential arrival note, not the last note),
  `}{` elision. Counts over 36 movements: 842 `{`, 842 `}`, 226 `}{` (rows, repeats counted).
- `cadence`: PAC 547, HC 410, IAC 75, EC 65, DC 47 (rows). `cadence_type` / `phrase_type` are
  integer codes of the same info.
- `xml_mn` uses `X1`, `X2` for volta bars; `mn` is the DCML measure count.
- The match-built score (loader) has NO markings (only notes, measures, time/key sigs). The
  edited MusicXML `scores_edited/<stem>.musicxml` has the same base ids (`n10`). D-11 loader:
  `bm.iter_aligned(musicxml_score=True)` / `bm.performed_score` / `bm.phrase_annotations`.
  Every match id resolves in 36/36 (id_coverage 1.0); Jaccard 1.0 in 35, kv281_3 0.9996 (the
  MusicXML has one extra note n636-1; F-05b's "1.0 for all" was rounded). Beats equal the match
  score except 9 notes of one fast run in kv331_1 (+0.25 quarter). The MusicXML has dynamics,
  tempo words, barlines, but NO slurs. `scores/` (unedited) also Jaccard 1.0 but
  has more repeat paths (slower).
- kv284_3 (variations) has many repeat paths: building a part for EVERY variant took >30 min
  and 18 GB; build only the 4 variants with note counts closest to the match score (30 s).
  Unfolded parts do NOT pickle (RecursionError), so cache variant strings, not parts.
- Batik has no K.310. Overlap with other sets: Vienna 4x22 K.331/1 (theme only, 22 pianists;
  its MusicXML numbers bars in performed order 1-36 and starts at Batik beat 0, so map by beat
  and renumber bars to written bars for CV folds); ASAP K.331/3 (1 perf), K.332/1 (4), /2 (2),
  /3 (3): map by (written measure number, beat in bar), offset 0, onset pitch-set match
  1.0 / 0.92 / 1.0, K.331/3 0.71.
