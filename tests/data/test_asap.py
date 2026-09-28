import numpy as np
import pytest

from pianolens.data import asap

pytestmark = pytest.mark.skipif(
    not asap.data_available(), reason="(n)ASAP not downloaded to data/raw/asap"
)


def test_piece_and_performer_ids():
    assert asap.asap_piece_id("Chopin", "Etudes_op_10_3") == "chopin_op10_no3"
    assert asap.asap_piece_id("Beethoven", "Piano_Sonatas_17-1") == "beethoven_op31_no2_mv1"
    assert asap.asap_piece_id("Beethoven", "Piano_Sonatas_31-3_4") == "beethoven_op110_mv3to4"
    assert asap.asap_piece_id("Chopin", "Sonata_2_3rd") == "chopin_op35_mv3"
    assert asap.asap_piece_id("Haydn", "Keyboard_Sonatas_48-2").startswith("asap:")
    assert asap.asap_performer_id("X/Shi05M.mid") == "asap:shi"
    assert asap.asap_performer_id("X/Na_2009_02.mid") == "asap:na"
    assert asap.asap_performer_id("X/Bult-ItoS02M.mid") == "asap:bultitos"


def test_index():
    idx = asap.asap_index()
    assert len(idx) == 1066
    assert idx["performance_id"].is_unique


def test_load_one_aligned_performance():
    idx = asap.asap_index()
    row = idx[idx["midi_performance"] == "Chopin/Etudes_op_10/3/SunMeiting08.mid"].iloc[0]
    (ap,) = list(asap.iter_asap(index=idx.loc[[row.name]]))
    p, s, a = ap.performance, ap.score, ap.alignment
    assert p.piece_id == s.piece_id == "chopin_op10_no3"
    assert p.provenance == "disklavier"
    assert len(p.pedal) > 0
    assert a is not None and a.ground_truth
    # every matched id resolves on both sides
    m = a.matches
    assert np.isin(m["performance_id"], p.notes["id"]).all()
    assert np.isin(m["score_id"], s.notes["id"]).mean() > 0.99
    # matched pitches agree
    ppitch = dict(zip(p.notes["id"], p.notes["pitch"], strict=True))
    spitch = dict(zip(s.notes["id"], s.notes["pitch"], strict=True))
    both = [(ppitch[pi], spitch[si]) for si, pi in zip(m["score_id"], m["performance_id"],
                                                        strict=True) if si in spitch]
    assert np.mean([x == y for x, y in both]) > 0.99
    assert (s.note_measures() >= 0).all()


def test_schubert_d899_alignment_path_is_repaired():
    idx = asap.asap_index()
    row = idx[idx["midi_performance"] == "Schubert/Impromptu_op.90_D.899/3/Hou06M.mid"].iloc[0]
    assert "Impromptu_op_note_alignments" in row["note_alignments"]  # upstream bug still there
    assert asap.load_asap_alignment(row) is not None
