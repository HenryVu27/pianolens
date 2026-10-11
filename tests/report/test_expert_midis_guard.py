"""BL-38 part 1: the app's PianoCoRe expert references skip raw files the BL-35 guard rejects,
before the seeded choice, and skip score-version-mismatch pieces."""

from __future__ import annotations

import pandas as pd
import pytest

from pianolens.data import pianocore
from pianolens.data.piece_ids import SCORE_VERSION_MISMATCH
from pianolens.report.io import pianocore_expert_midis


class _FakeIndex:
    def __init__(self, df):
        self.index = df


class _FakeZip:
    def __init__(self, *_a, **_k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self, name):
        return name.encode()


def _fake(monkeypatch, n_rows: int, bad: set[str]):
    df = pd.DataFrame({
        "id": [f"P{i:03d}" for i in range(n_rows)], "performance_id": [f"perf{i}" for i in
                                                                          range(n_rows)],
        "piece_id": "x", "is_transcription": True, "capture_model": "Transkun V2",
        "performance_midi_path": [f"m{i}.mid" for i in range(n_rows)]})
    monkeypatch.setattr(pianocore, "data_available", lambda: True)
    monkeypatch.setattr(pianocore, "PianoCoRe", lambda: _FakeIndex(df))
    monkeypatch.setattr(pianocore, "raw_guard",
                        lambda rows: pd.Series(["too long" if i in bad else "" for i in
                                                rows["id"]], index=rows.index))
    import zipfile

    monkeypatch.setattr(zipfile, "ZipFile", _FakeZip)


def test_guard_runs_before_the_seeded_choice(monkeypatch):
    bad = {f"P{i:03d}" for i in range(0, 40, 2)}  # half of the first 40 rows are rejected
    _fake(monkeypatch, 40, bad)
    got = [i for i, _ in pianocore_expert_midis("x", "Transkun V2", n=15)]
    assert len(got) == 15  # a full set from the 20 accepted rows
    assert not set(got) & bad
    # the draw is the seeded choice over the accepted rows only
    import numpy as np

    ok = sorted(f"P{i:03d}" for i in range(40) if f"P{i:03d}" not in bad)
    pick = np.sort(np.random.default_rng(0).choice(len(ok), size=15, replace=False))
    assert got == [ok[i] for i in pick]


def test_no_rejected_rows_gives_the_old_draw(monkeypatch):
    _fake(monkeypatch, 30, set())
    import numpy as np

    got = [i for i, _ in pianocore_expert_midis("x", "Transkun V2", n=15)]
    pick = np.sort(np.random.default_rng(0).choice(30, size=15, replace=False))
    assert got == [f"P{i:03d}" for i in pick]


def test_score_version_mismatch_piece_has_no_references(monkeypatch):
    _fake(monkeypatch, 30, set())
    assert pianocore_expert_midis(next(iter(SCORE_VERSION_MISMATCH)), "Transkun V2") == []


@pytest.mark.skipif(not pianocore.data_available(), reason="PianoCoRe raw archive absent")
def test_real_op22_keeps_a_full_reference_set_of_guarded_files():
    idx = pianocore.PianoCoRe().index
    rows = idx[(idx["piece_id"] == "chopin_op22") & idx["is_transcription"].astype(bool)]
    reason = dict(zip(rows["id"].astype(str), pianocore.raw_guard(rows), strict=True))
    got = pianocore_expert_midis("chopin_op22", None, n=15)
    assert len(got) == 15
    assert all(reason[i] == "" for i, _ in got)
