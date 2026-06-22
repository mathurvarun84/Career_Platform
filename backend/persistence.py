"""Persistence layer for Supabase (resume_uploads + analysis_results)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from backend.db import get_db

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<!\d)(\+\d{1,3}[\s.-]?)?\d[\d\s.-]{8,12}\d(?!\d)")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_ADDRESS_LINE_RE = re.compile(
    r"^.*\b\d{1,5}[A-Za-z]?[,\s]+[\w.\- ]*\b(street|st|avenue|ave|road|rd|lane|ln|drive|dr|"
    r"block|sector|nagar|colony|apartment|apt|floor|flr)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_PIN_CODE_RE = re.compile(r"\b\d{6}\b")


def _strip_pii(text: str) -> str:
    """Redact emails, phone numbers, URLs, and address-like lines from resume text."""
    if not text:
        return text

    scrubbed = _EMAIL_RE.sub("[redacted-email]", text)
    scrubbed = _URL_RE.sub("[redacted-url]", scrubbed)
    scrubbed = _ADDRESS_LINE_RE.sub("[redacted-address]", scrubbed)
    scrubbed = _PHONE_RE.sub("[redacted-phone]", scrubbed)
    scrubbed = _PIN_CODE_RE.sub("[redacted-pincode]", scrubbed)
    return scrubbed


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


# Keys excluded from the pipeline_result blob (large/low-value or stored elsewhere)
_PIPELINE_RESULT_EXCLUDE = frozenset({"rewrites", "sim", "validation", "_inputs"})


def _build_pipeline_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a slim copy of the pipeline result for the pipeline_result JSONB column."""
    return {k: v for k, v in result.items() if k not in _PIPELINE_RESULT_EXCLUDE}


def _insert_resume_upload(
    db,
    *,
    user_id: str,
    file_name: str,
    file_size: int,
    jd_text: str,
    target_company: Optional[str],
    target_role: Optional[str],
    result: Dict[str, Any],
) -> str:
    """Insert resume_uploads row using live Supabase column names."""
    inputs = result.get("_inputs") or {}
    row: Dict[str, Any] = {
        "user_id": user_id,
        "file_name": file_name,
        "jd_text": inputs.get("jd_text", "")[:20000] or (jd_text or None),
        "target_company": (inputs.get("target_company", "") or target_company or "")[:500],
        "target_role": target_role,
        "has_jd": bool(jd_text and jd_text.strip()),
        "resume_text": _strip_pii(inputs.get("resume_text", ""))[:50000],
        "jd_source": (inputs.get("jd_source", "") or "pasted")[:50],
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
        result=result,
    )

    denormalized = _extract_denormalized_fields(result)

    analysis_row = {
        "upload_id": upload_id,
        "user_id": user_id,
        "full_result": result,
        **denormalized,
    }

    agent_outputs = {
        "a1_output": result.get("resume"),
        "a2_output": result.get("jd_intelligence"),
        "a3_output": result.get("gap"),
    }

    pipeline_result = {"pipeline_result": _build_pipeline_result(result)}

    try:
        insert_2 = db.table("analysis_results").insert(
            {**analysis_row, **agent_outputs, **pipeline_result}
        ).execute()
    except Exception as exc:
        logger.warning(
            "analysis_results insert with agent outputs + pipeline_result failed, "
            "retrying without pipeline_result: %s", exc,
        )
        try:
            insert_2 = db.table("analysis_results").insert(
                {**analysis_row, **agent_outputs}
            ).execute()
        except Exception as exc2:
            logger.warning(
                "analysis_results insert with agent outputs failed, retrying "
                "without a1/a2/a3 columns: %s", exc2,
            )
            insert_2 = db.table("analysis_results").insert(analysis_row).execute()

    if not insert_2.data:
        raise ValueError("analysis_results insert failed")

    try:
        db.rpc("increment_upload_count", {"p_user_id": user_id}).execute()
    except Exception as exc:
        logger.warning("increment_upload_count RPC failed: %s", exc)

    # Company Readiness persistence — non-fatal
    _insert_company_readiness(user_id, result.get("run_id") or upload_id, result)

    logger.info(
        "Analysis saved: user=%s upload_id=%s ats=%s",
        user_id,
        upload_id,
        denormalized.get("ats_score"),
    )
    return upload_id


def _insert_company_readiness(user_id: str, run_id: str, result: Dict[str, Any]) -> None:
    """
    Write one row to company_readiness_results if company readiness was computed for
    this run. No-op when final_result["company_readiness"] is None or missing.
    Failures are caught and logged — never raised to caller.
    """
    cr = result.get("company_readiness")
    if not cr:
        return
    try:
        db = get_db()
        db.table("company_readiness_results").insert({
            "run_id":                  run_id,
            "user_id":                 user_id,
            "company_key":             cr.get("company_key", ""),
            "company_display":         cr.get("company_display_name"),
            "readiness_score":         cr.get("readiness_score", 0),
            "readiness_label":         cr.get("readiness_label"),
            "dimensions_passing":      cr.get("dimensions_passing"),
            "dimensions_total":        cr.get("dimensions_total"),
            "dimensions_json":         cr.get("dimensions"),
            "target_ctc_min":          cr.get("target_ctc_min"),
            "target_ctc_max":          cr.get("target_ctc_max"),
            "ctc_delta_min":           cr.get("ctc_delta_min"),
            "ats_component":           cr.get("ats_component"),
            "jd_component":            cr.get("jd_component"),
            "seniority_component":     cr.get("seniority_component"),
            "company_signal_component": cr.get("company_signal_component"),
            "ctc_delta_max":           cr.get("ctc_delta_max"),
        }).execute()
    except Exception as e:
        logger.warning("Failed to write company_readiness_results for run %s: %s", run_id, e)
