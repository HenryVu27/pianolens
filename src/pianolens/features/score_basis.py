"""Score basis features (F-05): Basis-Mixer-style descriptors of every score note and onset.

A *basis function* (Grachten and Widmer 2012; Cancino-Chacón and Grachten, the Basis Mixer) is
a numeric descriptor of a score note: its metrical position, pitch, duration, the markings that
apply to it. Expression models write each expressive parameter (velocity, timing, articulation,
tempo) as a function of these. Tier C uses them to ask how much of a performer's own
expressive variation the score structure explains (structural coherence, H4, see
:mod:`pianolens.features.shaping`).

Computed from the **performed score** (the unfolded ``Score`` returned by
``pianolens.align.align_performance``, with ``part`` kept). Scores without a ``part`` (e.g.
built from MIDI or by hand) get the structural features only; marking columns are zero and
``meta["has_part"]`` is False. Grace notes are dropped (they carry no metrical position).

Units: score beats as partitura counts them (time-signature denominator units: 6/8 has six
beats per bar), semitones, octaves, log2 of beat durations. Every column is numeric.

Feature groups (``ScoreBasis.groups``; the names in parentheses are the columns)
--------------------------------------------------------------------------------
* ``metrical`` (``metrical_strength``, ``is_downbeat``, ``is_strong_beat``, ``is_beat``,
  ``is_offbeat``, ``beat_phase_sin``, ``beat_phase_cos``): ``metrical_strength`` is 1 on the
  downbeat, 0.75 on the secondary strong beat (bar middle in 4-beat simple meters, the middle
  dotted beat of 12/8), 0.5 on other beats (dotted beats in compound meters), 0.25 on the next
  subdivision (half beats; eighths in compound meters) and 0 below. ``beat_phase`` is the
  position in the bar as a fraction of the bar (sin / cos so it has no wrap-around jump). A
  short first bar is an anacrusis: its notes are right-aligned to the bar end. partitura's
  ``metrical_strength_feature`` needs ``include_metrical_position=True``, which crashes with
  numpy 2 (see ``.claude/rules/features.md``), so this is computed from ``measures`` and
  ``onset_beat``.
* ``pitch`` (``pitch_rel_oct``, ``is_top``, ``is_bass``, ``chord_rank``, ``chord_size_log``,
  ``melody_pitch_rel_oct``, ``melody_step_oct``, ``melody_peak``): pitch relative to the piece
  median in octaves; ``is_top``: the highest note starting at its onset and not below a note
  still held from before (skyline melody); ``is_bass``: lowest note of a chord; rank within
  the onset's chord (0 lowest, 1 highest); log chord size; the highest sounding pitch at the
  onset (held notes included); for onsets that start a skyline melody note, its signed step
  from the previous melody note (octaves) and whether it is a local peak of the melody line.
  ``is_top`` / ``chord_rank`` are partitura's ``vertical_neighbor_feature`` in another form.
* ``duration`` (``dur_log2``, ``ioi_next_log2``, ``ioi_prev_log2``): log2 of the notated
  duration and of the score inter-onset intervals to the next / from the previous onset, in
  beats (floored at 1/64 beat).
* ``dynamics`` (``dyn_level``, ``cresc_ramp``, ``dim_ramp``, ``in_cresc``, ``in_dim``,
  ``sf_accent``): ``dyn_level`` is the latest constant dynamic marking on an ordinal scale
  (``DYNAMIC_LEVELS``: ppp -3, pp -2, p -1, mp -0.5, mf 0.5, f 1, ff 2, fff 3; 0 before the
  first marking). Hairpins and cresc. / dim. words are ramps from 0 at their start to 1 at
  their end (partitura's ``feature_function_activation`` convention); a word without an
  extent lasts until the next constant marking, at most ``hairpin_default_bars`` bars.
  ``sf_accent`` is 1 on notes at an impulsive marking (sf, sfz, fz, fp, rf, ...).
* ``articulation`` (``staccato``, ``accent``, ``tenuto``, ``slur_incr``, ``slur_decr``):
  note articulations (partitura ``articulation_feature``; accent includes strong-accent and
  stress) and partitura's slur ramps (``slur_feature``). ASAP MusicXML has no slurs.
* ``tempo_marks`` (``rit_ramp``, ``accel_ramp``, ``tempo_mark_near``): rit. / accel. ramps
  (same convention as hairpins) and notes within one beat after a hard tempo marking
  (:func:`pianolens.features.tempo.score_tempo_breaks`).
* ``fermata`` (``fermata``, ``pre_fermata``): note at a fermata; note within one beat before.
* ``phrase`` (``phrase_pos``, ``phrase_pos_sq``, ``phrase_start``, ``phrase_end``,
  ``boundary_strength``): position ``u`` in [-1, 1] across the phrase and ``u^2`` (the
  parabolic phrase arc, Repp 1992; Todd 1992), first / last onset of a phrase and the proxy
  boundary strength (below). Phrases are supplied externally (``phrase_boundaries_beats``,
  e.g. annotations or R-08) or come from the **proxy**: a boundary before an onset scores
  1.5 for a silence (all notes off) of at least half a beat, 1 for a long melody note
  (skyline IOI >= 2x the median skyline IOI of the surrounding two bars and >= 1 beat; 1.5
  at >= 4x and >= 2 beats), 1 when a
  slur ends and another begins, 2 after a fermata, 1 at a double barline / tempo marking,
  and 1 after a cadence-like arrival (bass moves down a fifth / up a fourth onto a strong
  beat and is held >= 1 beat). Onsets scoring >= ``boundary_threshold`` become boundaries,
  strongest first, at least ``phrase_min_bars`` apart. Phrases longer than
  ``phrase_max_bars`` are split evenly (hypermeter proxy), so phrase position never becomes
  a global trend in time. The proxy is crude (F-05b: F1 0.34 at +-1 beat against Batik DCML
  phrase starts, no better than a 4-bar grid at bar tolerance). ``BasisConfig(phrase_source=
  "cadence")`` takes phrases from the cadence detector instead (F-05c,
  :mod:`pianolens.features.cadence`); ``source`` is then ``cadence``.
* ``harmony`` (``tension_diameter``, ``tension_strain``, ``tension_momentum``,
  ``nondiatonic_frac``): tonal tension ribbons (Herremans and Chew 2016, spiral array) from
  partitura ``estimate_tonaltension`` over a ``tension_window_beats`` window at each onset:
  cloud diameter (dissonance of the local pitch cloud), tensile strain (distance from the
  key) and cloud momentum (harmonic change). ``nondiatonic_frac`` is the fraction of pitch
  classes sounding at the onset that are outside the key signature's major / minor scale.
* ``position`` (``piece_pos``): position in the piece, 0 to 1. Not structure: excluded from
  structural-coherence regressions by default.

Optional groups (F-05b; off by default so existing results are unchanged)
------------------------------------------------------------------------
* ``phrase_detail`` (``BasisConfig(phrase_detail=True)``; ``OPTIONAL_GROUPS``): distances in
  bars, turned into exponential kernels ``exp(-d / k)`` so they are 1 at the event and fade
  over ``k`` bars. ``pre_end_k0.5`` / ``pre_end_k1`` / ``pre_end_k2``: approach to the next
  phrase end (phrase-final lengthening, Repp 1992; Todd 1992); ``post_end_k1``: time since the
  previous phrase end (recovery after the boundary); ``post_start_k1``: time since the phrase
  start; ``phrase_len_log2`` (log2 phrase length in bars) and its products with the arc
  (``pos_x_len``, ``possq_x_len``), so longer phrases may have deeper arcs. Phrase ends are
  ``phrase_ends_beats`` when given (annotated cadential arrivals), else the last onset of each
  phrase.
* ``cadence`` (only when ``cadences`` are given, e.g. DCML annotations): ``pre_cad_PAC_k1``,
  ``pre_cad_HC_k1``, ``pre_cad_other_k1`` (IAC / EC / DC and anything else): approach to the
  next cadence of that type, ``exp(-bars / 1)``; ``post_cad_k1``: time since the last cadence.
  DCML cadence labels: https://github.com/DCMLab/standards (method reference, not in the
  landscape doc).

Citations (``docs/research/2026-09-27-landscape.md`` sections 1.2-1.3 and
``docs/research/2026-09-27-expression-models.md``): Basis Mixer (Cancino-Chacón, Grachten et
al., https://github.com/CPJKU/basismixer; review Cancino-Chacón, Grachten, Goebl, Widmer 2018,
https://doi.org/10.3389/fdigh.2018.00025); partitura ``musicanalysis`` note features and tonal
tension (https://partitura.readthedocs.io/en/latest/modules/partitura.musicanalysis.html);
Repp 1992 (https://doi.org/10.1121/1.404425) for parabolic phrase-level timing. Herremans and
Chew 2016 (tension ribbons) and Todd 1992 (phrase arcs) are method references, not in the
landscape doc.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pianolens.features.tempo import _attach_measures, _measure_info, score_tempo_breaks

__all__ = [
    "BasisConfig",
    "DYNAMIC_LEVELS",
    "FEATURE_GROUPS",
    "MARKING_GROUPS",
    "OPTIONAL_GROUPS",
    "ScoreBasis",
    "base_note_id",
    "metrical_strength",
    "score_basis",
]

DYNAMIC_LEVELS: dict[str, float] = {
    "pppp": -4.0, "ppp": -3.0, "pp": -2.0, "p": -1.0, "mp": -0.5,
    "mf": 0.5, "f": 1.0, "ff": 2.0, "fff": 3.0, "ffff": 4.0,
}  # fmt: skip
"""Ordinal scale of constant dynamic markings (one step per letter; mp / mf half steps)."""

IMPULSIVE = ("sf", "sfz", "sffz", "fz", "ffz", "fp", "sfp", "rf", "rfz", "sfpp")

FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "metrical": ("metrical_strength", "is_downbeat", "is_strong_beat", "is_beat", "is_offbeat",
                 "beat_phase_sin", "beat_phase_cos"),
    "pitch": ("pitch_rel_oct", "is_top", "is_bass", "chord_rank", "chord_size_log",
              "melody_pitch_rel_oct", "melody_step_oct", "melody_peak"),
    "duration": ("dur_log2", "ioi_next_log2", "ioi_prev_log2"),
    "dynamics": ("dyn_level", "cresc_ramp", "dim_ramp", "in_cresc", "in_dim", "sf_accent"),
    "articulation": ("staccato", "accent", "tenuto", "slur_incr", "slur_decr"),
    "tempo_marks": ("rit_ramp", "accel_ramp", "tempo_mark_near"),
    "fermata": ("fermata", "pre_fermata"),
    "phrase": ("phrase_pos", "phrase_pos_sq", "phrase_start", "phrase_end",
               "boundary_strength"),
    "harmony": ("tension_diameter", "tension_strain", "tension_momentum", "nondiatonic_frac"),
    "position": ("piece_pos",),
}  # fmt: skip
"""Basis columns by group (see the module docstring)."""

OPTIONAL_GROUPS: dict[str, tuple[str, ...]] = {
    "phrase_detail": ("pre_end_k0.5", "pre_end_k1", "pre_end_k2", "post_end_k1",
                      "post_start_k1", "phrase_len_log2", "pos_x_len", "possq_x_len"),
    "cadence": ("pre_cad_PAC_k1", "pre_cad_HC_k1", "pre_cad_other_k1", "post_cad_k1"),
}  # fmt: skip
"""Groups added only on request (``BasisConfig.phrase_detail``, ``cadences``)."""

MARKING_GROUPS: tuple[str, ...] = ("dynamics", "articulation", "tempo_marks", "fermata")
"""Groups read from performance markings rather than notes: the "without markings" variant of
structural coherence drops these (dynamics trivially explain velocity, and so on)."""

_EPS = 1e-6
_SUFFIX = re.compile(r"-(\d+)$")


def base_note_id(note_id: str) -> tuple[str, int]:
    """Split a partitura unfolded id ``n12-2`` into (``n12``, 2); (``id``, 0) without suffix."""
    m = _SUFFIX.search(note_id)
    if not m:
        return note_id, 0
    return note_id[: m.start()], int(m.group(1))


@dataclass(frozen=True)
class BasisConfig:
    """Parameters of :func:`score_basis` (see the module docstring).

    Attributes:
        phrase_min_bars: minimum distance between proxy phrase boundaries, in bars.
        phrase_max_bars: longer phrases (proxy or external) are split evenly.
        boundary_threshold: proxy boundary score needed for a boundary.
        hairpin_default_bars: extent of a cresc. / dim. word with no end and no later marking.
        tension_window_beats: window of the tonal tension estimate, in beats.
        include_tension: compute the tension ribbons (about 0.5 s per 2,000 onsets).
        phrase_detail: add the ``phrase_detail`` group (phrase-end / start kernels, phrase
            length and its interaction with the arc; see the module docstring).
        phrase_source: where phrases come from when ``phrase_boundaries_beats`` is not given:
            ``proxy`` (the cue-based proxy, default) or ``cadence`` (phrase ends from
            :func:`pianolens.features.cadence.cadence_phrase_ends` and the starts it implies;
            the ends also feed ``phrase_detail`` unless ``phrase_ends_beats`` is given).
            F-05c (``docs/specs/phrase-coherence-validation.md``): its ends beat the proxy's
            (held-out Batik F1 0.46 vs 0.29 at +-1 beat) but tempo coherence with them is
            lower than with the proxy, so keep ``proxy`` for coherence.
    """

    phrase_min_bars: float = 2.0
    phrase_max_bars: float = 8.0
    boundary_threshold: float = 1.0
    hairpin_default_bars: float = 4.0
    tension_window_beats: float = 1.0
    include_tension: bool = True
    phrase_detail: bool = False
    phrase_source: str = "proxy"


@dataclass
class ScoreBasis:
    """Output of :func:`score_basis`.

    Attributes:
        notes: one row per non-grace score note, in score-array order: ``score_id``,
            ``base_id`` / ``repeat_index`` (unfolding suffix split off), ``beat``,
            ``quarter``, ``pitch``, ``duration_beat``, ``voice``, ``staff``,
            ``measure_idx``, ``measure_number``, ``beat_in_bar``, ``bar_beats``, then every
            column of ``FEATURE_GROUPS``.
        onsets: one row per distinct onset (``beat``): ``n_notes``, measure fields, and the
            feature columns taken from the onset's top note (markings: max over the chord).
        phrases: ``start_beat``, ``end_beat``, ``source`` (``proxy`` / ``external`` /
            ``split``), ``strength`` (proxy score at the start).
        dynamics: marking events: ``kind`` (``level`` / ``cresc`` / ``dim`` / ``impulsive``),
            ``text``, ``level`` (``DYNAMIC_LEVELS``), ``start_beat``, ``end_beat``
            (hairpins), ``has_end`` (the score gave an end).
        groups: ``FEATURE_GROUPS`` restricted to present columns.
        meta: ``has_part``, ``beats_per_bar``, ``n_grace_skipped``, ``tension`` (ok / off /
            failed), ``key_fifths``, ``key_mode``.
    """

    notes: pd.DataFrame
    onsets: pd.DataFrame
    phrases: pd.DataFrame
    dynamics: pd.DataFrame
    groups: dict[str, list[str]]
    meta: dict[str, Any] = field(default_factory=dict)

    def columns(self, exclude_groups: Sequence[str] = ("position",)) -> list[str]:
        """Feature columns of every group not in ``exclude_groups``."""
        return [c for g, cols in self.groups.items() if g not in exclude_groups for c in cols]


# --------------------------------------------------------------------------- metrical


def metrical_strength(beat_in_bar: np.ndarray, ts_beats: np.ndarray,
                      ts_beat_type: np.ndarray) -> np.ndarray:
    """Metrical strength (1 / 0.75 / 0.5 / 0.25 / 0) of positions in the bar (see module doc).

    ``beat_in_bar`` is in time-signature denominator units (partitura beats). Compound meters
    (6, 9, 12 beats of eighths or sixteenths) group beats in threes.
    """
    pos = np.asarray(beat_in_bar, float)
    nb = np.asarray(ts_beats, float)
    bt = np.asarray(ts_beat_type, float)
    out = np.zeros(len(pos))

    def on(grid: np.ndarray | float) -> np.ndarray:
        r = np.mod(pos, grid)
        return (r < _EPS) | (np.abs(r - grid) < _EPS)

    compound = np.isin(nb, (6, 9, 12)) & (bt >= 8)
    beat_unit = np.where(compound, 3.0, 1.0)
    sub_unit = np.where(compound, 1.0, 0.5)
    out[on(sub_unit)] = 0.25
    out[on(beat_unit)] = 0.5
    strong = (compound & (nb == 12) & on(6.0)) | (~compound & (nb == 4) & on(2.0))
    out[strong] = 0.75
    out[np.abs(pos) < _EPS] = 1.0
    return out


def _bar_positions(df: pd.DataFrame, score: Any) -> float:
    """Attach measure fields; right-align a short first bar (anacrusis). Returns beats/bar."""
    _, mb, mnum = _measure_info(score)
    bpb = float(np.median(df["ts_beats"])) if len(df) else 4.0
    _attach_measures(df, mb, mnum)
    if "measure_idx" not in df or len(mb) == 0:
        df["measure_idx"] = 0
        df["measure_number"] = 0
        df["beat_in_bar"] = df["beat"] - df["beat"].min()
        return bpb
    df["bar_beats"] = df["ts_beats"].astype(float)
    if len(mb) >= 2:
        first_len = mb[1] - mb[0]
        m0 = df["measure_idx"] == 0
        if m0.any():
            full = float(df.loc[m0, "bar_beats"].iloc[0])
            if first_len < full - _EPS:
                df.loc[m0, "beat_in_bar"] += full - first_len
    return bpb


# --------------------------------------------------------------------------- markings


def _dynamics_events(part: Any, bpb: float, cfg: BasisConfig) -> pd.DataFrame:
    import partitura as pt

    bm = part.beat_map
    rows: list[dict[str, Any]] = []
    for d in part.iter_all(pt.score.LoudnessDirection, include_subclasses=True):
        text = str(getattr(d, "text", "") or "").strip().lower()
        start = float(bm(d.start.t))
        if isinstance(d, pt.score.ConstantLoudnessDirection):
            if text in DYNAMIC_LEVELS:
                rows.append({"kind": "level", "text": text, "level": DYNAMIC_LEVELS[text],
                             "start_beat": start, "end_beat": np.nan, "has_end": False})
        elif isinstance(d, pt.score.ImpulsiveLoudnessDirection):
            rows.append({"kind": "impulsive", "text": text, "level": np.nan,
                         "start_beat": start, "end_beat": start, "has_end": True})
        elif isinstance(d, (pt.score.IncreasingLoudnessDirection,
                            pt.score.DecreasingLoudnessDirection)):
            kind = "cresc" if isinstance(d, pt.score.IncreasingLoudnessDirection) else "dim"
            has_end = d.end is not None and d.end.t > d.start.t
            end = float(bm(d.end.t)) if has_end else np.nan
            rows.append({"kind": kind, "text": text, "level": np.nan, "start_beat": start,
                         "end_beat": end, "has_end": bool(has_end)})
    ev = pd.DataFrame(rows, columns=["kind", "text", "level", "start_beat", "end_beat",
                                     "has_end"])
    ev = ev.drop_duplicates(["kind", "text", "start_beat"]).sort_values("start_beat")
    ev = ev.reset_index(drop=True)
    levels = ev.loc[ev["kind"] == "level", "start_beat"].to_numpy()
    for i in ev.index[ev["kind"].isin(["cresc", "dim"]) & ~ev["has_end"]]:
        s = ev.at[i, "start_beat"]
        nxt = levels[levels > s + _EPS]
        cap = s + cfg.hairpin_default_bars * bpb
        ev.at[i, "end_beat"] = min(float(nxt[0]), cap) if len(nxt) else cap
    return ev


def _ramp(beats: np.ndarray, start: float, end: float) -> np.ndarray:
    """0 at ``start`` rising to 1 at ``end``, 0 outside [start, end]."""
    out = np.zeros(len(beats))
    if end <= start + _EPS:
        return out
    m = (beats >= start - _EPS) & (beats <= end + _EPS)
    out[m] = np.clip((beats[m] - start) / (end - start), 0, 1)
    return out


def _dynamics_columns(df: pd.DataFrame, ev: pd.DataFrame) -> None:
    b = df["beat"].to_numpy()
    lev = ev[ev["kind"] == "level"]
    level = np.zeros(len(b))
    if len(lev):
        s = lev["start_beat"].to_numpy()
        idx = np.searchsorted(s, b + _EPS, side="right") - 1
        level = np.where(idx >= 0, lev["level"].to_numpy()[np.clip(idx, 0, None)], 0.0)
    df["dyn_level"] = level
    for kind, col in (("cresc", "cresc"), ("dim", "dim")):
        ramp = np.zeros(len(b))
        for _, r in ev[ev["kind"] == kind].iterrows():
            ramp = np.maximum(ramp, _ramp(b, r["start_beat"], r["end_beat"]))
        inside = np.zeros(len(b))
        for _, r in ev[ev["kind"] == kind].iterrows():
            inside[(b >= r["start_beat"] - _EPS) & (b <= r["end_beat"] + _EPS)] = 1.0
        df[f"{col}_ramp"] = ramp
        df[f"in_{col}"] = inside
    imp = ev.loc[ev["kind"] == "impulsive", "start_beat"].to_numpy()
    df["sf_accent"] = np.isin(np.round(b, 4), np.round(imp, 4)).astype(float)


def _articulation_columns(df: pd.DataFrame, na: np.ndarray, part: Any | None) -> None:
    for c in FEATURE_GROUPS["articulation"]:
        df[c] = 0.0
    if part is None:
        return
    from partitura.musicanalysis import note_features as nf

    rows = df["_row"].to_numpy()
    try:
        W, names = nf.articulation_feature(na, part, include_empty_features=True)
        W = W[rows]
        acc = [names.index(x) for x in ("accent", "strong-accent", "stress") if x in names]
        df["accent"] = W[:, acc].max(axis=1) if acc else 0.0
        for x in ("staccato", "tenuto"):
            if x in names:
                df[x] = W[:, names.index(x)]
        if "staccatissimo" in names:
            df["staccato"] = np.maximum(df["staccato"], W[:, names.index("staccatissimo")])
    except Exception as e:  # noqa: BLE001 - partitura id lookups can fail on odd parts
        warnings.warn(f"articulation_feature failed: {e!r}", stacklevel=2)
    try:
        W, names = nf.slur_feature(na, part)
        df["slur_incr"] = W[rows, 0]
        df["slur_decr"] = W[rows, 1]
    except Exception as e:  # noqa: BLE001
        warnings.warn(f"slur_feature failed: {e!r}", stacklevel=2)


def _tempo_columns(df: pd.DataFrame, part: Any | None, breaks: pd.DataFrame, bpb: float,
                   cfg: BasisConfig) -> None:
    b = df["beat"].to_numpy()
    for c in FEATURE_GROUPS["tempo_marks"] + FEATURE_GROUPS["fermata"]:
        df[c] = 0.0
    if part is None:
        return
    import partitura as pt

    bm = part.beat_map
    for d in part.iter_all(pt.score.DynamicTempoDirection, include_subclasses=True):
        s = float(bm(d.start.t))
        e = float(bm(d.end.t)) if d.end is not None and d.end.t > d.start.t \
            else s + cfg.hairpin_default_bars * bpb
        col = "accel_ramp" if isinstance(d, pt.score.IncreasingTempoDirection) else "rit_ramp"
        df[col] = np.maximum(df[col].to_numpy(), _ramp(b, s, e))
    marks = breaks.loc[breaks["kind"] == "tempo_marking", "beat"].to_numpy()
    ferm = breaks.loc[breaks["kind"] == "fermata", "beat"].to_numpy()
    for m in marks:
        df.loc[(b >= m - _EPS) & (b < m + 1.0), "tempo_mark_near"] = 1.0
    for f in ferm:
        df.loc[np.abs(b - f) < _EPS, "fermata"] = 1.0
        df.loc[(b < f - _EPS) & (b >= f - 1.0), "pre_fermata"] = 1.0


# --------------------------------------------------------------------------- pitch / duration


def _onset_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per distinct onset: top / bottom pitch of the notes starting there, size, max offset,
    the highest pitch still held from earlier onsets (``held``) and the skyline melody:
    ``melody_new`` is True when the top starting note is not below a held note, and
    ``melody_pitch`` is the highest sounding pitch (starting or held)."""
    g = df.groupby("beat", sort=True)
    on = pd.DataFrame({
        "top": g["pitch"].max(), "bass": g["pitch"].min(), "n_notes": g.size(),
        "max_end": (df["beat"] + df["duration_beat"]).groupby(df["beat"]).max(),
    }).reset_index()
    nb = df["beat"].to_numpy()
    ne = nb + df["duration_beat"].to_numpy()
    npitch = df["pitch"].to_numpy()
    ob = on["beat"].to_numpy()
    held = np.full(len(ob), -1.0)
    step = 512
    for k in range(0, len(ob), step):
        b = ob[k:k + step, None]
        sounding = (nb[None, :] < b - _EPS) & (ne[None, :] > b + _EPS)
        held[k:k + step] = np.where(sounding, npitch[None, :], -1).max(axis=1)
    on["held"] = held
    on["melody_new"] = on["top"] >= on["held"]
    on["melody_pitch"] = np.maximum(on["top"], on["held"])
    return on


def _pitch_duration_columns(df: pd.DataFrame, on: pd.DataFrame) -> None:
    med = float(np.median(df["pitch"])) if len(df) else 60.0
    df["pitch_rel_oct"] = (df["pitch"] - med) / 12.0
    grp = df.groupby("beat")["pitch"]
    top = grp.transform("max")
    bot = grp.transform("min")
    n = grp.transform("size")
    new = on.set_index("beat").loc[df["beat"].to_numpy(), "melody_new"].to_numpy()
    df["is_top"] = ((df["pitch"] == top).to_numpy() & new).astype(float)
    df["is_bass"] = ((df["pitch"] == bot) & (n > 1)).astype(float)
    rank = grp.rank(method="average") - 1
    df["chord_rank"] = np.where(n > 1, rank / np.maximum(n - 1, 1), 1.0)
    df["chord_size_log"] = np.log(n.astype(float))
    # skyline melody line: steps and local peaks over the onsets where a new melody note starts
    mel_on = on[on["melody_new"]]
    t = mel_on["top"].to_numpy(float)
    step = np.r_[0.0, np.diff(t)] / 12.0
    peak = np.zeros(len(t))
    if len(t) >= 3:
        peak[1:-1] = ((t[1:-1] > t[:-2]) & (t[1:-1] >= t[2:])).astype(float)
    mstep = pd.Series(step, index=mel_on["beat"]).reindex(on["beat"]).fillna(0.0).to_numpy()
    mpeak = pd.Series(peak, index=mel_on["beat"]).reindex(on["beat"]).fillna(0.0).to_numpy()
    b = on["beat"].to_numpy()
    ioi_next = np.r_[np.diff(b), np.nan]
    ioi_prev = np.r_[np.nan, np.diff(b)]
    if len(b) > 1:
        ioi_next[-1] = max(on["max_end"].iloc[-1] - b[-1], 1 / 64)
        ioi_prev[0] = ioi_next[0]
    else:
        ioi_next[:] = ioi_prev[:] = max(float(on["max_end"].iloc[0] - b[0]), 1 / 64)
    lut = pd.DataFrame({
        "beat": b, "melody_pitch_rel_oct": (on["melody_pitch"].to_numpy(float) - med) / 12.0,
        "melody_step_oct": mstep, "melody_peak": mpeak,
        "ioi_next_log2": np.log2(np.maximum(ioi_next, 1 / 64)),
        "ioi_prev_log2": np.log2(np.maximum(ioi_prev, 1 / 64)),
    }).set_index("beat")
    for c in lut.columns:
        df[c] = lut.loc[df["beat"].to_numpy(), c].to_numpy()
    df["dur_log2"] = np.log2(np.maximum(df["duration_beat"].to_numpy(float), 1 / 64))


# --------------------------------------------------------------------------- harmony


_MAJOR = np.array([0, 2, 4, 5, 7, 9, 11])
_MINOR_NAT = np.array([0, 2, 3, 5, 7, 8, 10, 11])  # natural + raised leading tone


def _harmony_columns(df: pd.DataFrame, score: Any, cfg: BasisConfig, meta: dict) -> None:
    for c in FEATURE_GROUPS["harmony"]:
        df[c] = 0.0
    part = getattr(score, "part", None)
    na = None
    try:
        if part is not None:
            na = part.note_array(include_pitch_spelling=True, include_key_signature=True,
                                 include_time_signature=True)
        else:
            na = score.notes
            if "is_grace" in (na.dtype.names or ()):
                na = na[~na["is_grace"].astype(bool)]
    except Exception as e:  # noqa: BLE001
        warnings.warn(f"note array for harmony failed: {e!r}", stacklevel=2)
    if na is None or len(na) == 0:
        meta["tension"] = "failed"
        return
    # key: key signature if present, else Krumhansl-Kessler estimate
    fifths, mode = 0, 1
    try:
        names = na.dtype.names or ()
        if "ks_fifths" in names:
            fifths = int(np.median(na["ks_fifths"]))
            mode = int(np.median(na["ks_mode"])) if "ks_mode" in names else 1
        else:
            from partitura.musicanalysis import estimate_key

            k = estimate_key(na)
            from partitura.utils.music import key_name_to_fifths_mode

            fifths, mode_s = key_name_to_fifths_mode(k)
            mode = 1 if mode_s == "major" else -1
    except Exception:  # noqa: BLE001
        pass
    meta["key_fifths"], meta["key_mode"] = fifths, mode
    tonic = (7 * fifths) % 12 if mode != -1 else ((7 * fifths) + 9) % 12
    scale = set(((tonic + (_MINOR_NAT if mode == -1 else _MAJOR)) % 12).tolist())
    pcs = df.groupby("beat")["pitch"].agg(lambda p: len(set(np.asarray(p) % 12) - scale)
                                          / max(len(set(np.asarray(p) % 12)), 1))
    df["nondiatonic_frac"] = pcs.loc[df["beat"].to_numpy()].to_numpy()
    if not cfg.include_tension:
        meta["tension"] = "off"
        return
    try:
        from partitura.musicanalysis import estimate_tonaltension

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tt = estimate_tonaltension(na, ws=cfg.tension_window_beats, ss="onset")
        tb = np.asarray(tt["onset_beat"], float)
        b = df["beat"].to_numpy()
        idx = np.clip(np.searchsorted(tb, b - 1e-4), 0, len(tb) - 1)
        close = np.abs(tb[idx] - b) < 1e-3
        for src, dst in (("cloud_diameter", "tension_diameter"),
                         ("tensile_strain", "tension_strain"),
                         ("cloud_momentum", "tension_momentum")):
            v = np.asarray(tt[src], float)[idx]
            v = np.where(close & np.isfinite(v), v, 0.0)
            df[dst] = v
        meta["tension"] = "ok"
    except Exception as e:  # noqa: BLE001
        warnings.warn(f"estimate_tonaltension failed: {e!r}", stacklevel=2)
        meta["tension"] = "failed"


# --------------------------------------------------------------------------- phrases


def _proxy_boundaries(df: pd.DataFrame, on: pd.DataFrame, part: Any | None,
                      breaks: pd.DataFrame, bpb: float, cfg: BasisConfig) -> pd.DataFrame:
    """Proxy boundary score before each onset (see module docstring)."""
    b = on["beat"].to_numpy()
    n = len(b)
    score = np.zeros(n)
    if n < 2:
        return pd.DataFrame({"beat": b, "strength": score})
    prev_end = np.maximum.accumulate(on["max_end"].to_numpy())
    silence = b[1:] - prev_end[:-1]
    score[1:] += 1.5 * (silence >= 0.5 - _EPS)
    # long skyline-melody note: IOI to the next melody onset vs the local median melody IOI
    mb = b[on["melody_new"].to_numpy()]
    if len(mb) >= 2:
        mioi = np.diff(mb)
        for k in range(1, len(mb)):
            m = (mb[:-1] >= mb[k] - 2 * bpb) & (mb[:-1] < mb[k] + 2 * bpb)
            med = float(np.median(mioi[m])) if m.any() else float(np.median(mioi))
            if mioi[k - 1] >= 2 * med - _EPS and mioi[k - 1] >= 1.0 - _EPS:
                j = int(np.searchsorted(b, mb[k] - _EPS))
                very = mioi[k - 1] >= 4 * med - _EPS and mioi[k - 1] >= 2.0 - _EPS
                score[j] += 1.5 if very else 1.0
    # fermata on the previous onset, tempo marking at this onset
    fer = breaks.loc[breaks["kind"] == "fermata", "beat"].to_numpy()
    for f in fer:
        j = int(np.searchsorted(b, f + _EPS, side="right"))
        if 0 < j < n:
            score[j] += 2.0
    for m in breaks.loc[breaks["kind"] == "tempo_marking", "beat"].to_numpy():
        j = int(np.searchsorted(b, m - _EPS))
        if 0 < j < n:
            score[j] += 1.0
    if part is not None:
        import partitura as pt

        bm = part.beat_map
        try:
            for bl in part.iter_all(pt.score.Barline):
                if str(getattr(bl, "style", "")) in ("light-light", "light-heavy"):
                    j = int(np.searchsorted(b, float(bm(bl.start.t)) - _EPS))
                    if 0 < j < n:
                        score[j] += 1.0
        except Exception:  # noqa: BLE001
            pass
        try:
            ends = [float(bm(s.end.t)) for s in part.iter_all(pt.score.Slur) if s.end]
            starts = [float(bm(s.start.t)) for s in part.iter_all(pt.score.Slur) if s.end]
            ends_a, starts_a = np.array(ends), np.array(starts)
            for j in range(1, n):
                if len(ends_a) and np.any((ends_a <= b[j] + _EPS) & (ends_a >= b[j - 1] - _EPS)) \
                        and np.any(np.abs(starts_a - b[j]) < _EPS):
                    score[j] += 1.0
        except Exception:  # noqa: BLE001
            pass
    # cadence-like arrival: bass down a fifth / up a fourth onto a strong beat, held >= 1 beat
    bass = on["bass"].to_numpy()
    strength = on["metrical_strength"].to_numpy()
    for k in range(1, n - 1):
        if (bass[k] - bass[k - 1]) % 12 == 5 and strength[k] >= 0.75 - _EPS \
                and (b[k + 1] - b[k]) >= 1.0 - _EPS and on["n_notes"].iloc[k] > 1:
            score[k + 1] += 1.0
    return pd.DataFrame({"beat": b, "strength": score})


def _phrases(on: pd.DataFrame, cand: pd.DataFrame, external: Sequence[float] | None,
             bpb: float, cfg: BasisConfig) -> pd.DataFrame:
    b = on["beat"].to_numpy()
    first, last_end = float(b[0]), float(on["max_end"].max())
    if external is not None:
        starts = sorted({float(x) for x in external if first - _EPS <= x < last_end})
        if not starts or starts[0] > first + _EPS:
            starts = [first, *starts]
        rows = [(s, "external", np.nan) for s in starts]
    else:
        c = cand[cand["strength"] >= cfg.boundary_threshold - _EPS]
        c = c.sort_values(["strength", "beat"], ascending=[False, True])
        min_d = cfg.phrase_min_bars * bpb
        acc = [first]
        strengths = {first: np.nan}
        for bt, st in zip(c["beat"], c["strength"], strict=True):
            if all(abs(bt - a) >= min_d - _EPS for a in acc) and last_end - bt >= min_d - _EPS:
                acc.append(float(bt))
                strengths[float(bt)] = float(st)
        rows = [(s, "proxy", strengths[s]) for s in sorted(acc)]
    # split long phrases evenly
    out = []
    max_len = cfg.phrase_max_bars * bpb
    starts = [r[0] for r in rows]
    ends = [*starts[1:], last_end]
    for (s, src, st), e in zip(rows, ends, strict=True):
        k = int(np.ceil((e - s) / max_len - _EPS)) if e > s else 1
        k = max(k, 1)
        for i in range(k):
            out.append({"start_beat": s + i * (e - s) / k, "end_beat": s + (i + 1) * (e - s) / k,
                        "source": src if i == 0 else "split", "strength": st if i == 0
                        else np.nan})
    return pd.DataFrame(out, columns=["start_beat", "end_beat", "source", "strength"])


def _phrase_columns(df: pd.DataFrame, on: pd.DataFrame, phrases: pd.DataFrame,
                    cand: pd.DataFrame) -> None:
    b = df["beat"].to_numpy()
    s = phrases["start_beat"].to_numpy()
    idx = np.clip(np.searchsorted(s, b + _EPS, side="right") - 1, 0, len(s) - 1)
    ob = on["beat"].to_numpy()
    # phrase position of onsets: u in [-1, 1] from the first to the last onset of the phrase
    oidx = np.clip(np.searchsorted(s, ob + _EPS, side="right") - 1, 0, len(s) - 1)
    first_on = pd.Series(ob).groupby(oidx).min()
    last_on = pd.Series(ob).groupby(oidx).max()
    f = first_on.reindex(idx).to_numpy()
    la = last_on.reindex(idx).to_numpy()
    span = np.where(la - f > _EPS, la - f, np.nan)
    u = np.where(np.isfinite(span), 2 * (b - f) / span - 1, 0.0)
    df["phrase_pos"] = np.clip(u, -1, 1)
    df["phrase_pos_sq"] = df["phrase_pos"] ** 2
    df["phrase_start"] = (np.abs(b - f) < _EPS).astype(float)
    df["phrase_end"] = (np.abs(b - la) < _EPS).astype(float)
    lut = dict(zip(np.round(cand["beat"], 6), cand["strength"], strict=True))
    df["boundary_strength"] = [lut.get(round(x, 6), 0.0) for x in b]


_FAR_BARS = 64.0  # distance used when no event lies ahead / behind (kernels are ~0 there)


def _dist(events: np.ndarray, b: np.ndarray, ahead: bool) -> np.ndarray:
    """Beats from ``b`` to the next event at or after it (``ahead``) or since the last event
    at or before it; ``inf`` when there is none."""
    ev = np.sort(np.asarray(events, float))
    if len(ev) == 0:
        return np.full(len(b), np.inf)
    if ahead:
        i = np.searchsorted(ev, b - _EPS, side="left")
        return np.where(i < len(ev), ev[np.minimum(i, len(ev) - 1)] - b, np.inf)
    i = np.searchsorted(ev, b + _EPS, side="right") - 1
    return np.where(i >= 0, b - ev[np.maximum(i, 0)], np.inf)


def _phrase_detail_columns(df: pd.DataFrame, on: pd.DataFrame, phrases: pd.DataFrame,
                           ends: Sequence[float] | None, bpb: float) -> None:
    b = df["beat"].to_numpy()
    s = phrases["start_beat"].to_numpy()
    ob = on["beat"].to_numpy()
    oidx = np.clip(np.searchsorted(s, ob + _EPS, side="right") - 1, 0, len(s) - 1)
    first_on = pd.Series(ob).groupby(oidx).min().reindex(range(len(s))).to_numpy()
    last_on = pd.Series(ob).groupby(oidx).max().reindex(range(len(s))).to_numpy()
    e = np.asarray(ends, float) if ends is not None else last_on[np.isfinite(last_on)]
    idx = np.clip(np.searchsorted(s, b + _EPS, side="right") - 1, 0, len(s) - 1)
    d_end = np.minimum(_dist(e, b, ahead=True) / bpb, _FAR_BARS)
    s_end = _dist(e, b, ahead=False) / bpb
    s_end = np.minimum(np.where(s_end > _EPS, s_end, _FAR_BARS), _FAR_BARS)
    s_start = np.clip((b - np.nan_to_num(first_on[idx], nan=b.min())) / bpb, 0, _FAR_BARS)
    for k in (0.5, 1.0, 2.0):
        df[f"pre_end_k{k:g}"] = np.exp(-d_end / k)
    df["post_end_k1"] = np.exp(-s_end)
    df["post_start_k1"] = np.exp(-s_start)
    plen = np.nan_to_num((last_on - first_on)[idx], nan=0.0) / bpb + 1.0 / bpb
    df["phrase_len_log2"] = np.log2(np.maximum(plen, 0.25))
    df["pos_x_len"] = df["phrase_pos"] * df["phrase_len_log2"]
    df["possq_x_len"] = df["phrase_pos_sq"] * df["phrase_len_log2"]


_CADENCE_TYPES = {"PAC": ("PAC",), "HC": ("HC",)}


def _cadence_columns(df: pd.DataFrame, cad: pd.DataFrame, bpb: float) -> None:
    b = df["beat"].to_numpy()
    kind = cad["cadence"].astype(str).to_numpy()
    beats = cad["beat"].to_numpy(float)
    known = np.isin(kind, [k for v in _CADENCE_TYPES.values() for k in v])
    for name, labels in [*_CADENCE_TYPES.items(), ("other", None)]:
        sel = ~known if labels is None else np.isin(kind, labels)
        d = np.minimum(_dist(beats[sel], b, ahead=True) / bpb, _FAR_BARS)
        df[f"pre_cad_{name}_k1"] = np.exp(-d)
    s_cad = _dist(beats, b, ahead=False) / bpb
    df["post_cad_k1"] = np.exp(-np.minimum(np.where(s_cad > _EPS, s_cad, _FAR_BARS), _FAR_BARS))


# --------------------------------------------------------------------------- main


def score_basis(
    score: Any,
    *,
    phrase_boundaries_beats: Sequence[float] | None = None,
    config: BasisConfig | None = None,
    phrase_ends_beats: Sequence[float] | None = None,
    cadences: pd.DataFrame | None = None,
) -> ScoreBasis:
    """Basis features of every non-grace note and onset of a (performed, unfolded) score.

    Args:
        score: ``pianolens.data.types.Score``; use the one ``align_performance`` returns
            (``part`` kept) so markings are read and ids match the alignment.
        phrase_boundaries_beats: phrase starts in score beats (annotations, R-08); replaces
            the boundary proxy.
        config: :class:`BasisConfig`.
        phrase_ends_beats: phrase ends in score beats (e.g. annotated cadential arrivals);
            used by the ``phrase_detail`` group only (default: last onset of each phrase).
        cadences: ``beat`` and ``cadence`` (DCML type: PAC, HC, IAC, EC, DC) columns; adds
            the ``cadence`` group.

    Returns:
        :class:`ScoreBasis` (columns and definitions in the module docstring).
    """
    cfg = config or BasisConfig()
    na = score.notes
    names = na.dtype.names or ()
    part = getattr(score, "part", None)
    grace = na["is_grace"].astype(bool) if "is_grace" in names else np.zeros(len(na), bool)
    rows = np.where(~grace)[0]
    df = pd.DataFrame({
        "_row": rows,
        "score_id": na["id"][rows].astype(str),
        "beat": na["onset_beat"][rows].astype(float),
        "quarter": na["onset_quarter"][rows].astype(float),
        "pitch": na["pitch"][rows].astype(int),
        "duration_beat": na["duration_beat"][rows].astype(float),
        "voice": na["voice"][rows].astype(int) if "voice" in names else 0,
        "staff": na["staff"][rows].astype(int) if "staff" in names else 0,
        "ts_beats": na["ts_beats"][rows].astype(float) if "ts_beats" in names else 4.0,
        "ts_beat_type": na["ts_beat_type"][rows].astype(float) if "ts_beat_type" in names
        else 4.0,
    })
    if len(df) == 0:
        raise ValueError("score has no non-grace notes")
    split = [base_note_id(x) for x in df["score_id"]]
    df["base_id"] = [s[0] for s in split]
    df["repeat_index"] = [s[1] for s in split]
    meta: dict[str, Any] = {"has_part": part is not None, "n_grace_skipped": int(grace.sum())}
    bpb = _bar_positions(df, score)
    meta["beats_per_bar"] = bpb

    # metrical
    bib = df["beat_in_bar"].to_numpy()
    ms = metrical_strength(bib, df["ts_beats"].to_numpy(), df["ts_beat_type"].to_numpy())
    df["metrical_strength"] = ms
    df["is_downbeat"] = (ms == 1.0).astype(float)
    df["is_strong_beat"] = (ms == 0.75).astype(float)
    df["is_beat"] = (ms == 0.5).astype(float)
    df["is_offbeat"] = (ms < 0.5).astype(float)
    phase = 2 * np.pi * bib / np.maximum(df["bar_beats"].to_numpy(), _EPS)
    df["beat_phase_sin"] = np.sin(phase)
    df["beat_phase_cos"] = np.cos(phase)

    on = _onset_table(df)
    _pitch_duration_columns(df, on)
    on["metrical_strength"] = df.groupby("beat")["metrical_strength"].max().to_numpy()

    # markings
    breaks = score_tempo_breaks(score)
    ev = _dynamics_events(part, bpb, cfg) if part is not None else pd.DataFrame(
        columns=["kind", "text", "level", "start_beat", "end_beat", "has_end"])
    _dynamics_columns(df, ev)
    _articulation_columns(df, na, part)
    _tempo_columns(df, part, breaks, bpb, cfg)
    _harmony_columns(df, score, cfg, meta)

    # phrases
    cand = _proxy_boundaries(df, on, part, breaks, bpb, cfg)
    source = None
    if phrase_boundaries_beats is None and cfg.phrase_source == "cadence":
        from pianolens.features.cadence import cadence_phrase_ends

        cad = cadence_phrase_ends(score)
        phrase_boundaries_beats = cad.starts
        if phrase_ends_beats is None:
            phrase_ends_beats = cad.end_beats
        source = "cadence"
        meta["cadence_ends"] = cad.end_beats
    elif cfg.phrase_source not in ("proxy", "cadence"):
        raise ValueError(f"unknown phrase_source {cfg.phrase_source!r}")
    phrases = _phrases(on, cand, phrase_boundaries_beats, bpb, cfg)
    if source is not None:
        phrases.loc[phrases["source"] == "external", "source"] = source
    _phrase_columns(df, on, phrases, cand)
    groups = {g: list(cols) for g, cols in FEATURE_GROUPS.items()}
    if cfg.phrase_detail:
        _phrase_detail_columns(df, on, phrases, phrase_ends_beats, bpb)
        groups["phrase_detail"] = list(OPTIONAL_GROUPS["phrase_detail"])
    if cadences is not None:
        _cadence_columns(df, pd.DataFrame(cadences), bpb)
        groups["cadence"] = list(OPTIONAL_GROUPS["cadence"])
    span = df["beat"].max() - df["beat"].min()
    df["piece_pos"] = (df["beat"] - df["beat"].min()) / span if span > 0 else 0.0

    feat_cols = [c for cols in groups.values() for c in cols]
    df[feat_cols] = df[feat_cols].astype(float).fillna(0.0)
    df = df.drop(columns=["_row"]).reset_index(drop=True)
    onsets = _onset_features(df, feat_cols)
    return ScoreBasis(df, onsets, phrases, ev, groups, meta)


_MAX_OVER_CHORD = set(FEATURE_GROUPS["dynamics"] + FEATURE_GROUPS["articulation"]
                      + FEATURE_GROUPS["tempo_marks"] + FEATURE_GROUPS["fermata"])


def _onset_features(df: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    """One row per onset: features of the top note; markings are the max over the chord."""
    top = df.sort_values(["beat", "pitch"]).groupby("beat", sort=True).tail(1).set_index("beat")
    g = df.groupby("beat", sort=True)
    out = pd.DataFrame(index=top.index)
    out["n_notes"] = g.size()
    for c in ("measure_idx", "measure_number", "beat_in_bar", "bar_beats", "pitch"):
        out[c] = top[c]
    for c in feat_cols:
        out[c] = g[c].max() if c in _MAX_OVER_CHORD else top[c]
    return out.reset_index()
