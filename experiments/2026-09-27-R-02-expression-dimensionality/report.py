"""R-02 step 3: headline tables, verdict and figures (called from analyze.py)."""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from pianolens.eval import bootstrap_ci

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
FIG = ART / "figures"

# reference categorical palette (dataviz skill, light surface)
C_REAL, C_PHASE, C_OTHER, C_MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"
SURFACE, INK, INK2 = "#fcfcfb", "#0b0b0b", "#52514e"


def _load():
    with open(ART / "piece_results.pkl", "rb") as fh:
        d = pickle.load(fh)
    rows = d["rows"]
    scal = pd.DataFrame([{k: v for k, v in r.items() if np.ndim(v) == 0} for r in rows])
    qc = pd.DataFrame(d["infos"])
    return rows, scal, qc


def _ci(x, f):
    r = bootstrap_ci(lambda a: float(f(a)), np.asarray(x, float), n_boot=2000, seed=0)
    return f"{r.estimate:.2f} [{r.low:.2f}, {r.high:.2f}]"


def _cnt(v: float) -> str:
    return f">{int(v) - 1}" if v in (21, 41) else f"{v:g}"


def block_table(scal: pd.DataFrame, variant: str) -> pd.DataFrame:
    real = scal[(scal.variant == variant) & (scal.source == "real")]
    ph = scal[(scal.variant == variant) & (scal.source == "phase")].set_index(["piece_id", "block"])
    out = []
    for blk in ["joint", "tempo", "vel_smooth", "vel_raw", "residual", "joint_3bar",
                "joint_velz", "joint_win16", "joint_trim10"]:
        g = real[real.block == blk]
        if g.empty:
            continue
        k = g["k80_in"].to_numpy(float)
        kho = g["k80_ho"].to_numpy(float)
        row = {
            "block": blk, "pieces": len(g), "n (median)": int(g["n"].median()),
            "beats (median)": int(g["p"].median()),
            "k80_in median [IQR]": f"{np.median(k):g} [{np.percentile(k, 25):g}, "
                                   f"{np.percentile(k, 75):g}]",
            "k80_in median 95% CI": _ci(k, np.median),
            "share k80_in <= 10": _ci(k, lambda a: np.mean(a <= 10)),
            "share k80_in > 20": _ci(k, lambda a: np.mean(a > 20)),
            "k90_in median": float(g["k90_in"].median()),
            "PC1 median": round(float(g["pc1"].median()), 3),
            "k80_ho median [IQR]": f"{_cnt(np.median(kho))} [{_cnt(np.percentile(kho, 25))}, "
                                   f"{_cnt(np.percentile(kho, 75))}]",
            "share k80_ho <= 10": _ci(kho, lambda a: np.mean(a <= 10)),
            "k80_ho_ext median (<=40)": _cnt(float(g["k80_ho_ext"].median())),
            "ho R2 k=5 / 10 / 20": f"{g['ho_r2_k5'].median():.2f} / {g['ho_r2_k10'].median():.2f}"
                                   f" / {g['ho_r2_k20'].median():.2f}",
            "mean-curve share": round(float(g["mean_share"].median()), 3),
        }
        key = [(p, blk) for p in g["piece_id"]]
        if blk in {"joint", "tempo", "vel_smooth", "vel_raw", "residual", "joint_win16"} and all(
                kk in ph.index for kk in key):
            pk = ph.loc[key, "k80_in"].to_numpy(float)
            row["phase-null k80_in median"] = float(np.median(pk))
            row["share real < null (k80_in)"] = _ci(k - pk, lambda a: np.mean(a < 0))
            row["phase-null ho R2 k=10"] = round(float(ph.loc[key, "ho_r2_k10"].median()), 2)
        out.append(row)
    return pd.DataFrame(out)


def null_table(scal: pd.DataFrame, variant: str) -> pd.DataFrame:
    g = scal[(scal.variant == variant) & scal.block.isin(["joint", "tempo", "vel_smooth"])]
    t = g.groupby(["block", "source"]).agg(pieces=("k80_in", "size"),
                                           k80_in=("k80_in", "median"),
                                           k90_in=("k90_in", "median"), pc1=("pc1", "median"),
                                           ho_r2_k10=("ho_r2_k10", "median"))
    return t.round(3).reset_index()


def strata(scal: pd.DataFrame, qc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    j = scal[(scal.block == "joint") & scal.source.isin(["real", "phase"])]
    w = j.pivot_table(index=["piece_id", "variant"], columns="source",
                      values=["k80_in", "k80_ho", "p", "n", "max_k"]).reset_index()
    w.columns = ["_".join(c).strip("_") for c in w.columns]
    a = w[w.variant == "n50"].copy()
    a["beats_bin"] = pd.qcut(a["p_real"] / 2, 3)  # joint p = 2 x beats
    s1 = a.groupby("beats_bin", observed=True).agg(
        pieces=("piece_id", "size"), k80_in=("k80_in_real", "median"),
        k80_in_null=("k80_in_phase", "median"), k80_ho=("k80_ho_real", "median"),
        k80_in_over_max=("k80_in_real", lambda s: float(np.median(s / 49)))).reset_index()
    b = w[w.variant == "all"].copy()
    b["n_bin"] = pd.cut(b["n_real"], [0, 75, 150, 300, 5000])
    b["ratio"] = b["k80_in_real"] / b["max_k_real"]
    s2 = b.groupby("n_bin", observed=True).agg(
        pieces=("piece_id", "size"), k80_in=("k80_in_real", "median"),
        k80_in_null=("k80_in_phase", "median"), k80_ho=("k80_ho_real", "median"),
        k80_over_maxk=("ratio", "median")).reset_index()
    return s1, s2


def verdict(scal: pd.DataFrame) -> str:
    g = scal[(scal.variant == "n50") & (scal.block == "joint")]
    r = g[g.source == "real"].set_index("piece_id")
    p = g[g.source == "phase"].set_index("piece_id").loc[r.index]
    a = np.mean(r["k80_in"] <= 10)
    b = np.mean(r["k80_ho"] <= 10)
    c = np.mean(r["k80_in"].to_numpy() < p["k80_in"].to_numpy())
    f = np.mean(r["k80_in"] > 20)
    lines = [f"share k80_in <= 10: {a:.3f}", f"share k80_ho <= 10: {b:.3f}",
             f"share k80_in < phase null: {c:.3f}", f"share k80_in > 20: {f:.3f}"]
    if f > 0.5:
        v = "FALSIFIED (k80_in > 20 on most pieces)"
    elif a > 0.5 and b > 0.5 and c > 0.5:
        v = "SUPPORTED"
    else:
        v = "PARTLY SUPPORTED / INCONCLUSIVE: " + ", ".join(
            n for n, ok in (("in-sample <= 10", a > 0.5), ("held-out <= 10", b > 0.5),
                            ("below phase null", c > 0.5)) if not ok) + " not met"
    return "\n".join(lines + [v])


def cmd_summarize() -> None:
    rows, scal, qc = _load()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    out = []
    ok = qc[~qc.get("failed", pd.Series(False, index=qc.index)).fillna(False).astype(bool)]
    out.append(f"pieces: {len(qc)}; QC-passing {len(ok)}; n50-analysed "
               f"{scal[(scal.variant == 'n50')].piece_id.nunique()}")
    for c in ["n_total", "n_kept", "beats_total", "beats_kept", "vbeats_kept", "pos_total",
              "pos_kept", "n_resid_kept", "edf_median", "n_pauses_median", "bpb"]:
        if c in ok:
            out.append(f"  {c}: median {ok[c].median():g}, IQR [{ok[c].quantile(.25):g}, "
                       f"{ok[c].quantile(.75):g}], sum {ok[c].sum():g}")
    out.append(f"  performances dropped by QC: {int((ok.n_total - ok.n_kept).sum())} of "
               f"{int(ok.n_total.sum())}")
    for v in ["n50", "all"]:
        t = block_table(scal, v)
        t.to_csv(ART / f"headline_{v}.csv", index=False)
        out.append(f"\n== headline {v} ==\n" + t.T.to_string())
        n = null_table(scal, v)
        n.to_csv(ART / f"nulls_{v}.csv", index=False)
        out.append(f"\n== nulls {v} ==\n" + n.to_string())
    s1, s2 = strata(scal, qc)
    s1.to_csv(ART / "strata_beats_n50.csv", index=False)
    s2.to_csv(ART / "strata_nperf_all.csv", index=False)
    out.append("\n== joint n50 by beats tertile ==\n" + s1.to_string())
    out.append("\n== joint all by n performances ==\n" + s2.to_string())
    out.append("\n== verdict (pre-registered, joint n50) ==\n" + verdict(scal))
    txt = "\n".join(out)
    (ART / "summary.txt").write_text(txt)
    print(txt)


# --------------------------------------------------------------------------- figures


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(C_MUTED)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color="#e6e5e0", lw=0.6)
    ax.set_axisbelow(True)


def cmd_figures() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG.mkdir(parents=True, exist_ok=True)
    rows, scal, qc = _load()
    # 1. cumulative explained variance and held-out R2 (n50), real vs phase null
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5), facecolor=SURFACE)
    for j, blk in enumerate(["joint", "tempo", "vel_smooth"]):
        for i, (key, lab) in enumerate([("ratios", "in-sample cumulative variance"),
                                        ("ho", "held-out reconstruction R²")]):
            ax = axes[i, j]
            _style(ax)
            for src, col in (("real", C_REAL), ("phase", C_PHASE)):
                arrs = [r[key] for r in rows if r["variant"] == "n50" and r["block"] == blk
                        and r["source"] == src and key in r]
                if not arrs:
                    continue
                L = min(len(a) for a in arrs)
                m = np.array([a[:L] for a in arrs], float)
                if key == "ratios":
                    m = np.cumsum(m, axis=1)
                k = np.arange(1, L + 1)
                med = np.median(m, 0)
                ax.fill_between(k, np.percentile(m, 25, 0), np.percentile(m, 75, 0), color=col,
                                alpha=0.18, lw=0)
                ax.plot(k, med, color=col, lw=2,
                        label="real" if src == "real" else "phase-randomized null")
            ax.axhline(0.8, color=INK2, lw=1, ls="--")
            ax.axvline(10, color=C_MUTED, lw=1, ls=":")
            ax.set_ylim(0, 1)
            ax.set_xlim(1, 40)
            ax.set_title(f"{blk}: {lab}", fontsize=9, color=INK)
            if i == 1:
                ax.set_xlabel("components k", fontsize=8, color=INK2)
    axes[0, 0].legend(fontsize=8, frameon=False)
    fig.suptitle("PianoCoRe tier A, n = 50 performances per piece: median and IQR across pieces",
                 fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "scree_heldout_n50.png", dpi=150)
    plt.close(fig)

    # 2. histogram of k80_in (joint n50): real vs null
    fig, ax = plt.subplots(figsize=(6, 3.5), facecolor=SURFACE)
    _style(ax)
    g = scal[(scal.variant == "n50") & (scal.block == "joint")]
    bins = np.arange(0.5, 50.5, 1)
    for src, col, lab in (("real", C_REAL, "real"), ("phase", C_PHASE, "phase-randomized null"),
                          ("shuffle", C_OTHER, "column-shuffled null")):
        ax.hist(g[g.source == src]["k80_in"], bins=bins, color=col, alpha=0.55, label=lab)
    ax.axvline(10, color=INK2, lw=1, ls="--")
    ax.axvline(20, color=INK2, lw=1, ls=":")
    ax.set_xlabel("components for 80% (in-sample), joint tempo + velocity, n = 50", fontsize=8)
    ax.set_ylabel("pieces", fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "k80_hist_joint_n50.png", dpi=150)
    plt.close(fig)

    # 3. k80 vs beats, n50
    fig, ax = plt.subplots(figsize=(6, 3.5), facecolor=SURFACE)
    _style(ax)
    for src, col in (("real", C_REAL), ("phase", C_PHASE)):
        h = g[g.source == src]
        ax.scatter(h["p"] / 2, h["k80_in"], s=9, color=col, alpha=0.5,
                   label="real" if src == "real" else "phase null")
    ax.set_xscale("log")
    ax.set_xlabel("beats in piece (log)", fontsize=8)
    ax.set_ylabel("k80 in-sample (joint, n = 50)", fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "k80_vs_beats_n50.png", dpi=150)
    plt.close(fig)

    # 4. interpretability: loadings for two well-known pieces (all performances)
    import sys

    sys.path.insert(0, str(HERE))
    from analyze import CURVES, load_blocks

    from pianolens.data.pianocore_cache import piece_slug

    op9_2 = "pianocore:Chopin,_Frédéric/Nocturnes,_Op.9/Nocturne_No.2_in_E_flat_major,_Andante"
    for pid, short in (("chopin_op10_no3", "chopin_op10_no3"), (op9_2, "chopin_op9_no2")):
        path = CURVES / f"{piece_slug(pid)}.npz"
        if not path.exists():
            continue
        b = load_blocks(path)
        fig, axes = plt.subplots(4, 2, figsize=(13, 8), sharex=True, facecolor=SURFACE)
        for j, (blk, lab) in enumerate((("T", "log tempo ratio"), ("Vs", "velocity (MIDI)"))):
            x = b[blk]
            mu = x.mean(0)
            u, s, vt = np.linalg.svd(x - mu, full_matrices=False)
            ev = s**2 / (s**2).sum()
            grid = b["grid"]
            ax = axes[0, j]
            _style(ax)
            lo, hi = np.percentile(x, 10, 0), np.percentile(x, 90, 0)
            ax.fill_between(grid, lo, hi, color=C_REAL, alpha=0.15, lw=0)
            ax.plot(grid, mu, color=C_REAL, lw=1.6)
            ax.set_title(f"{short} {lab}: mean curve and 10-90% band (n = {len(x)})",
                         fontsize=9, color=INK)
            for c in range(3):
                ax = axes[c + 1, j]
                _style(ax)
                sd = s[c] / np.sqrt(len(x))
                sign = np.sign(vt[c][np.argmax(np.abs(vt[c]))])
                ax.plot(grid, sign * vt[c] * sd, color=[C_REAL, C_PHASE, C_OTHER][c], lw=1.6)
                ax.axhline(0, color=C_MUTED, lw=0.8)
                ax.set_title(f"PC{c + 1} ({ev[c]:.0%}): loading x 1 SD of score", fontsize=9,
                             color=INK)
            for ax in axes[:, j]:
                for k, bs in enumerate(b["bar_starts"]):
                    if grid[0] <= bs <= grid[-1]:
                        ax.axvline(bs, color="#d9d8d2", lw=0.5 if k % 4 else 1.0, zorder=0)
            axes[-1, j].set_xlabel("score beat (thin lines = bars, thick = every 4th bar)",
                                   fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG / f"loadings_{short}.png", dpi=150)
        plt.close(fig)
    print("figures in", FIG)
