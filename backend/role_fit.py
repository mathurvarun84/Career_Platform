"""
Deterministic role fit scoring from Agent 1 + Agent 2 + gap outputs. No LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict

# Unified ladder: IC (1–4) → management (5–6) → exec (7–8).
# Resume Agent 1 uses em | senior_em | director; JD Agent 2 uses manager | director | vp.
_SENIORITY_RANK = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "staff": 4,
    "em": 5,
    "senior_em": 5,
    "manager": 5,
    "engineering_manager": 5,
    "director": 6,
    "associate_director": 6,
    "ad": 6,
    "vp": 7,
    "c-suite": 8,
    "unknown": 0,
}

_RECOMMENDED_ROLES = {
    "junior": ["Software Engineer", "Junior SDE"],
    "mid": ["Software Engineer II", "SDE 2", "Backend Engineer"],
    "senior": ["Senior Software Engineer", "Staff Engineer", "Tech Lead"],
    "staff": ["Staff Engineer", "Principal Engineer", "Engineering Lead", "EM (small team)"],
    "em": ["Engineering Manager", "Senior Engineering Manager"],
    "senior_em": ["Senior Engineering Manager", "Director of Engineering (small org)"],
    "director": ["Director of Engineering", "Senior Director of Engineering"],
}

_NEXT_STEP_ROLES = {
    "junior": ["SDE 2", "Software Engineer II"],
    "mid": ["Senior Software Engineer", "Tech Lead"],
    "senior": ["Staff Engineer", "Engineering Lead", "Engineering Manager"],
    "staff": ["Senior Staff Engineer", "Principal Engineer", "Engineering Manager"],
    "em": ["Senior Engineering Manager", "Director of Engineering"],
    "senior_em": ["Director of Engineering", "Associate Director of Engineering"],
    "director": ["Senior Director of Engineering", "VP Engineering"],
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
    return str(raw).lower().strip().replace(" ", "_")


def _seniority_rank(label: str, years: int = 0, *, for_jd: bool = False) -> int:
    """
    Map a seniority label to the unified ladder.

    JD unknown → 0 (ignore seniority gap). Resume unknown → years-based inference
    so 17Y EM profiles are not treated as mid-level IC.
    """
    key = _enum_value(label) or "unknown"
    rank = _SENIORITY_RANK.get(key, 0)
    if rank > 0:
        return rank
    if for_jd:
        return 0
    if years >= 15:
        return _SENIORITY_RANK["em"]
    if years >= 11:
        return _SENIORITY_RANK["staff"]
    if years >= 6:
        return _SENIORITY_RANK["senior"]
    if years >= 3:
        return _SENIORITY_RANK["mid"]
    return _SENIORITY_RANK["junior"]


def _jd_seniority_rank(jd_intel: dict) -> int:
    """Prefer explicit JD band; fall back to seniority_expected when band is unknown."""
    primary = _seniority_rank(
        jd_intel.get("jd_seniority_level") or "", for_jd=True
    )
    if primary > 0:
        return primary
    return _seniority_rank(jd_intel.get("seniority_expected") or "", for_jd=True)


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

    resume_rank = _seniority_rank(raw_resume_seniority, candidate_years, for_jd=False)
    jd_rank = _jd_seniority_rank(jd_intel)
    seniority_gap = max(0, jd_rank - resume_rank) if jd_rank > 0 else 0

    # Strong YoE meeting JD minimum → do not label as underqualified for 1–2 level stretch.
    if experience_gap == 0 and candidate_years >= jd_min_years and seniority_gap <= 2:
        seniority_underqualified = False
    else:
        seniority_underqualified = seniority_gap >= 3

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

    if experience_gap > 5 or seniority_underqualified:
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
