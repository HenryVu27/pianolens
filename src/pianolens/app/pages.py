"""HTML pages of the app. Pages are thin shells; ``static/app.js`` fills them from the JSON API.

No external assets: styles and scripts come from ``/static/``, fonts are the system's.
"""

from __future__ import annotations

from html import escape
from typing import Any

__all__ = ["error_page", "history_page", "home_page", "job_page", "layout"]


def layout(title: str, body: str, page: str, attrs: str = "") -> str:
    nav = "".join(
        f'<a href="{href}"{" aria-current=page" if key == page else ""}>{label}</a>'
        for key, href, label in (("home", "/", "New analysis"), ("history", "/history", "History"))
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · PianoLens</title>
<link rel="stylesheet" href="/static/app.css">
<script src="/static/app.js" defer></script>
</head><body data-page="{page}" {attrs}>
<header class="top"><div class="wrap top-in">
<a class="brand" href="/">PianoLens</a><nav>{nav}</nav>
<button type="button" class="ghost" id="theme"
 aria-label="Switch light or dark theme">Theme</button>
</div></header>
<main class="wrap">{body}</main>
<footer class="wrap foot">Runs on this computer only. Recordings and results stay in
<code>data/interim/app/</code>; reference data is for non-commercial research use.</footer>
</body></html>"""


def home_page() -> str:
    body = """
<h1>New analysis</h1>
<p class="lede">Choose the piece, add your recording or MIDI, and PianoLens compares it with expert
performances bar by bar.</p>
<form id="new" class="stack" autocomplete="off">
<section class="card">
  <h2><span class="num">1</span> Piece</h2>
  <label class="field" for="q">Search supported pieces</label>
  <input id="q" type="search" placeholder="Composer, title or opus (e.g. chopin op. 10)"
    aria-controls="pieces">
  <div id="pieces" class="pieces" role="listbox" aria-label="Supported pieces">
    <p class="muted">Loading the piece list...</p></div>
  <p id="chosen" class="chosen muted">No piece chosen.</p>
  <input type="hidden" name="piece_id" id="piece_id">
  <details class="more"><summary>My piece is not in the list</summary>
    <p class="muted">Upload its score as MusicXML. The report then has notes, timing and shaping,
    but no comparison with experts (there are no references for it).</p>
    <label class="field" for="score">Score (MusicXML, .mxl, MEI)</label>
    <input id="score" name="score" type="file" accept=".musicxml,.xml,.mxl,.mei">
    <label class="field" for="title">Title (optional)</label>
    <input id="title" name="title" type="text" maxlength="200">
  </details>
</section>
<section class="card">
  <h2><span class="num">2</span> Performance</h2>
  <label class="field" for="perf">Recording (wav, mp3, m4a, flac, aac, ogg) or MIDI (.mid,
    .midi). Several files = several takes of the same piece; the first is the one analysed in
    detail.</label>
  <input id="perf" name="performance" type="file" multiple required
    accept=".wav,.mp3,.m4a,.flac,.aac,.ogg,.mid,.midi">
  <div id="kind-audio" class="note" hidden>
    <b>Audio input.</b> It is transcribed to notes on this computer (Transkun), which takes
    about a quarter of a minute per take. From a phone recording, <b>timing and tempo</b> are
    trustworthy; <b>extra notes, dynamics and pedal</b> are low confidence and are shown but not
    ranked.
    <label class="check"><input type="checkbox" name="filter_extras"> Remove likely
    transcription extras first (A-01b rule filter)</label>
  </div>
  <div id="kind-midi" class="note" hidden>
    <b>MIDI input.</b> How was it recorded?
    <select name="provenance" aria-label="How the MIDI was recorded">
      <option value="unknown">Not sure</option>
      <option value="disklavier">Disklavier or other acoustic piano with MIDI out</option>
      <option value="sensor">Digital piano or key sensors</option>
      <option value="synthetic">Written or edited by hand</option>
      <option value="transcribed:transkun">Transcribed from audio by Transkun</option>
      <option value="transcribed">Transcribed from audio by another transcriber</option>
    </select>
    <p class="muted small">Transcribed MIDI is read like an audio upload: extra notes, dynamics
    and pedal are low confidence, and wrong notes are checked against expert
    transcriptions.</p>
    <label class="check"><input type="checkbox" name="filter_extras"> If transcribed: remove
    likely transcription extras first (A-01b rule filter, validated on Transkun)</label>
  </div>
</section>
<details class="card more"><summary>Advanced</summary>
  <label class="field" for="excl">Leave out these references (PianoCoRe ids or source ids,
    e.g. ASAP_SunMeiting08 when the upload is a copy of that performance)</label>
  <input id="excl" name="exclude_references" type="text">
  <label class="field" for="mw">Comparison passages (1-12)</label>
  <input id="mw" name="max_windows" type="number" min="1" max="12" value="8">
  <label class="check"><input type="checkbox" name="no_clips"> Report only, no audio clips</label>
  <label class="check"><input type="checkbox" name="ignore_wrong_piece"> Analyse even if the
    quick check says the recording is another piece (for a short excerpt)</label>
</details>
<div class="actions"><button type="submit" class="primary" id="go">Analyse</button>
<span id="form-msg" class="muted" role="status"></span></div>
</form>"""
    return layout("New analysis", body, "home")


def job_page(job: dict[str, Any]) -> str:
    spec = job.get("spec", {})
    kind = "Audio" if spec.get("input_kind") == "audio" else "MIDI"
    n = len(job.get("takes", []))
    body = f"""
<div class="head-row"><div>
<h1 id="job-title">{escape(spec.get("title") or "Analysis")}</h1>
<p class="muted">{kind} input, {n} take{"s" if n != 1 else ""} ·
started {escape(job.get("created", ""))}</p>
</div><div id="job-actions" class="actions"></div></div>
<section id="progress" class="card" hidden></section>
<section id="results" hidden></section>"""
    return layout(spec.get("title") or "Analysis", body, "job",
                  f'data-job="{escape(job["id"])}"')


def history_page(jobs: list[dict[str, Any]]) -> str:
    if not jobs:
        rows = '<p class="muted">No analyses yet. <a href="/">Start one</a>.</p>'
    else:
        items = []
        for j in jobs:
            spec = j.get("spec", {})
            s = j.get("summary") or {}
            rep = s.get("report") or {}
            facts = []
            transcribed = spec.get("provenance") == "transcribed"
            if transcribed and rep.get("wrong_missed_rate") is not None:
                facts.append(f"{100 * rep['wrong_missed_rate']:.1f}% wrong or missed notes")
            elif not transcribed and rep.get("error_rate") is not None:
                facts.append(f"{100 * rep['error_rate']:.1f}% note errors")
            if rep.get("n_practise") is not None:
                facts.append(f"{rep['n_practise']} practise items")
            names = ", ".join(t.get("original_name", "") for t in j.get("takes", []))
            items.append(f"""<li class="hist" data-id="{escape(j['id'])}">
<div class="hist-main"><a href="/jobs/{escape(j['id'])}">{escape(spec.get("title", ""))}</a>
<span class="pill {escape(j.get('state', ''))}">{escape(j.get('state', ''))}</span>
<div class="muted small">{escape(j.get("created", ""))} · {escape(spec.get("input_kind", ""))} ·
{escape(names)}{" · " + escape(", ".join(facts)) if facts else ""}</div></div>
<button type="button" class="ghost danger" data-delete="{escape(j['id'])}">Delete</button></li>""")
        rows = '<ul class="hist-list">' + "".join(items) + "</ul>"
    body = f"""<h1>History</h1>
<p class="lede">Past analyses on this computer, newest first. Deleting removes the uploaded
files, the report and the clips.</p>{rows}"""
    return layout("History", body, "history")


def error_page(code: int, msg: str) -> str:
    return layout(f"Error {code}", f"<h1>Error {code}</h1><p>{escape(msg)}</p>"
                  f'<p><a href="/">Back to the start</a></p>', "error")

