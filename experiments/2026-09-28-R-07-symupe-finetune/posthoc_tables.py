"""R-07 post-hoc tables asked for by the audits (exploratory; not pre-registered).

1. `transcriber` (AUDIT.md section 8): E - frozen and pt_E - pt_frozen on R10u and R10s, per
   PianoCoRe capture model. The audit found E's R10u gain concentrated in Aria-AMT transcriptions
   (77% of E's selected training rows). Transcriber and source corpus are confounded (Aria-AMT =
   Aria-MIDI, Transkun V2 = PERiScoPe), so a stratum is a corpus as much as a transcriber.
   Method: the R10 rows of `results/<set>/a_per_rendition.csv` are joined to
   `data/raw/pianocore/metadata.csv` by the PianoCoRe id at the end of each stem
   (`<piece>__PianoCoRe_NNNNNN`); the paired difference is then computed within each capture
   model with `job/summarize_eval.py`'s own `boot_ci` (two-way passage x performer bootstrap,
   2,000 resamples, seed 0, unweighted mean over works), as for the pooled (a) statistic.
2. `h1b_groups` (AUDIT.md section 9 item 4): R10u H1b-preview medians split into the 74
   pre-registered unseen R-02 pieces, the 7 pieces paired in PERiScoPe, and the 4 unpaired
   work-mates, from the committed `results/R10u/h1b.csv` and `split/pieces.csv`.

    uv run python experiments/2026-09-28-R-07-symupe-finetune/posthoc_tables.py [TABLE ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from pair_ci import pair  # noqa: E402

PAIRS = (("E", "frozen"), ("pt_E", "pt_frozen"))


def transcriber() -> pd.DataFrame:
    meta = pd.read_csv(ROOT / "data/raw/pianocore/metadata.csv", usecols=["id", "capture_model"])
    cm = meta.set_index("id")["capture_model"]
    rows = []
    for s in ("R10u", "R10s"):
        A = pd.read_csv(HERE / "results" / s / "a_per_rendition.csv")
        pc_id = A["stem"].str.extract(r"(PianoCoRe_\d+)$", expand=False)
        assert pc_id.notna().all(), f"{s}: stem without a PianoCoRe id"
        A["capture_model"] = pc_id.map(cm)
        assert A["capture_model"].notna().all(), f"{s}: id missing from metadata"
        for arm, base in PAIRS:
            for model, g in A.groupby("capture_model"):
                c = pair(g, arm, base)
                rows.append({"set": s, "diff": f"{arm} - {base}", "capture_model": model,
                             "n": c["n"], "n_works": g["work"].nunique(),
                             "point": c["composite"][0], "lo": c["composite"][1],
                             "hi": c["composite"][2]})
    return pd.DataFrame(rows)


def h1b_groups() -> pd.DataFrame:
    P = pd.read_csv(HERE / "split/pieces.csv").set_index("piece_id")
    H = pd.read_csv(HERE / "results/R10u/h1b.csv")
    r = P.reindex(H["passage"])
    assert r.index.isin(P.index).all(), "h1b passage missing from split/pieces.csv"
    paired = (r["n_periscope_paired"].to_numpy() > 0) | r["periscope_possible"].to_numpy(bool)
    r02 = r["r02"].to_numpy(bool)
    H["group"] = ["paired" if p else ("unseen" if u else "workmate_unpaired")
                  for p, u in zip(paired, r02, strict=True)]
    cols = ["captured", "r2c_velocity", "r2c_log_ioi"]
    out = H.groupby(["group", "arm"])[cols].median()
    out["n_pieces"] = H.groupby(["group", "arm"])["passage"].nunique()
    return out.reset_index()


def main(argv: list[str]) -> None:
    pd.set_option("display.width", 200)
    which = argv or ["transcriber", "h1b_groups"]
    if "h1b_groups" in which:
        print(h1b_groups().round(3).to_string(index=False))
    if "transcriber" in which:
        print(transcriber().round(4).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
