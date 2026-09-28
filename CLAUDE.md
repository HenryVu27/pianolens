# CLAUDE.md

## What this is

PianoLens is a research program and tool for scoring piano performances: note correctness first,
then control (evenness, stability), musical shaping, and interpretation relative to expert
performances. It is also a research bet: **piano performance quality is a low-dimensional function
of a low-dimensional, score-conditioned expressive space**, so interpretable features plus a small
model should match large audio foundation models. Every phase either tests that bet or builds on it.

Owner: Henry (vuducdung). Started 2026-09-27. Read `docs/plans/2026-09-27-research-program.md`
(the plan) and `docs/research/2026-09-27-landscape.md` (what is known, with sources) before any
non-trivial work.

## Why the bet is plausible (short version)

A piano note is fully specified by onset, velocity, offset, plus pedal curves. The hammer leaves
the string before the note sounds, so the player has no other control. MIDI + score is therefore a
near-complete description of a piano performance, unlike any other instrument. Expressive
deviations are hierarchical (global, phrase, beat, note, noise) and largely predictable from score
structure. Details and caveats are in the plan, section 1.

## Where knowledge lives

| What | Where |
|---|---|
| The plan: phases, hypotheses, success criteria | `docs/plans/2026-09-27-research-program.md` |
| Literature, datasets, models, products, with URLs | `docs/research/2026-09-27-landscape.md` |
| Work to do, claimed by agents | `WORKBOARD.md` |
| Every dataset: source, license, size, path, loader | `DATASETS.md` |
| Every experiment: hypothesis, result, verdict | `EXPERIMENTS.md` plus `experiments/<id>/README.md` |
| Decisions and why | `DECISIONS.md` |
| One-page summary of results and blockers | `STATUS.md` (the lead updates it) |
| Deferred work / known bugs | `BACKLOG.md`, `DEFECTS.md` |
| Path-scoped rules (load automatically) | `.claude/rules/*.md`: `data`, `features`, `experiments`, `audio`, `study` |
| Procedures | `.claude/skills/`: `run-experiment`, `fetch-dataset`, `gpu-job` |
| Role agents and their memories | `.claude/agents/*.md`, `.claude/agent-memory/<agent>/MEMORY.md` |

## Layout

```
src/pianolens/
  data/       dataset loaders; each returns the common types in data/types.py
  align/      score-to-performance note alignment (parangonar, Nakamura), error labels
  features/   tier A-D feature extractors (see rules/features.md)
  models/     expression models, quality/preference models
  eval/       splits, metrics, rater-parity, statistics
  audio/      transcription front end, loudness calibration (Phase 6)
  feedback/   LLM feedback layer (Phase 7)
tests/        pytest; fixtures are tiny and committed
scripts/      one-off CLI entry points (download_*.py, build_*.py)
configs/      experiment configs (yaml)
experiments/  one folder per experiment id, README.md committed, artifacts/ gitignored
data/         raw/ interim/ processed/, all gitignored; DATASETS.md is the manifest
study/        listening-study web app and protocol (Phase 3-4)
```

## Environment and commands

- Python 3.12 via uv. `uv sync` installs the core; `uv sync --extra audio --extra torch` adds the
  heavy stack. Run everything as `uv run ...`.
- Tests: `uv run pytest -q`. Lint: `uv run ruff check src tests`. Both must pass before a ticket
  is Done.
- **Machines.**
  - This Mac: M4 Pro, 48 GB RAM, about 150 GB free disk. All symbolic (MIDI) work runs here.
    MPS is fine for embedding extraction on small sets.
  - Henry's RTX 5080 box: 16 GB VRAM, Blackwell (sm_120), so it needs PyTorch built for CUDA
    12.8 or newer. Use it for transcription fine-tuning and model training. It is a separate
    machine: see the `gpu-job` skill.
  - Cloud GPU rental (Runpod, Lambda, Vast): only with Henry's approval. Log the spend in
    `DECISIONS.md`.
- **Disk budget:** raw data at most 60 GB on this Mac. MIDI corpora are small. Audio corpora
  (MAESTRO audio is about 120 GB) do not go on this Mac. They belong on the GPU box.

## Hard rules

1. **Hold out whole pieces.** Any claim about quality prediction reports leave-piece-out results.
   Leave-performer-out is reported separately and never substitutes for it.
   (Why: prior models collapse on unseen pieces. See the landscape doc, section 4.)
2. **No claim without a baseline and a ceiling.**
   - The baseline is the simplest sensible model.
   - For human-rated targets, the ceiling is rater parity: does the model agree with the panel
     mean as well as a typical held-out rater does?
3. **Every skill claim must be checked for context shortcuts, for audio *and* transcribed MIDI.**
   - Recording context (concert vs demo vs practice vs sight-reading) and recording quality
     correlate with skill.
   - A skill result that is not controlled for recording context (e.g. MAJEPPA `recording_type`)
     is not a skill result.
   - D-10 / R-09: tier B and coherence looked like they separated skill in pooled MAJEPPA data.
     Within matched contexts, no effect was shown from beginner to advanced-student levels; the
     top levels are confounded with concert/demo context (see DECISIONS 2026-09-28).
4. **Licenses.**
   - Nearly every dataset here is CC BY-NC(-SA/-ND). Research use only.
   - Never commit data or model weights trained on it to git.
   - Record each license in `DATASETS.md`.
5. **Never invent data or numbers.** If a figure is not measured in this repo or cited from a
   source in the landscape doc, do not write it.
6. **Stage and commit nothing unless Henry asks.** Stage explicit paths only. Never push.
7. **Agents do not spend money or touch credentials.** GPU rental, API keys and recruiting
   listeners are OWNER tickets.

## Agent roster

| Agent | Owns |
|---|---|
| `data-engineer` | Downloads, loaders, `DATASETS.md`, data QA |
| `feature-engineer` | Alignment, error labels, tier A-D features |
| `ml-researcher` | Experiments and models, Phases 2, 5 |
| `eval-auditor` | Adversarial review of every experiment verdict before it is marked Confirmed |
| `lit-scout` | Keeps the landscape doc current and verifies claims |
| `audio-engineer` | Phase 6: transcription and calibration |
| `study-designer` | Phases 3-4: perceptual and pairwise listening studies |

The lead session plans, dispatches and merges. Agents claim tickets from `WORKBOARD.md`, work only
inside the paths their ticket names, and update their memory before they finish.

## Scratch output

Scratch files never go in the repo. Use the absolute scratchpad path your session gives you. Shell
variables such as `$SP` do not persist between tool calls; an unexpanded one once created a literal
`$SP/` folder at the repo root.
