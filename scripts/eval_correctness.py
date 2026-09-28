"""Evaluate tier A correctness labels (F-02) on the synthetic mistake set (D-08).

Run: ``uv run python scripts/eval_correctness.py [--workers 12] [--limit N]``

For every performance in ``data/processed/mistakes_v1`` (clean copy + each mistake rate), this
aligns the perturbed MIDI to its score with ``pianolens.align.align_performance``, labels it with
``pianolens.features.correctness.correctness``, and scores the labels against the injected
ground truth. Two modes:

* ``aligned``: our aligner, as in production.
* ``gt_alignment``: the exact ground-truth alignment of the perturbed performance, to separate
  labelling errors (wrong-pitch pairing, ornaments) from alignment errors.

Scoring: units are performed notes (extra, wrong_pitch), score notes (missed) and bars (every
type). Mistakes already present in the source performance ((n)ASAP ground-truth insertions and
deletions: real slips or ground-truth noise) are "don't care": predictions on them count neither
as true nor as false positives; at bar level, bars holding such a natural mistake are don't care
for the matching type. ``wrong_pitch_lenient`` counts an injected wrong pitch as found when its
performed note is labelled wrong_pitch or extra. ``any`` pools every type at bar level.

Outputs (gitignored): ``data/interim/correctness_eval/counts.csv`` (tp / fp / fn per performance,
mode, window, level, type) and ``summary.csv`` (pooled precision / recall / F1).
"""

from __future__ import annotations

import argparse
import logging
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("eval_correctness")
WINDOWS = (0.05, 0.1)  # 0.1 = default WRONG_PITCH_WINDOW_SEC (F-02b); 0.05 = old default
_STATE: dict = {}


def _init(root: str) -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import asap
    from pianolens.data.perturb import load_mistake_set

    index, get = load_mistake_set(root)
    _STATE["get"] = get
    _STATE["index"] = index.set_index("key")
    _STATE["asap"] = asap.asap_index().set_index("performance_id", drop=False)


def _prf_counts(pred: set, gt: set, ignore: set) -> tuple[int, int, int]:
    tp = len(pred & gt)
    fp = len(pred - gt - ignore)
    fn = len(gt - pred)
    return tp, fp, fn


def score_one(res, lab) -> list[dict]:
    """tp / fp / fn rows for one correctness result against the ground-truth labels."""
    gn = lab.notes
    inj = gn[gn["injected"]]
    nat = gn[~gn["injected"]]
    g_wrong = set(inj.loc[inj["label"] == "wrong_pitch", "performance_id"])
    g_extra = set(inj.loc[inj["label"] == "extra", "performance_id"])
    g_missed = set(lab.missed.loc[lab.missed["injected"], "score_id"])
    nat_extra = set(nat.loc[nat["label"] == "extra", "performance_id"])
    nat_missed = set(lab.missed.loc[~lab.missed["injected"], "score_id"])

    pn, sn = res.notes, res.score_notes
    p_wrong = set(pn.loc[pn["label"] == "wrong_pitch", "performance_id"])
    p_extra = set(pn.loc[pn["label"] == "extra", "performance_id"])
    p_missed = set(sn.loc[sn["label"] == "missed", "score_id"])
    # wrong pitch predictions that sit on natural ins+del pairs are don't care
    p_wrong_nat = set(pn.loc[pn["label"] == "wrong_pitch"].query(
        "performance_id in @nat_extra")["performance_id"])  # fmt: skip

    rows = []
    for typ, pred, gt, ign in (
        ("wrong_pitch", p_wrong, g_wrong, p_wrong_nat),
        ("wrong_pitch_lenient", p_wrong | p_extra, g_wrong, nat_extra | g_extra),
        ("extra", p_extra, g_extra, nat_extra),
        ("missed", p_missed, g_missed, nat_missed),
    ):
        rows.append(("note", typ, *_prf_counts(pred, gt, ign)))

    # bar level
    s_bar = dict(zip(sn["score_id"], sn["measure_index"], strict=True))
    p_bar = dict(zip(pn["performance_id"], pn["measure_index"], strict=True))
    gn_sid = dict(zip(gn["performance_id"], gn["score_id"], strict=True))

    def bars_of_score(ids):
        return {s_bar[i] for i in ids if s_bar.get(i, -1) >= 0}

    def bars_of_perf(ids):
        return {p_bar[i] for i in ids if p_bar.get(i, -1) >= 0}

    g_bars = {
        "wrong_pitch": bars_of_score(gn_sid[i] for i in g_wrong),
        "extra": bars_of_score(gn_sid.get(a, "") for a in
                               inj.loc[inj["label"] == "extra", "anchor_id"]),  # fmt: skip
        "missed": bars_of_score(g_missed),
    }
    nat_bars = {"extra": bars_of_perf(nat_extra), "missed": bars_of_score(nat_missed)}
    nat_bars["wrong_pitch"] = nat_bars["extra"] | nat_bars["missed"]
    p_bars = {
        "wrong_pitch": bars_of_perf(p_wrong),
        "extra": bars_of_perf(p_extra),
        "missed": bars_of_score(p_missed),
    }
    for typ in ("wrong_pitch", "extra", "missed"):
        rows.append(("bar", typ, *_prf_counts(p_bars[typ], g_bars[typ], nat_bars[typ])))
    g_any = set().union(*g_bars.values())
    p_any = set().union(*p_bars.values())
    n_any = set().union(*nat_bars.values())
    rows.append(("bar", "any", *_prf_counts(p_any, g_any, n_any)))
    n_units = {"note": len(pn), "bar": len(res.bars)}
    return [
        {"level": lv, "type": t, "tp": tp, "fp": fp, "fn": fn, "n_units": n_units[lv],
         "n_bars_dont_care": len(nat_bars.get(t, n_any)) if lv == "bar" else 0}
        for lv, t, tp, fp, fn in rows
    ]  # fmt: skip


def run_one(key: str) -> list[dict]:
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.types import AlignedPerformance
    from pianolens.features.correctness import correctness

    warnings.filterwarnings("ignore")
    perf, lab = _STATE["get"](key)
    r = _STATE["index"].loc[key]
    row = _STATE["asap"].loc[r["performance_id"]]
    score = asap.load_asap_score(row)
    t0 = time.perf_counter()
    ap = align_performance(score, perf)
    t_align = time.perf_counter() - t0
    out = []
    modes = {"aligned": ap, "gt_alignment": AlignedPerformance(perf, ap.score, lab.alignment)}
    for mode, a in modes.items():
        for w in WINDOWS:
            res = correctness(a, wrong_pitch_window_sec=w)
            for d in score_one(res, lab):
                d.update(key=key, rate=float(r["rate"]), composer=r["composer"], mode=mode,
                         window=w, align_s=t_align,
                         match_ratio=res.summary["match_ratio"])  # fmt: skip
                out.append(d)
    return out


def prf(g: pd.DataFrame) -> pd.Series:
    tp, fp, fn = g["tp"].sum(), g["fp"].sum(), g["fn"].sum()
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if p + r else np.nan
    return pd.Series({"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn,
                      "n_units": g["n_units"].sum()})  # fmt: skip


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="data/processed/mistakes_v1")
    ap.add_argument("--out", type=Path, default=Path("data/interim/correctness_eval"))
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0, help="first N source performances only")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    index = pd.read_csv(Path(a.root) / "index.csv", keep_default_na=False)
    if a.limit:
        keep = index["performance_id"].drop_duplicates().iloc[: a.limit]
        index = index[index["performance_id"].isin(keep)]
    rows, failed = [], []
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(a.root,)) as ex:
        futs = {ex.submit(run_one, k): k for k in index["key"]}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                rows.extend(f.result())
            except Exception as e:  # noqa: BLE001 - count and continue
                failed.append((futs[f], repr(e)))
            if n % 50 == 0:
                log.info("%d / %d", n, len(futs))
    a.out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out / "counts.csv", index=False)
    log.info("failed: %d %s", len(failed), failed[:5])
    summ = (df.groupby(["mode", "window", "level", "type", "rate"])
            .apply(prf, include_groups=False).reset_index())  # fmt: skip
    summ.to_csv(a.out / "summary.csv", index=False)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 500)
    log.info("%s", summ.round(3).to_string())
    per_perf = df[(df["mode"] == "aligned") & (df["window"] == 0.1)].drop_duplicates("key")
    log.info("align time median %.1f s, max %.1f s; match ratio median %.3f",
             per_perf["align_s"].median(), per_perf["align_s"].max(),
             per_perf["match_ratio"].median())  # fmt: skip


if __name__ == "__main__":
    main()
