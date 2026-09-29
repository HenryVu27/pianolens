"""Extra-note filter for transcribed phone / room audio (A-01b).

Transcribers add notes that were not played. On Henry's phone takes (A-01) 15-29% of score notes
came out as extras, many at G6 and above on a few fixed pitches with no plausible source note.
This module scores every transcribed note with features computed from the transcription alone
(no score, no ground truth), so it can run on any input:

* ``pitch``, ``velocity``, ``log_dur``;
* ``vel_rel_local`` (velocity minus the median of other notes within 1 s) and ``vel_rel_chord``
  (minus the loudest other note within 50 ms);
* ``n_chord`` (other notes within 50 ms), ``density`` (other notes within 1 s);
* ``harm_onset``: a note a harmonic interval below (``HARMONIC_STEPS``) starts within 50 ms;
  ``harm_sounding``: such a note is still sounding (key down) at this onset;
* ``gap_above`` (pitch minus the highest other pitch within 0.5 s) and ``gap_nearest`` (distance
  to the nearest other pitch within 0.5 s); NaN when no other note is that close;
* ``same_pitch_dt``: log seconds since the previous note of the same pitch (capped at 10 s);
* ``pitch_spike``: log of (count of this pitch + 1) over (mean count of the 4 neighbouring
  pitches + 1) in the whole file. High on a pitch that recurs far more than its neighbours, the
  "fixed pitch" signature of the A-01 takes.

:func:`label_false_extras` labels transcribed notes against ground-truth MIDI (unmatched at 50 ms
after removing a constant offset = false extra). :func:`rule_scores` is a transparent rule
baseline; :class:`ExtraNoteFilter` wraps a fitted classifier. Fitted models trained on
PianoVAM (CC BY-NC-SA 4.0) are data-derived and never committed; they live under ``data/``.

Validation (PianoVAM, leave-one-pianist-out) is in ``docs/specs/phone-audio-baseline.md``,
section A-01b. The filter is **off by default**: nothing in the report pipeline calls it unless
asked (``scripts/pianolens_report.py --filter-extras``).
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.audio.transcription import match_notes, note_f1

__all__ = ["FEATURES", "HARMONIC_STEPS", "ExtraNoteFilter", "filter_midi", "filter_notes",
           "label_false_extras", "note_features", "rule_scores"]  # fmt: skip

#: Semitone distances of partials 2-8 above a fundamental (rounded to equal temperament).
HARMONIC_STEPS = (12, 19, 24, 28, 31, 34, 36)

FEATURES = ["pitch", "velocity", "log_dur", "vel_rel_local", "vel_rel_chord", "n_chord",
            "density", "harm_onset", "harm_sounding", "gap_above", "gap_nearest",
            "same_pitch_dt", "pitch_spike"]  # fmt: skip


def _cols(notes) -> tuple[np.ndarray, ...]:  # noqa: ANN001 - structured array or DataFrame
    on = np.asarray(notes["onset_sec"], float)
    dur = np.asarray(notes["duration_sec"], float)
    p = np.asarray(notes["pitch"], int)
    v = np.asarray(notes["velocity"], float)
    return on, dur, p, v


def note_features(notes, chord_sec: float = 0.05, local_sec: float = 1.0,  # noqa: ANN001
                  reg_sec: float = 0.5, sound_back_sec: float = 4.0) -> pd.DataFrame:
    """Per-note features (rows in the input order), computed from the transcription alone."""
    on, dur, p, v = _cols(notes)
    n = len(on)
    out = {k: np.full(n, np.nan) for k in FEATURES}
    if n == 0:
        return pd.DataFrame(out)
    order = np.argsort(on, kind="stable")
    so, sd, sp, sv = on[order], dur[order], p[order], v[order]
    harm = np.array(HARMONIC_STEPS)
    counts = np.bincount(p.clip(0, 127), minlength=130).astype(float)
    res = {k: np.full(n, np.nan) for k in FEATURES}
    last_seen: dict[int, float] = {}
    lo_l = np.searchsorted(so, so - local_sec, "left")
    hi_l = np.searchsorted(so, so + local_sec, "right")
    lo_b = np.searchsorted(so, so - sound_back_sec, "left")
    for i in range(n):
        t, pi = so[i], int(sp[i])
        idx = np.arange(lo_l[i], hi_l[i])
        idx = idx[idx != i]
        d = so[idx] - t
        ch = idx[np.abs(d) <= chord_sec]
        rg = idx[np.abs(d) <= reg_sec]
        res["density"][i] = len(idx)
        res["n_chord"][i] = len(ch)
        res["vel_rel_local"][i] = sv[i] - np.median(sv[idx]) if len(idx) else 0.0
        res["vel_rel_chord"][i] = sv[i] - sv[ch].max() if len(ch) else 0.0
        res["harm_onset"][i] = float(np.isin(pi - sp[ch], harm).any()) if len(ch) else 0.0
        # still-sounding source: started up to sound_back_sec before (or within chord_sec after)
        # and key still down at this onset
        b = np.arange(lo_b[i], np.searchsorted(so, t + chord_sec, "right"))
        b = b[b != i]
        snd = b[so[b] + sd[b] >= t - chord_sec]
        res["harm_sounding"][i] = float(np.isin(pi - sp[snd], harm).any()) if len(snd) else 0.0
        if len(rg):
            res["gap_above"][i] = pi - sp[rg].max()
            res["gap_nearest"][i] = np.abs(pi - sp[rg]).min()
        prev = last_seen.get(pi)
        res["same_pitch_dt"][i] = np.log(min(10.0, t - prev) + 1e-3) if prev is not None \
            else np.log(10.0)
        last_seen[pi] = t
        nb = [counts[q] for q in (pi - 2, pi - 1, pi + 1, pi + 2) if 0 <= q < 128]
        res["pitch_spike"][i] = np.log((counts[pi] + 1) / (np.mean(nb) + 1))
    res["pitch"] = sp.astype(float)
    res["velocity"] = sv
    res["log_dur"] = np.log(np.maximum(sd, 0) + 1e-3)
    for k in FEATURES:
        out[k][order] = res[k]
    return pd.DataFrame(out)[FEATURES]


def label_false_extras(ref, est, onset_tol: float = 0.05  # noqa: ANN001
                       ) -> tuple[np.ndarray, dict[str, float]]:
    """1 for each ``est`` note with no ground-truth note of the same pitch within ``onset_tol``
    (after removing the median offset between the two clocks), else 0. Also returns
    :func:`note_f1`'s summary."""
    f = note_f1(ref, est, onset_tol=onset_tol, estimate_offset=True)
    m = match_notes(ref, est, onset_tol=onset_tol, offset=f["offset_sec"])
    y = np.ones(len(est["pitch"]), dtype=int)
    for _, j in m:
        y[j] = 0
    return y, f


def rule_scores(feat: pd.DataFrame, min_pitch: int = 91, max_vel_rel: float = 99.0,
                min_spike: float = 0.0, max_dur: float = 0.15) -> np.ndarray:
    """Rule for the A-01 phone-take signature: 1.0 for a note that is at or above ``min_pitch``
    (G6), has no harmonic source (no note a harmonic step below starts with it or is still
    down), is shorter than ``max_dur`` seconds, is at most ``max_vel_rel`` louder than the local
    median, and sits on a pitch that recurs at least as often as its neighbours
    (``pitch_spike >= min_spike``); else 0.0."""
    return ((feat["pitch"] >= min_pitch)
            & (feat["harm_onset"] == 0) & (feat["harm_sounding"] == 0)
            & (feat["log_dur"] < np.log(max_dur + 1e-3))
            & (feat["vel_rel_local"] <= max_vel_rel)
            & (feat["pitch_spike"] >= min_spike)).to_numpy(float)  # fmt: skip


@dataclass
class ExtraNoteFilter:
    """A fitted classifier (``predict_proba`` over :data:`FEATURES`) and its removal threshold.

    ``meta`` records what it was trained on and its held-out numbers. Save with :meth:`save`
    under ``data/`` only (trained on non-commercial data)."""

    model: object
    threshold: float
    meta: dict

    def scores(self, notes) -> np.ndarray:  # noqa: ANN001
        feat = note_features(notes)
        if len(feat) == 0:
            return np.zeros(0)
        return self.model.predict_proba(feat[FEATURES])[:, 1]

    def save(self, path: Path | str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "threshold": self.threshold, "meta": self.meta}, f)

    @classmethod
    def load(cls, path: Path | str) -> ExtraNoteFilter:
        with open(path, "rb") as f:
            d = pickle.load(f)  # noqa: S301 - our own file under data/
        return cls(d["model"], float(d["threshold"]), dict(d["meta"]))


def filter_notes(notes, flt: ExtraNoteFilter | None = None,  # noqa: ANN001
                 threshold: float | None = None, rule_params: dict | None = None
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Return (kept notes, boolean mask of removed notes). With ``flt`` None the rule baseline
    is used, with ``rule_params`` passed to :func:`rule_scores`. ``threshold`` overrides the
    filter's own."""
    if flt is None:
        s = rule_scores(note_features(notes), **(rule_params or {}))
        thr = 0.5 if threshold is None else threshold
    else:
        s = flt.scores(notes)
        thr = flt.threshold if threshold is None else threshold
    drop = s >= thr
    return notes[~drop], drop


def filter_midi(src: Path | str, dst: Path | str, flt: ExtraNoteFilter | None = None,
                threshold: float | None = None, rule_params: dict | None = None) -> dict:
    """Write ``src`` to ``dst`` without the notes the filter removes. Pedal, tempo and all other
    events are kept. Returns counts and the removed notes' pitches."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(src))
    rows = [(k, j, n.start, n.end - n.start, n.pitch, n.velocity)
            for k, ins in enumerate(pm.instruments) for j, n in enumerate(ins.notes)]
    df = pd.DataFrame(rows, columns=["ins", "j", "onset_sec", "duration_sec", "pitch",
                                     "velocity"])  # fmt: skip
    _, drop = filter_notes(df, flt, threshold, rule_params)
    gone = set(map(tuple, df.loc[drop, ["ins", "j"]].to_numpy().tolist()))
    for k, ins in enumerate(pm.instruments):
        ins.notes = [n for j, n in enumerate(ins.notes) if (k, j) not in gone]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(dst))
    return {"n_in": len(df), "n_removed": int(drop.sum()),
            "removed_pitches": df.loc[drop, "pitch"].astype(int).tolist(),
            "removed_onsets": df.loc[drop, "onset_sec"].astype(float).tolist()}  # fmt: skip
