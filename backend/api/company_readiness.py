"""POST /api/company-readiness — re-score readiness for an existing analysis run."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user_id
from backend.db import get_db
from backend.engine.company_readiness import compute_readiness_score, load_company_keys
from backend.models.readiness import CompanyReadinessResult

router = APIRouter()
logger = logging.getLogger(__name__)


class CompanyReadinessRequest(BaseModel):
    run_id: str
    company_key: str
    seniority_override: str | None = None


def _rebuild_resume_und(run_row: dict, resume_row: dict | None) -> dict:
    """Reconstruct minimal A1-shaped dict from corpus tables."""
    resume_und: dict = {}
    if resume_row:
        resume_und["seniority"] = resume_row.get("inferred_seniority") or "mid"
        resume_und["resume_sections"] = resume_row.get("parsed_sections") or {}
        resume_und["sections_present"] = list(resume_und["resume_sections"].keys())
        resume_und["has_metrics"] = (
            (run_row.get("ats_result") or {}).get("breakdown", {}).get("impact_metrics", 0) >= 18
        )
        resume_und["resume_health"] = resume_row.get("resume_health_data") or {}
        resume_und["domains"] = list(resume_row.get("domains") or [])
        resume_und["role_family"] = resume_row.get("role_family") or None
    return resume_und


@router.post("/api/company-readiness", response_model=CompanyReadinessResult)
async def get_company_readiness(
    request: CompanyReadinessRequest,
    user_id: str = Depends(get_current_user_id),
) -> CompanyReadinessResult:
    """Re-score company readiness for an existing run (e.g. manual company selection)."""
    company_key = request.company_key.lower().strip().replace(" ", "")
    if company_key not in load_company_keys():
        raise HTTPException(status_code=400, detail=f"Unknown company: {company_key}")

    db = get_db()
    try:
        run_resp = (
            db.table("analysis_runs")
            .select("*")
            .eq("run_id", request.run_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = run_resp.data or []
        row = rows[0] if rows else None
    except Exception as exc:
        logger.error("Failed to fetch analysis run %s: %s", request.run_id, exc)
        raise HTTPException(status_code=404, detail="Run not found") from exc

    if not row:
        raise HTTPException(status_code=404, detail="Run not found or access denied")

    resume_row = None
    resume_id = row.get("resume_id")
    if resume_id:
        try:
            resume_resp = (
                db.table("resumes")
                .select("*")
                .eq("resume_id", resume_id)
                .limit(1)
                .execute()
            )
            resume_rows = resume_resp.data or []
            resume_row = resume_rows[0] if resume_rows else None
        except Exception as exc:
            logger.warning("Failed to fetch resume %s: %s", resume_id, exc)

    resume_und = _rebuild_resume_und(row, resume_row)
    gap_result = row.get("gap_analysis_result") or {}
    ats_result = row.get("ats_result") or {}
    seniority = request.seniority_override or str(resume_und.get("seniority") or "mid")

    result = compute_readiness_score(
        run_id=request.run_id,
        resume_und=resume_und,
        gap_result=gap_result,
        ats_result=ats_result,
        company_key=company_key,
        seniority=seniority,
    )
    if result is None:
        raise HTTPException(status_code=400, detail=f"Could not score readiness for {company_key}")
    return result
