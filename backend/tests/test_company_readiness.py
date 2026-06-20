"""Unit tests for Company Readiness scoring engine — 3 resumes × 3 companies."""

from __future__ import annotations

import pytest

from backend.engine.company_readiness import READINESS_DISCLAIMER, compute_readiness_score

VALID_LABELS = {"Not Ready", "Partially Ready", "Ready", "Highly Ready"}


def _resume_a() -> dict:
    """Senior IC — strong metrics, data signals, ownership."""
    return {
        "seniority": "senior",
        "has_metrics": True,
        "sections_present": ["experience", "projects", "certifications"],
        "resume_health": {
            "expected_signals": [
                {"signal": "ownership of outcomes", "present": True, "strength": "strong"},
            ],
        },
        "resume_sections": {
            "experience": {
                "full_text": (
                    "Led checkout API serving 2M+ daily users, reducing p99 latency by 40%. "
                    "Ran A/B tests with SQL analytics dashboards and funnel cohort analysis. "
                    "Collaborated with product and design stakeholders on cross-functional alignment."
                ),
            },
            "projects": {"full_text": "Built experiment platform with metric tracking."},
        },
    }


def _resume_b() -> dict:
    """Mid IC — weak signals."""
    return {
        "seniority": "mid",
        "has_metrics": False,
        "sections_present": ["experience"],
        "resume_health": {"expected_signals": []},
        "resume_sections": {
            "experience": {"full_text": "Software developer working on backend services."},
        },
    }


def _resume_c() -> dict:
    """EM — collaboration-heavy, partial data signals."""
    return {
        "seniority": "em",
        "has_metrics": True,
        "sections_present": ["experience", "projects"],
        "resume_health": {"expected_signals": []},
        "resume_sections": {
            "experience": {
                "full_text": (
                    "Engineering Manager aligning product, design, and ops teams. "
                    "Drove cross-functional stakeholder alignment across cross-team initiatives. "
                    "Collaborated with product on roadmap delivery."
                ),
            },
            "projects": {"full_text": "Team mentoring and hiring calibration."},
        },
    }


def _ats_strong() -> dict:
    return {"score": 75, "breakdown": {"impact_metrics": 20}}


def _ats_weak() -> dict:
    return {"score": 45, "breakdown": {"impact_metrics": 10}}


def _ats_mid() -> dict:
    return {"score": 62, "breakdown": {"impact_metrics": 18}}


def _gap_strong() -> dict:
    return {"jd_match_score_before": 72, "priority_fixes": []}


def _gap_weak() -> dict:
    return {
        "jd_match_score_before": 38,
        "priority_fixes": [
            {"gap_reason": "technical depth missing in system design"},
            {"gap_reason": "another technical depth gap"},
        ],
    }


def _gap_mid() -> dict:
    return {"jd_match_score_before": 55, "priority_fixes": []}


def _assert_common(result, company_key: str):
    assert result is not None
    assert 0 <= result.readiness_score <= 100
    assert result.readiness_label in VALID_LABELS
    assert result.dimensions_passing <= result.dimensions_total
    assert len(result.dimensions) > 0
    assert result.company_key == company_key
    assert result.disclaimer == READINESS_DISCLAIMER
    assert all(d.display_label for d in result.dimensions)
    if result.dimensions_passing == result.dimensions_total:
        assert result.top_fix is None
    elif any(not d.passes for d in result.dimensions):
        assert result.top_fix is not None or not any(d.fix_hint for d in result.dimensions if not d.passes)


@pytest.mark.parametrize(
    "resume_fn, ats, gap, company, seniority",
    [
        (_resume_a, _ats_strong, _gap_strong, "amazon", "senior"),
        (_resume_a, _ats_strong, _gap_strong, "flipkart", "senior"),
        (_resume_a, _ats_strong, _gap_strong, "google", "senior"),
        (_resume_b, _ats_weak, _gap_weak, "amazon", "mid"),
        (_resume_b, _ats_weak, _gap_weak, "flipkart", "mid"),
        (_resume_b, _ats_weak, _gap_weak, "google", "mid"),
        (_resume_c, _ats_mid, _gap_mid, "amazon", "em"),
        (_resume_c, _ats_mid, _gap_mid, "flipkart", "em"),
        (_resume_c, _ats_mid, _gap_mid, "google", "em"),
    ],
)
def test_compute_readiness_matrix(resume_fn, ats, gap, company, seniority):
    result = compute_readiness_score(
        run_id="run-test",
        resume_und=resume_fn(),
        gap_result=gap(),
        ats_result=ats(),
        company_key=company,
        seniority=seniority,
    )
    _assert_common(result, company)


def test_strong_resume_scores_higher_than_weak_for_amazon():
    strong = compute_readiness_score(
        run_id="run-a",
        resume_und=_resume_a(),
        gap_result=_gap_strong(),
        ats_result=_ats_strong(),
        company_key="amazon",
        seniority="senior",
    )
    weak = compute_readiness_score(
        run_id="run-b",
        resume_und=_resume_b(),
        gap_result=_gap_weak(),
        ats_result=_ats_weak(),
        company_key="amazon",
        seniority="mid",
    )
    assert strong.readiness_score > weak.readiness_score


def test_unknown_company_returns_none():
    result = compute_readiness_score(
        run_id="run-x",
        resume_und=_resume_a(),
        gap_result=_gap_strong(),
        ats_result=_ats_strong(),
        company_key="wipro",
        seniority="senior",
    )
    assert result is None


def test_display_labels_not_pass_fail():
    result = compute_readiness_score(
        run_id="run-y",
        resume_und=_resume_b(),
        gap_result=_gap_weak(),
        ats_result=_ats_weak(),
        company_key="flipkart",
        seniority="mid",
    )
    for dim in result.dimensions:
        assert dim.display_label not in ("PASS", "DEVELOPING", "NEEDS WORK")
