"""BL-19b post-hoc diagnostics (not pre-registered; written after the ``score`` stage results).

    uv run python experiments/2026-10-10-BL-19b-hand-proxies/posthoc.py

1. Are the staff/hand mismatches label artefacts? (a) hand-identity swaps: measure passes where
   both staves are mostly labelled with the other hand; (b) hand-order violations: a note
   labelled L above every R-labelled note sounding within 50 ms, or R below every L; (c) run
   lengths of consecutive mismatches in performance order.
2. BL-19 recommendation 1 (drop hand-sync events with a P1 or P3 note): the event mismatch with
   and without those events, and the event share the BL-19 proxies predict on the same events.

Writes ``artifacts/posthoc.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.features import hand_proxies as hp

ART = Path(__file__).resolve().parent / "artifacts"
SEED = 20261010


def main() -> None:
    n0 = pd.read_parquet(ART / "notes_labelled.parquet")
    n = n0[n0["hand"].isin(["L", "R"])].reset_index(drop=True)
    n["bad"] = n["STAFF"] != n["hand"]
    out: dict = {"n_mismatch": int(n["bad"].sum())}
    # 1a swaps
    k = ["record_time", "take", "measure_idx"]
    g = n.groupby(k + ["staff"]).agg(nn=("bad", "size"), nb=("bad", "sum")).unstack(
        "staff", fill_value=0)
    g.columns = [f"{a}{b}" for a, b in g.columns]
    g["swap"] = ((g["nn1"] >= 2) & (g["nn2"] >= 2) & (g["nb1"] / g["nn1"].clip(lower=1) >= 0.5)
                 & (g["nb2"] / g["nn2"].clip(lower=1) >= 0.5))  # fmt: skip
    n = n.join(g["swap"], on=k)
    out["swap_measure_passes"] = [int(g["swap"].sum()), len(g)]
    out["mismatch_in_swap_measures"] = int((n["bad"] & n["swap"]).sum())
    # 1b hand order
    viol = np.zeros(len(n), bool)
    for _, d in n.groupby("record_time"):
        d = d.sort_values("perf_onset_sec", kind="stable")
        t, p, h = d["perf_onset_sec"].to_numpy(), d["pitch"].to_numpy(), d["hand"].to_numpy()
        ix = d.index.to_numpy()
        lo, hi = np.searchsorted(t, t - 0.05), np.searchsorted(t, t + 0.05, side="right")
        for i in range(len(d)):
            oth = p[lo[i]:hi[i]][h[lo[i]:hi[i]] != h[i]]
            if len(oth):
                viol[ix[i]] = (h[i] == "L" and p[i] > oth.max()) or (h[i] == "R" and p[i] < oth.min())
    n["order_viol"] = viol
    out["order_violation_share"] = {"all": float(viol.mean()),
                                    "mismatched": float(n.loc[n["bad"], "order_viol"].mean()),
                                    "agreeing": float(n.loc[~n["bad"], "order_viol"].mean())}  # fmt: skip
    out["order_violation_by_piece_top"] = (n[n["bad"]].groupby("score_pid")["order_viol"].sum()
                                           .sort_values(ascending=False).head(5).to_dict())  # fmt: skip
    out["mismatch_direction"] = {"staff1_played_L": int((n["bad"] & (n["staff"] == 1)).sum()),
                                 "staff2_played_R": int((n["bad"] & (n["staff"] == 2)).sum())}  # fmt: skip
    runs = []
    for _, d in n.sort_values("perf_onset_sec", kind="stable").groupby(["record_time", "take"]):
        b = d["bad"].to_numpy().astype(int)
        e = np.diff(np.r_[0, b, 0])
        runs += list(np.flatnonzero(e == -1) - np.flatnonzero(e == 1))
    runs = np.array(runs)
    out["mismatch_runs"] = {"n_runs": len(runs), "median": float(np.median(runs)),
                            "max": int(runs.max()), "notes_in_runs_ge10": int(runs[runs >= 10].sum())}  # fmt: skip
    # 2 BL-19 recommendation 1 on real labels
    n["p13"] = n["cross_voice"] | n["capacity"]
    ec = ["record_time", "take", "score_pid", "onset"]
    ev = hp.event_mismatch(n, ec, rule="STAFF")
    flags = n.groupby(ec)[["p13", "at_risk"]].any().reset_index()
    ev = ev.merge(flags, on=ec)

    def pooled(e: pd.DataFrame) -> list[float]:
        pc = e.groupby("score_pid")["affected"].agg(["sum", "size"])
        return list(hp.cluster_ratio_ci(pc["sum"].to_numpy(), pc["size"].to_numpy(), 2000, SEED))

    out["events"] = {
        "all": {"n": len(ev), "affected": pooled(ev)},
        "drop_p1_p3": {"n": int((~ev["p13"]).sum()), "affected": pooled(ev[~ev["p13"]])},
        "drop_at_risk": {"n": int((~ev["at_risk"]).sum()), "affected": pooled(ev[~ev["at_risk"]])},
        "proxy_predicted_share_at_risk": float(ev["at_risk"].mean()),
    }
    (ART / "posthoc.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
