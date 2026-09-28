# D-10 skill control check (2026-09-27)

Spec: `docs/specs/skill-control-check.md`. Outputs: `data/interim/skill_control_d10/`.

## MAJEPPA traps
- Score MIDIs: no staff (all 0) and playback-shortened durations (x0.95 or -1 tick). F-04 hand
  sync is empty and even runs are 0 unless `majeppa.prepare_aligned(ap, score_id)` runs after
  `align_performance` (align re-reads the MIDI, so fix the *aligned* score, not the loaded one).
- Onset keys: partitura onset_quarter == tick / ticks_per_beat for these MIDIs (round 1e-3).
- `score_coverage >= 0.85` is not a quality gate: 28% of the D-10 set is still match ratio < 0.8.
  Suspect alignments also poison LOO consensus (R2 -170 in the pilot): pick references
  from trusted alignments only.
- Recording context tracks level (virtuoso = all concert; teachers = demos). The pooled skill
  effect (~0.75x) vanishes in practice/performance-only clips. Always stratify by context.
- Transcriber is Transkun (paper). Build: 16 min / 8 workers for 1,604 perfs.

## Transcription noise pairs
- PianoCoRe duplicates with an ASAP `lead_performance` (or reverse) = same performance,
  Disklavier vs transcription: 59+3 Aria-AMT, 6 Transkun. PianoCoRe's ASAP copies are trimmed
  by a few notes: match by name + note count (2%) + length (10 s), not MD5.
- Transkun local onset error robust SD 9.3 ms, velocity slope 0.64 / residual 9 MIDI;
  feature-level timing change ~1%; tier A error rate 0.039 -> 0.080.

## PianoVAM / Rach3
- PianoVAM: HF PianoVAM/PianoVAM_v1, `snapshot_download(allow_patterns=["MIDI/*",...])`,
  6.2 MB; CC BY-NC-SA; no scores. Audio + Disklavier MIDI -> ideal amateur noise floor (BL-13).
- Rach3: GitHub raw per-file download from the tree API list; names end in `mi.mid`; Hanon
  score is the whole book (22k notes) so no alignment; score-free stream proxy in
  `scripts/check_rach3_hanon_d10.py`. Instrument unstated -> tagged `sensor` provisionally.
- `timeout` does not exist on this Mac (zsh); do not use it in commands.
