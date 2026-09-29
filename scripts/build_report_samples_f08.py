"""F-08 sample reports and their known-answer checks.

Run: ``uv run python scripts/build_report_samples_f08.py`` (about 1 minute).

Writes to ``data/interim/reports/`` (gitignored):

* (a) ``a_asap_op10no3_sunmeiting``: ASAP Chopin Op. 10 No. 3 (SunMeiting08), PianoCoRe refs.
* (b) ``b_vienna_op10no3_p01``: Vienna 4x22 pianist p01 (bars 1-21), with the 21 other Vienna
  pianists as same-score sensor references plus PianoCoRe.
* (c) ``c_asap_op10no3_perturbed``: (a) with D-08 mistakes (``perturb``, 5% of matched notes,
  equal mix of wrong / extra / missed) and 30 ms Gaussian onset jitter on every note.
* (d) ``d_deadpan_op10no3``: a deadpan rendition of the performed score of (a): constant tempo
  (the geometric-mean tempo of (a)), constant velocity 64, 95% legato, no pedal.
* (e) ``e_three_takes_recurring`` (F-08b): three synthetic takes of Chopin Op. 10 No. 4 (Op. 10
  No. 3 has one ASAP performance, too few for the expert check). Base = the first ASAP
  performance made note-perfect for the checker (extra notes dropped, wrong pitches set to the
  score pitch, missed notes added at their expected onset). Each take = D-08 ``perturb`` of
  the base with its own seed (2% random slips, 10 ms onset jitter) plus one fixed mistake: the
  top note of bar ``E_BAR_LABEL`` played a semitone high in every take. Up to 6 other ASAP
  performances of the piece are the expert check that removes checker artefacts from recurring
  errors.

Checks printed at the end: (c) must surface the injected mistakes (bar recall) and the jitter
(timing steadiness worse than (a)); (d) must say "too flat"; (e) must mark the fixed mistake's
bar "strong" as a recurring error and must not promote any random slip. F-08c: each sample's
per-bar expert check (experts, suppressed / down-tiered bars).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import partitura as pt

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "interim" / "reports"
INPUTS = OUT / "inputs"
PIECE = "chopin_op10_no3"
E_PIECE = "chopin_op10_no4"  # sample (e): 22 ASAP performances, so experts can check errors
E_TITLE = "Chopin, Etude Op. 10 No. 4"
E_BAR_LABEL = "30"  # bar of the recurring mistake in sample (e)
E_SEEDS = (101, 102, 103)
TITLE = "Chopin, Etude Op. 10 No. 3"


def save_midi(notes: np.ndarray, pedal: np.ndarray, path: Path) -> None:
    na = np.zeros(len(notes), dtype=[("onset_sec", "f8"), ("duration_sec", "f8"),
                                     ("pitch", "i4"), ("velocity", "i4"), ("id", "U32")])
    for c in ("onset_sec", "duration_sec", "pitch", "velocity"):
        na[c] = notes[c]
    na["onset_sec"] -= min(0.0, float(na["onset_sec"].min()))
    na["id"] = [f"n{i}" for i in range(len(na))]
    pp = pt.performance.PerformedPart.from_note_array(na)
    pp.controls = [{"time": float(t), "number": int(n), "value": int(v)}
                   for t, n, v in zip(pedal["time_sec"], pedal["number"], pedal["value"],
                                      strict=True)]
    pt.save_performance_midi(pp, str(path))


def main() -> None:
    warnings.filterwarnings("ignore")
    from pianolens.data import asap
    from pianolens.data.perturb import MistakeSpec, perturb
    from pianolens.report import report_from_files, write_report

    INPUTS.mkdir(parents=True, exist_ok=True)
    idx = asap.asap_index()
    row = idx[idx["piece_id"] == PIECE].iloc[0]
    midi_a = Path(asap.DEFAULT_ROOT) / row["midi_performance"]
    xml = Path(asap.DEFAULT_ROOT) / row["xml_score"]
    excl = ["ASAP_SunMeiting08"]
    out = {}

    # (a)
    rep_a = report_from_files(midi_a, piece_id=PIECE, provenance="disklavier",
                              title=f"{TITLE} (ASAP, SunMeiting08)")
    out["a"] = write_report(rep_a, OUT / "a_asap_op10no3_sunmeiting.html")

    # (b)
    vroot = REPO / "data" / "raw" / "vienna4x22"
    vmidis = sorted((vroot / "midi").glob("Chopin_op10_no3_p[0-9][0-9].mid"))
    rep_b = report_from_files(vmidis[0], score=vroot / "musicxml" / "Chopin_op10_no3.musicxml",
                              piece_id=PIECE, provenance="sensor",
                              title=f"{TITLE}, bars 1-21 (Vienna 4x22, pianist p01)",
                              reference_midis=vmidis[1:], reference_provenance="sensor")
    out["b"] = write_report(rep_b, OUT / "b_vienna_op10no3_p01.html")

    # (c) D-08 perturbation of (a)
    perf = asap.load_asap_performance(row)
    gt = asap.load_asap_alignment(row)
    spec = MistakeSpec(rate=0.05, timing_jitter_sd_sec=0.03)
    pc, labels = perturb(perf, gt, spec, seed=7)
    midi_c = INPUTS / "c_sunmeiting08_perturbed.mid"
    save_midi(pc.notes, pc.pedal, midi_c)
    rep_c = report_from_files(midi_c, score=xml, piece_id=PIECE, provenance="disklavier",
                              title=f"{TITLE} (SunMeiting08 + D-08 mistakes and 30 ms jitter)",
                              exclude_references=excl,
                              notes=["Synthetic test input: D-08 perturbation of ASAP "
                                     "SunMeiting08 (5% mistakes, 30 ms onset jitter, seed 7)."])
    out["c"] = write_report(rep_c, OUT / "c_asap_op10no3_perturbed.html")

    # (d) deadpan rendition of the performed score of (a)
    from pianolens.align import align_performance
    from pianolens.report.io import load_performance, load_score

    ap_a = align_performance(load_score(xml, PIECE), load_performance(midi_a, "disklavier"))
    sn = ap_a.score.notes
    bpm = rep_a["tempo"]["tempo_bpm_geomean"]
    spb = 60.0 / bpm
    dn = np.zeros(len(sn), dtype=[("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                                  ("velocity", "i4")])
    b0 = float(sn["onset_beat"].min())
    dn["onset_sec"] = (sn["onset_beat"] - b0) * spb
    dn["duration_sec"] = np.maximum(sn["duration_beat"] * spb * 0.95, 0.03)
    dn["pitch"] = sn["pitch"]
    dn["velocity"] = 64
    midi_d = INPUTS / "d_deadpan_op10no3.mid"
    save_midi(dn, np.zeros(0, dtype=[("time_sec", "f8"), ("number", "i4"), ("value", "i4")]),
              midi_d)
    rep_d = report_from_files(midi_d, score=xml, piece_id=PIECE, provenance="synthetic",
                              title=f"{TITLE} (deadpan rendition)", exclude_references=excl,
                              notes=[f"Synthetic test input: the performed score of (a) at a "
                                     f"constant {bpm:.1f} beats per minute, velocity 64."])
    out["d"] = write_report(rep_d, OUT / "d_deadpan_op10no3.html")

    # (e) three takes with one recurring mistake and random slips
    rep_e, e_info = sample_e()
    out["e"] = write_report(rep_e, OUT / "e_three_takes_recurring.html")

    # ---- checks
    checks = {}
    # (c): injected mistakes -> bars; compare with bars where (c) has more errors than (a)
    from pianolens.features.correctness import correctness

    ap_c = align_performance(load_score(xml, PIECE), load_performance(midi_c, "disklavier"))
    cc = correctness(ap_c)
    inj = labels.notes[labels.notes["injected"]]
    pbar = dict(zip(cc.notes["performance_id"], cc.notes["measure_index"], strict=True))
    # perturbed MIDI note ids were renumbered n0.. in the order of pc.notes
    pid_map = {str(o): f"n{i}" for i, o in enumerate(pc.notes["id"])}
    inj_bars = {pbar.get(pid_map.get(str(p), ""), -1) for p in inj["performance_id"]}
    # missed notes: the source performance's note that was dropped, placed by its onset
    src_on = dict(zip(perf.notes["id"].astype(str), perf.notes["onset_sec"], strict=True))
    tpos = cc.score_notes.dropna(subset=["expected_onset_sec"])
    miss = labels.missed[labels.missed["injected"]]
    for op in miss["original_performance_id"]:
        t = src_on.get(str(op))
        if t is not None and len(tpos):
            j = int(np.argmin(np.abs(tpos["expected_onset_sec"].to_numpy() - t)))
            inj_bars.add(int(tpos["measure_index"].iloc[j]))
    inj_bars.discard(-1)
    ba = {b["index"]: b["correctness"]["n_errors"] for b in rep_a["bars"]}
    bc = {b["index"]: b["correctness"]["n_errors"] for b in rep_c["bars"]}
    more = {i for i in bc if bc[i] > ba.get(i, 0)}
    checks["c_injected"] = {k: int(v) for k, v in labels.counts().items()}
    checks["c_bars_with_injected_mistakes"] = len(inj_bars)
    checks["c_bar_recall_errors_increase"] = len(inj_bars & more) / max(len(inj_bars), 1)
    checks["c_bar_recall_any_error"] = sum(bc[i] > 0 for i in inj_bars) / max(len(inj_bars), 1)
    checks["c_bars_error_increase_without_injection"] = len(more - inj_bars)
    for k, r in (("a", rep_a), ("c", rep_c)):
        checks[f"{k}_error_rate"] = r["correctness"]["error_rate"]
        checks[f"{k}_n_wrong_missed_extra"] = [r["correctness"][x] for x in
                                               ("n_wrong_pitch", "n_missed", "n_extra")]
        checks[f"{k}_timing_noise_ms"] = r["timing"].get("noise_rms_ms")
        checks[f"{k}_timing_bars_tiered"] = sum(b["timing"]["tier"] != "none" for b in r["bars"])
        checks[f"{k}_correctness_bars_tiered"] = sum(b["correctness"]["tier"] != "none"
                                                     for b in r["bars"])
        checks[f"{k}_practise"] = [f"[{d['tier']}] {d['text']}" for d in r["practise"]]
    # (d): too flat
    wins = rep_d["interpretation"]["windows"]
    checks["d_too_flat_windows"] = {b: [w["flat_tier"] for w in wins if w["block"] == b]
                                    for b in ("tempo", "velocity")}
    checks["d_tempo_typicality"] = [round(w["typicality_pct"], 4) for w in wins
                                    if w["block"] == "tempo"]
    checks["d_practise"] = [f"[{d['tier']}] {d['text']}" for d in rep_d["practise"]]
    checks["d_says_too_flat"] = any("too flat" in d["text"] for d in rep_d["practise"])
    checks["b_practise"] = [f"[{d['tier']}] {d['text']}" for d in rep_b["practise"]]
    # (e): the recurring mistake is strong, random slips are not promoted
    lab = [b["label"] for b in rep_e["bars"]]
    fb = rep_e["bars"][lab.index(E_BAR_LABEL)]["correctness"]
    rec_bars = rep_e["takes"]["recurring_error_bars"]
    checks["e_base_errors_wrong_missed_extra"] = e_info["base_errors"]
    checks["e_injected_per_take"] = e_info["injected"]
    checks["e_fixed_bar"] = {"label": E_BAR_LABEL, "tier": fb["tier"],
                             "n_wrong_pitch_this_take": fb["n_wrong_pitch"],
                             "recurring": fb["recurring"]}
    checks["e_recurring_error_bars"] = rec_bars
    checks["e_expert_checks"] = rep_e["takes"]["n_expert_checks"]
    checks["e_promoted"] = rep_e["takes"]["promoted"]
    checks["e_slip_bars_per_take"] = e_info["slip_bars"]
    slip_all = sorted({b for t in e_info["slip_bars"] for b in t} - {E_BAR_LABEL}, key=float)
    checks["e_slip_bars_promoted"] = [b for b in slip_all if b in rec_bars]
    main_slip = [b for b in e_info["slip_bars"][0] if b != E_BAR_LABEL]
    checks["e_main_take_slip_bar_tiers"] = {
        t: sum(rep_e["bars"][lab.index(b)]["correctness"]["tier"] == t for b in main_slip)
        for t in ("none", "notable", "strong")}
    checks["e_practise"] = [f"[{d['tier']}] {d['text']}" for d in rep_e["practise"]]
    checks["e_pass"] = bool(fb["tier"] == "strong" and fb["recurring"]
                            and rec_bars == [E_BAR_LABEL] and not checks["e_slip_bars_promoted"]
                            and rep_e["practise"][0]["bars"] == [lab.index(E_BAR_LABEL)])
    # F-08c: the per-bar expert check in every sample
    for k, r in (("a", rep_a), ("b", rep_b), ("c", rep_c), ("d", rep_d), ("e", rep_e)):
        xc = r["correctness"].get("expert_check") or {}
        checks[f"{k}_expert_check"] = {
            "n_experts": xc.get("n_expert_performances"), "provenance": xc.get("provenance"),
            "n_bars_checked": xc.get("n_bars_checked"),
            **{s: xc.get(f"bars_{s}", []) for s in ("suppressed", "down_tiered", "confirmed",
                                                     "unchecked")}}  # fmt: skip
        checks[f"{k}_practise"] = [f"[{d['tier']}] {d['text']}" for d in r["practise"]]
    checks["files"] = {k: [str(p) for p in v] for k, v in out.items()}
    (OUT / "sample_checks.json").write_text(json.dumps(checks, indent=1, default=float))
    print(json.dumps(checks, indent=1, default=float))


def sample_e() -> tuple[dict, dict]:
    """Sample (e): see the module docstring. Returns the report and facts for the checks."""
    from pianolens.align import align_performance
    from pianolens.data import asap
    from pianolens.data.perturb import MistakeSpec, perturb
    from pianolens.features.correctness import correctness
    from pianolens.report import report_from_files
    from pianolens.report.build import bar_labels
    from pianolens.report.io import load_performance, load_score

    # base: the first ASAP performance of E_PIECE, made note-perfect for the checker
    idx = asap.asap_index()
    rows = idx[idx["piece_id"] == E_PIECE].sort_values("midi_performance")
    row = rows.iloc[0]
    xml = Path(asap.DEFAULT_ROOT) / row["xml_score"]
    src = Path(row["midi_performance"]).stem
    excl = [f"ASAP_{src}"]
    ap_a = align_performance(load_score(xml, E_PIECE),
                             load_performance(Path(asap.DEFAULT_ROOT) / row["midi_performance"],
                                              "disklavier"))
    cr = correctness(ap_a)
    pn = ap_a.performance.notes
    lab = cr.notes["label"].to_numpy()
    keep = ~np.isin(lab, ("extra",))
    pitch = np.where(lab == "wrong_pitch", cr.notes["score_pitch"].to_numpy(), pn["pitch"])
    base = [(float(o), float(d), int(p), int(v)) for o, d, p, v, k in zip(
        pn["onset_sec"], pn["duration_sec"], pitch, pn["velocity"], keep, strict=True) if k]
    miss = cr.score_notes[(cr.score_notes["label"] == "missed")
                          & cr.score_notes["expected_onset_sec"].notna()]
    vmed = int(np.median(pn["velocity"]))
    base += [(float(r.expected_onset_sec), 0.15, int(r.pitch), vmed) for r in miss.itertuples()]
    base.sort()
    arr = np.array(base, dtype=[("onset_sec", "f8"), ("duration_sec", "f8"), ("pitch", "i4"),
                                ("velocity", "i4")])
    empty_ped = np.zeros(0, dtype=[("time_sec", "f8"), ("number", "i4"), ("value", "i4")])
    midi_base = INPUTS / "e_base_clean.mid"
    save_midi(arr, empty_ped, midi_base)
    sc = load_score(xml, E_PIECE)
    ap_b = align_performance(sc, load_performance(midi_base, "disklavier"))
    crb = correctness(ap_b)
    info = {"base_errors": [int(crb.summary[k]) for k in ("n_wrong_pitch", "n_missed",
                                                          "n_extra")]}
    # the fixed mistake: top note of bar E_BAR_LABEL, a semitone high
    labels = bar_labels(ap_b.score)
    bi = labels.index(E_BAR_LABEL)
    cand = crb.notes[(crb.notes["measure_index"] == bi) & (crb.notes["label"] == "correct")]
    fixed_id = str(cand.sort_values(["pitch", "onset_sec"], ascending=[False, True])
                   .iloc[0]["performance_id"])
    spec = MistakeSpec(rate=0.02, timing_jitter_sd_sec=0.01)
    paths, info["injected"], info["slip_bars"] = [], [], []
    for k, seed in enumerate(E_SEEDS):
        pc, labs = perturb(ap_b.performance, ap_b.alignment, spec, seed=seed)
        ids = pc.notes["id"].astype(str)
        hit = np.flatnonzero(ids == fixed_id)
        row = labs.notes[labs.notes["performance_id"].astype(str) == fixed_id]
        if len(hit) != 1 or bool(row["injected"].iloc[0]):
            raise RuntimeError(f"seed {seed} perturbed the fixed note; pick another seed")
        notes = pc.notes.copy()
        notes["pitch"][hit[0]] += 1
        path = INPUTS / f"e_take{k + 1}.mid"
        save_midi(notes, pc.pedal, path)
        paths.append(path)
        info["injected"].append({kk: int(v) for kk, v in labs.counts().items()})
        # bars of this take's injected slips, by the checker on the take itself
        apk = align_performance(sc, load_performance(path, "disklavier"))
        ck = correctness(apk)
        tl = bar_labels(apk.score)
        info["slip_bars"].append(sorted({tl[i] for i in ck.bars.loc[
            ck.bars["n_errors"] > 0, "measure_index"]}, key=float))
    rep = report_from_files(
        paths[0], score=xml, piece_id=E_PIECE, provenance="synthetic", takes=paths[1:],
        title=f"{E_TITLE} (three synthetic takes, one recurring mistake)",
        exclude_references=excl,
        notes=[f"Synthetic test input (F-08b): three takes of a note-perfect copy of ASAP {src}, "
               "each with its own D-08 slips (2%, 10 ms onset jitter, seeds "
               f"{', '.join(map(str, E_SEEDS))}) and the top note of bar {E_BAR_LABEL} played "
               "a semitone high in every take. Other ASAP performances of the piece are the "
               "expert check for recurring errors."])
    info["base_source"] = src
    return rep, info


if __name__ == "__main__":
    main()
