---
name: run-experiment
description: Procedure for any experiment in PianoLens, from hypothesis to audited verdict. Use before training or evaluating any model, running any statistical analysis that supports a claim, or writing a number into EXPERIMENTS.md.
---

# Run an experiment

## 1. Pre-register (before running anything)

Create `experiments/<id>/README.md`. The id is `<YYYY-MM-DD>-<ticket>-<slug>`, for example
`2026-09-28-R-01-percepiano-factors`. Fill in:

```
# <title>
Ticket: <id>    Hypothesis: <H# from the plan>    Status: Provisional
## Question
## Falsified if
<the exact criterion, copied or refined from the plan's hypothesis table>
## Data
<datasets + versions from DATASETS.md, filters, counts>
## Splits
<leave-piece-out folds (required for quality claims); leave-performer-out; seeds>
## Baselines
<trivial baseline(s); ceiling (rater parity if per-rater labels exist)>
## Method
## Command
<exact uv run ... command(s)>
```

Do not change "Falsified if" after you see results. If it was wrong, say so in a new section.

## 2. Run

- Put code in `src/pianolens/` (reusable) or `experiments/<id>/run.py` (one-off). Configs go in
  `configs/` or next to `run.py`.
- Outputs go to `experiments/<id>/artifacts/`, which is gitignored. Keep tables small enough to
  copy into the README.
- Record the git commit or a diff hash, the seeds, and the wall time.

## 3. Report (append to the README)

```
## Results
<table: baseline | model | ceiling, with 95% bootstrap CIs, per split type>
## Verdict (Provisional)
<supported / not supported / inconclusive, against the pre-registered criterion>
## Threats to validity
<leakage risks, small n, transcribed-MIDI noise, renderer effects>
```

Add a row to `EXPERIMENTS.md`.

## 4. Audit

Ask the lead to dispatch `eval-auditor` on the experiment folder. Only the auditor changes the
verdict to Confirmed, or sends it back with required fixes.

## Common failure modes

- **Piece leakage.** Segments of the same piece end up in train and test. PercePiano segments
  overlap in bars across performers.
- **Label leakage.** Features computed from data that includes the test fold (e.g. an expert mean
  curve that contains the test performance).
- **Reporting the best layer or seed chosen on test.** Choose on validation.
- **Comparing numbers across different splits** as if they were comparable.
