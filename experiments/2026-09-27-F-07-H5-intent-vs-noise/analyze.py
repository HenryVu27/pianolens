"""F-07 / H5 step 2: QC, aggregation, cluster bootstrap, sensitivity. Reads
``artifacts/groups.jsonl`` (+ ``asap_groups.jsonl``), writes ``artifacts/*.csv`` and prints the
tables copied into README.md.

    uv run python experiments/2026-09-27-F-07-H5-intent-vs-noise/analyze.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.eval.bootstrap import bootstrap_ci

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
CHANNELS = ("timing", "articulation", "tempo", "velocity")
MIN_TIMING_OBS = 100
MIN_BLOCKS = 3
N_BOOT = 2000
SEED = 0
BAND = 0.02


def long_table(path: Path, group_cols: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, groups = [], []
    for line in path.read_text().splitlines():
        d = json.loads(line)
        g = {c: d.get(c) for c in group_cols}
        groups.append({**g, "status": d.get("status", "ok"), "n_loaded": d.get("n_loaded"),
                       "n_rows": d.get("n_rows"), "n_errors": len(d.get("errors", [])),
                       **{f"k_{t}": v.get("k") for t, v in d.get("by_threshold", {}).items()},
                       **{f"n_dedup_{t}": v.get("n_after_dedup")
                          for t, v in d.get("by_threshold", {}).items()}})
        for thr, b in d.get("by_threshold", {}).items():
            summ = {s["channel"]: s for s in b.get("summary", [])}
            for s in b.get("structure", []):
                ch = s["channel"]
                vc = summ.get(ch, {})
                rows.append({**g, "threshold": float(thr), "channel": ch, "k": b["k"],
                             **{k: s.get(k) for k in ("n", "n_blocks", "n_written_bars",
                                                       "undefined_reason", "n_pairs",
                                                       "r2_consistent",
                                                       "r2_specific", "r2_pair_sum",
                                                       "r2_pair_diff", "delta_pair",
                                                       "var_pair_sum", "var_pair_diff")},
                             **{k: vc.get(k) for k in ("icc_single", "icc_mean",
                                                        "var_consistent", "var_specific",
                                                        "n_dropped")}})
    return pd.DataFrame(rows), pd.DataFrame(groups)


def eligible(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    t = df[(df["channel"] == "timing") & (df["n"] >= MIN_TIMING_OBS)
           & (df["n_blocks"] >= MIN_BLOCKS) & (df["k"] >= 2)]
    if "undefined_reason" in t:  # F-05d minimum length (>= 12 distinct written bars)
        t = t[t["undefined_reason"].fillna("") == ""]
    ok = t[keys + ["threshold"]].drop_duplicates()
    return df.merge(ok, on=keys + ["threshold"], how="inner")


def _mean(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else float("nan")


def summarize(df: pd.DataFrame, cluster: str) -> pd.DataFrame:
    out = []
    for (thr, ch), g in df.groupby(["threshold", "channel"], sort=False):
        row = {"threshold": thr, "channel": ch, "n_groups": len(g),
               "n_pianists": g["performer_id"].nunique(), "n_pieces": g["piece_id"].nunique(),
               "share_delta_pos": float((g["delta_pair"] > 0).mean())}
        for col in ("delta_pair", "r2_pair_sum", "r2_pair_diff", "r2_consistent", "r2_specific",
                    "icc_single"):
            v = g[col].to_numpy(float)
            bs = bootstrap_ci(_mean, v, groups=g[cluster].to_numpy(), n_boot=N_BOOT, seed=SEED)
            row[col] = bs.estimate
            row[f"{col}_lo"] = bs.low
            row[f"{col}_hi"] = bs.high
        # pianist-level mean (each pianist weighs once)
        pm = g.groupby("performer_id")["delta_pair"].mean().to_numpy()
        bs = bootstrap_ci(_mean, pm, n_boot=N_BOOT, seed=SEED)
        row["delta_pianist_mean"], row["delta_pianist_lo"], row["delta_pianist_hi"] = \
            bs.estimate, bs.low, bs.high
        out.append(row)
    return pd.DataFrame(out)


def verdict(row: pd.Series) -> str:
    lo, hi = row["delta_pair_lo"], row["delta_pair_hi"]
    if lo > 0:
        v = "supported"
        if row["r2_pair_diff_lo"] > BAND:
            v = "partly supported (inconsistent part also score-structured)"
        return v
    if hi < 0 or (lo >= -BAND and hi <= BAND):
        return "falsified"
    return "inconclusive"


def main() -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    keys = ["piece_id", "performer_id"]
    df, groups = long_table(ART / "groups.jsonl", tuple(keys))
    groups.to_csv(ART / "groups_status.csv", index=False)
    meta = json.loads((ART / "meta.json").read_text())
    print("meta:", meta)
    print("group status:", groups["status"].value_counts().to_dict())
    for t in ("0.98", "0.95", "0.9"):
        c = f"k_{t}"
        if c in groups:
            print(f"threshold {t}: groups with k >= 2 after dedup: {(groups[c] >= 2).sum()}, "
                  f"k = 1 (all duplicates): {(groups[c] == 1).sum()}; takes kept "
                  f"{groups.loc[groups[c] >= 2, c].sum()}")
    el = eligible(df, keys)
    el.to_csv(ART / "group_channel_rows.csv", index=False)
    by_p = summarize(el, "performer_id")
    by_p.to_csv(ART / "summary_by_pianist.csv", index=False)
    by_piece = summarize(el[el["threshold"] == 0.98], "piece_id")
    by_piece.to_csv(ART / "summary_by_piece.csv", index=False)
    cols = ["threshold", "channel", "n_groups", "n_pianists", "n_pieces", "delta_pair",
            "delta_pair_lo", "delta_pair_hi", "r2_pair_sum", "r2_pair_sum_lo", "r2_pair_sum_hi",
            "r2_pair_diff", "r2_pair_diff_lo", "r2_pair_diff_hi", "share_delta_pos",
            "delta_pianist_mean", "delta_pianist_lo", "delta_pianist_hi"]
    print("\nPrimary + secondary (cluster bootstrap over pianists):")
    print(by_p[cols].round(4).to_string(index=False))
    print("\nk-mean vs per-take deviation (unbalanced view) and ICC:")
    print(by_p[["threshold", "channel", "r2_consistent", "r2_consistent_lo", "r2_consistent_hi",
                "r2_specific", "r2_specific_lo", "r2_specific_hi", "icc_single", "icc_single_lo",
                "icc_single_hi"]].round(4).to_string(index=False))
    print("\nBootstrap over pieces (threshold 0.98):")
    print(by_piece[cols].round(4).to_string(index=False))
    prim = by_p[(by_p["threshold"] == 0.98) & (by_p["channel"] == "timing")].iloc[0]
    print("\nVERDICT (timing, 0.98, pianist bootstrap):", verdict(prim))
    for _, r in by_p.iterrows():
        print(f"  reading {r['threshold']} {r['channel']}: {verdict(r)}")
    # per-pianist table (primary)
    p = el[(el["threshold"] == 0.98) & (el["channel"] == "timing")]
    pt = p.groupby("performer_id").agg(n_groups=("delta_pair", "size"),
                                       delta=("delta_pair", "mean"),
                                       r2_sum=("r2_pair_sum", "mean"),
                                       r2_diff=("r2_pair_diff", "mean"),
                                       icc=("icc_single", "mean")).sort_values("n_groups",
                                                                               ascending=False)
    pt.to_csv(ART / "per_pianist_timing.csv")
    print("\nPer pianist (timing, >= 10 groups):")
    print(pt[pt["n_groups"] >= 10].round(3).to_string())
    print(f"pianists with mean delta > 0: {(pt['delta'] > 0).sum()} of {len(pt)}")
    print("\nk distribution (0.98):", p["k"].value_counts().sort_index().to_dict())
    # k == 2 only (fully balanced pairs, one pair per group)
    k2 = el[(el["threshold"] == 0.98) & (el["k"] == 2)]
    if len(k2):
        s2 = summarize(k2, "performer_id")
        print("\nk == 2 groups only (0.98):")
        print(s2[cols[:14]].round(4).to_string(index=False))

    asap = ART / "asap_groups.jsonl"
    if asap.exists():
        adf, ag = long_table(asap, ("folder", "piece_id", "performer_id"))
        print("\nASAP (Disklavier) groups:", len(ag), "k>=2 at 0.98:",
              int((ag.get("k_0.98", pd.Series(dtype=float)) >= 2).sum()))
        for line in asap.read_text().splitlines():
            d = json.loads(line)
            for pr in d.get("pairs", []):
                print(f"  {d['folder']} {d['performer_id']}: {pr['take_a']} vs {pr['take_b']} "
                      f"r_timing {pr.get('timing', float('nan')):.3f} "
                      f"r_tempo {pr.get('tempo', float('nan')):.3f}")
        a = adf[(adf["threshold"] == 0.98) & (adf["k"] >= 2)]
        if len(a):
            print(a[["folder", "performer_id", "channel", "k", "n", "n_blocks", "r2_pair_sum",
                     "r2_pair_diff", "delta_pair", "icc_single"]].round(3).to_string(index=False))
            a.to_csv(ART / "asap_rows.csv", index=False)
            a = a.assign(performer=a["performer_id"])
            print("\nASAP summary (0.98; bootstrap over performers, descriptive):")
            for ch, g in a.groupby("channel", sort=False):
                parts = []
                for col in ("r2_pair_sum", "r2_pair_diff", "delta_pair", "icc_single"):
                    bs = bootstrap_ci(_mean, g[col].to_numpy(float),
                                      groups=g["performer"].to_numpy(), n_boot=N_BOOT, seed=SEED)
                    parts.append(f"{col} {bs}")
                print(f"  {ch} (n={len(g)}, performers={g['performer'].nunique()}): "
                      + "; ".join(parts) + f"; delta>0 in {(g['delta_pair'] > 0).sum()}")


if __name__ == "__main__":
    main()
