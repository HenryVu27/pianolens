"""Known-answer tests for pianolens.features.score_basis and pianolens.features.shaping (F-05)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import partitura as pt
import pytest

from pianolens.data import types
from pianolens.features.score_basis import (
    BasisConfig,
    base_note_id,
    metrical_strength,
    score_basis,
)
from pianolens.features.shaping import (
    ShapingConfig,
    channel_data,
    dynamic_compliance,
    pooled_structural_coherence,
    repeated_material,
    shaping,
    structural_coherence,
    voicing,
)

PERF_DTYPE = [("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
              ("velocity", "i4"), ("id", "U32")]  # fmt: skip
_SPELL = {
    0: ("C", None), 1: ("C", 1), 2: ("D", None), 3: ("D", 1), 4: ("E", None), 5: ("F", None),
    6: ("F", 1), 7: ("G", None), 8: ("G", 1), 9: ("A", None), 10: ("A", 1), 11: ("B", None),
}  # fmt: skip
Q = 4  # divisions per quarter


def rand_pitches(n, seed=0, lo=60, hi=84):
    rng = np.random.default_rng(seed)
    out = [int(rng.integers(lo, hi))]
    while len(out) < n:
        p = int(rng.integers(lo, hi))
        if p != out[-1]:
            out.append(p)
    return out


def build_part(events, *, ts=(4, 4), extras=()):
    """``events``: (onset_q, duration_q, pitch, voice, articulations) tuples.
    ``extras``: (object, start_q, end_q or None)."""
    part = pt.score.Part("P0", "piano", quarter_duration=Q)
    part.add(pt.score.TimeSignature(*ts), 0)
    for i, (on, du, p, voice, arts) in enumerate(events):
        step, alter = _SPELL[p % 12]
        note = pt.score.Note(step=step, octave=p // 12 - 1, alter=alter, id=f"n{i}",
                             voice=voice, articulations=arts or None)
        part.add(note, start=int(round(on * Q)), end=int(round((on + du) * Q)))
    for obj, s, e in extras:
        part.add(obj, int(round(s * Q)), None if e is None else int(round(e * Q)))
    pt.score.add_measures(part)
    return part


def melody_events(n_bars=16, step_q=0.5, seed=0, lo=60, hi=84):
    n = int(n_bars * 4 / step_q)
    ps = rand_pitches(n, seed, lo, hi)
    return [(i * step_q, step_q, p, 1, None) for i, p in enumerate(ps)]


def manual_ap(part, *, vel=None, onset=None, dur=None, drop=()):
    """AlignedPerformance with a hand-made alignment (score note i <-> performed note i).

    ``vel`` / ``onset`` / ``dur``: functions of the score DataFrame row arrays
    (``beat``, ``pitch``, ``duration_beat``) returning arrays. Default: 120 BPM deadpan,
    velocity 64, key-down duration 0.9 of the notated value. ``drop``: score indices left
    unplayed (deletions).
    """
    score = types.score_from_partitura(part, score_id="synth:s", piece_id=types.PieceId("synth"),
                                       keep_part=True)
    sn = score.notes
    beat, pitch, dbeat = sn["onset_beat"], sn["pitch"], sn["duration_beat"]
    n = len(sn)
    on = onset(beat) if onset else beat * 0.5
    ve = vel(beat, pitch) if vel else np.full(n, 64)
    du = dur(dbeat) if dur else 0.9 * dbeat * 0.5
    keep = [i for i in range(n) if i not in set(drop)]
    pn = np.zeros(len(keep), dtype=PERF_DTYPE)
    pn["onset_sec"] = np.asarray(on)[keep]
    pn["duration_sec"] = np.asarray(du)[keep]
    pn["pitch"] = pitch[keep]
    pn["velocity"] = np.clip(np.round(np.asarray(ve)[keep]), 1, 127)
    pn["id"] = [f"p{i}" for i in keep]
    perf = types.Performance("synth:p", types.PieceId("synth"), types.PerformerId("synth:x"),
                             "synthetic", pn, np.zeros(0, types.PEDAL_DTYPE), "synth")
    rows = [("match", str(sn["id"][i]), f"p{i}") if i in keep
            else ("deletion", str(sn["id"][i]), "") for i in range(n)]
    al = types.Alignment(np.array(rows, dtype=types.ALIGNMENT_DTYPE), "synth:s", "synth:p",
                         False, "test")
    return types.AlignedPerformance(perf, score, al)


# --------------------------------------------------------------------------- score basis


def test_metrical_strength_known_values():
    pos = np.array([0, 1, 2, 3, 0.5, 0.25])
    assert metrical_strength(pos, np.full(6, 4), np.full(6, 4)).tolist() == \
        [1, 0.5, 0.75, 0.5, 0.25, 0]
    pos = np.array([0, 1, 2, 3, 4, 5, 0.5])
    assert metrical_strength(pos, np.full(7, 6), np.full(7, 8)).tolist() == \
        [1, 0.25, 0.25, 0.5, 0.25, 0.25, 0]
    assert metrical_strength(np.array([0, 1, 2]), np.full(3, 3), np.full(3, 4)).tolist() == \
        [1, 0.5, 0.5]
    assert metrical_strength(np.array([6.0, 3.0]), np.full(2, 12), np.full(2, 8)).tolist() == \
        [0.75, 0.5]


def test_base_note_id():
    assert base_note_id("n12-2") == ("n12", 2)
    assert base_note_id("n12") == ("n12", 0)


def test_basis_markings_and_columns():
    ev = melody_events(8)
    ev[8] = (ev[8][0], ev[8][1], ev[8][2], 1, ["staccato"])
    ev[9] = (ev[9][0], ev[9][1], ev[9][2], 1, ["accent"])
    extras = [
        (pt.score.ConstantLoudnessDirection("p", "p"), 0, None),
        (pt.score.IncreasingLoudnessDirection("crescendo", "crescendo", wedge=True), 8, 16),
        (pt.score.ConstantLoudnessDirection("f", "f"), 16, None),
        (pt.score.ImpulsiveLoudnessDirection("sf", "sf"), 20, None),
        (pt.score.Fermata(), 31.5, None),
    ]
    b = score_basis(types.score_from_partitura(build_part(ev, extras=extras), score_id="s",
                                               piece_id=types.PieceId("x"), keep_part=True))
    n = b.notes.set_index("beat")
    assert b.meta["has_part"] and b.meta["tension"] == "ok"
    assert n.loc[0.0, "dyn_level"] == -1 and n.loc[15.5, "dyn_level"] == -1
    assert n.loc[16.0, "dyn_level"] == 1 and n.loc[31.5, "dyn_level"] == 1
    assert n.loc[8.0, "cresc_ramp"] == pytest.approx(0)
    assert n.loc[12.0, "cresc_ramp"] == pytest.approx(0.5)
    assert n.loc[12.0, "in_cresc"] == 1 and n.loc[4.0, "in_cresc"] == 0
    assert n.loc[20.0, "sf_accent"] == 1 and n.loc[20.5, "sf_accent"] == 0
    assert n.loc[4.0, "staccato"] == 1 and n.loc[4.5, "accent"] == 1
    assert n["staccato"].sum() == 1
    assert n.loc[31.5, "fermata"] == 1 and n.loc[31.0, "pre_fermata"] == 1
    assert n.loc[0.0, "metrical_strength"] == 1 and n.loc[2.0, "metrical_strength"] == 0.75
    assert n.loc[1.5, "metrical_strength"] == 0.25
    for cols in b.groups.values():
        assert np.isfinite(b.notes[cols].to_numpy()).all()
    assert list(b.dynamics["kind"]) == ["level", "cresc", "level", "impulsive"]
    assert len(b.onsets) == len(b.notes)  # monophonic


def test_basis_without_part_and_anacrusis():
    # hand-built score: 1-beat pickup, then 4/4 bars; no partitura part
    beats = np.arange(0, 9, 0.5)
    sn = np.zeros(len(beats), dtype=[("onset_beat", "f8"), ("duration_beat", "f8"),
                                     ("onset_quarter", "f8"), ("duration_quarter", "f8"),
                                     ("pitch", "i4"), ("id", "U8"), ("is_grace", "?"),
                                     ("ts_beats", "i4"), ("ts_beat_type", "i4")])
    sn["onset_beat"] = sn["onset_quarter"] = beats
    sn["duration_beat"] = sn["duration_quarter"] = 0.5
    sn["pitch"] = rand_pitches(len(beats))
    sn["id"] = [f"n{i}" for i in range(len(beats))]
    sn["ts_beats"], sn["ts_beat_type"] = 4, 4
    ms = np.zeros(3, dtype=types.MEASURE_DTYPE)
    ms["number"] = [0, 1, 2]
    ms["start_quarter"] = [0, 1, 5]
    ms["end_quarter"] = [1, 5, 9]
    b = score_basis(types.Score("s", types.PieceId("x"), sn, ms))
    n = b.notes.set_index("beat")
    assert not b.meta["has_part"]
    assert n.loc[0.0, "beat_in_bar"] == 3 and n.loc[0.0, "metrical_strength"] == 0.5
    assert n.loc[1.0, "metrical_strength"] == 1.0 and n.loc[3.0, "metrical_strength"] == 0.75
    assert (b.notes["dyn_level"] == 0).all()


def test_skyline_melody_ignores_notes_under_a_held_melody_note():
    # melody half notes on top, eighth-note accompaniment below
    ev = []
    for bar in range(4):
        for k in range(2):
            ev.append((bar * 4 + 2 * k, 2.0, 76 + k, 1, None))
        for j in range(8):
            ev.append((bar * 4 + 0.5 * j, 0.5, 60 + (j % 4), 2, None))
    b = score_basis(types.score_from_partitura(build_part(ev), score_id="s",
                                               piece_id=types.PieceId("x"), keep_part=True))
    top = b.notes[b.notes["is_top"] > 0]
    assert set(top["pitch"]) == {76, 77}
    assert len(top) == 8
    on = b.onsets.set_index("beat")
    assert on.loc[0.5, "melody_pitch_rel_oct"] == on.loc[0.0, "melody_pitch_rel_oct"]


def test_phrase_proxy_finds_rests_and_external_overrides():
    # 4-bar phrases of eighths, each ending with a quarter rest
    ev = []
    ps = rand_pitches(200)
    k = 0
    for ph in range(4):
        for i in range(30):  # 15 beats of eighths, then 1 beat of rest
            ev.append((ph * 16 + i * 0.5, 0.5, ps[k], 1, None))
            k += 1
    sc = types.score_from_partitura(build_part(ev), score_id="s", piece_id=types.PieceId("x"),
                                    keep_part=True)
    b = score_basis(sc)
    assert b.phrases["start_beat"].tolist() == [0, 16, 32, 48]
    n = b.notes.set_index("beat")
    assert n.loc[16.0, "phrase_start"] == 1 and n.loc[14.5, "phrase_end"] == 1
    assert n.loc[16.0, "phrase_pos"] == -1 and n.loc[14.5, "phrase_pos"] == 1
    assert n.loc[16.0, "boundary_strength"] >= 1.5
    ext = score_basis(sc, phrase_boundaries_beats=[0, 32])
    assert ext.phrases["start_beat"].tolist() == [0, 32]
    assert set(ext.phrases["source"]) == {"external"}
    # long phrases are split to at most phrase_max_bars
    short = score_basis(sc, phrase_boundaries_beats=[0],
                        config=BasisConfig(phrase_max_bars=4))
    assert len(short.phrases) == 4


# --------------------------------------------------------------------------- coherence


def metric_velocity(beat, pitch):
    bib = np.mod(beat, 4)
    return 40 + 60 * metrical_strength(bib, np.full(len(beat), 4), np.full(len(beat), 4))


def test_coherence_velocity_linear_in_metrical_strength_is_one():
    ap = manual_ap(build_part(melody_events(16)), vel=metric_velocity)
    res = structural_coherence(ap)
    assert res.r2("velocity") > 0.99
    assert res.r2("velocity", "r2_no_markings") > 0.99
    s = res.summary.set_index("channel")
    assert s.loc["velocity", "n"] == 128
    # deadpan timing / constant articulation: nothing to explain -> NaN, not a crash
    assert np.isnan(s.loc["timing", "r2"]) and np.isnan(s.loc["articulation", "r2"])
    bars = res.bars[res.bars["channel"] == "velocity"]
    assert len(bars) == 16 and (bars["r2_local"] > 0.98).all()
    assert abs(res.coefs.loc["velocity", "metrical_strength"]) > 1


def test_coherence_random_velocity_is_about_zero():
    rng = np.random.default_rng(1)
    r2 = []
    for seed in range(5):
        rng = np.random.default_rng(seed)
        ap = manual_ap(build_part(melody_events(32, seed=seed)),
                       vel=lambda b, p, rng=rng: rng.normal(64, 12, len(b)))
        r2.append(structural_coherence(ap).r2("velocity"))
    assert np.mean(r2) < 0.05 and max(r2) < 0.15


def test_coherence_smooth_unstructured_velocity_is_not_inflated():
    """A slow random walk has no score structure; bar-block CV must not credit it."""
    r2 = []
    for seed in range(5):
        rng = np.random.default_rng(10 + seed)

        def walk(b, p, rng=rng):
            steps = rng.normal(0, 1.5, len(b))
            return 64 + np.cumsum(steps) - np.cumsum(steps).mean()
        ap = manual_ap(build_part(melody_events(32, seed=seed)), vel=walk)
        r2.append(structural_coherence(ap).r2("velocity"))
    assert np.mean(r2) < 0.15


def test_coherence_markings_explain_velocity_only_with_markings():
    extras = []
    for k in range(8):  # alternate p / f every 2 bars
        text = "p" if k % 2 == 0 else "f"
        extras.append((pt.score.ConstantLoudnessDirection(text, text), 8 * k, None))
    part = build_part(melody_events(16), extras=extras)
    rng = np.random.default_rng(3)
    ap = manual_ap(part, vel=lambda b, p: np.where(np.mod(b // 8, 2) == 0, 45, 85)
                   + rng.normal(0, 2, len(b)))
    res = structural_coherence(ap)
    assert res.r2("velocity") > 0.9
    assert res.r2("velocity", "r2_no_markings") < 0.2


def test_coherence_tempo_follows_phrase_arcs():
    """Tempo arcs over external 4-bar phrases: the smooth tempo channel is explained."""
    part = build_part(melody_events(24))
    bounds = list(range(0, 96, 16))

    def onset(beat):
        u = 2 * np.mod(beat, 16) / 16 - 1
        period = 0.5 * np.exp(0.15 * u**2)  # slower at phrase edges
        t = np.r_[0, np.cumsum(period[:-1] * np.diff(beat))]
        return t

    ap = manual_ap(part, onset=onset)
    basis = score_basis(ap.score, phrase_boundaries_beats=bounds)
    res = structural_coherence(ap, basis)
    assert res.r2("tempo") > 0.7


def test_coherence_skips_unmatched_notes():
    ap = manual_ap(build_part(melody_events(16)), vel=metric_velocity, drop=range(0, 128, 9))
    res = structural_coherence(ap)
    assert res.meta["n_deletion"] == len(range(0, 128, 9))
    assert res.summary.set_index("channel").loc["velocity", "n"] == 128 - 15
    assert res.r2("velocity") > 0.99


def test_duplicate_score_matches_are_counted_once():
    ap = manual_ap(build_part(melody_events(8)), vel=metric_velocity)
    pairs = ap.alignment.pairs
    extra = np.array([("match", pairs["score_id"][3], pairs["performance_id"][4])],
                     dtype=types.ALIGNMENT_DTYPE)
    ap.alignment.pairs = np.concatenate([pairs, extra])
    assert len(channel_data(ap)["velocity"]) == 64
    first = melody_events(4, seed=5)
    ev = first + [(on + 16, du, p, v, a) for on, du, p, v, a in first]
    ap = manual_ap(build_part(ev))
    pairs = ap.alignment.pairs
    ap.alignment.pairs = np.concatenate([pairs, np.array(
        [("match", pairs["score_id"][40], pairs["performance_id"][41])],
        dtype=types.ALIGNMENT_DTYPE)])
    assert len(repeated_material(ap).runs) == 4


def test_channel_data_articulation_log_ratio():
    ap = manual_ap(build_part(melody_events(4)), dur=lambda d: 0.5 * d * 0.5)
    d = channel_data(ap)
    assert d["articulation"]["y"].to_numpy() == pytest.approx(np.log(0.5), abs=1e-6)
    assert d["tempo"]["y"].abs().max() < 1e-6


def test_pooled_coherence_shares_structure_across_performers():
    part = build_part(melody_events(16))
    aps = [manual_ap(part, vel=lambda b, p, a=a, s=s: a + s * metric_velocity(b, p) / 60)
           for a, s in ((30, 20), (50, 40), (60, 10))]
    res = pooled_structural_coherence(aps, scale=True)
    assert res.r2("velocity") > 0.99
    pp = res.per_performance[res.per_performance["channel"] == "velocity"]
    assert len(pp) == 3 and (pp["r2_pooled_model"] > 0.99).all()
    assert res.summary["n_performances"].iloc[0] == 3


# --------------------------------------------------------------------------- repeats


def test_repeated_passage_played_identically_has_consistency_one():
    first = melody_events(4, seed=5)
    ev = first + [(on + 16, du, p, v, a) for on, du, p, v, a in first]
    ev += [(32 + on, du, p, v, a) for on, du, p, v, a in melody_events(2, seed=9)]
    part = build_part(ev)
    rng = np.random.default_rng(2)
    base = rng.normal(64, 12, 32)
    art = rng.uniform(0.4, 1.0, 32)

    def vel(b, p):
        out = rng.normal(64, 12, len(b))
        m = b < 32
        out[m] = base[(np.mod(b[m], 16) * 2).astype(int)]
        return out

    def dur(d):  # score notes are in time order: 32 + 32 repeated, then 16 others
        return np.r_[art, art, np.full(len(d) - 64, 0.5)] * d * 0.5

    ap = manual_ap(part, vel=vel, dur=dur)
    res = repeated_material(ap)
    runs = res.runs[res.runs["channel"] == "velocity"]
    assert len(runs) == 1
    r = runs.iloc[0]
    assert (r["first_measure_idx"], r["repeat_measure_idx"], r["n_bars"]) == (0, 4, 4)
    assert r["n"] == 32 and r["r"] == pytest.approx(1.0) and r["ccc"] == pytest.approx(1.0)
    assert r["mean_diff"] == pytest.approx(0) and r["rms_diff"] == pytest.approx(0)
    a = res.runs[res.runs["channel"] == "articulation"].iloc[0]
    assert a["r"] == pytest.approx(1.0)
    s = res.summary.set_index("channel")
    assert s.loc["velocity", "r_mean"] == pytest.approx(1.0, abs=1e-5)
    assert len(res.bars[res.bars["channel"] == "velocity"]) == 8


def test_repeated_passage_played_differently_is_inconsistent():
    first = melody_events(4, seed=5)
    ev = first + [(on + 16, du, p, v, a) for on, du, p, v, a in first]
    rng = np.random.default_rng(4)
    ap = manual_ap(build_part(ev), vel=lambda b, p: rng.normal(64, 12, len(b)))
    r = repeated_material(ap).runs.query("channel == 'velocity'").iloc[0]
    assert abs(r["r"]) < 0.4


# --------------------------------------------------------------------------- voicing


def chordal_part(n_bars=4):
    ev = []
    ps = rand_pitches(n_bars * 4, seed=7, lo=72, hi=84)
    for k in range(n_bars * 4):
        ev.append((k, 1.0, ps[k], 1, None))
        ev.append((k, 1.0, 55, 2, None))
        ev.append((k, 1.0, 48, 2, None))
    return build_part(ev)


def test_voicing_known_velocity_difference_and_lead():
    part = chordal_part()
    ap = manual_ap(part, vel=lambda b, p: np.where(p >= 72, 80, 60),
                   onset=lambda b: b * 0.5)
    # melody 20 ms early
    pn = ap.performance.notes
    pn["onset_sec"] = np.where(pn["pitch"] >= 72, pn["onset_sec"] - 0.02, pn["onset_sec"])
    res = voicing(ap)
    assert res.summary["n_onsets"] == 16
    assert res.summary["vel_diff_mean_midi"] == pytest.approx(20)
    assert res.summary["lead_mean_ms"] == pytest.approx(20, abs=1e-6)
    assert res.summary["frac_melody_louder"] == 1.0
    assert len(res.bars) == 4 and res.bars["vel_diff_midi"].tolist() == pytest.approx([20] * 4)
    assert res.onsets["lead_beats"].to_numpy() == pytest.approx(0.04, abs=1e-3)
    # explicit melody ids: the bass as "melody" has no lower notes -> nothing qualifies
    bass = ap.score.notes["id"][ap.score.notes["pitch"] == 48]
    assert voicing(ap, melody_ids=bass).summary["n_onsets"] == 0


def test_voicing_zero_beat_period_gives_nan_lead_beats_not_a_crash():
    """Degenerate smooth tempo (beat period 0, seen on very short segments in R-04)."""
    from pianolens.features.tempo import tempo_model

    ap = manual_ap(chordal_part(), vel=lambda b, p: np.where(p >= 72, 80, 60))
    tc = tempo_model(ap)
    tc.positions.loc[tc.positions["beat"] < 4, "beat_period_sec"] = 0.0
    res = voicing(ap, tempo=tc)
    assert res.summary["n_onsets"] == 16
    assert res.summary["n_lead_beats_undefined"] == 4
    early = res.onsets["beat"] < 4
    assert res.onsets.loc[early, "lead_beats"].isna().all()
    assert res.onsets.loc[~early, "lead_beats"].notna().all()
    assert np.isfinite(res.summary["lead_mean_ms"])


# --------------------------------------------------------------------------- dynamics


def dynamics_part():
    extras = [
        (pt.score.ConstantLoudnessDirection("p", "p"), 0, None),
        (pt.score.IncreasingLoudnessDirection("crescendo", "crescendo", wedge=True), 8, 16),
        (pt.score.ConstantLoudnessDirection("f", "f"), 16, None),
        (pt.score.DecreasingLoudnessDirection("diminuendo", "diminuendo", wedge=True), 24, 32),
        (pt.score.ConstantLoudnessDirection("p", "p"), 32, None),
    ]
    return build_part(melody_events(10), extras=extras)


def follow_marks(b, p, sign=1):
    lv = np.interp(b, [0, 8, 16, 24, 32, 40], [50, 50, 90, 90, 50, 50])
    return 70 + sign * (lv - 70)


def test_dynamic_compliance_follows_and_opposes_markings():
    good = dynamic_compliance(manual_ap(dynamics_part(), vel=follow_marks))
    s = good.summary
    assert s["hairpin_n"] == 2 and s["hairpin_agree_frac"] == 1.0
    assert s["hairpin_mean_signed_change_vel"] == pytest.approx(40, abs=2)
    assert s["level_n"] == 2 and s["level_agree_frac"] == 1.0
    assert s["level_vel_per_step"] > 0
    assert s["level_velocity_spearman"] > 0.5
    assert set(good.bars["measure_number"]) >= {3, 5, 7, 9}
    bad = dynamic_compliance(manual_ap(dynamics_part(),
                                       vel=lambda b, p: follow_marks(b, p, -1))).summary
    assert bad["hairpin_agree_frac"] == 0.0 and bad["level_agree_frac"] == 0.0
    assert bad["hairpin_mean_signed_change_vel"] < -30


def test_accent_compliance():
    ev = melody_events(4)
    ev[4] = (ev[4][0], ev[4][1], ev[4][2], 1, ["accent"])
    ap = manual_ap(build_part(ev), vel=lambda b, p: np.where(np.isclose(b, 2.0), 90, 60))
    s = dynamic_compliance(ap).summary
    assert s["accent_n"] == 1 and s["accent_agree_frac"] == 1
    assert s["accent_mean_excess_vel"] == pytest.approx(30)


def test_shaping_runs_end_to_end():
    res = shaping(manual_ap(dynamics_part(), vel=follow_marks))
    assert res.summary["dynamics_hairpin_agree_frac"] == 1.0
    assert "coherence_velocity_r2" in res.summary and "voicing_n_onsets" in res.summary
    assert ShapingConfig().block_bars == 4


# --------------------------------------------------------------------------- F-05b phrase detail


def test_phrase_detail_and_cadence_columns_are_opt_in():
    part = build_part(melody_events(16))
    sc = types.score_from_partitura(part, score_id="s", piece_id=types.PieceId("x"),
                                    keep_part=True)
    plain = score_basis(sc, phrase_boundaries_beats=[0, 16, 32, 48])
    assert "phrase_detail" not in plain.groups and "pre_end_k1" not in plain.notes
    cad = pd.DataFrame({"beat": [14.0, 30.0, 46.0], "cadence": ["HC", "PAC", "EC"]})
    b = score_basis(sc, phrase_boundaries_beats=[0, 16, 32, 48], phrase_ends_beats=[14, 30, 46],
                    cadences=cad, config=BasisConfig(phrase_detail=True))
    assert b.groups["phrase_detail"][0] == "pre_end_k0.5" and "cadence" in b.groups
    n = b.notes.set_index("beat")
    # at the annotated end the kernel is 1; one bar (4 beats) earlier it is exp(-1)
    assert n.loc[14.0, "pre_end_k1"] == pytest.approx(1.0)
    assert n.loc[10.0, "pre_end_k1"] == pytest.approx(np.exp(-1))
    assert n.loc[10.0, "pre_end_k2"] == pytest.approx(np.exp(-0.5))
    assert n.loc[16.0, "post_start_k1"] == pytest.approx(1.0)
    assert n.loc[18.0, "post_end_k1"] == pytest.approx(np.exp(-1))
    # 16 beats of eighths: last onset at 15.5 -> (15.5 / 4 + 1 / 4) bars
    assert n.loc[4.0, "phrase_len_log2"] == pytest.approx(np.log2(4.125))
    assert n.loc[30.0, "pre_cad_PAC_k1"] == pytest.approx(1.0)
    assert n.loc[26.0, "pre_cad_PAC_k1"] == pytest.approx(np.exp(-1))
    assert n.loc[14.0, "pre_cad_HC_k1"] == pytest.approx(1.0)
    assert n.loc[46.0, "pre_cad_other_k1"] == pytest.approx(1.0)  # EC counts as other
    assert n.loc[34.0, "post_cad_k1"] == pytest.approx(np.exp(-1))
    assert n.loc[60.0, "pre_cad_PAC_k1"] < 1e-20  # no cadence ahead
    assert b.onsets.set_index("beat").loc[14.0, "pre_end_k1"] == pytest.approx(1.0)


def test_phrase_final_ritardando_needs_phrase_detail():
    """Irregular phrases (2 to 8 bars) with a short ritardando into each phrase end: the arc
    features (position in the phrase) place it badly, the phrase-end kernels explain it."""
    lens = [2, 7, 3, 8, 2, 6, 4]
    part = build_part(melody_events(sum(lens)))
    starts = list(np.cumsum([0, *lens[:-1]]) * 4.0)
    ends = [s + 4 * n - 0.5 for s, n in zip(starts, lens, strict=True)]

    def onset(beat):
        e = np.array(ends)
        d = np.array([e[e >= b - 1e-9].min() - b if (e >= b - 1e-9).any() else 99
                      for b in beat]) / 4
        period = 0.5 * np.exp(0.3 * np.exp(-d / 0.5))
        return np.r_[0, np.cumsum(period[:-1] * np.diff(beat))]

    ap = manual_ap(part, onset=onset)
    plain = score_basis(ap.score, phrase_boundaries_beats=starts,
                        config=BasisConfig(phrase_max_bars=1e6))
    rich = score_basis(ap.score, phrase_boundaries_beats=starts, phrase_ends_beats=ends,
                       config=BasisConfig(phrase_max_bars=1e6, phrase_detail=True))
    cfg = ShapingConfig(clip_to_train=True)
    r_plain = structural_coherence(ap, plain, config=cfg).r2("tempo")
    r_rich = structural_coherence(ap, rich, config=cfg).r2("tempo")
    assert r_rich > 0.7  # measured 0.77
    assert r_rich > r_plain + 0.2  # measured 0.50


def test_clip_to_train_stops_extrapolation_from_sparse_features():
    """A feature that is almost constant in training and large in one held-out block: the
    unclipped ridge extrapolates wildly, the clipped one does not."""
    rng = np.random.default_rng(0)
    measure = np.repeat(np.arange(40), 8)
    x1 = rng.normal(size=len(measure))
    y = x1 + rng.normal(0, 0.3, len(measure))
    x2 = 1e-4 * rng.normal(size=len(measure))  # pure noise with a tiny spread
    x2[measure < 4] = 1.0  # one block, far outside the training range
    X = np.c_[x1, x2]
    shaping_mod = sys.modules["pianolens.features.shaping"]
    _, r_raw, _ = shaping_mod._cv_ridge(X, y, measure, ShapingConfig(clip_to_train=False))
    _, r_clip, _ = shaping_mod._cv_ridge(X, y, measure, ShapingConfig(clip_to_train=True))
    assert r_raw < 0
    assert r_clip > 0.8


def test_coherence_reports_cv_blocks():
    # n_blocks = ceil(distinct written bars / block_bars), not the bar-number range (F-05d)
    ap = manual_ap(build_part(melody_events(4)), vel=metric_velocity)
    s = structural_coherence(ap).summary.set_index("channel")
    assert s.loc["velocity", "n_written_bars"] == 4 and s.loc["velocity", "n_blocks"] == 1
    assert np.isnan(s.loc["velocity", "r2"])
    assert s.loc["velocity", "undefined_reason"] == "too_few_bars"
    ap = manual_ap(build_part(melody_events(16)), vel=metric_velocity)
    s = structural_coherence(ap).summary.set_index("channel")
    assert s.loc["velocity", "n_written_bars"] == 16 and s.loc["velocity", "n_blocks"] == 4
    assert s.loc["velocity", "undefined_reason"] == ""
    assert s.loc["timing", "undefined_reason"] == "constant"  # deadpan timing


def test_coherence_short_score_numbered_from_zero_is_nan():
    """F-05d regression (R-09): an 8-bar score with a bar 0 (numbers 0-8) spans three 4-bar
    number blocks, so the old range-based rule called it defined and R² could be hugely
    negative. It has 9 distinct written bars < 12, so R² must be NaN."""
    part = build_part(melody_events(9))
    for i, m in enumerate(part.iter_all(pt.score.Measure)):
        m.number = i
    rng = np.random.default_rng(0)
    ap = manual_ap(part, vel=lambda b, p: 40 + 3 * (p - 60) + rng.normal(0, 5, len(b)))
    assert sorted(set(ap.score.measures["number"])) == list(range(9))
    s = structural_coherence(ap).summary.set_index("channel")
    assert s.loc["velocity", "n_written_bars"] == 9
    assert s.loc["velocity", "n_blocks"] == 3  # passes the block count ...
    assert s.loc["velocity", "undefined_reason"] == "too_few_bars"  # ... not the bar count
    for col in ("r2", "r2_no_markings", "alpha"):
        assert np.isnan(s.loc["velocity", col])
    # the gate, not the data, is what makes it NaN: lowering it lets the fit run
    s = structural_coherence(ap, config=ShapingConfig(min_written_bars=0)).summary
    assert np.isfinite(s.set_index("channel").loc["velocity", "r2"])
    # the block rule still applies on its own
    s = structural_coherence(ap, config=ShapingConfig(min_written_bars=0, block_bars=8))
    v = s.summary.set_index("channel").loc["velocity"]
    assert v["n_blocks"] == 2 and v["undefined_reason"] == "too_few_blocks"


# --------------------------------------------------------------------------- F-05c phrase tempo


def arc_onsets(bounds, depth):
    """Onset function: log beat period ``depth * u^2`` inside each phrase (``u`` in [-1, 1]);
    depth > 0 = slower at the phrase edges (a concave tempo arc)."""
    b0 = np.asarray(bounds, float)

    def onset(beat):
        i = np.clip(np.searchsorted(b0, beat, side="right") - 1, 0, len(b0) - 1)
        s = b0[i]
        e = np.r_[b0[1:], beat.max() + 1][i]
        u = 2 * (beat - s) / (e - s) - 1
        period = 0.5 * np.exp(depth * u**2)
        return np.r_[0, np.cumsum(period[:-1] * np.diff(beat))]

    return onset


def test_phrase_tempo_concave_arcs_known_answer():
    from pianolens.features.shaping import phrase_tempo_shaping

    part = build_part(melody_events(32))
    bounds = [0, 16, 28, 48, 64, 80, 96, 112]  # 4-, 3- and 5-bar phrases
    ap = manual_ap(part, onset=arc_onsets(bounds, 0.15))
    res = phrase_tempo_shaping(ap, bounds)
    s = res.summary
    assert s["n_phrases"] == len(bounds)
    assert s["concave_share"] == 1.0
    assert s["arc_r2_within"] > 0.8
    assert s["null_concave_share"] < 0.8 and s["concave_excess"] > 0.2
    assert s["arc_r2_excess"] > 0.1
    assert s["depth_median_log"] > 0
    assert len(res.null) == 2 and set(res.null["shift_bars"]) == {-2.0, 2.0}
    # per bar: every bar present, phrase ids follow the boundaries
    assert len(res.bars) == 32
    first = res.bars.set_index("measure_idx")["phrase"]
    assert first.iloc[0] == 0 and first.iloc[4] == 1 and first.iloc[7] == 2
    assert res.bars["phrase_concave"].all()
    # per phrase
    assert list(res.phrases["start_beat"]) == [float(b) for b in bounds]
    assert (res.phrases["depth_log"] > 0).all()


def test_phrase_tempo_convex_arcs_and_unmatched_notes():
    from pianolens.features.shaping import phrase_tempo_shaping

    part = build_part(melody_events(24))
    bounds = list(range(0, 96, 16))
    ap = manual_ap(part, onset=arc_onsets(bounds, -0.15), drop=range(5, 40, 3))
    s = phrase_tempo_shaping(ap, bounds).summary
    assert s["concave_share"] == 0.0 and s["concave_excess"] <= 0.0
    # default boundaries come from the basis (proxy) and still run
    d = phrase_tempo_shaping(ap).summary
    assert d["n_phrases"] >= 1 and np.isfinite(d["arc_r2_within"])


def test_merge_short_phrases_known_answer():
    from pianolens.features.shaping import merge_short_phrases

    # 3/4, phrases of 4 bars (12 beats) split into 2-bar halves -> merged back to 4 bars
    halves = [0, 6, 12, 18, 24, 30]
    assert merge_short_phrases(halves, 4, 3, 36) == [0.0, 12.0, 24.0]
    # already long enough: unchanged; boundaries past the end are dropped
    assert merge_short_phrases([0, 12, 24, 40], 4, 3, 36) == [0.0, 12.0, 24.0]
    # a short phrase merges with its shorter neighbour (here the previous 1-bar phrase ...
    # after the first merge the 2-bar phrase joins the following one on a tie)
    assert merge_short_phrases([0, 12, 15, 18, 30], 4, 3, 42) == [0.0, 12.0, 30.0]
    # the last phrase merges into the previous one; a single phrase is never removed
    assert merge_short_phrases([0, 12, 21], 4, 3, 24) == [0.0, 12.0]
    assert merge_short_phrases([0], 4, 3, 6) == [0.0]


def test_merge_short_phrases_restores_concave_share():
    """Concave 4-bar arcs marked as 2-bar halves: merging recovers the true phrases.

    (Half of a parabola has the same curvature sign, so halving alone does not flip ``c2``;
    the merge matters for the level of the arcs and for the shifted null.)"""
    from pianolens.features.shaping import merge_short_phrases, phrase_tempo_shaping

    part = build_part(melody_events(32))
    bounds = list(range(0, 128, 16))  # 4-bar phrases in 4/4
    ap = manual_ap(part, onset=arc_onsets(bounds, 0.15))
    halves = sorted([*bounds, *[b + 8 for b in bounds]])
    split = phrase_tempo_shaping(ap, halves).summary
    merged = merge_short_phrases(halves, 4, 4, 128)
    assert merged == [float(b) for b in bounds]
    m = phrase_tempo_shaping(ap, merged).summary
    assert split["n_phrases"] == 2 * m["n_phrases"]
    assert m["concave_share"] == 1.0 and m["concave_excess"] > 0.2
