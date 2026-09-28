"""R-07: fix the piece-disjoint split (run once on the Mac, project env; output committed).

Held-out TEST works (never trained on):
  P     PercePiano works (all 4, incl. D935 no. 3; all D960 movements through the work key)
  V     Vienna 4x22 works (Chopin Op. 10/3, Op. 38, Mozart K. 331, Schubert D783)
  A     works of the 23 (n)ASAP folders in Pianist Transformer's shipped test set (R-06 set A)
  R10u  R-10 evaluation pieces unseen by SyMuPe pretraining: R-02 pieces (>= 50 tier A
        performances on the majority score) with no score-paired performance in PERiScoPe v1.0
        and no possible alias among PERiScoPe's unmatched paired rows
  R10s  R-10 exposure contrast: 24 R-02 pieces that ARE paired in PERiScoPe (seeded draw)
VAL: 5% of the remaining works that have tier A performances (seeded draw); used for early
stopping and for developing the typicality scores, never for reporting.
QUARANTINE: works of pieces whose composer + catalogue numbers may alias a TEST or VAL piece under
another id (pianolens.models.expression_split.alias_conflicts); used for nothing.

    uv run python experiments/2026-09-28-R-07-symupe-finetune/make_split.py
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.data.asap import asap_index
from pianolens.data.pianocore import pianocore_index
from pianolens.data.piece_ids import load_piece_id_table
from pianolens.models.expression_split import alias_conflicts, assign_split, work_key

HERE = Path(__file__).resolve().parent
OUT = HERE / "split"
ROOT = HERE.parents[1]
PERISCOPE = HERE / "artifacts" / "periscope" / "v1.0" / "metadata_v1.0.csv"
R02_STATS = (ROOT / "experiments" / "2026-09-27-R-02-expression-dimensionality" / "artifacts"
             / "piece_stats.csv")
SEED = 20260928
VAL_FRAC = 0.05
N_R10_SEEN = 24
PT_TEST_FOLDERS = [  # identical to R-06 prepare.py A_TEST_FOLDERS
    "Bach/Fugue/bwv_854", "Bach/Fugue/bwv_864", "Bach/Italian_concerto", "Bach/Prelude/bwv_885",
    "Beethoven/Piano_Sonatas/1-1", "Beethoven/Piano_Sonatas/2-1",
    "Beethoven/Piano_Sonatas/32-1_no_repeat", "Beethoven/Piano_Sonatas/4-1",
    "Beethoven/Piano_Sonatas/5-1", "Beethoven/Piano_Sonatas/7-1", "Chopin/Etudes_op_25/4",
    "Chopin/Etudes_op_25/8", "Chopin/Sonata_2/2nd", "Chopin/Sonata_3/4th",
    "Haydn/Keyboard_Sonatas/48-2", "Haydn/Keyboard_Sonatas/49-1", "Liszt/Transcendental_Etudes/1",
    "Liszt/Transcendental_Etudes/10", "Mozart/Fantasie_475", "Mozart/Piano_Sonatas/12-2",
    "Mozart/Piano_Sonatas/8-1", "Ravel/Miroirs/3_Une_Barque", "Schumann/Kreisleriana/1",
]
# ASAP-only ids with no canonical form, mapped by hand to a piece of the same music so that both
# land in one work (PianoCoRe copies are then held out with the ASAP piece). Checked against
# piece_ids.parquet titles on 2026-09-28. ASAP numbers Haydn sonatas by Hob. XVI (the folder
# numbers 31-52 match PianoCoRe's Hob.XVI:<n> titles), so every asap Haydn id maps by rule.
MANUAL_ALIASES = {
    "asap:Bach/Italian_concerto": "bach_bwv971",
    "asap:Ravel/Miroirs_3_Une_Barque":
        "pianocore:Ravel,_Maurice/Miroirs,_M.43/3._Une_barque_sur_l'océan",
    "asap:Ravel/Miroirs_4_Alborada_del_gracioso":
        "pianocore:Ravel,_Maurice/Miroirs,_M.43/4._Alborada_del_gracioso",
}
HAYDN_ASAP = re.compile(r"^asap:Haydn/Keyboard_Sonatas_(\d+)-\d+$")


def piece_table() -> pd.DataFrame:
    ids = load_piece_id_table()
    ids["text"] = (ids["title"].fillna("").astype(str) + "/"
                   + ids["movement"].fillna("").astype(str))
    g = ids.groupby("piece_id")
    # catalogue text = every dataset's title + movement, plus the id itself (canonical ids carry
    # opus / number tokens, e.g. chopin_op10_no3)
    text = g["text"].agg(lambda s: " | ".join(sorted(set(s))))
    text = text + " | " + text.index.to_series().str.replace("_", " ")
    t = pd.DataFrame({
        "composer": g["composer"].first(),
        "text": text,
        "datasets": g["dataset"].agg(lambda s: ";".join(sorted(set(s)))),
    })
    md = pianocore_index(tier="c")
    t["pianocore_composition"] = md.groupby("piece_id")["composition"].first()
    t["n_tier_a"] = md[md["tier_a"]].groupby("piece_id").size()
    t["n_tier_a"] = t["n_tier_a"].fillna(0).astype(int)
    t = t.reset_index()
    t["work"] = [work_key(p, c if isinstance(c, str) else None)
                 for p, c in zip(t["piece_id"], t["pianocore_composition"], strict=True)]
    wk = dict(zip(t["piece_id"], t["work"], strict=True))
    for a, target in MANUAL_ALIASES.items():
        t.loc[t["piece_id"] == a, "work"] = wk.get(target, work_key(target))
    for i, p in t["piece_id"].items():
        m = HAYDN_ASAP.match(p)
        if m:
            t.at[i, "work"] = f"haydn_hobxvi{m.group(1)}"
    return t, md


def periscope_flags(t: pd.DataFrame, md: pd.DataFrame) -> pd.DataFrame:
    p = pd.read_csv(PERISCOPE)
    p["pid"] = p["performance"].str.split("/").str[-1].str.replace(".mid", "", regex=False)
    p["paired"] = p["score"].notna()
    j = p.merge(md[["performance_id", "piece_id"]], left_on="pid", right_on="performance_id",
                how="left")
    paired = j[j["paired"] & j["piece_id"].notna()].groupby("piece_id").size()
    t["n_periscope_paired"] = t["piece_id"].map(paired).fillna(0).astype(int)
    un = j[j["paired"] & j["piece_id"].isna()].copy()
    parts = un["performance"].str.split("/")
    un = pd.DataFrame({"piece_id": "periscope:" + parts.str[:-1].str.join("/"),
                       "composer": parts.str[0], "text": parts.str[1:-1].str.join("/")})
    un = un.drop_duplicates()
    c = alias_conflicts(un, t[["piece_id", "composer", "text"]])
    t["periscope_possible"] = t["piece_id"].isin(set(c["piece_id"]))
    return t, {"periscope_rows": int(len(p)), "periscope_paired": int(p["paired"].sum()),
               "paired_unmatched_to_pianocore": int(len(j[j["paired"] & j["piece_id"].isna()])),
               "unmatched_paired_titles": int(len(un))}


def main() -> None:
    t, md = piece_table()
    t, pinfo = periscope_flags(t, md)
    ps = pd.read_csv(R02_STATS)
    r02 = set(ps[(ps["block"] == "joint") & (ps["source"] == "real") & (ps["n"] == 50)]
              ["piece_id"])
    t["r02"] = t["piece_id"].isin(r02)
    by_piece = t.set_index("piece_id")

    role: dict[str, str] = {}  # work -> role (first assignment wins; order = priority)

    def force(pids, name):
        for p in pids:
            w = by_piece.at[p, "work"] if p in by_piece.index else work_key(p)
            role.setdefault(w, name)

    ids = load_piece_id_table()
    force(ids.loc[ids["dataset"] == "percepiano", "piece_id"], "P")
    force(ids.loc[ids["dataset"] == "vienna4x22", "piece_id"], "V")
    aidx = asap_index()
    force(aidx.loc[aidx["folder"].isin(PT_TEST_FOLDERS), "piece_id"].unique(), "A")
    unseen = t[t["r02"] & (t["n_periscope_paired"] == 0) & ~t["periscope_possible"]]
    force(unseen["piece_id"], "R10u")
    rng = np.random.default_rng(SEED)
    seen = t[t["r02"] & (t["n_periscope_paired"] > 0) & ~t["work"].isin(role)]
    pick = rng.choice(np.sort(seen["piece_id"].to_numpy()), size=N_R10_SEEN, replace=False)
    force(pick, "R10s")

    forced = {w: "test" for w in role}
    pool = set(t.loc[t["n_tier_a"] > 0, "work"])
    t["split"] = assign_split(t[["piece_id", "work"]], forced, VAL_FRAC, SEED,
                              val_pool=pool).to_numpy()
    t["role"] = [role.get(w, s) for w, s in zip(t["work"], t["split"], strict=True)]

    # quarantine: works of train pieces that may alias a held-out piece
    held = t[t["split"] != "train"]
    cand = t[t["split"] == "train"]
    conf = alias_conflicts(held[["piece_id", "composer", "text"]],
                           cand[["piece_id", "composer", "text"]])
    qworks = set(t.loc[t["piece_id"].isin(conf["piece_id"]), "work"])
    reason = conf.groupby("piece_id")["held_piece_id"].agg(lambda s: ";".join(sorted(s)))
    q = t["work"].isin(qworks) & (t["split"] == "train")
    t.loc[q, "split"] = "quarantine"
    t.loc[q, "role"] = "quarantine"
    t["quarantine_reason"] = t["piece_id"].map(reason).fillna("")

    cols = ["piece_id", "work", "split", "role", "datasets", "composer", "text", "n_tier_a",
            "n_periscope_paired", "periscope_possible", "r02", "quarantine_reason"]
    t = t[cols].sort_values(["split", "role", "work", "piece_id"]).reset_index(drop=True)
    OUT.mkdir(exist_ok=True)
    path = OUT / "pieces.csv"
    t.to_csv(path, index=False)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    summ = {
        "seed": SEED, "val_frac": VAL_FRAC, "n_r10_seen": N_R10_SEEN, "sha256_pieces_csv": sha,
        **pinfo,
        "pieces_by_split": t["split"].value_counts().to_dict(),
        "pieces_by_role": t["role"].value_counts().to_dict(),
        "works_by_role": t.groupby("role")["work"].nunique().to_dict(),
        "tier_a_perfs_by_split": t.groupby("split")["n_tier_a"].sum().to_dict(),
        "tier_a_perfs_by_role": t.groupby("role")["n_tier_a"].sum().to_dict(),
        "r02_pieces_by_role": t[t["r02"]].groupby("role").size().to_dict(),
        "test_pieces_periscope_paired": int(((t["split"] == "test")
                                             & (t["n_periscope_paired"] > 0)).sum()),
    }
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=int))
    print(json.dumps(summ, indent=1, default=int))


if __name__ == "__main__":
    main()
