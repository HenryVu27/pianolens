"""D-12: QA of the DCML jc_bach_sonatas loader, leakage check of the R-08a renderer on its
label-free scores, and F-05c comparator scores (for R-08c).

    OMP_NUM_THREADS=1 uv run python scripts/check_dcml_jc_bach.py

Writes to ``data/interim/dcml_jc_bach/``:

* ``pieces.csv``: per movement (unfolded score): time signature, bars, onsets, phrase ends /
  starts / cadences (folded label rows and distinct unfolded beats), cadences by type,
  R-08a rendering size (chars, pointer bars), leakage hits, pilot stratum and suitability.
* ``cands.pkl``: per movement, the same dict as ``data/interim/phrase_f05c/cands.pkl``
  (``cand``, ``meta``, ``starts``, ``ends``, ``cadences``, ``proxy``, ``proxy_split``,
  ``downbeats``, ``onset_beats``, ``max_end``), so R-08a's ``score.py`` can run on it.
* ``comparators.csv``: F-05c rows (``boundary_prf``) per movement for the cadence detector
  (shipped Batik-fitted defaults), the proxy (last onset before each proxy start), the 4-bar
  grid and the DCML oracle.
* ``summary.txt``: the printed report.

The leakage check renders every movement with R-08a's ``common.render`` (not written to disk)
and fails if any DCML label string (length >= 3, from ``harmonies/``), any of R-08a's banned
words, or any Roman-numeral token appears.
"""

from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"))
warnings.filterwarnings("ignore")

from check_phrase_f05b import boundary_prf  # noqa: E402
from common import render  # noqa: E402  (R-08a renderer)
from render import BANNED_WORDS, ROMAN  # noqa: E402  (R-08a leakage vocabulary)

from pianolens.data import dcml_jc_bach as jc  # noqa: E402
from pianolens.features.cadence import cadence_candidates, cadence_phrase_ends  # noqa: E402
from pianolens.features.score_basis import BasisConfig, score_basis  # noqa: E402

OUT = ROOT / "data" / "interim" / "dcml_jc_bach"
TYPES = jc.CADENCE_TYPES
# R-08a pilot movements spanned 110-344 performed bars and 23k-88k rendered characters
R08A_BARS = (110, 344)
R08A_CHARS = (22_992, 88_116)


def leakage_hits(text: str, stem: str) -> dict[str, list[str]]:
    labels = {v for v in jc.label_strings(stem, min_len=3)
              if not re.fullmatch(r"[\d.,\s-]+", v)}
    return {
        "labels": sorted(v for v in labels
                         if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text)),
        "banned": [w for w in BANNED_WORDS if re.search(w, text, re.I)],
        "roman": sorted({m.group(0) for m in ROMAN.finditer(text)}),
    }


def stratum(stem: str, ts: str, all_stems: list[str]) -> str:
    """First movement 4/4 or 2/2 / first movement other metre / middle / finale duple / finale
    triple (R-08a's strata). The one-movement variation set (op. 17/1) and the minuet-trio
    pair that ends op. 5/2 are 'other'."""
    head = stem.split("_")[0]
    sib = sorted(s for s in all_stems if s.split("_")[0][:-1] == head[:-1])
    pos = sib.index(stem)
    if len(sib) == 1 or head in ("wa02op05no2c", "wa02op05no2d"):
        return "other"
    num = int(ts.split("/")[0])
    if pos == 0:
        return "first_4_4" if ts in ("4/4", "2/2") else "first_other"
    if pos == len(sib) - 1:
        return "finale_triple" if num in (3, 9) else "finale_duple"
    return "middle"


def cands_entry(score, ann) -> dict:
    bp = score_basis(score, config=BasisConfig(include_tension=False))
    cand, meta = cadence_candidates(score, basis=bp)
    me = (bp.notes["beat"] + bp.notes["duration_beat"]).groupby(bp.notes["beat"]).max()
    ph = bp.phrases
    ms = np.unique((bp.notes["beat"] - bp.notes["beat_in_bar"]).to_numpy())
    return {"cand": cand, "meta": meta, "starts": ann.starts, "ends": ann.ends,
            "cadences": ann.cadence_table(),
            "proxy": ph.loc[ph["source"] == "proxy", "start_beat"].tolist(),
            "proxy_split": ph["start_beat"].tolist(), "downbeats": ms.tolist(),
            "onset_beats": me.index.to_numpy(float), "max_end": me.to_numpy(float)}


def prev_onset(onsets: np.ndarray, beats) -> list[float]:
    out = []
    for b in beats:
        i = int(np.searchsorted(onsets, b - 1e-6)) - 1
        if i >= 0:
            out.append(float(onsets[i]))
    return out


def comparator_rows(stem: str, d: dict, score) -> list[dict]:
    res = cadence_phrase_ends(score)
    ob = d["onset_beats"]
    db = np.asarray(d["downbeats"], float)
    preds = {
        "cadence": (res.end_beats, res.starts),
        "proxy_last_onset": (prev_onset(ob, d["proxy"][1:]) + [float(ob[-1])], None),
        "proxy": (None, d["proxy"]),
        "grid4": (db[3::4].tolist(), db[::4].tolist()),
        "oracle_dcml_ends": (list(d["ends"]), list(d["starts"])),
    }
    bpb = d["meta"]["beats_per_bar"]
    first = float(ob[0])
    cad = d["cadences"]
    rows = []
    for m, (en, st) in preds.items():
        base = {"movement": stem, "method": m}
        for tol, tn in ((1.0, "1beat"), (bpb, "1bar")):
            if en is not None:
                rows.append({**base, "target": "end", "tol": tn,
                             **boundary_prf(en, d["ends"], tol, -np.inf)})
                rows.append({**base, "target": "cadence", "tol": tn,
                             **boundary_prf(en, cad["beat"].tolist(), tol, -np.inf)})
            if st is not None:
                rows.append({**base, "target": "start", "tol": tn,
                             **boundary_prf(st, d["starts"], tol, first)})
        if en is not None:
            for t in TYPES:
                g = cad[cad["cadence"] == t]
                r = boundary_prf(en, g["beat"].tolist(), 1.0, -np.inf)
                rows.append({**base, "target": f"cad_{t}", "tol": "1beat", "tp": r["tp"],
                             "n_true": r["n_true"], "n_pred": r["n_pred"]})
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stems = jc.pieces()
    rows, comp, cands, lines = [], [], {}, []
    leak_fail = 0
    for stem in stems:
        s = jc.load_score(stem)
        ann = jc.phrase_annotations(s)
        folded = jc.load_labels(stem)
        r = render(s, "X")
        hits = leakage_hits(r.text, stem)
        bad = any(hits.values())
        leak_fail += bad
        ts = jc.read_facet(stem, "measures")["timesig"].iloc[0]
        d = cands_entry(s, ann)
        cands[stem] = d
        comp += comparator_rows(stem, d, s)
        ca = ann.cadence_table()
        row = {"stem": stem, "piece_id": s.piece_id, "timesig": ts,
               "stratum": stratum(stem, ts, stems), "bars": len(s.measures),
               "onsets": len(d["onset_beats"]), "notes": len(s.notes),
               "ends_folded": int(folded["phraseend"].isin(["}", "}{"]).sum()),
               "cadences_folded": int((folded["cadence"] != "").sum()),
               "ends": len(ann.ends), "starts": len(ann.starts), "cadences": len(ca),
               **{f"n_{t}": int((ca["cadence"] == t).sum()) for t in TYPES},
               "labels_off_onset": ann.n_off_onset, "other_phrase_labels": ann.n_other,
               "render_chars": len(r.text), "pointer_bars": r.n_pointer_bars,
               "leak_labels": ";".join(hits["labels"]), "leak_banned": ";".join(hits["banned"]),
               "leak_roman": ";".join(hits["roman"])}
        row["pilot_size_ok"] = bool(R08A_BARS[0] <= row["bars"] <= R08A_BARS[1]
                                    and row["render_chars"] <= R08A_CHARS[1])
        rows.append(row)
        print(f"{stem}: {row['bars']} bars, {row['ends']} ends, {row['render_chars']:,} chars, "
              f"leak {'FAIL ' + str(hits) if bad else 'ok'}", flush=True)
    P = pd.DataFrame(rows)
    C = pd.DataFrame(comp)
    P.to_csv(OUT / "pieces.csv", index=False)
    C.to_csv(OUT / "comparators.csv", index=False)
    pd.to_pickle(cands, OUT / "cands.pkl")

    lines.append(f"{len(P)} movements; folded phrase ends {P['ends_folded'].sum()}, "
                 f"cadence labels {P['cadences_folded'].sum()}; unfolded distinct ends "
                 f"{P['ends'].sum()}, cadences {P['cadences'].sum()}")
    lines.append("cadences by type (unfolded): " + ", ".join(
        f"{t} {int(P[f'n_{t}'].sum())}" for t in TYPES))
    cols = ["stem", "stratum", "timesig", "bars", "onsets", "ends", "cadences", "n_HC",
            "render_chars", "pilot_size_ok"]
    lines.append("\n" + P[cols].to_string(index=False))
    main_t = C[C["target"].isin(["end", "start", "cadence"])]
    agg = main_t.groupby(["target", "tol", "method"])["F1"].mean().unstack("method").round(3)
    lines.append("\nMean F1 over all 29 movements (unfolded)\n" + agg.to_string())
    ok = P[P["pilot_size_ok"]]["stem"]
    agg2 = (main_t[main_t["movement"].isin(ok)].groupby(["target", "tol", "method"])["F1"]
            .mean().unstack("method").round(3))
    lines.append(f"\nMean F1 over the {len(ok)} pilot-size movements\n" + agg2.to_string())
    ct = C[C["target"].str.startswith("cad_") & (C["method"] == "cadence")]
    s_ = ct.groupby("target")[["tp", "n_true"]].sum()
    lines.append("\nDetector recall of DCML cadences by type (+-1 beat, pooled): " + ", ".join(
        f"{k[4:]} {int(v.tp)}/{int(v.n_true)}" for k, v in s_.iterrows()))
    e1 = C[(C["target"] == "end") & (C["tol"] == "1beat")].pivot(
        index="movement", columns="method", values="F1")
    lines.append("\nPer-movement end F1 +-1 beat\n" + e1.round(3).to_string())
    lines.append(f"\nLEAKAGE CHECK {'PASSED' if leak_fail == 0 else f'FAILED ({leak_fail})'}")
    txt = "\n".join(lines)
    (OUT / "summary.txt").write_text(txt + "\n")
    print(txt)
    return 1 if leak_fail else 0


if __name__ == "__main__":
    sys.exit(main())
