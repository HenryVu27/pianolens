"""Synthetic checks for the BL-19 staff/hand proxies and the BL-20 local note rate.

Both helpers live in one-off scripts (``scripts/staff_hand_proxies.py``,
``scripts/eval_correctness_density.py``), loaded here by path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shp = _load("staff_hand_proxies")
dens = _load("eval_correctness_density")


def _notes(rows):
    return pd.DataFrame(rows, columns=["onset", "duration", "pitch", "voice", "staff"])


def test_plain_two_staff_texture_has_no_flags():
    # RH melody C5-D5-E5 over LH half notes C3 / G2; hands never cross
    df = _notes([(0, 1, 72, 1, 1), (1, 1, 74, 1, 1), (2, 1, 76, 1, 1),
                 (0, 2, 48, 5, 2), (2, 2, 43, 5, 2)])  # fmt: skip
    fl = shp.note_flags(df)
    assert not fl["at_risk"].any()
    ev = shp.hand_sync_events(fl)
    assert list(ev["onset"]) == [0.0, 2.0]
    assert not ev["at_risk"].any()


def test_cross_voice_note_is_flagged():
    # voice 1 (upper staff) dips into staff 2 for one note, as in Chopin Op. 10/1
    df = _notes([(0, 1, 72, 1, 1), (1, 1, 60, 1, 1), (2, 1, 55, 1, 2), (3, 1, 67, 1, 1),
                 (0, 4, 36, 5, 2)])  # fmt: skip
    fl = shp.note_flags(df)
    assert fl["cross_voice"].tolist() == [False, False, True, False, False]


def test_pitch_crossing_strict_and_loose():
    # LH holds C4-G4 (60, 67); RH plays E4 (64) inside it, then A3 (57) below it
    df = _notes([(0, 2, 60, 5, 2), (0, 2, 67, 5, 2), (0, 1, 64, 1, 1), (1, 1, 57, 1, 1)])
    fl = shp.note_flags(df)
    rh = fl[fl["staff"] == 1]
    assert rh["cross_pitch"].tolist() == [False, True]  # strict: only below the lowest
    assert rh["cross_pitch_loose"].tolist() == [True, True]  # loose: below the highest
    # at onset 0 the only upper-staff note is E4 (64): the lower-staff G4 (67) is above it
    lh = fl[fl["staff"] == 2]
    assert lh["cross_pitch"].tolist() == [False, True]
    assert lh["cross_pitch_loose"].tolist() == [False, True]


def test_capacity_count_and_span():
    six = [(0, 1, p, 1, 1) for p in (60, 62, 64, 65, 67, 69)]  # 6 notes, span 9
    wide = [(1, 1, 60, 1, 1), (1, 1, 77, 1, 1)]  # span 17 > a major tenth
    tenth = [(2, 1, 60, 1, 1), (2, 1, 76, 1, 1)]  # span 16: allowed
    fl = shp.note_flags(_notes(six + wide + tenth))
    assert fl["capacity_count"].tolist() == [True] * 6 + [False] * 4
    assert fl["capacity_span"].tolist() == [False] * 6 + [True, True, False, False]


def test_classify_hand_words():
    assert shp.classify_words("m.s.") == "LH"
    assert shp.classify_words(" M.G. ") == "LH"
    assert shp.classify_words("l.h.") == "LH"
    assert shp.classify_words("m.d.") == "RH"
    assert shp.classify_words("r.h.") == "RH"
    assert shp.classify_words("sopra") == "cross"
    assert shp.classify_words("sotto voce") is None
    assert shp.classify_words("cresc.") is None
    assert shp.classify_words("dolce") is None


def test_local_ioi_even_run_and_chords():
    # 16th notes 80 ms apart, then chords 500 ms apart with a 10 ms spread
    run = np.arange(10) * 0.08
    chords = 1.0 + np.repeat(np.arange(5) * 0.5, 3) + np.tile([0.0, 0.005, 0.01], 5)
    ioi, ch = dens.local_ioi(np.concatenate([run, chords]))
    assert np.allclose(ioi[2:8], 0.08)
    assert len(np.unique(ch[10:])) == 5  # chord spread is grouped
    assert np.allclose(ioi[-3:], 0.5)
    assert list(dens.density_bin(np.array([0.05, 0.08, 0.15, 0.3, np.nan]))) == [
        "<60", "60-100", "100-200", ">200", "none"]  # fmt: skip
