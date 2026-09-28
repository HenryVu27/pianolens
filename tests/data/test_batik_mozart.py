import pytest

from pianolens.data import batik_mozart as b

pytestmark = pytest.mark.skipif(not b.data_available(), reason="data/raw/batik_mozart absent")


def test_piece_id():
    assert b.movement_piece_id("kv331_3") == "mozart_k331_mv3"


def test_loads_one_movement_and_annotations():
    assert len(b.match_files()) == 36
    stats = b.BatikStats()
    ap = next(b.iter_aligned(stats=stats))
    assert stats.failed == 0
    assert ap.performance.provenance == "sensor" and ap.performance.piece_id == "mozart_k279_mv1"
    assert ap.alignment.ground_truth and len(ap.alignment.matches) > 1000
    ann = b.load_note_annotations("kv279_1", "phrases")
    assert "id" in ann.columns and len(ann) > 0


def test_musicxml_performed_score_keeps_ids_and_markings():
    ap = b.load_aligned("kv279_2", musicxml_score=True)
    s = ap.score
    assert s.meta["id_coverage"] == 1.0 and s.meta["id_jaccard"] == 1.0
    assert s.meta["score_source"] == "musicxml_edited" and s.part is not None
    match = b.load_aligned("kv279_2").score
    assert set(s.notes["id"].astype(str)) == set(match.notes["id"].astype(str))
    beat = dict(zip(match.notes["id"].astype(str), match.notes["onset_beat"], strict=True))
    assert all(abs(beat[i] - x) < 1e-6
               for i, x in zip(s.notes["id"].astype(str), s.notes["onset_beat"], strict=True))
    # every aligned score id resolves in the performed score
    ids = set(s.notes["id"].astype(str))
    sid = ap.alignment.matches["score_id"].astype(str)
    assert len(sid) > 100 and all(x in ids for x in sid)
    # markings present (the match-built score has none; the Batik MusicXML has no slurs)
    import partitura as pt

    assert sum(1 for _ in s.part.iter_all(pt.score.ConstantLoudnessDirection)) > 10


def test_phrase_annotations_map_to_performed_beats():
    s = b.load_aligned("kv279_2", musicxml_score=True).score
    ann = b.phrase_annotations(s)
    assert ann.n_unmapped == 0
    raw = b.load_note_annotations("kv279_2", "phrases")["phraseend"].dropna().astype(str)
    n_start = int(raw.isin(["{", "}{"]).sum())
    assert len(ann.phrases) == len(raw) and int(ann.phrases["is_start"].sum()) == n_start
    assert ann.starts == sorted(ann.starts) and len(ann.starts) == len(ann.ends)
    beat = dict(zip(s.notes["id"].astype(str), s.notes["onset_beat"].astype(float), strict=True))
    assert all(abs(beat[i] - x) < 1e-9 for i, x in zip(ann.phrases["id"], ann.phrases["beat"],
                                                        strict=True))
    assert set(ann.cadences["cadence"]) <= {"PAC", "IAC", "HC", "EC", "DC"}
    ct = ann.cadence_table()
    assert list(ct.columns) == ["beat", "cadence"] and ct["beat"].is_monotonic_increasing
    # the same tables from the match-built score (same ids and beats)
    ann0 = b.phrase_annotations(b.load_aligned("kv279_2").score)
    assert ann0.starts == ann.starts and ann0.ends == ann.ends


def test_iter_aligned_stems_filter():
    aps = list(b.iter_aligned(stems={"kv280_2"}))
    assert len(aps) == 1 and aps[0].score.score_id.endswith("kv280_2")
