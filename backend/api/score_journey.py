"""GET /api/score-journey — cross-session score timeline, read-only from analysis_runs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.auth import get_current_user_id
from backend.db import get_db
from backend.engine.milestone_detector import _build_journey_response
from backend.models.score_journey import ScoreJourneyResult

router = APIRouter()
logger = logging.getLogger(__name__)

_SELECT_COLUMNS = (
    "run_id,created_at,ats_score,ats_result,percentile_result,"
    "positioning_result,gap_analysis_result,jd_intelligence"
)

# Keyword → role family mapping (checked in order; first match wins)
_ROLE_FAMILY_KEYWORDS: list[tuple[str, str]] = [
    ("data scien", "data"),
    ("machine learning", "data"),
    ("ml engineer", "data"),
    ("data engineer", "data"),
    ("analytics", "data"),
    ("frontend", "frontend"),
    ("front-end", "frontend"),
    ("front end", "frontend"),
    ("react", "frontend"),
    ("angular", "frontend"),
    ("vue", "frontend"),
    ("ios", "mobile"),
    ("android", "mobile"),
    ("mobile", "mobile"),
    ("flutter", "mobile"),
    ("devops", "devops"),
    ("sre", "devops"),
    ("platform engineer", "devops"),
    ("infrastructure", "devops"),
    ("cloud engineer", "devops"),
    ("security", "security"),
    ("full stack", "fullstack"),
    ("fullstack", "fullstack"),
    ("full-stack", "fullstack"),
    ("backend", "backend"),
    ("back-end", "backend"),
    ("back end", "backend"),
    ("software engineer", "backend"),
    ("sde", "backend"),
    ("software development", "backend"),
]


def _infer_role_family(role_title: str | None) -> str | None:
    """Derive a broad role family from a JD role title string."""
    if not role_title:
        return None
    lower = role_title.lower()
    for keyword, family in _ROLE_FAMILY_KEYWORDS:
        if keyword in lower:
            return family
    return None


def _row_to_snapshot_dict(row: dict, user_id: str) -> dict:
    """Flatten one analysis_runs row into a SessionSnapshot-shaped dict."""
    ats_result = row.get("ats_result") or {}
    breakdown = ats_result.get("breakdown") or {}
    positioning = row.get("positioning_result") or {}
    percentile_result = row.get("percentile_result") or {}
    gap_result = row.get("gap_analysis_result") or {}
    jd_intel = row.get("jd_intelligence") or {}

    ats_score = row.get("ats_score") or 0
    jd_match = gap_result.get("jd_match_score_before")
    composite_score = int(ats_score * 0.4 + jd_match * 0.6) if jd_match else int(ats_score)

    role_title = jd_intel.get("role_title")

    return {
        "run_id": row["run_id"],
        "user_id": user_id,
        "created_at": row.get("created_at") or "",
        "ats_score": int(ats_score),
        "jd_match_score": jd_match,
        "composite_score": composite_score,
        "percentile_value": percentile_result.get("percentile"),
        "percentile_label": percentile_result.get("label"),
        "current_tier": positioning.get("current_tier"),
        "current_tier_label": positioning.get("current_tier_label"),
        "current_ctc_min": positioning.get("current_ctc_min"),
        "current_ctc_max": positioning.get("current_ctc_max"),
        "seniority": jd_intel.get("seniority_expected") or None,
        "role_family": _infer_role_family(role_title),
        "jd_company": jd_intel.get("company"),
        "jd_role_title": role_title,
        "ats_keyword_match": breakdown.get("keyword_match"),
        "ats_formatting": breakdown.get("formatting"),
        "ats_readability": breakdown.get("readability"),
        "ats_impact_metrics": breakdown.get("impact_metrics"),
    }


def _dedup_by_date(rows: list[dict]) -> list[dict]:
    """Keep the latest run per calendar date (UTC). Input must be sorted by created_at ASC."""
    from itertools import groupby

    result = []
    for _date_key, group in groupby(rows, key=lambda r: r["created_at"][:10]):
        *_, latest = group
        result.append(latest)
    return result


@router.get("/api/score-journey", response_model=ScoreJourneyResult)
async def get_score_journey(user_id: str = Depends(get_current_user_id)) -> ScoreJourneyResult:
    """Return the authenticated user's full Score Journey across all analysis runs."""
    db = get_db()
    result = (
        db.table("analysis_runs")
        .select(_SELECT_COLUMNS)
        .eq("user_id", user_id)
        .order("created_at", desc=False)
        .execute()
    )
    raw_rows = [_row_to_snapshot_dict(row, user_id) for row in (result.data or [])]
    rows = _dedup_by_date(raw_rows)
    return _build_journey_response(rows)
