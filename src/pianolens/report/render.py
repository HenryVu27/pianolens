"""Self-contained HTML for the practice report (F-08): inline SVG charts, inline CSS, no scripts
and no external requests; light and dark via ``prefers-color-scheme``.

Sections, in order: header (piece, input, confidence notes), summary cards, bar-by-bar
timeline, charts (tempo and loudness against the expert 10-50-90 band, evenness per run
against note rate), "What to practise", methods and limitations.
"""

from __future__ import annotations

import html
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

from pianolens.report import calibration as cal
from pianolens.report import text

REPO = Path(__file__).resolve().parents[3]
SPECS = {
    "Alignment": "docs/specs/alignment-validation.md",
    "Correctness": "docs/specs/correctness-validation.md",
    "Control": "docs/specs/control-validation.md",
    "Phrases and coherence": "docs/specs/phrase-coherence-validation.md",
    "Skill vs context check (D-10)": "docs/specs/skill-control-check.md",
    "Literature and reference ranges": "docs/research/2026-09-27-landscape.md",
    "Decisions": "DECISIONS.md",
}

CSS = """
:root{--bg:#fbfaf8;--card:#ffffff;--ink:#1d2127;--ink2:#4b5563;--muted:#8a8f98;--line:#e4e2dd;
--grid:#eeece8;--band:#c9d6e8;--band-mid:#7c93b5;--target:#1f4e8c;--strong:#c2410c;
--notable:#f4c9a3;--neutral:#e9e7e2;--ok:#dbe7d3;--flat:#8b5cf6;--flat-l:#ddd2fb}
@media (prefers-color-scheme:dark){:root{--bg:#15171b;--card:#1d2026;--ink:#e8e6e1;--ink2:#b5b9c0;
--muted:#838892;--line:#2d3139;--grid:#262a31;--band:#2c3b52;--band-mid:#6d86ab;--target:#8fb8f0;
--strong:#f08a4b;--notable:#6b4428;--neutral:#2a2e35;--ok:#2d3b2a;--flat:#b69cf7;--flat-l:#3f3366}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,
"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
main{max-width:1040px;margin:0 auto;padding:40px 24px 72px}
h1{font-size:26px;margin:0 0 4px;font-weight:650;letter-spacing:-.01em}
h2{font-size:18px;margin:44px 0 14px;font-weight:620}
h3{font-size:15px;margin:0 0 8px;font-weight:620}
.sub{color:var(--ink2);margin:0 0 18px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:6px 24px;
color:var(--ink2);font-size:13.5px;margin:0 0 16px}
.meta b{color:var(--ink);font-weight:560}
.notes{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;
font-size:13.5px;color:var(--ink2)}
.notes li{margin:4px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
.card ul{margin:0;padding-left:18px}.card li{margin:6px 0;font-size:14px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:16px 16px 10px;overflow-x:auto}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:var(--ink2);margin:8px 4px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:6px}
.practise{counter-reset:p;list-style:none;padding:0;margin:0}
.practise li{background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--notable);border-radius:10px;padding:14px 18px;margin:0 0 12px}
.practise li.strong{border-left-color:var(--strong)}
.tag{font-size:12px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em}
.caption{font-size:12.5px;color:var(--muted);margin:6px 4px 0}
footer{margin-top:48px;font-size:13px;color:var(--ink2)}
footer li{margin:4px 0}
a{color:var(--target)}
svg text{font-family:inherit}
table.takes{border-collapse:collapse;font-size:13px;margin-top:10px}
table.takes td,table.takes th{border-bottom:1px solid var(--line);padding:4px 10px;text-align:right}
"""


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _ok(x: Any) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _fmt(x: Any, nd: int = 1) -> str:
    return f"{float(x):.{nd}f}" if _ok(x) else "n/a"


# =========================================================================== timeline


def _notes_tip(b: dict, rep: dict) -> str:
    c = b["correctness"]
    low = not rep["correctness"].get("extras_counted", True)
    tip = (f"{c['n_wrong_pitch']} wrong, {c['n_missed']} missed, {c['n_extra']} extra"
           + (" (extra notes: low confidence)" if low and c["n_extra"] else ""))
    st = c.get("expert_check")
    if st == "suppressed":
        tip += f"; {text.artefact_text(rep)}"
    elif st == "down_tiered":
        tip += f"; experts also show errors here (was {c.get('tier_global')})"
    return tip


TIER_FILL = {"strong": "var(--strong)", "notable": "var(--notable)"}


def timeline_svg(rep: dict) -> str:
    """Rows = measures, columns = bars; strong cells solid, notable cells tinted."""
    bars = rep["bars"]
    n = len(bars)
    rows: list[tuple[str, Any]] = [
        ("Notes", lambda b: (b["correctness"]["tier"], b["correctness"]["n_errors"],
                             _notes_tip(b, rep))),
        ("Tempo vs experts", lambda b: (b["tempo"]["tier"], None, _dev_tip(b, "tempo"))),
        ("Loudness vs experts", lambda b: (b["velocity"]["tier"], None, _dev_tip(b, "velocity"))),
        ("Too flat (tempo)", lambda b: (b["too_flat"]["tempo"], None, "")),
        ("Too flat (loudness)", lambda b: (b["too_flat"]["velocity"], None, "")),
        ("Timing steadiness", lambda b: (b["timing"]["tier"], None,
                                         f"{_fmt(b['timing'].get('noise_rms_ms'), 0)} ms RMS")),
        ("Pedal blur", lambda b: (b["pedal"]["tier"],
                                  "p" if (b["pedal"]["blur_fraction"] or 0) > 0 else None,
                                  f"held through {_fmt(b['pedal']['blur_fraction'], 2)} of "
                                  f"{b['pedal']['n_harmony_changes']} changes")),
        ("Evenness (runs)", lambda b: (b["evenness"]["tier"],
                                       "e" if b["evenness"]["n_iois"] else None,
                                       f"CV {_fmt(b['evenness']['ioi_cv'], 3)} at "
                                       f"{_fmt(b['evenness']['note_rate_nps'])} notes/s")),
    ]
    if rep.get("takes"):
        rows.append(("Errors in takes", lambda b: (
            "strong" if b["correctness"].get("recurring") and rep["takes"].get("promoted")
            else "none",
            b.get("takes_with_errors") or None,
            f"flagged notes in {b.get('takes_with_errors', 0)} of {rep['takes']['n_takes']} "
            "takes" + ("; recurring: " + "; ".join(
                f"{r['text']} ({r['n_takes']} takes)" for r in b["correctness"]["recurring"])
                if b["correctness"].get("recurring") else ""))))
    lw, cw, rh, top = 150, max(9.0, min(22.0, 860 / max(n, 1))), 24, 28
    width = lw + cw * n + 10
    height = top + rh * len(rows) + 8
    out = [f'<svg viewBox="0 0 {width:.0f} {height}" width="{width:.0f}" height="{height}" '
           f'role="img" aria-label="Bar-by-bar timeline">']
    step = max(1, int(math.ceil(28 / cw)))
    for i, b in enumerate(bars):
        if i % step == 0:
            x = lw + cw * i + cw / 2
            out.append(f'<text x="{x:.1f}" y="{top - 10}" font-size="10.5" fill="var(--muted)" '
                       f'text-anchor="middle">{_e(b["label"])}</text>')
    for r, (name, fn) in enumerate(rows):
        y = top + rh * r
        out.append(f'<text x="0" y="{y + rh / 2 + 4:.1f}" font-size="12.5" '
                   f'fill="var(--ink2)">{_e(name)}</text>')
        for i, b in enumerate(bars):
            tier, mark, tip = fn(b)
            x = lw + cw * i
            fill = TIER_FILL.get(tier, "var(--neutral)")
            if name.startswith("Too flat") and tier != "none":
                fill = "var(--flat)" if tier == "strong" else "var(--flat-l)"
            out.append(f'<rect x="{x + 1:.1f}" y="{y + 3}" width="{cw - 2:.1f}" height="{rh - 6}" '
                       f'rx="2" fill="{fill}"><title>Bar {_e(b["label"])}: {_e(name)}: '
                       f'{_e(tier if tier != "none" else "in range / not tiered")}'
                       f'{"; " + _e(tip) if tip else ""}</title></rect>')
            if mark not in (None, 0):
                txt = str(mark) if isinstance(mark, int) else ""
                if txt and cw >= 11:
                    col = "#fff" if tier == "strong" else "var(--ink)"
                    out.append(f'<text x="{x + cw / 2:.1f}" y="{y + rh / 2 + 3.5:.1f}" '
                               f'font-size="9.5" text-anchor="middle" fill="{col}" '
                               f'pointer-events="none">{txt}</text>')
                elif not txt:
                    out.append(f'<circle cx="{x + cw / 2:.1f}" cy="{y + rh / 2:.1f}" r="1.8" '
                               f'fill="var(--muted)" pointer-events="none"/>')
    out.append("</svg>")
    return "".join(out)


def _dev_tip(b: dict, ch: str) -> str:
    d = b[ch]
    if not _ok(d.get("dev_rms")):
        return "no expert band"
    return f"deviation {_fmt(d['dev_rms'], 3)} (experts 95%: {_fmt(d.get('q95'), 3)})"


# =========================================================================== curves


def _path(xs: np.ndarray, ys: np.ndarray, sx, sy) -> str:
    parts, pen = [], False
    for x, y in zip(xs, ys, strict=True):
        if not (np.isfinite(x) and np.isfinite(y)):
            pen = False
            continue
        parts.append(f"{'L' if pen else 'M'}{sx(x):.1f},{sy(y):.1f}")
        pen = True
    return "".join(parts)


def _band(xs, lo, hi, sx, sy) -> str:
    """Polygons for each finite run of the band."""
    ok = np.isfinite(lo) & np.isfinite(hi) & np.isfinite(xs)
    out, i, n = [], 0, len(xs)
    while i < n:
        if not ok[i]:
            i += 1
            continue
        j = i
        while j < n and ok[j]:
            j += 1
        up = [f"{sx(xs[k]):.1f},{sy(hi[k]):.1f}" for k in range(i, j)]
        dn = [f"{sx(xs[k]):.1f},{sy(lo[k]):.1f}" for k in range(j - 1, i - 1, -1)]
        out.append(f'<polygon points="{" ".join(up + dn)}" fill="var(--band)"/>')
        i = j
    return "".join(out)


def curve_svg(rep: dict, block: str) -> str:
    """Target smooth curve against the expert 10-50-90 band, flagged bars shaded behind."""
    cv = (rep.get("interpretation") or {}).get("curves", {}).get(block)
    if not cv:
        return '<p class="caption">No expert band: no references for this piece.</p>'
    x = np.asarray(cv["beat"], float)
    t = np.asarray([np.nan if v is None else v for v in cv["target"]], float)
    lo = np.asarray([np.nan if v is None else v for v in cv["lo"]], float)
    mid = np.asarray([np.nan if v is None else v for v in cv["mid"]], float)
    hi = np.asarray([np.nan if v is None else v for v in cv["hi"]], float)
    W, H, L, R, T, B = 980, 250, 52, 12, 14, 30
    allv = np.concatenate([t, lo, hi])
    allv = allv[np.isfinite(allv)]
    if not len(allv) or not np.isfinite(x).any():
        return '<p class="caption">No curve.</p>'
    y0, y1 = float(np.quantile(allv, 0.005)), float(np.quantile(allv, 0.995))
    pad = 0.08 * (y1 - y0 or 1)
    y0, y1 = y0 - pad, y1 + pad
    x0, x1 = float(np.nanmin(x)), float(np.nanmax(x)) + 1

    def sx(v):
        return L + (v - x0) / (x1 - x0) * (W - L - R)

    def sy(v):
        return T + (1 - (min(max(v, y0), y1) - y0) / (y1 - y0)) * (H - T - B)

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'aria-label="{_e(block)} against the expert band">']
    # flagged bars behind
    bars = rep["bars"]
    starts = [b["start_beat"] for b in bars]
    for i, b in enumerate(bars):
        tier = b[block]["tier"]
        if tier == "none" or not _ok(starts[i]):
            continue
        a = starts[i]
        e = starts[i + 1] if i + 1 < len(starts) and _ok(starts[i + 1]) else a + \
            rep["piece"]["beats_per_bar"]
        op = "0.32" if tier == "strong" else "0.5"
        col = "var(--strong)" if tier == "strong" else "var(--notable)"
        out.append(f'<rect x="{sx(a):.1f}" y="{T}" width="{max(sx(e) - sx(a), 1):.1f}" '
                   f'height="{H - T - B}" fill="{col}" opacity="{op}">'
                   f'<title>Bar {_e(b["label"])}: {tier}</title></rect>')
    # grid + y ticks
    for k in range(5):
        v = y0 + (y1 - y0) * (k + 0.5) / 5
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" '
                   f'stroke="var(--grid)"/><text x="{L - 6}" y="{sy(v) + 4:.1f}" font-size="11" '
                   f'text-anchor="end" fill="var(--muted)">{v:.0f}</text>')
    # x ticks: bar labels
    step = max(1, int(math.ceil(len(bars) / 16)))
    for i, b in enumerate(bars):
        if i % step == 0 and _ok(starts[i]) and x0 <= starts[i] <= x1:
            out.append(f'<text x="{sx(starts[i]):.1f}" y="{H - 10}" font-size="11" '
                       f'text-anchor="middle" fill="var(--muted)">{_e(b["label"])}</text>')
    out.append(_band(x, lo, hi, sx, sy))
    out.append(f'<path d="{_path(x, mid, sx, sy)}" fill="none" stroke="var(--band-mid)" '
               f'stroke-width="1.5" stroke-dasharray="4 3"/>')
    out.append(f'<path d="{_path(x, t, sx, sy)}" fill="none" stroke="var(--target)" '
               f'stroke-width="2" stroke-linejoin="round"/>')
    out.append("</svg>")
    return "".join(out)


def evenness_svg(rep: dict) -> str:
    """IOI CV per strict run against note rate, with the literature reference ranges."""
    runs = [r for r in rep.get("evenness_runs", []) if _ok(r.get("ioi_cv"))
            and _ok(r.get("note_rate_nps"))]
    lit = rep.get("literature_evenness", [])
    if not runs:
        return '<p class="caption">No scale or figure passages with enough matched notes.</p>'
    W, H, L, R, T, B = 980, 280, 52, 150, 14, 36
    xs = [r["note_rate_nps"] for r in runs] + [e["note_rate_nps"] for e in lit]
    ys = [r["ioi_cv"] for r in runs] + [e["ioi_cv_hi"] for e in lit]
    x0, x1 = 0.0, max(xs) * 1.08
    y0, y1 = 0.0, max(ys) * 1.12

    def sx(v):
        return L + (v - x0) / (x1 - x0) * (W - L - R)

    def sy(v):
        return T + (1 - (v - y0) / (y1 - y0)) * (H - T - B)

    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
           'aria-label="Evenness per run against note rate">']
    for k in range(1, 6):
        v = y1 * k / 6
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" '
                   f'stroke="var(--grid)"/><text x="{L - 6}" y="{sy(v) + 4:.1f}" font-size="11" '
                   f'text-anchor="end" fill="var(--muted)">{v:.2f}</text>')
    for k in range(0, int(x1) + 1, 2 if x1 > 8 else 1):
        out.append(f'<text x="{sx(k):.1f}" y="{H - 16}" font-size="11" text-anchor="middle" '
                   f'fill="var(--muted)">{k}</text>')
    out.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 2}" font-size="11.5" '
               'text-anchor="middle" fill="var(--ink2)">notes per second</text>')
    seen: dict[float, int] = {}
    for e in lit:
        xx, a, b = sx(e["note_rate_nps"]), sy(e["ioi_cv_lo"]), sy(e["ioi_cv_hi"])
        k = seen.get(e["note_rate_nps"], 0)
        seen[e["note_rate_nps"]] = k + 1
        lx, anchor = (xx + 9, "start") if k % 2 == 0 else (xx - 9, "end")
        out.append(f'<rect x="{xx - 5:.1f}" y="{min(a, b) - 1.5:.1f}" width="10" '
                   f'height="{abs(a - b) + 3:.1f}" rx="2" fill="none" stroke="var(--ink2)" '
                   f'stroke-width="1.5"><title>{_e(e["label"])} ({_e(e["source"])}): CV '
                   f'{e["ioi_cv_lo"]}-{e["ioi_cv_hi"]} at {e["note_rate_nps"]} notes/s'
                   f'</title></rect><text x="{lx:.1f}" y="{b + 4 + 12 * (k // 2):.1f}" '
                   f'font-size="10.5" text-anchor="{anchor}" fill="var(--ink2)">'
                   f'{_e(e["label"])}</text>')
    for r in runs:
        col = {"strong": "var(--strong)"}.get(r.get("tier"), "var(--target)")
        rr = 4 + min(4, r["n_iois"] / 12)
        out.append(f'<circle cx="{sx(r["note_rate_nps"]):.1f}" cy="{sy(r["ioi_cv"]):.1f}" '
                   f'r="{rr:.1f}" fill="{col}" fill-opacity="0.75" stroke="var(--card)" '
                   f'stroke-width="1.5"><title>{_e(r["bars_label"])}: CV {r["ioi_cv"]:.3f} at '
                   f'{r["note_rate_nps"]:.1f} notes/s, {r["n_iois"]} intervals ({_e(r["kind"])})'
                   f'</title></circle>')
    out.append("</svg>")
    return "".join(out)


# =========================================================================== page


def _meta(rep: dict) -> str:
    p, i, r = rep["piece"], rep["input"], rep["references"]
    paths = i.get("paths", {})
    items = [("Piece", p.get("title") or p.get("piece_id") or "unknown"),
             ("Performance", i["performance_id"]),
             ("Capture", i["provenance"]),
             ("Notes played", f"{i['n_notes']} in {_fmt(i['duration_sec'], 0)} s"),
             ("Pedal data", "yes" if i["has_pedal"] else "no"),
             ("Bars (as played)", p["n_bars"]),
             ("Expert references", f"{r.get('tier_d_total', 0)} "
              f"({r.get('pianocore', 0)} PianoCoRe, {r.get('same_score', 0)} same score)"),
             ("Loudness references", f"{r.get('n_velocity_references') or 0} "
              f"({r.get('velocity_source') or 'none'})")]
    for k in ("score", "performance"):
        if paths.get(k):
            items.append((k.capitalize() + " file", Path(str(paths[k])).name))
    return '<div class="meta">' + "".join(
        f"<div>{_e(k)}: <b>{_e(v)}</b></div>" for k, v in items) + "</div>"


def _takes_table(rep: dict) -> str:
    tk = rep.get("takes")
    if not tk or not tk.get("takes"):
        return ""
    rows = "".join(f"<tr><td>{t['take']}</td><td>{_fmt(100 * t['accuracy'], 1)}%</td>"
                   f"<td>{t['n_wrong_pitch']}</td><td>{t['n_missed']}</td><td>{t['n_extra']}"
                   f"</td><td>{_fmt(t['tempo_bpm'], 0)}</td></tr>" for t in tk["takes"])
    return ('<table class="takes"><tr><th>Other take</th><th>correct</th><th>wrong</th>'
            f'<th>missed</th><th>extra</th><th>beats/min</th></tr>{rows}</table>')


def _links(out_dir: Path | None) -> str:
    items = []
    for name, rel in SPECS.items():
        target = REPO / rel
        href = os.path.relpath(target, out_dir) if out_dir is not None else rel
        items.append(f'<li><a href="{_e(href)}">{_e(name)}</a> ({_e(rel)})</li>')
    return "<ul>" + "".join(items) + "</ul>"


def render_html(rep: dict, out_dir: Path | str | None = None) -> str:
    """The report page. ``out_dir``: where it will be saved (for relative links to the specs)."""
    od = Path(out_dir).resolve() if out_dir is not None else None
    p = rep["piece"]
    title = p.get("title") or p.get("piece_id") or "Performance"
    notes = "".join(f"<li>{_e(n)}</li>" for n in rep["confidence"].get("notes", []))
    cards = "".join(
        f'<div class="card"><h3>{_e(c["title"])}</h3><ul>'
        + "".join(f"<li>{_e(f)}</li>" for f in c["findings"])
        + ("" if c["title"] != "Correctness" else "</ul>" + _takes_table(rep) + "<ul>")
        + "</ul></div>" for c in rep["summary"])
    prac = rep.get("practise", [])
    if prac:
        plist = '<ol class="practise">' + "".join(
            f'<li class="{_e(d["tier"])}"><div class="tag">{k + 1}. {_e(d["tier"])} · '
            f'{_e(d["category"].replace("_", " "))} · {_e(d["channel"])}</div>'
            f'<div>{_e(d["text"])}</div></li>' for k, d in enumerate(prac)) + "</ol>"
    else:
        plist = ("<p>Nothing here is beyond the expert range. Keep the whole piece in view "
                 "and use the timeline for detail.</p>")
    vlow = rep["confidence"]["velocity"] == "low"
    legend_tl = ('<div class="legend"><span><span class="sw" style="background:var(--strong)">'
                 '</span>strong (beyond experts\' 99th percentile)</span><span><span class="sw" '
                 'style="background:var(--notable)"></span>notable (beyond the 95th)</span>'
                 '<span><span class="sw" style="background:var(--flat)"></span>too flat, '
                 'strong</span><span><span class="sw" style="background:var(--flat-l)"></span>'
                 'too flat, notable</span><span><span class="sw" style="background:var('
                 '--neutral)"></span>in range or not tiered</span><span>numbers = flagged '
                 'notes; dots = pedal held or run present</span></div>')
    legend_c = ('<div class="legend"><span><span class="sw" style="background:var(--target)">'
                '</span>this performance (smooth)</span><span><span class="sw" style="background:'
                'var(--band)"></span>experts, 10th to 90th percentile</span><span><span '
                'class="sw" style="background:var(--band-mid)"></span>expert median (dashed)'
                '</span><span><span class="sw" style="background:var(--strong);opacity:.3">'
                '</span>strong bar</span><span><span class="sw" style="background:var(--notable)'
                '"></span>notable bar</span></div>')
    it = rep.get("interpretation") or {}
    tl = (it.get("curves", {}).get("tempo") or {}).get("level")
    vl = (it.get("curves", {}).get("velocity") or {}).get("level")
    methods = f"""
<ul>
<li>Alignment: parangonar DualDTW with the repeat path chosen from the performance (F-01, mean
note F1 0.964 on (n)ASAP). Bars are counted as played, so a repeated bar appears twice.</li>
<li>Correctness (F-02): wrong pitch, missed and extra notes; missed notes are reliable per bar,
not per note. Bars are ranked only beyond what the same checker reports on clean expert
recordings ({cal.CORRECTNESS_EXPERT_BARS['n_performances']} (n)ASAP performances,
{cal.CORRECTNESS_EXPERT_BARS['n_bars']} bars): more than
{int(cal.CORRECTNESS_EXPERT_BARS['wrong_pitch_q95'])} wrong note, or missed plus extra notes
above {cal.CORRECTNESS_EXPERT_BARS['missed_extra_per_note_q95']:.2f} per note (95th percentile);
the 99th percentile gives "strong". Per-bar expert check (F-08c): with at least
{cal.EXPERT_CHECK_MIN_REFS} expert performances of the same score and capture method (transcribed
experts for transcribed input), a bar must also exceed their {int(100 * cal.EXPERT_CHECK_Q[0])}th /
{int(100 * cal.EXPERT_CHECK_Q[1])}th percentile at that bar;
bars within it are marked as likely score or edition artefacts. On transcribed input extra notes
are low confidence and not ranked (A-01).</li>
<li>Tempo and loudness (F-03, F-06): 1.5-bar smooth curves. The level is removed before
comparing shapes, so the charts show your shape on the expert level
({_fmt(tl, 0)} beats per minute, {_fmt(vl, 0)} velocity). A bar is notable when its deviation
from the expert mean is beyond the 95th percentile of held-out experts at that bar, strong beyond
the 99th; "too flat" uses the same two tiers on the amount of shaping per 16-bar section.</li>
<li>Timing steadiness (F-04): your timing residual minus the expert fine-timing consensus, per
bar, against each expert's own leave-one-out value. Checked on 64 same-performance pairs
(Disklavier MIDI vs its audio transcription, against transcribed references): the capture method
does not change the flag rate (report-validation.md). Pedal blur: sustain pedal held across a
detected harmony change (F-04b). Evenness: strict runs (scales, arpeggios, repeated figures);
compared with experts only on the same score, and with published values only at a similar note
rate (within {int(100 * cal.SIMILAR_RATE_REL)}%).</li>
<li>Shaping (F-05): structural coherence is cross-validated by blocks of bars; per-phrase tempo
uses phrase ends found from cadences (held-out F1 0.46), compared with shifted boundaries.</li>
<li>No overall grade: how these measures combine into quality is an open research question
(R-04, Phase 3). "What to practise" is ranked by tier; within a tier, wrong or
missed notes come first, then control, then shaping; then by how far past the notable limit
the value is. The same wrong note in the same bar in two or more takes is marked strong, unless
the checker reports it for other pianists too (an artefact)
{"; loudness items are excluded here because velocity is low confidence" if vlow
else ""}. Text is filled from templates, not written by a language model.</li>
</ul>"""
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} · PianoLens report</title><style>{CSS}</style></head><body><main>
<h1>{_e(title)}</h1>
<p class="sub">PianoLens practice report · {_e(rep['generated'])} · schema {_e(rep['schema'])}</p>
{_meta(rep)}
<div class="notes"><b>Confidence notes</b><ul>{notes}</ul></div>
<h2>Summary</h2>
<div class="cards">{cards}</div>
<h2>Bar by bar</h2>
<div class="panel">{timeline_svg(rep)}</div>{legend_tl}
<p class="caption">Hover a cell for its numbers.</p>
<h2>Tempo against the experts</h2>
<div class="panel">{curve_svg(rep, 'tempo')}</div>{legend_c}
<p class="caption">Beats per minute (score beats). Shaded bars are outside the expert range.</p>
<h2>Loudness against the experts{' (low confidence)' if vlow else ''}</h2>
<div class="panel">{curve_svg(rep, 'velocity')}</div>
<p class="caption">MIDI velocity, smoothed over 1.5 bars.</p>
<h2>Evenness per run</h2>
<div class="panel">{evenness_svg(rep)}</div>
<p class="caption">Each dot is one scale or figure passage: timing variation (CV of the
tempo-normalized note intervals) against its speed. Outlined boxes are published values from
instructed, metronomic scales (landscape section 1.5); they are a floor for deliberate evenness,
not a norm for repertoire, and unevenness rises with speed, so compare only at a similar
rate.</p>
<h2>What to practise</h2>
{plist}
<footer><h2>Methods and limitations</h2>{methods}
<p>Specifications and sources:</p>{_links(od)}
<p>Research use only. Reference data are CC BY-NC datasets (PianoCoRe, (n)ASAP, Vienna 4x22).</p>
</footer></main></body></html>"""
    return body
