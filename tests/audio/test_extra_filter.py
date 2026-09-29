"""Known-answer tests for the A-01b extra-note filter features, labels and rules."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pianolens.audio.extra_filter import (
    FEATURES,
    ExtraNoteFilter,
    filter_notes,
    label_false_extras,
    note_features,
    rule_scores,
)


def _notes(onsets, pitches, dur=0.2, vel=64):
    n = len(onsets)
    vel = np.broadcast_to(np.asarray(vel, float), (n,))
    return pd.DataFrame({"onset_sec": np.asarray(onsets, float), "pitch": np.asarray(pitches),
                         "duration_sec": np.full(n, dur), "velocity": vel})


def test_features_harmonic_source_and_register():
    # C4 (60) and its octave C5 (72) together; a lone D7 (98) 2 s later, while C4 still sounds
    n = _notes([0.0, 0.01, 2.0], [60, 72, 98])
    n.loc[:, "duration_sec"] = [3.0, 0.2, 0.1]
    f = note_features(n)
    assert list(f.columns) == FEATURES and len(f) == 3
    assert f.loc[1, "harm_onset"] == 1.0 and f.loc[0, "harm_onset"] == 0.0
    assert f.loc[1, "n_chord"] == 1 and f.loc[2, "n_chord"] == 0
    # 98 - 60 = 38 is not a harmonic step; C4 is still down at 2.0 s but not a source
    assert f.loc[2, "harm_sounding"] == 0.0
    assert np.isnan(f.loc[2, "gap_above"])  # nothing within 0.5 s
    assert f.loc[1, "gap_above"] == 12 and f.loc[0, "gap_nearest"] == 12


def test_features_sounding_source_and_fixed_pitch_spike():
    # a held C5 (72) with its 3rd partial G6 (91) appearing 1 s later
    n = _notes([0.0, 1.0], [72, 91])
    n.loc[:, "duration_sec"] = [2.0, 0.1]
    f = note_features(n)
    assert f.loc[1, "harm_sounding"] == 1.0 and f.loc[1, "harm_onset"] == 0.0
    # pitch 98 recurring 10 times, neighbours absent -> high spike; order of rows is preserved
    on = np.arange(12) * 0.7
    p = [98] * 10 + [60, 64]
    g = note_features(_notes(on[::-1], p))
    assert g.loc[0, "pitch"] == 98 and g.loc[0, "pitch_spike"] > 2.0
    assert abs(g.loc[10, "pitch_spike"]) < 1.0
    assert g.loc[1, "same_pitch_dt"] < np.log(1.0)  # 0.7 s since the previous 98


def test_label_false_extras_with_offset():
    ref = _notes(np.arange(10) * 0.5, [60 + k for k in range(10)])
    est = pd.concat([ref.assign(onset_sec=ref["onset_sec"] + 0.1),
                     _notes([1.23], [100])], ignore_index=True)  # fmt: skip
    y, f = label_false_extras(ref, est)
    assert y.tolist() == [0] * 10 + [1]
    assert abs(f["offset_sec"] - 0.1) < 1e-9 and f["recall"] == 1.0


def test_rule_and_filter_notes():
    # loud-ish melody in the middle, one quiet isolated high D#7 (99) with no source
    n = _notes([0.0, 0.3, 0.6, 0.62], [60, 62, 64, 99], vel=[70, 70, 70, 40])
    n.loc[3, "duration_sec"] = 0.06  # short, like the A-01 artefacts
    s = rule_scores(note_features(n))
    assert s.tolist() == [0, 0, 0, 1]
    # a long high note is kept by default, removed when the duration cap is lifted
    n.loc[3, "duration_sec"] = 0.5
    assert rule_scores(note_features(n)).tolist() == [0, 0, 0, 0]
    assert rule_scores(note_features(n), max_dur=99).tolist() == [0, 0, 0, 1]
    n.loc[3, "duration_sec"] = 0.06
    kept, drop = filter_notes(n)
    assert drop.tolist() == [False, False, False, True] and len(kept) == 3
    # an octave above a played note is not removed by the rule
    m = _notes([0.0, 0.0], [84, 96], vel=[70, 40])
    assert rule_scores(note_features(m)).tolist() == [0, 0]


class _Const:
    def __init__(self, p):
        self.p = p

    def predict_proba(self, x):
        return np.column_stack([1 - self.p[: len(x)], self.p[: len(x)]])


def test_filter_object_roundtrip(tmp_path):
    n = _notes([0.0, 0.5, 1.0], [60, 62, 100])
    flt = ExtraNoteFilter(_Const(np.array([0.1, 0.2, 0.9])), 0.5, {"trained_on": "test"})
    kept, drop = filter_notes(n, flt)
    assert drop.tolist() == [False, False, True]
    flt.save(tmp_path / "f.pkl")
    g = ExtraNoteFilter.load(tmp_path / "f.pkl")
    assert g.threshold == 0.5 and g.meta["trained_on"] == "test"
    assert filter_notes(n, g, threshold=0.15)[1].tolist() == [False, True, True]
    assert len(note_features(n.iloc[:0])) == 0


def test_filter_midi_keeps_pedal(tmp_path):
    import pretty_midi

    from pianolens.audio.extra_filter import filter_midi

    pm = pretty_midi.PrettyMIDI()
    ins = pretty_midi.Instrument(0)
    for t, p, v, d in [(0.0, 60, 70, 0.2), (0.3, 62, 70, 0.2), (0.6, 64, 70, 0.2),
                       (0.62, 99, 40, 0.06)]:
        ins.notes.append(pretty_midi.Note(velocity=v, pitch=p, start=t, end=t + d))
    ins.control_changes.append(pretty_midi.ControlChange(64, 127, 0.1))
    pm.instruments.append(ins)
    pm.write(str(tmp_path / "a.mid"))
    r = filter_midi(tmp_path / "a.mid", tmp_path / "b.mid")
    assert r["n_in"] == 4 and r["n_removed"] == 1 and r["removed_pitches"] == [99]
    out = pretty_midi.PrettyMIDI(str(tmp_path / "b.mid"))
    assert sorted(n.pitch for n in out.instruments[0].notes) == [60, 62, 64]
    assert [c.number for c in out.instruments[0].control_changes] == [64]


def test_rule_defaults_are_the_a01b_choice():
    import inspect

    sig = inspect.signature(rule_scores)
    got = {k: sig.parameters[k].default for k in ("min_pitch", "max_dur", "min_spike",
                                                  "max_vel_rel")}  # fmt: skip
    # changing these invalidates the A-01b validation in docs/specs/phone-audio-baseline.md
    assert got == {"min_pitch": 96, "max_dur": 0.1, "min_spike": 0.5, "max_vel_rel": 99.0}
