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
    # per performance; 5-95%: 0.113-0.820. BL-23 (2026-09-29): 0.421 -> 0.420 after the
    # same-pitch reassignment became the correctness default; every other value in this dict
    # and the tier limits are unchanged at the precision shown (rerun in
    # experiments/2026-09-29-BL-23-aligner-ornaments/, variant R).
    "share_bars_with_error_median": 0.420,
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

#: Missed notes per graded score note in a bar, on the same expert set (clean D-08 copies,
#: ``correctness_bars.parquet`` of ``scripts/calibrate_report_f08.py``; 27% of expert bars have
#: a missed note). Used instead of missed + extra when extra notes are low confidence
#: (transcribed / phone input, A-01; ``rules/audio.md``).
CORRECTNESS_EXPERT_BARS["missed_per_note_q95"] = 0.158
CORRECTNESS_EXPERT_BARS["missed_per_note_q99"] = 0.286

#: Per-bar expert check for single-take reports (F-08c). A bar's correctness tier is set against
#: the larger of the global expert limit (above) and the same quantity's quantile over the expert
#: performances of the same score at that bar: notable needs more than the per-bar
#: EXPERT_CHECK_Q[0] quantile, strong more than EXPERT_CHECK_Q[1]. So a bar where the target's
#: errors are within what experts of the same score (same provenance: transcribed experts for
#: transcribed input, A-01) show there is not ranked; it is reported as a likely score or edition
#: artefact. At least EXPERT_CHECK_MIN_REFS experts must cover the bar, otherwise the bar keeps
#: the global tier. Calibrated by ``scripts/calibrate_expert_check_f08c.py`` (2026-09-28; see
#: ``docs/specs/report-validation.md``, section 4). A bar must exceed both limits, so the
#: joint rate is below either alone. Notable / strong share of expert bars, global -> checked:
#:   key-sensor (40 clean D-08 copies, 28 pieces, 5-15 other ASAP experts): 6.8/1.7% -> 3.7/0.67%
#:   (per-bar q95 instead of q80: 2.8/0.67%);
#:   transcribed (150 A-01 floor transcriptions, leave-one-out, extras not counted):
#:   11.8/3.0% -> 5.3/1.4%.
#: Injected D-08 mistakes (rate 0.05): 85.5% of the bars tiered without the check stay tiered
#: (74.9% with q95).
EXPERT_CHECK_MIN_REFS = 5
EXPERT_CHECK_Q = (0.80, 0.99)

#: BL-18 (``docs/specs/report-validation.md``, section 5;
#: ``scripts/calibrate_strong_tier_bl18.py``).
#: On transcribed input the strong tier ran above its nominal 1% (A-01 floor, leave-one-out:
#: Transkun V2 0.58%, Aria-AMT 2.25%). Two changes, for transcribed input only (key-sensor input
#: keeps the F-08c rule, 0.67% strong):
#: 1. Per-bar strong limit (``build.expert_bar_limits``, ``strong_margin``): the finite-sample
#:    order statistic of rank ceil(0.99 (n + 1)). With fewer than 99 experts (always, at up to 15)
#:    that rank does not exist, so a bar is strong only with more than the worst expert there
#:    plus EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED notes.
#: 2. Strong global limits per transcriber family (notable keeps the key-sensor limits): the 99th
#:    percentile of the family's A-01 floor bars (75 transcriptions per family, 5 Chopin pieces,
#:    8,685 bars, extras not counted). The wrong-pitch limit equals the key-sensor one; missed
#:    notes per note do not (key-sensor 0.286). An unknown family gets the larger limits.
#: **After the BL-18 audit (DECISIONS 2026-09-29, "lead: BL-18 after audit")** the implemented
#: R1(2) + R2s was returned: it cut strong detection of injected mistakes to 0.16 of R0's, and the
#: Aria-AMT limit 0.771 is set by runs of fully missed bars (Aria-MIDI segment truncation; 0.422
#: without them). Interim default: **R1(0) without R2s**, i.e. margin 0 (strong needs more than
#: every expert at the bar) and ``ReportConfig.transcribed_strong_limits=False``. Held-out BL-18:
#: strong 0.62% (Transkun V2) / 1.01% (Aria-AMT). Runs of fully missed bars get their own rule
#: (NOT_HEARD_*). Provisional until the BL-18b confirmation run (report-validation.md).
#: The family limits below are kept for that comparison only.
EXPERT_CHECK_STRONG_MARGIN_TRANSCRIBED = 0
TRANSCRIBED_STRONG_LIMITS: dict[str, dict[str, float]] = {
    "Transkun V2": {"wrong_q99": 2.0, "me_q99": 0.308},
    "Aria-AMT": {"wrong_q99": 2.0, "me_q99": 0.771},
}
TRANSCRIBED_STRONG_LIMITS_UNKNOWN: dict[str, float] = {
    k: max(v[k] for v in TRANSCRIBED_STRONG_LIMITS.values()) for k in ("wrong_q99", "me_q99")
}
#: "Passage not heard" (BL-18 audit, section 3-4): on transcribed input, a run of at least
#: NOT_HEARD_MIN_BARS consecutive graded bars, each with at least NOT_HEARD_MISSED_SHARE of its
#: graded notes missed, is reported once as "passage not heard (not played, or not in the
#: recording)", a low-confidence item, and its bars get no correctness tier. Bars without graded
#: notes neither break nor extend a run. Measured: dev (A-01 floor) 55 such bars in 6 of 75
#: Aria-AMT transcriptions (0.63% of bars), mostly at the start or end of the piece (Aria-MIDI
#: segments cut from longer videos); held-out 15 bars in 4 of 109. No per-bar limit can move
#: them (80% missed is above every candidate limit).
NOT_HEARD_MIN_BARS = 3
NOT_HEARD_MISSED_SHARE = 0.8

#: BL-25 (from BL-21, audited): on transcribed input a missed note whose same-pitch predecessor in
#: the score is due less than FAST_REPEAT_MAX_IOI_SEC earlier (expected onsets at the played
#: tempo) is low confidence: the transcriber merges fast repeats (PianoVAM, Transkun: recall 0.33
#: under 80 ms, 0.89 at 80-120 ms, 0.976 for other notes; the loss sits below about 100 ms once
#: key-bounce echoes are excluded). Such missed notes are shown on the timeline but are not
#: counted towards correctness tiers (target and, where the table has the column, experts).
FAST_REPEAT_MAX_IOI_SEC = 0.1

#: BL-20 proposal 3: in fast runs (local inter-onset interval under FAST_RUN_MAX_IOI_SEC: median of
#: up to 4 gaps between neighbouring chord onsets, chords = onsets within FAST_RUN_CHORD_SEC) the
#: aligner absorbs or mispairs 6.9-8.3% of wrong pitches (2.5% in slow passages), so the note
#: checker is reliable about the bar but not about which note. Wrong notes there are worded at bar
#: level ("wrong notes in this fast run"), never as "X instead of Y". Tiers are unchanged.
FAST_RUN_MAX_IOI_SEC = 0.1
FAST_RUN_CHORD_SEC = 0.03

#: Default number of expert performances loaded for the check (ASAP for key-sensor input,
#: PianoCoRe transcriptions for transcribed input, as in the A-01 floor).
EXPERT_CHECK_MAX_REFS = 15

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
