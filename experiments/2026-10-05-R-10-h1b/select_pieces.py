"""R-10: select the fresh confirmation pieces (run once on the Mac, project env; output committed).

A piece qualifies when all of these hold (pre-registered in ../README.md, "Data"):
  1. PianoCoRe v1.0 tier A, rows whose source is not ASAP (as R-07 prep), and at least
     MIN_PERFS performances on the piece's majority refined score (R-02 / R-07 rule).
  2. Unseen by SyMuPe pretraining as R-07 determined it: n_periscope_paired == 0 and not
     periscope_possible in R-07 split/pieces.csv.
  3. No work-mate (same R-07 work key) is paired or possibly paired in PERiScoPe.
  4. No possible catalogue alias (expression_split.alias_conflicts) of any PERiScoPe-paired
     piece or of any R-07 / R-06 evaluation piece.
  5. Not evaluated in R-07 or R-06 (roles P, V, A, R10u, R10s), not quarantined, not an R-02
     piece.
All qualifying pieces are used (no subsample). The seeded draw is the per-piece cap of 50
performances (R-07 prep rule, applied by job/prep_fresh.py) and the order of the list
(seeded permutation, SEED), which fixes nothing else.

    uv run python experiments/2026-10-05-R-10-h1b/select_pieces.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.data.pianocore import pianocore_index
from pianolens.models.expression_split import alias_conflicts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R07 = ROOT / "experiments" / "2026-09-28-R-07-symupe-finetune"
SPLIT = R07 / "split" / "pieces.csv"
SPLIT_SHA = "3341bfa58ff2d8bb89ca7d72468dc5077ea12fdc0e0e598338a5b4d322296b86"
SEED = 20261005
MIN_PERFS = 20          # R-07 (b) minimum renditions per piece
MIN_ORACLE = 36         # 16 held-out experts + at least 20 reference performers (R-07 audit B2)
EVAL_ROLES = {"P", "V", "A", "R10u", "R10s"}


def main() -> None:
    sha = hashlib.sha256(SPLIT.read_bytes()).hexdigest()
    assert sha == SPLIT_SHA, f"R-07 split changed: {sha}"
    sp = pd.read_csv(SPLIT)
    idx = pianocore_index(tier="a")
    idx = idx[idx["performance_dataset"] != "ASAP"]
    g = idx.groupby(["piece_id", "refined_score_midi_path"]).size().rename("n").reset_index()
    g = g.sort_values(["piece_id", "n", "refined_score_midi_path"], ascending=[True, False, True])
    maj = g.drop_duplicates("piece_id").set_index("piece_id")
    t = sp.set_index("piece_id").copy()
    t["n_majority"] = maj["n"].reindex(t.index).fillna(0).astype(int)
    t["majority_score"] = maj["refined_score_midi_path"].reindex(t.index)
    t["n_scores"] = idx.groupby("piece_id")["refined_score_midi_path"].nunique().reindex(
        t.index).fillna(0).astype(int)
    t = t.reset_index()

    paired = t[(t["n_periscope_paired"] > 0) | t["periscope_possible"]]
    paired_works = set(paired["work"])
    eval_pieces = t[t["role"].isin(EVAL_ROLES)]

    steps = {}
    c = t[t["n_majority"] >= MIN_PERFS]
    steps["1_tierA_majority_ge_min"] = len(c)
    c = c[(c["n_periscope_paired"] == 0) & ~c["periscope_possible"]]
    steps["2_unpaired_no_possible_alias"] = len(c)
    wm = c["work"].isin(paired_works)
    steps["3_dropped_paired_workmate"] = int(wm.sum())
    dropped_wm = c[wm]
    c = c[~wm]
    steps["3_after_workmate_rule"] = len(c)
    held = pd.concat([paired, eval_pieces]).drop_duplicates("piece_id")
    conf = alias_conflicts(held[["piece_id", "composer", "text"]],
                           c[["piece_id", "composer", "text"]])
    steps["4_dropped_alias"] = int(c["piece_id"].isin(set(conf["piece_id"])).sum())
    alias_drop = conf.groupby("piece_id")["held_piece_id"].agg(lambda s: ";".join(sorted(s)))
    c = c[~c["piece_id"].isin(set(conf["piece_id"]))]
    steps["4_after_alias_rule"] = len(c)
    bad = c["role"].isin(EVAL_ROLES | {"quarantine"}) | c["r02"]
    steps["5_dropped_eval_quarantine_r02"] = int(bad.sum())
    c = c[~bad]
    steps["5_final"] = len(c)

    rng = np.random.default_rng(SEED)
    c = c.sort_values("piece_id").reset_index(drop=True)
    c = c.iloc[rng.permutation(len(c))].reset_index(drop=True)
    c["order"] = np.arange(len(c))
    c["oracle_eligible_by_metadata"] = c["n_majority"] >= MIN_ORACLE
    cm = (idx[idx["piece_id"].isin(c["piece_id"])]
          .merge(c[["piece_id", "majority_score"]], on="piece_id")
          .query("refined_score_midi_path == majority_score")
          .groupby(["piece_id", "capture_model"]).size().unstack(fill_value=0))
    for col in cm.columns:
        c[f"n_{col.replace(' ', '_').replace('-', '_')}"] = c["piece_id"].map(cm[col]).fillna(
            0).astype(int)
    cols = ["order", "piece_id", "work", "composer", "text", "role", "n_tier_a", "n_majority",
            "n_scores", "majority_score", "oracle_eligible_by_metadata"] + [
        x for x in c.columns if x.startswith("n_") and x not in ("n_tier_a", "n_majority",
                                                                 "n_scores",
                                                                 "n_periscope_paired")]
    out = c[cols].rename(columns={"role": "r07_role"})
    HERE.joinpath("pieces").mkdir(exist_ok=True)
    path = HERE / "pieces" / "fresh_pieces.csv"
    out.to_csv(path, index=False)
    dropped_wm[["piece_id", "work", "n_majority"]].to_csv(
        HERE / "pieces" / "dropped_workmate.csv", index=False)
    pd.DataFrame({"piece_id": alias_drop.index, "aliases": alias_drop.values}).to_csv(
        HERE / "pieces" / "dropped_alias.csv", index=False)
    summ = {"seed": SEED, "min_perfs": MIN_PERFS, "min_oracle": MIN_ORACLE,
            "r07_split_sha256": sha, "steps": steps,
            "pieces": len(out), "works": int(out["work"].nunique()),
            "composers": int(out["composer"].nunique()),
            "oracle_eligible_by_metadata": int(out["oracle_eligible_by_metadata"].sum()),
            "r07_role": out["r07_role"].value_counts().to_dict(),
            "perfs_majority_total": int(out["n_majority"].sum()),
            "perfs_by_capture_model": {x: int(out[x].sum()) for x in out.columns
                                       if x.startswith("n_") and x not in
                                       ("n_tier_a", "n_majority", "n_scores")},
            "sha256_fresh_pieces_csv": hashlib.sha256(path.read_bytes()).hexdigest()}
    (HERE / "pieces" / "summary.json").write_text(json.dumps(summ, indent=1, default=int))
    print(json.dumps(summ, indent=1, default=int))


if __name__ == "__main__":
    main()
