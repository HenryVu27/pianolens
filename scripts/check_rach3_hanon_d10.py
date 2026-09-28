"""D-10: beginner vs advanced evenness in Rach3 Hanon practice sessions (score-free).

    uv run python scripts/check_rach3_hanon_d10.py

Rach3's Hanon "score" is the whole book (22,071 notes, 1,433 bars) and each session file is a
long practice run through an unknown subset of exercises, so F-01 alignment and the F-04
features (which need a score) cannot run. Hanon exercises are continuous sixteenth notes with
both hands an octave apart, which allows a score-free measure close to Kim et al. 2021
(landscape 1.5: Hanon No. 1, relative-IOI SD and between-hand SD, experts vs amateurs):

* **Events**: onsets closer than ``CHORD_MS`` merge into one event (the two hands).
* **Steady streams**: IOIs between events, each divided by the running median of the
  ``WIN`` IOIs around it. A stream is a stretch of at least ``MIN_STREAM`` consecutive IOIs
  whose ratio lies within [0.6, 1.6]. Stops, slow practice and rhythm changes break streams.
* ``ioi_cv``: RMS of (ratio - 1) over a stream (tempo-normalized, as ``even_ioi_cv``);
  ``ioi_cv_robust``: 1.4826 * MAD of the ratio. ``rate_nps``: events per second in the stream.
* ``vel_sd``: SD of velocity around its running median (``WIN`` events), within the stream.
* ``octave_async_sd_ms``: for events that hold exactly two notes 12 or 24 semitones apart, the
  upper minus lower onset; robust SD per stream (between-hand spread, no velocity fit).

Streams are pooled per (session, note-rate bin) and then per pianist. With 1 beginner and 2
advanced pianists (p4 did not practise Hanon), this is descriptive: no performer-level
inference is possible. Writes ``data/interim/skill_control_d10/rach3_hanon_streams.csv``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "interim" / "skill_control_d10"
CHORD_MS = 40.0
WIN = 9
MIN_STREAM = 24
BINS = [0, 4, 6, 8, 10, 12, 30]


def _rsd(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) > 3 else np.nan


def streams(notes: np.ndarray) -> list[dict]:
    order = np.argsort(notes["onset_sec"], kind="stable")
    on = notes["onset_sec"][order].astype(float)
    pitch = notes["pitch"][order].astype(int)
    vel = notes["velocity"][order].astype(float)
    # events
    starts = np.r_[0, np.flatnonzero(np.diff(on) * 1000 > CHORD_MS) + 1]
    ends = np.r_[starts[1:], len(on)]
    ev_t = np.array([on[a:b].mean() for a, b in zip(starts, ends, strict=True)])
    ev_v = np.array([vel[a:b].mean() for a, b in zip(starts, ends, strict=True)])
    ev_async = np.full(len(starts), np.nan)
    for k, (a, b) in enumerate(zip(starts, ends, strict=True)):
        if b - a == 2 and abs(pitch[a] - pitch[a + 1]) in (12, 24):
            hi = a if pitch[a] > pitch[a + 1] else a + 1
            lo = a + 1 if hi == a else a
            ev_async[k] = 1000 * (on[hi] - on[lo])
    ioi = np.diff(ev_t)
    if len(ioi) < MIN_STREAM:
        return []
    med = pd.Series(ioi).rolling(WIN, center=True, min_periods=3).median().to_numpy()
    ratio = ioi / med
    ok = (ratio > 0.6) & (ratio < 1.6)
    out = []
    k = 0
    while k < len(ok):
        if not ok[k]:
            k += 1
            continue
        j = k
        while j < len(ok) and ok[j]:
            j += 1
        if j - k >= MIN_STREAM:
            r = ratio[k:j]
            ev = slice(k, j + 1)
            v = ev_v[ev]
            vmed = pd.Series(v).rolling(WIN, center=True, min_periods=3).median().to_numpy()
            out.append({
                "n_iois": j - k,
                "rate_nps": (j - k) / float(ev_t[j] - ev_t[k]),
                "ioi_cv": float(np.sqrt(np.mean((r - 1) ** 2))),
                "ioi_cv_robust": _rsd(r),
                "vel_sd": float(np.std(v - vmed)),
                "octave_async_sd_ms": _rsd(ev_async[ev]),
                "octave_async_n": int(np.isfinite(ev_async[ev]).sum()),
                "octave_async_median_ms": float(np.nanmedian(ev_async[ev]))
                if np.isfinite(ev_async[ev]).any() else np.nan,
            })  # fmt: skip
        k = j
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import rach3

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in rach3.iter_performances(piece_code="hanoncexercs"):
        for s in streams(p.notes):
            rows.append({"performance_id": p.performance_id,
                         "pianist": p.performer_id.split(":")[1], "level": p.meta["level"],
                         "date": p.meta["date"], **s})  # fmt: skip
    df = pd.DataFrame(rows)
    df["rate_bin"] = pd.cut(df["rate_nps"], BINS)
    df.to_csv(OUT / "rach3_hanon_streams.csv", index=False)
    pd.set_option("display.width", 250)
    print(df.groupby("pianist").agg(sessions=("performance_id", "nunique"),
                                    streams=("n_iois", "size"), iois=("n_iois", "sum")))
    w = df.assign(w=df["n_iois"])
    agg = (w.groupby(["rate_bin", "pianist"], observed=True)
           .apply(lambda g: pd.Series({
               "sessions": g["performance_id"].nunique(), "iois": g["n_iois"].sum(),
               "ioi_cv": np.sqrt(np.average(g["ioi_cv"] ** 2, weights=g["w"])),
               "ioi_cv_robust_med": g["ioi_cv_robust"].median(),
               "vel_sd_med": g["vel_sd"].median(),
               "octave_async_sd_ms_med": g["octave_async_sd_ms"].median(),
               "octave_async_median_ms": g["octave_async_median_ms"].median(),
           }), include_groups=False))  # fmt: skip
    print(agg.round(3).to_string())


if __name__ == "__main__":
    main()
