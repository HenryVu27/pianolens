"""Headless smoke test of the S-03 study app (no audio, simulated answers).

1. Serves the repository root on a free localhost port (Python http.server, local only).
2. Checks that the app files, the manifest and a sample of stimulus WAVs are served.
3. Runs the app in headless Chrome with ``?autotest=1`` and reads the exported JSON from the
   DOM (``#autotest-result``), then checks it: every trial answered, counts per dimension and
   level as designed, positions balanced, catch trials present.

Usage: uv run python study/app/smoke_test.py [--mode main|pilot] [--parts AB|A|B] [--chrome PATH]
Needs the stimuli built (scripts/build_study_s03.py) and Google Chrome or Chromium.
Exit code 0 on success. Nothing is published or sent anywhere.
"""

from __future__ import annotations

import argparse
import collections
import functools
import http.server
import json
import re
import shutil
import socket
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
]


def find_chrome(explicit: str | None) -> str | None:
    for c in [explicit] if explicit else CHROME_CANDIDATES:
        if c and (Path(c).exists() or shutil.which(c)):
            return c if Path(c).exists() else shutil.which(c)
    return None


def serve() -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_QuietHandler, directory=str(REPO))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # noqa: D401 - silence
        pass


def fetch(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read()


def run(mode: str, chrome: str | None, parts: str = "AB") -> list[str]:
    problems: list[str] = []
    httpd, port = serve()
    base = f"http://127.0.0.1:{port}"
    try:
        for path in ("study/app/index.html", "study/app/app.js", "study/app/design.js",
                     "study/app/style.css", "data/interim/study_s03/manifest.js"):
            status, body = fetch(f"{base}/{path}")
            if status != 200 or not body:
                problems.append(f"GET {path}: {status}")
        manifest = json.loads((REPO / "data/interim/study_s03/manifest.json").read_text())
        sample = manifest["stimuli"][:: max(1, len(manifest["stimuli"]) // 20)]
        for stim in sample:
            status, body = fetch(f"{base}/data/interim/study_s03/{stim['file']}")
            if status != 200 or body[:4] != b"RIFF":
                problems.append(f"GET {stim['file']}: {status}, not a WAV")
        print(f"served app + manifest + {len(sample)} sample WAVs")

        exe = find_chrome(chrome)
        if exe is None:
            problems.append("Chrome/Chromium not found: headless run skipped")
            return problems
        url = f"{base}/study/app/index.html?autotest=1&mode={mode}&parts={parts}"
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
               "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
               "--virtual-time-budget=60000", "--dump-dom", url]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        m = re.search(r'<pre id="autotest-result"[^>]*>(.*?)</pre>', proc.stdout, re.S)
        if not m or not m.group(1).strip():
            problems.append("no autotest result in the DOM; stderr: " + proc.stderr[-800:])
            return problems
        import html

        data = json.loads(html.unescape(m.group(1)))
        if "error" in data:
            problems.append("app error: " + data["error"])
            return problems
        problems += check_result(data, manifest, mode)
        out = REPO / "data" / "interim" / "study_s03" / f"smoke_{mode}_{parts}.json"
        out.write_text(json.dumps(data, indent=1))
        print(f"autotest export: {len(data['responses'])} responses -> {out}")
    finally:
        httpd.shutdown()
    return problems


def check_result(data: dict, manifest: dict, mode: str) -> list[str]:
    p: list[str] = []
    s = data["session"]
    cfg = s["config"]
    if s["missing_stimuli"]:
        p.append(f"missing stimuli: {s['missing_stimuli'][:5]}")
    if not s["headphone"]["pass"]:
        p.append("simulated headphone check failed")
    resp = data["responses"]
    by_list = collections.Counter(r["list"] for r in resp)
    levels = collections.defaultdict(set)
    for st in manifest["stimuli"]:
        if st["dimension"] not in ("original", "catch"):
            levels[(st["span"], st["dimension"])].add(st["level"])
    n_det = sum(len(v) for (sp, _), v in levels.items() if sp == "det") * cfg["detReps"]
    n_pref = sum(len(v) for (sp, _), v in levels.items() if sp == "pref") * cfg["prefReps"]
    want = {"practiceA": 3, "partA": n_det + cfg["detCatch"], "practiceB": 1,
            "partB": n_pref + cfg["prefIdentical"] + cfg["prefCatch"]}
    parts = s.get("parts", "AB")
    want = {k: v for k, v in want.items() if k[-1] in parts}
    for k, v in want.items():
        if by_list[k] != v:
            p.append(f"{k}: {by_list[k]} responses, expected {v}")
    a = [r for r in resp if r["list"] == "partA" and r["kind"] == "test"]
    cells = collections.Counter((r["dimension"], r["level"]) for r in a)
    if "A" in parts and set(cells.values()) != {cfg["detReps"]}:
        p.append(f"part A cells not all {cfg['detReps']} reps: {sorted(set(cells.values()))}")
    for dim in {r["dimension"] for r in a}:
        pos = collections.Counter(r["degraded_position"] for r in a if r["dimension"] == dim)
        if abs(pos[1] - pos[2]) > 1:
            p.append(f"part A {dim}: degraded positions unbalanced {dict(pos)}")
        ex = collections.Counter(r["excerpt"] for r in a if r["dimension"] == dim)
        usable = {st["excerpt"] for st in manifest["stimuli"] if st["span"] == "det"
                  and st["dimension"] == dim and st.get("changed", True)}
        if max(ex.values()) - min(ex.values()) > 1 or not set(ex) <= usable or (
                sum(ex.values()) >= len(usable) and len(ex) < len(usable)):
            p.append(f"part A {dim}: excerpts unevenly used {dict(ex)} (usable {sorted(usable)})")
        bad = [r for r in a if r["dimension"] == dim and not any(
            st["id"] in (r["stim_a"], r["stim_b"]) and st.get("changed", True)
            and st["dimension"] == dim for st in manifest["stimuli"])]
        if bad:
            p.append(f"part A {dim}: {len(bad)} trials use an unchanged stimulus")
    b = [r for r in resp if r["list"] == "partB" and r["kind"] == "test"]
    for dim in {r["dimension"] for r in b}:
        pos = collections.Counter(r["original_position"] for r in b if r["dimension"] == dim)
        if abs(pos[1] - pos[2]) > 1:
            p.append(f"part B {dim}: original positions unbalanced {dict(pos)}")
    if not all(isinstance(r["rt_ms"], int) for r in resp):
        p.append("missing reaction times")
    same = sum(resp[i]["excerpt"] == resp[i - 1]["excerpt"] for i in range(1, len(resp))
               if resp[i]["list"] == resp[i - 1]["list"])
    print(f"lists {dict(by_list)}; back-to-back same excerpt: {same}")
    probe = data.get("audio_probe") or {}
    want_dur = next(st["duration_sec"] for st in manifest["stimuli"]
                    if st["file"] == probe.get("file"))
    if not probe.get("ok") or abs(probe.get("duration_s", 0) - want_dur) > 0.05:
        p.append(f"browser could not load/decode a stimulus WAV: {probe}")
    else:
        print(f"browser decoded {probe['file']}: {probe['duration_s']:.2f} s")
    keys = set(data["participant"]["background"])
    if keys != {"musician", "training_years", "plays_piano", "hearing", "device"}:
        p.append(f"unexpected background fields {keys}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="main", choices=["main", "pilot"])
    ap.add_argument("--chrome")
    ap.add_argument("--parts", default="AB", choices=["AB", "A", "B"])
    args = ap.parse_args()
    problems = run(args.mode, args.chrome, args.parts)
    for pr in problems:
        print("PROBLEM:", pr)
    print("SMOKE TEST", "FAILED" if problems else "PASSED",
          f"(mode={args.mode}, parts={args.parts})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
