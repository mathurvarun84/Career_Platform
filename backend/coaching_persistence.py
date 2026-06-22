"""Supabase persistence for career memory (coaching sessions)."""

from __future__ import annotations

import logging
from typing import Any

from backend.db import get_db
from backend.schemas.career_memory import CareerMemoryEntry

logger = logging.getLogger(__name__)


def save_coaching_entry(entry: CareerMemoryEntry) -> None:
    """Insert one coaching entry into coaching_sessions. Non-fatal on failure."""
    try:
        db = get_db()
        db.table("coaching_sessions").insert({
            "id":                entry.id,
            "session_id":        entry.session_id,
            "timestamp":         entry.timestamp,
            "skill_category":    entry.skill_category,
            "gap_reason":        entry.gap_reason,
            "company":           entry.company,
            "role":              entry.role,
            "section":           entry.section,
            "coaching_question": entry.coaching_question,
            "raw_answer":        entry.raw_answer,
            "generated_bullet":  entry.generated_bullet,
            "grounding_check":   entry.grounding_check,
            "user_approved":     entry.user_approved,
            "gap_id":            entry.gap_id or None,
            "sub_label":         entry.sub_label,
        }).execute()
    except Exception as exc:
        logger.warning("save_coaching_entry failed for %s: %s", entry.id, exc)


def approve_coaching_entry(entry_id: str) -> None:
    """Flip user_approved=true for an existing coaching_sessions row."""
    try:
        db = get_db()
        db.table("coaching_sessions").update(
            {"user_approved": True}
        ).eq("id", entry_id).execute()
    except Exception as exc:
        logger.warning("approve_coaching_entry failed for %s: %s", entry_id, exc)


def load_coaching_entries(session_id: str) -> list[dict[str, Any]]:
    """Fetch all coaching entries for a session from DB (fallback read path)."""
    try:
        db = get_db()
        result = (
            db.table("coaching_sessions")
            .select("*")
            .eq("session_id", session_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("load_coaching_entries failed for %s: %s", session_id, exc)
        return []
