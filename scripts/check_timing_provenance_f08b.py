"""F-08b: are timing flags a reference-provenance artefact? Disklavier vs transcribed targets.

    uv run python scripts/check_timing_provenance_f08b.py [--workers 10] [--n-ref-targets 20]

Uses D-10's same-performance pairs (``data/interim/skill_control_d10/transcription_pairs.csv``,
built by ``scripts/check_transcription_noise_d10.py``): one ASAP Disklavier MIDI and a
transcription of the same recording (Aria-AMT or Transkun). Each version is aligned to the
ASAP score with ``align_performance`` and scored exactly as the practice report does
(``pianolens.report.build``: tier D tempo bar flags from ``interpret`` at the 95th / 99th
percentile, and the report's timing-noise bar tiers) against the same PianoCoRe references,
with *both* versions of the performance left out of the references.

Baselines on the same reference sets (reference as target, leave-one-out, PianoCoRe curves,
no re-alignment): up to ``--n-ref-targets`` random transcribed references per piece, and every
Disklavier reference (PianoCoRe's ASAP copies) of the piece.

Writes to ``data/interim/timing_provenance_f08b/``:
``bars.parquet`` (one row per target and bar: tiers and value / threshold ratios),
``targets.csv`` (per target) and ``summary.json``.
"""

from __future__ import annotations

import argparse
import json
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "interim" / "timing_provenance_f08b"
PAIRS = ROOT / "data" / "interim" / "skill_control_d10" / "transcription_pairs.csv"


def _stem(p: str) -> str:
    return p.split("/")[-1].removesuffix(".mid")


def score_target(target, refs, bmap, cfg, n_bars: int, extra: dict) -> pd.DataFrame:
    """The report's tier D tempo tiers and timing-noise tiers for one target, per bar."""
    from pianolens.report import calibration as cal
    from pianolens.report.build import (
        ReportInputs,
        _bar_of,
        _interpretation_section,
        _tier,
        _timing_matrix,
        timing_noise_bars,
    )

    inp = ReportInputs(ap=None)
    it = _interpretation_section(inp, target, refs, bmap, cfg, n_bars)
    tb = it["bars"]["tempo"]
    tbar = _bar_of(target.pos_grid, target.bar_starts)
    X = _timing_matrix(refs.exclude([target.performance_id, target.source_id]), target, bmap)
    tdf, tsum = timing_noise_bars(target.timing, X, tbar, n_bars,
                                  cfg.interpretation.min_refs_timing, cal.MIN_TIER_REFERENCES)
    rows = pd.DataFrame({
        "measure_index": np.arange(n_bars),
        "tempo_dev_rms": tb["dev_rms"].to_numpy(float), "tempo_q95": tb["q95"].to_numpy(float),
        "tempo_q99": tb["q99"].to_numpy(float), "tempo_tier": tb["tier"].to_numpy(),
        "timing_noise": tdf["noise_rms_beats"].to_numpy(float),
        "timing_q95": tdf["ref_q95"].to_numpy(float), "timing_q99": tdf["ref_q99"].to_numpy(float),
        "timing_n_refs": tdf["n_refs"].to_numpy(int),
    })  # fmt: skip
    rows["timing_tier"] = [_tier(v, a, b) for v, a, b in zip(
        rows["timing_noise"], rows["timing_q95"], rows["timing_q99"], strict=True)]
    for k, v in extra.items():
        rows[k] = v
    rows["timing_noise_rms_beats_all"] = tsum.get("noise_rms_beats", np.nan)
    rows["timing_consensus_r2"] = tsum.get("consensus_r2", np.nan)
    rows["n_refs_used"] = it["meta"].get("n_references")
    return rows


def run_pair(p: dict) -> pd.DataFrame:
    warnings.filterwarnings("ignore")
    import logging
    import tempfile
    import zipfile

    logging.disable(logging.WARNING)
    from pianolens.align import align_performance
    from pianolens.data.asap import asap_index, load_asap_performance, load_asap_score
    from pianolens.data.midi_io import performance_from_midi
    from pianolens.features.interpretation import (
        load_pianocore_references,
        map_score_beats,
        target_from_aligned,
    )
    from pianolens.report.build import ReportConfig, bar_labels

    cfg = ReportConfig(shaping=False)
    idx = asap_index().set_index("performance_id")
    row = idx.loc[p["asap_performance_id"]].copy()
    row["performance_id"] = p["asap_performance_id"]
    asap_src, trans_src = _stem(p["asap_path"]), _stem(p["trans_path"])
    refs = load_pianocore_references(p["piece_id"], exclude=[asap_src, trans_src],
                                     config=cfg.interpretation)
    if len(refs) < cfg.interpretation.min_references:
        raise RuntimeError(f"only {len(refs)} references")
    score = load_asap_score(row)
    disk = load_asap_performance(row)
    rz = ROOT / "data" / "raw" / "pianocore" / "PianoCoRe-1.0-raw-midi.zip"
    with zipfile.ZipFile(rz) as z, tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.mid"
        f.write_bytes(z.read("PianoCoRe/raw/" + p["trans_path"]))
        trans = performance_from_midi(f, dataset="pianocore", performance_id=f"trans:{trans_src}",
                                      piece_id=row["piece_id"], performer_id=row["performer_id"],
                                      provenance="transcribed")  # fmt: skip
    out = []
    for tag, perf, src in (("disklavier", disk, asap_src), ("transcribed", trans, trans_src)):
        ap = align_performance(score, perf)
        target = target_from_aligned(ap, cfg.interpretation, source_id=src)
        target.provenance = tag
        bmap = map_score_beats(target.score_notes, refs.score_notes)
        nb = len(bar_labels(ap.score))
        out.append(score_target(target, refs, bmap, cfg, nb, {
            "kind": "pair", "version": tag, "pair_id": asap_src + "|" + trans_src,
            "piece_id": p["piece_id"], "capture_model": p["capture_model"],
            "target_id": src, "n_refs_total": len(refs),
            "n_refs_disklavier": int((refs.provenance == "disklavier").sum()),
            "beat_map_mapped_fraction": float(bmap.mapped_fraction),
        }))
    return pd.concat(out, ignore_index=True)


def run_ref_targets(piece_id: str, n_trans: int, exclude: list[str]) -> pd.DataFrame:
    """Reference-as-target baseline: transcribed (random subset) and every Disklavier ref."""
    warnings.filterwarnings("ignore")
    from pianolens.features.interpretation import load_pianocore_references, target_from_references
    from pianolens.report.build import ReportConfig

    cfg = ReportConfig(shaping=False)
    refs = load_pianocore_references(piece_id, exclude=exclude, config=cfg.interpretation)
    prov = refs.provenance.astype(str)
    rng = np.random.default_rng(0)
    tr = np.flatnonzero(prov == "transcribed")
    pick = list(rng.choice(tr, min(n_trans, len(tr)), replace=False)) + \
        list(np.flatnonzero(prov == "disklavier"))
    nb = len(refs.bar_starts)
    out = []
    for i in pick:
        pid = str(refs.performance_ids[i])
        t, rest = target_from_references(refs, pid)
        if len(rest) < cfg.interpretation.min_references:
            continue
        out.append(score_target(t, refs, None, cfg, nb, {
            "kind": "ref", "version": prov[i], "pair_id": "", "piece_id": piece_id,
            "capture_model": "", "target_id": str(refs.source_ids[i]),
            "n_refs_total": len(refs) - 1,
            "n_refs_disklavier": int((prov == "disklavier").sum() - (prov[i] == "disklavier")),
            "beat_map_mapped_fraction": 1.0,
        }))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def rates(b: pd.DataFrame) -> dict:
    """Bar flag rates (share of tier-defined bars) for tempo (tier D) and timing (tier B)."""
    out = {}
    for ch in ("tempo", "timing"):
        d = b[np.isfinite(b[f"{ch}_q95"])]
        out[f"{ch}_n_bars"] = len(d)
        out[f"{ch}_notable_plus"] = float(d[f"{ch}_tier"].ne("none").mean()) if len(d) else np.nan
        out[f"{ch}_strong"] = float(d[f"{ch}_tier"].eq("strong").mean()) if len(d) else np.nan
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    a = argparse.ArgumentParser()
    a.add_argument("--workers", type=int, default=10)
    a.add_argument("--n-ref-targets", type=int, default=20)
    a.add_argument("--summarize-only", action="store_true")
    args = a.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.summarize_only:
        pr = pd.read_csv(PAIRS)
        pr = pr[~pr["piece_id"].str.startswith("asap:")]  # no canonical id -> no PianoCoRe refs
        frames, fails = [], []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(run_pair, p): ("pair", p["asap_path"])
                    for p in pr.to_dict("records")}
            # baselines exclude every paired source of the piece (same as the pair runs)
            for pid, g in pr.groupby("piece_id"):
                excl = sorted({_stem(x) for x in g["asap_path"]} | {_stem(x) for x in
                                                                    g["trans_path"]})
                futs[ex.submit(run_ref_targets, pid, args.n_ref_targets, excl)] = ("ref", pid)
            for f in as_completed(futs):
                try:
                    frames.append(f.result())
                except Exception as e:  # noqa: BLE001
                    fails.append({"job": futs[f][0], "id": futs[f][1], "error": repr(e)})
                    print("FAIL", futs[f], repr(e)[:200])
        bars = pd.concat([f for f in frames if len(f)], ignore_index=True)
        bars.to_parquet(OUT / "bars.parquet")
        pd.DataFrame(fails).to_csv(OUT / "failures.csv", index=False)
    bars = pd.read_parquet(OUT / "bars.parquet")
    tg = bars.groupby(["kind", "version", "piece_id", "target_id", "pair_id"],
                      dropna=False).apply(lambda d: pd.Series(rates(d))).reset_index()
    tg.to_csv(OUT / "targets.csv", index=False)
    summ = {}
    paired = set(bars.loc[bars["kind"] == "pair", "pair_id"])
    for (k, v), d in bars.groupby(["kind", "version"]):
        summ[f"{k}:{v}"] = {**rates(d), "n_targets": int(d["target_id"].nunique()),
                            "n_pieces": int(d["piece_id"].nunique())}
    # paired difference per pair (Disklavier minus transcribed), bar-weighted per target
    pt = tg[tg["kind"] == "pair"].pivot_table(index="pair_id", columns="version",
                                              values=["tempo_notable_plus", "tempo_strong",
                                                      "timing_notable_plus", "timing_strong"])
    for m in ("tempo_notable_plus", "tempo_strong", "timing_notable_plus", "timing_strong"):
        dlt = (pt[(m, "disklavier")] - pt[(m, "transcribed")]).dropna()
        rng = np.random.default_rng(0)
        boots = [rng.choice(dlt.to_numpy(), len(dlt)).mean() for _ in range(2000)]
        summ[f"paired_diff_{m}"] = {
            "n_pairs": len(dlt), "mean": float(dlt.mean()), "median": float(dlt.median()),
            "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))],
            "share_disk_higher": float((dlt > 0).mean()),
        }
    summ["n_pairs_scored"] = len(paired)
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
