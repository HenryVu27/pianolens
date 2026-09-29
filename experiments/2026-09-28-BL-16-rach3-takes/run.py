"""BL-16: same-day repeated Hanon takes (Rach3), F-07 analysis with a cross-pianist control.

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
        uv run python experiments/2026-09-28-BL-16-rach3-takes/run.py --workers 6

Reads the takes built by ``scripts/build_rach3_hanon_takes.py``. Writes
``artifacts/groups_<window>.jsonl``: one line per same-pianist group with the decomposition and
structure of all its takes (``all``), of the same-pianist pair (a1, a2) (``same``) and of the
cross-pianist pair (a1, b1) (``cross``). Definitions in the README.
"""

from __future__ import annotations

import argparse
import json
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
SEED = 0
CHANNELS = ("timing", "tempo", "velocity", "articulation")

_T = None


def _takes():
    global _T
    if _T is None:
        from pianolens.data.rach3_takes import HanonTakes

        _T = HanonTakes()
    return _T


def _score(aps, ids):
    from pianolens.features.takes import TakesConfig, decompose_takes, take_structure
    from pianolens.features.tempo import tempo_model

    tempos = [tempo_model(ap) for ap in aps]
    res = decompose_takes(aps, tempos=tempos, config=TakesConfig(channels=CHANNELS),
                          take_ids=ids)  # fmt: skip
    st = take_structure(res, TakesConfig(channels=CHANNELS))
    beat_sec = [float(np.nanmedian(t.positions["beat_period_sec"])) for t in tempos]
    summ = res.summary.drop(columns=[c for c in res.summary.columns if c.startswith("level_")])
    return {
        "summary": summ.to_dict("records"),
        "structure": st.to_dict("records"),
        "beat_sec": beat_sec,
        "pairs_r": res.pairs.to_dict("records"),
    }


def _group(job: dict) -> dict:
    warnings.filterwarnings("ignore")
    T = _takes()
    out = {k: job[k] for k in ("key", "pianist", "level", "exercise", "window", "take_ids")}
    try:
        aps = T.aligned(job["take_ids"])
        out["all"] = _score(aps, job["take_ids"])
        a1, a2, b1 = job["a1"], job["a2"], job["b1"]
        out["a1"], out["a2"], out["b1"] = a1, a2, b1
        out["b1_pianist"] = job["b1_pianist"]
        m = {tid: ap for tid, ap in zip(job["take_ids"], aps, strict=True)}
        out["same"] = _score([m[a1], m[a2]], [a1, a2])
        if b1 is not None:
            out["cross"] = _score([m[a1], T.aligned([b1])[0]], [a1, b1])
        out["status"] = "ok"
    except Exception as e:  # noqa: BLE001 - record and continue
        out["status"] = f"error: {e!r}"
    return out


def _cross(ok: pd.DataFrame, p: str, ex: int, level: str, rng) -> tuple:
    others = ok[(ok["exercise"] == ex) & (ok["pianist"] != p)]
    if level == "advanced":  # primary cross partner of an advanced pianist: the other advanced
        others = others[others["level"] == "advanced"]
    if not len(others):
        return None, None
    pick = others.iloc[int(rng.integers(len(others)))]
    return pick["take_id"], pick["pianist"]


def build_jobs(takes: pd.DataFrame, window: str) -> list[dict]:
    """``same_day``: groups (pianist, exercise, day) with >= 2 QC takes (first 8 in time order;
    a1, a2 = the first two). ``next_day``: per pianist and exercise, days d and d + 1 that both
    have a QC take, paired greedily without reusing a day; a1 = first take on d, a2 = first
    take on d + 1."""
    rng = np.random.default_rng(SEED)
    ok = takes[takes["qc_ok"]].copy()
    ok["day"] = pd.to_datetime(ok["date"]).dt.normalize()
    ok = ok.sort_values(["pianist", "day", "session", "t0_sec"])
    jobs = []
    if window == "same_day":
        for (p, ex, day), g in ok.groupby(["pianist", "exercise", "day"], sort=True):
            if len(g) < 2:
                continue
            ids = g["take_id"].tolist()[:8]
            level = g["level"].iloc[0]
            b1, b1p = _cross(ok, p, ex, level, rng)
            jobs.append({"key": f"{p}|{ex}|{day.date()}", "pianist": p, "level": level,
                         "exercise": int(ex), "window": window, "take_ids": ids,
                         "a1": ids[0], "a2": ids[1], "b1": b1, "b1_pianist": b1p})  # fmt: skip
    elif window == "next_day":
        for (p, ex), g in ok.groupby(["pianist", "exercise"], sort=True):
            first = g.groupby("day").head(1).set_index("day")
            days = list(first.index)
            used: set = set()
            for d in days:
                d1 = d + pd.Timedelta(days=1)
                if d in used or d1 not in first.index or d1 in used:
                    continue
                used |= {d, d1}
                ids = [first.at[d, "take_id"], first.at[d1, "take_id"]]
                level = g["level"].iloc[0]
                b1, b1p = _cross(ok, p, ex, level, rng)
                jobs.append({"key": f"{p}|{ex}|{d.date()}", "pianist": p, "level": level,
                             "exercise": int(ex), "window": window, "take_ids": ids,
                             "a1": ids[0], "a2": ids[1], "b1": b1, "b1_pianist": b1p})  # fmt: skip
    else:
        raise ValueError(window)
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--window", choices=("same_day", "next_day"), default="same_day")
    args = ap.parse_args()
    from pianolens.data.rach3_takes import HanonTakes

    ART.mkdir(parents=True, exist_ok=True)
    takes = HanonTakes().takes
    jobs = build_jobs(takes, args.window)
    if args.limit:
        jobs = jobs[: args.limit]
    pd.DataFrame(jobs).to_csv(ART / f"jobs_{args.window}.csv", index=False)
    out = ART / f"groups_{args.window}.jsonl"
    with open(out, "w") as f, ProcessPoolExecutor(args.workers) as ex:
        for r in ex.map(_group, jobs):
            f.write(json.dumps(r, default=float) + "\n")
            f.flush()
            print(r["key"], r["status"], flush=True)


if __name__ == "__main__":
    main()
