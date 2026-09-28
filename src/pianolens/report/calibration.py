"""Reference values the practice report compares against. Every number here is either measured in
this repo (script named next to it) or cited from ``docs/research/2026-09-27-landscape.md``.

Tiers (DECISIONS 2026-09-28, after F-06): a localized value is **notable** beyond the 95th
percentile of the matching expert reference distribution and **strong** beyond the 99th. The
report highlights only "strong"; "notable" is shown subtly. About 5% of genuine expert bars are
notable and about 1% strong by construction.
"""

from __future__ import annotations

NOTABLE_Q = 0.95
STRONG_Q = 0.99
#: Fewer references than this at a bar / run -> the value is shown but not tiered.
MIN_TIER_REFERENCES = 10

#: What the deployed correctness pipeline (``align_performance`` + ``correctness``) reports on
#: **clean expert playing**: the rate-0 copies of the D-08 mistake set (100 (n)ASAP
#: performances, 62 pieces, 12,940 bars). Its "errors" are real slips plus alignment and
#: ground-truth noise; on average 42% of an expert performance's bars have at least one.
#: Measured by ``scripts/calibrate_report_f08.py`` on 2026-09-28 (raw output in
#: ``data/interim/reports/calibration/``). Bars are tiered on the two most reliable
#: quantities: the number of wrong-pitch notes (bar-level precision 0.996 or higher on D-08,
#: ``docs/specs/correctness-validation.md``) and missed + extra notes per graded score note.
CORRECTNESS_EXPERT_BARS: dict[str, float] = {
    "n_performances": 100,
    "n_bars": 12940,
    "wrong_pitch_q95": 1.0,  # 7.1% of expert bars have >= 1, 2.1% >= 2, 0.85% >= 3
    "wrong_pitch_q99": 2.0,
    "missed_extra_per_note_q95": 0.267,
    "missed_extra_per_note_q99": 0.634,
    "share_bars_with_error_median": 0.421,  # per performance; 5-95%: 0.113-0.820
    "error_rate_q50": 0.0465,  # (wrong + missed + extra) / graded notes, per performance
    "error_rate_q95": 0.164,
    "error_rate_q99": 0.207,
}

#: Recurring errors across repeated takes (DECISIONS 2026-09-28, after F-08; F-08b). An error
#: is recurring when the same error key (``build.error_signatures``) is in the same bar in at
#: least RECURRING_MIN_TAKES takes, only RECURRING_KINDS count, and keys that the checker also
#: reports for expert performances of the same score (``build.expert_error_keys``) are removed.
#: Without at least RECURRING_MIN_EXPERTS such experts nothing is promoted (recurring errors are
#: listed only). Calibrated on expert pseudo-takes (3 ASAP pianists per piece, 30 pieces) by
#: ``scripts/calibrate_recurring_f08b.py`` on 2026-09-28; share of expert bars promoted:
#:   no expert filter: wrong+missed+extra 24-31%, wrong pitch only 3.3% (2 takes) / 4.2% (3);
#:   filter, 2 experts: wrong pitch only 0.5% (2 takes) / 1.0% (3 takes);
#:   filter, all other experts (median 6, 15 pieces): wrong pitch only 0.18% / 0.51%,
#:   wrong+extra 1.6% / 3.8%, wrong+missed 2.8% / 7.1%.
#: So only wrong pitches recur reliably enough for "strong" (the 99th-percentile tier), and only
#: with the expert filter. Missed notes are judged per bar, not per note (F-01), and recurring
#: missed / extra notes are mostly score and checker artefacts shared by every pianist.
RECURRING_MIN_TAKES = 2
RECURRING_KINDS: tuple[str, ...] = ("wrong_pitch",)
RECURRING_MIN_EXPERTS = 2

#: D-10 (DECISIONS 2026-09-27): on transcribed MIDI the apparent tier A error rate doubles
#: (0.039 -> 0.080) and velocity residual SD is about 9 MIDI units.
TRANSCRIBED_ERROR_RATE = (0.039, 0.080)

#: Evenness reference ranges, landscape section 1.5 ("Reference ranges at a glance"). All are
#: instructed, metronomic scales on a MIDI keyboard; CV values are derived (SD / IOI) by
#: lit-scout. They are a floor for deliberate evenness, not a norm for repertoire, and they are
#: only comparable at a similar note rate (MacKenzie and Van Eerd 1990).
LITERATURE_EVENNESS: tuple[dict, ...] = (
    {"label": "Professionals, scales", "note_rate_nps": 8.0, "ioi_cv_lo": 0.067,
     "ioi_cv_hi": 0.074, "source": "van Vugt, Jabusch, Altenmüller 2013"},
    {"label": "Audibility threshold", "note_rate_nps": 8.0, "ioi_cv_lo": 0.08,
     "ioi_cv_hi": 0.08, "source": "van Vugt, Jabusch, Altenmüller 2013"},
    {"label": "Music students, scales", "note_rate_nps": 10.7, "ioi_cv_lo": 0.11,
     "ioi_cv_hi": 0.13, "source": "van Vugt, Treutler, Altenmüller, Jabusch 2013"},
    {"label": "Dystonia patients, scales", "note_rate_nps": 5.3, "ioi_cv_lo": 0.079,
     "ioi_cv_hi": 0.079, "source": "Cheng, Großbach, Altenmüller 2013"},
)  # fmt: skip
#: A literature value is "at a similar note rate" when its rate is within this relative
#: distance of the run's rate. A presentation choice of the report, not a published value.
SIMILAR_RATE_REL = 0.2
#: Velocity just-noticeable difference between consecutive tones, MIDI units (Slade et al. 2023).
VELOCITY_JND_MIDI = (2.7, 4.5)
