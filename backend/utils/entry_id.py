"""
Stable entry_id derivation from resume sub_entry labels.

Used as the canonical key for experience/education entries across A1 → gap
analyzer → rewriter → frontend. Human-readable slug; deterministic from label.
"""

import re

_STOP_TOKENS = frozenset({
    "present", "jan", "feb", "mar", "apr", "may", "jun", "jul",
    "aug", "sep", "oct", "nov", "dec", "bengaluru", "bangalore",
    "mumbai", "delhi", "hyderabad", "pune", "austin", "texas",
    "ka", "mh", "tn", "dl", "ny", "ca",
})


def derive_entry_id(label: str) -> str:
    """
    Derive a stable snake_case entry_id from a human-readable sub_entry label.

    Handles A1 format ("Role | Company — Location Date") and LLM format
    ("Company — Role (date)"). Same label always yields the same id.

    Args:
        label: Human-readable sub_entry label from A1 or gap analyzer.

    Returns:
        Stable slug e.g. ``flipkart_engineering_manager_2020``.
    """
    lower = (label or "").lower().strip()
    if not lower:
        return "entry_unknown"

    year_match = re.search(r"\b(20\d{2})\b", lower)
    year = year_match.group(1) if year_match else ""

    normalized = re.sub(r"[—|–/]", " ", lower)
    tokens = [t for t in re.split(r"\W+", normalized) if len(t) > 2]
    sig_tokens = [
        t for t in tokens
        if t not in _STOP_TOKENS and not re.match(r"^\d{4}$", t)
    ]
    slug_tokens = sig_tokens[:3]
    base = "_".join(slug_tokens)

    if year and not base.endswith(year):
        base = f"{base}_{year}" if base else year

    return (base[:60] or "entry_unknown")
