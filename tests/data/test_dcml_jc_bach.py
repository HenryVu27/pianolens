"""D-12: DCML jc_bach_sonatas loader, label-free score path and leakage tests."""

import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

from pianolens.data import dcml_jc_bach as jc
from pianolens.data.batik_mozart import PhraseAnnotations

R08A = Path(__file__).resolve().parents[2] / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"
needs_data = pytest.mark.skipif(not jc.data_available(), reason="data/raw/dcml_jc_bach absent")
# a movement with repeats, an anacrusis and many labels; a compound-metre one; a minor one
STEMS = ("wa01op05no1a_Allegretto", "wa08op17no2c_Prestissimo", "wa06op05no6a_Grave")


# --------------------------------------------------------------------------- no data needed


def test_piece_id():
    assert jc.piece_id("wa02op05no2b_Andante_di_molto") == "jcbach_op5_no2_mv2"
    assert jc.piece_id("wa12op17no6c_Prestissimo") == "jcbach_op17_no6_mv3"


def test_playthrough_follows_next_column():
    ms = pd.DataFrame({"mc": ["1", "2", "3", "4", "5"],
                       "next": ["2", "1, 3", "4", "5", "3, -1"]})
    assert jc.playthrough(ms) == [1, 2, 1, 2, 3, 4, 5, 3, 4, 5]
    assert jc.playthrough(ms, unfold=False) == [1, 2, 3, 4, 5]


def test_label_facets_are_refused():
    with pytest.raises(ValueError):
        jc._read_label_free("x", "harmonies", jc.DEFAULT_ROOT, [])


# --------------------------------------------------------------------------- data


@needs_data
def test_unfolding_matches_metadata_for_all_movements():
    md = jc.metadata().set_index("piece")
    assert len(md) == 29
    for stem in jc.pieces():
        ms = jc.read_facet(stem, "measures")
        order = jc.playthrough(ms)
        passes = jc._passes(ms, order)
        assert len(order) == int(md.loc[stem, "last_mc_unfolded"]), stem
        total = passes[-1].start + passes[-1].length
        assert float(total) == pytest.approx(float(md.loc[stem, "length_qb_unfolded"])), stem


@needs_data
@pytest.mark.parametrize("stem", STEMS)
def test_score_matches_corpus_counts(stem):
    md = jc.metadata().set_index("piece")
    s = jc.load_score(stem, unfold=False)
    # ties merged, grace notes kept: equals ms3's onset count
    assert len(s.notes) == int(md.loc[stem, "n_onsets"])
    u = jc.load_score(stem)
    assert len(u.measures) == int(md.loc[stem, "last_mc_unfolded"])
    assert u.part is not None and u.piece_id.startswith("jcbach_op")
    assert len(u.notes) >= len(s.notes)
    assert all(re.fullmatch(r"n\d+-\d+", i) for i in u.notes["id"].astype(str))


@needs_data
@pytest.mark.parametrize("stem", STEMS)
def test_phrase_annotations_map_every_label(stem):
    lab = jc.load_labels(stem)
    n_end = int(lab["phraseend"].isin(["}", "}{"]).sum())
    n_cad = int((lab["cadence"] != "").sum())
    s = jc.load_score(stem, unfold=False)
    pa = jc.phrase_annotations(s)
    assert isinstance(pa, PhraseAnnotations) and pa.n_unmapped == 0
    assert int(pa.phrases["is_end"].sum()) == n_end and len(pa.cadences) == n_cad
    assert set(pa.cadences["cadence"]) <= set(jc.CADENCE_TYPES)
    onsets = set(s.notes["onset_beat"].astype(float).round(6))
    assert pa.n_off_onset == sum(round(b, 6) not in onsets
                                 for b in [*pa.phrases["beat"], *pa.cadences["beat"]])
    assert pa.n_off_onset == 0
    u = jc.load_score(stem)
    pu = jc.phrase_annotations(u)
    assert len(pu.ends) >= len(pa.ends) and pu.n_unmapped == 0
    lo, hi = float(u.notes["onset_beat"].min()), float(u.notes["onset_beat"].max())
    assert all(lo - 1e-6 <= b <= hi + 1e-6 for b in pu.ends)
    assert set(pu.cadence_table().columns) == {"beat", "cadence"}


# --------------------------------------------------------------------------- leakage


def _text_objects(part):
    """Every text value the partitura part carries (directions, words, any object with a
    ``text`` attribute)."""
    import partitura as pt

    out = []
    for o in part.iter_all(pt.score.TimedObject, include_subclasses=True):
        for attr in ("text", "raw_text", "name", "label"):
            v = getattr(o, attr, None)
            if isinstance(v, str) and v:
                out.append((type(o).__name__, attr, v))
    return out


def _label_hits(text: str, stem: str) -> list[str]:
    labels = {v for v in jc.label_strings(stem, min_len=3)
              if not re.fullmatch(r"[\d.,\s-]+", v)}
    return sorted(v for v in labels
                  if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text))


@needs_data
@pytest.mark.parametrize("stem", STEMS)
def test_score_path_reads_no_label_file(stem):
    s = jc.load_score(stem)
    files = s.meta["source_files"]
    assert files and all(f.split("/")[0] in jc.LABEL_FREE_FACETS or f.startswith("metadata.tsv")
                         for f in files)
    assert not any("harmonies" in f or "MS3" in f or "reviewed" in f for f in files)


@needs_data
@pytest.mark.parametrize("stem", STEMS)
def test_renderer_input_has_no_label_objects_or_strings(stem):
    import partitura as pt

    s = jc.load_score(stem)
    for cls in ("ChordSymbol", "RomanNumeral", "Harmony"):
        c = getattr(pt.score, cls, None)
        if c is not None:
            assert not list(s.part.iter_all(c, include_subclasses=True)), cls
    texts = _text_objects(s.part)
    assert texts  # measures, dynamics, the title
    blob = "\n".join(v for _, _, v in texts)
    assert _label_hits(blob, stem) == []
    # the facets the score is built from carry no label column at all
    for facet in jc.LABEL_FREE_FACETS:
        cols = set(jc.read_facet(stem, facet).columns)
        assert not cols & {"label", "phraseend", "cadence", "numeral", "chord", "localkey"}, facet


def _r08a_render():
    if not (R08A / "common.py").is_file():
        pytest.skip("R-08a renderer absent")
    sys.path.insert(0, str(R08A))
    spec = importlib.util.spec_from_file_location("r08a_common", R08A / "common.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["r08a_common"] = mod
    spec.loader.exec_module(mod)
    return mod.render


@needs_data
@pytest.mark.parametrize("stem", STEMS)
def test_r08a_rendering_contains_no_label_string(stem):
    render = _r08a_render()
    s = jc.load_score(stem)
    txt = render(s, "X").text
    assert "BAR 1 " in txt and txt.rstrip().endswith("END")
    assert _label_hits(txt, stem) == []
    for w in ("cadenc", "phrase", "harmon", "PAC", "HC}"):
        assert w not in txt


@needs_data
def test_leakage_check_catches_a_planted_label():
    """Positive control: a label written into the score is found by the same check."""
    import partitura as pt

    render = _r08a_render()
    stem = STEMS[0]
    s = jc.load_score(stem)
    planted = next(v for v in sorted(jc.label_strings(stem, min_len=4)) if "|" in v)
    s.part.add(pt.score.Words(planted), 0)
    assert planted in _label_hits(render(s, "X").text, stem)
