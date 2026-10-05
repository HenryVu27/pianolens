---
name: r11-teacher-annotations-audit-facts
description: R-11 tonebase teacher-annotation pilot audit - prereg/order recipe, read-only rerun recipe, waltz MusicXML hand trap, nocturne null pool, (b) gain-sweep reachability, deviation-timing findings
metadata:
  type: project
---

R-11 audited 2026-10-05: Confirmed with caveats (labels stand, README text fixes 1-6).

- **Prereg hash**: python `t[:t.index('<!-- end of pre-registration')]` -> 390903481b69...29ca
  (same as artifacts/prereg_section.md). Inputs: `grep -v '^#' prereg_sha256.txt | grep -v
  README.md | shasum -a 256 -c` from repo root (18 OK incl. encoder B).
- **Transcripts**: author agent-a278c06becfb7bc29, encoder B agent-a25bcee0832fdf633 (session
  73c389dd). B blind check: grep tool-call inputs for the repo path (none). B's prompt
  contained the repo path once, in the "never access" line.
- **Read-only rerun**: wrapper that does `sys.path.insert(0, E); import run; run.ART = <scratch>`
  then run_gate / run_a / run_c / run_b_main. All 8 artifacts byte-identical. (b) about 13-20
  min.
- **Waltz hands**: the MusicXML is two single-staff parts. LH chords sit in part 1 in m29-33,
  45-49, 117-121 and 133-136 (62 notes; the lower part has 1 note/bar there). m1-4, 84-92 are
  genuinely RH-only. Heuristic fix: upper-part notes below MIDI 70 in those measures go to
  staff 2. Then WAL-A-031 r 0.176, WAL-A-023 0.692->0.588, WAL-A-055 0.644->0.521; pooled
  0.598 [0.471, 0.714].
- **Nocturne null pool**: 38 measures, 21 annotated, cadenza m33-38 excluded, 15 left. Dropped
  rows' r with their few nulls: 005 0.0, 021 0.833, 040 0.0, 044 0.0. Wide pool (only the
  row's own window excluded): NOC mean 0.450, pooled 0.589.
- **(b) reachability**: gain sweep (degradation scaled by g on vel/onset deltas; `interpret`
  with NOTABLE_Q only, flag = dev_rms > dev_rms_q). g=1 reproduces the author's hits exactly.
  Only ETU-A-014 (0.95) and NOC-A-027 (0.75) are reachable at g=3. Window too_flat/extreme
  tiers changed 0/117.
- **Deviation timing**: the gate bar-map fix came 8 s after a printed gate_pass False (the README
  said "before"). B-sensitivity first run 0.504 (7 rows) -> 0.588 after the set fix moved
  NOC-B-038 (r 0).
- Licence BL-29: the audit text must carry ids and numbers only; never quote encoder notes or
  teacher text.
