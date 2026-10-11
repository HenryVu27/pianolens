"""BL-37: does the parangonar ornament-step fallback in ``align_note_arrays`` change anything?

Run: ``OMP_NUM_THREADS=1 uv run python scripts/check_ornament_fallback_bl37.py [--workers 10]``

parangonar 3.3.3's ornament step crashes (numpy ``DTypePromotionError``) when no performed note is
left unmatched and a matched score note carries an ornament. BL-37 catches that error in
``pianolens.align.core.align_note_arrays`` and aligns again without the ornament step. This
script aligns every item twice in the same process with ``align()`` (default settings, repeat
path "auto"): once with the pre-BL-37 ``align_note_arrays`` (the crash propagates and is
recorded), once with the current one. For every item where the old code did not crash, the two
results must be identical (alignment list, chosen repeat path, candidate match ratios, score
note array). Items where it crashed are listed.

Sets: nASAP (every ASAP performance with a ground-truth alignment), the D-08 key-sensor mistake
set (100 clean copies and 300 mistake copies; the F-08 / BL-28 calibration inputs), the A-01
floor transcriptions (150; BL-28 floor tables) and Henry's A-01 takes (5 takes x 2
transcribers). Output: ``data/interim/bl37/ornament_fallback.json`` (gitignored).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "bl37"
MISTAKES = REPO / "data" / "processed" / "mistakes_v1"
HENRY = REPO / "data" / "interim" / "henry_takes"
_STATE: dict = {}


def _mod(name: str, file: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _quiet() -> None:
    import logging

    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def _old_align_note_arrays(score_na, perf_na, *, score_part=None, process_ornaments=True,
                           matcher=None):
    """``align_note_arrays`` as it was before BL-37 (no fallback)."""
    from parangonar import DualDTWNoteMatcher

    from pianolens.align import core

    matcher = matcher or DualDTWNoteMatcher()
    use_orn = process_ornaments and score_part is not None
    raw = matcher(score_na, perf_na, process_ornaments=use_orn, score_part=score_part)
    return [core._clean(a) for a in raw]


def _load(item: tuple) -> tuple:
    """(score, performance) for one item."""
    kind, key = item[0], item[1]
    if kind == "asap":
        from pianolens.data import asap

        row = asap.asap_index().set_index("performance_id", drop=False).loc[key]
        return asap.load_asap_score(row), asap.load_asap_performance(row)
    if kind == "d08":
        from pianolens.data import asap
        from pianolens.data.perturb import load_mistake_set

        if "get" not in _STATE:
            index, get = load_mistake_set(MISTAKES)
            _STATE.update(get=get, index=index.set_index("key"),
                          asap=asap.asap_index().set_index("performance_id", drop=False))
        perf, _ = _STATE["get"](key)
        arow = _STATE["asap"].loc[_STATE["index"].loc[key, "performance_id"]]
        return asap.load_asap_score(arow), perf
    from pianolens.report.io import load_performance, load_score

    if kind == "floor":
        import tempfile
        import zipfile

        from pianolens.data.pianocore import DEFAULT_ROOT, RAW_PREFIX, RAW_ZIP

        k, ref_id, rel = item[1], item[2], item[3]
        meta = json.loads((HENRY / "scores" / "scores.json").read_text())[k]
        sc = load_score(HENRY / "scores" / f"{k}_score.mxl", meta["piece_id"])
        with zipfile.ZipFile(DEFAULT_ROOT / RAW_ZIP) as z, tempfile.TemporaryDirectory() as td:
            f = Path(td) / "ref.mid"
            f.write_bytes(z.read(RAW_PREFIX + rel))
            perf = load_performance(f, "transcribed", meta["piece_id"], performance_id=ref_id)
        return sc, perf
    k, t = item[1], item[2]  # henry
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())[k]
    sc = load_score(HENRY / "scores" / f"{k}_score.mxl", meta["piece_id"])
    perf = load_performance(HENRY / "transcribed" / t / f"{k}.mid", "transcribed",
                            meta["piece_id"], performance_id=f"{k}:{t}")
    return sc, perf


def one(item: tuple) -> dict:
    _quiet()
    from pianolens.align import core

    sc, perf = _load(item)
    new_fn = core.align_note_arrays
    core.align_note_arrays = _old_align_note_arrays
    crashed, err = False, ""
    try:
        old = core.align(sc, perf)
    except np.exceptions.DTypePromotionError as e:
        crashed, err, old = True, repr(e)[:120], None
    finally:
        core.align_note_arrays = new_fn
    new = core.align(sc, perf)
    out = {"set": item[0], "key": str(item[1] if item[0] != "floor" else item[2]),
           "crashed_before": crashed, "error": err}
    if old is not None:
        out["identical"] = bool(old.alignment == new.alignment and old.variant == new.variant
                                and old.candidates == new.candidates
                                and np.array_equal(old.score_note_array, new.score_note_array))
    return out


def items() -> list[tuple]:
    from pianolens.data import asap
    from pianolens.data.perturb import load_mistake_set

    ai = asap.asap_index()
    out = [("asap", str(r["performance_id"])) for _, r in ai.iterrows()
           if asap.asap_alignment_path(r).is_file()]
    index, _ = load_mistake_set(MISTAKES)
    out += [("d08", str(k)) for k in index["key"]]
    f08c = _mod("f08c", "calibrate_expert_check_f08c.py")
    out += [("floor", k, ref_id, rel) for k, ref_id, rel, _t in f08c.floor_jobs()]
    meta = json.loads((HENRY / "scores" / "scores.json").read_text())
    out += [("henry", k, t) for k in sorted(meta) for t in ("transkun", "aria_amt")]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    _quiet()
    OUT.mkdir(parents=True, exist_ok=True)
    its = items()
    if args.limit:
        its = its[:args.limit]
    print(len(its), "items", flush=True)
    rows, failed = [], []
    with ProcessPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, it): it for it in its}
        for k, fu in enumerate(as_completed(futs)):
            try:
                rows.append(fu.result())
            except Exception as e:  # noqa: BLE001 - count failures
                failed.append((str(futs[fu][:3]), repr(e)[:200]))
            if k % 100 == 0:
                print("done", k, len(failed), flush=True)
    summ: dict = {"n_items": len(its), "failed_other": failed, "by_set": {}}
    for s in sorted({r["set"] for r in rows}):
        g = [r for r in rows if r["set"] == s]
        ok = [r for r in g if not r["crashed_before"]]
        summ["by_set"][s] = {"n": len(g), "crashed_before": sum(r["crashed_before"] for r in g),
                             "crashed_keys": sorted(r["key"] for r in g if r["crashed_before"]),
                             "n_not_crashed": len(ok),
                             "identical": sum(r["identical"] for r in ok),
                             "not_identical_keys": sorted(r["key"] for r in ok
                                                          if not r["identical"])}
    (OUT / "ornament_fallback.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
