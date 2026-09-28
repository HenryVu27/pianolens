"""Inject realistic playing mistakes into an aligned performance, with exact ground truth.

Used for the synthetic mistake set (D-08, ``data/processed/mistakes_v1``) that validates the
tier A correctness labels (F-02), and shared with the degradation generator (S-01), which will
use the timing / velocity perturbations.

Entry point: :func:`perturb` ``(performance, alignment, spec, seed) -> (performance, labels)``.

Mistake model
-------------
Loosely follows the MAESTRO-E generator (Chou et al., "Detecting Music Performance Errors with
Transformers", AAAI 2025; code ``ben2002chou/CocoChorales-E_MAESTRO-E``,
``mistake_augmentations.py``, read 2026-09-27). What that generator does:

* picks ``ceil(lambda * n_notes)`` notes (± half of that, uniformly), ``lambda`` 0.03-0.05;
* per picked note, an integer "screwup type" uniform in 0..15: 0 drops the note, 1 changes its
  pitch, 2 plays a wrong pitch briefly and then the right one, 3 adds an extra note, 4-15 only
  shift timing. Types 1-15 also shift the onset by N(0, 300 ms);
* pitch offsets are ``int(N(0, 1))`` redrawn until non-zero and not a pitch of the next chord,
  so almost always ±1 or ±2 semitones;
* extra notes start uniformly between the note and the next onset, with the note's duration
  scaled by a Gamma factor (mean 1).

Differences here, and why:

* The mistake count is exact: ``round(rate * n_eligible)``, split between wrong pitch, extra and
  missed by ``spec.mix`` (largest remainder). Fixed counts make per-rate evaluation clean.
* Wrong pitch keeps the note's timing, duration and velocity. Offsets are ±1 / ±2 semitones
  (neighbour keys) plus a small share of octave errors (±12), which MAESTRO-E does not model but
  which are a known real error (a hand landing in the wrong octave). The new pitch may not be a
  pitch already sounding in the same chord.
* Extra notes are modelled as neighbour-key slips: a key next to a played note (±1 or ±2
  semitones) caught at almost the same time, short and soft. Onset offset, duration and velocity
  ratio come from ``spec``. They never overlap a sounding note of the same pitch.
* Missed notes are biased to inner voices of chords and to fast passages, where real players
  drop notes, instead of being uniform. The top voice is never favoured.
* No timing shift is attached to mistakes: S-01 wants timing and correctness varied separately.
  Global timing jitter, velocity jitter and a tempo scale are separate ``spec`` fields.
* Only notes the alignment labels ``match`` are perturbed. Existing insertions / deletions
  (real mistakes, or ground-truth noise) are carried into the labels with ``injected=False``.
  ``interpolated`` notes (not played) are never touched.

Only use performances with exact timing (``disklavier`` / ``sensor`` provenance): the output is
tagged ``provenance="synthetic"`` with the source provenance in ``meta``.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pianolens.data.types import ALIGNMENT_DTYPE, PEDAL_DTYPE, Alignment, Performance

__all__ = [
    "LABELS",
    "MistakeLabels",
    "MistakeSpec",
    "chord_clusters",
    "load_mistake_set",
    "perturb",
]

LABELS: tuple[str, ...] = ("correct", "extra", "wrong_pitch", "missed")
"""Ground-truth labels. ``correct`` / ``extra`` / ``wrong_pitch`` label performed notes,
``missed`` labels score notes."""

_PIANO_LO, _PIANO_HI = 21, 108
_EXACT_PROVENANCE = ("disklavier", "sensor")


@dataclass(frozen=True)
class MistakeSpec:
    """Parameters of :func:`perturb`. Times in seconds, velocities in MIDI units.

    Attributes:
        rate: injected mistakes per eligible (``match``) performed note.
        mix: share of (wrong_pitch, extra, missed) among injected mistakes.
        wrong_pitch_deltas: ``(semitone offset, weight)`` pairs for wrong pitches.
        extra_pitch_deltas: ``(semitone offset, weight)`` pairs for extra notes, relative to the
            played note they slip from.
        extra_onset_sec: uniform range of the extra note's onset relative to that note.
        extra_duration_sec: uniform range of the extra note's key-down duration.
        extra_velocity_ratio: uniform range of extra velocity / anchor velocity.
        missed_inner_weight: sampling weight multiplier for inner chord notes (not the highest or
            lowest pitch of a chord of 3+ notes).
        missed_fast_weight: multiplier for notes in fast passages.
        fast_ioi_sec: a chord is "fast" when a neighbouring chord onset is closer than this.
        chord_window_sec: onsets within this window of a chord's first onset form one chord.
        timing_jitter_sd_sec: s.d. of Gaussian onset noise added to every note (0 = off).
        velocity_jitter_sd: s.d. of Gaussian velocity noise added to every note (0 = off).
        tempo_scale: multiplies every time (onsets, durations, pedal); >1 is slower.
    """

    rate: float = 0.05
    mix: tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3)
    wrong_pitch_deltas: tuple[tuple[int, float], ...] = (
        (-1, 0.3), (1, 0.3), (-2, 0.15), (2, 0.15), (-12, 0.05), (12, 0.05),
    )  # fmt: skip
    extra_pitch_deltas: tuple[tuple[int, float], ...] = (
        (-1, 0.35), (1, 0.35), (-2, 0.15), (2, 0.15),
    )  # fmt: skip
    extra_onset_sec: tuple[float, float] = (-0.02, 0.06)
    extra_duration_sec: tuple[float, float] = (0.03, 0.15)
    extra_velocity_ratio: tuple[float, float] = (0.4, 0.8)
    missed_inner_weight: float = 2.0
    missed_fast_weight: float = 2.0
    fast_ioi_sec: float = 0.15
    chord_window_sec: float = 0.05
    timing_jitter_sd_sec: float = 0.0
    velocity_jitter_sd: float = 0.0
    tempo_scale: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(eq=False)
class MistakeLabels:
    """Exact ground truth for a perturbed performance.

    Attributes:
        notes: one row per note of the perturbed performance, in its note order. Columns:
            ``performance_id`` (note id), ``label`` (``correct`` / ``extra`` /
            ``wrong_pitch``, or the source alignment's label for anything else, e.g.
            ``interpolated``), ``score_id`` (score note it realises or was meant to realise;
            ``""`` for extra notes), ``injected`` (True if this module made the mistake),
            ``original_pitch`` (pitch before perturbation; the anchor's pitch for extras),
            ``anchor_id`` (for injected extras: the played note it slipped from).
        missed: one row per missed score note: ``score_id``, ``injected``,
            ``original_performance_id`` (the dropped performed note; ``""`` for natural misses).
        alignment: ground-truth alignment of the perturbed performance in the partitura
            convention (a wrong pitch is a deletion plus an insertion).
        spec: the spec used.
        seed: the seed used.
    """

    notes: pd.DataFrame
    missed: pd.DataFrame
    alignment: Alignment
    spec: MistakeSpec
    seed: int

    def counts(self, injected: bool | None = True) -> dict[str, int]:
        """Number of notes per label (``injected=None`` counts natural and injected)."""
        n = self.notes if injected is None else self.notes[self.notes["injected"] == injected]
        m = self.missed if injected is None else self.missed[self.missed["injected"] == injected]
        out = {lab: int((n["label"] == lab).sum()) for lab in ("extra", "wrong_pitch")}
        out["missed"] = len(m)
        return out


def chord_clusters(onsets: np.ndarray, window: float) -> np.ndarray:
    """Chord index of each onset: sorted onsets within ``window`` of a chord's first onset share
    an index. Returned in the input order."""
    order = np.argsort(onsets, kind="stable")
    out = np.empty(len(onsets), dtype=int)
    cid, start = -1, -np.inf
    for i in order:
        if onsets[i] - start > window:
            cid += 1
            start = onsets[i]
        out[i] = cid
    return out


def _split_counts(total: int, mix: tuple[float, ...]) -> list[int]:
    w = np.asarray(mix, dtype=float)
    w = w / w.sum()
    raw = w * total
    base = np.floor(raw).astype(int)
    rest = total - base.sum()
    for i in np.argsort(-(raw - base), kind="stable")[:rest]:
        base[i] += 1
    return base.tolist()


def _draw_delta(rng: np.random.Generator, deltas: tuple[tuple[int, float], ...]) -> int:
    d = np.array([x for x, _ in deltas])
    p = np.array([w for _, w in deltas], dtype=float)
    return int(rng.choice(d, p=p / p.sum()))


def _missed_weights(notes: np.ndarray, idx: np.ndarray, chord: np.ndarray,
                    spec: MistakeSpec) -> np.ndarray:
    """Sampling weight for dropping each candidate note (index into ``notes``)."""
    onsets = notes["onset_sec"]
    pitches = notes["pitch"]
    n_chords = chord.max() + 1 if len(chord) else 0
    first = np.full(n_chords, np.inf)
    np.minimum.at(first, chord, onsets)
    hi = np.full(n_chords, -1)
    lo = np.full(n_chords, 999)
    size = np.zeros(n_chords, dtype=int)
    np.maximum.at(hi, chord, pitches)
    np.minimum.at(lo, chord, pitches)
    np.add.at(size, chord, 1)
    gaps = np.diff(first)
    near = np.full(n_chords, np.inf)
    if n_chords > 1:
        near[:-1] = gaps
        near[1:] = np.minimum(near[1:], gaps)
    c = chord[idx]
    inner = (size[c] >= 3) & (pitches[idx] < hi[c]) & (pitches[idx] > lo[c])
    fast = near[c] < spec.fast_ioi_sec
    return np.where(inner, spec.missed_inner_weight, 1.0) * np.where(
        fast, spec.missed_fast_weight, 1.0
    )


def _same_pitch_busy(notes: np.ndarray, pitch: int, t0: float, t1: float) -> bool:
    """True if a note of ``pitch`` sounds anywhere in [t0, t1] (MIDI cannot overlap them)."""
    m = notes["pitch"] == pitch
    on = notes["onset_sec"][m]
    off = on + notes["duration_sec"][m]
    return bool(np.any((on <= t1) & (off >= t0)))


def _tick_map(notes: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    names = notes.dtype.names or ()
    if "onset_tick" not in names or len(notes) < 2:
        return None
    o = np.argsort(notes["onset_sec"], kind="stable")
    return notes["onset_sec"][o].astype(float), notes["onset_tick"][o].astype(float)


def _to_ticks(tmap: tuple[np.ndarray, np.ndarray], t: np.ndarray) -> np.ndarray:
    sec, tick = tmap
    slope = (tick[-1] - tick[0]) / max(sec[-1] - sec[0], 1e-9)
    out = np.interp(t, sec, tick)
    out = np.where(t > sec[-1], tick[-1] + (t - sec[-1]) * slope, out)
    out = np.where(t < sec[0], tick[0] + (t - sec[0]) * slope, out)
    return np.round(out)


def perturb(
    performance: Performance,
    alignment: Alignment,
    spec: MistakeSpec | None = None,
    seed: int = 0,
    *,
    require_exact_timing: bool = True,
) -> tuple[Performance, MistakeLabels]:
    """Inject mistakes (and optional timing / velocity noise) into an aligned performance.

    Args:
        performance: the original performance; its note ids must be unique.
        alignment: its note alignment (ground truth preferred: (n)ASAP, Vienna, Batik).
        spec: what to inject; default ``MistakeSpec()`` (5% mistakes, equal mix).
        seed: seed of the ``numpy`` random generator; same inputs and seed give the same output.
        require_exact_timing: refuse performances whose provenance is not disklavier / sensor.

    Returns:
        ``(perturbed_performance, labels)``. The perturbed performance keeps every original note
        id (a wrong-pitch note keeps its id); extra notes get ids ``xN``. Its id is
        ``<performance_id>#r<rate>-s<seed>``, provenance ``synthetic``, and
        ``meta["perturbation"]`` records the spec, seed and source provenance.
    """
    spec = spec or MistakeSpec()
    if require_exact_timing and performance.provenance not in _EXACT_PROVENANCE:
        raise ValueError(
            f"provenance {performance.provenance!r}: mistakes need exact timing "
            "(disklavier / sensor); pass require_exact_timing=False to override"
        )
    rng = np.random.default_rng(seed)
    notes = performance.notes
    # widen the id field so extra-note ids ("x123") always fit
    width = max(int(notes.dtype["id"].itemsize // 4), 2 + len(str(len(notes))))
    notes = notes.astype(np.dtype(
        [(n, f"U{width}" if n == "id" else notes.dtype[n]) for n in notes.dtype.names]
    ))  # fmt: skip
    ids = notes["id"].astype(str)
    if len(set(ids.tolist())) != len(ids):
        raise ValueError("performance note ids are not unique")
    pos = {pid: i for i, pid in enumerate(ids.tolist())}

    # label of every performed note according to the source alignment
    perf_label = np.full(len(notes), "unaligned", dtype=object)
    perf_score = np.full(len(notes), "", dtype=object)
    for lab, sid, pid in alignment.pairs.tolist():
        if pid and pid in pos:
            perf_label[pos[pid]] = lab
            perf_score[pos[pid]] = sid
    eligible = np.flatnonzero(perf_label == "match")

    n_total = int(round(spec.rate * len(eligible)))
    n_wrong, n_extra, n_missed = _split_counts(n_total, spec.mix)
    chord = chord_clusters(notes["onset_sec"].astype(float), spec.chord_window_sec)

    # missed: weighted draw without replacement
    missed_idx = np.array([], dtype=int)
    if n_missed and len(eligible):
        w = _missed_weights(notes, eligible, chord, spec)
        k = min(n_missed, len(eligible))
        missed_idx = rng.choice(eligible, size=k, replace=False, p=w / w.sum())
    free = np.setdiff1d(eligible, missed_idx)

    # wrong pitch: uniform over the rest; skip notes with no legal new pitch
    wrong: dict[int, int] = {}
    for i in rng.permutation(free):
        if len(wrong) >= n_wrong:
            break
        chord_pitches = set(notes["pitch"][chord == chord[i]].tolist())
        for _ in range(20):
            new = int(notes["pitch"][i]) + _draw_delta(rng, spec.wrong_pitch_deltas)
            t0 = float(notes["onset_sec"][i])
            t1 = t0 + float(notes["duration_sec"][i])
            if (_PIANO_LO <= new <= _PIANO_HI and new not in chord_pitches
                    and not _same_pitch_busy(notes, new, t0, t1)):  # fmt: skip
                wrong[int(i)] = new
                break
    for i, new in wrong.items():
        notes["pitch"][i] = new

    # extra: neighbour-key slips next to a played note that is neither dropped nor wrong
    anchors = np.setdiff1d(free, np.fromiter(wrong, dtype=int, count=len(wrong)))
    kept = np.setdiff1d(np.arange(len(notes)), missed_idx)
    extra_rows: list[np.void] = []
    extra_anchor: list[str] = []
    extra_orig_pitch: list[int] = []
    tmap = _tick_map(performance.notes)
    for i in rng.permutation(anchors):
        if len(extra_rows) >= n_extra:
            break
        a = notes[i]
        chord_pitches = set(notes["pitch"][chord == chord[i]].tolist())
        for _ in range(20):
            pitch = int(a["pitch"]) + _draw_delta(rng, spec.extra_pitch_deltas)
            onset = max(0.0, float(a["onset_sec"]) + rng.uniform(*spec.extra_onset_sec))
            dur = float(rng.uniform(*spec.extra_duration_sec))
            busy = _same_pitch_busy(notes[kept], pitch, onset, onset + dur) or any(
                r["pitch"] == pitch
                and r["onset_sec"] <= onset + dur
                and r["onset_sec"] + r["duration_sec"] >= onset
                for r in extra_rows
            )
            if _PIANO_LO <= pitch <= _PIANO_HI and pitch not in chord_pitches and not busy:
                row = a.copy()
                row["pitch"] = pitch
                row["onset_sec"] = onset
                row["duration_sec"] = dur
                ratio = rng.uniform(*spec.extra_velocity_ratio)
                row["velocity"] = int(np.clip(round(int(a["velocity"]) * ratio), 1, 127))
                row["id"] = f"x{len(extra_rows)}"
                if tmap is not None:
                    t = _to_ticks(tmap, np.array([onset, onset + dur]))
                    row["onset_tick"] = t[0]
                    row["duration_tick"] = max(1, t[1] - t[0])
                extra_rows.append(row)
                extra_anchor.append(str(a["id"]))
                extra_orig_pitch.append(int(a["pitch"]))
                break

    # assemble the perturbed note array
    out = notes[kept]
    if extra_rows:
        out = np.concatenate([out, np.array(extra_rows, dtype=notes.dtype)])
    src_idx = np.concatenate([kept, np.full(len(extra_rows), -1)])
    out, src_idx = _jitter(out, src_idx, spec, rng, tmap)
    order = np.argsort(out["onset_sec"], kind="stable")
    out, src_idx = out[order], src_idx[order]

    # ground truth
    wrong_set = set(wrong)
    extra_pos = {r["id"]: k for k, r in enumerate(extra_rows)}
    rows = []
    for r, si in zip(out, src_idx, strict=True):
        pid = str(r["id"])
        if si < 0:
            k = extra_pos[pid]
            rows.append((pid, "extra", "", True, extra_orig_pitch[k], extra_anchor[k]))
            continue
        lab = perf_label[si]
        if si in wrong_set:
            rows.append((pid, "wrong_pitch", perf_score[si], True,
                         int(performance.notes["pitch"][si]), ""))  # fmt: skip
        elif lab == "match":
            rows.append((pid, "correct", perf_score[si], False, int(r["pitch"]), ""))
        elif lab in ("insertion", "unaligned"):
            rows.append((pid, "extra", "", False, int(r["pitch"]), ""))
        else:
            rows.append((pid, str(lab), perf_score[si], False, int(r["pitch"]), ""))
    note_df = pd.DataFrame(
        rows,
        columns=["performance_id", "label", "score_id", "injected", "original_pitch",
                 "anchor_id"],  # fmt: skip
    )
    missed_rows = [(str(perf_score[i]), True, str(ids[i])) for i in sorted(missed_idx.tolist())]
    missed_rows += [
        (sid, False, "") for lab, sid, _ in alignment.pairs.tolist() if lab == "deletion"
    ]
    missed_df = pd.DataFrame(missed_rows,
                             columns=["score_id", "injected", "original_performance_id"])

    gt_pairs = []
    dropped = {str(ids[i]) for i in missed_idx}
    wrong_ids = {str(ids[i]) for i in wrong}
    for lab, sid, pid in alignment.pairs.tolist():
        if pid in dropped:
            gt_pairs.append(("deletion", sid, ""))
        elif pid in wrong_ids:
            gt_pairs.append(("deletion", sid, ""))
            gt_pairs.append(("insertion", "", pid))
        else:
            gt_pairs.append((lab, sid, pid))
    gt_pairs += [("insertion", "", r["id"]) for r in extra_rows]
    new_id = f"{performance.performance_id}#r{spec.rate:g}-s{seed}"
    gt = Alignment(np.array(gt_pairs, dtype=ALIGNMENT_DTYPE), alignment.score_id, new_id,
                   ground_truth=True, source=f"{alignment.source}+perturb")  # fmt: skip

    pedal = performance.pedal.copy()
    if spec.tempo_scale != 1.0:
        pedal["time_sec"] = pedal["time_sec"] * spec.tempo_scale
    meta = {
        **performance.meta,
        "perturbation": {"spec": spec.to_dict(), "seed": seed,
                         "source_performance_id": performance.performance_id,
                         "source_provenance": performance.provenance},  # fmt: skip
    }
    new_perf = dataclasses.replace(
        performance, performance_id=new_id, provenance="synthetic", notes=out, pedal=pedal,
        meta=meta,
    )
    return new_perf, MistakeLabels(note_df, missed_df, gt, spec, seed)


def _jitter(out: np.ndarray, src_idx: np.ndarray, spec: MistakeSpec, rng: np.random.Generator,
            tmap: tuple[np.ndarray, np.ndarray] | None) -> tuple[np.ndarray, np.ndarray]:
    """Global timing / velocity perturbations (for S-01); a no-op with the default spec."""
    changed = False
    if spec.timing_jitter_sd_sec > 0:
        out["onset_sec"] = np.maximum(
            0.0, out["onset_sec"] + rng.normal(0.0, spec.timing_jitter_sd_sec, len(out))
        )
        changed = True
    if spec.tempo_scale != 1.0:
        out["onset_sec"] = out["onset_sec"] * spec.tempo_scale
        out["duration_sec"] = out["duration_sec"] * spec.tempo_scale
        changed = True
    if spec.velocity_jitter_sd > 0:
        v = out["velocity"] + rng.normal(0.0, spec.velocity_jitter_sd, len(out))
        out["velocity"] = np.clip(np.round(v), 1, 127)
    if changed and tmap is not None:
        on = _to_ticks(tmap, out["onset_sec"].astype(float))
        off = _to_ticks(tmap, (out["onset_sec"] + out["duration_sec"]).astype(float))
        out["onset_tick"] = on
        out["duration_tick"] = np.maximum(1, off - on)
    return out, src_idx


# --------------------------------------------------------------------------- stored set

_NOTE_COLS = ("onset_sec", "duration_sec", "pitch", "velocity", "id")


def load_mistake_set(
    root: Path | str = "data/processed/mistakes_v1",
) -> tuple[pd.DataFrame, Any]:
    """Load a stored mistake set built by ``scripts/build_mistake_set.py``.

    Returns ``(index, get)``: ``index`` is ``index.csv`` (one row per perturbed performance,
    column ``key``), and ``get(key)`` returns ``(Performance, MistakeLabels)`` for one row.
    ``MistakeLabels.alignment`` is not stored and is rebuilt from the labels.
    """
    root = Path(root)
    index = pd.read_csv(root / "index.csv", keep_default_na=False)
    notes = pd.read_parquet(root / "notes.parquet")
    missed = pd.read_parquet(root / "missed.parquet")
    pedal = pd.read_parquet(root / "pedal.parquet")
    spec_json = json.loads((root / "spec.json").read_text())
    by_note = dict(tuple(notes.groupby("key", sort=False)))
    by_miss = dict(tuple(missed.groupby("key", sort=False)))
    by_pedal = dict(tuple(pedal.groupby("key", sort=False)))
    rows = index.set_index("key")

    def get(key: str) -> tuple[Performance, MistakeLabels]:
        r = rows.loc[key]
        nd = by_note[key]
        width = max(2, int(nd["id"].str.len().max()))
        dt = np.dtype([("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                       ("velocity", "i4"), ("id", f"U{width}")])  # fmt: skip
        na = np.empty(len(nd), dtype=dt)
        for c in _NOTE_COLS:
            na[c] = nd[c].to_numpy()
        pd_rows = by_pedal.get(key)
        ped = np.empty(0 if pd_rows is None else len(pd_rows), dtype=PEDAL_DTYPE)
        if pd_rows is not None:
            for c in PEDAL_DTYPE.names:
                ped[c] = pd_rows[c].to_numpy()
        spec = MistakeSpec(**{k: _tuplify(v) for k, v in spec_json["specs"][str(r["rate"])]
                              .items()})  # fmt: skip
        perf = Performance(
            performance_id=key, piece_id=r["piece_id"], performer_id=r["performer_id"],
            provenance="synthetic", notes=na, pedal=ped, dataset="mistakes_v1",
            meta={"source_performance_id": r["performance_id"], "rate": float(r["rate"]),
                  "seed": int(r["seed"]), "xml_score": r["xml_score"]},  # fmt: skip
        )
        lab = nd[["performance_id", "label", "score_id", "injected", "original_pitch",
                  "anchor_id"]].reset_index(drop=True)  # fmt: skip
        mdf = by_miss.get(key)
        mdf = (pd.DataFrame(columns=["score_id", "injected", "original_performance_id"])
               if mdf is None else mdf[["score_id", "injected", "original_performance_id"]]
               .reset_index(drop=True))  # fmt: skip
        gt = labels_to_alignment(lab, mdf, str(r["score_id"]), key)
        return perf, MistakeLabels(lab, mdf, gt, spec, int(r["seed"]))

    return index, get


def labels_to_alignment(notes: pd.DataFrame, missed: pd.DataFrame, score_id: str,
                        performance_id: str) -> Alignment:
    """Rebuild the ground-truth ``Alignment`` from label tables (wrong pitch = del + ins)."""
    pairs = []
    for pid, lab, sid in notes[["performance_id", "label", "score_id"]].itertuples(index=False):
        if lab == "correct":
            pairs.append(("match", sid, pid))
        elif lab == "wrong_pitch":
            pairs.append(("deletion", sid, ""))
            pairs.append(("insertion", "", pid))
        elif lab == "extra":
            pairs.append(("insertion", "", pid))
        else:
            pairs.append((lab, sid, pid))
    pairs += [("deletion", sid, "") for sid in missed["score_id"]]
    return Alignment(np.array(pairs, dtype=ALIGNMENT_DTYPE), score_id, performance_id,
                     ground_truth=True, source="mistakes_v1")  # fmt: skip


def _tuplify(v: Any) -> Any:
    if isinstance(v, list):
        return tuple(_tuplify(x) for x in v)
    return v
