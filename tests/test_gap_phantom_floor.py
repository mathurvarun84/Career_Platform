"""Tests for A3 phantom-gap suppression and minimum gap floor."""

from backend.agents.gap_analyzer import (
    _apply_phantom_gap_filter,
    _ensure_minimum_gap_floor,
    _count_actionable_gaps,
)


def test_phantom_gap_suppressed_on_qualified_match():
    resume_analysis = {
        "experience_years": 6,
        "seniority": "senior",
        "tech_stack": ["Python", "MLflow", "CI/CD"],
        "resume_sections": {
            "experience": {
                "full_text": "Built MLflow pipelines with CI/CD deployment",
                "sub_entries": [],
            }
        },
    }
    jd_analysis = {
        "role_title": "Senior Data Scientist",
        "min_years_required": 5,
        "jd_seniority_level": "senior",
        "must_have_skills": ["MLOps", "Python"],
        "semantic_skill_map": {"MLOps": ["MLflow", "CI/CD", "model monitoring"]},
    }
    gaps = [{
        "section": "experience",
        "needs_change": True,
        "gap_reason": "Missing MLOps experience",
        "missing_keywords": ["MLOps"],
        "rewrite_instruction": "Add MLOps",
        "sub_changes": [],
    }]
    filtered = _apply_phantom_gap_filter(gaps, resume_analysis, jd_analysis, "")
    assert filtered[0]["needs_change"] is False


def test_minimum_gap_floor_injects_catch_all_for_underqualified():
    resume_analysis = {"experience_years": 0, "seniority": "junior"}
    jd_analysis = {
        "role_title": "Senior Data Scientist",
        "min_years_required": 5,
        "jd_seniority_level": "senior",
        "must_have_skills": ["Python", "TensorFlow", "MLOps", "Spark", "SQL"],
    }
    gaps = [{
        "section": "skills",
        "needs_change": True,
        "gap_reason": "Missing Python",
        "missing_keywords": ["Python"],
        "rewrite_instruction": "Add Python",
        "sub_changes": [],
    }]
    assert _count_actionable_gaps(gaps) < 5
    enriched = _ensure_minimum_gap_floor(gaps, resume_analysis, jd_analysis)
    assert _count_actionable_gaps(enriched) >= 2
    assert any("seniority" in (g.get("gap_reason") or "").lower() for g in enriched)
