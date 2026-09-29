"""Results-page data: the report's practise items joined to the comparison clips by bar overlap.

Reads only the job's ``report.json`` (``pianolens.report/1``) and ``compare/manifest.json``
(``pianolens.compare/1``). Clips are referenced by URL (``/jobs/<id>/clips/<file>``), never
embedded. Each passage also carries the tempo and velocity curves of the report
(``interpretation.curves``: the target against the expert band) over its bars plus one bar either
side.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["best_window", "results_data", "trust_notes", "window_curves"]

_CLIP_KEEP = ("label", "duration_sec", "window_on", "window_off", "bar_times", "performer",
              "source_dataset", "capture_model", "distance_percentile")  # fmt: skip


def best_window(bars: list[int], windows: list[dict[str, Any]]) -> str | None:
    """Id of the window sharing the most bars with ``bars`` (first on ties), or None."""
    best, n_best = None, 0
    s = set(bars)
    for w in windows:
        n = len(s & set(w.get("bars", [])))
        if n > n_best:
            best, n_best = w["id"], n
    return best


def window_curves(rep: dict[str, Any], bars: list[int], pad: int = 1) -> dict[str, Any]:
    """Per block (tempo, velocity): the curve points of bars ``min-pad .. max+pad``."""
    out: dict[str, Any] = {}
    curves = (rep.get("interpretation") or {}).get("curves") or {}
    if not bars:
        return out
    lo_b, hi_b = min(bars) - pad, max(bars) + pad
    inside = set(bars)
    for block, c in curves.items():
        mi = c.get("measure_index") or []
        idx = [i for i, m in enumerate(mi) if m is not None and lo_b <= m <= hi_b]
        if len(idx) < 2:
            continue

        def pick(key: str, idx: list[int] = idx, c: dict[str, Any] = c) -> list[Any]:
            v = c.get(key) or []
            return [v[i] if i < len(v) else None for i in idx]

        out[block] = {"beat": pick("beat"), "target": pick("target"), "lo": pick("lo"),
                      "mid": pick("mid"), "hi": pick("hi"), "unit": c.get("unit", ""),
                      "flagged": [mi[i] in inside for i in idx],
                      "bar": [mi[i] for i in idx]}  # fmt: skip
    return out


def trust_notes(rep: dict[str, Any], input_kind: str) -> list[dict[str, str]]:
    """What the input supports, per measure (shown above the results)."""
    conf = rep.get("confidence") or {}
    if input_kind == "audio":
        return [
            {"what": "Timing and tempo", "level": "trust",
             "why": "Onsets from the transcription are accurate enough on phone audio (A-01)."},
            {"what": "Wrong and missed notes", "level": "check",
             "why": "Read against expert recordings transcribed the same way; bars where experts "
                    "also show errors are not ranked."},
            {"what": "Extra notes", "level": "low",
             "why": "Phone and room audio produce spurious high notes; never a practise item."},
            {"what": "Dynamics, voicing, pedal", "level": "low",
             "why": "Velocity and pedal from audio are relative and uncalibrated; shown, not "
                    "ranked."},
        ]  # fmt: skip
    vel = conf.get("velocity", "low")
    return [
        {"what": "Notes, timing and tempo", "level": "trust",
         "why": "Read directly from the MIDI."},
        {"what": "Dynamics and voicing", "level": "trust" if vel == "high" else "low",
         "why": "Velocity confidence in this report: " + str(vel) + "."},
        {"what": "Control and shaping measures", "level": "check",
         "why": "They describe the playing against experts; not yet validated as skill "
                "measures (D-10)."},
    ]  # fmt: skip


def results_data(job_dir: Path | str, job_id: str) -> dict[str, Any]:
    job_dir = Path(job_dir)
    rep = json.loads((job_dir / "report.json").read_text())
    job = json.loads((job_dir / "job.json").read_text())
    mf = job_dir / "compare" / "manifest.json"
    man = json.loads(mf.read_text()) if mf.is_file() else {"windows": []}
    windows = []
    for w in man.get("windows", []):
        clips = {}
        for kind, c in (w.get("clips") or {}).items():
            clips[kind] = {k: c.get(k) for k in _CLIP_KEEP if c.get(k) is not None}
            clips[kind]["url"] = f"/jobs/{job_id}/clips/{Path(c['path']).name}"
        if not clips:
            continue
        windows.append({"id": w["id"], "label": w.get("bars_label", ""), "tier": w.get("tier"),
                        "bars": w.get("bars", []), "truncated": w.get("truncated", False),
                        "reasons": [r.get("text") or f"{r.get('category')} / {r.get('channel')}"
                                    for r in w.get("reasons", [])],
                        "clips": clips, "curves": window_curves(rep, w.get("bars", []))})
    practise = []
    for d in rep.get("practise", []):
        practise.append({"text": d.get("text", ""), "tier": d.get("tier"),
                         "bars": d.get("bars", []), "bars_label": d.get("bars_label", ""),
                         "category": d.get("category"), "channel": d.get("channel"),
                         "window": best_window(d.get("bars", []), windows)})  # fmt: skip
    kind = job["spec"]["input_kind"]
    corr = rep.get("correctness") or {}
    return {
        "title": rep.get("piece", {}).get("title") or job["spec"].get("title"),
        "piece_id": rep.get("piece", {}).get("piece_id"),
        "input_kind": kind,
        "provenance": rep.get("input", {}).get("provenance"),
        "n_takes": len(job.get("takes", [])),
        "trust": trust_notes(rep, kind),
        "confidence_notes": (rep.get("confidence") or {}).get("notes", []),
        "facts": {"error_rate": corr.get("error_rate"),
                  "n_bars": rep.get("piece", {}).get("n_bars"),
                  "n_references": (rep.get("references") or {}).get("tier_d_total"),
                  "tempo_bpm": ((rep.get("interpretation") or {}).get("tempo_overall")
                                or {}).get("target_bpm")},
        "practise": practise,
        "windows": windows,
        "report_url": f"/jobs/{job_id}/report",
        "errors": rep.get("errors") or {},
    }
