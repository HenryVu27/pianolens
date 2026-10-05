---
name: r11-teacher-annotations
description: R-11 tonebase teacher-annotation pilot - gate/(a)/(b)/(c) results and where they live, interim layout, PianoCoRe score/reference quirks hit while running (staffs, empty measures, target grid), tooling traps
metadata:
  type: project
---

R-11 status (2026-10-05): gate passed, (a)-(c) run, eval-auditor: Confirmed with caveats; six README text fixes applied (Post-audit corrections). Audit lessons are in rules/experiments.md (gain sweep before registering a removal test, count null positions, check MusicXML hands, honest deviation timing, one-row strata).
Prereg section sha256 390903481b69...29ca; inputs + encoder B hashes in
`experiments/2026-10-05-R-11-teacher-annotations/artifacts/prereg_sha256.txt`.
Numbers: `artifacts/gate.json`, `a_summary.json`, `a_rows.csv`, `b_summary.json`, `c_summary.json`;
README Results section has the tables. **Why:** keep the next session from recomputing.

Layout (tonebase-derived content only in gitignored `data/interim/tonebase_annotations/`, BL-29):
PROTOCOL.md v1.2, scores/, pages/, encoder_A/ (rows, barmaps, operationalisation_A.csv),
encoder_B/ (NOC only, blind). Code: run.py (gate, c, drivers), part_a.py, part_b.py.

Traps hit (how to apply: check these before any new note-level analysis on PianoCoRe):
- Refined score MIDI: every note staff 0, upbeat padded to a full measure, repeats unfolded.
  Staffs must come from the MusicXML (`PianoCoRe-1.0-raw-midi.zip`, prefix `PianoCoRe/raw/`),
  unfolded with `unfold_part_maximal`, matched by onset+pitch with a constant offset search
  (NOC +6 q, 1222/1243; ETU +4 q, all; WAL 0, all). The waltz MusicXML is two single-staff
  parts (staff = part index), and its upper part holds some LH chords (WAL-A-031 lost its
  reference set).
- `load_pianocore_references` bar_starts skip measures with no notes (waltz 137 bars vs 140
  measures) and start bar 1 at the first note (upbeat). Map measure -> report bar by start
  beat (fit beat = a*quarter + b from the cache), never `m - 1`.
- `target_from_notes` builds its grid from the notes' span; a performance missing its first or
  last notes makes `interpret` raise "grids differ". Build the target on `refs.grid` /
  `refs.pos_grid` with `beat_grid_curves` (reproduces `target_from_references` tiers exactly).
- `_interpretation_section(ReportInputs(ap=None), target, refs.exclude([pid]), None, cfg, nb)`
  is the report's tempo/loudness per-bar tier path (about 2.5 s per call on the nocturne).
- `pgrep -f "run.py b"` in a wait loop matches the wait loop itself; use the Monitor tool or
  grep the log for a completion marker. Use `PYTHONUNBUFFERED=1` for progress logs.
- No pdf tools in the core env: `uv run --no-project --with pymupdf`; PDF text layer gives
  teacher text with positions, colour must be judged visually.

Gate lesson (protocol limitation): the vertical-gap anchor rule is ambiguous for text between
systems (near ties, local vs page-wide gap); 3 of 44 nocturne rows anchored differently,
including the primary timing row NOC-A-027.

Env: `.venv` core-only (no pyloudnorm); R-10 shares it, do not `uv sync` other extras.
See [[r08a-llm-phrase-pilot]] for blind-annotator hygiene.

Audit corrections to my own practice (2026-10-05): I wrote "fixed before reading the outcome" for
a fix made 8 s after a printed gate fail, and "only corrected numbers reported" for a fix that
moved an estimate by +0.084. **How to apply:** when a run prints a result and I then fix code,
report the pre-fix number and what the fix moved, and title deviation sections by when they were
written. My (a) verdict sentence also claimed a direction the intervals did not support.
