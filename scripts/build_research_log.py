"""Render the project's reader-facing docs to self-contained HTML pages that share a tab bar.

Usage: uv run --with markdown python scripts/build_research_log.py [--open]
Pages (no external requests; light and dark themes):
  docs/SCORING_MODEL.md -> docs/scoring-model.html  (how a performance is scored, as it stands)
  docs/RESEARCH_LOG.md  -> docs/research-log.html   (what was tried, in full)

Any other markdown file renders the same way, without the tab bar (images stay relative to the
output file):
    uv run --with markdown python scripts/build_research_log.py SRC.md OUT.html "Title" [--open]
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
# (source, output, tab label, page title, description)
PAGES = [
    ("SCORING_MODEL.md", "scoring-model.html", "The scoring model",
     "PianoLens scoring model", "How PianoLens judges a piano performance, as it stands."),
    ("RESEARCH_LOG.md", "research-log.html", "Research log",
     "PianoLens research log", "Can a computer judge piano playing? What was tried, in full."),
]

CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#5b6470;--line:#e3e0d8;--card:#ffffff;
--accent:#2f5d8a;--accent-soft:#e8eef5;--code:#f3f1ec;--good:#2e7d4f;--warn:#9a6b00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e6e3;
--muted:#9aa3ad;--line:#2c3036;--card:#1c1f23;--accent:#8fb6e0;--accent-soft:#1f2a36;
--code:#22262b;--good:#6fcf97;--warn:#e0b458}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e6e3;--muted:#9aa3ad;--line:#2c3036;--card:#1c1f23;
--accent:#8fb6e0;--accent-soft:#1f2a36;--code:#22262b;--good:#6fcf97;--warn:#e0b458}
*{box-sizing:border-box}
header.tabs{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:6px;
padding:10px 24px;background:var(--bg);border-bottom:1px solid var(--line)}
header.tabs .brand{font-weight:700;margin-right:18px}
header.tabs a{color:var(--muted);text-decoration:none;padding:6px 14px;border-radius:999px;
font-size:14px}
header.tabs a:hover{color:var(--accent)}
header.tabs a.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
header.tabs .theme{margin-left:auto;position:static}
main [id]{scroll-margin-top:64px}
figure.diagram{margin:1.6rem 0;padding:1rem;background:var(--card);border:1px solid var(--line);
border-radius:10px;overflow-x:auto}
figure.diagram svg{display:block;max-width:100%;height:auto;margin:0 auto}
figure.diagram figcaption{font-size:.88rem;color:var(--muted);margin-top:.6rem}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.wrap{display:grid;grid-template-columns:260px minmax(0,760px);gap:48px;
max-width:1100px;margin:0 auto;padding:32px 24px 96px}
nav.toc{position:sticky;top:76px;align-self:start;max-height:calc(100vh - 96px);overflow:auto;
font-size:14px;line-height:1.45;border-right:1px solid var(--line);padding-right:16px}
nav.toc .title{font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;
font-size:12px;margin-bottom:10px}
nav.toc a{display:block;color:var(--muted);text-decoration:none;padding:3px 0 3px 8px;
border-left:2px solid transparent}
nav.toc a.h2{color:var(--fg);font-weight:600;margin-top:12px}
nav.toc a.h3{padding-left:20px;font-size:13px}
nav.toc a:hover{color:var(--accent)}
nav.toc a.active{color:var(--accent);border-left-color:var(--accent)}
nav.toc .sub{display:none;margin:2px 0 6px}
nav.toc .sub.open{display:block}
nav.toc a.h4{padding-left:32px;font-size:12.5px;line-height:1.35}
p.coderef{font-size:.85rem;color:var(--muted);border-top:1px dashed var(--line);padding-top:.4rem}
main h1{font-size:2.1rem;line-height:1.2;margin:0 0 .4rem}
main h2{font-size:1.75rem;line-height:1.25;margin:4.5rem 0 1rem;padding-top:1.4rem;
border-top:3px solid var(--accent)}
main h3{font-size:1.3rem;margin:2.8rem 0 .7rem;padding-top:.4rem;border-top:1px solid var(--line)}
main h4{font-size:1.05rem;margin:1.9rem 0 .4rem;color:var(--accent)}
main h5{font-size:.98rem;margin:1.4rem 0 .3rem}
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
.theme{background:var(--card);color:var(--fg);
border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:13px;cursor:pointer}
@media (max-width:900px){.wrap{grid-template-columns:1fr;gap:0;padding:56px 16px 64px}
nav.toc{position:static;max-height:none;border-right:none;border-bottom:1px solid var(--line);
padding:0 0 16px;margin-bottom:24px}}
@media (max-width:600px){header.tabs{padding:8px 12px;flex-wrap:wrap}
header.tabs .brand{display:none}}
@media print{nav.toc,header.tabs{display:none}.wrap{display:block}}
"""

JS = """
(function(){
var r = document.documentElement, b = document.querySelector('.theme');
try { var s = localStorage.getItem('rl-theme'); if (s) r.dataset.theme = s; } catch (e) {}
b.addEventListener('click', function () {
  var dark = matchMedia('(prefers-color-scheme: dark)').matches;
  var d = r.dataset.theme || (dark ? 'dark' : 'light');
  r.dataset.theme = d === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('rl-theme', r.dataset.theme); } catch (e) {}
});
var links = {};
document.querySelectorAll('nav.toc a').forEach(function (a) {
  links[a.getAttribute('href').slice(1)] = a;
});
var hs = [].slice.call(document.querySelectorAll('main h2[id],main h3[id],main h4[id]'));
function clear(sel, cls) {
  document.querySelectorAll(sel).forEach(function (e) { e.classList.remove(cls); });
}
function spy() {
  var cur = null;
  for (var i = 0; i < hs.length; i++) {
    if (hs[i].getBoundingClientRect().top < 140) cur = hs[i].id; else break;
  }
  clear('nav.toc a.active', 'active');
  clear('nav.toc .sub.open', 'open');
  var a = cur && links[cur];
  if (!a) return;
  a.classList.add('active');
  var isSub = a.classList.contains('h4');
  var next = a.nextElementSibling;
  var sub = isSub ? a.parentNode : (next && next.classList.contains('sub') ? next : null);
  if (!sub) return;
  sub.classList.add('open');
  if (isSub && sub.previousElementSibling) sub.previousElementSibling.classList.add('active');
}
addEventListener('scroll', spy, {passive: true});
spy();
})();
"""


def slug(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


def toc_markup(toc: list[tuple[int, str, str]]) -> str:
    """Parts and chapters always visible; a chapter's subsections fold open while reading it."""
    out: list[str] = []
    open_sub = False
    for lvl, sid, txt in toc:
        label = html.escape(html.unescape(txt))
        if lvl == 4:
            if not open_sub:
                out.append('<div class="sub">')
                open_sub = True
            out.append(f'<a class="h4" href="#{sid}">{label}</a>')
            continue
        if open_sub:
            out.append("</div>")
            open_sub = False
        out.append(f'<a class="h{lvl}" href="#{sid}">{label}</a>')
    if open_sub:
        out.append("</div>")
    return "".join(out)


def tab_bar(current: str) -> str:
    links = "".join(
        f'<a class="{"on" if out == current else ""}" href="{out}">{html.escape(label)}</a>'
        for _, out, label, _, _ in PAGES
    )
    return (f'<header class="tabs"><span class="brand">PianoLens</span>{links}'
            '<button class="theme" type="button">Light / dark</button></header>')


def diagrams(body: str) -> str:
    """Replace <!-- DIAGRAM:name --> markers with inline SVG from docs/diagrams/<name>.svg."""
    def sub(m: re.Match) -> str:
        path = DOCS / "diagrams" / f"{m.group(1)}.svg"
        return path.read_text(encoding="utf-8") if path.exists() else ""
    return re.sub(r"<!--\s*DIAGRAM:([\w-]+)\s*-->", sub, body)


def build_page(src: Path, out: Path, title: str, description: str, tabs: bool = True) -> Path:
    md = src.read_text(encoding="utf-8")
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])

    toc: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}

    def add_id(m: re.Match) -> str:
        level, inner = int(m.group(1)), m.group(2)
        base = slug(inner)
        n = seen.get(base, 0)
        seen[base] = n + 1
        sid = base if n == 0 else f"{base}-{n}"
        if level in (2, 3, 4):
            toc.append((level, sid, re.sub(r"<[^>]+>", "", inner)))
        return f'<h{level} id="{sid}">{inner}</h{level}>'

    body = re.sub(r"<h([1-4])>(.*?)</h\1>", add_id, body, flags=re.S)
    body = re.sub(r"<p>(<strong>)?In the code:", r'<p class="coderef">\1In the code:', body)
    body = diagrams(body)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<style>{CSS}</style></head>
<body>{tab_bar(out.name) if tabs else ''}
<div class="wrap"><nav class="toc"><div class="title">Contents</div>{toc_markup(toc)}</nav>
<main>{body}</main></div>
<script>{JS}</script></body></html>
"""
    out.write_text(page, encoding="utf-8")
    return out


def build() -> list[Path]:
    return [build_page(DOCS / src, DOCS / out, title, desc)
            for src, out, _, title, desc in PAGES if (DOCS / src).exists()]


def open_file(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.run([opener, str(path)], check=False)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--open"]
    if args:
        title = args[2] if len(args) > 2 else Path(args[0]).stem
        outs = [build_page(Path(args[0]), Path(args[1]), title, title, tabs=False)]
    else:
        outs = build()
    for o in outs:
        print(o)
    if "--open" in sys.argv and outs:
        open_file(outs[0])
