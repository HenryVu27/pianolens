import numpy as np
import pandas as pd
import partitura as pt
import pytest

from pianolens.data.piece_ids import make_piece_id, prefixed_piece_id
from pianolens.data.types import (
    ALIGNMENT_DTYPE,
    ALIGNMENT_LABELS,
    PEDAL_DTYPE,
    Alignment,
    BeatCurve,
    Performance,
    PerformerId,
    PieceId,
    Ratings,
    Score,
    compact_ids,
    performance_from_partitura,
    score_from_partitura,
    tempo_from_beat_times,
)


def _performed_part():
    notes = [
        {"id": "n0", "midi_pitch": 60, "note_on": 0.0, "note_off": 0.5, "velocity": 64},
        {"id": "n1", "midi_pitch": 64, "note_on": 0.5, "note_off": 0.75, "velocity": 70},
    ]
    controls = [
        {"time": 0.1, "number": 64, "value": 127, "track": 0, "channel": 0},
        {"time": 2.0, "number": 64, "value": 0, "track": 0, "channel": 0},
        {"time": 0.2, "number": 7, "value": 100, "track": 0, "channel": 0},
        {"time": 0.3, "number": 67, "value": 90, "track": 0, "channel": 0},
    ]
    return pt.performance.PerformedPart(notes=notes, controls=controls)


def test_performance_from_partitura_uses_key_down_duration_and_collects_pedal():
    pp = _performed_part()
    # partitura's default note array is pedal-extended: that is the trap we guard against
    assert pp.note_array()["duration_sec"][0] == pytest.approx(2.0)
    perf = performance_from_partitura(
        pp, performance_id="t:1", piece_id=PieceId("x"), performer_id=PerformerId("t:p"),
        provenance="synthetic", dataset="t",
    )
    np.testing.assert_allclose(perf.notes["duration_sec"], [0.5, 0.25])
    assert perf.pedal.dtype == PEDAL_DTYPE
    assert perf.pedal["number"].tolist() == [64, 67, 64]  # CC7 volume dropped, time-sorted
    assert perf.duration_sec == pytest.approx(0.75)
    assert perf.notes.dtype["id"].itemsize < 256 * 4  # ids compacted


def test_performance_from_multitrack_parts_has_unique_ids():
    a = pt.performance.PerformedPart(notes=[
        {"id": "n0", "midi_pitch": 60, "note_on": 0.0, "note_off": 0.5, "velocity": 64},
        {"id": "n1", "midi_pitch": 62, "note_on": 1.0, "note_off": 1.5, "velocity": 64}])
    b = pt.performance.PerformedPart(notes=[
        {"id": "n0", "midi_pitch": 48, "note_on": 0.5, "note_off": 1.0, "velocity": 50}])
    perf = performance_from_partitura(
        pt.performance.Performance(performedparts=[a, b]), performance_id="t:2",
        piece_id=PieceId("x"), performer_id=PerformerId("t:p"), provenance="synthetic",
        dataset="t",
    )
    assert perf.notes["id"].tolist() == ["n0", "n1", "n2"]
    assert perf.notes["pitch"].tolist() == [60, 48, 62]  # onset order
    # a single part keeps partitura's ids
    one = performance_from_partitura(
        b, performance_id="t:3", piece_id=PieceId("x"), performer_id=PerformerId("t:p"),
        provenance="synthetic", dataset="t",
    )
    assert one.notes["id"].tolist() == ["n0"]


def test_performance_rejects_bad_provenance():
    pp = _performed_part()
    with pytest.raises(ValueError):
        performance_from_partitura(
            pp, performance_id="t:1", piece_id=PieceId("x"), performer_id=PerformerId("p"),
            provenance="phone", dataset="t",  # type: ignore[arg-type]
        )


def _toy_part():
    part = pt.score.Part("P0", "toy", quarter_duration=4)
    part.add(pt.score.TimeSignature(2, 4), start=0)
    for i, (start, pitch) in enumerate([(0, "C"), (4, "E"), (8, "G"), (12, "C")]):
        part.add(pt.score.Note(id=f"n{i}", step=pitch, octave=4, voice=1), start, start + 4)
    pt.score.add_measures(part)
    return part


def test_score_from_partitura_and_measures():
    score = score_from_partitura(_toy_part(), score_id="t:s", piece_id=PieceId("x"))
    assert list(score.notes["id"]) == ["n0", "n1", "n2", "n3"]
    assert score.measures["number"].tolist() == [1, 2]
    np.testing.assert_allclose(score.measures["start_quarter"], [0, 2])
    assert score.note_measures().tolist() == [1, 1, 2, 2]


def test_score_requires_fields():
    bad = np.zeros(2, dtype=[("pitch", "i4")])
    with pytest.raises(ValueError):
        Score("s", PieceId("x"), bad, np.zeros(0, dtype=[("number", "i4")]))


def test_alignment_roundtrip():
    al = [
        {"label": "match", "score_id": "n1-1", "performance_id": "n0"},
        {"label": "deletion", "score_id": "n2-1"},
        {"label": "insertion", "performance_id": "n5"},
    ]
    a = Alignment.from_partitura(al, "s", "p", ground_truth=True, source="test")
    assert a.pairs.dtype == ALIGNMENT_DTYPE
    assert len(a.matches) == len(a.deletions) == len(a.insertions) == 1
    assert a.to_partitura() == al


def test_compact_ids():
    arr = np.array([(1, "a"), (2, "abcd")], dtype=[("x", "i4"), ("id", "U256")])
    out = compact_ids(arr)
    assert out.dtype["id"] == np.dtype("U4")
    assert out["id"].tolist() == ["a", "abcd"]


def test_ratings_matrix_and_mean():
    t = pd.DataFrame(
        {
            "performance_id": ["a", "a", "b", "b"],
            "rater_id": ["r1", "r2", "r1", "r2"],
            "dimension": ["d", "d", "d", "d"],
            "value": [1.0, 3.0, 5.0, 7.0],
        }
    )
    r = Ratings(t, ("d",), (1.0, 7.0), "t")
    assert r.matrix("d").loc["a", "r2"] == 3.0
    assert r.mean().loc["b", "d"] == 6.0


def test_piece_ids():
    assert make_piece_id("Chopin", "Op. 10", 3) == "chopin_op10_no3"
    assert make_piece_id("Bach", "BWV 846", None, "Fugue") == "bach_bwv846_fugue"
    assert make_piece_id("Mozart", "K.331", None, 3) == "mozart_k331_mv3"
    assert prefixed_piece_id("asap", "Ravel/Pavane") == "asap:Ravel/Pavane"


def test_performance_requires_pedal_dtype():
    notes = np.zeros(
        1, dtype=[("onset_sec", "f4"), ("duration_sec", "f4"), ("pitch", "i4"),
                  ("velocity", "i4"), ("id", "U4")]
    )
    with pytest.raises(ValueError):
        Performance("p", PieceId("x"), PerformerId("q"), "synthetic", notes,
                    np.zeros(0, dtype=[("t", "f8")]), "t")


def test_piece_ids_fold_accents():
    assert make_piece_id("Dvořák", "Op. 101", 7) == "dvorak_op101_no7"
    assert make_piece_id("Janáček", "JW VIII/17") == "janacek_jwviii17"
    assert make_piece_id("Satie", "Gymnopédie", None, "Lent") == "satie_gymnopedie_lent"


def test_alignment_interpolated_is_separate_from_matches():
    al = [
        {"label": "match", "score_id": "s0", "performance_id": "p0"},
        {"label": "interpolated", "score_id": "s1", "performance_id": "p1"},
        {"label": "deletion", "score_id": "s2"},
    ]
    a = Alignment.from_partitura(al, "s", "p", ground_truth=False, source="test")
    assert "interpolated" in ALIGNMENT_LABELS
    assert a.matches["score_id"].tolist() == ["s0"]
    assert a.interpolated["performance_id"].tolist() == ["p1"]
    assert a.paired["score_id"].tolist() == ["s0", "s1"]
    assert a.to_partitura() == al


def test_beat_curve_tempo_and_frame():
    c = BeatCurve("t:1", PieceId("x"), PerformerId("t:p"), time_sec=[0.0, 0.5, 1.5, np.nan, 3.0],
                  loudness=[1, 2, 3, 4, 5], measure=[1, 1, 1, 2, 2], beat=[0, 1, 2, 0, 1])
    np.testing.assert_allclose(c.tempo_bpm, [120.0, 60.0, np.nan, np.nan, np.nan])
    assert len(c) == 5 and c.measure.dtype.kind == "i"
    df = c.to_frame()
    assert list(df.columns) == ["measure", "beat", "time_sec", "tempo_bpm", "loudness"]
    c2 = BeatCurve("t:2", PieceId("x"), PerformerId("t:p"), time_sec=[0.0, 1.0])
    assert list(c2.to_frame().columns) == ["time_sec", "tempo_bpm"]


def test_beat_curve_validates():
    with pytest.raises(ValueError):
        BeatCurve("t", PieceId("x"), PerformerId("p"), time_sec=[0.0, 1.0], loudness=[1.0])
    with pytest.raises(ValueError):
        BeatCurve("t", PieceId("x"), PerformerId("p"), time_sec=[0.0], provenance="phone")  # type: ignore[arg-type]
    np.testing.assert_allclose(tempo_from_beat_times(np.array([0.0, 0.0, 1.0])),
                               [np.nan, 60.0, np.nan])


def test_piece_id_table_if_built():
    from pianolens.data.piece_ids import PIECE_ID_COLUMNS, PIECE_ID_TABLE, datasets_by_piece

    if not PIECE_ID_TABLE.is_file():
        pytest.skip("piece_ids.parquet not built")
    from pianolens.data.piece_ids import load_piece_id_table

    t = load_piece_id_table()
    assert tuple(t.columns) == PIECE_ID_COLUMNS
    assert not t.duplicated(["dataset", "source_key"]).any()
    assert set(datasets_by_piece(t)["chopin_op10_no3"]) >= {"asap", "pianocore", "vienna4x22"}
