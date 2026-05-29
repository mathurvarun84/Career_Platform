"""
Deterministic seniority inference from job titles in resume text.

Agent 1 (LLM) often labels 11+ year profiles as 'staff' because YoE rules
are listed before management-track rules. Title signals in the most recent
roles should override that when they are unambiguous.
"""

from __future__ import annotations

import re
from typing import Optional

# Order matters: check higher bands first.
_TITLE_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:associate\s+)?director\s+of\s+engineering\b|"
            r"\bvp\s*,?\s*engineering\b|"
            r"\bvice\s+president\s*,?\s*engineering\b|"
            r"\bhead\s+of\s+engineering\b|"
            r"\bsenior\s+director\s+of\s+engineering\b|"
            r"\bengineering\s+director\b",
            re.IGNORECASE,
        ),
        "director",
    ),
    (
        re.compile(
            r"\bsenior\s+engineering\s+manager\b|"
            r"\bgroup\s+engineering\s+manager\b|"
            r"\bsenior\s+em\b|"
            r"\bengineering\s+manager\s*,\s*engineering\b",
            re.IGNORECASE,
        ),
        "senior_em",
    ),
    (
        re.compile(
            r"\bengineering\s+manager\b|"
            r"\beng(?:ineering)?\s+manager\b|"
            r"\btech(?:nical)?\s+manager\b|"
            r"\bsoftware\s+development\s+manager\b|"
            r"\bsdm\b",
            re.IGNORECASE,
        ),
        "em",
    ),
    (
        re.compile(
            r"\bhead\s+of\s+engineering\b|"
            r"\bhead\s*,\s*engineering\b",
            re.IGNORECASE,
        ),
        "director",
    ),
]

_IC_STAFF_RULE = re.compile(
    r"\b(?:staff|principal|distinguished)\s+engineer\b",
    re.IGNORECASE,
)

_MGMT_RANK = {"em": 1, "senior_em": 2, "director": 3}


def _recent_experience_window(resume_text: str, max_chars: int = 5000) -> str:
    """
    Prefer the experience section and the top of the file (most recent roles).
    """
    text = resume_text or ""
    lower = text.lower()
    for marker in ("experience", "professional experience", "work experience"):
        idx = lower.find(marker)
        if idx >= 0:
            return text[idx : idx + max_chars]
    return text[:max_chars]


def infer_seniority_from_titles(resume_text: str) -> Optional[str]:
    """
    Infer management-track seniority from job titles when unambiguous.

    Returns:
        em | senior_em | director, or None if no clear management title.
    """
    window = _recent_experience_window(resume_text)
    best: Optional[str] = None
    best_rank = 0

    for pattern, level in _TITLE_RULES:
        if pattern.search(window):
            rank = _MGMT_RANK.get(level, 0)
            if rank > best_rank:
                best_rank = rank
                best = level

    return best


def reconcile_seniority(
    llm_seniority: str,
    resume_text: str,
    experience_years: int = 0,
) -> tuple[str, bool]:
    """
    Override LLM seniority when titles clearly indicate management track.

    Returns:
        (final_seniority, was_corrected)
    """
    _ = experience_years  # reserved for future YoE tie-breaks
    llm = (llm_seniority or "").lower().strip()
    from_titles = infer_seniority_from_titles(resume_text)

    if not from_titles:
        return llm or "mid", False

    ic_labels = {"junior", "mid", "senior", "staff"}
    mgmt_labels = {"em", "senior_em", "director"}

    if from_titles in mgmt_labels and llm in ic_labels:
        return from_titles, True

    # LLM said staff but titles show director — upgrade
    if (
        from_titles in mgmt_labels
        and llm in mgmt_labels
        and _MGMT_RANK.get(from_titles, 0) > _MGMT_RANK.get(llm, 0)
    ):
        return from_titles, True

    # Explicit IC staff/principal in recent window — keep staff unless EM also present
    if _IC_STAFF_RULE.search(_recent_experience_window(resume_text)) and not from_titles:
        return llm, False

    return llm, False
