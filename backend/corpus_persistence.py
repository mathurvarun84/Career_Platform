"""Supabase persistence for the RIP V2 labeled corpus (four-key spine)."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from backend.db import get_db
from backend.utils.pii_stripper import strip_pii

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enum_value(raw: Any) -> str:
    if raw is None:
        return ""
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw)


def _extract_companies(resume_und: dict[str, Any]) -> list[str]:
    sections = resume_und.get("resume_sections") or {}
    companies: list[str] = []
    for key in ("experience", "Experience", "work_experience", "Work Experience"):
        block = sections.get(key)
        if not isinstance(block, dict):
            continue
        for entry in block.get("sub_entries") or []:
            label = (entry.get("label") or "").strip()
            if not label:
                continue
            company = label.split("|")[0].split("—")[0].split(" - ")[0].strip()
            if company and company not in companies:
                companies.append(company)
    return companies


def _extract_highest_education(resume_und: dict[str, Any]) -> str | None:
    sections = resume_und.get("resume_sections") or {}
    for key in ("education", "Education"):
        block = sections.get(key)
        if isinstance(block, dict):
            text = (block.get("full_text") or "").strip()
            if text:
                return text[:500]
    return None


def _gap_counts(gap_result: dict[str, Any] | None) -> tuple[int, int, int, int]:
    gaps = (gap_result or {}).get("section_gaps") or (gap_result or {}).get("gaps") or []
    surface = structural = evidence = 0
    for gap in gaps:
        gap_type = _enum_value(gap.get("gap_type")).lower()
        if gap_type == "surface":
            surface += 1
        elif gap_type == "structural":
            structural += 1
        elif gap_type == "evidence":
            evidence += 1
    return len(gaps), surface, structural, evidence


def _jd_content_hash(jd_text: str) -> str:
    normalized = " ".join(jd_text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _percentile_score(percentile: Any) -> float | None:
    if isinstance(percentile, dict):
        raw = percentile.get("percentile")
        return float(raw) if raw is not None else None
    if percentile is not None:
        return float(percentile)
    return None


def _seniority_rank(jd_intel: dict[str, Any]) -> int | None:
    from backend.role_fit import _jd_seniority_rank

    rank = _jd_seniority_rank(jd_intel)
    return rank if rank > 0 else None


def _gap_type_for_patch(gap_result: dict[str, Any] | None, gap_id: str) -> str:
    if not gap_id:
        return "Surface"
    for source in (
        (gap_result or {}).get("priority_fixes") or [],
        (gap_result or {}).get("section_gaps") or [],
        (gap_result or {}).get("gaps") or [],
    ):
        for item in source:
            if str(item.get("gap_id") or item.get("change_id") or "") != gap_id:
                continue
            gap_type = _enum_value(item.get("gap_type")).capitalize()
            if gap_type in {"Surface", "Structural", "Evidence"}:
                return gap_type
    return "Surface"


def save_corpus_run(
    *,
    user_id: str,
    run_id: str,
    resume_text: str,
    file_name: str,
    resume_und: dict[str, Any],
    jd_text: str,
    jd_source: str = "pasted",
    target_company: str | None,
    final_result: dict[str, Any],
    elapsed_ms: int,
) -> dict[str, str | None]:
    """
    Persist resume, JD, and analysis run rows for one pipeline execution.

    Returns:
        Dict with resume_id, jd_id, run_id keys (values None on failure).
    """
    empty = {"resume_id": None, "jd_id": None, "run_id": None}
    try:
        db = get_db()
    except Exception as exc:
        logger.warning("save_corpus_run skipped (no db): %s", exc)
        return empty

    resume_und = resume_und or {}
    jd_intel = final_result.get("jd_intelligence") or {}
    gap_result = final_result.get("gap") or {}
    role_fit = final_result.get("role_fit") or {}
    raw_text_clean = strip_pii(resume_text)

    seniority = _enum_value(resume_und.get("seniority")) or None
    years = (
        resume_und.get("total_years")
        or resume_und.get("years_of_experience")
        or resume_und.get("experience_years")
    )
    skills = list(resume_und.get("tech_stack") or [])

    storage_path = f"resumes/{user_id}/{run_id}/{file_name or 'resume.pdf'}"

    try:
        resume_insert = (
            db.table("resumes")
            .insert(
                {
                    "user_id": user_id,
                    "storage_path": storage_path,
                    "parsed_sections": resume_und.get("resume_sections") or {},
                    "raw_text_clean": raw_text_clean,
                    "inferred_seniority": seniority,
                    "years_of_experience": years,
                    "word_count": len(resume_text.split()),
                    "skills_mentioned": skills,
                    "companies_worked_at": _extract_companies(resume_und),
                    "highest_education": _extract_highest_education(resume_und),
                    "resume_health_data": resume_und.get("resume_health") or None,
                    "domains": list(resume_und.get("domains") or []),
                    "has_metrics": bool(resume_und.get("has_metrics")),
                    "has_summary": bool(resume_und.get("has_summary")),
                    "keyword_density_verdict": resume_und.get("keyword_density_verdict") or None,
                    "role_family": resume_und.get("role_family") or None,
                }
            )
            .execute()
        )
        resume_id = resume_insert.data[0]["resume_id"] if resume_insert.data else None
        if not resume_id:
            raise ValueError("resumes insert returned no resume_id")
    except Exception as exc:
        logger.warning("save_corpus_run resume insert failed: %s", exc)
        return empty

    jd_id = None
    if jd_text and jd_text.strip():
        role_title = jd_intel.get("role_title") or target_company or "unknown"
        company = target_company or jd_intel.get("company") or "unknown"
        try:
            jd_insert = (
                db.table("job_descriptions")
                .insert(
                    {
                        "user_id": user_id,
                        "target_company": company,
                        "target_role": role_title,
                        "jd_source": jd_source,
                        "source_url": None,
                        "jd_intelligence": jd_intel,
                        "raw_text": jd_text,
                        "jd_seniority_level": _seniority_rank(jd_intel),
                        "min_years_required": jd_intel.get("min_years_required"),
                        "required_skills": jd_intel.get("must_have_skills") or [],
                        "preferred_skills": jd_intel.get("nice_to_have_skills") or [],
                        "content_hash": _jd_content_hash(jd_text),
                    }
                )
                .execute()
            )
            jd_id = jd_insert.data[0]["jd_id"] if jd_insert.data else None
        except Exception as exc:
            logger.warning("save_corpus_run jd insert failed: %s", exc)

    gap_count, surface_count, structural_count, evidence_count = _gap_counts(gap_result)
    early_exit = bool(
        jd_text
        and role_fit.get("fitness") == "underqualified"
        and final_result.get("rewrites") is None
    )

    sim_result = final_result.get("sim") or None
    shortlist_rate = (sim_result or {}).get("shortlist_rate") if sim_result else None
    jd_match_score = gap_result.get("jd_match_score_before") or gap_result.get("jd_match_score")
    missing_keywords = list(gap_result.get("missing_keywords") or [])

    try:
        db.table("analysis_runs").insert(
            {
                "run_id": run_id,
                "user_id": user_id,
                "resume_id": resume_id,
                "jd_id": jd_id,
                "ats_result": final_result.get("ats"),
                "role_fit_result": role_fit or None,
                "gap_analysis_result": gap_result or None,
                "rewrite_result": final_result.get("rewrites"),
                "patch_result": final_result.get("patches"),
                "positioning_result": final_result.get("positioning"),
                "percentile_result": final_result.get("percentile"),
                "jd_intelligence": jd_intel or None,
                "ats_score": (final_result.get("ats") or {}).get("score"),
                "role_fit_band": role_fit.get("fitness"),
                "percentile": _percentile_score(final_result.get("percentile")),
                "gap_count": gap_count,
                "surface_gap_count": surface_count,
                "structural_gap_count": structural_count,
                "evidence_gap_count": evidence_count,
                "run_duration_ms": elapsed_ms,
                "early_exit": early_exit,
                "sim_result": sim_result,
                "shortlist_rate": shortlist_rate,
                "jd_match_score": jd_match_score,
                "estimated_score_after": gap_result.get("estimated_score_after"),
                "missing_keywords": missing_keywords,
                "role_family": resume_und.get("role_family") or None,
                "company_type": _enum_value(jd_intel.get("company_type")) or None,
                "seniority_expected": _enum_value(jd_intel.get("seniority_expected")) or None,
            }
        ).execute()
    except Exception as exc:
        logger.warning("save_corpus_run analysis_runs insert failed: %s", exc)
        return {"resume_id": resume_id, "jd_id": jd_id, "run_id": None}

    logger.info(
        "Corpus run saved: user=%s run=%s resume=%s jd=%s",
        user_id,
        run_id,
        resume_id,
        jd_id,
    )
    return {"resume_id": resume_id, "jd_id": jd_id, "run_id": run_id}


def record_patch_decisions(
    *,
    run_id: str,
    user_id: str,
    gap_result: dict[str, Any] | None,
    patches: list[dict[str, Any]],
    applied_ids: list[str],
    rejected_ids: list[str],
    style_used: str | None = None,
) -> None:
    """Upsert patch accept/reject decisions for a run."""
    if not run_id or not patches:
        return
    try:
        db = get_db()
    except Exception as exc:
        logger.warning("record_patch_decisions skipped (no db): %s", exc)
        return

    patch_map = {p.get("patch_id"): p for p in patches if p.get("patch_id")}
    decided_at = _utc_now_iso()

    for patch_id, accepted in (
        *((pid, True) for pid in applied_ids),
        *((pid, False) for pid in rejected_ids),
    ):
        patch = patch_map.get(patch_id)
        if not patch:
            continue

        entry_label = patch.get("section") or "unknown"
        sub_label = (patch.get("sub_entry_label") or "").strip()
        if sub_label:
            entry_label = f"{entry_label} > {sub_label}"

        row = {
            "run_id": run_id,
            "user_id": user_id,
            "source_patch_id": patch_id,
            "entry_label": entry_label,
            "gap_type": _gap_type_for_patch(gap_result, str(patch.get("gap_id") or "")),
            "gap_skill": patch.get("keyword") or None,
            "original_text": patch.get("original_text") or "",
            "patched_text": patch.get("replacement_text") or patch.get("proposed_text") or "",
            "style_used": style_used,
            "user_accepted": accepted,
            "decided_at": decided_at,
        }

        try:
            db.table("patches").upsert(row, on_conflict="run_id,source_patch_id").execute()
        except Exception as exc:
            logger.warning("record_patch_decisions upsert failed for %s: %s", patch_id, exc)
