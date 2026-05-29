"""Strip personally identifiable information from resume text before corpus storage."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)
PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
ADDRESS_RE = re.compile(
    r"\d+\s[\w\s]+(?:road|street|avenue|lane|blvd|st|ave|rd|ln|dr|way|close|nagar|layout)\b",
    re.I,
)
LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+",
    re.I,
)
GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+",
    re.I,
)
URL_RE = re.compile(r"https?://\S+", re.I)


def _looks_like_name(line: str) -> bool:
    """Heuristic: first resume line is often a title-cased name without contact markers."""
    words = line.strip().split()
    return (
        2 <= len(words) <= 4
        and all(w[0].isupper() for w in words if w)
        and not any(char in line for char in ("@", ".com", "|", "-"))
    )


def strip_pii(text: str) -> str:
    """Remove common PII fields from resume text. Safe to call on empty input."""
    if not text:
        return text

    cleaned = EMAIL_RE.sub("[email removed]", text)
    cleaned = PHONE_RE.sub("[phone removed]", cleaned)
    cleaned = ADDRESS_RE.sub("[address removed]", cleaned)
    cleaned = LINKEDIN_RE.sub("[linkedin removed]", cleaned)
    cleaned = GITHUB_RE.sub("[github removed]", cleaned)
    cleaned = URL_RE.sub("[url removed]", cleaned)

    lines = cleaned.splitlines()
    if lines and _looks_like_name(lines[0]):
        lines[0] = "[name removed]"
    return "\n".join(lines)
