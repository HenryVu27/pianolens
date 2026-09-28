# R-06 frozen head-to-head: SyMuPe EncDec vs Pianist Transformer (2026-09-28)

Folder: `experiments/2026-09-27-R-06-expression-model-h2h/` (prereg sha in artifacts/prereg_sha256.txt,
first 160 README lines). Results in README; raw tables artifacts/results/*.csv, summary.json.

## Running the models (own venvs under envs/, gitignored)
- symupe-venv: py3.12, `uv pip install -e envs/SyMuPe` (commit 13cc57d) **plus numba** (undeclared dep).
  torch 2.14 / transformers 5.x work. MPS crashes (float64 tensor in prepare_sequence): CPU only.
- pt-venv: py3.11, torch 2.7.1, transformers 4.54.0, miditoolkit, partitura 1.7; repo on sys.path.
  HF id `yhj137/pianist-transformer-rendering`. Scoring on MPS is 3x faster and matches CPU (3e-5);
  generation on MPS is 2x SLOWER than CPU (HF generate overhead).
- Adapters read interchange npz from prepare.py (`pianolens.models.expression_io`): score arrays +
  perf arrays in score order, spq_cond / vel_cond, time sigs. Build MIDI in memory; don't round-trip files.
- SyMuPe teacher forcing: gen.prepare_sequence(seq=perf_seq, task="performance", score_seq=score_perf)
  then model(enc=init_seq, dec=target, labels=target, dec_score_tokens=score_seq); logits dict per key;
  mask ids < tok.zero_token. Perf seq: encode_performance(note_alignment=arange) -> add_pedal_tokens ->
  remove_pedal_tokens -> sort_tokens(by_time=False). Grid quantisation can permute notes: use
  score_seq.token_to_note (also in generation; r.score_seq.token_to_note is not usable).
- PT labels: sorted perf onsets assigned in score order, ms ticks, pedal binarised at 64; restrict
  softmax to config.valid_id_range per slot (8 tokens/note). SFT held-out ASAP = testset/score/0..22.mid
  (identified note-for-note; list in prepare.py). Seed-42 reshuffle on our (n)ASAP does NOT reproduce it.
- Overlap: PERiScoPe v1.0 metadata (HF SyMuPe/PERiScoPe) has no split column; split unpublished.
  WoO 80, D960 (all mvts) and D783 no.15 have no aligned pair -> unseen by SyMuPe; not in ASAP -> unseen
  by PT SFT. Vienna 4th excerpt is Schubert D783 no.15 (not Traeumerei).

## Findings
- Unseen pieces: quality tie (composite r 0.39 each) but paired per-target/per-work CIs differ:
  log IOI SyMuPe +0.059 [0.017,0.101], art PT +0.053 [0.015,0.094], D960 mv3 PT +0.038 [0.007,0.069].
  SyMuPe's big lead on ASAP/Vienna is exposure. Chosen SyMuPe via tie-break (+0.0075, two-way CI
  [0.0027,0.0129]; carried by 10 ms jitter only). Audit: Confirmed with caveats; lead keeps PT as secondary.
- c2 vs synthetic deadpan on P = FAIL (CI wholly < 0.5), not inconclusive. H1b preview: timing falsif.
  level both; velocity falsif. SyMuPe, inconclusive PT (0.30); r2 0.35-0.37 (shape ok, amplitude off).
- Post-audit text fixes applied 2026-09-28 (README "Post-audit corrections"). Lesson: trial analyze runs
  on partial outputs count as "results seen"; log them and word deviations accordingly.
- Teacher-forced likelihood of both prefers deadpans over every expert (AUC 0.00) while catching
  jitter perfectly -> do not use raw likelihood as quality/typicality; needs a predictability correction.
- Mean-curve centered R² on unseen: velocity 0.10-0.30, timing ~0 (reliability 0.93).
- Cost: PT fp32 AdamW 4096 tok batch 1/2/4 = 8.9/15.4/27.3 GB (MPS); SyMuPe 256 notes batch 32/128 =
  6.5/23 GB RSS (CPU). Generation K=8: SyMuPe 37 ms/note, PT 212 ms/note CPU (idle) = 5.7x; under 4 jobs 80 vs 168 = 2.1x.
- Run 3 PT generation workers in parallel over the same dir (script skips existing outputs).
