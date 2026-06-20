"""Unit tests for Score Journey milestone detection."""

from backend.engine.milestone_detector import _build_journey_response


def _row(run_id, composite_score, current_tier="service",
         percentile_label="Below Average", current_ctc_min=None):
    return {
        "run_id": run_id,
        "user_id": "user-1",
        "created_at": "2026-06-01T00:00:00Z",
        "ats_score": composite_score,
        "jd_match_score": None,
        "composite_score": composite_score,
        "percentile_value": None,
        "percentile_label": percentile_label,
        "current_tier": current_tier,
        "current_tier_label": None,
        "current_ctc_min": current_ctc_min,
        "current_ctc_max": None,
        "seniority": None,
        "role_family": None,
        "jd_company": None,
        "jd_role_title": None,
        "ats_keyword_match": None,
        "ats_formatting": None,
        "ats_readability": None,
        "ats_impact_metrics": None,
    }


def test_empty_first_time_user():
    result = _build_journey_response([])
    assert result.total_sessions == 0
    assert result.milestones == []
    assert result.score_delta == 0


def test_single_session_first_analysis():
    rows = [_row("run-1", 48, current_tier="service", percentile_label="Below Average")]
    result = _build_journey_response(rows)
    assert result.total_sessions == 1
    assert result.score_delta == 0
    assert len(result.milestones) == 1
    assert result.milestones[0].type == "first_analysis"


def test_flat_arc_no_tier_or_percentile_change():
    rows = [
        _row("run-1", 48, current_tier="service", percentile_label="Below Average"),
        _row("run-2", 50, current_tier="service", percentile_label="Below Average"),
        _row("run-3", 52, current_tier="service", percentile_label="Below Average"),
    ]
    result = _build_journey_response(rows)
    assert result.total_sessions == 3
    assert result.score_delta == 4
    assert result.tier_changed is False
    assert len(result.milestones) == 1
    assert result.milestones[0].type == "first_analysis"


def test_tier_crossing_upward():
    rows = [
        _row("run-1", 48, current_tier="service", percentile_label="Below Average"),
        _row("run-2", 58, current_tier="service", percentile_label="Below Average"),
        _row("run-3", 70, current_tier="product_mid", percentile_label="Below Average"),
    ]
    result = _build_journey_response(rows)
    tier_milestones = [m for m in result.milestones if m.type == "tier_unlock"]
    assert len(tier_milestones) == 1
    assert tier_milestones[0].from_value == "service"
    assert tier_milestones[0].to_value == "product_mid"


def test_percentile_band_crossing_upward():
    rows = [
        _row("run-1", 52, current_tier="service", percentile_label="Below Average"),
        _row("run-2", 68, current_tier="service", percentile_label="Above Average"),
    ]
    result = _build_journey_response(rows)
    band_milestones = [m for m in result.milestones if m.type == "percentile_band"]
    assert len(band_milestones) == 1
    assert band_milestones[0].from_value == "Below Average"
    assert band_milestones[0].to_value == "Above Average"
