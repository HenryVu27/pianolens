"""F-05e: per-phrase tempo shaping and phrase-aware coherence with LLM phrase boundaries.

    OMP_NUM_THREADS=1 uv run python experiments/2026-09-28-F-05e-llm-phrase-measures/run.py \
        [compute] [summary]

``compute`` writes one parquet of rows per work unit to ``artifacts/rows/`` (resumable: a unit
whose file exists is skipped), ``summary`` builds ``artifacts/summary.txt`` and the tables.
See README (pre-registered) for sources, rule and threats.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ART = HERE / "artifacts"
ROWS = ART / "rows"
EXP = ROOT / "experiments"
R08A = EXP / "2026-09-28-R-08a-llm-phrase-pilot"
R08B = EXP / "2026-09-28-R-08b-llm-memorisation-control"
R08D = EXP / "2026-09-28-R-08d-llm-romantic-repertoire"
F05C = ROOT / "data" / "interim" / "phrase_f05c"
SEED = 20261002
N_PERF = 30
N_BOOT = 10_000
MARGIN = -0.10
MIN_AGREE = 0.80
MINI = "_mini_refined.mid"  # abridged score (excluded); full = any other refined score

sys.path.insert(0, str(R08A))
sys.path.insert(0, str(R08B))
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

BATIK = {"M1": "kv330_2", "M2": "kv333_1", "M3": "kv533_1", "M4": "kv330_3", "M5": "kv457_3"}
PC_MOZART = {"M1": "mozart_k330_mv2", "M2": "mozart_k333_mv1", "M4": "mozart_k330_mv3",
             "M5": "mozart_k457_mv3"}
ROMANTIC = {"R1": "tchaikovsky_op37a_no6", "R2": "chopin_op7_no4", "R3": "schumann_op15_no7"}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- boundaries


def _llm_df(mapped: pd.DataFrame) -> dict:
    s = sorted(mapped.loc[mapped["type"] == "phrase_start", "beat"].astype(float))
    e = mapped[mapped["type"] == "phrase_end"]
    return {"starts": s, "ends": sorted(e["beat"].astype(float)),
            "cad_ends": sorted(e.loc[e["cadence"].isin(["PAC", "HC"]), "beat"].astype(float))}


def movement_sources() -> dict[str, dict]:
    """Per movement id: source-score boundaries (DCML, detector, proxy, grid) and the mapped
    LLM runs, all in the performed-score beats the R-08 scorers use."""
    A = _load("r08a_score_f05e", R08A / "score.py")
    B = _load("r08b_score_f05e", R08B / "score.py")
    D = _load("r08d_score_f05e", R08D / "score.py")
    from check_phrase_f05c import _cfg_from_fit, cadence_bounds

    out: dict[str, dict] = {}
    MA = A.movement_inputs()
    cfg = _cfg_from_fit()
    for mid, mv in MA.items():
        d = mv["d"]
        cst, cen = cadence_bounds(d, cfg)
        out[mid] = {"kind": "batik", "stem": mv["stem"], "bpb": d["meta"]["beats_per_bar"],
                    "onsets": np.asarray(d["onset_beats"], float),
                    "dcml": (list(d["starts"]), list(d["ends"])),
                    "cadence": (list(cst), list(cen)),
                    "proxy": list(d["proxy_split"]),
                    "grid4": list(np.asarray(d["downbeats"], float)[::4]), "llm": {}}
        for run, folder in (("a", R08A / "annotations"), ("B1", R08B / "annotations_B1"),
                            ("B2", R08B / "annotations_B2")):
            ann = json.loads((folder / f"{mid}.json").read_text())
            df, _ = A.map_events(ann["events"], mv)
            out[mid]["llm"][run] = _llm_df(df)
    for did, mv in B.inputs_A().items():
        mid = mv["param"]["m_id"]
        ann = json.loads((R08B / "annotations_A" / f"{did}.json").read_text())
        df, _ = B.S.map_events(ann["events"], mv)
        out[mid]["llm"]["A_disguised"] = _llm_df(df)
    for rid, mv in D.movement_inputs().items():
        if rid not in ROMANTIC:
            continue
        d = mv["d"]
        cen, cst = D.detector(mv["corpus"], mv["stem"])
        out[rid] = {"kind": "dcml", "corpus": mv["corpus"], "stem": mv["stem"],
                    "bpb": d["meta"]["beats_per_bar"],
                    "onsets": np.asarray(d["onset_beats"], float),
                    "dcml": (list(mv["gt"]["starts"]), list(mv["gt"]["ends"])),
                    "cadence": (list(cst), list(cen)), "llm": {}}
        for run in ("A", "B"):
            ann = json.loads((R08D / f"annotations_{run}" / f"{rid}.json").read_text())
            df, _ = D.S.map_events(ann["events"], mv)
            out[rid]["llm"][run] = _llm_df(df)
    return out


def cad_level(llm: dict, bpb: float) -> list[float]:
    """First LLM start + every LLM start within 2 bars after an LLM PAC/HC phrase end."""
    st = llm["starts"]
    if not st:
        return []
    ce = np.asarray(llm["cad_ends"], float)
    keep = [st[0]] + [s for s in st[1:] if ((ce <= s + 1e-6) & (ce >= s - 2 * bpb)).any()]
    return sorted(set(keep))


def oracle_group(llm_starts, dcml_starts, bpb: float) -> list[float]:
    """For each DCML start, the nearest LLM start within +-1 bar (diagnostic only)."""
    ls = np.asarray(llm_starts, float)
    out = set()
    for t in dcml_starts:
        if len(ls) and np.abs(ls - t).min() <= bpb + 1e-6:
            out.add(float(ls[np.argmin(np.abs(ls - t))]))
    return sorted(out)


def ends_for(starts, ends) -> list[float]:
    """Ends of a merged segmentation: the last source end in each retained phrase's span
    before the next retained start, plus the last end overall."""
    e = np.asarray(sorted(ends), float)
    out = []
    for a, b in zip(starts[:-1], starts[1:], strict=True):
        m = e[(e > a + 1e-6) & (e <= b + 1e-6)]
        if len(m):
            out.append(float(m[-1]))
    if len(e):
        out.append(float(e[-1]))
    return sorted(set(out))


# --------------------------------------------------------------------------- score mapping


def _onset_sets(notes) -> tuple[np.ndarray, np.ndarray]:
    ob = np.asarray(notes["onset_beat"], float).round(4)
    pitch = np.asarray(notes["pitch"], int)
    u, inv = np.unique(ob, return_inverse=True)
    M = np.zeros((len(u), 128), np.float32)
    M[inv, pitch] = 1
    return u, M


def score_map(src_notes, tgt_notes) -> dict:
    """DTW over unique onsets, cost 1 - Jaccard of the pitch sets; source onset -> target."""
    import librosa

    su, SM = _onset_sets(src_notes)
    tu, TM = _onset_sets(tgt_notes)
    inter = SM @ TM.T
    union = SM.sum(1)[:, None] + TM.sum(1)[None, :] - inter
    C = 1 - inter / np.maximum(union, 1)
    _, wp = librosa.sequence.dtw(C=C, backtrack=True)
    wp = wp[::-1]
    first: dict[int, int] = {}
    for i, j in wp:
        first.setdefault(int(i), int(j))
    idx = np.array([first[i] for i in range(len(su))])
    exact = np.array([C[i, idx[i]] < 1e-6 for i in range(len(su))])
    covered = np.zeros(len(tu), bool)
    for i, j in wp:
        if C[i, j] < 1e-6:
            covered[j] = True
    return {"su": su, "tu": tu, "idx": idx, "exact": exact, "onset_agree": float(exact.mean()),
            "target_coverage": float(covered.mean())}


def map_beats(beats, mp: dict) -> tuple[list[float], list[bool]]:
    out, ok = [], []
    for x in beats:
        i = int(np.argmin(np.abs(mp["su"] - x)))
        out.append(float(mp["tu"][mp["idx"][i]]))
        ok.append(bool(mp["exact"][i]))
    return out, ok


# --------------------------------------------------------------------------- measures


def source_sets(src: dict, to_target, bpb_t: float, end_t: float, native: dict) -> dict:
    """name -> (starts, ends or None, run) in target beats; merged variants merged on target."""
    from pianolens.features.shaping import merge_short_phrases

    def m(st, k):
        return merge_short_phrases(st, k, bpb_t, end_t)

    S: dict[str, tuple] = {}
    ds, de = (to_target(x) for x in src["dcml"])
    cs, ce = (to_target(x) for x in src["cadence"])
    S["dcml"] = (ds, de, "")
    S["dcml_m4"] = (m(ds, 4), ends_for(m(ds, 4), de), "")
    S["cadence"] = (cs, ce, "")
    S["cadence_m4"] = (m(cs, 4), ends_for(m(cs, 4), ce), "")
    S["proxy"] = (native["proxy"], None, "")
    S["grid4"] = (native["grid4"], None, "")
    for run, llm in src["llm"].items():
        ls, le = to_target(llm["starts"]), to_target(llm["ends"])
        S[f"llm|{run}"] = (ls, le, run)
        for k in (4, 8):
            S[f"llm_m{k}|{run}"] = (m(ls, k), ends_for(m(ls, k), le), run)
        cl = to_target(cad_level(llm, src["bpb"]))
        S[f"llm_cad|{run}"] = (cl, ends_for(cl, le), run)
        S[f"llm_oracle|{run}"] = (to_target(oracle_group(llm["starts"], src["dcml"][0],
                                                         src["bpb"])), None, run)
    return {k: (sorted(set(v[0])), None if v[1] is None else sorted(set(v[1])), v[2])
            for k, v in S.items()}


COH_SOURCES = ("dcml", "llm", "llm_m4", "cadence", "proxy")


class Bases:
    """score_basis per (score, source), built once and reused across performances."""

    def __init__(self):
        self.cache: dict = {}

    def get(self, score, key: str, starts, ends):
        from check_phrase_f05b import NOSPLIT

        from pianolens.features.score_basis import BasisConfig, score_basis

        k = (score.score_id, key)
        if k not in self.cache:
            if ends is None:
                self.cache[k] = score_basis(score)
            else:
                self.cache[k] = score_basis(
                    score, phrase_boundaries_beats=starts, phrase_ends_beats=ends,
                    config=BasisConfig(phrase_detail=True, phrase_max_bars=NOSPLIT))
        return self.cache[k]


def measure_performance(ap, sets: dict, bases: Bases, coherence: bool = True) -> list[dict]:
    from check_phrase_f05b import feature_cols

    from pianolens.features.shaping import (
        ShapingConfig,
        _cv_ridge,
        channel_data,
        phrase_tempo_shaping,
    )
    from pianolens.features.tempo import tempo_model

    cfg = ShapingConfig(clip_to_train=True)
    tc = tempo_model(ap)
    rows = []
    for name, (starts, ends, run) in sets.items():
        src = name.split("|")[0]
        row = {"source": src, "run": run, "n_starts": len(starts)}
        if len(starts) >= 1:
            s = phrase_tempo_shaping(ap, starts, tempo=tc).summary
            row.update({k: s[k] for k in ("n_phrases", "concave_share", "null_concave_share",
                                          "concave_excess", "arc_r2_within",
                                          "null_arc_r2_within", "arc_r2_excess")})
        if coherence and src in COH_SOURCES:
            b = bases.get(ap.score, name, starts, None if src == "proxy" else ends)
            df = channel_data(ap, b, tc, cfg)["tempo"]
            X = df[feature_cols(b.groups, False)].to_numpy(float)
            row["tempo_r2_nm"] = _cv_ridge(X, df["y"].to_numpy(float),
                                           df["measure_number"].to_numpy(), cfg)[1]
        rows.append(row)
    return rows


def _native(score) -> dict:
    from pianolens.features.score_basis import score_basis

    b = score_basis(score)
    n = b.notes
    db = np.unique((n["beat"] - n["beat_in_bar"]).round(6).to_numpy(float))
    return {"proxy": b.phrases["start_beat"].astype(float).tolist(), "grid4": list(db[::4])}


# --------------------------------------------------------------------------- work units


def unit_batik(src_all: dict) -> pd.DataFrame:
    from pianolens.data import batik_mozart as bm
    from pianolens.features.tempo import _beats_per_bar

    rows = []
    bases = Bases()
    stems = {v: k for k, v in BATIK.items()}
    for ap in bm.iter_aligned(musicxml_score=True, stems=set(stems)):
        mid = stems[bm.stem_of(ap.score)]
        src = src_all[mid]
        bpb = float(_beats_per_bar(ap.score))
        end = float(ap.score.notes["onset_beat"].max()) + 1
        native = {"proxy": src["proxy"], "grid4": src["grid4"]}
        sets = source_sets(src, lambda x: [float(v) for v in x], bpb, end, native)
        for r in measure_performance(ap, sets, bases):
            rows.append({"set": "batik", "movement": mid, "piece": src["stem"],
                         "performance": ap.performance.performance_id, **r})
    return pd.DataFrame(rows)


def draw_rows(pid: str) -> pd.DataFrame:
    from pianolens.data.pianocore import PianoCoRe

    idx = PianoCoRe(tier="a").index
    r = idx[(idx["piece_id"] == pid) & ~idx["refined_score_midi_path"].str.endswith(MINI)]
    assert r["refined_score_midi_path"].nunique() == 1, pid
    r = r.sort_values("id")
    rng = np.random.default_rng(SEED)
    take = np.sort(rng.choice(len(r), size=min(N_PERF, len(r)), replace=False))
    return r.iloc[take]


def unit_pianocore(mid: str, pid: str, src: dict) -> pd.DataFrame:
    from pianolens.data.pianocore import PianoCoRe
    from pianolens.features.tempo import _beats_per_bar

    pc = PianoCoRe(tier="a")
    rows_pc = draw_rows(pid)
    if src["kind"] == "batik":
        from pianolens.data import batik_mozart as bm

        src_score = bm.load_aligned(src["stem"], musicxml_score=True).score
    else:
        from pianolens.data import dcml

        src_score = dcml.load_score(src["corpus"], src["stem"])
    so = np.unique(np.asarray(src_score.notes["onset_beat"], float).round(4))
    assert np.allclose(so, np.unique(src["onsets"].round(4)), atol=1e-3), mid
    tscore = pc.load_score(rows_pc.iloc[0])
    mp = score_map(src_score.notes, tscore.notes)
    bpb = float(_beats_per_bar(tscore))
    end = float(tscore.notes["onset_beat"].max()) + 1
    agree_log: list[bool] = []

    def to_t(x):
        b, ok = map_beats(x, mp)
        agree_log.extend(ok)
        return b

    sets = source_sets(src, to_t, bpb, end, _native(tscore))
    b_agree = float(np.mean(agree_log)) if agree_log else np.nan
    info = {"set": "pianocore_mozart" if src["kind"] == "batik" else "pianocore_romantic",
            "movement": mid, "piece": pid, "boundary_agree": b_agree,
            "onset_agree": mp["onset_agree"], "target_coverage": mp["target_coverage"],
            "n_drawn": len(rows_pc)}
    print(mid, pid, {k: v for k, v in info.items() if k not in ("set",)}, flush=True)
    bases = Bases()
    rows = []
    for _, row in rows_pc.iterrows():
        ap = pc.load(row)
        assert ap.score.score_id == tscore.score_id
        for r in measure_performance(ap, sets, bases):
            rows.append({**info, "performance": ap.performance.performance_id, **r})
    return pd.DataFrame(rows)


def _work(args) -> str:
    name, fn, a = args
    out = ROWS / f"{name}.parquet"
    if out.exists():
        return f"{name}: cached"
    t0 = time.time()
    df = fn(*a)
    df.to_parquet(out)
    return f"{name}: {len(df)} rows, {time.time() - t0:.0f}s"


def compute() -> None:
    ROWS.mkdir(parents=True, exist_ok=True)
    src = movement_sources()
    slim = {k: v for k, v in src.items()}
    (ART / "boundaries.json").write_text(json.dumps(
        {k: {"dcml_starts": len(v["dcml"][0]), "cadence_starts": len(v["cadence"][0]),
             "llm_starts": {r: len(x["starts"]) for r, x in v["llm"].items()}}
         for k, v in slim.items()}, indent=1))
    jobs = [("batik", unit_batik, (src,))]
    jobs += [(f"pc_{m}", unit_pianocore, (m, p, src[m])) for m, p in ROMANTIC.items()]
    jobs += [(f"pc_{m}", unit_pianocore, (m, p, src[m])) for m, p in PC_MOZART.items()]
    with ProcessPoolExecutor(max_workers=6) as ex:
        for msg in ex.map(_work, jobs):
            print(msg, flush=True)


# --------------------------------------------------------------------------- summary


def t_int(x) -> tuple[float, float]:
    from scipy import stats as st

    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return (np.nan, np.nan)
    h = st.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean() - h), float(x.mean() + h)


def boot(x, rng) -> tuple[float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    bs = x[rng.integers(0, len(x), (N_BOOT, len(x)))].mean(1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def harness(R: pd.DataFrame) -> str:
    ref = pd.read_csv(F05C / "phrase_tempo.csv")
    bad, lines = 0, []
    b = R[R["set"] == "batik"]
    for mid, stem in BATIK.items():
        for mine, theirs in (("dcml", "ann"), ("cadence", "cadence"), ("proxy", "proxy_split"),
                             ("grid4", "grid4")):
            x = b[(b["movement"] == mid) & (b["source"] == mine)]["concave_excess"].iloc[0]
            y = ref[(ref["movement"] == stem) & (ref["bounds"] == theirs)]["concave_excess"]
            y = float(y.iloc[0])
            same = np.isclose(x, y, atol=1e-9)
            bad += not same
            lines.append(f"{mid} {stem} {mine:8s} here {x:+.4f} F-05c {y:+.4f} "
                         f"{'OK' if same else 'MISMATCH'}")
    return ("Harness (Batik concave_excess vs F-05c phrase_tempo.csv): "
            + ("PASSED" if bad == 0 else f"FAILED ({bad})") + "\n" + "\n".join(lines))


def per_movement(R: pd.DataFrame, col: str) -> pd.DataFrame:
    """movement x source: mean over performances within run, then over runs."""
    g = R.groupby(["set", "movement", "source", "run"])[col].mean().reset_index()
    return g.groupby(["set", "movement", "source"])[col].mean().unstack("source")


def summary() -> None:
    R = pd.concat([pd.read_parquet(f) for f in sorted(ROWS.glob("*.parquet"))],
                  ignore_index=True)
    rng = np.random.default_rng(SEED)
    out = [harness(R), ""]
    pcinfo = (R[R["set"] != "batik"].groupby(["set", "movement", "piece"])
              [["boundary_agree", "onset_agree", "target_coverage", "n_drawn"]].first())
    out.append("PianoCoRe score mapping (DTW):\n" + pcinfo.round(3).to_string())
    excluded = set(pcinfo[pcinfo["boundary_agree"] < MIN_AGREE].index.get_level_values(1)
                   + "@" + pcinfo[pcinfo["boundary_agree"] < MIN_AGREE]
                   .index.get_level_values(0))
    out.append(f"excluded (boundary agreement < {MIN_AGREE}): {sorted(excluded) or 'none'}\n")
    R = R[~(R["movement"] + "@" + R["set"]).isin(excluded)]
    order = ["dcml", "llm", "llm_m4", "llm_m8", "llm_cad", "llm_oracle", "dcml_m4", "cadence",
             "cadence_m4", "proxy", "grid4"]
    for col in ("concave_excess", "arc_r2_excess", "n_phrases", "concave_share",
                "null_concave_share", "tempo_r2_nm"):
        T = per_movement(R, col)
        T = T[[c for c in order if c in T.columns]]
        out.append(f"== {col}: per movement (LLM = mean over runs; PianoCoRe = mean over "
                   f"performances)\n" + T.round(3).to_string())
        for s, g in T.groupby(level="set"):
            out.append(f"  mean {s:20s} " + "  ".join(f"{c} {g[c].mean():+.3f}" for c in
                                                      g.columns))
        out.append("")
    # primary units: Batik M1-M5 + PianoCoRe Romantic R1-R3
    T = per_movement(R, "concave_excess")
    P = T.loc[[i for i in T.index if i[0] in ("batik", "pianocore_romantic")]]
    out.append(f"PRIMARY units: {len(P)} movements {[i[1] for i in P.index]}")
    res = {}
    for a, b in (("llm", "dcml"), ("llm_m4", "dcml"), ("llm_m8", "dcml"), ("llm_cad", "dcml"),
                 ("llm_oracle", "dcml"), ("llm", "cadence"), ("llm_m4", "cadence"),
                 ("dcml", "cadence"), ("llm_m4", "llm"), ("dcml_m4", "dcml")):
        for name, sub in (("all", P), ("batik", P.loc[["batik"]]),
                          ("romantic", P.loc[[i for i in P.index
                                              if i[0] == "pianocore_romantic"]])):
            dd = (sub[a] - sub[b]).to_numpy(float)
            if not len(dd):
                continue
            lo, hi = t_int(dd)
            blo, bhi = boot(dd, rng) if len(dd) > 1 else (np.nan, np.nan)
            res[(a, b, name)] = float(np.nanmean(dd))
            out.append(f"  {a:10s} - {b:8s} [{name:8s} n={len(dd)}] mean {np.nanmean(dd):+.3f}"
                       f"  t [{lo:+.3f}, {hi:+.3f}]  boot [{blo:+.3f}, {bhi:+.3f}]  "
                       f"positive {int((dd > 0).sum())}/{len(dd)}  per movement "
                       + " ".join(f"{v:+.2f}" for v in dd))
    for a in ("llm", "llm_m4"):
        d_ = res[(a, "dcml", "all")]
        c_ = res[(a, "cadence", "all")]
        verdict = ("RECOVERED" if d_ >= MARGIN and c_ > 0 else
                   "NOT RECOVERED" if d_ < MARGIN else "RECOVERED vs DCML but not above detector")
        out.append(f"RULE {a}: mean({a} - dcml) = {d_:+.3f} (margin {MARGIN}), "
                   f"mean({a} - cadence) = {c_:+.3f} -> {verdict}")
    # coherence
    C = per_movement(R, "tempo_r2_nm")
    Pc = C.loc[P.index]
    out.append("\nSECONDARY coherence tempo R2 (no markings), paired over primary units")
    for a, b in (("llm", "dcml"), ("llm_m4", "dcml"), ("llm", "proxy"), ("dcml", "proxy"),
                 ("llm", "cadence")):
        dd = (Pc[a] - Pc[b]).to_numpy(float)
        lo, hi = t_int(dd)
        out.append(f"  {a:8s} - {b:8s} mean {np.nanmean(dd):+.3f} t [{lo:+.3f}, {hi:+.3f}] "
                   f"positive {int((dd > 0).sum())}/{len(dd)}")
    # per run
    g = (R[R["run"] != ""].groupby(["set", "movement", "source", "run"])["concave_excess"]
         .mean().unstack("source"))
    out.append("\nPer LLM run, concave_excess\n" + g.round(3).to_string())
    # over-segmentation diagnostic
    N = per_movement(R, "n_phrases")
    diag = pd.DataFrame({"ratio_llm_dcml": N["llm"] / N["dcml"],
                         "m4_minus_llm": T["llm_m4"] - T["llm"],
                         "llm_minus_dcml": T["llm"] - T["dcml"]})
    out.append("\nOver-segmentation diagnostic\n" + diag.round(3).to_string())
    txt = "\n".join(out)
    (ART / "summary.txt").write_text(txt + "\n")
    per_movement(R, "concave_excess").to_csv(ART / "concave_excess_per_movement.csv")
    print(txt)


if __name__ == "__main__":
    parts = sys.argv[1:] or ["compute", "summary"]
    if "compute" in parts:
        compute()
    if "summary" in parts:
        summary()
