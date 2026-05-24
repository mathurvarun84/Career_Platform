"""
Deterministic role fit scoring from Agent 1 + Agent 2 + gap outputs. No LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict

_SENIORITY_RANK = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "staff": 4,
    "manager": 5,
    "director": 6,
    "vp": 7,
    "c-suite": 8,
    "unknown": 0,
}

_RESUME_SENIORITY_RANK = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "staff": 4,
}

_RECOMMENDED_ROLES = {
    "junior": ["Software Engineer", "Junior SDE"],
    "mid": ["Software Engineer II", "SDE 2", "Backend Engineer"],
    "senior": ["Senior Software Engineer", "Staff Engineer", "Tech Lead"],
    "staff": ["Staff Engineer", "Principal Engineer", "Engineering Lead", "EM (small team)"],
}

_NEXT_STEP_ROLES = {
    "junior": ["SDE 2", "Software Engineer II"],
    "mid": ["Senior Software Engineer", "Tech Lead"],
    "senior": ["Staff Engineer", "Engineering Lead", "Engineering Manager"],
    "staff": ["Senior Staff Engineer", "Principal Engineer", "Engineering Manager"],
}

_EVIDENCE_SIGNALS = {
    "mentor",
    "coach",
    "1:1",
    "performance management",
    "promotion",
    "stakeholder",
    "executive",
    "p&l",
    "budget",
    "hiring decision",
    "org design",
    "succession",
    "board",
    "vision",
    "strategy",
}


def _enum_value(raw: Any) -> str:
    """Coerce enum or string seniority values to lowercase string."""
    if raw is None:
        return ""
    if hasattr(raw, "value"):
        return str(raw.value).lower().strip()
    return str(raw).lower().strip()


def compute_role_fit(
    resume_und: dict,
    jd_intel: dict,
    gap_result: dict | None = None,
) -> dict:
    """
    Deterministic role fit computation. Zero LLM calls.

    Returns:
        fitness: qualified | stretch | underqualified
        score: 0-100
        experience_gap: years short (0 if met)
        seniority_gap: levels short (0 if met)
        unanswerable_evidence_gaps: int
        recommended_roles: roles candidate is qualified for
        next_step_roles: best next-step roles toward goal
    """
    candidate_years = int(
        resume_und.get("total_years")
        or resume_und.get("years_of_experience")
        or resume_und.get("experience_years")
        or 0
    )
    jd_min_years = int(jd_intel.get("min_years_required") or 0)
    experience_gap = max(0, jd_min_years - candidate_years)

    raw_resume_seniority = _enum_value(resume_und.get("seniority")) or "mid"
    raw_jd_seniority = _enum_value(jd_intel.get("jd_seniority_level")) or "unknown"

    resume_rank = _RESUME_SENIORITY_RANK.get(raw_resume_seniority, 2)
    jd_rank = _SENIORITY_RANK.get(raw_jd_seniority, 0)
    seniority_gap = max(0, jd_rank - resume_rank) if jd_rank > 0 else 0

    gap_result = gap_result or {}
    unanswerable = 0
    for gap in (gap_result.get("section_gaps") or gap_result.get("gaps") or []):
        reason = (gap.get("gap_reason") or "").lower()
        if any(sig in reason for sig in _EVIDENCE_SIGNALS):
            unanswerable += 1

    score = 100
    score -= min(experience_gap * 6, 50)
    score -= min(seniority_gap * 12, 36)
    score -= min(unanswerable * 2, 14)
    score = max(0, min(100, score))

    if experience_gap > 5 or seniority_gap >= 3:
        fitness = "underqualified"
    elif experience_gap > 1 or seniority_gap >= 1:
        fitness = "stretch"
    else:
        fitness = "qualified"

    return {
        "fitness": fitness,
        "score": score,
        "experience_gap": experience_gap,
        "seniority_gap": seniority_gap,
        "unanswerable_evidence_gaps": unanswerable,
        "candidate_years": candidate_years,
        "jd_min_years": jd_min_years,
        "recommended_roles": _RECOMMENDED_ROLES.get(raw_resume_seniority, []),
        "next_step_roles": _NEXT_STEP_ROLES.get(raw_resume_seniority, []),
    }
