# feature-engineer memory

Index. One line per note; details in topic files beside this one. Settled facts belong in
`.claude/rules/` or `.claude/skills/`, not here.

- [partitura-parangonar-traps.md](partitura-parangonar-traps.md) - API traps: grace fields,
  repeats, stateful get_paths, unfold-twice crash, load_match tuple, Nakamura tool build/format.
- [nasap-alignment-facts.md](nasap-alignment-facts.md) - (n)ASAP GT quirks and F-01 measured
  alignment accuracy / runtime.
- [correctness-and-mistakes.md](correctness-and-mistakes.md) - F-02/D-08: MAESTRO-E generator
  params, natural GT ins/del rates, parangonar ornament gap, missed-note ambiguity, measured F1.
- [tempo-model-f03.md](tempo-model-f03.md) - F-03 tempo model design (P-spline time map, 1.5-bar
  cutoff, robust scale bug), partitura tempo-mark facts, Op.10/12 numbers, residual is shared.
- [control-f04.md](control-f04.md) - F-04 tier B: design (LOO consensus noise, even runs, hand
  sync with dv covariate, 1.5-4 bar tempo instability, pedal blur rule), pickling trap, ranges.
- [shaping-f05.md](shaping-f05.md) - F-05 tier C: partitura feature-function wrapping (numpy-2
  crash), skyline-with-held-notes, bar-block CV design, duplicate-match trap, D.899/3 numbers.
- [f04b-validation.md](f04b-validation.md) - F-04b: DCML harmony GT on Batik (join recipe, key
  parsing), harmony rule now quarter window + functional templates (F1 0.761), pedal window kept.
- [batik-annotations.md](batik-annotations.md) - Batik DCML phrase/cadence CSVs (ids, labels,
  counts), MusicXML re-unfold with Jaccard 1.0, overlap with Vienna / ASAP and how to map.
- [phrase-f05b.md](phrase-f05b.md) - F-05b: proxy boundary F1, tempo R² proxy vs annotated,
  phrase_detail / clip_to_train, shaping-module monkeypatch trap, OMP threads.
- [f05c-cadence.md](f05c-cadence.md) - F-05c: cadence detector (held-out end F1 0.46 vs 0.29
  proxy) does not rescue tempo coherence; per-phrase concave excess vs shifted null does.
- [interpretation-f06.md](interpretation-f06.md) - F-06 tier D: frame/beat mapping, deadpan-safe
  typicality (log magnitude), LW mixed-scale trap, Horn vs sequential PA on real data, calibration.
- [report-f08.md](report-f08.md) - F-08 report: tier plumbing, correctness calibration on clean
  D-08 copies, too-flat ranking, timing-noise convention, sample results (a)-(d); F-08b
  provenance check (no Disklavier over-flagging) and recurring-error calibration (expert filter);
  F-08c per-bar expert check (q80/q99, matched capture) and no extras on transcribed input.
- [coherence-f05d.md](coherence-f05d.md) - F-05d: coherence min-length rule (n_written_bars,
  12 bars), extract override, R-04/R-09 impact, clip_to_train drift vs R-04 parquet.
- [takes-f07.md](takes-f07.md) - F-07 repeated takes: decomposition design, pooled-deviation R² = 0; audit: consistent part is piece-shared, not intent
  trap, PianoCoRe duplicate facts (tempo-r rule over-merges), BLAS oversubscription, H5 numbers.
- [f05e-llm-phrases.md](f05e-llm-phrases.md) - F-05e: LLM starts recover DCML concave_excess on
  average (-0.055; Romantic -0.12, n=3); short-phrase merge does not help; PianoCoRe score DTW.
- [compare-p01.md](compare-p01.md) - P-01 A/B clips: report-JSON-only coupling, window merge,
  isotonic time map, expert choice, excerpt render, tuplet tolerance, check biases, measured.
- [app-p02.md](app-p02.md) - P-02 local app: stdlib server + guards, subprocess worker and
  cancel, job hashing, catalog (584 PianoCoRe + 221 ASAP), clip/curve joining, measured runs;
  DF-05: code-version key, transcribed MIDI, wrong-piece stop (Dice 0.5), same-score ref trap.
- DF-06 (2026-09-29): pooled evenness = RMS of per-note scaled residuals (code intended,
  docstring fixed in control.py); pedal_blur_beats capped at 4 beats.
- [df02-llm-phrase-cache.md](df02-llm-phrase-cache.md) - DF-02: LLM phrase cache + loader,
  report disclosure, build protocol traps (prompt location, title-word removals), O-01 numbers;
  post-BL-17 disclosure (undetermined on sign disagreement, genre/recognition caveats).
- [bl19-bl20-density-staff.md](bl19-bl20-density-staff.md) - BL-20 density (aligner absorbs wrong keys equal to nearby pitch; window fine; F-02 repro) and BL-19 staff proxies (5.2% notes at risk; partitura Words has no staff; staff-numbering gap; PianoVAM Fingering/ upstream).
- [bl18-strong-tier.md](bl18-strong-tier.md) - BL-18: strong tier on transcribed input; cause (Aria missed
  notes), R1(2)+R2s implemented but overshoots (0.2%), R1(0) nearest nominal, dev LOO overstates.
- [bl23-df09-df10.md](bl23-df09-df10.md) - DF-10 pitch check is a no-op under the legacy ornament rule; DF-09 staff fix in `to_part` (25 -> 0 zero-event scores); BL-23 tight whitelist fails genuine-ornament check, post-pass `reassign=True` is default.
- [bl18b-interim-rules.md](bl18b-interim-rules.md) - interim R1(0) + passage-not-heard rule, BL-25 fast-repeat
  missed (score IOI < 100 ms), BL-20 fast-run wording; BL-18b FAIL on C4 = checker loss (DF-12).
- [df13-pairing-window.md](df13-pairing-window.md) - DF-13: only half the DF-12 unpaired loss is window-reachable (rest = aligner
  re-matching after injection); held-out FAIL (F1 clean pairs, Scarbo); relabel experts too.
