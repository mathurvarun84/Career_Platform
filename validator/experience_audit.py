"""
Experience section audit — counts entries at each pipeline stage and backfills from raw text.

Ground truth for entry count comes from deterministic date-range detection on the
parsed resume text (validator/resume_understanding_validator._detect_sub_entries).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.schemas.common import SectionText, SubEntry

try:
    from backend.agents.rewriter import COMPANY_HEADER_START, _ensure_experience_markers
except ImportError:
    COMPANY_HEADER_START = "##COMPANY##"

    def _ensure_experience_markers(text: str, sub_label: str) -> str:  # type: ignore
        return text

try:
    from validator.resume_understanding_validator import (
        _detect_sub_entries,
        _extract_all_sections_from_text,
        _labels_overlap,
    )
except ImportError:
    _detect_sub_entries = None  # type: ignore
    _extract_all_sections_from_text = None  # type: ignore
    _labels_overlap = None  # type: ignore

_EXPERIENCE_MARKER_RE = re.compile(
    r"##COMPANY##.*?##END_HEADER##",
    re.DOTALL,
)


def count_experience_markers(text: str) -> int:
    """Count ##COMPANY##…##END_HEADER## blocks in rewrite output."""
    if not text:
        return 0
    return len(_EXPERIENCE_MARKER_RE.findall(text))


def detect_ground_truth_entries(resume_text: str) -> list[dict[str, str]]:
    """
    Deterministic experience blocks from raw resume text.

    Returns:
        List of {label, text} dicts in resume order.
    """
    if not resume_text.strip() or _detect_sub_entries is None:
        return []

    raw_exp = ""
    if _extract_all_sections_from_text is not None:
        sections = _extract_all_sections_from_text(resume_text)
        raw_exp = sections.get("experience", "") or ""

    if not raw_exp.strip():
        raw_exp = resume_text

    return _detect_sub_entries(raw_exp, "experience")


def count_sub_entries(section: SectionText | dict[str, Any] | None) -> int:
    """Count experience sub_entries on a SectionText or dict."""
    if section is None:
        return 0
    if isinstance(section, dict):
        subs = section.get("sub_entries") or []
    else:
        subs = section.sub_entries or []
    return len(subs)


def _coerce_section_text(section: SectionText | dict[str, Any] | None) -> SectionText | None:
    if section is None:
        return None
    if isinstance(section, SectionText):
        return section
    if isinstance(section, dict):
        try:
            return SectionText(**section)
        except Exception:
            return None
    return None


def ensure_experience_completeness(
    section_text: SectionText | dict[str, Any] | None,
    resume_text: str,
) -> SectionText | None:
    """
    Backfill missing experience sub_entries from ground-truth detection.

    Mutates nothing if section already has >= ground-truth count.
    """
    st = _coerce_section_text(section_text)
    if st is None and not resume_text.strip():
        return st

    ground = detect_ground_truth_entries(resume_text)
    if not ground:
        return st

    if st is None:
        entries = [
            SubEntry(label=b["label"], verbatim_text=b["text"])
            for b in ground
            if b.get("label") and b.get("text")
        ]
        if not entries:
            return None
        return SectionText(
            header="experience",
            full_text="\n\n".join(e.verbatim_text for e in entries),
            sub_entries=entries,
        )

    existing = list(st.sub_entries or [])
    existing_labels = [e.label for e in existing]
    added = 0

    for block in ground:
        label = str(block.get("label", "") or "")
        text = str(block.get("text", "") or "")
        if not label or not text:
            continue
        if _labels_overlap is not None and any(
            _labels_overlap(label, lbl) for lbl in existing_labels
        ):
            continue
        existing.append(SubEntry(label=label, verbatim_text=text))
        existing_labels.append(label)
        added += 1

    if not added:
        return st

    merged_full = "\n\n".join(
        e.verbatim_text for e in existing if e.verbatim_text.strip()
    ) or st.full_text

    logging.warning(
        "ExperienceAudit: backfilled %d missing entries (now %d, ground truth %d)",
        added,
        len(existing),
        len(ground),
    )

    return SectionText(
        header=st.header or "experience",
        full_text=merged_full,
        sub_entries=existing,
    )


def rebuild_experience_rewrites(
    variants: dict[str, str],
    section_text: SectionText,
    *,
    prefer_rewritten: bool = True,
) -> dict[str, str]:
    """
    Rebuild all three style variants from sub_entries when marker count is low.

    When prefer_rewritten=True, keeps existing variant text for entries whose
    company label fuzzy-matches a block already present in the rewrite.
    """
    expected = len(section_text.sub_entries)
    if expected == 0:
        return variants

    repaired: dict[str, str] = {}
    for style in ("balanced", "aggressive", "top_1_percent"):
        existing = variants.get(style, "") or ""
        if prefer_rewritten and count_experience_markers(existing) >= expected:
            repaired[style] = existing
            continue

        parts: list[str] = []
        for entry in section_text.sub_entries:
            block = _ensure_experience_markers(entry.verbatim_text, entry.label)
            if prefer_rewritten and existing and _labels_overlap is not None:
                # Try to pull rewritten block for this entry from existing output
                for chunk in re.split(r"\n\s*\n+", existing):
                    if _labels_overlap(entry.label, chunk[:120]):
                        block = chunk.strip()
                        if not block.startswith(COMPANY_HEADER_START):
                            block = _ensure_experience_markers(block, entry.label)
                        break
            parts.append(block)
        repaired[style] = "\n\n".join(parts)

    return repaired


def log_experience_audit(
    stage: str,
    resume_text: str,
    resume_sections: dict[str, Any] | None = None,
    rewrites: dict[str, Any] | None = None,
    style: str = "balanced",
) -> dict[str, Any]:
    """
    Log experience entry counts at a pipeline stage. Returns summary dict for tests.
    """
    ground = detect_ground_truth_entries(resume_text)
    ground_n = len(ground)
    ground_labels = [b.get("label", "")[:60] for b in ground]

    section = None
    if resume_sections:
        section = resume_sections.get("experience")
        if section is None:
            for key, val in resume_sections.items():
                if str(key).lower().strip() in (
                    "experience",
                    "work experience",
                    "professional experience",
                    "employment",
                ):
                    section = val
                    break

    sub_n = count_sub_entries(section)

    rewrite_n = 0
    if rewrites:
        exp_rw = rewrites.get("experience") or {}
        if isinstance(exp_rw, dict):
            text = exp_rw.get(style) or exp_rw.get("balanced") or ""
            rewrite_n = count_experience_markers(str(text))

    summary = {
        "stage": stage,
        "ground_truth_count": ground_n,
        "ground_truth_labels": ground_labels,
        "sub_entries_count": sub_n,
        "rewrite_marker_count": rewrite_n,
        "delta_vs_ground": sub_n - ground_n,
        "rewrite_delta_vs_ground": rewrite_n - ground_n,
    }

    level = logging.INFO
    if ground_n > 0 and (sub_n < ground_n or rewrite_n < ground_n):
        level = logging.WARNING

    logging.log(
        level,
        "ExperienceAudit [%s]: ground_truth=%d sub_entries=%d rewrite_markers=%d | "
        "labels=%s",
        stage,
        ground_n,
        sub_n,
        rewrite_n,
        ground_labels[:10],
    )

    if ground_n > sub_n:
        logging.warning(
            "ExperienceAudit [%s]: MISSING %d experience entries in resume_sections "
            "(have %d, need %d)",
            stage,
            ground_n - sub_n,
            sub_n,
            ground_n,
        )
    if ground_n > rewrite_n and rewrite_n > 0:
        logging.warning(
            "ExperienceAudit [%s]: rewrite output missing %d experience blocks "
            "(markers %d vs ground %d)",
            stage,
            ground_n - rewrite_n,
            rewrite_n,
            ground_n,
        )

    return summary
