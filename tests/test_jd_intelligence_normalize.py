"""Tests for Agent 2 seniority field guard (fallback after few-shot prompt)."""

from backend.agents.jd_intelligence import _guard_seniority_fields
from backend.schemas.agent2_schema import JDIntelligenceOutput


def _minimal_payload(**overrides) -> dict:
    base = {
        "role_title": "Director of Engineering",
        "must_have_skills": ["Python"],
        "nice_to_have_skills": [],
        "hidden_signals": [{"signal": "x", "implication": "y"}],
        "semantic_skill_map": {"Python": ["Python"]},
        "seniority_expected": "director",
        "company_type": "enterprise",
        "min_years_required": 10,
        "jd_seniority_level": "unknown",
    }
    base.update(overrides)
    return base


def test_director_in_seniority_expected_coerced():
    normalized = _guard_seniority_fields(_minimal_payload())
    assert normalized["seniority_expected"] == "staff"
    assert normalized["jd_seniority_level"] == "director"
    output = JDIntelligenceOutput(**normalized)
    assert output.seniority_expected.value == "staff"
    assert output.jd_seniority_level.value == "director"


def test_canonical_seniority_unchanged():
    normalized = _guard_seniority_fields(
        _minimal_payload(seniority_expected="senior", jd_seniority_level="senior")
    )
    assert normalized["seniority_expected"] == "senior"
    assert normalized["jd_seniority_level"] == "senior"
