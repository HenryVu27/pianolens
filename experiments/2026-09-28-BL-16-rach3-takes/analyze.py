"""BL-16 analysis: reads artifacts/groups.jsonl, writes artifacts/analysis.txt and rows.csv.

    uv run python experiments/2026-09-28-BL-16-rach3-takes/analyze.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ART = Path(__file__).resolve().parent / "artifacts"
B = 2000
SEED = 0
CHANNELS = ("timing", "articulation", "velocity", "tempo")


def _get(block: dict, ch: str) -> dict:
    s = next((r for r in block["summary"] if r["channel"] == ch), {})
    t = next((r for r in block["structure"] if r["channel"] == ch), {})
    return {
        "icc": s.get("icc_single", np.nan), "sd_spec": s.get("sd_specific", np.nan),
        "sd_spec_ms": s.get("sd_specific", np.nan) * 1000 * float(np.mean(block["beat_sec"]))
        if ch == "timing" else np.nan,
        "r2_sum": t.get("r2_pair_sum", np.nan), "r2_diff": t.get("r2_pair_diff", np.nan),
        "n": s.get("n", np.nan),
    }  # fmt: skip


def rows(window: str) -> pd.DataFrame:
    out = []
    for line in open(ART / f"groups_{window}.jsonl"):
        g = json.loads(line)
        if g["status"] != "ok":
            continue
        day = g["key"].split("|")[2]
        for ch in CHANNELS:
            r = {"key": g["key"], "pianist": g["pianist"], "level": g["level"],
                 "exercise": g["exercise"], "cluster": f"{g['pianist']}|{day}", "channel": ch,
                 "k": len(g["take_ids"]), "b1_pianist": g.get("b1_pianist"),
                 "beat_sec_a1": g["same"]["beat_sec"][0]}  # fmt: skip
            for blk in ("all", "same", "cross"):
                if blk in g:
                    for kk, v in _get(g[blk], ch).items():
                        r[f"{blk}_{kk}"] = v
            out.append(r)
    df = pd.DataFrame(out)
    if "cross_r2_diff" in df:
        df["gap_r2_diff"] = df["cross_r2_diff"] - df["same_r2_diff"]
        df["gap_r2_sum"] = df["cross_r2_sum"] - df["same_r2_sum"]
    return df


def boot(df: pd.DataFrame, col: str) -> tuple[float, float, float, float, float, int]:
    """Mean over groups; 95% cluster bootstrap (clusters = pianist-day) and t-interval over
    cluster means."""
    d = df[["cluster", col]].dropna()
    if len(d) == 0:
        return (np.nan,) * 5 + (0,)
    cl = d.groupby("cluster")[col].agg(["sum", "size"])
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(cl), size=(B, len(cl)))
    s, n = cl["sum"].to_numpy()[idx].sum(1), cl["size"].to_numpy()[idx].sum(1)
    lo, hi = np.percentile(s / n, [2.5, 97.5])
    cm = (cl["sum"] / cl["size"]).to_numpy()
    if len(cm) > 1:
        h = stats.t.ppf(0.975, len(cm) - 1) * cm.std(ddof=1) / np.sqrt(len(cm))
        tlo, thi = cm.mean() - h, cm.mean() + h
    else:
        tlo = thi = np.nan
    return float(d[col].mean()), float(lo), float(hi), float(tlo), float(thi), len(cl)


def fmt(t: tuple) -> str:
    m, lo, hi, tlo, thi, nc = t
    return f"{m:.3f} [{lo:.3f}, {hi:.3f}] (t [{tlo:.3f}, {thi:.3f}], {nc} clusters)"


def main() -> None:
    L = []
    for window in ("same_day", "next_day"):
        if not (ART / f"groups_{window}.jsonl").exists():
            continue
        df = rows(window)
        df.to_csv(ART / f"rows_{window}.csv", index=False)
        L.append(f"##### window {window}")
        L += report(df)
    text = "\n".join(L)
    (ART / "analysis.txt").write_text(text + "\n")
    print(text)


def report(df: pd.DataFrame) -> list[str]:
    L = []
    for ch in CHANNELS:
        d = df[df.channel == ch]
        L.append(f"=== {ch} ===")
        for name, sub in (("beginner", d[d.level == "beginner"]),
                          ("advanced", d[d.level == "advanced"]),
                          *((f"pianist {p}", g) for p, g in d.groupby("pianist"))):  # fmt: skip
            if len(sub) == 0:
                continue
            L.append(f"-- {name}: {len(sub)} groups, {sub.cluster.nunique()} pianist-days, "
                     f"takes {int(sub.k.sum())}")
            for col in ("all_icc", "all_sd_spec", "all_sd_spec_ms", "same_icc", "cross_icc",
                        "same_sd_spec", "cross_sd_spec", "same_r2_sum", "same_r2_diff",
                        "cross_r2_sum", "cross_r2_diff", "gap_r2_diff", "gap_r2_sum"):
                if col in sub and sub[col].notna().any():
                    L.append(f"   {col:16s} {fmt(boot(sub, col))}")
            if "gap_r2_diff" in sub:
                pos, tot = int((sub.gap_r2_diff > 0).sum()), int(sub.gap_r2_diff.notna().sum())
                L.append(f"   groups with gap_r2_diff > 0: {pos} of {tot}")
    return L


if __name__ == "__main__":
    main()
