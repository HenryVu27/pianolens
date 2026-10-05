"""R-11 analysis, implementing the pre-registration in README.md (hash in artifacts/).

    uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py gate
    uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py a
    uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py b
    uv run python experiments/2026-10-05-R-11-teacher-annotations/run.py c

Outputs go to artifacts/ (gitignored). Annotation text never leaves data/interim (BL-29); the
artifacts hold ids, codes and numbers only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ART = HERE / "artifacts"
INTERIM = ROOT / "data" / "interim" / "tonebase_annotations"
SEED = 20261005
CATS10 = ["voicing", "dynamics", "timing", "articulation", "pedal", "evenness", "character",
          "fingering_physical", "practice", "analysis"]
MERGE8 = {"practice": "fingering_physical", "analysis": "character"}
OBS_ORD = {"no": 0, "partly": 1, "yes": 2}


# ----------------------------------------------------------------------------- helpers
def load_rows(enc: str, tag: str) -> pd.DataFrame:
    return pd.read_csv(INTERIM / f"encoder_{enc}" / f"{tag}_annotations.csv", dtype=str).fillna("")


def expand_bars(ed: str) -> set[str]:
    out: set[str] = set()
    for part in [p.strip() for p in ed.split(";") if p.strip()]:
        if re.fullmatch(r"\d+-\d+", part):
            a, b = map(int, part.split("-"))
            out |= {str(i) for i in range(a, b + 1)}
        else:
            out.add(part)
    return out


def tokens(text: str) -> set[str]:
    t = text.lower().replace("’", "'").replace("‘", "'")
    return set(re.findall(r"[a-z0-9']+", t))


def jacc(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def is_notation(mark: str, kind: str) -> bool:
    return kind in mark


def cohen_kappa(a: list, b: list, labels: list) -> float:
    idx = {c: i for i, c in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)))
    for x, y in zip(a, b, strict=True):
        m[idx[x], idx[y]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = (m.sum(1) @ m.sum(0)) / n**2
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def weighted_kappa(a: list[int], b: list[int], k: int) -> float:
    m = np.zeros((k, k))
    for x, y in zip(a, b, strict=True):
        m[x, y] += 1
    n = m.sum()
    w = np.abs(np.subtract.outer(np.arange(k), np.arange(k))) / (k - 1)
    exp = np.outer(m.sum(1), m.sum(0)) / n
    return float(1 - (w * m).sum() / (w * exp).sum())


# ----------------------------------------------------------------------------- gate
def match_rows(A: pd.DataFrame, B: pd.DataFrame, require_bar_overlap: bool = True
               ) -> list[tuple[int, int, float, str]]:
    """Pre-registered matching: same page; anchor bars overlap (or both global); and text
    token Jaccard >= 0.5, or target Jaccard >= 0.5, or both digit (or both label) rows.
    One-to-one greedy by highest Jaccard."""
    cands = []
    for i, ra in A.iterrows():
        for j, rb in B.iterrows():
            if ra["pdf_page"] != rb["pdf_page"]:
                continue
            ba, bb = expand_bars(ra["ed_bars"]), expand_bars(rb["ed_bars"])
            if require_bar_overlap and not ((not ba and not bb) or (ba & bb)):
                continue
            tj = jacc(tokens(ra["text"]), tokens(rb["text"]))
            ta = {t for t in ra["targets"].split(";") if t}
            tb = {t for t in rb["targets"].split(";") if t}
            gj = jacc(ta, tb) if ta and tb else 0.0
            notation = ""
            for kind in ("digits", "labels"):
                if is_notation(ra["mark_type"], kind) and is_notation(rb["mark_type"], kind):
                    notation = kind
            score, why = max((tj, "text"), (gj, "targets"))
            if score >= 0.5:
                cands.append((score, i, j, why))
            elif notation:
                cands.append((max(jacc(ba, bb), 0.01), i, j, notation))
    cands.sort(key=lambda c: -c[0])
    used_a, used_b, out = set(), set(), []
    for score, i, j, why in cands:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        out.append((i, j, score, why))
    return out


def presence(df: pd.DataFrame, n_meas: int) -> np.ndarray:
    p = np.zeros((n_meas, len(CATS10)), bool)
    for _, r in df.iterrows():
        for m in [int(x) for x in r["pc_measures"].split(";") if x.strip()]:
            if 1 <= m <= n_meas:
                p[m - 1, CATS10.index(r["category"])] = True
    return p


def run_gate(tag: str = "NOC") -> dict:
    A, B = load_rows("A", tag), load_rows("B", tag)
    pairs = match_rows(A, B)
    ia = [p[0] for p in pairs]
    ib = [p[1] for p in pairs]
    MA, MB = A.loc[ia].reset_index(drop=True), B.loc[ib].reset_index(drop=True)
    res: dict = {"n_A": len(A), "n_B": len(B), "n_matched": len(pairs),
                 "share_A_matched": len(pairs) / len(A), "share_B_matched": len(pairs) / len(B),
                 "match_basis": pd.Series([p[3] for p in pairs]).value_counts().to_dict()}
    res["kappa_category10"] = cohen_kappa(list(MA["category"]), list(MB["category"]), CATS10)
    c8a = [MERGE8.get(c, c) for c in MA["category"]]
    c8b = [MERGE8.get(c, c) for c in MB["category"]]
    res["kappa_category8"] = cohen_kappa(c8a, c8b, [c for c in CATS10 if c not in MERGE8])
    res["agree_category10"] = float(np.mean(MA["category"] == MB["category"]))
    res["kappa_observable_linear"] = weighted_kappa([OBS_ORD[x] for x in MA["observable"]],
                                                    [OBS_ORD[x] for x in MB["observable"]], 3)
    res["agree_observable"] = float(np.mean(MA["observable"] == MB["observable"]))
    both_obs = (MA["observable"] != "no") & (MB["observable"] != "no")
    res["n_both_observable"] = int(both_obs.sum())
    res["agree_direction_both_observable"] = float(
        np.mean(MA.loc[both_obs, "direction"] == MB.loc[both_obs, "direction"]))
    tj = []
    for (_, ra), (_, rb) in zip(MA.iterrows(), MB.iterrows(), strict=True):
        ta = {t for t in ra["targets"].split(";") if t}
        tb = {t for t in rb["targets"].split(";") if t}
        if ta and tb:
            tj.append(jacc(ta, tb))
    res["target_jaccard_mean_both_nonempty"] = float(np.mean(tj)) if tj else float("nan")
    res["n_both_targets"] = len(tj)
    res["agree_ed_bars_exact"] = float(np.mean([expand_bars(a) == expand_bars(b) for a, b in
                                                zip(MA["ed_bars"], MB["ed_bars"], strict=True)]))
    res["agree_pc_measures_exact"] = float(np.mean(
        [set(a.split(";")) == set(b.split(";")) for a, b in
         zip(MA["pc_measures"], MB["pc_measures"], strict=True)]))
    # bar map
    ba = pd.read_csv(INTERIM / "encoder_A" / f"{tag}_barmap.csv", dtype=str).fillna("")
    bb = pd.read_csv(INTERIM / "encoder_B" / f"{tag}_barmap.csv", dtype=str).fillna("")
    for bm in (ba, bb):  # an empty pass means a bar played once: same as pass 1
        bm["pass"] = bm["pass"].replace("", "1")
    key = ["ed_bar", "pass"]
    mm = ba.merge(bb, on=key, how="outer", suffixes=("_a", "_b"), indicator=True)
    same = [(set(str(x).split(";")) == set(str(y).split(";"))) for x, y in
            zip(mm["pc_measures_a"], mm["pc_measures_b"], strict=True)]
    res["barmap_n_bars"] = len(mm)
    res["barmap_agree_pc"] = float(np.mean(same))
    res["barmap_agree_pc_and_q"] = float(np.mean(
        [s and qa == qb and ta == tb for s, qa, qb, ta, tb in
         zip(same, mm["q_from_a"], mm["q_from_b"], mm["q_to_a"], mm["q_to_b"], strict=True)]))
    # bar x category presence kappa
    n_meas = 38
    pa, pb = presence(A, n_meas).ravel(), presence(B, n_meas).ravel()
    res["kappa_bar_x_category"] = cohen_kappa(list(pa), list(pb), [False, True])
    # bootstrap CIs (descriptive, not pre-registered) over matched rows
    rng = np.random.default_rng(SEED)
    kc, ko = [], []
    n = len(MA)
    for _ in range(2000):
        s = rng.integers(0, n, n)
        kc.append(cohen_kappa(list(MA["category"].iloc[s]), list(MB["category"].iloc[s]), CATS10))
        ko.append(weighted_kappa([OBS_ORD[x] for x in MA["observable"].iloc[s]],
                                 [OBS_ORD[x] for x in MB["observable"].iloc[s]], 3))
    res["kappa_category10_ci"] = [float(np.nanpercentile(kc, 2.5)),
                                  float(np.nanpercentile(kc, 97.5))]
    res["kappa_observable_ci"] = [float(np.nanpercentile(ko, 2.5)),
                                  float(np.nanpercentile(ko, 97.5))]
    gate = {"category_kappa>=0.60": res["kappa_category10"] >= 0.60,
            "observable_wkappa>=0.60": res["kappa_observable_linear"] >= 0.60,
            "A_matched>=0.80": res["share_A_matched"] >= 0.80,
            "B_matched>=0.80": res["share_B_matched"] >= 0.80,
            "barmap>=0.95": res["barmap_agree_pc"] >= 0.95}
    res["gate"] = gate
    res["gate_pass"] = bool(all(gate.values()))
    # sensitivity (not the gate): matching without the bar-overlap requirement
    pairs2 = match_rows(A, B, require_bar_overlap=False)
    res["sens_no_bar_overlap"] = {"n_matched": len(pairs2),
                                  "share_A": len(pairs2) / len(A), "share_B": len(pairs2) / len(B)}
    # ids only (no text) for the record
    res["pairs"] = [[A.loc[i, "ann_id"], B.loc[j, "ann_id"], round(sc, 3), w]
                    for i, j, sc, w in pairs]
    res["unmatched_A"] = [A.loc[i, "ann_id"] for i in A.index if i not in set(ia)]
    res["unmatched_B"] = [B.loc[j, "ann_id"] for j in B.index if j not in set(ib)]
    disagree = []
    for (_, ra), (_, rb) in zip(MA.iterrows(), MB.iterrows(), strict=True):
        diffs = [f for f in ("category", "observable", "direction", "ed_bars")
                 if (expand_bars(ra[f]) != expand_bars(rb[f]) if f == "ed_bars"
                     else ra[f] != rb[f])]
        if diffs:
            disagree.append([ra["ann_id"], rb["ann_id"]] + [f"{f}:{ra[f]}|{rb[f]}" for f in diffs])
    res["disagreements"] = disagree
    return res


# ----------------------------------------------------------------------------- (a)
def t_interval(x: np.ndarray) -> list[float]:
    from scipy import stats
    x = np.asarray(x, float)
    if len(x) < 2:
        return [float("nan")] * 2
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return [float(x.mean() - h), float(x.mean() + h)]


def strat_boot(df: pd.DataFrame, col: str, b: int = 10_000) -> list[float]:
    rng = np.random.default_rng(SEED)
    groups = [g[col].to_numpy(float) for _, g in df.groupby("piece")]
    means = np.empty(b)
    for i in range(b):
        means[i] = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups]).mean()
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def summarise_r(df: pd.DataFrame) -> dict:
    ok = df[df["status"] == "ok"]
    out = {"n_rows": int(len(ok)), "mean_r": float(ok["r"].mean()) if len(ok) else float("nan")}
    if len(ok) == 0:
        return out
    out["ci_boot"] = strat_boot(ok, "r")
    pm = ok.groupby("piece")["r"].mean()
    out["piece_means"] = pm.to_dict()
    out["piece_n"] = ok.groupby("piece").size().to_dict()
    out["t_interval_piece_means"] = t_interval(pm.to_numpy())
    out["loo_piece"] = {p: float(ok[ok["piece"] != p]["r"].mean()) for p in pm.index}
    out["mean_f_marked"] = float(ok["f_marked"].mean())
    out["share_f_marked_gt_half"] = float((ok["f_marked"] > 0.5).mean())
    out["mean_f_null_median"] = float(ok["f_null_median"].mean())
    return out


def decide_a(s: dict) -> str:
    if not s.get("n_rows"):
        return "no rows"
    lo, hi = s["ci_boot"]
    if s["mean_r"] >= 0.65 and lo > 0.50 and sum(v > 0.5 for v in s["piece_means"].values()) >= 2:
        return "supported"
    if hi < 0.65:
        return "not supported (falsified for this pilot)"
    return "inconclusive"


def run_a() -> dict:
    import part_a as pa

    ops_df = pd.read_csv(INTERIM / "encoder_A" / "operationalisation_A.csv",
                         dtype=str).fillna("")
    res_rows, extra = [], {}
    pieces = {}
    for tag in ("NOC", "WAL", "ETU"):
        P = pa.load_piece(tag)
        pieces[tag] = P
        A = load_rows("A", tag)
        U = pa.unannotated(A)
        extra[tag] = {"staff_log": P.staff_log, "n_unannotated_excluded_measures": len(U)}
        for row in pa.build_rows(P, A, ops_df):
            r = pa.evaluate_row(P, row, U)
            res_rows.append(r)
            # provenance split for etude velocity rows (Disklavier only)
            if tag == "ETU" and row.quantity == "velocity" and row.fn is not None:
                sub = P.perf["provenance"].to_numpy() != "transcribed"
                r2 = pa.evaluate_row(P, row, U, subset=sub)
                r2["ann_id"] = row.ann_id + "@sensor"
                r2["set"] = "provenance_split"
                res_rows.append(r2)
            print(r["ann_id"], r.get("status"), {k: round(v, 3) for k, v in r.items()
                  if k in ("f_marked", "r", "n_null", "n_perf", "median_E")}, flush=True)
    R = pd.DataFrame(res_rows)
    R.to_csv(ART / "a_rows.csv", index=False)
    prim = R[R["set"] == "primary"]
    summ = {"primary": summarise_r(prim)}
    summ["decision"] = decide_a(summ["primary"])
    summ["primary_status_counts"] = prim["status"].value_counts().to_dict()
    for col in ("category", "quantity", "restates_print"):
        ok = prim[prim["status"] == "ok"]
        agg = ok.groupby(col).agg(n=("r", "size"), mean_r=("r", "mean"),
                                  mean_f=("f_marked", "mean"))
        summ[f"by_{col}"] = agg.round(3).to_dict("index")
    sec = R[R["set"] == "secondary"]
    summ["secondary"] = summarise_r(sec)
    summ["provenance_split"] = R[R["set"] == "provenance_split"][
        ["ann_id", "status", "f_marked", "n_perf", "r", "n_null"]].to_dict("records")
    summ["extra"] = extra
    # sensitivity: encoder B's nocturne rows under the same generic rules
    summ["sensitivity_B"] = run_a_with_b(pieces["NOC"], ops_df)
    (ART / "a_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    return summ


def run_a_with_b(P, O_A: pd.DataFrame) -> dict:
    """README Method (a) 8: B's nocturne rows, generic rules; A's row rule where targets match."""
    import part_a as pa

    A, B = load_rows("A", "NOC"), load_rows("B", "NOC")
    pairs = {B.loc[j, "ann_id"]: A.loc[i, "ann_id"] for i, j, _, _ in match_rows(A, B)}
    oa = O_A.set_index("ann_id")
    recs = []
    for _, b in B[B["observable"].isin(["yes", "partly"])].iterrows():
        a_id = pairs.get(b["ann_id"])
        rec = {"ann_id": b["ann_id"], "set": "", "reason": ""}
        a_row = A[A["ann_id"] == a_id].iloc[0] if a_id else None
        same_targets = a_row is not None and a_row["targets"] == b["targets"] and \
            a_row["ed_bars"] == b["ed_bars"]
        if same_targets and a_id in oa.index:
            # set from B's own fields (generic classification); A's frozen exclusion for a
            # non-computable anchor carries over because it is a property of the targets
            a_excl = oa.loc[a_id, "set"] == "excluded" and "computable" in oa.loc[a_id, "reason"]
            rec["set"] = "excluded" if a_excl else _classify_generic(b)
            rec["reason"] = "A rule (same targets)"
            rec["use_id"] = a_id
        else:
            rec["set"], rec["reason"] = _classify_generic(b), "generic"
            rec["use_id"] = b["ann_id"]
        recs.append(rec)
    O_B = pd.DataFrame(recs)
    # rows: A-rule rows re-use A's row object (with B's ann id); generic rows built from B
    Bx = B.copy()
    rows = []
    a_rule = O_B[O_B["reason"].str.startswith("A rule")]
    gen = O_B[O_B["reason"] == "generic"]
    OA = a_rule.rename(columns={"ann_id": "b_id", "use_id": "ann_id"})[["ann_id", "set"]]
    a_to_b = dict(zip(a_rule["use_id"], a_rule["ann_id"], strict=True))
    for r in pa.build_rows(P, A[A["ann_id"].isin(a_rule["use_id"])], OA):
        r.ann_id = a_to_b[r.ann_id]
        rows.append(r)
    OG = gen.rename(columns={"use_id": "x"})[["ann_id", "set"]]
    rows += pa.build_rows(P, Bx[Bx["ann_id"].isin(gen["ann_id"])], OG)
    U = pa.unannotated(B)
    out = [pa.evaluate_row(P, r, U) for r in rows]
    D = pd.DataFrame(out)
    D.to_csv(ART / "a_rows_encoderB_NOC.csv", index=False)
    prim = D[D["set"] == "primary"]
    return {"mapping": O_B.to_dict("records"), "primary": summarise_r(prim.assign(piece="NOC")),
            "rows": D[["ann_id", "set", "status", "f_marked", "r", "n_null"]].to_dict("records")}


def _classify_generic(r: pd.Series) -> str:
    """The frozen classification rules (build_operationalisation_A.classify), no overrides."""
    if r["scope"] == "global" or not r["ed_bars"]:
        return "excluded"
    if r["direction"] in ("NONE", "DIFFERENT_FROM_REF", "LOW_LEVEL", "FOLLOW_HAIRPINS",
                          "TEMPO_FOLLOWS_HAIRPINS") or r["quantity"].startswith("pedal"):
        return "excluded"
    if (r["observable"] != "yes" or r["modality"] == "option"
            or r["reference"].startswith("earlier_statement")
            or r["direction"] in ("PERIODIC_GROUPING", "NONISOCHRONOUS")
            or r["quantity"] == "duration"):
        return "secondary"
    return "primary"


# ----------------------------------------------------------------------------- (b)
def wilson(k: int, n: int) -> list[float]:
    if n == 0:
        return [float("nan")] * 2
    z, ph = 1.96, k / n
    c = (ph + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(c - h), float(c + h)]


def b_stat(df: pd.DataFrame, a: str, b: str, B: int = 10_000) -> dict:
    """Mean over rows of (rate a - rate b); bootstrap rows within pieces, performances
    within rows."""
    d = df.dropna(subset=[a])
    rows = {k: g for k, g in d.groupby("ann_id")}
    if not rows:
        return {"n_rows": 0}
    per = {k: float(g[a].mean() - g[b].mean()) for k, g in rows.items()}
    rng = np.random.default_rng(SEED)
    pieces = {p: [k for k in rows if rows[k]["piece"].iloc[0] == p] for p in d["piece"].unique()}
    arr = {k: (g[a].to_numpy(float), g[b].to_numpy(float)) for k, g in rows.items()}
    boots = np.empty(B)
    for i in range(B):
        vals = []
        for ks in pieces.values():
            for k in rng.choice(ks, len(ks)):
                x, y = arr[k]
                j = rng.integers(0, len(x), len(x))
                vals.append(x[j].mean() - y[j].mean())
        boots[i] = np.mean(vals)
    return {"n_rows": len(per), "mean": float(np.mean(list(per.values()))),
            "ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "per_row": per}


def run_b_main() -> dict:
    import part_b as pb

    a_rows = pd.read_csv(ART / "a_rows.csv")
    df, orig, meta = pb.run_b(a_rows=a_rows)
    df.to_csv(ART / "b_rows.csv", index=False)
    orig.to_csv(ART / "b_original_bars.csv", index=False)
    voicing = {"WAL-A-023", "WAL-A-055", "ETU-A-040", "NOC-A-018"}
    for c in ("hit", "fa", "null_hit", "null_fa"):
        if c in df:
            df[c] = df[c].astype(float)
    prim = df[~df["ann_id"].isin(voicing)]
    voi = df[df["ann_id"].isin(voicing)]
    res = {"meta": meta,
           "primary_hit_minus_fa": b_stat(prim, "hit", "fa"),
           "primary_hit_minus_nullhit": b_stat(prim.dropna(subset=["null_hit"]), "hit",
                                               "null_hit"),
           "voicing_hit_minus_fa": b_stat(voi, "hit", "fa")}
    k, n = int(prim["fa"].sum()), int(prim["fa"].notna().sum())
    res["fa_pooled"] = {"k": k, "n": n, "rate": k / n if n else float("nan"),
                        "wilson": wilson(k, n)}
    ob = orig.groupby("channel")[["n_flag", "n_bars"]].sum()
    res["original_all_bars_flag_rate"] = (ob["n_flag"] / ob["n_bars"]).to_dict()
    res["rates_by_row"] = df.groupby("ann_id")[["hit", "fa", "null_hit", "null_fa"]].mean() \
        .round(3).to_dict("index")
    res["n_by_row"] = df.groupby("ann_id")["hit"].count().to_dict()
    s = res["primary_hit_minus_fa"]
    if not s.get("n_rows"):
        res["decision_notice"] = "no rows"
    elif s["mean"] >= 0.25 and s["ci"][0] > 0.10:
        res["decision_notice"] = "the report notices"
    elif s["ci"][1] < 0.25:
        res["decision_notice"] = "does not notice"
    else:
        res["decision_notice"] = "inconclusive"
    res["decision_quiet"] = "stays quiet" if res["fa_pooled"]["rate"] <= 0.10 else "not quiet"
    (ART / "b_summary.json").write_text(json.dumps(res, indent=1, default=float))
    return res


# ----------------------------------------------------------------------------- (c)
def obs_table(d: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for k, g in list(d.groupby(by)) + [("All", d)]:
        n = len(g)
        rec = {by: k, "n": n}
        for o in ("yes", "partly", "no"):
            c = int((g["observable"] == o).sum())
            lo, hi = wilson(c, n)
            rec[o] = c
            rec[f"{o}_share"] = round(c / n, 3) if n else np.nan
            rec[f"{o}_ci"] = f"[{lo:.3f}, {hi:.3f}]"
        rows.append(rec)
    return pd.DataFrame(rows)


def run_c() -> dict:
    A = pd.concat([load_rows("A", t) for t in ("NOC", "WAL", "ETU")], ignore_index=True)
    notation = A["mark_type"].str.contains("digits|labels")
    views = {"all": A, "no_digit_label_rows": A[~notation],
             "ticket8": A.assign(category=A["category"].replace(MERGE8))}
    out = {}
    for name, d in views.items():
        out[name] = {"by_category": obs_table(d, "category").to_dict("records"),
                     "by_piece": obs_table(d, "piece_tag").to_dict("records")}
    out["by_modality"] = obs_table(A, "modality").to_dict("records")
    B = load_rows("B", "NOC")
    out["NOC_A_vs_B"] = {"A": obs_table(A[A["piece_tag"] == "NOC"], "piece_tag")
                         .to_dict("records")[-1],
                         "B": obs_table(B, "piece_tag").to_dict("records")[-1]}
    g = json.loads((ART / "gate.json").read_text())
    out["NOC_observable_weighted_kappa"] = g["kappa_observable_linear"]
    (ART / "c_summary.json").write_text(json.dumps(out, indent=1, default=float))
    for name in views:
        print(name)
        print(pd.DataFrame(out[name]["by_category"]).to_string(index=False))
    print(pd.DataFrame(out["by_modality"]).to_string(index=False))
    print(out["NOC_A_vs_B"])
    return out


# ----------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["gate", "a", "b", "c"])
    a = ap.parse_args()
    ART.mkdir(exist_ok=True)
    if a.part == "gate":
        res = run_gate()
        (ART / "gate.json").write_text(json.dumps(res, indent=1, default=float))
        for k, v in res.items():
            if k not in ("pairs", "disagreements"):
                print(k, v)
        print("disagreements:")
        for d in res["disagreements"]:
            print(" ", d)
    elif a.part == "a":
        import sys
        sys.path.insert(0, str(HERE))
        s = run_a()
        print(json.dumps({k: v for k, v in s.items() if k not in ("sensitivity_B", "extra")},
                         indent=1, default=float))
        print("sensitivity_B primary", s["sensitivity_B"]["primary"])
    elif a.part == "b":
        import sys
        sys.path.insert(0, str(HERE))
        r = run_b_main()
        print(json.dumps({k: v for k, v in r.items() if k != "rates_by_row"}, indent=1,
                         default=float))
        print(json.dumps(r["rates_by_row"], indent=1))
    else:
        run_c()


if __name__ == "__main__":
    main()
