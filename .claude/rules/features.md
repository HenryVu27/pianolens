---
paths:
  - "src/pianolens/align/**"
  - "src/pianolens/features/**"
  - "tests/align/**"
  - "tests/features/**"
---

# Alignment and feature rules

- Alignment comes before any feature. Every feature function takes (Score, Performance, Alignment)
  and must behave sensibly when notes are unmatched: skip them and count them, never crash.
- Build on partitura (`musicanalysis`, performance codec) and parangonar. Wrap them; do not
  reimplement them.
- **Tiers** (plan, section 3, Phase 1):
  - A: correctness
  - B: control
  - C: shaping
  - D: interpretation, relative to a reference set
- Every feature must satisfy all of these:
  - **Localizable:** it returns per-bar (or per-beat) values as well as a summary.
  - **Documented:** its docstring gives the definition, the unit, and the citation from
    `docs/research/2026-09-27-landscape.md`.
  - **Tempo-aware:** timing features are normalized by local beat period, since timing scales
    with tempo (TISMIR 2026).
  - **Velocity-aware:** melody lead is always reported alongside the velocity difference
    (Goebl 2001).
- **Separate intent from noise.** Tempo is a smooth component plus a residual. Tier B reads the
  residual; tier C reads the smooth part.
- Units: seconds, beats, MIDI velocity (0-127). Log-ratios for tempo and articulation. Say which
  in the output column name, e.g. `ioi_ratio_log`, `vel_midi`.
- Test each feature on a synthetic performance whose value you know. Examples: a perfectly
  deadpan performance has zero jitter; a performance with injected ±20 ms noise has jitter of
  about 20 ms.

## partitura traps (promoted from data-engineer memory, 2026-09-27)

- **Performance note arrays extend `duration_sec` to the sustain-pedal release by default.**
  PianoLens types store key-down durations (see `performance_from_partitura`). Articulation
  features must use key-down durations. Pedal effects are measured separately from pedal events.
- **`note_array(include_metrical_position=True)` crashes with numpy 2.** Compute metrical position
  from `measures` and `onset_beat` instead, or check whether a newer partitura fixes it.
- **Scores must be parts-merged and unfolded** before alignment ids such as `n22-1` resolve. Use
  `score_from_partitura` on a merged, unfolded part.

## Repeats and the performed score (from F-01, 2026-09-27)

- **Downstream code uses the score returned by `align_performance`**, not the score from a loader.
  - Loaders (ASAP) expand every repeat, but performers skip some: at least 13 of 99 ASAP
    performances of scores with repeats do.
  - `align_performance` picks the repeat path the performer actually took. Alignment ids refer to
    that path.
- **DualDTW does not handle repeats.** Unfold to a single path first; `align()` does this.
- **Unfolding an already unfolded part crashes.**
- **`get_paths` returns different results on a second call unless the section markers are
  rebuilt.** This silently broke the da capo sonatas once. See the feature-engineer memory,
  `partitura-parangonar-traps.md`.
- **`parangonar.RepeatIdentifier` is broken with numpy 2.** Don't use it.
- **Missed notes are reported per bar, not per note.** Deletion F1 is 0.75, so per-note "missed"
  labels are unreliable when the same pitch repeats or appears in octaves.
- **The Nakamura aligner is an optional cross-check only.** It crashes on about 9% of
  performances. Our aligner is the default.
