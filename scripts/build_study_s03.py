"""Build the S-03 listening stimuli: excerpts x dimensions x levels, one fixed piano (S-02).

Reads ``study/stimuli-S03.json`` and writes, under ``data/interim/study_s03/``:

* ``audio/{det,pref}/<excerpt>_<dimension>_<levelcode>.wav`` (44.1 kHz mono PCM16,
  loudness-normalised to the spec's LUFS target after trimming), plus ``orig`` and ``catch``;
* ``midi/...`` the MIDI of every stimulus, for audit;
* ``manifest.json`` and ``manifest.js`` (the same data as ``window.S03_MANIFEST`` so the app
  can load it from ``file://``).

Every stimulus is degraded *after* the excerpt is cut (so the dose is exact within the clip):
``degrade(excerpt(original, bars))``. The detection span and the preference span are built
separately from the original.

Usage:
    uv run python scripts/build_study_s03.py                  # pilot ladders, all excerpts
    uv run python scripts/build_study_s03.py --probe          # bar timings only, no audio
    uv run python scripts/build_study_s03.py --excerpts E3 --dims voicing --workers 4
    uv run python scripts/build_study_s03.py --ladder main    # after the pilot sets "main"
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import math
import subprocess
import time
import warnings
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "study" / "stimuli-S03.json"
OUT = REPO / "data" / "interim" / "study_s03"

log = logging.getLogger("build_study_s03")


# --------------------------------------------------------------------------- sources


def _median_tempo(aps: list) -> Any:
    from pianolens.features.tempo import tempo_model

    tempos = [tempo_model(a).summary["tempo_bpm_overall"] for a in aps]
    order = np.argsort(tempos, kind="stable")
    return aps[order[(len(order) - 1) // 2]]


def load_source(ex: dict[str, Any]) -> Any:
    """The AlignedPerformance an excerpt spec points to (with the selection rule applied)."""
    from pianolens.data.types import AlignedPerformance

    src, piece = ex["source"], ex["piece"]
    if src == "vienna4x22":
        from pianolens.data import vienna4x22

        aps = [a for a in vienna4x22.iter_aligned() if a.score.score_id == piece]
    elif src == "batik_mozart":
        from pianolens.data import batik_mozart

        aps = [batik_mozart.load_aligned(piece)]
    elif src == "asap":
        from pianolens.data import asap

        idx = asap.asap_index()
        rows = idx[(idx["folder"] == piece) & idx["maestro_midi_performance"].notna()
                   & (idx["robust_note_alignment"] == 1)]  # fmt: skip
        aps = [AlignedPerformance(asap.load_asap_performance(r), asap.load_asap_score(r),
                                  asap.load_asap_alignment(r)) for _, r in rows.iterrows()]
    else:
        raise ValueError(f"unknown source {src}")
    if not aps:
        raise RuntimeError(f"no performances for {src}:{piece}")
    if ex["performance"] == "median_tempo" and len(aps) > 1:
        return _median_tempo(aps)
    return aps[0]


# --------------------------------------------------------------------------- stimuli


def level_code(level: float) -> str:
    s = f"{level:g}".replace("-", "m").replace(".", "p")
    return f"L{s}"


def analysis_x(dim_spec: dict[str, Any], level: float, phys: dict[str, float]) -> float:
    """The analysis level of a stimulus (see the spec's comment)."""
    kind = dim_spec["x"]
    if kind.startswith("phys:"):
        v = phys.get(kind[5:])
        return float(v) if v is not None else float("nan")
    if kind == "rubato_removed_log":
        return float(phys["tempo_log_sd_before"] - phys["tempo_log_sd_after"])
    if kind == "log2_inverse_level":
        return float(math.log2(1.0 / level))
    if kind == "level":
        return float(level)
    raise ValueError(kind)


def changed(base: Any, perf: Any) -> bool:
    """True if the degraded performance differs from the undegraded excerpt at all."""
    a, b = base.notes, perf.notes
    if len(a) != len(b) or len(base.pedal) != len(perf.pedal):
        return True
    ka, kb = np.argsort(a["id"].astype(str)), np.argsort(b["id"].astype(str))
    for f in ("onset_sec", "duration_sec", "pitch", "velocity"):
        if not np.allclose(a[f][ka].astype(float), b[f][kb].astype(float), atol=1e-6):
            return True
    pa, pb = np.sort(base.pedal, order="time_sec"), np.sort(perf.pedal, order="time_sec")
    return not (np.allclose(pa["time_sec"], pb["time_sec"], atol=1e-6)
                and np.array_equal(pa["value"], pb["value"]))


def solve_level(base: Any, dim: str, ds: dict[str, Any], target: float, lo: float, hi: float,
                seed: int, iters: int = 14) -> tuple[float, Any]:
    """Control level whose analysis x is closest to ``target`` (bisection; x must grow from
    ``lo`` to ``hi``). Returns (level, DegradeResult)."""
    from pianolens.study import degrade

    def run(level: float) -> tuple[float, Any]:
        r = degrade(base, dim, level, seed=seed, **ds.get("options", {}))
        return analysis_x(ds, level, r.physical), r

    best: tuple[float, float, Any] | None = None
    a, b = lo, hi
    for _ in range(iters):
        mid = 0.5 * (a + b)
        x, r = run(mid)
        if math.isfinite(x) and (best is None or abs(x - target) < best[0]):
            best = (abs(x - target), mid, r)
        if not math.isfinite(x) or x < target:
            a = mid
        else:
            b = mid
    x, r = run(hi)
    if math.isfinite(x) and (best is None or abs(x - target) < best[0]):
        best = (abs(x - target), hi, r)
    if best is None:
        raise RuntimeError(f"{dim}: no finite x in [{lo}, {hi}]")
    return best[1], best[2]


def _seed(base: int, *parts: object) -> int:
    return (base + zlib.crc32("|".join(map(str, parts)).encode())) % (2**31)


def _render(perf: Any, wav: Path, midi: Path, rcfg: dict[str, Any]) -> dict[str, float]:
    import pyloudnorm as pyln
    import soundfile as sf

    from pianolens.audio.render import RenderConfig, performance_to_midi, render_midi

    cfg = RenderConfig(sample_rate=int(rcfg["sample_rate"]))
    performance_to_midi(perf, midi)
    res = render_midi(midi, cfg)
    sr = res.sample_rate
    ex = perf.meta.get("excerpt", {})
    dur = float(ex.get("duration_sec", perf.duration_sec)) + float(rcfg["release_sec"]) \
        + float(rcfg["tail_sec"])
    y = res.audio[: int(round(dur * sr))].astype(np.float64)
    n_out, n_in = int(rcfg["fade_out_sec"] * sr), max(1, int(rcfg["fade_in_sec"] * sr))
    y[:n_in] *= np.linspace(0, 1, n_in)
    if n_out and len(y) > n_out:
        y[-n_out:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, n_out)))
    loud = pyln.Meter(sr).integrated_loudness(y)
    gain_db = float(rcfg["target_lufs"] - loud) if np.isfinite(loud) else 0.0
    y = y * 10 ** (gain_db / 20)
    peak = float(np.max(np.abs(y)))
    wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(wav), y.astype(np.float32), sr, subtype="PCM_16")
    return {"duration_sec": len(y) / sr, "lufs_before": float(loud), "gain_db": gain_db,
            "peak": peak, "clipped": bool(peak >= 1.0),
            "config_hash": cfg.config_hash()}  # fmt: skip


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.floating, np.integer)):
            v = v.item()
        if isinstance(v, float) and not math.isfinite(v):
            v = None
        out[k] = v
    return out


def build_excerpt(ex: dict[str, Any], spec: dict[str, Any], dims: list[str] | None,
                  probe: bool, ladder: str = "pilot") -> list[dict[str, Any]]:
    """All stimuli of one excerpt (both spans). Runs in a worker process."""
    warnings.filterwarnings("ignore")
    from pianolens.study import degrade, excerpt

    rcfg = spec["render"]
    ap = load_source(ex)
    rows: list[dict[str, Any]] = []
    src_id = ap.performance.performance_id
    for span in ("det", "pref"):
        b0, b1 = ex[f"{span}_bars"]
        base = excerpt(ap, b0, b1, lead_in_sec=rcfg["lead_in_sec"],
                       release_sec=rcfg["release_sec"])  # fmt: skip
        dur = base.performance.meta["excerpt"]["duration_sec"]
        if probe:
            rows.append({"excerpt": ex["id"], "span": span, "bars": [b0, b1],
                         "duration_sec": dur, "n_notes": len(base.performance.notes),
                         "source_performance": src_id})  # fmt: skip
            continue
        jobs: list[tuple[str, float | None, dict[str, Any], float | None]] = [
            ("original", None, {}, None)]
        for dim, ds in spec["dimensions"].items():
            if dims and dim not in dims:
                continue
            if ladder == "pilot":
                jobs += [(dim, lv, ds, None) for lv in ds["pilot_levels"]]
            else:
                jobs += [(dim, None, ds, float(t)) for t in spec["main"][dim][span]]
        jobs.append(("catch", spec["catch"]["level"], spec["dimensions"]["wrong_notes"], None))
        for dim, lv, ds, target in jobs:
            seed = _seed(spec["seed"], ex["id"], span, dim, lv if target is None else target)
            control = lv
            if dim == "original":
                perf, phys, ref, x, code = base.performance, {}, {}, 0.0, "orig"
                name = "none"
            else:
                real = "wrong_notes" if dim == "catch" else dim
                if target is None:
                    r = degrade(base, real, float(lv), seed=seed, **ds.get("options", {}))
                else:
                    lo, hi = spec["control_range"][dim]
                    control, r = solve_level(base, real, ds, target, lo, hi, seed)
                perf, phys, ref = r.performance, r.physical, r.summary()
                x = analysis_x(ds, float(control), phys)
                # the design groups trials by `level`: the control value for pilot ladders,
                # the x target for main ladders
                lv = float(control) if target is None else target
                code = "catch" if dim == "catch" else level_code(lv)
                name = r.level_name if target is None else "x_target"
                # keep the excerpt meta for rendering length
                perf.meta.setdefault("excerpt", base.performance.meta["excerpt"])
            stem = f"{ex['id']}_{dim}_{code}" if dim != "original" else f"{ex['id']}_orig"
            wav = OUT / "audio" / span / f"{stem}.wav"
            midi = OUT / "midi" / span / f"{stem}.mid"
            info = _render(perf, wav, midi, rcfg)
            rows.append({
                "id": f"{span}/{stem}", "file": f"audio/{span}/{stem}.wav", "span": span,
                "excerpt": ex["id"], "dimension": dim, "level_name": name,
                "level": None if lv is None else float(lv),
                "control_level": None if control is None else float(control),
                "x": x if math.isfinite(x) else None, "seed": seed,
                "changed": dim == "original" or changed(base.performance, perf),
                "bars": [b0, b1], "source_performance": src_id,
                **_jsonable(info),
                "physical": _jsonable(phys),
                "ratios": _jsonable({k: v for k, v in ref.items() if k.startswith("ratio")}),
            })  # fmt: skip
    return rows


def _git_state() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
        return out or "uncommitted"
    except Exception:  # noqa: BLE001 - not a git repo
        files = sorted((REPO / "src" / "pianolens" / "study").glob("*.py")) + [Path(__file__)]
        h = hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()[:12]
        return f"uncommitted:{h}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, default=SPEC)
    ap.add_argument("--excerpts", nargs="*")
    ap.add_argument("--dims", nargs="*")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--ladder", choices=["pilot", "main"], default="pilot",
                    help="pilot: the spec's pilot_levels; main: the spec's x targets")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    spec = json.loads(args.spec.read_text())
    if args.ladder == "main" and not spec.get("main"):
        raise SystemExit("spec has no 'main' ladder yet: it is set after the pilot (protocol 8)")
    exs = [e for e in spec["excerpts"] if not args.excerpts or e["id"] in args.excerpts]
    t0 = time.time()
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(build_excerpt, e, spec, args.dims, args.probe, args.ladder)
                for e in exs]
        for e, f in zip(exs, futs, strict=True):
            r = f.result()
            rows += r
            log.info("%s: %d rows (%.0f s)", e["id"], len(r), time.time() - t0)
    if args.probe:
        for r in rows:
            print(r)
        return

    from pianolens.audio.render import SOUNDFONT_SHA256, RenderConfig, fluidsynth_version

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "study": "S-03", "spec_version": spec["spec_version"], "ladder": args.ladder,
        "built": time.strftime("%Y-%m-%d"),
        "code_state": _git_state(), "fluidsynth": fluidsynth_version(),
        "soundfont_sha256": SOUNDFONT_SHA256,
        "render_config": dataclasses.asdict(RenderConfig(
            sample_rate=int(spec["render"]["sample_rate"]))),
        "render": spec["render"], "dimensions": spec["dimensions"], "catch": spec["catch"],
        "excerpts": [{"id": e["id"], "det_bars": e["det_bars"], "pref_bars": e["pref_bars"]}
                     for e in exs],
        "stimuli": rows, "build_seconds": round(time.time() - t0, 1),
    }  # fmt: skip
    manifest["render_config"]["soundfont"] = Path(manifest["render_config"]["soundfont"]).name
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (OUT / "manifest.js").write_text("window.S03_MANIFEST = " + json.dumps(manifest) + ";\n")
    peaks = [r["peak"] for r in rows]
    log.info("%d stimuli, max peak %.3f, clipped %d, %.0f s -> %s", len(rows), max(peaks),
             sum(r["clipped"] for r in rows), time.time() - t0, OUT)


if __name__ == "__main__":
    main()
