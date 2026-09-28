"""D-13: QA of the shared DCML loader on the five R-08d Romantic corpora, leakage check of the
R-08a renderer on their label-free scores, and F-05c comparator scores (for R-08d).

    OMP_NUM_THREADS=1 uv run python scripts/check_dcml_romantic.py [corpus ...]

Corpora (default all five): chopin_mazurkas, grieg_lyric_pieces, tchaikovsky_seasons,
schumann_kinderszenen, liszt_pelerinage (``pianolens.data.dcml.ROMANTIC``).

Writes to ``data/interim/dcml_romantic/``:

* ``pieces.csv``: one row per movement (unfolded score): corpus, stem, piece id, time
  signatures, meter class (``simple`` / ``compound`` / ``other``, ``meter_changes``), folded and
  unfolded bars, whether the unfolding equals ``metadata.tsv``, onsets, notes against ms3's
  ``n_onsets``, phrase ends / starts / cadences (folded label rows and distinct unfolded
  beats), cadences by type, labels off onsets, R-08a rendering size (chars, pointer bars),
  leakage hits, identity hits (composer or title words in the rendering; reported, not a
  failure), and the R-08d eligibility flags: ``eligible`` = has labels and at least 5 folded
  phrase ends (DECISIONS 2026-09-28, R-08d design); ``simple_meter``; ``eligible_simple``.
* ``cands.pkl``: per movement (key: ``score_id``), the same dict as
  ``data/interim/phrase_f05c/cands.pkl`` so R-08a's ``score.py`` can run on it.
* ``comparators.csv``: F-05c rows (``boundary_prf``) per movement for the cadence detector
  (shipped Batik-fitted defaults), the proxy, the 4-bar grid and the DCML oracle.
* ``summary.txt``: the printed report.

The leakage check renders every labelled movement with R-08a's ``common.render`` (not written
to disk) and fails if any DCML label string (length >= 3, from ``harmonies/``), any of R-08a's
banned words, or any Roman-numeral token appears.
"""

from __future__ import annotations

import re
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "2026-09-28-R-08a-llm-phrase-pilot"))
warnings.filterwarnings("ignore")

from check_dcml_jc_bach import R08A_BARS, R08A_CHARS, cands_entry, comparator_rows  # noqa: E402
from common import render  # noqa: E402  (R-08a renderer)
from render import BANNED_WORDS, ROMAN  # noqa: E402  (R-08a leakage vocabulary)

from pianolens.data import dcml  # noqa: E402

OUT = ROOT / "data" / "interim" / "dcml_romantic"
TYPES = dcml.CADENCE_TYPES
MIN_ENDS = 5  # R-08d design: exclude movements with fewer than 5 phrase ends


def leakage_hits(text: str, corpus: str, stem: str) -> dict[str, list[str]]:
    labels = {v for v in dcml.label_strings(corpus, stem, min_len=3)
              if not re.fullmatch(r"[\d.,\s-]+", v)}
    return {
        "labels": sorted(v for v in labels
                         if re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w])", text)),
        "banned": [w for w in BANNED_WORDS if re.search(w, text, re.I)],
        "roman": sorted({m.group(0) for m in ROMAN.finditer(text)}),
    }


STOP = {"From", "With", "Tempo", "Quasi", "Mazurkas", "Pieces", "Lyric", "Lyrische", "Stücke",
        "Book", "Seasons", "Months", "Scenes", "Années", "Pèlerinage", "Année"}


def identity_words(corpus: str, md: pd.Series) -> set[str]:
    """Composer surname and capitalised title words (4+ letters) that would name the piece;
    matched case-sensitively."""
    c = dcml.get_corpus(corpus)
    words = {c.composer.split()[-1]}
    for col in ("workTitle", "movementTitle", "title_text"):
        v = str(md.get(col, "") or "")
        if v and v != "nan":
            words |= set(re.findall(r"\b[^\W\d_a-z][^\W\d_]{3,}", v))
    return words - STOP


def meter_class(ts: str) -> str:
    num = int(ts.split("/")[0])
    return "simple" if num in (2, 3, 4) else "compound" if num in (6, 9, 12) else "other"


def main(corpora: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, comp, cands, lines = [], [], {}, []
    leak_fail = 0
    for corpus in corpora:
        md = dcml.metadata(corpus).set_index("piece")
        labelled = set(dcml.pieces(corpus, labelled=True))
        t0 = time.time()
        for stem in dcml.pieces(corpus):
            s = dcml.load_score(corpus, stem)
            f = dcml.load_score(corpus, stem, unfold=False)
            ms = dcml.read_facet(corpus, stem, "measures")
            tss = list(dict.fromkeys(ms["timesig"]))
            classes = sorted({meter_class(t) for t in tss})
            row = {"corpus": corpus, "stem": stem, "score_id": s.score_id,
                   "piece_id": s.piece_id, "timesig": " ".join(tss),
                   "meter": classes[0] if len(classes) == 1 else "mixed",
                   "meter_changes": len(tss) > 1, "simple_meter": classes == ["simple"],
                   "bars_folded": len(f.measures), "bars": len(s.measures),
                   "unfold_validated": bool(s.meta["unfold_validated"]),
                   "notes_folded": len(f.notes), "n_onsets_ms3": int(md.loc[stem, "n_onsets"]),
                   "orphan_ties": f.meta["n_orphan_ties"], "gap_ties": f.meta["n_gap_ties"],
                   "notes": len(s.notes), "has_labels": stem in labelled}
            if stem not in labelled:
                row.update(eligible=False, eligible_simple=False)
                rows.append(row)
                print(f"{corpus}/{stem}: no harmonies table, skipped", flush=True)
                continue
            ann = dcml.phrase_annotations(s)
            folded = dcml.load_labels(corpus, stem)
            r = render(s, "X")
            hits = leakage_hits(r.text, corpus, stem)
            bad = any(hits.values())
            leak_fail += bad
            ident = sorted(w for w in identity_words(corpus, md.loc[stem])
                           if re.search(r"\b" + re.escape(w) + r"\b", r.text))
            ca = ann.cadence_table()
            ends_folded = int(folded["phraseend"].isin(["}", "}{"]).sum())
            row.update({
                "ends_folded": ends_folded,
                "starts_folded": int(folded["phraseend"].isin(["{", "}{"]).sum()),
                "cadences_folded": int((folded["cadence"] != "").sum()),
                "ends": len(ann.ends), "starts": len(ann.starts), "cadences": len(ca),
                **{f"n_{t}": int((ca["cadence"] == t).sum()) for t in TYPES},
                "labels_off_onset": ann.n_off_onset, "labels_unmapped": ann.n_unmapped,
                "other_phrase_labels": ann.n_other,
                "render_chars": len(r.text), "pointer_bars": r.n_pointer_bars,
                "leak_labels": ";".join(hits["labels"]), "leak_banned": ";".join(hits["banned"]),
                "leak_roman": ";".join(hits["roman"]), "identity_hits": ";".join(ident),
            })
            row["pilot_size_ok"] = bool(R08A_BARS[0] <= row["bars"] <= R08A_BARS[1]
                                        and row["render_chars"] <= R08A_CHARS[1])
            row["eligible"] = ends_folded >= MIN_ENDS
            row["eligible_simple"] = row["eligible"] and row["simple_meter"]
            try:
                d = cands_entry(s, ann)
                cands[s.score_id] = d
                cr = comparator_rows(stem, d, s)
                for x in cr:
                    x["corpus"] = corpus
                comp += cr
                row["onsets"] = len(d["onset_beats"])
            except Exception as e:  # noqa: BLE001 - record and continue
                row["detector_error"] = repr(e)[:200]
            rows.append(row)
            print(f"{corpus}/{stem}: {row['bars']} bars, {row['ends']} ends, "
                  f"{row['render_chars']:,} chars, leak "
                  f"{'FAIL ' + str(hits) if bad else 'ok'}", flush=True)
        print(f"{corpus}: {time.time() - t0:.0f}s", flush=True)
    P = pd.DataFrame(rows)
    C = pd.DataFrame(comp)
    P.to_csv(OUT / "pieces.csv", index=False)
    C.to_csv(OUT / "comparators.csv", index=False)
    pd.to_pickle(cands, OUT / "cands.pkl")

    L = P[P["has_labels"]]
    for corpus, g in P.groupby("corpus", sort=False):
        gl = g[g["has_labels"]]
        n_same = int((g["notes_folded"] == g["n_onsets_ms3"]).sum())
        lines.append(
            f"{corpus}: {len(g)} movements ({len(gl)} labelled); folded phrase ends "
            f"{int(gl['ends_folded'].sum())}, cadence labels {int(gl['cadences_folded'].sum())}; "
            f"unfolded distinct ends {int(gl['ends'].sum())}, "
            f"cadences {int(gl['cadences'].sum())}; notes == ms3 n_onsets {n_same}/{len(g)}; "
            f"unfold == metadata {int(g['unfold_validated'].sum())}/{len(g)}; "
            f"eligible (>= {MIN_ENDS} ends) {int(gl['eligible'].sum())}, of which simple meter "
            f"{int(gl['eligible_simple'].sum())}")
    lines.append("cadences by type (unfolded): " + ", ".join(
        f"{t} {int(L[f'n_{t}'].sum())}" for t in TYPES))
    lines.append(f"labels off onsets (unfolded placements): {int(L['labels_off_onset'].sum())}; "
                 f"unmapped: {int(L['labels_unmapped'].sum())}")
    cols = ["corpus", "stem", "timesig", "meter", "bars", "unfold_validated", "ends_folded",
            "ends", "cadences", "render_chars", "eligible", "eligible_simple", "identity_hits"]
    lines.append("\n" + L[cols].to_string(index=False))
    if len(C):
        main_t = C[C["target"].isin(["end", "start", "cadence"])]
        agg = (main_t.groupby(["corpus", "target", "tol", "method"])["F1"].mean()
               .unstack("method").round(3))
        lines.append("\nMean F1 per corpus, all labelled movements (unfolded)\n" + agg.to_string())
        el = L[L["eligible"]]["stem"]
        e1 = main_t[(main_t["target"] == "end") & (main_t["tol"] == "1beat")]
        agg2 = (e1[e1["movement"].isin(el)].groupby("corpus")[["method", "F1"]]
                .apply(lambda x: x.groupby("method")["F1"].mean()).round(3))
        lines.append("\nMean end F1 +-1 beat over eligible movements\n" + agg2.to_string())
        ct = C[C["target"].str.startswith("cad_") & (C["method"] == "cadence")]
        s_ = ct.groupby("target")[["tp", "n_true"]].sum()
        lines.append("\nDetector recall of DCML cadences by type (+-1 beat, pooled): " + ", ".join(
            f"{k[4:]} {int(v.tp)}/{int(v.n_true)}" for k, v in s_.iterrows()))
    if "detector_error" in P:
        errs = P[P["detector_error"].notna()]
        lines.append(f"\ndetector errors: {len(errs)}")
        for _, r in errs.iterrows():
            lines.append(f"  {r['corpus']}/{r['stem']}: {r['detector_error']}")
    lines.append(f"\nLEAKAGE CHECK {'PASSED' if leak_fail == 0 else f'FAILED ({leak_fail})'}")
    txt = "\n".join(lines)
    (OUT / "summary.txt").write_text(txt + "\n")
    print(txt)
    return 1 if leak_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(dcml.ROMANTIC)))
