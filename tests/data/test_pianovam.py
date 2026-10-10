import shutil
from pathlib import Path

import numpy as np
import pytest

from pianolens.data import pianovam
from pianolens.data.types import HAND_LABEL_DTYPE

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "pianovam"
needs_data = pytest.mark.skipif(not pianovam.data_available(), reason="data/raw/pianovam absent")
needs_hands = pytest.mark.skipif(
    not (pianovam.data_available() and pianovam.hand_labels_available()),
    reason="data/raw/pianovam/Fingering absent (BL-24)",
)


@needs_data
def test_index():
    md = pianovam.pianovam_index()
    assert len(md) == 107
    assert set(md["P1_skill"]) == set(pianovam.SKILLS)
    assert md["performance_id"].is_unique


@needs_data
def test_loads_performances():
    stats = pianovam.PianoVAMStats()
    perfs = list(pianovam.iter_performances(limit=3, stats=stats))
    assert stats.failed == 0 and len(perfs) == 3
    for p in perfs:
        assert p.provenance == "disklavier"
        assert p.meta["skill"] in pianovam.SKILLS
        assert len(p.notes) > 0


# ---- hand labels on the synthetic fixture (tests/fixtures/pianovam/make_fixture.py)


def _fixture_perf(root: Path = FIXTURE):
    (perf,) = pianovam.iter_performances(root)
    return perf


def test_fixture_video_labels_follow_note_order():
    perf = _fixture_perf()
    lab = pianovam.hand_labels(perf, "video", FIXTURE)
    assert lab.dtype == HAND_LABEL_DTYPE
    assert (lab["id"] == perf.notes["id"]).all()
    # the label file lists the first chord as 67, 60, 64; the result follows the MIDI notes
    by_pitch = {(round(float(o), 3), int(p)): (h, f) for o, p, h, f in
                zip(perf.notes["onset_sec"], perf.notes["pitch"], lab["hand"], lab["finger"],
                    strict=True)}  # fmt: skip
    assert by_pitch[(0.5, 67)] == ("R", 5)
    assert by_pitch[(0.5, 60)] == ("R", 1)
    assert by_pitch[(0.5, 64)] == ("R", 3)
    assert by_pitch[(1.0, 48)] == ("L", 5)
    assert by_pitch[(1.0, 72)] == ("", 0)  # Noinfo
    assert by_pitch[(1.5, 60)] == ("R", 1)


def test_fixture_manual_labels_cover_prefix_only():
    perf = _fixture_perf()
    lab = pianovam.hand_labels(perf, "manual", FIXTURE)
    assert (lab["hand"] != "").sum() == 3
    first_chord = perf.notes["onset_sec"] < 0.75
    assert (lab["hand"][first_chord] != "").all()
    assert sorted(lab["hand"][first_chord]) == ["L", "R", "R"]


def test_fixture_missing_source_returns_none(tmp_path):
    root = tmp_path / "pv"
    shutil.copytree(FIXTURE, root)
    shutil.rmtree(root / "Fingering_GT")
    assert pianovam.hand_labels(_fixture_perf(root), "manual", root) is None
    stats = pianovam.HandLabelStats()
    assert list(pianovam.iter_hand_labels("manual", root, stats=stats)) == []
    assert stats.no_labels == 1 and stats.loaded == 0


def test_fixture_mismatch_is_counted_not_raised(tmp_path):
    root = tmp_path / "pv"
    shutil.copytree(FIXTURE, root)
    f = root / "Fingering" / "2000-01-01_00-00-00.tsv"
    f.write_text(f.read_text().replace("\t48\t60\t", "\t49\t60\t"))  # a pitch no note has
    with pytest.raises(pianovam.HandLabelMismatch):
        pianovam.hand_labels(_fixture_perf(root), "video", root)
    stats = pianovam.HandLabelStats()
    assert list(pianovam.iter_hand_labels("video", root, stats=stats)) == []
    assert stats.failed == 1 and "1 unmatched" in stats.failures[0][1]


def test_fixture_summary():
    s = pianovam.hand_label_summary(FIXTURE)
    (r,) = s.itertuples()
    assert (r.n_notes, r.n_left, r.n_right, r.n_noinfo, r.n_manual) == (6, 1, 4, 1, 3)
    assert r.score_candidates == () and r.score_match == ""


def test_score_candidates_keys_are_pianovam_ids():
    for pid, (cands, kind) in pianovam.SCORE_CANDIDATES.items():
        assert pid.startswith("pianovam:") and cands and kind in ("unit", "ambiguous")


# ---- hand labels on the real data


@needs_hands
def test_real_hand_labels_load():
    stats = pianovam.HandLabelStats()
    out = list(pianovam.iter_hand_labels("video", limit=3, stats=stats))
    assert stats.failed == 0 and stats.loaded == 3
    for perf, lab in out:
        assert len(lab) == len(perf.notes) and (lab["id"] == perf.notes["id"]).all()
        assert set(np.unique(lab["hand"])) <= {"", "L", "R"}
        # left-hand notes sit lower than right-hand notes
        lo = np.median(perf.notes["pitch"][lab["hand"] == "L"])
        hi = np.median(perf.notes["pitch"][lab["hand"] == "R"])
        assert lo < hi


@needs_hands
def test_real_summary_counts():
    s = pianovam.hand_label_summary()
    assert s["n_notes"].notna().sum() == 106  # every solo recording
    assert int(s["n_notes"].sum()) == 525_483  # dataset card
    assert (s["n_manual"] > 0).sum() == 11 and int(s["n_manual"].sum()) == 1_800
    assert set(pianovam.SCORE_CANDIDATES) <= set(s["piece_id"])
