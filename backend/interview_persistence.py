"""Supabase persistence for mock interview sessions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from backend.db import get_db

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_interview_session(
    *,
    session_id: str,
    user_id: str,
    company: str,
    seniority: str,
    question_mode: str,
    questions: list[dict],
) -> None:
    """Create a new in-progress interview session row."""
    try:
        db = get_db()
        db.table("interview_sessions").insert(
            {
                "session_id": session_id,
                "user_id": user_id,
                "company": company,
                "seniority": seniority,
                "question_mode": question_mode,
                "questions": questions,
                "answers": [],
                "feedback": [],
                "summary": None,
                "model_answers": None,
                "created_at": _utc_now_iso(),
                "completed_at": None,
            }
        ).execute()
    except Exception as exc:
        logger.warning("insert_interview_session failed: %s", exc)


def sync_interview_session_progress(
    session_id: str,
    *,
    answers: list[dict],
    feedback: list[dict],
) -> None:
    """Replace answers and feedback arrays after each evaluated turn."""
    try:
        db = get_db()
        db.table("interview_sessions").update(
            {"answers": answers, "feedback": feedback}
        ).eq("session_id", session_id).execute()
    except Exception as exc:
        logger.warning("sync_interview_session_progress failed: %s", exc)


def complete_interview_session(session_id: str, summary: dict) -> None:
    """Persist session summary and completion timestamp."""
    try:
        db = get_db()
        db.table("interview_sessions").update(
            {
                "summary": summary,
                "completed_at": _utc_now_iso(),
            }
        ).eq("session_id", session_id).execute()
    except Exception as exc:
        logger.warning("complete_interview_session failed: %s", exc)


def get_interview_session_row(session_id: str) -> dict[str, Any] | None:
    """Load a session row by id. Returns None on miss or DB error."""
    try:
        db = get_db()
        result = (
            db.table("interview_sessions")
            .select("*")
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("get_interview_session_row failed: %s", exc)
        return None


def cache_model_answer(
    session_id: str,
    question_id: str,
    model_answer: dict,
) -> None:
    """Merge one model answer into the session's model_answers jsonb dict."""
    try:
        db = get_db()
        row = get_interview_session_row(session_id)
        existing = (row or {}).get("model_answers") or {}
        if not isinstance(existing, dict):
            existing = {}
        updated = {**existing, question_id: model_answer}
        db.table("interview_sessions").update(
            {"model_answers": updated}
        ).eq("session_id", session_id).execute()
    except Exception as exc:
        logger.warning("cache_model_answer failed: %s", exc)


def list_completed_interview_sessions(
    user_id: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent completed sessions for a user (summary not null)."""
    try:
        db = get_db()
        result = (
            db.table("interview_sessions")
            .select("session_id, company, seniority, created_at, summary")
            .eq("user_id", user_id)
            .not_.is_("summary", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("list_completed_interview_sessions failed: %s", exc)
        return []
