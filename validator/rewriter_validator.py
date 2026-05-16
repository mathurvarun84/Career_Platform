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

from backend.schemas.common import SectionText, SubEntry

from validator.experience_audit import (
    count_experience_markers,
    detect_ground_truth_entries,
    ensure_experience_completeness,
    log_experience_audit,
    rebuild_experience_rewrites,
)

from backend.agents.rewriter import (
    _ensure_experience_markers,
    _build_content_from_sub_entries,
    _canonicalize_key,
    _SUB_ENTRY_SECTIONS as _REWRITER_SUB_ENTRY_SECTIONS,
)


_METRIC_PATTERN    = re.compile(r'\b\d+\.?\d*\s*(%|x|X|\bk\b|\bK\b|Cr\b|L\b|ms\b|\bs\b)')
_PLACEHOLDER_RE    = re.compile(r'\[[A-Z][A-Z0-9_]{2,}\]')
_COMPANY_MARKER_RE = re.compile(r'##COMPANY##(.*?)(?:##ROLE##|##END_HEADER##)')
_EXPERIENCE_MARKER_RE = re.compile(
    r'##COMPANY##(.*?)##ROLE##(.*?)##END_HEADER##',
    re.DOTALL,
)

# Sections that have sub_entries and need entry-level completeness checks
_SUB_ENTRY_SECTIONS = tuple(_REWRITER_SUB_ENTRY_SECTIONS)

# Sections that are flat text (no sub_entries)
_FLAT_SECTIONS = ('summary', 'skills', 'awards', 'publications', 'extracurriculars')

_CANONICAL_ALIASES: dict[str, list[str]] = {
    "projects": [
        "projects & side work",
        "projects and side work",
        "side projects",
        "project work",
        "key projects",
        "project_experience",
        "personal_projects",
    ],
    "awards": [
        "awards & achievements",
        "awards and achievements",
        "honours",
        "honors",
        "accomplishments",
        "achievements",
    ],
    "experience": [
        "career history",
        "employment history",
        "work history",
        "professional experience",
        "work_experience",
        "professional_experience",
        "employment",
    ],
    "skills": [
        "technical skills",
        "core competencies",
        "key skills",
        "technical_skills",
        "core_competencies",
        "key_skills",
    ],
    "summary": [
        "professional summary",
        "objective",
        "profile",
        "professional_summary",
    ],
    "certifications": ["certificates", "credentials"],
    "education": ["academic background", "academics", "academic_background"],
}

_RAW_TO_CANONICAL: dict[str, str] = {
    alias.lower().strip(): canon
    for canon, aliases in _CANONICAL_ALIASES.items()
    for alias in aliases
}
_RAW_TO_CANONICAL.update({canon: canon for canon in _CANONICAL_ALIASES})


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


def _canonical_section_name(raw_key: str) -> str:
    """Map sectioner/raw section keys to canonical section names."""
    normalized = raw_key.lower().strip()
    return _RAW_TO_CANONICAL.get(normalized, normalized)


def _variants_have_content(variants: dict[str, Any] | None) -> bool:
    """True when at least one style variant has meaningful text."""
    if not isinstance(variants, dict):
        return False
    for style in ("balanced", "aggressive", "top_1_percent"):
        text = str(variants.get(style, "") or "").strip()
        if len(text) >= 10:
            return True
    return False


def _variants_richness(variants: dict[str, Any]) -> int:
    """Max character count across style variants (for merge tie-break)."""
    return max(
        len(str(variants.get(style, "") or ""))
        for style in ("balanced", "aggressive", "top_1_percent")
    )


def collapse_rewrites_to_canonical(rewrites: dict[str, Any]) -> dict[str, dict[str, str]]:
    """
    Collapse aliased rewrite keys (e.g. 'projects & side work') into canonical keys.

    When two raw keys map to the same canonical section, keep the richer variant
    so experience and projects never overwrite each other incorrectly.
    """
    collapsed: dict[str, dict[str, str]] = {}
    for raw_key, variants in rewrites.items():
        if not isinstance(variants, dict):
            continue
        canon = _canonical_section_name(str(raw_key))
        existing = collapsed.get(canon)
        if existing is None:
            collapsed[canon] = variants
            continue
        if _variants_richness(variants) > _variants_richness(existing):
            logging.warning(
                "RewriterValidator: merging duplicate rewrite key '%s' into '%s' "
                "(kept richer variant)",
                raw_key,
                canon,
            )
            collapsed[canon] = variants
    return collapsed


def _get_rewrite_variants(rewrites: dict[str, Any], section_name: str) -> dict[str, str] | None:
    """Return rewrite variants for a canonical section, including aliased keys."""
    if section_name in rewrites and isinstance(rewrites[section_name], dict):
        return rewrites[section_name]
    for key, value in rewrites.items():
        if not isinstance(value, dict):
            continue
        if _canonical_section_name(str(key)) == section_name:
            return value
    return None


def _extract_entry_ids(text: str, section: str) -> list[str]:
    """
    Extract the identifiers used for completeness checks per section type.
    For experience: ##COMPANY## markers.
    For projects: double-newline blocks when >=2; else empty so verbatim fallback runs.
    For others: first line of each entry block (heuristic).
    """
    if section == 'experience':
        ids: list[str] = []
        for company, role in _EXPERIENCE_MARKER_RE.findall(text):
            ids.append(f"{company} {role}".strip())
        if ids:
            return ids
        return _COMPANY_MARKER_RE.findall(text)

    if section == 'projects':
        blocks = _split_nonempty_blocks(text)
        ids_from_blocks = [b.splitlines()[0].strip()[:80] for b in blocks if b]
        if len(ids_from_blocks) >= 2:
            return ids_from_blocks
        return []

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
    """Backfill missing experience entries from raw resume text (see experience_audit)."""
    augmented = ensure_experience_completeness(section_text, resume_text)
    return augmented if augmented is not None else section_text


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
    """
    Resolve section from resume_sections by canonical name or alias.
    Handles dict or SectionText values.
    """
    raw = resume_sections.get(section_name)
    if raw is None:
        for stored_key, stored_val in resume_sections.items():
            if _canonicalize_key(stored_key) == section_name:
                raw = stored_val
                break
    if raw is None:
        return None
    if isinstance(raw, SectionText):
        return raw
    if isinstance(raw, dict):
        try:
            return SectionText(**raw)
        except Exception:
            return None
    return None


def assert_structural_completeness(
    rewrites: dict,
    resume_sections: dict,
) -> list[str]:
    """
    Return section names present in resume_sections but absent from rewrites.

    Call after validate_and_fix() and before build_final_docx().
    Does not raise — caller logs or surfaces findings.
    """
    missing: list[str] = []
    for raw_key in resume_sections:
        canonical = _canonical_section_name(str(raw_key))
        if canonical in rewrites or raw_key in rewrites:
            continue
        section_text = _get_section_text(resume_sections, canonical)
        if section_text and section_text.full_text.strip():
            missing.append(canonical)
    return missing


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

        log_experience_audit(
            "rewriter_validator_in",
            resume_text,
            resume_sections,
            rewrites,
        )

        # Build unified section name set — canonicalize resume_sections keys
        all_section_names = set(rewrites.keys()) | {
            _canonicalize_key(k) for k in resume_sections.keys()
        }

        for section_name in all_section_names:
            section_text = _get_section_text(resume_sections, section_name)
            if not section_text:
                continue
            if section_name == 'experience':
                section_text = _augment_experience_entries(section_text, resume_text)

            variants = _get_rewrite_variants(rewrites, section_name)
            if not _variants_have_content(variants):
                # Section exists in original but A4 produced nothing for it.
                # Build from sub_entries (Invariant B) — never initialise to full_text.
                content = _build_content_from_sub_entries(
                    section_name,
                    section_text.sub_entries or [],
                    full_text_fallback=section_text.full_text,
                )
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

        # ── Experience: force full rebuild when marker count < ground truth ─
        exp_section = _get_section_text(resume_sections, 'experience')
        if exp_section and resume_text.strip():
            exp_section = _augment_experience_entries(exp_section, resume_text)
            ground_n = len(detect_ground_truth_entries(resume_text))
            exp_variants = _get_rewrite_variants(rewrites, 'experience')
            if ground_n > 0 and exp_variants and exp_section.sub_entries:
                for style in ('balanced', 'aggressive', 'top_1_percent'):
                    style_text = exp_variants.get(style, '') or ''
                    marker_n = count_experience_markers(style_text)
                    if marker_n < len(exp_section.sub_entries):
                        all_anomalies.append(
                            f"experience/{style}: {marker_n} markers vs "
                            f"{len(exp_section.sub_entries)} sub_entries "
                            f"(ground truth {ground_n}) — rebuilding from sub_entries"
                        )
                exp_variants = rebuild_experience_rewrites(
                    exp_variants,
                    exp_section,
                    prefer_rewritten=True,
                )
                rewrites['experience'] = exp_variants

        rewrites = collapse_rewrites_to_canonical(rewrites)
        output['rewrites'] = rewrites
        output['styles'] = _build_legacy_styles(rewrites)

        log_experience_audit(
            "rewriter_validator_out",
            resume_text,
            resume_sections,
            rewrites,
        )

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
