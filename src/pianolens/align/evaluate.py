"""Compare a predicted note alignment with a ground-truth one.

Metrics follow parangonar's ``fscore_alignments`` (Peter et al., TISMIR 2023, which reports
match F-score on (n)ASAP), computed with sets so they run in linear time:

- **match** precision / recall / F1 over (score_id, performance_id) pairs;
- **insertion** precision / recall / F1 over performance ids labelled "insertion"
  (extra notes the performer played);
- **deletion** precision / recall / F1 over score ids labelled "deletion"
  (score notes the performer skipped);
- **perf_note_accuracy**: fraction of ground-truth performance notes whose predicted status is
  exactly right (matched to the same score note, or both call it an insertion);
- **score_note_accuracy**: the same over ground-truth score notes (same partner, or both
  call it a deletion).

When neither side has any item of a type, precision, recall and F1 are 1.0 (nothing to find,
nothing wrongly found), as in parangonar.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# a list of partitura-style dicts, a pianolens.data.types.Alignment, or an AlignResult
AlignmentLike = Any


@dataclass(frozen=True)
class PRF:
    precision: float
    recall: float
    f1: float
    n_pred: int
    n_true: int
    n_correct: int


@dataclass(frozen=True)
class AlignmentScores:
    match: PRF
    insertion: PRF
    deletion: PRF
    perf_note_accuracy: float
    score_note_accuracy: float

    def as_flat_dict(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for kind in ("match", "insertion", "deletion"):
            for k, v in asdict(getattr(self, kind)).items():
                out[f"{kind}_{k}"] = v
        out["perf_note_accuracy"] = self.perf_note_accuracy
        out["score_note_accuracy"] = self.score_note_accuracy
        return out


def prf(pred: set, true: set) -> PRF:
    """Precision, recall, F1 of a predicted set against a true set."""
    n_correct = len(pred & true)
    if not pred and not true:
        return PRF(1.0, 1.0, 1.0, 0, 0, 0)
    p = n_correct / len(pred) if pred else 0.0
    r = n_correct / len(true) if true else 0.0
    f = 2 * p * r / (p + r) if p + r > 0 else 0.0
    return PRF(p, r, f, len(pred), len(true), n_correct)


def _entries(alignment: AlignmentLike) -> list[dict[str, Any]]:
    if hasattr(alignment, "to_partitura"):  # pianolens.data.types.Alignment
        return alignment.to_partitura()
    return list(getattr(alignment, "alignment", alignment))


def _split(alignment: AlignmentLike) -> tuple[set, set, set]:
    matches, insertions, deletions = set(), set(), set()
    for a in _entries(alignment):
        label = a["label"]
        if label == "match":
            matches.add((str(a["score_id"]), str(a["performance_id"])))
        elif label == "insertion":
            insertions.add(str(a["performance_id"]))
        elif label == "deletion":
            deletions.add(str(a["score_id"]))
    return matches, insertions, deletions


def evaluate_alignment(predicted: AlignmentLike, ground_truth: AlignmentLike) -> AlignmentScores:
    """Score ``predicted`` against ``ground_truth`` (see module docstring for definitions).

    Both arguments are partitura-style alignment lists, ``pianolens.data.types.Alignment`` or
    :class:`~pianolens.align.core.AlignResult` objects. Labels
    other than match / insertion / deletion (e.g. "ornament") are ignored.
    """
    pm, pi, pd = _split(predicted)
    tm, ti, td = _split(ground_truth)

    pred_perf = {p: s for s, p in pm} | {p: None for p in pi}
    true_perf = {p: s for s, p in tm} | {p: None for p in ti}
    pred_score = {s: p for s, p in pm} | {s: None for s in pd}
    true_score = {s: p for s, p in tm} | {s: None for s in td}

    def acc(pred_map: dict, true_map: dict) -> float:
        if not true_map:
            return 1.0
        ok = sum(1 for k, v in true_map.items() if k in pred_map and pred_map[k] == v)
        return ok / len(true_map)

    return AlignmentScores(
        match=prf(pm, tm),
        insertion=prf(pi, ti),
        deletion=prf(pd, td),
        perf_note_accuracy=acc(pred_perf, true_perf),
        score_note_accuracy=acc(pred_score, true_score),
    )
