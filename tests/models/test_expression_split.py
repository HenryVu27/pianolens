import pandas as pd
import pytest

from pianolens.models.expression_split import (
    LeakageError,
    alias_conflicts,
    assign_split,
    catalogue_tokens,
    composer_surname,
    leakage_check,
    work_key,
)


def test_work_key_groups_movements():
    assert work_key("beethoven_op27_no2_mv1") == "beethoven_op27_no2"
    assert work_key("beethoven_op110_mv3to4") == "beethoven_op110"
    assert work_key("bach_bwv846_prelude") == work_key("bach_bwv846_fugue") == "bach_bwv846"
    assert work_key("chopin_op10_no3") == "chopin_op10_no3"
    assert work_key("schubert_d960") == work_key("schubert_d960_mv2")
    assert work_key("asap:Haydn/Keyboard_Sonatas_48-2") == "asap:Haydn/Keyboard_Sonatas_48"
    son = "pianocore:X,_Y/Piano_Sonata_in_C/2._Adagio"
    assert work_key(son) == "pianocore:X,_Y/Piano_Sonata_in_C"
    pre = "pianocore:X,_Y/Preludes,_Book_1/3._Voiles"
    assert work_key(pre) == pre


def test_catalogue_tokens_and_surname():
    assert catalogue_tokens("Nocturnes,_Op.9/Nocturne_No.2_in_E_flat") == {"op9", "no2"}
    assert catalogue_tokens("Piano_Sonata_No.21_in_B_flat_major,_D.960") == {"d960", "no21"}
    assert "hobxvi34" in catalogue_tokens("Keyboard_Sonata_in_E_minor,_Hob.XVI:34")
    assert catalogue_tokens("Sonata_in_D_major") == frozenset()
    assert composer_surname("Chopin,_Frédéric") == "chopin"
    assert composer_surname("Frederic_Chopin") == "chopin"


def test_alias_conflicts_subset_rule():
    held = pd.DataFrame({"piece_id": ["chopin_op10_no3"], "composer": ["Chopin"],
                         "text": ["Etudes Op.10 No.3"]})
    cand = pd.DataFrame({
        "piece_id": ["pianocore:a", "pianocore:b", "pianocore:c", "pianocore:d"],
        "composer": ["Chopin,_F", "Chopin,_F", "Chopin,_F", "Liszt,_F"],
        "text": ["12_Etudes,_Op.10", "12_Etudes,_Op.10/No.12", "Waltz_No.3", "Op.10/No.3"],
    })
    c = alias_conflicts(held, cand)
    assert c["piece_id"].tolist() == ["pianocore:a"]  # whole-set id; not No.12, not Liszt


def _pieces():
    return pd.DataFrame({
        "piece_id": ["a_mv1", "a_mv2", "b", "c", "d", "e", "f", "g"],
        "work": ["a", "a", "b", "c", "d", "e", "f", "g"],
    })


def test_assign_split_by_work_and_seeded():
    p = _pieces()
    s1 = assign_split(p, {"a": "test"}, val_frac=2 / 7, seed=0)
    s2 = assign_split(p, {"a": "test"}, val_frac=2 / 7, seed=0)
    assert (s1 == s2).all()
    assert s1["a_mv1"] == s1["a_mv2"] == "test"
    assert (s1 == "val").sum() == 2 and (s1 == "train").sum() == 4


def test_leakage_check_catches_held_out_and_unknown():
    p = _pieces()
    p["split"] = assign_split(p, {"a": "test", "b": "val"}, val_frac=0.0, seed=0).to_numpy()
    ok = leakage_check(p, ["c", "c", "d"])
    assert ok.ok and ok.n_used == 3 and ok.n_pieces == 2
    with pytest.raises(LeakageError):
        leakage_check(p, ["c", "a_mv2"])
    rep = leakage_check(p, ["c", "zzz"], raise_on_error=False)
    assert not rep.ok and rep.unknown == ["zzz"]
    # a train piece that shares a work with a held-out piece is also a violation
    p.loc[p["piece_id"] == "a_mv2", "split"] = "train"
    rep = leakage_check(p, ["a_mv2"], raise_on_error=False)
    assert rep.held_work_in_train == ["a"]


def test_assign_split_val_pool():
    p = _pieces()
    s = assign_split(p, {"a": "test"}, val_frac=0.5, seed=0, val_pool={"b", "c"})
    assert (s == "val").sum() == 1
    assert set(s[s == "val"].index) <= {"b", "c"}


def test_catalogue_range_is_not_a_piece():
    t = catalogue_tokens("The_Well-Tempered_Clavier,_Book_I,_BWV_846-869/No.2,_BWV_847:_Fugue")
    assert "bwv846" not in t and "bwv847" in t
