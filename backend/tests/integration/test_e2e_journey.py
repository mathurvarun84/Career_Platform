"""
Integration test: exercises _build_journey_response with synthetic analysis_runs-shaped
rows (same flattening contract as backend/api/score_journey.py).
"""

from backend.engine.milestone_detector import _build_journey_response


def _make_row(ats_score, jd_match, tier, percentile_label, created_at):
    composite = int(ats_score * 0.4 + jd_match * 0.6) if jd_match else ats_score
    return {
        "run_id": f"run_{created_at}",
        "user_id": "test_user_e2e",
        "created_at": created_at,
        "ats_score": ats_score,
        "jd_match_score": jd_match,
        "composite_score": composite,
        "percentile_value": None,
        "percentile_label": percentile_label,
        "current_tier": tier,
        "current_tier_label": tier,
        "current_ctc_min": None,
        "current_ctc_max": None,
        "seniority": "mid",
        "role_family": "engineering",
        "jd_company": None,
        "jd_role_title": None,
        "ats_keyword_match": None,
        "ats_formatting": None,
        "ats_readability": None,
        "ats_impact_metrics": None,
    }


def test_three_session_arc_with_tier_crossing():
    rows = [
        _make_row(43, None, "service", "Below Average", "2026-06-01T10:00:00Z"),
        _make_row(58, 62, "service", "Above Average", "2026-06-04T10:00:00Z"),
        _make_row(70, 78, "product_mid", "Top 25%", "2026-06-08T10:00:00Z"),
    ]
    result = _build_journey_response(rows)

    assert result.total_sessions == 3
    assert result.first_score == 43
    assert result.latest_score == int(70 * 0.4 + 78 * 0.6)
    assert result.score_delta == result.latest_score - 43
    assert result.tier_changed is True
    assert result.first_tier == "service"
    assert result.latest_tier == "product_mid"

    milestone_types = {m.type for m in result.milestones}
    assert "first_analysis" in milestone_types
    assert "tier_unlock" in milestone_types
    assert "percentile_band" in milestone_types


def test_single_session_no_milestones_beyond_first():
    rows = [_make_row(50, None, "service", "Below Average", "2026-06-01T10:00:00Z")]
    result = _build_journey_response(rows)

    assert result.total_sessions == 1
    assert result.score_delta == 0
    assert len(result.milestones) == 1
    assert result.milestones[0].type == "first_analysis"


def test_empty_journey():
    result = _build_journey_response([])
    assert result.total_sessions == 0
    assert result.milestones == []
    assert result.score_delta == 0
