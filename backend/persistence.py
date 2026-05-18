"""Persistence layer for Supabase (resume_uploads + analysis_results)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.db import get_db

logger = logging.getLogger(__name__)


def _extract_denormalized_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    """Pull score fields from orchestrator result for analysis_results columns."""
    fields: Dict[str, Any] = {}

    ats_data = result.get("ats") or {}
    fields["ats_score"] = ats_data.get("score")

    gap_data = result.get("gap") or {}
    fields["jd_match_score"] = (
        gap_data.get("jd_match_score_before")
        or gap_data.get("jd_match_score")
        or gap_data.get("match_score")
        or (result.get("resume") or {}).get("match_score")
    )

    sim_data = result.get("sim") or {}
    fields["shortlist_rate"] = sim_data.get("shortlist_rate")

    percentile_data = result.get("percentile") or {}
    if isinstance(percentile_data, dict):
        fields["percentile_value"] = percentile_data.get("percentile")
    elif percentile_data is not None:
        fields["percentile_value"] = percentile_data

    return {k: v for k, v in fields.items() if v is not None}


def _insert_resume_upload(
    db,
    *,
    user_id: str,
    file_name: str,
    file_size: int,
    jd_text: str,
    target_company: Optional[str],
    target_role: Optional[str],
) -> str:
    """Insert resume_uploads row using live Supabase column names."""
    row: Dict[str, Any] = {
        "user_id": user_id,
        "file_name": file_name,
        "jd_text": jd_text or None,
        "target_company": target_company,
        "target_role": target_role,
        "has_jd": bool(jd_text and jd_text.strip()),
    }
    if file_size > 0:
        row["file_size_bytes"] = file_size

    insert = db.table("resume_uploads").insert(row).execute()
    upload_id = insert.data[0]["id"] if insert.data else None
    if not upload_id:
        raise ValueError("resume_uploads insert returned no id")
    return upload_id


def save_analysis(
    user_id: str,
    file_name: str,
    file_size: int,
    jd_text: str,
    target_company: Optional[str],
    target_role: Optional[str],
    result: Dict[str, Any],
) -> str:
    """
    Persist analysis to Supabase: resume_uploads + analysis_results.

    Returns:
        upload_id (resume_uploads.id)
    """
    db = get_db()

    upload_id = _insert_resume_upload(
        db,
        user_id=user_id,
        file_name=file_name,
        file_size=file_size,
        jd_text=jd_text,
        target_company=target_company,
        target_role=target_role,
    )

    denormalized = _extract_denormalized_fields(result)

    insert_2 = db.table("analysis_results").insert(
        {
            "upload_id": upload_id,
            "user_id": user_id,
            "full_result": result,
            **denormalized,
        }
    ).execute()

    if not insert_2.data:
        raise ValueError("analysis_results insert failed")

    try:
        db.rpc("increment_upload_count", {"p_user_id": user_id}).execute()
    except Exception as exc:
        logger.warning("increment_upload_count RPC failed: %s", exc)

    logger.info(
        "Analysis saved: user=%s upload_id=%s ats=%s",
        user_id,
        upload_id,
        denormalized.get("ats_score"),
    )
    return upload_id
