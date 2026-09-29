"""Render docs/RESEARCH_LOG.md to a self-contained, readable HTML page.

Usage: uv run --with markdown python scripts/build_research_log.py [--open]
Output: docs/research-log.html (no external requests; light and dark themes).
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "RESEARCH_LOG.md"
OUT = ROOT / "docs" / "research-log.html"

CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#5b6470;--line:#e3e0d8;--card:#ffffff;
--accent:#2f5d8a;--accent-soft:#e8eef5;--code:#f3f1ec;--good:#2e7d4f;--warn:#9a6b00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e6e3;
--muted:#9aa3ad;--line:#2c3036;--card:#1c1f23;--accent:#8fb6e0;--accent-soft:#1f2a36;
--code:#22262b;--good:#6fcf97;--warn:#e0b458}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e6e3;--muted:#9aa3ad;--line:#2c3036;--card:#1c1f23;
--accent:#8fb6e0;--accent-soft:#1f2a36;--code:#22262b;--good:#6fcf97;--warn:#e0b458}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.wrap{display:grid;grid-template-columns:260px minmax(0,760px);gap:48px;
max-width:1100px;margin:0 auto;padding:48px 24px 96px}
nav.toc{position:sticky;top:24px;align-self:start;max-height:calc(100vh - 48px);overflow:auto;
font-size:14px;line-height:1.45;border-right:1px solid var(--line);padding-right:16px}
nav.toc .title{font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;
font-size:12px;margin-bottom:10px}
nav.toc a{display:block;color:var(--muted);text-decoration:none;padding:3px 0}
nav.toc a.h3{padding-left:12px;font-size:13px}
nav.toc a:hover{color:var(--accent)}
main h1{font-size:2.1rem;line-height:1.2;margin:0 0 .4rem}
main h2{font-size:1.45rem;margin:2.6rem 0 .8rem;padding-top:.6rem;border-top:1px solid var(--line)}
main h3{font-size:1.12rem;margin:2rem 0 .5rem;color:var(--accent)}
main p,main li{max-width:72ch}
main a{color:var(--accent)}
blockquote{margin:1.2rem 0;padding:.9rem 1.2rem;background:var(--accent-soft);
border-left:4px solid var(--accent);border-radius:6px}
blockquote p{margin:.3rem 0}
code{background:var(--code);padding:.1em .35em;border-radius:4px;font-size:.88em}
table{width:100%;border-collapse:collapse;margin:1rem 0 1.4rem;font-size:.92rem;
background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden;display:block;
overflow-x:auto}
th,td{text-align:left;padding:.55rem .75rem;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--accent-soft);font-weight:600}
tr:last-child td{border-bottom:none}
hr{border:none;border-top:1px solid var(--line);margin:2rem 0}
.meta{color:var(--muted);font-size:.95rem;margin-bottom:1.5rem}
.theme{position:fixed;top:14px;right:16px;background:var(--card);color:var(--fg);
border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:13px;cursor:pointer}
@media (max-width:900px){.wrap{grid-template-columns:1fr;gap:0;padding:56px 16px 64px}
nav.toc{position:static;max-height:none;border-right:none;border-bottom:1px solid var(--line);
padding:0 0 16px;margin-bottom:24px}}
@media print{nav.toc,.theme{display:none}.wrap{display:block}}
"""

JS = """
(function(){var r=document.documentElement,b=document.querySelector('.theme');
try{var s=localStorage.getItem('rl-theme');if(s)r.dataset.theme=s;}catch(e){}
b.addEventListener('click',function(){var d=r.dataset.theme||
(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
r.dataset.theme=d==='dark'?'light':'dark';try{localStorage.setItem('rl-theme',r.dataset.theme);}catch(e){}});})();
"""


def slug(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


def build() -> Path:
    md = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])

    toc: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}

    def add_id(m: re.Match) -> str:
        level, inner = int(m.group(1)), m.group(2)
        base = slug(inner)
        n = seen.get(base, 0)
        seen[base] = n + 1
        sid = base if n == 0 else f"{base}-{n}"
        if level in (2, 3):
            toc.append((level, sid, re.sub(r"<[^>]+>", "", inner)))
        return f'<h{level} id="{sid}">{inner}</h{level}>'

    body = re.sub(r"<h([1-3])>(.*?)</h\1>", add_id, body, flags=re.S)
    toc_html = "".join(
        f'<a class="h{lvl}" href="#{sid}">{html.escape(html.unescape(txt))}</a>'
        for lvl, sid, txt in toc
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PianoLens research log</title>
<style>{CSS}</style></head>
<body><button class="theme" type="button">Light / dark</button>
<div class="wrap"><nav class="toc"><div class="title">Contents</div>{toc_html}</nav>
<main>{body}</main></div>
<script>{JS}</script></body></html>
"""
    OUT.write_text(page, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    out = build()
    print(out)
    if "--open" in sys.argv:
        subprocess.run(["open", str(out)], check=False)
