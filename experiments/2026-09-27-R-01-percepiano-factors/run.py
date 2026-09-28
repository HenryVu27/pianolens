"""R-01 / H2: factor structure of PercePiano's 19 rating dimensions.

Pre-registration: README.md in this folder. Parses the label CSV directly because the D-02
loader did not exist when this ran.

    uv run python experiments/2026-09-27-R-01-percepiano-factors/run.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import time
import warnings
from pathlib import Path

import factor_analyzer.factor_analyzer as _fam  # noqa: E402
import numpy as np
import pandas as pd
from factor_analyzer import FactorAnalyzer
from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity, calculate_kmo
from scipy.optimize import linear_sum_assignment

from pianolens.eval import bootstrap_indices

# factor-analyzer 0.5.1 passes `force_all_finite` to sklearn's check_array; scikit-learn 1.9
# renamed it `ensure_all_finite`. Translate the keyword (see ml-researcher memory).
_orig_check_array = _fam.check_array


def _check_array_compat(*args, force_all_finite=None, **kwargs):
    if force_all_finite is not None:
        kwargs["ensure_all_finite"] = force_all_finite
    return _orig_check_array(*args, **kwargs)


_fam.check_array = _check_array_compat

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/percepiano"
CSV = RAW / "labels/total_2rounds.csv"
OUT = Path(__file__).resolve().parent / "artifacts"
SEED = 0

ITEMS = [
    "Timing_Stable_Unstable",
    "Articulation_Short_Long",
    "Articulation_Soft_Hard",
    "Pedal_Sparse_Saturated",
    "Pedal_Clean_Blurred",
    "Timbre_Even_Colorful",
    "Timbre_Shallow_Rich",
    "Timbre_Bright_Dark",
    "Timbre_Soft_Loud",
    "Dynamic_Mellow_Raw",
    "Dynamic_Range_Little_Large",
    "Music_Fast_Slow",
    "Music_Flat_Spacious",
    "Music_Disproportioned_Balanced",
    "Music_Pure_Dramatic",
    "Emotion_Pleasant_Dark",
    "Emotion_LowEnergy_HighEnergy",
    "Emotion_Honest_Imaginative",
    "Interpretation_Unconvincing_Convincing",
]
P = len(ITEMS)


# ----------------------------------------------------------------------------- data


def _normalise_name(fn: str) -> str:
    """Same file-name fixes as the authors' labels/map_midi_to_label.py."""
    name = ".".join(fn.split(".")[:-1])
    if "_score" in name:
        name = name.replace("_score", "_Score")
    seg = int(name.split("_")[-1])
    if ("Beethoven_WoO80" in name and "Score" in name and seg in range(5, 17)) or (
        "Schubert_" in name and "_no.3_4bars" in name and "_Score_" in name and seg == 1
    ):
        name = name.replace("_Score_", "_Score2_")
    return name


def load_long() -> pd.DataFrame:
    raw = pd.read_csv(CSV)
    qcols = list(raw.columns[3:22])
    assert len(qcols) == P and qcols[0] == "Question_1_1_1" and qcols[-1] == "Question_9_1_1"
    df = raw[["user", "dataID", "filename"] + qcols].copy()
    df.columns = ["rater", "dataID", "filename"] + ITEMS
    df["segment"] = df.filename.map(_normalise_name)
    vals = df[ITEMS].astype(float)
    bad = (vals > 7.1).any(axis=1)
    df = df[~bad].copy()
    df[ITEMS] = df[ITEMS].astype(float).replace(0.0, np.nan)
    parts = df.segment.str.extract(r"^(?P<piece>.+)_(?P<bars>\d+)bars_(?P<player>[^_]+)_\d+$")
    assert parts.notna().all().all()
    df["piece"] = parts.piece
    df["performer"] = parts.player.replace({"Score2": "Score"})
    df.attrs["n_dropped_gt7"] = int(bad.sum())
    return df


def segment_means(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("segment")
    m = g[ITEMS].mean()  # NaN-skipping mean = authors' "remove 0 then average"
    m = m.dropna()
    meta = g[["piece", "performer"]].first().loc[m.index]
    return pd.concat([meta, m], axis=1)


def one_row_per_rater_segment(df: pd.DataFrame) -> pd.DataFrame:
    d = df.drop_duplicates(["rater", "dataID", "segment"])
    agg = d.groupby(["rater", "segment"])[ITEMS].mean().reset_index()
    meta = d.groupby("segment")[["piece", "performer"]].first()
    return agg.join(meta, on="segment")


# ----------------------------------------------------------------------------- stats


def corr(x: np.ndarray) -> np.ndarray:
    return np.corrcoef(x, rowvar=False)


def smc_reduced(r: np.ndarray) -> np.ndarray:
    rr = r.copy()
    np.fill_diagonal(rr, 1 - 1 / np.diag(np.linalg.pinv(r)))
    return rr


def eig_desc(r: np.ndarray) -> np.ndarray:
    return np.sort(np.linalg.eigvalsh(r))[::-1]


def parallel_analysis(x: np.ndarray, n_iter: int, seed: int, q: float = 0.95) -> dict:
    """Horn PA with a column-permutation null; PCA and FA (SMC-reduced) variants."""
    rng = np.random.default_rng(seed)
    r = corr(x)
    obs_pca, obs_fa = eig_desc(r), eig_desc(smc_reduced(r))
    null_pca = np.empty((n_iter, x.shape[1]))
    null_fa = np.empty((n_iter, x.shape[1]))
    xp = x.copy()
    for i in range(n_iter):
        for j in range(x.shape[1]):
            xp[:, j] = x[rng.permutation(len(x)), j]
        rn = corr(xp)
        null_pca[i] = eig_desc(rn)
        null_fa[i] = eig_desc(smc_reduced(rn))
    thr_pca, thr_fa = np.quantile(null_pca, q, axis=0), np.quantile(null_fa, q, axis=0)

    def count(obs, thr):
        above = obs > thr
        return int(np.argmin(above)) if not above.all() else len(obs)

    return {
        "n_pca": count(obs_pca, thr_pca),
        "n_fa": count(obs_fa, thr_fa),
        "obs_pca": obs_pca,
        "thr_pca": thr_pca,
        "obs_fa": obs_fa,
        "thr_fa": thr_fa,
    }


def pa_count_fast(x: np.ndarray, n_iter: int, rng: np.random.Generator) -> int:
    """PCA-PA retained count only (used inside bootstraps / subsamples)."""
    obs = eig_desc(corr(x))
    null = np.empty((n_iter, x.shape[1]))
    n = len(x)
    for i in range(n_iter):
        idx = np.argsort(rng.random((n, x.shape[1])), axis=0)
        null[i] = eig_desc(corr(np.take_along_axis(x, idx, axis=0)))
    thr = np.quantile(null, 0.95, axis=0)
    above = obs > thr
    return int(np.argmin(above)) if not above.all() else len(obs)


def velicer_map(r: np.ndarray) -> int:
    p = r.shape[0]
    vals, vecs = np.linalg.eigh(r)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    load = vecs * np.sqrt(np.clip(vals, 0, None))
    off = ~np.eye(p, dtype=bool)
    fm = [np.mean(r[off] ** 2)]
    for m in range(1, p - 1):
        a = load[:, :m]
        c = r - a @ a.T
        d = np.sqrt(np.diag(c))
        pr = c / np.outer(d, d)
        fm.append(np.mean(pr[off] ** 2))
    return int(np.argmin(fm))


def efa(x: np.ndarray, k: int) -> FactorAnalyzer:
    fa = FactorAnalyzer(n_factors=k, rotation="oblimin" if k > 1 else None, method="minres")
    fa.fit(x)
    return fa


def aligned_phi(fa: FactorAnalyzer) -> np.ndarray:
    """Factor correlations in the same column order as `fa.loadings_`.

    factor-analyzer 0.5.1 re-sorts `loadings_` and `structure_` by variance after an oblique
    rotation but leaves `phi_` in the pre-sort order (post-audit fix, 2026-09-27). Recover the
    permutation from structure_ = loadings_ @ phi (exact for the aligned phi).
    """
    k = fa.loadings_.shape[1]
    phi = getattr(fa, "phi_", None)
    if phi is None or k == 1:
        return np.eye(k)
    lam, st = fa.loadings_, fa.structure_
    best, best_err = None, np.inf
    for perm in itertools.permutations(range(k)):
        cand = phi[np.ix_(perm, perm)]
        err = np.max(np.abs(lam @ cand - st))
        if err < best_err:
            best, best_err = cand, err
    assert best_err < 1e-8, f"phi_ alignment failed (max residual {best_err:.2e})"
    return best.copy()


def communalities(lam: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """True communalities diag(L Phi L') (get_communalities() ignores Phi under oblimin)."""
    return np.einsum("ij,jk,ik->i", lam, phi, lam)


def sort_factors(fa: FactorAnalyzer) -> tuple[np.ndarray, np.ndarray]:
    """Order factors by sum of squared loadings; flip so each factor's largest loading > 0."""
    lam = fa.loadings_.copy()
    phi = aligned_phi(fa)
    order = np.argsort(-(lam**2).sum(axis=0))
    lam, phi = lam[:, order], phi[np.ix_(order, order)]
    sign = np.sign(lam[np.argmax(np.abs(lam), axis=0), np.arange(lam.shape[1])])
    lam = lam * sign
    phi = phi * np.outer(sign, sign)
    return lam, phi


def congruence(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    num = a.T @ b
    den = np.sqrt(np.outer((a**2).sum(0), (b**2).sum(0)))
    return num / den


def matched_congruence(ref: np.ndarray, other: np.ndarray) -> np.ndarray:
    c = congruence(ref, other)
    rows, cols = linear_sum_assignment(-np.abs(c))
    out = np.empty(ref.shape[1])
    out[rows] = np.abs(c[rows, cols])
    return out


def cronbach_alpha(x: np.ndarray) -> float:
    k = x.shape[1]
    return float(k / (k - 1) * (1 - x.var(axis=0, ddof=1).sum() / x.sum(axis=1).var(ddof=1)))


def omega_total(x: np.ndarray) -> float:
    if x.shape[1] < 3:
        return float("nan")
    fa = FactorAnalyzer(n_factors=1, rotation=None, method="minres").fit(x)
    lam = np.abs(fa.loadings_[:, 0])
    return float(lam.sum() ** 2 / (lam.sum() ** 2 + (1 - lam**2).sum()))


def split_half(per: pd.DataFrame, segs: pd.Index, fa: FactorAnalyzer, n_split: int,
               seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Spearman-Brown split-half reliability of item means and factor scores over raters."""
    rng = np.random.default_rng(seed)
    d = per[per.segment.isin(segs)].reset_index(drop=True)
    item_r, fac_r = [], []
    for _ in range(n_split):
        key = rng.random(len(d))
        rank = pd.Series(key).groupby(d.segment).rank(method="first")
        size = d.groupby("segment").segment.transform("size")
        half = (rank <= size / 2).to_numpy()
        m1 = d[half].groupby("segment")[ITEMS].mean()
        m2 = d[~half].groupby("segment")[ITEMS].mean()
        common = m1.dropna().index.intersection(m2.dropna().index)
        a, b = m1.loc[common].to_numpy(), m2.loc[common].to_numpy()
        ri = np.array([np.corrcoef(a[:, j], b[:, j])[0, 1] for j in range(P)])
        fa_a, fa_b = fa.transform(a), fa.transform(b)
        rf = np.array([np.corrcoef(fa_a[:, j], fa_b[:, j])[0, 1] for j in range(fa_a.shape[1])])
        item_r.append(ri)
        fac_r.append(rf)
    sb = lambda r: 2 * r / (1 + r)  # noqa: E731
    return sb(np.mean(item_r, axis=0)), sb(np.mean(fac_r, axis=0))


def describe_corr(x: np.ndarray) -> dict:
    r = corr(x)
    off = r[~np.eye(P, dtype=bool)]
    ev = eig_desc(r)
    return {
        "n": int(len(x)),
        "mean_abs_r": float(np.mean(np.abs(off))),
        "median_abs_r": float(np.median(np.abs(off))),
        "max_abs_r": float(np.max(np.abs(off))),
        "ev1_share": float(ev[0] / P),
        "ev_top5": ev[:5].round(3).tolist(),
    }


# ----------------------------------------------------------------------------- main


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = {"seed": SEED}
    res["provenance"] = {
        "git": "no commits in repo yet (uncommitted)",
        "run_py_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],
        "csv_sha256": hashlib.sha256(CSV.read_bytes()).hexdigest()[:16],
        "data": "PercePiano shallow clone 2026-09-27 (DATASETS.md)",
    }

    df = load_long()
    seg = segment_means(df)
    x = seg[ITEMS].to_numpy()
    res["counts"] = {
        "rating_rows_after_gt7_drop": int(len(df)),
        "rows_dropped_gt7": df.attrs["n_dropped_gt7"],
        "segments": int(len(seg)),
        "pieces": int(seg.piece.nunique()),
        "performers": int(seg.performer.nunique()),
        "raters": int(df.rater.nunique()),
    }

    # cross-check against the authors' mean json files
    xc = {}
    for name in ["labels/label_2round_mean_reg_19_with0_rm_highstd0.json",
                 "label_2round_mean_reg_19_with0_rm_highstd0.json"]:
        js = json.load(open(RAW / name))
        common = [k for k in seg.index if k in js]
        a = np.array([js[k][:P] for k in common]) * 7
        b = seg.loc[common, ITEMS].to_numpy()
        xc[name] = {"keys": len(js), "common": len(common),
                    "max_abs_diff": float(np.max(np.abs(a - b))),
                    "frac_segments_exact": float(np.mean(np.all(np.abs(a - b) < 1e-9, axis=1)))}
    res["crosscheck_json"] = xc

    # ---------------- A. segment-mean level
    A: dict = {"corr": describe_corr(x)}
    r = corr(x)
    pd.DataFrame(r, index=ITEMS, columns=ITEMS).round(3).to_csv(OUT / "corr_segment_mean.csv")
    kmo_items, kmo = calculate_kmo(x)
    chi2, pval = calculate_bartlett_sphericity(x)
    A["kmo"], A["bartlett_chi2"], A["bartlett_p"] = float(kmo), float(chi2), float(pval)
    pa = parallel_analysis(x, 1000, SEED)
    A["pa_pca_retained"], A["pa_fa_retained"] = pa["n_pca"], pa["n_fa"]
    A["map_retained"] = velicer_map(r)
    pd.DataFrame({"obs_pca": pa["obs_pca"], "null95_pca": pa["thr_pca"],
                  "obs_fa": pa["obs_fa"], "null95_fa": pa["thr_fa"]},
                 index=range(1, P + 1)).round(4).to_csv(OUT / "parallel_analysis.csv")
    A["eigen"] = {"obs_pca": pa["obs_pca"].round(3).tolist(),
                  "null95_pca": pa["thr_pca"].round(3).tolist()}
    k_star = max(pa["n_pca"], 1)
    A["k_primary"] = k_star

    fits = {}
    for k in sorted({1, 2, 3, 4, 5, k_star}):
        fa = efa(x, k)
        lam, phi = sort_factors(fa)
        fits[k] = (fa, lam, phi)
        comm = communalities(lam, phi)  # post-audit: true h2 = diag(L Phi L')
        _, prop, cum = fa.get_factor_variance()
        tab = pd.DataFrame(lam, index=ITEMS, columns=[f"F{i + 1}" for i in range(k)])
        tab["h2"] = comm
        tab["pattern_ss"] = (lam**2).sum(1)  # what get_communalities() returned (not h2)
        tab.round(3).to_csv(OUT / f"loadings_k{k}.csv")
        cols = [f"F{i + 1}" for i in range(k)]
        pd.DataFrame(phi, index=cols, columns=cols).round(3).to_csv(OUT / f"phi_k{k}.csv")
        A[f"efa_k{k}"] = {"cum_var_pattern_ss": float(cum[-1]),
                          "mean_h2": float(np.mean(comm)),
                          "max_h2": float(np.max(comm)),
                          "max_h2_item": ITEMS[int(np.argmax(comm))],
                          "phi_offdiag_max": float(np.max(np.abs(phi - np.eye(k)))) if k > 1
                          else 0.0}

    # reliability for the primary solution
    fa, lam, phi = fits[k_star]
    assign = np.argmax(np.abs(lam), axis=1)
    salient = np.abs(lam).max(axis=1) >= 0.40
    rel = []
    for f in range(k_star):
        items = [i for i in range(P) if assign[i] == f and salient[i]]
        xi = x[:, items] * np.sign(lam[items, f])
        rel.append({"factor": f"F{f + 1}", "items": [ITEMS[i] for i in items],
                    "alpha": cronbach_alpha(xi) if len(items) > 1 else float("nan"),
                    "omega": omega_total(xi)})
    A["salient_items_none"] = [ITEMS[i] for i in range(P) if not salient[i]]

    per = one_row_per_rater_segment(df)
    sh_items, sh_fac = split_half(per, seg.index, fits[k_star][0], 100, SEED)
    # fa.transform returns unsorted factor order; map to sorted order
    order = np.argsort(-(fits[k_star][0].loadings_ ** 2).sum(axis=0))
    sh_fac = sh_fac[order]
    for f in range(k_star):
        rel[f]["split_half_sb"] = float(sh_fac[f])
    A["reliability"] = rel
    A["split_half_items"] = dict(zip(ITEMS, np.round(sh_items, 3).tolist(), strict=True))
    A["split_half_items_median"] = float(np.median(sh_items))

    # bootstrap stability (performers primary, pieces secondary)
    rng = np.random.default_rng(SEED)
    for cluster in ["performer", "piece"]:
        counts, congr = [], []
        for idx in bootstrap_indices(seg[cluster].to_numpy(), len(seg), 500, seed=SEED):
            xb = x[idx]
            counts.append(pa_count_fast(xb, 200, rng))
            try:
                lb, _ = sort_factors(efa(xb, k_star))
                congr.append(matched_congruence(lam, lb))
            except Exception:  # noqa: BLE001  (non-convergence in a replicate)
                congr.append(np.full(k_star, np.nan))
        counts = np.array(counts)
        congr = np.array(congr)
        A[f"boot_{cluster}"] = {
            "retained_counts": {int(v): int(c) for v, c in
                                zip(*np.unique(counts, return_counts=True), strict=True)},
            "frac_gt8": float(np.mean(counts > 8)),
            "frac_3_to_5": float(np.mean((counts >= 3) & (counts <= 5))),
            "congruence_median_per_factor": np.nanmedian(congr, axis=0).round(3).tolist(),
            "congruence_p05_per_factor": np.nanquantile(congr, 0.05, axis=0).round(3).tolist(),
        }

    # sensitivities
    noscore = seg[seg.performer != "Score"]
    xs = noscore[ITEMS].to_numpy()
    pa_s = parallel_analysis(xs, 1000, SEED)
    A["sens_no_score"] = {"n": int(len(xs)), "pa_pca": pa_s["n_pca"], "pa_fa": pa_s["n_fa"],
                          "map": velicer_map(corr(xs)), **describe_corr(xs)}
    dedup = segment_means(per)
    xd = dedup[ITEMS].to_numpy()
    pa_d = parallel_analysis(xd, 1000, SEED)
    A["sens_dedup"] = {"n": int(len(xd)), "pa_pca": pa_d["n_pca"], "pa_fa": pa_d["n_fa"],
                       "map": velicer_map(corr(xd)), **describe_corr(xd)}
    # post-audit sensitivities (2026-09-27): the pedal doublet, and dedup + no Score together
    pedal = [ITEMS.index("Pedal_Sparse_Saturated"), ITEMS.index("Pedal_Clean_Blurred")]
    A["pedal_items_r"] = float(r[pedal[0], pedal[1]])
    keep = [i for i in range(P) if i not in pedal]
    x_merge = np.column_stack([x[:, keep], x[:, pedal].mean(axis=1)])
    x_drop = np.delete(x, pedal[1], axis=1)
    xds = dedup[dedup.performer != "Score"][ITEMS].to_numpy()
    for name, xv in [("sens_pedal_merged", x_merge), ("sens_drop_pedal_clean", x_drop),
                     ("sens_dedup_no_score", xds)]:
        pa_v = parallel_analysis(xv, 1000, SEED)
        A[name] = {"n": int(len(xv)), "n_items": int(xv.shape[1]), "pa_pca": pa_v["n_pca"],
                   "pa_fa": pa_v["n_fa"], "map": velicer_map(corr(xv))}
    res["A_segment_mean"] = A

    # ---------------- B. per-rater level
    B: dict = {}
    comp = per.dropna(subset=ITEMS).reset_index(drop=True)
    B["complete_rows"] = int(len(comp))
    cen = comp[ITEMS] - comp.groupby("rater")[ITEMS].transform("mean")
    xc_ = cen.to_numpy()
    pa_b = parallel_analysis(xc_, 1000, SEED)
    B["pooled_within_rater"] = {"pa_pca": pa_b["n_pca"], "pa_fa": pa_b["n_fa"],
                                "map": velicer_map(corr(xc_)), **describe_corr(xc_)}
    fa_b = efa(xc_, k_star)
    lam_b, _ = sort_factors(fa_b)
    B["pooled_congruence_with_segment_mean"] = matched_congruence(lam, lam_b).round(3).tolist()
    pd.DataFrame(lam_b, index=ITEMS, columns=[f"F{i + 1}" for i in range(k_star)]).round(3) \
        .to_csv(OUT / f"loadings_pooled_within_rater_k{k_star}.csv")

    rows = []
    rng = np.random.default_rng(SEED + 1)
    ev1_seg = eig_desc(r)[0] / P
    for rid, g in comp.groupby("rater"):
        if len(g) < 100:
            continue
        xr = g[ITEMS].to_numpy()
        if np.any(xr.std(axis=0) == 0):
            rows.append({"rater": rid, "n": len(g), "note": "constant item"})
            continue
        n_r = pa_count_fast(xr, 500, rng)
        ev = eig_desc(corr(xr))
        sub = []
        for _ in range(200):
            pick = rng.choice(len(x), size=min(len(g), len(x)), replace=False)
            sub.append(pa_count_fast(x[pick], 100, rng))
        rows.append({"rater": rid, "n": len(g), "pa_rater": n_r,
                     "pa_segmean_matchedN_median": float(np.median(sub)),
                     "ev1_share_rater": float(ev[0] / P),
                     "mean_abs_r_rater": float(np.mean(np.abs(corr(xr)[~np.eye(P, dtype=bool)])))})
    pr = pd.DataFrame(rows)
    pr.to_csv(OUT / "per_rater.csv", index=False)
    ok = pr.dropna(subset=["pa_rater"])
    B["per_rater"] = {
        "n_raters": int(len(ok)),
        "n_excluded_constant_item": int(pr.pa_rater.isna().sum()) if "pa_rater" in pr else 0,
        "pa_rater_median": float(ok.pa_rater.median()),
        "pa_rater_counts": {int(v): int(c) for v, c in ok.pa_rater.value_counts().items()},
        "matchedN_median_of_medians": float(ok.pa_segmean_matchedN_median.median()),
        "frac_rater_lt_matched": float(np.mean(ok.pa_rater < ok.pa_segmean_matchedN_median)),
        "frac_rater_gt_matched": float(np.mean(ok.pa_rater > ok.pa_segmean_matchedN_median)),
        "ev1_share_rater_median": float(ok.ev1_share_rater.median()),
        "ev1_share_segment_mean": float(ev1_seg),
        "frac_raters_ev1_ge_segmean": float(np.mean(ok.ev1_share_rater >= ev1_seg)),
    }

    # exploratory: within-rater test-retest on repeat ratings with a new dataID
    d1 = df.drop_duplicates(["rater", "dataID", "segment"])
    rep = d1[d1.duplicated(["rater", "segment"], keep=False)].copy()
    rep["k"] = rep.groupby(["rater", "segment"]).cumcount()
    a = rep[rep.k == 0].set_index(["rater", "segment"])[ITEMS]
    b = rep[rep.k == 1].set_index(["rater", "segment"])[ITEMS]
    common = a.index.intersection(b.index)
    tr = {it: float(pd.concat([a.loc[common, it], b.loc[common, it]], axis=1).dropna()
                    .corr().iloc[0, 1]) for it in ITEMS}
    B["test_retest"] = {"pairs": int(len(common)), "raters": int(common.get_level_values(0)
                                                                  .nunique()),
                        "median_r": float(np.median(list(tr.values()))), "per_item": tr}
    res["B_per_rater"] = B
    res["wall_time_sec"] = round(time.time() - t0, 1)

    with open(OUT / "results.json", "w") as f:
        json.dump(res, f, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else o)
    print(json.dumps(res, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else o))


if __name__ == "__main__":
    main()
