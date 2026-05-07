"""
Style fingerprint extractor.

Analyzes a user's session history and produces a short plain‑English summary of
their rewrite preferences. The output is limited to <200 tokens (≈900 characters)
as required by the architecture.
"""

import logging

logger = logging.getLogger(__name__)

def _truncate(text: str, limit: int = 900) -> str:
    """Truncate *text* to *limit* characters without cutting in the middle of a word.

    The limit is chosen to keep the result under the 200‑token budget.
    """
    if len(text) <= limit:
        return text
    # Find last space before the limit
    cut = text.rfind(" ", 0, limit)
    return text[:cut] + "..."

def extract_fingerprint(session_data: dict) -> str:
    """Return a concise style fingerprint.

    The fingerprint is a single sentence of the form::

        "User tends to accept rewrites that <pattern>. User rejects <pattern>. Preferred tone: <tone>."

    *session_data* must follow the memory schema defined in CLAUDE.md.
    If fewer than three runs are recorded, an empty string is returned.
    The result is truncated to a maximum of 900 characters to stay under the
    200‑token budget.
    """
    try:
        runs = session_data.get("runs", [])
        if len(runs) < 3:
            return ""
        decisions = session_data.get("style_decisions", {})
        accepted = decisions.get("accepted", [])
        rejected = decisions.get("rejected", [])

        # Simple aggregation – join distinct items
        accept_str = ", ".join(sorted(set(accepted))) if accepted else "various patterns"
        reject_str = ", ".join(sorted(set(rejected))) if rejected else "various patterns"
        # Tone is not stored; default to "neutral"
        tone = "neutral"

        summary = (
            f"User tends to accept rewrites that {accept_str}. "
            f"User rejects {reject_str}. Preferred tone: {tone}."
        )
        return _truncate(summary)
    except Exception as e:
        logger.error("Failed to extract style fingerprint: %s", e)
        return ""
