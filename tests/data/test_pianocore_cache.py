import numpy as np
import pyarrow.parquet as pq
import pytest

from pianolens.data import pianocore_cache as pcc
from pianolens.data.types import (
    ALIGNMENT_DTYPE,
    PEDAL_DTYPE,
    AlignedPerformance,
    Alignment,
    Performance,
    PerformerId,
    PieceId,
    Score,
)

S_DT = [("onset_beat", "f4"), ("duration_beat", "f4"), ("onset_quarter", "f4"),
        ("duration_quarter", "f4"), ("pitch", "i4"), ("voice", "i4"), ("id", "U4"),
        ("is_grace", "i1"), ("ts_beats", "i4"), ("ts_beat_type", "i4"),
        ("staff", "i4")]  # fmt: skip
P_DT = [("onset_sec", "f4"), ("duration_sec", "f4"), ("pitch", "i4"), ("velocity", "i4"),
        ("id", "U4")]  # fmt: skip
M_DT = [("number", "i4"), ("name", "U16"), ("start_quarter", "f8"), ("end_quarter", "f8")]


def _aligned() -> AlignedPerformance:
    s_notes = np.array([(0, 1, 0, 1, 60, 1, "n0", 0, 2, 4, 1),
                        (1, 1, 1, 1, 62, 1, "n1", 0, 2, 4, 1),
                        (2, 1, 2, 1, 64, 1, "n2", 0, 2, 4, 1)], dtype=S_DT)  # fmt: skip
    measures = np.array([(1, "1", 0.0, 2.0), (2, "2", 2.0, 4.0)], dtype=M_DT)
    score = Score("t:s", PieceId("chopin_op10_no3"), s_notes, measures)
    p_notes = np.array([(0.0, 0.4, 60, 50, "p0"), (0.5, 0.4, 62, 60, "p1"),
                        (0.7, 0.1, 70, 30, "p2")], dtype=P_DT)  # fmt: skip
    perf = Performance("t:p", PieceId("chopin_op10_no3"), PerformerId("t:x"), "transcribed",
                       p_notes, np.zeros(0, dtype=PEDAL_DTYPE), "t", meta={"split": "train"})
    pairs = np.array([("match", "n0", "p0"), ("interpolated", "n1", "p1"), ("deletion", "n2", ""),
                      ("insertion", "", "p2")], dtype=ALIGNMENT_DTYPE)  # fmt: skip
    return AlignedPerformance(perf, score, Alignment(pairs, "t:s", "t:p", False, "test"))


def test_piece_slug():
    assert pcc.piece_slug("chopin_op10_no3") == "chopin_op10_no3"
    a = pcc.piece_slug("pianocore:Chopin,_Frédéric/Nocturnes,_Op.9/Nocturne_No.2")
    assert a.startswith("pianocore_chopin_frederic_nocturnes_op_9") and a.isascii()
    assert pcc.piece_slug("pianocore:A/B") != pcc.piece_slug("pianocore:A_B")


def test_aligned_columns_roundtrip(tmp_path):
    ap = _aligned()
    table = pcc.columns_to_table(pcc.aligned_columns(ap))
    assert table.schema == pcc.NOTE_SCHEMA and table.num_rows == 4
    (tmp_path / "notes").mkdir()
    pq.write_table(table, tmp_path / "notes" / "chopin_op10_no3.parquet")
    df = pcc.load_piece_notes("chopin_op10_no3", tmp_path)
    assert df["label"].tolist() == ["match", "interpolated", "deletion", "insertion"]
    assert df["s_measure"].tolist() == [1, 1, 2, -1]
    assert df["p_velocity"].tolist() == [50, 60, -1, 30]
    assert np.isnan(df["p_onset_sec"].iloc[2]) and np.isnan(df["s_onset_beat"].iloc[3])
    assert df["s_id"].tolist() == ["n0", "n1", "n2", ""]
    only = pcc.load_piece_notes("chopin_op10_no3", tmp_path, columns=["p_onset_sec"],
                                labels=("match",))  # fmt: skip
    assert list(only.columns) == ["p_onset_sec"] and len(only) == 1
    with pytest.raises(KeyError):
        pcc.load_piece_notes("nope", tmp_path)


def test_performance_record():
    import pandas as pd

    rec = pcc.performance_record(_aligned(), pd.Series({"id": "PianoCoRe_1"}), False)
    assert set(rec) == set(pcc.PERFORMANCE_COLUMNS)
    assert (rec["n_match"], rec["n_interpolated"], rec["n_deletion"], rec["n_insertion"]) == (
        1, 1, 1, 1)


@pytest.mark.skipif(not pcc.cache_available(), reason="PianoCoRe cache not built")
def test_cache_manifest_consistent():
    pieces = pcc.load_pieces()
    perfs = pcc.load_performances()
    assert pieces["n_performances"].sum() == len(perfs)
    top = pieces.iloc[0]
    df = pcc.load_piece_notes(top["piece_id"], columns=["performance_id", "label"])
    assert len(df) == top["n_rows"]
    assert df["performance_id"].nunique() == top["n_performances"]
