# R-06 (SyMuPe EncDec vs Pianist Transformer, frozen) audit facts, 2026-09-28

- Prereg: `head -n 160 README.md` hash d9ee9eac...; ml-researcher transcript
  agent-ad5684d873d90011a.jsonl (README Write 02:27:17 UTC, hash 02:27:32, P prepare 02:27:48).
  A trial analyze.py run at 02:44 printed summary tail BEFORE the generation-permutation fix (02:57)
  and A/V bootstrap change (02:51); README wrongly says "before any result was looked at".
- PERiScoPe v1.0 metadata csv (HF SyMuPe/PERiScoPe) lives in the session scratchpad as
  periscope_meta_v1.0.csv (46,473 rows, 38,077 with score). Empty `score` = unpaired. D960
  49/54/54/59 per mv, WoO 80 5 (all unpaired); D935/3 paired; D783 only no. 7 paired. Regex trap:
  `\W` does not match `_` in names like WoO_80. ASAP (242 folders) has no D960, no WoO 80.
- SyMuPe encoder masking verified: gen.mask_token_dims {'performance': [4,5,6,7]} (Velocity,
  TimeShift, TimeDuration, TimeDurationSustain); string task "performance" works as dict key.
- Rerun recipe: sed-copy analyze.py to scratch with HERE = experiment dir and RES = scratch;
  ~7 min at OMP 4; byte-identical. Adapters re-score an item dir into any --out (SyMuPe CPU,
  PT --device mps); 688 items took a few minutes each.
- Round trips: SyMuPe onset MAE up to 0.5 ms (1 tick = 1.04 ms at 120 qpm/480 tpq); PT duration
  differs up to 267 ms on D960 mv2 (authors' same-pitch cut), by design.
- Deadpan likelihood preference is robust: vel_cond ±12, 15% slower, per field, half-deadpans,
  and deadpan+noise (10 ms, 4 vel) still beats humans 91%. Mode vs typical set; not an artifact.
- c2 vs synthetic deadpan on P: CI fully below 0.5 -> pre-registered "fails" (README said
  inconclusive). Check reading rules against CI position, not just "straddles".
- Composite tie hides per-work/per-target sig. differences (D960 mv3 PT; log IOI SyMuPe; art PT).
- PercePiano D960 has overlapping 8- and 16-bar segmentations; same 12 performers across all
  passages of a work -> also bootstrap by performer and two-way.
- Tie-break jitter AUC diff is carried by jitT10 only (+0.037; 6% of renditions differ).
