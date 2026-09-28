"""D-13: shared DCML loader on the five R-08d Romantic corpora (label-free score path, repeat
unfolding, phrase tables, leakage). The J. C. Bach wrapper keeps its own tests
(``test_dcml_jc_bach.py``)."""

import importlib.util
import re
import sys
from fractions import Fraction
from pathlib import Path

import pandas as pd
import pytest

from pianolens.data import dcml
from pianolens.data.batik_mozart import PhraseAnnotations

R08A = Path(__file__).resolve().parents[2] / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"

# one or two movements per corpus: repeats with voltas, D.S. al Fine, coda, anacrusis
STEMS = {
    "chopin_mazurkas": ("BI77-3op17-3", "BI16-2"),
    "grieg_lyric_pieces": ("op38n08", "op12n01"),
    "tchaikovsky_seasons": ("op37a12",),
    "schumann_kinderszenen": ("n07", "n05"),
    "liszt_pelerinage": ("162.01_Gondoliera",),
}
CASES = [(c, s) for c, ss in STEMS.items() for s in ss]
# movements whose unfolding cannot equal metadata.tsv: ms3 leaves it empty (dal segno) or
# stops at the Fine before the D.C. is played (bars in playing order, checked by hand)
HAND_UNFOLDED = {"BI16-2": 64, "BI73": 62, "BI61-5op07-5": 36, "BI77-3op17-3": 174}
# grace notes marked as tie continuations (n07, 160.02) and cross-voice ties (161.07)
ORPHAN_TIES = {"n07": 3, "160.02_Au_Lac_de_Wallenstadt": 1, "161.04_Sonetto_47_del_Petrarca": 1,
               "161.07_Apres_une_lecture_du_Dante": 2}


def needs(corpus):
    return pytest.mark.skipif(not dcml.data_available(corpus),
                              reason=f"data/raw/dcml_{corpus} absent")


def skip_absent(corpus):
    if not dcml.data_available(corpus):
        pytest.skip(f"data/raw/dcml_{corpus} absent")


# --------------------------------------------------------------------------- no data needed


@pytest.mark.parametrize(("corpus", "stem", "pid"), [
    ("chopin_mazurkas", "BI105-2op30-2", "chopin_op30_no2"),
    ("chopin_mazurkas", "BI60-1op06-1", "chopin_op6_no1"),
    ("chopin_mazurkas", "BI16-1", "chopin_b16_no1"),
    ("chopin_mazurkas", "BI134", "chopin_b134"),
    ("grieg_lyric_pieces", "op12n01", "grieg_op12_no1"),
    ("tchaikovsky_seasons", "op37a06", "tchaikovsky_op37a_no6"),
    ("schumann_kinderszenen", "n07", "schumann_op15_no7"),
    ("liszt_pelerinage", "162.01_Gondoliera", "liszt_s162_no1"),
    ("jc_bach", "wa02op05no2b_Andante_di_molto", "jcbach_op5_no2_mv2"),
])  # fmt: skip
def test_piece_ids(corpus, stem, pid):
    assert dcml.piece_id(corpus, stem) == pid


def test_corpus_registry():
    assert set(dcml.ROMANTIC) < set(dcml.CORPORA)
    assert dcml.get_corpus("dcml_grieg_lyric_pieces").name == "grieg_lyric_pieces"
    for c in dcml.CORPORA.values():
        assert len(c.commit) == 40 and c.url.startswith("https://github.com/DCMLab/")
    with pytest.raises(KeyError):
        dcml.get_corpus("chopin_nocturnes")
    with pytest.raises(ValueError):
        dcml._read_label_free("grieg_lyric_pieces", "x", "harmonies", None, [])


def test_clean_text():
    assert dcml.clean_text('<font size="9"/><font face="Times"/><i>a tempo</i>') == "a tempo"
    assert dcml.clean_text("\U0001D158\U0001D165=144") == "quarter=144"
    assert dcml.clean_text("\U0001D158\U0001D165\U0001D16E=132") == "eighth=132"
    assert dcml.clean_text("♮") == ""  # a natural sign alone
    assert dcml.clean_text(" <font face='ScoreText'/>") == ""  # private-use glyph
    assert dcml.clean_text("TempoI°") == dcml.clean_text("Tempo I.") == "Tempo primo"
    assert dcml.clean_text("Temp. I., tranq.") == "Tempo primo, tranq."
    assert dcml.clean_text("una chorda") == "una corda"
    assert dcml.clean_text("tres chorde, piu crescendo") == "tres corde, piu crescendo"


def _measures(rows):
    cols = ["mc", "next", "markers", "jump_bwd", "play_until"]
    return pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows])


def test_playthrough_dal_segno_al_fine_takes_the_fine_ending():
    # 1 2(segno) 3 |: 4 5 :|1. 6(Fine) |2. 7 8 D.S. al Fine
    ms = _measures([("1", "2", "", "", ""), ("2", "3", "segno", "", ""),
                    ("3", "4", "", "", ""), ("4", "5", "", "", ""), ("5", "6, 7", "", "", ""),
                    ("6", "4", "fine", "", ""), ("7", "8", "", "", ""),
                    ("8", "2", "", "segno", "fine")])  # fmt: skip
    assert dcml.playthrough(ms) == [1, 2, 3, 4, 5, 6, 4, 5, 7, 8, 2, 3, 4, 5, 6]


def test_playthrough_fine_before_the_da_capo_does_not_end_the_piece():
    # ms3 writes next = -1 at the Fine; the Fine only counts after the D.C.
    ms = _measures([("1", "2", "", "", ""), ("2", "-1", "fine", "", ""),
                    ("3", "4", "", "", ""), ("4", "1", "", "start", "fine")])
    assert dcml.playthrough(ms) == [1, 2, 3, 4, 1, 2]


def test_playthrough_senza_fine_plays_the_segno_once():
    ms = _measures([("1", "2", "", "", ""), ("2", "3", "segno", "", ""),
                    ("3", "2", "", "segno", "/")])
    assert dcml.playthrough(ms) == [1, 2, 3, 2, 3]


def test_tie_across_a_gap_is_merged():
    notes = pd.DataFrame({
        "mc": ["1", "2"], "mc_onset": ["0", "1/4"], "duration": ["3/4", "1/2"],
        "name": ["C4", "C4"], "midi": ["60", "60"], "octave": ["4", "4"],
        "staff": ["1", "1"], "voice": ["1", "1"], "gracenote": ["", ""], "tied": ["1", "-1"],
    })  # fmt: skip
    passes = [dcml._Pass(1, 1, Fraction(0), Fraction(4)), dcml._Pass(2, 1, Fraction(4),
                                                                     Fraction(4))]
    out, orphans, gap = dcml._linear_notes(notes, passes, suffix=False)
    assert len(out) == 1 and orphans == 0 and gap == 1
    assert out[0].dur == Fraction(4 + 1 + 2)  # to the end of the continuation


# --------------------------------------------------------------------------- data


@pytest.mark.parametrize("corpus", dcml.ROMANTIC)
def test_unfolding_matches_metadata(corpus):
    skip_absent(corpus)
    md = dcml.metadata(corpus).set_index("piece")
    for stem in dcml.pieces(corpus):
        ms = dcml.read_facet(corpus, stem, "measures")
        order = dcml.playthrough(ms)
        if stem in HAND_UNFOLDED:
            assert len(order) == HAND_UNFOLDED[stem], stem
            continue
        passes = dcml._passes(ms, order)
        total = passes[-1].start + passes[-1].length
        assert len(order) == int(float(md.loc[stem, "last_mc_unfolded"])), stem
        assert float(total) == pytest.approx(float(md.loc[stem, "length_qb_unfolded"]),
                                             abs=0.01), stem


@pytest.mark.parametrize(("corpus", "stem"), CASES)
def test_score_matches_corpus_counts(corpus, stem):
    skip_absent(corpus)
    md = dcml.metadata(corpus).set_index("piece")
    s = dcml.load_score(corpus, stem, unfold=False)
    # ties merged, grace notes kept: ms3's onset count, bar the known orphan tie heads
    assert len(s.notes) == int(md.loc[stem, "n_onsets"]) + ORPHAN_TIES.get(stem, 0)
    assert s.meta["n_orphan_ties"] == ORPHAN_TIES.get(stem, 0)
    u = dcml.load_score(corpus, stem)
    assert u.meta["unfold_validated"] is (stem not in HAND_UNFOLDED)
    assert u.part is not None and u.piece_id == dcml.piece_id(corpus, stem)
    assert u.score_id == f"dcml_{corpus}:{stem}"
    assert len(u.notes) >= len(s.notes)
    assert all(re.fullmatch(r"n\d+-\d+", i) for i in u.notes["id"].astype(str))


@pytest.mark.parametrize(("corpus", "stem"), CASES)
def test_phrase_annotations_map_every_label(corpus, stem):
    skip_absent(corpus)
    lab = dcml.load_labels(corpus, stem)
    n_end = int(lab["phraseend"].isin(["}", "}{"]).sum())
    n_cad = int((lab["cadence"] != "").sum())
    s = dcml.load_score(corpus, stem, unfold=False)
    pa = dcml.phrase_annotations(s)
    assert isinstance(pa, PhraseAnnotations) and pa.n_unmapped == 0 and pa.n_other == 0
    assert int(pa.phrases["is_end"].sum()) == n_end and len(pa.cadences) == n_cad
    assert set(pa.cadences["cadence"]) <= set(dcml.CADENCE_TYPES)
    onsets = set(s.notes["onset_beat"].astype(float).round(6))
    assert pa.n_off_onset == sum(round(b, 6) not in onsets
                                 for b in [*pa.phrases["beat"], *pa.cadences["beat"]])
    u = dcml.load_score(corpus, stem)
    pu = dcml.phrase_annotations(u)
    assert len(pu.ends) >= len(pa.ends) and pu.n_unmapped == 0
    lo, hi = float(u.notes["onset_beat"].min()), float(u.notes["onset_beat"].max())
    assert all(lo - 1e-6 <= b <= hi + 1e-6 for b in pu.ends)


@needs("chopin_mazurkas")
def test_unlabelled_movement_is_listed_but_not_labelled():
    all_, lab = dcml.pieces("chopin_mazurkas"), dcml.pieces("chopin_mazurkas", labelled=True)
    assert len(all_) == 56 and len(lab) == 55
    assert set(all_) - set(lab) == {"BI105-1op30-1"}


# --------------------------------------------------------------------------- leakage


def _label_hits(text: str, corpus: str, stem: str) -> list[str]:
    labels = {v for v in dcml.label_strings(corpus, stem, min_len=3)
              if not re.fullmatch(r"[\d.,\s-]+", v)}
    return sorted(v for v in labels
                  if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text))


def _r08a():
    if not (R08A / "common.py").is_file():
        pytest.skip("R-08a renderer absent")
    sys.path.insert(0, str(R08A))
    mods = {}
    for name in ("common", "render"):
        spec = importlib.util.spec_from_file_location(name, R08A / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods["common"].render, mods["render"]


@pytest.mark.parametrize(("corpus", "stem"), CASES)
def test_score_path_reads_no_label_file(corpus, stem):
    skip_absent(corpus)
    s = dcml.load_score(corpus, stem)
    files = s.meta["source_files"]
    assert files and all(f.split("/")[0] in dcml.LABEL_FREE_FACETS
                         or f.startswith("metadata.tsv") for f in files)
    assert not any("harmonies" in f or "MS3" in f or "reviewed" in f for f in files)
    for facet in dcml.LABEL_FREE_FACETS:
        cols = set(dcml.read_facet(corpus, stem, facet).columns)
        assert not cols & {"label", "phraseend", "cadence", "numeral", "chord", "localkey",
                           "special", "alt_label"}, facet


@pytest.mark.parametrize(("corpus", "stem"), CASES)
def test_r08a_rendering_has_no_label_banned_word_or_roman_numeral(corpus, stem):
    import partitura as pt

    skip_absent(corpus)
    render, voc = _r08a()
    s = dcml.load_score(corpus, stem)
    for cls in ("ChordSymbol", "RomanNumeral", "Harmony"):
        c = getattr(pt.score, cls, None)
        if c is not None:
            assert not list(s.part.iter_all(c, include_subclasses=True)), cls
    txt = render(s, "X").text
    assert "BAR 1 " in txt and txt.rstrip().endswith("END")
    assert _label_hits(txt, corpus, stem) == []
    assert [w for w in voc.BANNED_WORDS if re.search(w, txt, re.I)] == []
    assert not list(voc.ROMAN.finditer(txt))
    # the movement title names the piece and is never rendered
    title = str(dcml.metadata(corpus).set_index("piece").loc[stem, "movementTitle"])
    if title and title != "nan" and len(title) > 4:
        assert title not in txt


@pytest.mark.parametrize("corpus", dcml.ROMANTIC)
def test_leakage_check_catches_a_planted_label(corpus):
    """Positive control: a label written into the score is found by the same check."""
    import partitura as pt

    skip_absent(corpus)
    render, _ = _r08a()
    stem = STEMS[corpus][0]
    s = dcml.load_score(corpus, stem)
    planted = next(v for v in sorted(dcml.label_strings(corpus, stem, min_len=4))
                   if re.search(r"[IViv]", v) and not re.fullmatch(r"[\d.,\s-]+", v))
    s.part.add(pt.score.Words(planted), 0)
    assert planted in _label_hits(render(s, "X").text, corpus, stem)
