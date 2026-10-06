"""R-10 piece lists (metadata only; no curves, no model).

  decision    R10u pieces that R-07's split calls unseen (R-02 piece, role R10u, no score-paired
              PERiScoPe performance, no possible alias) with at least N_REF + K tier A
              performances on the majority refined score.
  calibration R-02 pieces of the R-07 train / val roles (never R-10 evaluation pieces) with at
              least N_REF + 48 such performances; seeded draw of 40. Used only for the
              reachability simulation (experts only).
  dryrun      the 2 calibration pieces with the fewest score notes (pipeline check only).

    python select_pieces.py --pianocore C:/Users/Vuduc/r07/data/pianocore --k 32
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SPLIT = HERE.parent / "2026-09-28-R-07-symupe-finetune" / "split" / "pieces.csv"
SEED = 20261005
N_REF = 50
N_CALIB = 40
K_MAX_SIM = 48


def piece_table(pianocore: str) -> pd.DataFrame:
    from pianolens.data.pianocore import pianocore_index

    idx = pianocore_index(pianocore, tier="a")
    nc = pd.read_csv(Path(pianocore) / "metadata.csv", usecols=["id", "refined_score_note_count"])
    idx = idx.merge(nc, on="id", how="left")
    sp = pd.read_csv(SPLIT).set_index("piece_id")
    idx = idx[idx["piece_id"].isin(sp.index)]
    rows = []
    for pid, g in idx.groupby("piece_id"):
        vc = g["refined_score_midi_path"].value_counts()
        maj = g[g["refined_score_midi_path"] == vc.index[0]]
        rows.append({"piece_id": pid, "n_tier_a": len(g), "n_maj": int(vc.iloc[0]),
                     "score_notes": int(maj["refined_score_note_count"].iloc[0])})
    t = pd.DataFrame(rows).set_index("piece_id")
    for c in ("work", "role", "r02", "n_periscope_paired", "periscope_possible"):
        t[c] = sp[c].reindex(t.index)
    return t.reset_index()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pianocore", required=True)
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--out", default=str(HERE / "pieces.csv"))
    a = ap.parse_args(argv)
    t = piece_table(a.pianocore)
    unseen = (t["role"] == "R10u") & t["r02"].astype(bool) & (t["n_periscope_paired"] == 0) & \
        ~t["periscope_possible"].astype(bool)
    dec = t[unseen & (t["n_maj"] >= N_REF + a.k)].assign(set="decision")
    cand = t[t["role"].isin(["train", "val"]) & t["r02"].astype(bool)
             & (t["n_maj"] >= N_REF + K_MAX_SIM)].sort_values("piece_id")
    rng = np.random.default_rng(SEED)
    pick = np.sort(rng.choice(len(cand), N_CALIB, replace=False))
    cal = cand.iloc[pick].assign(set="calibration")
    dry = cal.nsmallest(2, "score_notes").assign(set="dryrun")
    out = pd.concat([dec, cal, dry], ignore_index=True)
    out.to_csv(a.out, index=False)
    info = {"k": a.k, "unseen_r10u": int(unseen.sum()), "decision": len(dec),
            "decision_works": int(dec["work"].nunique()),
            "decision_score_notes": int(dec["score_notes"].sum()),
            "calibration": len(cal), "calibration_candidates": len(cand),
            "dryrun": dry["piece_id"].tolist()}
    Path(a.out).with_suffix(".json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
