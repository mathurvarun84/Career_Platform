"""
Tracks which dimensions + resume signals have been asked per user per resume.

Thin wrapper over ``memory.session_store`` — no new storage layer.
"""

from __future__ import annotations

from memory.session_store import (
    compute_resume_fingerprint,
    extract_signal_phrase,
    load_question_ledger,
    update_question_ledger,
)

ALL_DIMENSIONS = [
    "ownership",
    "impact_and_scale",
    "influence_without_authority",
    "problem_solving",
    "collaboration",
    "growth_mindset",
    "conflict_resolution",
]


def resume_fingerprint(resume_text: str) -> str:
    """Deterministic sha256 fingerprint for resume text (full hash)."""
    return compute_resume_fingerprint(resume_text)


def get_ledger(user_id: str, resume_fp: str) -> dict:
    """Return ledger entry for this user + resume fingerprint."""
    return load_question_ledger(user_id, resume_fp)


def get_available_dimensions(user_id: str, resume_fp: str) -> list[str]:
    """Dimensions not yet asked; resets to full set after a full cycle."""
    ledger = get_ledger(user_id, resume_fp)
    asked = {d.lower() for d in ledger.get("asked_dimensions", []) if d}
    available = [d for d in ALL_DIMENSIONS if d.lower() not in asked]
    return available if len(available) >= 3 else list(ALL_DIMENSIONS)


def get_excluded_dimensions(user_id: str, resume_fp: str) -> list[str]:
    """Dimensions to exclude this session (complement of available)."""
    available = set(get_available_dimensions(user_id, resume_fp))
    return [d for d in ALL_DIMENSIONS if d not in available]


def update_ledger(
    user_id: str,
    resume_fp: str,
    completed_questions: list[dict],
) -> None:
    """Persist dimensions/signals from a completed mock interview session."""
    update_question_ledger(user_id, resume_fp, completed_questions)


def extract_signal(why_this_question: str) -> str:
    """Public alias for signal phrase extraction."""
    return extract_signal_phrase(why_this_question)
