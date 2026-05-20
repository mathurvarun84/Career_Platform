"""Prepare A1 structured resume for surgical-fix DOCX export (patched plain text)."""

from __future__ import annotations

import logging
from typing import Any

from backend.agents.rewriter import COMPANY_HEADER_START, _ensure_experience_markers
from parser import _extract_section_blocks
from validator.experience_audit import detect_ground_truth_entries, repair_experience_for_export


def _marked_experience_from_patched(
    patched_text: str,
    resume_sections: dict[str, Any],
) -> str:
    """Build marker-wrapped experience body from patched resume text."""
    blocks = _extract_section_blocks(patched_text)
    exp_block = (blocks.get("experience") or "").strip()
    if not exp_block:
        return ""

    if COMPANY_HEADER_START in exp_block:
        return exp_block

    ground = detect_ground_truth_entries(patched_text)
    if ground:
        return "\n\n".join(
            _ensure_experience_markers(b["text"], b["label"])
            for b in ground
            if b.get("text")
        )

    exp_sec = resume_sections.get("experience") or {}
    subs = exp_sec.get("sub_entries") if isinstance(exp_sec, dict) else []
    if subs:
        parts = []
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            verbatim = (sub.get("verbatim_text") or "").strip()
            label = (sub.get("label") or "").strip()
            if verbatim:
                parts.append(_ensure_experience_markers(verbatim, label))
        if parts:
            return "\n\n".join(parts)

    logging.warning(
        "surgical_export: could not marker-wrap experience; using flat patched block"
    )
    return exp_block


def prepare_surgical_export(
    structured: dict[str, Any],
    resume_sections: dict[str, Any] | None,
    patched_text: str,
) -> dict[str, Any]:
    """
    Merge patched plain text into A1 resume structure for DOCX build.

    Keeps A1 sub_entries and only updates section full_text from patches.
    Experience is re-wrapped with ##COMPANY## markers so labels are not distorted.
    """
    out = dict(structured or {})
    base_sections = dict(resume_sections or out.get("resume_sections") or {})
    sections, _, _ = repair_experience_for_export(
        patched_text,
        base_sections,
        {},
    )

    blocks = _extract_section_blocks(patched_text)
    for sec_key, block_text in blocks.items():
        if not block_text or not str(block_text).strip():
            continue
        if sec_key == "experience":
            block_text = _marked_experience_from_patched(patched_text, sections)

        existing = sections.get(sec_key)
        if isinstance(existing, dict):
            sections[sec_key] = {**existing, "full_text": block_text}
        else:
            sections[sec_key] = {"header": sec_key, "full_text": block_text}

    out["resume_sections"] = sections
    return out
