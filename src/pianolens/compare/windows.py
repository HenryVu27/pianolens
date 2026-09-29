"""Which passages of a practice report get an audible A/B comparison (P-01).

A comparison window is a short run of consecutive bars built from the report's tiered issues
(``report["issues"]`` of a ``pianolens.report/1`` dict). Order of preference:

1. tier: ``strong`` before ``notable`` (DECISIONS 2026-09-28, after F-06);
2. practise-eligible issues before low-confidence ones (e.g. velocity from transcribed input);
3. the report's "what to practise" category order: correctness, control, then interpretation
   (DECISIONS 2026-09-28, after F-08);
4. magnitude (multiple of the notable limit), largest first.

Issues are merged when their bars touch or overlap (gap of at most ``merge_gap`` bars) and the
merged span stays within ``max_bars``. A single issue longer than ``max_bars`` (a 16-bar
"too flat" window) is cut to its first ``max_bars`` bars and marked ``truncated``. At most
``max_windows`` windows are made; a later issue can still join an existing window.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = ["CATEGORY_RANK", "TIER_RANK", "Window", "select_windows"]

TIER_RANK = {"none": 0, "notable": 1, "strong": 2}
#: Same order as ``pianolens.report.build.CATEGORY_RANK`` (copied, not imported, so this module
#: only depends on the report's JSON, not on its code).
CATEGORY_RANK = {"correctness": 0, "control": 1, "interpretation": 2, "too_flat": 2}


@dataclass
class Window:
    """One comparison window: bars are 0-based rows of the performed score's measures (the
    report's ``bars[i]["index"]``)."""

    bars: list[int]
    tier: str
    reasons: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False

    @property
    def first(self) -> int:
        return self.bars[0]

    @property
    def last(self) -> int:
        return self.bars[-1]

    def label(self, labels: Sequence[str] | None = None) -> str:
        def lab(i: int) -> str:
            return labels[i] if labels is not None and 0 <= i < len(labels) else str(i + 1)
        if self.first == self.last:
            return f"bar {lab(self.first)}"
        return f"bars {lab(self.first)}-{lab(self.last)}"


def _priority(issue: Mapping[str, Any]) -> tuple:
    return (-TIER_RANK.get(str(issue.get("tier")), 0),
            0 if issue.get("practise_eligible", True) else 1,
            CATEGORY_RANK.get(str(issue.get("category")), 3),
            -float(issue.get("magnitude") or 0.0))  # fmt: skip


def _reason(issue: Mapping[str, Any]) -> dict[str, Any]:
    return {k: issue.get(k) for k in ("category", "channel", "tier", "bars", "bars_label",
                                      "magnitude", "practise_eligible", "text")}


def select_windows(
    report: Mapping[str, Any],
    max_windows: int = 8,
    max_bars: int = 4,
    merge_gap: int = 1,
    min_tier: str = "notable",
) -> list[Window]:
    """Comparison windows from a report dict, in priority order.

    Args:
        report: a ``pianolens.report/1`` dict (``issues`` with ``tier``, ``bars``, ``category``,
            ``channel``, ``magnitude``, ``practise_eligible``, ``text``).
        max_windows: cap on windows per report.
        max_bars: longest window, in bars (pre- and post-roll come on top).
        merge_gap: issues whose bars are at most this many bars apart are merged; 1 merges
            adjacent bars only.
        min_tier: lowest tier that makes a window.
    """
    floor = TIER_RANK[min_tier]
    issues = [i for i in report.get("issues", []) if TIER_RANK.get(str(i.get("tier")), 0) >= floor
              and i.get("bars")]  # fmt: skip
    issues.sort(key=_priority)
    wins: list[Window] = []
    for iss in issues:
        bars = sorted({int(b) for b in iss["bars"]})
        truncated = False
        if bars[-1] - bars[0] + 1 > max_bars:
            bars = [b for b in bars if b < bars[0] + max_bars]
            truncated = True
        lo, hi = bars[0], bars[-1]
        placed = False
        for w in wins:
            if lo <= w.last + merge_gap and hi >= w.first - merge_gap:
                nlo, nhi = min(lo, w.first), max(hi, w.last)
                if nhi - nlo + 1 <= max_bars:
                    w.bars = list(range(nlo, nhi + 1))
                    w.reasons.append(_reason(iss))
                    w.truncated = w.truncated or truncated
                    if TIER_RANK[str(iss["tier"])] > TIER_RANK[w.tier]:
                        w.tier = str(iss["tier"])
                    placed = True
                    break
        if not placed and len(wins) < max_windows:
            wins.append(Window(list(range(lo, hi + 1)), str(iss["tier"]), [_reason(iss)],
                               truncated))
        wins = _coalesce(wins, max_bars, merge_gap)
    return wins


def _coalesce(wins: list[Window], max_bars: int, merge_gap: int) -> list[Window]:
    """A window that grew can reach a later one: merge them if the union fits, otherwise
    remove the overlap from the later (lower-priority) window."""
    changed = True
    while changed:
        changed = False
        for i in range(len(wins)):
            for j in range(i + 1, len(wins)):
                a, b = wins[i], wins[j]
                if not (b.first <= a.last + merge_gap and b.last >= a.first - merge_gap):
                    continue
                lo, hi = min(a.first, b.first), max(a.last, b.last)
                if hi - lo + 1 <= max_bars:
                    a.bars = list(range(lo, hi + 1))
                    a.reasons += b.reasons
                    a.truncated = a.truncated or b.truncated
                    if TIER_RANK[b.tier] > TIER_RANK[a.tier]:
                        a.tier = b.tier
                    del wins[j]
                    changed = True
                    break
                if b.first <= a.last and b.last >= a.first:
                    left = [x for x in b.bars if x < a.first]
                    right = [x for x in b.bars if x > a.last]
                    rest = left if len(left) >= len(right) else right
                    if rest:
                        b.bars = rest
                    else:
                        a.reasons += b.reasons
                        del wins[j]
                    changed = True
                    break
            if changed:
                break
    return wins
