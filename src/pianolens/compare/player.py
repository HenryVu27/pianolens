"""Standalone A/B player for a comparison manifest (P-01).

One self-contained HTML file: every clip is embedded as a base64 MP3, all code and styles are
inline, and the page makes no network requests. Audio is decoded with the Web Audio API, so
switching clips is instant. When the listener switches, the position carries over bar by bar:
the current time is located between two bar lines of the playing clip (``bar_times``) and moved
to the same fraction between the same bar lines of the new clip, which follows each performer's
rubato. Per window: one button per clip (keys 1-4), play/pause (space), loop (L), and a clickable
timeline with the bar lines and the flagged bars shaded. Light and dark themes follow the system
setting, with a toggle.

The page template is ``player_template.html`` beside this module (``__TITLE__`` and ``__DATA__``
are filled in). The HTML embeds the clips, so it is as private as they are: keep it under
``data/interim/``.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any

__all__ = ["player_html", "write_player"]

_KEEP = ("label", "duration_sec", "window_on", "window_off", "bar_times", "performance_id",
         "source_id", "provenance", "performer", "source_dataset", "capture_model",
         "distance_percentile", "score_span_match")


def _clip_payload(c: dict[str, Any], base: Path) -> dict[str, Any]:
    data = (base / c["path"]).read_bytes()
    out = {k: c.get(k) for k in _KEEP if c.get(k) is not None}
    out["src"] = "data:audio/mpeg;base64," + base64.b64encode(data).decode("ascii")
    return out


def player_html(manifest: dict[str, Any], base_dir: Path | str) -> str:
    """The player page for ``manifest`` (clip paths relative to ``base_dir``)."""
    base = Path(base_dir)
    rep = manifest.get("report", {})
    wins = []
    for w in manifest.get("windows", []):
        clips = {k: _clip_payload(c, base) for k, c in w.get("clips", {}).items()}
        if not clips:
            continue
        wins.append({"id": w["id"], "label": w["bars_label"], "tier": w["tier"],
                     "truncated": w.get("truncated", False),
                     "reasons": [{"tier": r.get("tier"), "category": r.get("category"),
                                  "channel": r.get("channel"), "text": r.get("text")}
                                 for r in w.get("reasons", [])],
                     "clips": clips})  # fmt: skip
    data = {"title": rep.get("title") or manifest.get("name", "Comparison"),
            "provenance": rep.get("provenance"), "windows": wins}
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(str(data["title"]))
    template = (Path(__file__).with_name("player_template.html")).read_text()
    return template.replace("__TITLE__", title).replace("__DATA__", payload)


def write_player(manifest_path: Path | str, out_html: Path | str | None = None) -> Path:
    """Write ``player.html`` next to ``manifest.json`` (or to ``out_html``)."""
    manifest_path = Path(manifest_path)
    m = json.loads(manifest_path.read_text())
    out = Path(out_html) if out_html else manifest_path.with_name("player.html")
    out.write_text(player_html(m, manifest_path.parent))
    return out
