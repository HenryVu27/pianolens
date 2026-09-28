"""Tests for pianolens.data.perturb on synthetic performances with a known answer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pianolens.data.perturb import MistakeSpec, chord_clusters, perturb
from pianolens.data.types import ALIGNMENT_DTYPE, PEDAL_DTYPE, Alignment, Performance

PERF_DTYPE = np.dtype([("onset_sec", "f8"), ("duration_sec", "f8"), ("onset_tick", "i4"),
                       ("duration_tick", "i4"), ("pitch", "i4"), ("velocity", "i4"),
                       ("id", "U8")])  # fmt: skip


def make_performance(n_chords: int = 200, provenance: str = "disklavier", fast: bool = False
                     ) -> tuple[Performance, Alignment]:
    """Three-note chords (C-E-G shifted) every 0.5 s (0.1 s if ``fast``), all matched."""
    rows, pairs = [], []
    step = 0.1 if fast else 0.5
    k = 0
    for c in range(n_chords):
        base = 48 + (c % 12)
        for j, iv in enumerate((0, 4, 7)):
            t = c * step + 0.005 * j
            rows.append((t, 0.4 * step, int(t * 960), int(0.4 * step * 960), base + iv, 60 + j,
                         f"n{k}"))  # fmt: skip
            pairs.append(("match", f"s{k}", f"n{k}"))
            k += 1
    notes = np.array(rows, dtype=PERF_DTYPE)
    pedal = np.array([(0.0, 64, 127), (1.0, 64, 0)], dtype=PEDAL_DTYPE)
    perf = Performance("test:p", "piece", "performer", provenance, notes, pedal, "test")
    al = Alignment(np.array(pairs, dtype=ALIGNMENT_DTYPE), "test:s", "test:p", True, "test")
    return perf, al


def test_rate_zero_is_identity():
    perf, al = make_performance(50)
    q, lab = perturb(perf, al, MistakeSpec(rate=0.0), seed=3)
    np.testing.assert_array_equal(q.notes["pitch"], perf.notes["pitch"])
    np.testing.assert_allclose(q.notes["onset_sec"], perf.notes["onset_sec"])
    assert set(lab.notes["label"]) == {"correct"}
    assert len(lab.missed) == 0
    assert q.provenance == "synthetic"
    assert q.meta["perturbation"]["source_provenance"] == "disklavier"


@pytest.mark.parametrize("rate", [0.02, 0.05, 0.1])
def test_exact_counts(rate):
    perf, al = make_performance(200)
    q, lab = perturb(perf, al, MistakeSpec(rate=rate), seed=1)
    total = round(rate * 600)
    c = lab.counts()
    assert sum(c.values()) == total
    assert max(c.values()) - min(c.values()) <= 1
    assert len(q.notes) == 600 - c["missed"] + c["extra"]
    assert len(set(q.notes["id"].tolist())) == len(q.notes)


def test_deterministic_given_seed():
    perf, al = make_performance(100)
    a, la = perturb(perf, al, MistakeSpec(rate=0.1), seed=7)
    b, lb = perturb(perf, al, MistakeSpec(rate=0.1), seed=7)
    c, _ = perturb(perf, al, MistakeSpec(rate=0.1), seed=8)
    np.testing.assert_array_equal(a.notes, b.notes)
    assert la.notes.equals(lb.notes)
    assert not np.array_equal(a.notes["pitch"], c.notes["pitch"]) or len(a.notes) != len(c.notes)


def test_wrong_pitch_properties():
    perf, al = make_performance(200)
    q, lab = perturb(perf, al, MistakeSpec(rate=0.1, mix=(1, 0, 0)), seed=2)
    wrong = lab.notes[lab.notes["label"] == "wrong_pitch"]
    assert len(wrong) == 60
    by_id = {r["id"]: r for r in q.notes}
    orig = {r["id"]: r for r in perf.notes}
    chord = chord_clusters(perf.notes["onset_sec"], 0.05)
    for pid in wrong["performance_id"]:
        new, old = int(by_id[pid]["pitch"]), int(orig[pid]["pitch"])
        assert new - old in (-1, 1, -2, 2, -12, 12)
        i = int(np.flatnonzero(perf.notes["id"] == pid)[0])
        assert new not in set(perf.notes["pitch"][chord == chord[i]].tolist())
        assert by_id[pid]["onset_sec"] == orig[pid]["onset_sec"]
        assert by_id[pid]["velocity"] == orig[pid]["velocity"]
    # ground truth keeps the intended score note
    assert set(wrong["score_id"]) <= {f"s{k}" for k in range(600)}


def test_extra_note_properties():
    spec = MistakeSpec(rate=0.1, mix=(0, 1, 0))
    perf, al = make_performance(200)
    q, lab = perturb(perf, al, spec, seed=4)
    extra = lab.notes[lab.notes["label"] == "extra"]
    assert len(extra) == 60 and extra["injected"].all()
    by_id = {str(r["id"]): r for r in q.notes}
    for pid, anchor in zip(extra["performance_id"], extra["anchor_id"], strict=True):
        e, a = by_id[pid], by_id[anchor]
        assert abs(int(e["pitch"]) - int(a["pitch"])) in (1, 2)
        assert -0.02 - 1e-9 <= e["onset_sec"] - a["onset_sec"] <= 0.06 + 1e-9
        assert 0.03 <= e["duration_sec"] <= 0.15
        assert e["velocity"] < a["velocity"]
    # no two notes of the same pitch overlap in time
    for p in np.unique(q.notes["pitch"]):
        m = q.notes[q.notes["pitch"] == p]
        m = m[np.argsort(m["onset_sec"])]
        assert np.all(m["onset_sec"][1:] >= (m["onset_sec"] + m["duration_sec"])[:-1] - 1e-9)


def test_missed_bias_to_inner_voices():
    perf, al = make_performance(300)
    spec = MistakeSpec(rate=0.1, mix=(0, 0, 1), missed_inner_weight=10.0)
    _, lab = perturb(perf, al, spec, seed=5)
    dropped = lab.missed[lab.missed["injected"]]["original_performance_id"]
    inner = sum(int(pid[1:]) % 3 == 1 for pid in dropped)  # middle note of each chord
    # uniform would give 1/3; weight 10 on inner gives 10/12 expected
    assert inner / len(dropped) > 0.7


def test_missed_bias_to_fast_passages():
    slow, al_s = make_performance(100)
    fast, _ = make_performance(100, fast=True)
    notes = np.concatenate([slow.notes, fast.notes])
    notes["onset_sec"][300:] += 60.0
    notes["id"] = [f"n{k}" for k in range(600)]
    pairs = np.array([("match", f"s{k}", f"n{k}") for k in range(600)], dtype=ALIGNMENT_DTYPE)
    perf = Performance("test:p", "piece", "x", "disklavier", notes, slow.pedal, "test")
    al = Alignment(pairs, "s", "p", True, "t")
    spec = MistakeSpec(rate=0.1, mix=(0, 0, 1), missed_fast_weight=5.0, missed_inner_weight=1.0)
    _, lab = perturb(perf, al, spec, seed=6)
    ids = lab.missed["original_performance_id"].str[1:].astype(int)
    assert (ids >= 300).mean() > 0.7


def test_natural_mistakes_and_interpolated_are_carried():
    perf, al = make_performance(30)
    pairs = al.pairs.copy()
    pairs[0] = ("insertion", "", "n0")
    pairs[1] = ("interpolated", "s1", "n1")
    pairs = np.concatenate([pairs, np.array([("deletion", "s999", "")], dtype=ALIGNMENT_DTYPE)])
    al2 = Alignment(pairs, "s", "p", True, "t")
    q, lab = perturb(perf, al2, MistakeSpec(rate=0.2), seed=0)
    row0 = lab.notes[lab.notes["performance_id"] == "n0"].iloc[0]
    row1 = lab.notes[lab.notes["performance_id"] == "n1"].iloc[0]
    assert (row0["label"], row0["injected"]) == ("extra", False)
    assert (row1["label"], row1["injected"]) == ("interpolated", False)
    nat = lab.missed[~lab.missed["injected"]]
    assert nat["score_id"].tolist() == ["s999"]
    # the untouched notes are still in the output
    assert {"n0", "n1"} <= set(q.notes["id"].tolist())


def test_ground_truth_alignment_is_consistent():
    perf, al = make_performance(100)
    q, lab = perturb(perf, al, MistakeSpec(rate=0.1), seed=9)
    pairs = lab.alignment.pairs
    pids = pairs["performance_id"][pairs["performance_id"] != ""]
    assert sorted(pids.tolist()) == sorted(q.notes["id"].tolist())
    c = lab.counts()
    assert (pairs["label"] == "deletion").sum() == c["missed"] + c["wrong_pitch"]
    assert (pairs["label"] == "insertion").sum() == c["extra"] + c["wrong_pitch"]


def test_requires_exact_timing():
    perf, al = make_performance(10, provenance="transcribed")
    with pytest.raises(ValueError, match="exact timing"):
        perturb(perf, al, MistakeSpec(), seed=0)
    perturb(perf, al, MistakeSpec(), seed=0, require_exact_timing=False)


def test_timing_velocity_and_tempo():
    perf, al = make_performance(400)
    spec = MistakeSpec(rate=0.0, timing_jitter_sd_sec=0.02, velocity_jitter_sd=5.0)
    q, lab = perturb(perf, al, spec, seed=1)
    orig = {r["id"]: r for r in perf.notes}
    d = np.array([r["onset_sec"] - orig[r["id"]]["onset_sec"] for r in q.notes])
    assert 0.017 < d.std() < 0.023
    dv = np.array([int(r["velocity"]) - int(orig[r["id"]]["velocity"]) for r in q.notes])
    assert 4.0 < dv.std() < 6.0
    assert set(lab.notes["label"]) == {"correct"}

    q2, _ = perturb(perf, al, MistakeSpec(rate=0.0, tempo_scale=1.5), seed=1)
    by_id = {r["id"]: r for r in q2.notes}
    last = perf.notes[-1]
    assert by_id[last["id"]]["onset_sec"] == pytest.approx(1.5 * last["onset_sec"])
    assert q2.pedal["time_sec"][1] == pytest.approx(1.5)
    # ticks follow the new times
    assert by_id[last["id"]]["onset_tick"] > last["onset_tick"]


def test_chord_clusters():
    on = np.array([0.0, 0.01, 0.04, 0.2, 0.26, 0.3])
    np.testing.assert_array_equal(chord_clusters(on, 0.05), [0, 0, 0, 1, 2, 2])


MISTAKES_V1 = Path(__file__).resolve().parents[2] / "data" / "processed" / "mistakes_v1"


@pytest.mark.skipif(not (MISTAKES_V1 / "index.csv").is_file(), reason="mistakes_v1 not built")
def test_stored_set_round_trip():
    from pianolens.data.perturb import load_mistake_set

    index, get = load_mistake_set(MISTAKES_V1)
    assert index["performance_id"].nunique() == 100
    assert sorted(index["rate"].unique().tolist()) == [0.0, 0.02, 0.05, 0.1]
    row = index[index["rate"] == 0.05].iloc[0]
    perf, lab = get(row["key"])
    assert len(perf.notes) == row["n_notes"] == len(lab.notes)
    assert (perf.notes["id"] == lab.notes["performance_id"].to_numpy()).all()
    c = lab.counts()
    assert (c["wrong_pitch"], c["extra"], c["missed"]) == (
        row["n_wrong_pitch"], row["n_extra"], row["n_missed"])
    assert lab.spec.rate == 0.05
    pairs = lab.alignment.pairs
    assert (pairs["label"] == "deletion").sum() == c["missed"] + c["wrong_pitch"] + lab.counts(
        False)["missed"]
