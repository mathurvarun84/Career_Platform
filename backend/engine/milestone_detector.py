"""Score Journey milestone detection — pure Python, zero LLM calls."""

from __future__ import annotations

from backend.models.score_journey import MilestoneEvent, ScoreJourneyResult, SessionSnapshot

_TIER_ORDER = ["service", "startup_early", "product_mid", "product_unicorn", "faang"]
_PERCENTILE_BAND_ORDER = ["Bottom 25%", "Below Average", "Above Average", "Top 25%", "Top 10%"]


def detect_milestones(rows: list[dict]) -> list[MilestoneEvent]:
    """Detect milestone events across an ordered (ascending created_at) session sequence."""
    if not rows:
        return []

    milestones: list[MilestoneEvent] = [
        MilestoneEvent(
            run_id=rows[0]["run_id"],
            type="first_analysis",
            label="First analysis",
            from_value="",
            to_value=str(rows[0]["composite_score"]),
        )
    ]

    for prev, curr in zip(rows, rows[1:]):
        prev_tier, curr_tier = prev.get("current_tier"), curr.get("current_tier")
        if (
            curr_tier and curr_tier != prev_tier
            and prev_tier in _TIER_ORDER and curr_tier in _TIER_ORDER
            and _TIER_ORDER.index(curr_tier) > _TIER_ORDER.index(prev_tier)
        ):
            milestones.append(MilestoneEvent(
                run_id=curr["run_id"], type="tier_unlock", label="Tier unlocked",
                from_value=prev_tier, to_value=curr_tier,
            ))

        prev_band, curr_band = prev.get("percentile_label"), curr.get("percentile_label")
        if (
            curr_band and curr_band != prev_band
            and prev_band in _PERCENTILE_BAND_ORDER and curr_band in _PERCENTILE_BAND_ORDER
            and _PERCENTILE_BAND_ORDER.index(curr_band) > _PERCENTILE_BAND_ORDER.index(prev_band)
        ):
            milestones.append(MilestoneEvent(
                run_id=curr["run_id"], type="percentile_band", label="Percentile band improved",
                from_value=prev_band, to_value=curr_band,
            ))

    return milestones


def _build_journey_response(rows: list[dict]) -> ScoreJourneyResult:
    """Build the full Score Journey response from ordered session rows."""
    if not rows:
        return ScoreJourneyResult(
            sessions=[], total_sessions=0, first_score=0, latest_score=0, score_delta=0,
            first_tier=None, latest_tier=None, tier_changed=False,
            first_ctc_min=None, latest_ctc_min=None, ctc_delta_min=None, milestones=[],
        )

    first, last = rows[0], rows[-1]
    first_ctc_min, latest_ctc_min = first.get("current_ctc_min"), last.get("current_ctc_min")
    ctc_delta_min = (
        latest_ctc_min - first_ctc_min
        if first_ctc_min is not None and latest_ctc_min is not None
        else None
    )

    return ScoreJourneyResult(
        sessions=[SessionSnapshot(**row) for row in rows],
        total_sessions=len(rows),
        first_score=first["composite_score"],
        latest_score=last["composite_score"],
        score_delta=last["composite_score"] - first["composite_score"],
        first_tier=first.get("current_tier"),
        latest_tier=last.get("current_tier"),
        tier_changed=first.get("current_tier") != last.get("current_tier"),
        first_ctc_min=first_ctc_min,
        latest_ctc_min=latest_ctc_min,
        ctc_delta_min=ctc_delta_min,
        milestones=detect_milestones(rows),
    )
