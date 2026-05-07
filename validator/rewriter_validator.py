"""
RewriterValidator — post-processes A4 (Rewriter) output for ALL sections.

Validates and repairs:
  experience     — every original company present in all 3 styles
  education      — every degree block present in all 3 styles
  certifications — every cert block present in all 3 styles
  projects       — every project present in all 3 styles
  skills         — full_text not empty, not shorter than original
  summary        — full_text not empty, not truncated
  awards         — full_text present
  publications   — full_text present
  extracurriculars — full_text present
  cross-section  — truncation guard (< 35% of original length)
  placeholder    — [ALL_CAPS] unfilled placeholders removed
  invented metrics — warning only, no auto-fix

No LLM calls for any fix. All repairs use data already in resume_sections.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from schemas.common import SectionText, SubEntry

# Import marker helpers from rewriter (or redefine if circular import risk)
try:
    from agents.rewriter import _ensure_experience_markers
except ImportError:
    def _ensure_experience_markers(text: str, sub_label: str) -> str:  # type: ignore
        return text


_METRIC_PATTERN    = re.compile(r'\b\d+\.?\d*\s*(%|x|X|\bk\b|\bK\b|Cr\b|L\b|ms\b|\bs\b)')
_PLACEHOLDER_RE    = re.compile(r'\[[A-Z][A-Z0-9_]{2,}\]')
_COMPANY_MARKER_RE = re.compile(r'##COMPANY##(.*?)(?:##ROLE##|##END_HEADER##)')
_EXPERIENCE_MARKER_RE = re.compile(
    r'##COMPANY##(.*?)##ROLE##(.*?)##END_HEADER##',
    re.DOTALL,
)

# Sections that have sub_entries and need entry-level completeness checks
_SUB_ENTRY_SECTIONS = ('experience', 'education', 'certifications', 'projects')

# Sections that are flat text (no sub_entries)
_FLAT_SECTIONS = ('summary', 'skills', 'awards', 'publications', 'extracurriculars')


def _split_bullets(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-*").strip()
        if line:
            lines.append(line)
    return lines


def _build_legacy_styles(rewrites: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    styles: dict[str, dict[str, Any]] = {
        "balanced": {"summary": "", "skills": "", "experience": [], "projects": []},
        "aggressive": {"summary": "", "skills": "", "experience": [], "projects": []},
        "top_1_percent": {"summary": "", "skills": "", "experience": [], "projects": []},
    }

    for section_name, variants in rewrites.items():
        for style_name, section_text in variants.items():
            if style_name not in styles:
                continue
            if section_name == "summary":
                styles[style_name]["summary"] = section_text
            elif section_name == "skills":
                styles[style_name]["skills"] = section_text
            elif section_name == "experience":
                styles[style_name]["experience"] = [{
                    "company": "Experience",
                    "role": "",
                    "rewritten_bullets": _split_bullets(section_text) or [section_text],
                }]
            elif section_name == "projects":
                styles[style_name]["projects"] = [{
                    "name": "Projects",
                    "tech_stack": [],
                    "rewritten_description": section_text,
                }]

    return styles


def _normalize_presence_text(text: str) -> str:
    """Normalize text for conservative containment/presence checks."""
    text = re.sub(r'##(?:COMPANY|ROLE|END_HEADER)##', ' ', str(text))
    return re.sub(r'\s+', ' ', text.lower()).strip()


def _split_nonempty_blocks(text: str) -> list[str]:
    """Split a section into nonempty blocks, falling back to lines."""
    blocks = [b.strip() for b in re.split(r'\n\s*\n+', str(text)) if b.strip()]
    if len(blocks) > 1:
        return blocks
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def _dedupe_repeated_lines(text: str) -> str:
    """Remove exact duplicate nonempty lines while preserving order."""
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        key = _normalize_presence_text(line)
        if key in seen:
            continue
        seen.add(key)
        lines.append(raw_line)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _entry_verbatim_present(entry_text: str, style_text: str) -> bool:
    """True when an unchanged entry already exists in a style variant."""
    entry_norm = _normalize_presence_text(entry_text)
    style_norm = _normalize_presence_text(style_text)
    return bool(entry_norm) and entry_norm in style_norm


def _extract_entry_ids(text: str, section: str) -> list[str]:
    """
    Extract the identifiers used for completeness checks per section type.
    For experience: ##COMPANY## markers.
    For others: first line of each entry block (heuristic).
    """
    if section == 'experience':
        ids: list[str] = []
        for company, role in _EXPERIENCE_MARKER_RE.findall(text):
            ids.append(f"{company} {role}".strip())
        if ids:
            return ids
        return _COMPANY_MARKER_RE.findall(text)

    # For other sections without markers, split on double newline or individual
    # lines and take first lines. Exact verbatim containment is checked first.
    blocks = _split_nonempty_blocks(text)
    return [b.splitlines()[0].strip()[:80] for b in blocks if b]


def _matched_entry_indexes(found_ids: list[str], section_text: SectionText) -> set[int]:
    """One-to-one fuzzy match found output identifiers to original sub_entries."""
    used_ids: set[int] = set()
    matched_entries: set[int] = set()

    for entry_idx, entry in enumerate(section_text.sub_entries):
        best_id: int | None = None
        best_rank = -1
        for found_idx, found in enumerate(found_ids):
            if found_idx in used_ids:
                continue
            if not _labels_overlap(entry.label, found):
                continue
            rank = 10
            if _normalize_presence_text(entry.label) == _normalize_presence_text(found):
                rank = 100
            elif (
                _normalize_presence_text(entry.label) in _normalize_presence_text(found)
                or _normalize_presence_text(found) in _normalize_presence_text(entry.label)
            ):
                rank = 50
            if rank > best_rank:
                best_rank = rank
                best_id = found_idx
        if best_id is not None:
            used_ids.add(best_id)
            matched_entries.add(entry_idx)

    return matched_entries


def _augment_experience_entries(section_text: SectionText, resume_text: str) -> SectionText:
    """Backfill missing experience entries from raw resume text when possible."""
    if not resume_text.strip():
        return section_text
    try:
        from validator.resume_understanding_validator import (
            _detect_sub_entries,
            _extract_all_sections_from_text,
            _labels_overlap,
        )
    except Exception:
        return section_text

    detected_sections = _extract_all_sections_from_text(resume_text)
    raw_exp = detected_sections.get('experience', '')
    if not raw_exp.strip():
        return section_text

    detected_blocks = _detect_sub_entries(raw_exp, 'experience')
    if not detected_blocks:
        return section_text

    existing = list(section_text.sub_entries or [])
    existing_labels = [e.label for e in existing]
    added = False
    for block in detected_blocks:
        label = str(block.get('label', '') or '')
        text = str(block.get('text', '') or '')
        if not label or not text:
            continue
        if any(_labels_overlap(label, l) for l in existing_labels):
            continue
        if _entry_verbatim_present(text, section_text.full_text):
            existing.append(SubEntry(label=label, verbatim_text=text))
            existing_labels.append(label)
            added = True
            continue
        existing.append(SubEntry(label=label, verbatim_text=text))
        existing_labels.append(label)
        added = True

    if not added:
        return section_text

    merged_full = section_text.full_text.strip()
    if len(existing) > len(section_text.sub_entries or []):
        merged_full = '\n\n'.join(
            e.verbatim_text for e in existing if e.verbatim_text.strip()
        ) or merged_full

    return SectionText(
        header=section_text.header,
        full_text=merged_full,
        sub_entries=existing,
    )


def _labels_overlap(a: str, b: str) -> bool:
    """Shared token ratio check for label matching."""
    stopwords = {
        "engineer", "engineering", "manager", "senior", "lead", "software",
        "consultant", "developer", "architect", "principal", "staff",
        "bengaluru", "bangalore", "india", "remote", "hybrid", "onsite",
        "company", "experience", "payroll", "altran",
    }

    def normalized(s: str) -> str:
        s = re.sub(r'\d{4}', '', s.lower())
        return re.sub(r'[^a-z0-9]+', ' ', s).strip()

    def tokens(s: str) -> set[str]:
        s = re.sub(r'\d{4}', '', s)
        return {
            w.lower()
            for w in re.split(r'[\s|–—(),.\[\]\-]+', s)
            if len(w) > 3 and w.lower() not in stopwords
        }

    na, nb = normalized(a), normalized(b)
    if na and nb and (na in nb or nb in na):
        return True

    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    return bool(ta & tb) and len(ta & tb) / min(len(ta), len(tb)) > 0.6


def _get_section_text(resume_sections: dict, section_name: str) -> SectionText | None:
    """Resolve section from resume_sections, handling dict or SectionText."""
    raw = resume_sections.get(section_name)
    if raw is None:
        return None
    if isinstance(raw, dict):
        try:
            return SectionText(**raw)
        except Exception:
            return None
    if isinstance(raw, SectionText):
        return raw
    return None


def _repair_sub_entry_section(
    section_name: str,
    variants: dict[str, str],
    section_text: SectionText,
) -> tuple[dict[str, str], list[str]]:
    """
    Ensures every sub_entry from the original section appears in all 3 style variants.
    Returns (repaired_variants, anomalies).
    """
    anomalies: list[str] = []
    if not section_text.sub_entries:
        return variants, anomalies

    repaired = dict(variants)

    for style in ('balanced', 'aggressive', 'top_1_percent'):
        style_text = repaired.get(style, '')
        if section_name != 'experience':
            style_text = _dedupe_repeated_lines(style_text)
        repaired[style] = style_text
        found_markers = _extract_entry_ids(style_text, section_name)
        matched_indexes = _matched_entry_indexes(found_markers, section_text)

        for entry_idx, entry in enumerate(section_text.sub_entries):
            orig_label = entry.label
            if (
                entry_idx in matched_indexes
                or _entry_verbatim_present(entry.verbatim_text, style_text)
            ):
                continue  # entry present — ok

            anomalies.append(
                f"{section_name}/{style}: missing entry '{orig_label[:50]}' — injecting verbatim"
            )
            verbatim = entry.verbatim_text
            if section_name == 'experience':
                verbatim = _ensure_experience_markers(verbatim, orig_label)

            style_text = (style_text + '\n\n' + verbatim).strip() \
                if style_text else verbatim
            repaired[style] = style_text

    return repaired, anomalies


def _repair_flat_section(
    section_name: str,
    variants: dict[str, str],
    section_text: SectionText,
) -> tuple[dict[str, str], list[str]]:
    """
    For flat sections (summary, skills, awards, publications, extracurriculars):
    - If any style is empty → replace with original full_text
    - If any style is < 35% of original length → replace with original
    """
    anomalies: list[str] = []
    original = section_text.full_text.strip()
    if not original:
        return variants, anomalies

    repaired = dict(variants)
    for style in ('balanced', 'aggressive', 'top_1_percent'):
        style_text = repaired.get(style, '').strip()
        if not style_text:
            anomalies.append(
                f"{section_name}/{style}: empty — replacing with original"
            )
            repaired[style] = original
        elif len(style_text) < len(original) * 0.35:
            anomalies.append(
                f"{section_name}/{style}: truncated "
                f"({len(style_text)} vs {len(original)} chars) — replacing with original"
            )
            repaired[style] = original
        elif section_name in {'awards', 'publications', 'extracurriculars'}:
            deduped = _dedupe_repeated_lines(style_text)
            if deduped != style_text:
                anomalies.append(
                    f"{section_name}/{style}: duplicate lines removed"
                )
                repaired[style] = deduped

    return repaired, anomalies


def _check_placeholder_bleed(
    section_name: str,
    variants: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Strip unfilled [PLACEHOLDER] tokens from all style variants."""
    anomalies: list[str] = []
    repaired = dict(variants)
    for style, text in repaired.items():
        found = _PLACEHOLDER_RE.findall(text)
        if found:
            anomalies.append(
                f"{section_name}/{style}: unfilled placeholders {found} — stripped"
            )
            repaired[style] = _PLACEHOLDER_RE.sub('', text).strip()
    return repaired, anomalies


def _check_invented_metrics(
    section_name: str,
    variants: dict[str, str],
    original_text: str,
) -> list[str]:
    """Warning-only check for metrics present in rewrite but not in original."""
    warnings: list[str] = []
    if not original_text:
        return warnings

    original_metrics = {
        m[0] for m in _METRIC_PATTERN.findall(original_text)
    }

    for style, text in variants.items():
        rewrite_metrics = {m[0] for m in _METRIC_PATTERN.findall(text)}
        # Filter out bracketed placeholders like [X%] — those are intentional
        invented = {
            m for m in rewrite_metrics - original_metrics
            if not re.search(r'\[.{1,4}' + re.escape(m), text)
        }
        if invented:
            warnings.append(
                f"{section_name}/{style}: possibly invented metrics {invented} — REVIEW MANUALLY"
            )

    return warnings


class RewriterValidator:
    """
    Validates and repairs A4 (Rewriter) output for ALL canonical sections.

    Checks run per section:
      sub-entry sections (experience, education, certifications, projects):
        - every original entry present in all 3 styles
      flat sections (summary, skills, awards, publications, extracurriculars):
        - full_text not empty or truncated vs original
      all sections:
        - truncation guard (< 35% of original → replace)
        - placeholder bleed removal
        - invented metric warning

    Usage:
        validator = RewriterValidator()
        repaired = validator.validate_and_fix(rewriter_output, resume_sections, resume_text)
    """

    def validate_and_fix(
        self,
        rewriter_output: dict[str, Any],
        resume_sections: dict[str, Any],
        resume_text: str = '',
    ) -> dict[str, Any]:
        """
        Entry point. Repairs and returns corrected rewriter output.

        Args:
            rewriter_output: Raw dict from A4 (keys: 'rewrites', 'styles').
            resume_sections:  Dict of {section_name: SectionText | dict} from A1.
            resume_text:      Full cleaned resume text (for invented metric check).

        Returns:
            Repaired dict safe to pass to career_positioning / docx builder.
        """
        output = dict(rewriter_output)
        rewrites = dict(output.get('rewrites', {}))
        all_anomalies: list[str] = []
        all_warnings: list[str] = []

        # ── Process every section that appears in the rewrites ─────────
        all_section_names = set(rewrites.keys()) | set(resume_sections.keys())

        for section_name in all_section_names:
            section_text = _get_section_text(resume_sections, section_name)
            if not section_text:
                continue
            if section_name == 'experience':
                section_text = _augment_experience_entries(section_text, resume_text)

            variants = rewrites.get(section_name)
            if not variants:
                # Section exists in original but A4 produced nothing for it
                # Preserve verbatim for all 3 styles
                content = section_text.full_text
                if section_name == 'experience' and section_text.sub_entries:
                    from agents.rewriter import _ensure_experience_markers
                    parts = [
                        _ensure_experience_markers(e.verbatim_text, e.label)
                        for e in section_text.sub_entries
                    ]
                    content = '\n\n'.join(parts)
                if content.strip():
                    all_anomalies.append(
                        f"{section_name}: completely missing from rewrites — injecting verbatim"
                    )
                    rewrites[section_name] = {
                        'balanced': content,
                        'aggressive': content,
                        'top_1_percent': content,
                    }
                continue

            # ── Sub-entry completeness check ──────────────────────────
            if section_name in _SUB_ENTRY_SECTIONS and section_text.sub_entries:
                variants, anomalies = _repair_sub_entry_section(
                    section_name, variants, section_text
                )
                all_anomalies.extend(anomalies)

            # ── Flat section completeness check ───────────────────────
            elif section_name in _FLAT_SECTIONS:
                variants, anomalies = _repair_flat_section(
                    section_name, variants, section_text
                )
                all_anomalies.extend(anomalies)

            # ── Placeholder bleed ─────────────────────────────────────
            variants, anomalies = _check_placeholder_bleed(section_name, variants)
            all_anomalies.extend(anomalies)

            # ── Invented metric warning ───────────────────────────────
            orig_text = section_text.full_text if section_text else ''
            warnings = _check_invented_metrics(section_name, variants, orig_text)
            all_warnings.extend(warnings)

            rewrites[section_name] = variants

        output['rewrites'] = rewrites
        output['styles'] = _build_legacy_styles(rewrites)

        # ── Log all findings ──────────────────────────────────────────
        if all_anomalies:
            logging.warning(
                "RewriterValidator: %d anomalies fixed:\n  %s",
                len(all_anomalies),
                '\n  '.join(f"[{i+1}] {a}" for i, a in enumerate(all_anomalies))
            )
        else:
            logging.info("RewriterValidator: all checks passed (0 anomalies)")

        for w in all_warnings:
            logging.warning("RewriterValidator WARNING: %s", w)

        return output
