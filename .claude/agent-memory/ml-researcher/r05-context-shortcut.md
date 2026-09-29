# R-05 H8 recording-context shortcut (2026-09-28, Provisional: supported)

Folder `experiments/2026-09-28-R-05-context-shortcut/` (build.py, common.py, reachability.py,
analyze.py). Prereg header sha256 7add1490...f0c5 (hash = text before "\n## Results").

## Reusable cache
- `artifacts/embeddings.npz`: 1,500 MAJEPPA clips (250/level, seed 0, score_id present, >= 10 s),
  first 30 s of Transkun MIDI, S-02 render -> 4 contexts (clean, phone_room, recital_phone,
  concert_hall), MuQ mean||std pooled: `l912` (N,4,2048) f32, `layers` (N,4,14,2048) f16.
  `sample.csv` (labels, context_real), `excerpt_stats.csv` (note_rate, vel stats).
  Any "does MuQ encode X on MAJEPPA renders" question can start from it.
- Build: 1.46 s/clip for 4 contexts (MuQ-bound, batch of 4 x 30 s on MPS), 36 min total.
- Context params seeded by sha256("R-05|clip|ctx"); AAC round trip via ffmpeg at 24 kHz.

## Numbers
- Beginner vs advanced AUC: matched mean 0.870, confounded 0.943 (+0.073), confounded->permuted
  test 0.730 (+0.214), swapped 0.475, random-context control +0.002; context decode 0.997.
- Teachers vs beginners carries it (0.778 -> 0.958). Symbolic excerpt stats alone 0.760: the
  rendered MIDI carries repertoire difficulty, so matched 0.87 is NOT a skill accuracy.
- Observed Spearman CC vs M scores 0.80; CI half-width ~0.018.

## Gotchas
- zsh does not word-split `$a` in `for a in "--x 1"`: argparse gets one arg and fails silently
  under 2>/dev/null. Write each command out.
- np.savez of an object array of ids needs allow_pickle on load; use `.astype(str)`.
- reachability.py is slow (200 sims x 400 boots x ~10 AUCs per case: ~20 min/case while MuQ
  runs). Start it early or cut N_SIM.
- MAJEPPA recording_id ~ unique per clip (1,392 for 1,500); piece+recording components = pieces.
