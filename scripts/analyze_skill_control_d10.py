"""D-10 analysis: do tier A / tier B features separate MAJEPPA skill groups at matched note rate?

    uv run python scripts/analyze_skill_control_d10.py [--boot 1000]

Reads ``data/interim/skill_control_d10/majeppa_features.csv`` (``build_skill_control_d10.py``).

Sets:
* tier A: every performance (and the trusted-alignment subset, match ratio >= 0.8).
* tier B: trusted alignment (``a_alignment_suspect`` False) and a quantized score (at most 10%
  of score onsets off the 1/48-quarter grid). Below match ratio 0.8 the F-01 validation says
  not to trust the labels, and timing features read alignment errors.

Model per feature (descriptive, no tuning): ``y = piece fixed effect + b_int * intermediate +
b_adv * advanced + g * log(note rate) + e`` by OLS, beginner = reference. Positive, skewed
features (SDs, CVs, RMS) enter as ``log(y)``, so ``exp(b)`` is a ratio (advanced / beginner);
the others enter raw. ``d`` = b / residual SD (within-piece, rate-adjusted standardized effect).
Rate: the feature's own run rate for evenness (``even_note_rate_nps`` /
``even_strict_note_rate_nps``), otherwise performed notes per second. 95% CIs: percentile
bootstrap over ``recording_id`` (one source video = one performer; the only performer proxy
MAJEPPA gives). Also: the same model without the rate term, and within-piece medians per
note-rate bin.

Writes ``effects.csv``, ``by_level.csv``, ``by_rate_bin.csv``, ``counts.csv``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[1] / "data" / "interim" / "skill_control_d10"
GROUPS = ["beginner", "intermediate", "advanced"]
LEVELS = ["child_beginner", "adult_beginner", "adult_intermediate", "child_professional",
          "piano_teacher", "virtuoso"]  # fmt: skip
# (column, tier, log-transform, rate column)
FEATURES = [
    ("a_accuracy", "A", False, "perf_note_rate_nps"),
    ("a_error_rate", "A", False, "perf_note_rate_nps"),
    ("a_wrong_rate", "A", False, "perf_note_rate_nps"),
    ("a_missed_rate", "A", False, "perf_note_rate_nps"),
    ("a_extra_rate", "A", False, "perf_note_rate_nps"),
    ("timing_noise_best_rms_ms", "B", True, "perf_note_rate_nps"),
    ("timing_noise_best_rms_beats", "B", True, "perf_note_rate_nps"),
    ("timing_noise_cons_rms_ms", "B", True, "perf_note_rate_nps"),
    ("jitter_nometric_rms_ms", "B", True, "perf_note_rate_nps"),
    ("jitter_nometric_rms_beats", "B", True, "perf_note_rate_nps"),
    ("even_ioi_cv", "B", True, "even_note_rate_nps"),
    ("even_vel_sd_midi", "B", True, "even_note_rate_nps"),
    ("even_strict_ioi_cv", "B", True, "even_strict_note_rate_nps"),
    ("even_strict_vel_sd_midi", "B", True, "even_strict_note_rate_nps"),
    ("hand_async_resid_sd_ms", "B", True, "perf_note_rate_nps"),
    ("hand_async_resid_sd_beats", "B", True, "perf_note_rate_nps"),
    ("hand_async_vel_slope_ms", "B", False, "perf_note_rate_nps"),
    ("tempo_instability_log_sd", "B", True, "perf_note_rate_nps"),
    ("tempo_drift_log", "B", True, "perf_note_rate_nps"),
    ("pedal_blur_fraction", "B", False, "perf_note_rate_nps"),
]  # fmt: skip


def load() -> pd.DataFrame:
    d = pd.read_csv(D / "majeppa_features.csv")
    n = d["a_n_score_notes"].where(d["a_n_score_notes"] > 0)
    d["a_wrong_rate"] = d["a_n_wrong_pitch"] / n
    d["a_missed_rate"] = d["a_n_missed"] / n
    d["a_extra_rate"] = d["a_n_extra"] / n
    d["timing_noise_cons_rms_ms"] = d["timing_noise_rms_ms"].where(
        d["timing_noise_coverage"] >= 0.5)
    d["trusted"] = ~d["a_alignment_suspect"].astype(bool)
    d["tier_b_ok"] = d["trusted"] & (d["score_offgrid_share"] <= 0.10)
    return d


def design(df: pd.DataFrame, rate: str | None) -> tuple[np.ndarray, list[str]]:
    X = [(df["skill_group"] == "intermediate").to_numpy(float),
         (df["skill_group"] == "advanced").to_numpy(float)]  # fmt: skip
    names = ["b_int", "b_adv"]
    if rate:
        X.append(np.log(df[rate].to_numpy(float)))
        names.append("g_lograte")
    P = pd.get_dummies(df["score_id"]).to_numpy(float)
    return np.column_stack(X + [P]), names


def fit(df: pd.DataFrame, y: np.ndarray, rate: str | None) -> dict[str, float]:
    X, names = design(df, rate)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(len(y) - np.linalg.matrix_rank(X), 1)
    out = dict(zip(names, beta[: len(names)], strict=True))
    out["resid_sd"] = float(np.sqrt(resid @ resid / dof))
    return out


def prep(d: pd.DataFrame, col: str, logy: bool, rate: str) -> tuple[pd.DataFrame, np.ndarray]:
    x = d[[col, rate, "skill_group", "score_id", "recording_id"]].copy()
    x = x[np.isfinite(x[col]) & np.isfinite(x[rate]) & (x[rate] > 0)]
    if logy:
        x = x[x[col] > 0]
    # keep pieces with at least two skill groups (single-group pieces carry no contrast)
    ng = x.groupby("score_id")["skill_group"].nunique()
    x = x[x["score_id"].isin(ng[ng >= 2].index)].reset_index(drop=True)
    y = np.log(x[col].to_numpy(float)) if logy else x[col].to_numpy(float)
    return x, y


def effects(d: pd.DataFrame, n_boot: int, seed: int = 0, only: list[str] | None = None
            ) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for col, tier, logy, rate in FEATURES:
        if only is not None and col not in only:
            continue
        sub = d if tier == "A" else d[d["tier_b_ok"]]
        x, y = prep(sub, col, logy, rate)
        cnt = x["skill_group"].value_counts()
        if len(x) < 20 or cnt.get("beginner", 0) < 5 or cnt.get("advanced", 0) < 5:
            rows.append({"feature": col, "tier": tier, "n": len(x)})
            continue
        est = fit(x, y, rate)
        est0 = fit(x, y, None)
        recs = x["recording_id"].unique()
        by_rec = {r: np.flatnonzero(x["recording_id"].to_numpy() == r) for r in recs}
        boots = []
        for _ in range(n_boot):
            pick = rng.choice(recs, size=len(recs), replace=True)
            idx = np.concatenate([by_rec[r] for r in pick])
            xb = x.iloc[idx].reset_index(drop=True)
            try:
                e = fit(xb, y[idx], rate)
                boots.append((e["b_adv"], e["b_int"], e["b_adv"] / e["resid_sd"]))
            except Exception:  # noqa: BLE001
                continue
        b = np.array(boots)
        lo, hi = np.nanpercentile(b, [2.5, 97.5], axis=0)
        tr = np.exp if logy else (lambda v: v)
        rows.append({
            "feature": col, "tier": tier, "log": logy, "rate_col": rate, "n": len(x),
            "n_pieces": x["score_id"].nunique(), "n_recordings": len(recs),
            "n_beginner": int(cnt.get("beginner", 0)),
            "n_intermediate": int(cnt.get("intermediate", 0)),
            "n_advanced": int(cnt.get("advanced", 0)),
            "adv_vs_beg": float(tr(est["b_adv"])), "adv_lo": float(tr(lo[0])),
            "adv_hi": float(tr(hi[0])),
            "int_vs_beg": float(tr(est["b_int"])), "int_lo": float(tr(lo[1])),
            "int_hi": float(tr(hi[1])),
            "d_adv": est["b_adv"] / est["resid_sd"], "d_adv_lo": float(lo[2]),
            "d_adv_hi": float(hi[2]),
            "adv_vs_beg_norate": float(tr(est0["b_adv"])),
            "rate_slope": est["g_lograte"], "resid_sd": est["resid_sd"],
            "n_boot": len(b),
        })  # fmt: skip
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    d = load()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 200)

    counts = pd.DataFrame({
        "all": d.groupby("expertise_level").size(),
        "trusted": d[d["trusted"]].groupby("expertise_level").size(),
        "tier_b_ok": d[d["tier_b_ok"]].groupby("expertise_level").size(),
        "recordings_tier_b": d[d["tier_b_ok"]].groupby("expertise_level")["recording_id"]
        .nunique(),
        "pieces_tier_b": d[d["tier_b_ok"]].groupby("expertise_level")["score_id"].nunique(),
        "median_note_rate": d[d["tier_b_ok"]].groupby("expertise_level")["perf_note_rate_nps"]
        .median(),
        "consensus_share": d[d["tier_b_ok"]].groupby("expertise_level")["timing_noise_source"]
        .apply(lambda s: (s == "consensus").mean()),
    }).reindex(LEVELS)  # fmt: skip
    counts.loc["total"] = [len(d), int(d["trusted"].sum()), int(d["tier_b_ok"].sum()),
                           d.loc[d["tier_b_ok"], "recording_id"].nunique(),
                           d.loc[d["tier_b_ok"], "score_id"].nunique(),
                           d.loc[d["tier_b_ok"], "perf_note_rate_nps"].median(),
                           (d.loc[d["tier_b_ok"], "timing_noise_source"] == "consensus").mean()]
    counts.to_csv(D / "counts.csv")
    print("counts\n", counts.round(3))
    print("\nrecording type x level (tier B)\n",
          pd.crosstab(d.loc[d["tier_b_ok"], "expertise_level"],
                      d.loc[d["tier_b_ok"], "recording_type"]).reindex(LEVELS))
    print("\nscores excluded as unquantized:",
          d.loc[d["score_offgrid_share"] > 0.10, "score_id"].nunique())

    feats = [f for f, *_ in FEATURES] + ["perf_note_rate_nps", "even_note_rate_nps",
                                          "even_strict_note_rate_nps", "t_tempo_bpm_geomean"]
    lv = pd.concat({
        "A_all": d.groupby("expertise_level")[[f for f, t, *_ in FEATURES if t == "A"]].median(),
        "B": d[d["tier_b_ok"]].groupby("expertise_level")[feats].median(),
    }, axis=1).reindex(LEVELS)  # fmt: skip
    lv.T.to_csv(D / "by_level.csv")
    print("\nmedian by level\n", lv.T.round(3))

    b = d[d["tier_b_ok"]].copy()
    bins = [0, 2, 4, 6, 8, 12, 40]
    rows = []
    for f, tier, _logy, rate in FEATURES:
        if tier != "B":
            continue
        x = b[np.isfinite(b[f]) & np.isfinite(b[rate])].copy()
        x["rate_bin"] = pd.cut(x[rate], bins)
        g = x.groupby(["rate_bin", "skill_group"], observed=True)[f].agg(["median", "size"])
        g = g.unstack("skill_group")
        g.columns = [f"{s}_{c}" for c, s in g.columns]
        g.insert(0, "feature", f)
        rows.append(g.reset_index())
    rb = pd.concat(rows)
    rb.to_csv(D / "by_rate_bin.csv", index=False)
    print("\nby rate bin (medians, n)\n", rb.round(3).to_string())

    eff = effects(d, a.boot)
    eff.to_csv(D / "effects.csv", index=False)
    cols = ["feature", "n", "n_pieces", "n_recordings", "n_beginner", "n_advanced",
            "adv_vs_beg", "adv_lo", "adv_hi", "d_adv", "d_adv_lo", "d_adv_hi", "int_vs_beg",
            "int_lo", "int_hi", "adv_vs_beg_norate", "rate_slope"]  # fmt: skip
    print("\neffects (log features: ratio advanced / beginner)\n", eff[cols].round(3).to_string())

    # sensitivity: recording context is confounded with level (virtuoso = concert recordings,
    # piano teachers mostly class demos)
    key = ["a_accuracy", "a_error_rate", "timing_noise_best_rms_ms",
           "timing_noise_best_rms_beats", "jitter_nometric_rms_ms", "even_ioi_cv",
           "even_vel_sd_midi", "even_strict_ioi_cv", "even_strict_vel_sd_midi",
           "hand_async_resid_sd_ms", "tempo_instability_log_sd", "pedal_blur_fraction"]
    children = d[d["expertise_level"].isin(["child_beginner", "child_professional"])]
    sens = {
        "no_virtuoso": d[d["expertise_level"] != "virtuoso"],
        "children_only": children,
        "practice_performance_only": d[d["recording_type"].isin(["practice", "performance"])],
    }
    out = []
    for name, sub in sens.items():
        e = effects(sub, max(200, a.boot // 2), only=key)
        e.insert(0, "subset", name)
        out.append(e)
    se = pd.concat(out)
    se.to_csv(D / "effects_sensitivity.csv", index=False)
    cols_s = ["subset", "feature", "n", "n_pieces", "n_beginner", "n_advanced", "adv_vs_beg",
              "adv_lo", "adv_hi", "d_adv", "d_adv_lo", "d_adv_hi"]  # fmt: skip
    print("\nsensitivity\n", se.reindex(columns=cols_s).round(3).to_string())

    # trusted-only tier A
    t = d[d["trusted"]]
    print("\ntier A on trusted alignments, median by level\n",
          t.groupby("expertise_level")[["a_accuracy", "a_error_rate", "a_extra_rate"]]
          .median().reindex(LEVELS).round(3))
    print("\nshare with suspect alignment by level\n",
          (~d["trusted"]).groupby(d["expertise_level"]).mean().reindex(LEVELS).round(3))


if __name__ == "__main__":
    main()
