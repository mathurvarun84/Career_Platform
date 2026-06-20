"""
Integration test: runs compute_readiness_score() against realistic fixtures and asserts
evaluator-patch fields (display_label, disclaimer).
"""

from backend.engine.company_readiness import compute_readiness_score

FIXTURE_RESUME_UND = {
    "resume_health": {
        "expected_signals": [
            {"signal": "ownership", "present": True, "strength": "strong"},
        ]
    },
    "impact_metrics": True,
    "sections_present": ["experience", "projects", "skills"],
    "resume_sections": {
        "experience": {
            "full_text": (
                "Owned the checkout redesign end to end, including post-launch "
                "metric tracking and iteration based on conversion data. "
                "Collaborated with design and product teams to ship a cross-functional "
                "initiative improving conversion by 12%."
            )
        }
    },
}

FIXTURE_GAP_RESULT = {
    "jd_match_score_before": 71,
    "priority_fixes": [],
}

FIXTURE_ATS_RESULT = {
    "score": 72,
    "breakdown": {
        "keyword_match": 18,
        "formatting": 18,
        "readability": 18,
        "impact_metrics": 19,
    },
}

_DISPLAY_BY_STRENGTH = {
    "strong": "Signal Found",
    "developing": "Partial Signal",
    "weak": "Signal Not Found",
}


def test_flipkart_readiness_full_shape():
    result = compute_readiness_score(
        run_id="test_run_001",
        resume_und=FIXTURE_RESUME_UND,
        gap_result=FIXTURE_GAP_RESULT,
        ats_result=FIXTURE_ATS_RESULT,
        company_key="flipkart",
        seniority="mid",
    )

    assert result is not None
    assert 0 <= result.readiness_score <= 100
    assert result.readiness_label in ["Not Ready", "Partially Ready", "Ready", "Highly Ready"]
    assert result.dimensions_passing <= result.dimensions_total
    assert len(result.dimensions) >= 3

    assert result.disclaimer
    for dim in result.dimensions:
        assert dim.display_label in ["Signal Found", "Partial Signal", "Signal Not Found"]
        assert dim.display_label == _DISPLAY_BY_STRENGTH[dim.signal_strength]


def test_unknown_company_returns_none():
    result = compute_readiness_score(
        run_id="test_run_002",
        resume_und=FIXTURE_RESUME_UND,
        gap_result=FIXTURE_GAP_RESULT,
        ats_result=FIXTURE_ATS_RESULT,
        company_key="wipro",
        seniority="mid",
    )
    assert result is None


def test_weak_resume_scores_lower_than_strong_resume():
    weak_resume = {
        "resume_health": {"expected_signals": []},
        "impact_metrics": False,
        "sections_present": ["experience"],
        "resume_sections": {
            "experience": {"full_text": "Worked on backend systems and fixed bugs."}
        },
    }
    weak_result = compute_readiness_score(
        run_id="test_run_003",
        resume_und=weak_resume,
        gap_result={"jd_match_score_before": 40, "priority_fixes": []},
        ats_result={
            "score": 45,
            "breakdown": {
                "keyword_match": 10,
                "formatting": 10,
                "readability": 10,
                "impact_metrics": 8,
            },
        },
        company_key="flipkart",
        seniority="mid",
    )
    strong_result = compute_readiness_score(
        run_id="test_run_004",
        resume_und=FIXTURE_RESUME_UND,
        gap_result=FIXTURE_GAP_RESULT,
        ats_result=FIXTURE_ATS_RESULT,
        company_key="flipkart",
        seniority="mid",
    )
    assert weak_result is not None
    assert strong_result is not None
    assert weak_result.readiness_score < strong_result.readiness_score
