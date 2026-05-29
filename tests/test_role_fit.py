"""Tests for deterministic role fit scoring."""

from backend.role_fit import compute_role_fit


def test_underqualified_vp_from_junior():
    resume = {"experience_years": 3, "seniority": "junior"}
    jd = {"min_years_required": 14, "jd_seniority_level": "vp"}
    gap = {"section_gaps": [{"gap_reason": "No board-level strategy experience"}]}
    result = compute_role_fit(resume, jd, gap)
    assert result["fitness"] == "underqualified"
    assert result["experience_gap"] == 11
    assert result["seniority_gap"] >= 3


def test_stretch_senior_ic():
    resume = {"experience_years": 6, "seniority": "mid"}
    jd = {"min_years_required": 8, "jd_seniority_level": "senior"}
    result = compute_role_fit(resume, jd, {})
    assert result["fitness"] == "stretch"
    assert result["experience_gap"] == 2
    assert result["seniority_gap"] == 1


def test_qualified_em():
    resume = {"experience_years": 9, "seniority": "senior"}
    jd = {"min_years_required": 6, "jd_seniority_level": "mid"}
    result = compute_role_fit(resume, jd, {})
    assert result["fitness"] == "qualified"
    assert result["experience_gap"] == 0
    assert result["seniority_gap"] == 0


def test_missing_fields_safe():
    result = compute_role_fit({}, {}, {})
    assert result["fitness"] in ("qualified", "stretch", "underqualified")
    assert 0 <= result["score"] <= 100


def test_unknown_jd_seniority_uses_experience_only():
    resume = {"experience_years": 3, "seniority": "junior"}
    jd = {"min_years_required": 10, "jd_seniority_level": "unknown"}
    result = compute_role_fit(resume, jd, {})
    assert result["seniority_gap"] == 0
    assert result["fitness"] == "underqualified"


def test_zero_min_years_no_experience_gap():
    """min_years=0 → exp gap 0; seniority_gap still applies for VP-level JD."""
    resume = {"experience_years": 3, "seniority": "junior"}
    jd = {"min_years_required": 0, "jd_seniority_level": "vp"}
    result = compute_role_fit(resume, jd, {})
    assert result["experience_gap"] == 0
    assert result["seniority_gap"] >= 3


def test_em_17_years_director_jd_is_stretch_not_underqualified():
    """EM → AD/Director with 17Y vs 15+ min should be stretch, not no-fit."""
    resume = {"experience_years": 17, "seniority": "em"}
    jd = {
        "min_years_required": 15,
        "jd_seniority_level": "director",
        "seniority_expected": "staff",
    }
    result = compute_role_fit(resume, jd, {})
    assert result["experience_gap"] == 0
    assert result["seniority_gap"] == 1
    assert result["fitness"] == "stretch"


def test_director_resume_director_jd_qualified():
    """Resume tagged director must not default to mid-level rank."""
    resume = {"experience_years": 17, "seniority": "director"}
    jd = {"min_years_required": 15, "jd_seniority_level": "director"}
    result = compute_role_fit(resume, jd, {})
    assert result["seniority_gap"] == 0
    assert result["fitness"] == "qualified"


def test_staff_resume_director_jd_two_level_stretch():
    """Staff IC → Director with YoE met is a 2-level stretch."""
    resume = {"experience_years": 17, "seniority": "staff"}
    jd = {"min_years_required": 15, "jd_seniority_level": "director"}
    result = compute_role_fit(resume, jd, {})
    assert result["seniority_gap"] == 2
    assert result["fitness"] == "stretch"
