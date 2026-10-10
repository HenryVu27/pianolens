"""Synthetic checks for the BL-19b hand rules and agreement statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pianolens.features import hand_proxies as hp


def test_staff_and_pitch_rules():
    assert list(hp.staff_hand([1, 2, 3])) == ["R", "L", ""]
    assert list(hp.pitch_split_hand([59, 60, 72])) == ["L", "R", "R"]
    assert list(hp.pitch_split_hand([64], split=65)) == ["L"]


def test_voice_hand_keeps_cross_staff_voice_in_its_hand():
    # voice 1 lives on staff 1 but dips into staff 2 once; voice 5 is on staff 2;
    # voice 3 is split evenly, so ties keep the note's own staff
    d = pd.DataFrame({"voice": [1, 1, 1, 1, 5, 5, 3, 3],
                      "staff": [1, 1, 1, 2, 2, 2, 1, 2],
                      "is_grace": [False] * 8})  # fmt: skip
    assert list(hp.voice_hand(d)) == ["R", "R", "R", "R", "L", "L", "R", "L"]


def test_voice_hand_ignores_grace_and_other_staves():
    d = pd.DataFrame({"voice": [1, 1, 1, 1], "staff": [2, 2, 1, 3],
                      "is_grace": [True, True, False, False]})  # fmt: skip
    assert list(hp.voice_hand(d)) == ["R", "R", "R", ""]


def test_mismatch_ignores_unlabelled():
    rule = np.array(["R", "R", "L", "L"])
    lab = np.array(["R", "L", "", "L"])
    assert hp.mismatch(rule, lab) == 1 / 3
    assert np.isnan(hp.mismatch(rule, np.array(["", "", "", ""])))


def test_event_mismatch_needs_both_staves():
    notes = pd.DataFrame({
        "ev": [0, 0, 1, 1, 2, 2],
        "staff": [1, 2, 1, 2, 1, 1],
        "rule": ["R", "L", "R", "L", "R", "R"],
        "hand": ["R", "L", "R", "R", "L", "R"],
    })  # fmt: skip
    ev = hp.event_mismatch(notes, ["ev"])
    assert list(ev["ev"]) == [0, 1]  # event 2 has one staff only
    assert list(ev["affected"]) == [False, True]


def test_noise_correction_and_wilson():
    assert hp.noise_corrected(0.01, 0.01) == 0.0
    assert abs(hp.noise_corrected(0.05, 0.0) - 0.05) < 1e-12
    lo, hi = hp.wilson(12, 1588)
    assert lo < 12 / 1588 < hi and 0 < lo and hi < 0.02


def test_cluster_ratio_ci_pooled_value_and_degenerate_interval():
    est, lo, hi = hp.cluster_ratio_ci(np.array([1, 1, 1]), np.array([10, 10, 10]), 200, 0)
    assert est == 0.1 and lo == hi == 0.1
    est, lo, hi = hp.cluster_ratio_ci(np.array([0, 10]), np.array([100, 100]), 500, 0)
    assert est == 0.05 and lo < 0.05 < hi


def test_t_interval_and_mean_ci():
    m, lo, hi = hp.t_interval(np.array([1.0, 2.0, 3.0]))
    assert m == 2.0 and lo < 2.0 < hi
    m, lo, hi = hp.cluster_mean_ci(np.array([0.0, 1.0, np.nan]), 300, 1, stat=np.median)
    assert m == 0.5 and 0.0 <= lo <= hi <= 1.0
