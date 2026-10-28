"""The app's quick wrong-piece check: one decision from the quick alignment (BL-40).

The app aligns the first take to the chosen score once before the long steps
(:mod:`pianolens.app.pipeline`, step 2) and reads the Dice match ratio of that alignment,
``2 * correct / (graded score notes + performed notes)`` (``correctness(ap).summary
["match_ratio"]``; unit: a share in [0, 1]).

**Partial alignment off, or a recording the aligner takes as the whole piece:** today's rule
(DEFECTS DF-05): a ratio below :data:`WRONG_PIECE_MATCH` stops the run ("probably another
piece"). A whole span under ``partial=True`` has exactly the alignment of ``partial=False``
(BL-36, BL-39), so its decision is unchanged.

**Partial alignment on and a trimmed span** (``align(..., partial=True)``, BL-36): the score is
trimmed to the part the recording covers, so an excerpt of the right piece scores near 1
instead of near its share of the piece. A wrong score is trimmed too, to the span that fits
best, and a short excerpt can then match a wrong piece by chance (BL-37 audit: 2 of 1,376
wrong-score excerpts of 4-7 bars reached 0.5). For a trimmed span :func:`decide` uses

* a stop of :data:`PARTIAL_STOP_MATCH`;
* a minimum length of :data:`PARTIAL_MIN_NOTES` performed notes: a shorter recording is too
  short to check, so the app asks the learner to confirm the piece (``"confirm"``) instead of
  passing it; :data:`PARTIAL_SHORT_MODE` says whether that applies at every ratio (``"all"``)
  or only at or above the stop (``"high"``, below it the run stops).

Values chosen on dev and registered in BL-40
(``experiments/2026-10-27-BL-40-wrong-piece-stop/README.md``). The app uses the partial branch
only when the quick alignment runs with ``partial=True``, which
``pianolens.align.partial.PARTIAL_DEFAULT`` keeps off.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["Decision", "PARTIAL_MIN_NOTES", "PARTIAL_SHORT_MODE", "PARTIAL_STOP_MATCH",
           "WRONG_PIECE_MATCH", "decide"]

Decision = Literal["pass", "stop", "confirm"]

#: Quick-check match ratio (Dice) below which the run stops as "probably another piece" when
#: ``partial`` is off or the span is the whole piece. Measured 2026-09-29 (DEFECTS DF-05):
#: Henry's five Transkun takes (A-01) gave 0.818-0.939 on their own score and 0.163-0.280 on
#: the 20 wrong-score pairs; one ASAP performance each of Chopin Op. 10/3, 10/4, 10/12 and
#: Beethoven Op. 53/1 gave 0.960-0.984 on their own score and 0.083-0.314 on 12 wrong pairs.
WRONG_PIECE_MATCH = 0.5

#: Stop below this ratio when ``partial`` is on and the recording covers part of the score.
PARTIAL_STOP_MATCH = 0.625  # BL-40, registered on dev (midpoint of the dev gap at >= 75 notes)

#: With ``partial`` on and a trimmed span, a take with fewer performed notes than this is too
#: short to check: the app asks the learner to confirm the piece.
PARTIAL_MIN_NOTES = 75  # BL-40, registered on dev (below it the ratio does not separate)

#: ``"all"``: every too-short trimmed take is asked to confirm; ``"high"``: only those at or
#: above :data:`PARTIAL_STOP_MATCH` (below it the run stops).
PARTIAL_SHORT_MODE: Literal["all", "high"] = "all"  # BL-40, registered on dev


def decide(ratio: float, *, partial: bool, span_whole: bool, n_performed: int,
           stop: float = WRONG_PIECE_MATCH, partial_stop: float | None = None,
           min_notes: int | None = None, short_mode: str | None = None) -> Decision:
    """The quick check's decision for one alignment.

    Args:
        ratio: Dice match ratio of the quick alignment (share in [0, 1]); NaN counts as 0.
        partial: whether the quick alignment ran with ``partial=True``.
        span_whole: ``score.meta["recorded_span"]["whole"]`` (ignored when ``partial`` is off).
        n_performed: performed notes of the take (the upload's notes, before alignment).
        stop: today's stop, for ``partial`` off or a whole span.
        partial_stop, min_notes, short_mode: the trimmed-span rule; default
            :data:`PARTIAL_STOP_MATCH`, :data:`PARTIAL_MIN_NOTES`, :data:`PARTIAL_SHORT_MODE`.

    Returns:
        ``"stop"`` (probably another piece), ``"confirm"`` (too short to check: ask the learner
        to confirm the piece) or ``"pass"``.
    """
    r = 0.0 if ratio != ratio else float(ratio)  # NaN -> 0
    if not partial or span_whole:
        return "stop" if r < stop else "pass"
    ps = PARTIAL_STOP_MATCH if partial_stop is None else partial_stop
    mn = PARTIAL_MIN_NOTES if min_notes is None else min_notes
    mode = PARTIAL_SHORT_MODE if short_mode is None else short_mode
    if mode not in ("all", "high"):
        raise ValueError(f"short_mode must be 'all' or 'high', not {mode!r}")
    if n_performed < mn and (mode == "all" or r >= ps):
        return "confirm"
    return "stop" if r < ps else "pass"
