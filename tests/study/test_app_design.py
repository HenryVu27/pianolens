"""The S-03 app's trial builder (study/app/design.js), run under Node on a synthetic manifest."""

from __future__ import annotations

import collections
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DESIGN = REPO / "study" / "app" / "design.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")

DIMS = {"timing_jitter": [0.0125, 0.025, 0.05, 0.1], "voicing": [0.75, 0.5, 0.0, -1.0],
        "wrong_notes": [0.01, 0.02, 0.04, 0.08]}  # fmt: skip
EXCERPTS = [f"E{i}" for i in range(1, 9)]


def fake_manifest() -> dict:
    stim = []
    for span in ("det", "pref"):
        for e in EXCERPTS:
            stim.append({"id": f"{span}/{e}_orig", "span": span, "excerpt": e,
                         "dimension": "original", "level": None, "x": 0.0})
            stim.append({"id": f"{span}/{e}_catch", "span": span, "excerpt": e,
                         "dimension": "catch", "level": 0.3, "x": 0.3})
            for d, levels in DIMS.items():
                for lv in levels:
                    stim.append({"id": f"{span}/{e}_{d}_{lv}", "span": span, "excerpt": e,
                                 "dimension": d, "level": lv, "x": abs(lv) + 0.1})
    return {"excerpts": [{"id": e} for e in EXCERPTS], "stimuli": stim}


def build(tmp_path: Path, mode: str, seed: str) -> dict:
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps(fake_manifest()))
    js = (f"const D = require({json.dumps(str(DESIGN))});"
          f"const m = require({json.dumps(str(m))});"
          f"process.stdout.write(JSON.stringify(D.buildSession(m, {{mode: {json.dumps(mode)}, "
          f"seed: {json.dumps(seed)}}})));")
    out = subprocess.run([NODE, "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_main_session_counts_balance_and_ids(tmp_path):
    s = build(tmp_path, "main", "P123456")
    cfg = s["config"]
    assert s["missing"] == []
    ids = {x["id"] for x in fake_manifest()["stimuli"]}
    lookup = {(x["span"], x["excerpt"], x["dimension"], x["level"]): x["id"]
              for x in fake_manifest()["stimuli"]}
    a = [t for t in s["partA"] if t["kind"] == "test"]
    assert len(a) == 3 * 4 * cfg["detReps"]
    assert sum(t["kind"] == "catch" for t in s["partA"]) == cfg["detCatch"]
    cells = collections.Counter((t["dimension"], t["level"]) for t in a)
    assert set(cells.values()) == {cfg["detReps"]}
    for d in DIMS:
        tr = [t for t in a if t["dimension"] == d]
        pos = collections.Counter(t["degraded_position"] for t in tr)
        assert abs(pos[1] - pos[2]) <= 1
        ex = collections.Counter(t["excerpt"] for t in tr)
        assert max(ex.values()) - min(ex.values()) <= 1  # 12 trials over 8 excerpts
        for t in tr:  # the reference is the original; exactly one of A/B is degraded
            assert t["ref"].endswith("_orig")
            want = lookup[("det", t["excerpt"], d, t["level"])]
            assert {t["a"], t["b"]} == {t["ref"], want}
            deg = t["a"] if t["degraded_position"] == 1 else t["b"]
            assert not deg.endswith("_orig")
    b = s["partB"]
    assert sum(t["kind"] == "identical" for t in b) == cfg["prefIdentical"]
    assert sum(t["kind"] == "test" for t in b) == 3 * 4 * cfg["prefReps"]
    for t in b:
        if t["kind"] in ("test", "catch"):
            orig = t["a"] if t["original_position"] == 1 else t["b"]
            assert orig.endswith("_orig")
    for lst in ("practiceA", "partA", "practiceB", "partB"):
        for t in s[lst]:
            for k in ("ref", "a", "b"):
                if t.get(k):
                    assert t[k] in ids
    # catch trials are spread, not bunched at the start or end
    catch_pos = [i for i, t in enumerate(s["partA"]) if t["kind"] == "catch"]
    assert catch_pos[0] > 0 and catch_pos[-1] < len(s["partA"]) - 1


def test_seeded_and_pilot_mode(tmp_path):
    a1 = build(tmp_path, "main", "PAAAAAA")
    a2 = build(tmp_path, "main", "PAAAAAA")
    b = build(tmp_path, "main", "PBBBBBB")
    assert a1["partA"] == a2["partA"]
    assert [t["a"] for t in a1["partA"]] != [t["a"] for t in b["partA"]]
    p = build(tmp_path, "pilot", "PAAAAAA")
    assert p["config"]["detReps"] == 2 and p["config"]["prefReps"] == 1
    assert sum(t["kind"] == "test" for t in p["partA"]) == 3 * 4 * 2


def test_unchanged_stimuli_are_not_used(tmp_path):
    m = fake_manifest()
    for st in m["stimuli"]:  # E1-E3 have nothing to blur at the lowest voicing level
        if st["dimension"] == "voicing" and st["level"] == 0.75 and st["excerpt"] in ("E1",
                                                                                      "E2",
                                                                                      "E3"):
            st["changed"] = False
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    js = (f"const D = require({json.dumps(str(DESIGN))});const m = require({json.dumps(str(p))});"
          "process.stdout.write(JSON.stringify(D.buildSession(m, {mode: 'main', seed: 'X'})));")
    s = json.loads(subprocess.run([NODE, "-e", js], capture_output=True, text=True,
                                  check=True).stdout)
    low = [t for t in s["partA"] if t["dimension"] == "voicing" and t["level"] == 0.75]
    assert len(low) == s["config"]["detReps"]
    assert not {t["excerpt"] for t in low} & {"E1", "E2", "E3"}
