"""
RewriterAgent - Agent 4 of the Resume Intelligence Platform.

Surgical sub-location rewriter: when a section has populated sub_changes,
only the entries with needs_change=True get rewritten; verbatim entries are
copied directly. Monolithic sections fall back to existing per-section logic.

Provider: Anthropic (claude-haiku-4.5)
Max tokens: 7000
"""

from __future__ import annotations

import logging
import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

from pydantic import BaseModel, Field

from .base_agent import BaseAgent
from backend.schemas.agent4_schema import RewriterInput
from backend.schemas.common import SectionText


COMPANY_HEADER_START = "##COMPANY##"
COMPANY_ROLE_START   = "##ROLE##"
HEADER_END           = "##END_HEADER##"


def _ensure_experience_markers(text: str, sub_label: str) -> str:
    """
    Wraps an experience sub-entry in structural markers for the docx writer.
    If text already starts with COMPANY_HEADER_START, returns unchanged.

    Marker format:
      ##COMPANY##Company Name | Location##ROLE##Role Title | Dates##END_HEADER##
      • bullet 1
      • bullet 2
      Tech Stack: React, Java
    """
    if text.startswith(COMPANY_HEADER_START):
        return text

    company = location = role = dates = ""

    if " — " in sub_label:
        parts = sub_label.split(" — ", 1)
        company = parts[0].strip()
        role_dates = parts[1].strip()
        m = _re.search(r'\(([^)]+)\)$', role_dates)
        if m:
            dates = m.group(1)
            role = role_dates[:m.start()].strip()
        else:
            role = role_dates
    else:
        company = sub_label

    # If parsing failed, extract from first lines of text
    if not company and text:
        first_lines = [l.strip() for l in text.splitlines() if l.strip()][:2]
        if first_lines:
            company = first_lines[0]
        if len(first_lines) > 1:
            role = first_lines[1]

    header = (f"{COMPANY_HEADER_START}{company}"
              f"{COMPANY_ROLE_START}{role} | {dates}{HEADER_END}")

    # Strip original header lines from body to avoid duplication
    text_lines = text.splitlines()
    content_start = 0
    for i, line in enumerate(text_lines[:3]):
        s = line.strip()
        if s and not s.startswith(('•', '-', '*', 'Tech Stack')):
            content_start = i + 1
        else:
            break
    content = '\n'.join(text_lines[content_start:]).strip()
    return f"{header}\n{content}"


SYSTEM_PROMPT = """CRITICAL MERGE RULE — Experience Preservation:

You will receive a full resume and a list of target companies to rewrite.
You MUST preserve ALL experience entries in the output, not just the rewritten ones.

Steps:
1. Parse ALL experience entries from the original resume
2. Rewrite ONLY the target companies
3. Merge: rewritten entries + all unchanged entries = full output
4. Validate: output entry count must equal input entry count

Example:
  Input:  8 entries (Flipkart, SmartVizX, Apttus, ClearTax, BT, Microsoft, Mindtree)
  Targets: Flipkart + SmartVizX
  Output: Must have all 8 entries (2 rewritten + 6 unchanged verbatim)

  WRONG: Only 2 entries in output DOCX
  RIGHT: All 8 entries in output DOCX

If output has fewer entries than input, rebuild before returning.

You are a resume rewriter for Indian software engineers with 20 years of experience and who has complete knowledge of the Indian job market and software engineering practices and what recruiter are looking for.

CRITICAL OUTPUT RULES:
1. Return ONLY a valid JSON object. No markdown, no backticks, no explanation.
2. Keep each rewrite to 150 words maximum per style. Be dense, not verbose.
3. Never leave a string unterminated. If you are near your output limit, close all
   open strings, arrays, and objects immediately and stop.
4. The JSON must be parseable by Python's json.loads() with zero post-processing.

Output format:
{"balanced": "...", "aggressive": "...", "top_1_percent": "..."}
"""

# Key invariant: a sub-entry with needs_change=False must NEVER be passed to the LLM.
# Verbatim copy only — zero LLM calls for entries that don't require changes.


class SectionRewrite(BaseModel):
    balanced: str = Field(..., min_length=1)
    aggressive: str = Field(..., min_length=1)
    top_1_percent: str = Field(..., min_length=1)


class RewriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(model="claude-haiku-4-5-20251001", max_tokens=7000, provider="anthropic")

    def run(self, input_dict: dict) -> dict:
        """
        Entry point for Agent 4 — rewrites resume sections based on gap analysis.

        Decision tree for each gap:
          1. needs_change=False → verbatim copy from sectioner to all 3 styles (zero LLM).
          2. sub_changes populated → _rewrite_with_sub_changes() (per-entry LLM calls).
          3. Monolithic section → _rewrite_monolithic() (existing per-section LLM call).

        original_content and original_text are sourced from resume_sections (the sectioner),
        not from the LLM gap analysis output — they are guaranteed to be populated.

        Args:
            input_dict: Must contain 'gaps' or 'gap_analysis' with section gap dicts,
                       'resume_sections' with {name: SectionText} from sectioner.

        Returns:
            Dict with 'rewrites' (section_name → 3-style rewrite) and legacy 'styles'.
        """
        normalized_input = dict(input_dict)
        if "gap_analysis" not in normalized_input:
            normalized_input["gap_analysis"] = {
                "gaps": normalized_input.pop("gaps", normalized_input.pop("section_gaps", [])),
                "strengths": normalized_input.pop("strengths", []),
                "quick_wins": normalized_input.pop("quick_wins", []),
                "match_score": normalized_input.pop("match_score", None),
                "confidence_score": normalized_input.pop("confidence_score", None),
            }
        normalized_input.setdefault("jd_intelligence", None)
        normalized_input.setdefault("style_fingerprint", None)
        normalized_input.setdefault("resume_text", "")

        inp = RewriterInput(**normalized_input)
        # Sectioner data — keyed by canonical section name, guaranteed populated
        resume_sections_raw = input_dict.get("resume_sections", {})
        resume_sections: Dict[str, SectionText] = {
            k: SectionText(**v) if isinstance(v, dict) else v
            for k, v in resume_sections_raw.items()
        }
        rewrites: Dict[str, Dict[str, str]] = {}

        gap_analysis = (
            inp.gap_analysis.model_dump()
            if hasattr(inp.gap_analysis, "model_dump")
            else inp.gap_analysis
        )
        gaps = gap_analysis.get("gaps") or gap_analysis.get("section_gaps") or []
        assert isinstance(gaps, list), f"RewriterAgent: gaps must be a list, got {type(gaps)}"
        logging.info("RewriterAgent: processing %d section gaps", len(gaps))
        unique_gaps: list[tuple[str, dict]] = []
        seen_sections: set[str] = set()
        for gap in gaps:
            section = str(gap.get("section", "other"))
            if section in seen_sections:
                continue
            seen_sections.add(section)
            unique_gaps.append((section, gap))

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(
                    self._rewrite_section_from_gap,
                    section,
                    gap,
                    resume_sections,
                ): section
                for section, gap in unique_gaps
            }
            for future in as_completed(futures):
                section = futures[future]
                rewrites[section] = future.result()

        # SECOND PASS — ensure every section from sectioner appears in rewrites.
        # A3 may have omitted sections with needs_change=False entirely.
        # This pass guarantees the full resume is always in the output.
        CANONICAL_SECTIONS = [
            "summary", "skills", "experience", "education",
            "certifications", "awards", "projects",
        ]
        for sec_name in CANONICAL_SECTIONS:
            if sec_name in rewrites:
                continue
            sec_text = resume_sections.get(sec_name)
            if isinstance(sec_text, dict):
                sec_text = SectionText(**sec_text)
            if not sec_text or not sec_text.full_text.strip():
                continue
            logging.info(
                "RewriterAgent: '%s' not in gaps — preserving verbatim", sec_name
            )
            content = sec_text.full_text
            if sec_name == "experience" and sec_text.sub_entries:
                parts = [
                    _ensure_experience_markers(e.verbatim_text, e.label)
                    for e in sec_text.sub_entries
                ]
                content = "\n\n".join(parts)
            rewrites[sec_name] = SectionRewrite(
                balanced=content,
                aggressive=content,
                top_1_percent=content,
            ).model_dump()

        return {
            "rewrites": rewrites,
            "styles": self._build_legacy_styles(rewrites),
        }

    def _rewrite_section_from_gap(
        self,
        section: str,
        gap: dict,
        resume_sections: Dict[str, SectionText],
    ) -> dict:
        """Compute one section rewrite from one section gap."""
        section_text = self._resolve_section_text(resume_sections, section)
        original_content = section_text.full_text if section_text else ""
        if not original_content:
            original_content = gap.get("original_content", "")

        if not gap.get("needs_change", gap.get("must_rewrite", True)):
            logging.info("RewriterAgent: copying verbatim section '%s'", section)
            return SectionRewrite(
                balanced=original_content or f"[{section} section unavailable]",
                aggressive=original_content or f"[{section} section unavailable]",
                top_1_percent=original_content or f"[{section} section unavailable]",
            ).model_dump()

        sub_changes = gap.get("sub_changes")
        if sub_changes:
            logging.info(
                "RewriterAgent: sub-location rewrite for section '%s' (%d entries)",
                section,
                len(sub_changes),
            )
            return self._rewrite_with_sub_changes(
                section, sub_changes, gap, section_text or None
            )

        return self._rewrite_monolithic(section, original_content, gap)

    def _build_sub_change_map(
        self,
        sub_changes: list,
        section_text: SectionText | None,
    ) -> dict[int, dict]:
        """
        Maps each sub_change to the integer index of its matching sub_entry.

        Priority:
          1. If sub_change carries ``entry_index`` (int) and in bounds, use directly.
          2. Otherwise try fuzzy label match against ``section_text.sub_entries``.
          3. Unmatched sub_changes are discarded and logged.
        """
        if not section_text or not section_text.sub_entries:
            return {}

        mapped: dict[int, dict] = {}
        used_indexes: set[int] = set()

        for raw_sub in sub_changes:
            sub = dict(raw_sub)
            raw_index = sub.get("entry_index")
            matched_index: int | None = None

            if isinstance(raw_index, int) and 0 <= raw_index < len(section_text.sub_entries):
                matched_index = raw_index
            elif isinstance(raw_index, int):
                logging.warning(
                    "RewriterAgent: sub_change '%s' has out-of-range entry_index=%s",
                    str(sub.get("sub_label", "") or sub.get("sub_id", "unknown")),
                    raw_index,
                )

            if matched_index is None:
                sub_label = str(sub.get("sub_label", "") or "")
                best_i: int | None = None
                best_rank = -1
                for i, entry in enumerate(section_text.sub_entries):
                    if i in used_indexes:
                        continue
                    entry_label = entry.label
                    if not self._labels_match(entry_label, sub_label):
                        continue
                    if entry_label == sub_label:
                        rank = 100
                    elif (
                        sub_label.lower() in entry_label.lower()
                        or entry_label.lower() in sub_label.lower()
                    ):
                        rank = 50
                    else:
                        rank = 10
                    if rank > best_rank:
                        best_rank = rank
                        best_i = i
                matched_index = best_i

            if matched_index is None:
                logging.warning(
                    "RewriterAgent: sub_change '%s' matched no SubEntry; skipping",
                    str(sub.get("sub_label", "") or sub.get("sub_id", "unknown")),
                )
                continue

            if matched_index in mapped:
                logging.warning(
                    "RewriterAgent: duplicate mapping for sub_entry index %d; keeping first",
                    matched_index,
                )
                continue

            mapped[matched_index] = sub
            used_indexes.add(matched_index)

        return mapped

    def _rewrite_with_sub_changes(
        self,
        section: str,
        sub_changes: list,
        gap: dict,
        section_text: SectionText | None,
    ) -> dict:
        """
        Rewrites a section entry-by-entry using sub_changes from the gap analysis.

        For each sub-change:
          - needs_change=False → verbatim copy from sectioner SubEntry to all 3 styles.
          - needs_change=True  → focused LLM call for this ONE entry only.

        After processing all entries, stitch results together with '\n\n' per style.

        Key invariant: entries with needs_change=False must NEVER call the LLM.
        Verbatim copy from sectioner only.

        When ``section_text.sub_entries`` is populated, output follows **canonical
        entry order**: each SubEntry appears exactly once (rewritten or verbatim).

        Args:
            section: Canonical section name (e.g. 'experience', 'education').
            sub_changes: List of SubLocationChange dicts from Agent 3.
            gap: The parent section gap dict (carries section-level context).
            section_text: SectionText from sectioner for this section, or None.

        Returns:
            Dict with balanced, aggressive, top_1_percent keys (SectionRewrite shape).
        """
        if section_text and section_text.sub_entries:
            return self._rewrite_with_sub_changes_ordered(
                section, sub_changes, gap, section_text
            )

        stitched_b: list[str] = []
        stitched_a: list[str] = []
        stitched_t: list[str] = []
        processed_labels: set[str] = set()

        for sub in sub_changes:
            sub_label = sub.get("sub_label", "")
            original_text = self._resolve_sub_text(section_text, sub_label)
            sub = dict(sub)
            sub["original_text"] = original_text
            if sub_label:
                processed_labels.add(sub_label)

            if not sub.get("needs_change", True):
                text = original_text
                if section == "experience":
                    text = _ensure_experience_markers(text, sub_label)
                stitched_b.append(text)
                stitched_a.append(text)
                stitched_t.append(text)
                continue

            entry_rw = self._rewrite_sub_entry(
                section=section,
                sub=sub,
                section_context=gap.get("rewrite_instruction", ""),
                original_verbatim=original_text,
            )

            if section == "experience":
                stitched_b.append(_ensure_experience_markers(
                    entry_rw.balanced, sub_label))
                stitched_a.append(_ensure_experience_markers(
                    entry_rw.aggressive, sub_label))
                stitched_t.append(_ensure_experience_markers(
                    entry_rw.top_1_percent, sub_label))
            else:
                stitched_b.append(entry_rw.balanced)
                stitched_a.append(entry_rw.aggressive)
                stitched_t.append(entry_rw.top_1_percent)

        if section_text and section_text.sub_entries:
            for entry in section_text.sub_entries:
                if any(self._labels_match(entry.label, label) for label in processed_labels):
                    continue
                text = entry.verbatim_text
                if section == "experience":
                    text = _ensure_experience_markers(text, entry.label)
                stitched_b.append(text)
                stitched_a.append(text)
                stitched_t.append(text)

        sep = "\n\n"
        return SectionRewrite(
            balanced=sep.join(stitched_b) or f"[{section} rewrite unavailable]",
            aggressive=sep.join(stitched_a) or f"[{section} rewrite unavailable]",
            top_1_percent=sep.join(stitched_t) or f"[{section} rewrite unavailable]",
        ).model_dump()

    def _rewrite_with_sub_changes_ordered(
        self,
        section: str,
        sub_changes: list,
        gap: dict,
        section_text: SectionText,
    ) -> dict:
        """
        Stitch sub_changes in the same order as ``section_text.sub_entries``.

        Ensures the merged section has exactly one block per sub-entry for DOCX.
        """
        sub_change_map = self._build_sub_change_map(sub_changes, section_text)
        stitched_b: list[str] = []
        stitched_a: list[str] = []
        stitched_t: list[str] = []
        ctx = gap.get("rewrite_instruction", "")

        for i, entry in enumerate(section_text.sub_entries):
            sub = sub_change_map.get(i)
            if sub is None:
                text = entry.verbatim_text
                if section == "experience":
                    text = _ensure_experience_markers(text, entry.label)
                stitched_b.append(text)
                stitched_a.append(text)
                stitched_t.append(text)
                continue

            if not sub.get("needs_change", True):
                text = entry.verbatim_text
                if section == "experience":
                    text = _ensure_experience_markers(text, entry.label)
                stitched_b.append(text)
                stitched_a.append(text)
                stitched_t.append(text)
                continue

            entry_rw = self._rewrite_sub_entry(
                section=section,
                sub=sub,
                section_context=ctx,
                original_verbatim=entry.verbatim_text,
            )

            if section == "experience":
                stitched_b.append(_ensure_experience_markers(
                    entry_rw.balanced, entry.label))
                stitched_a.append(_ensure_experience_markers(
                    entry_rw.aggressive, entry.label))
                stitched_t.append(_ensure_experience_markers(
                    entry_rw.top_1_percent, entry.label))
            else:
                stitched_b.append(entry_rw.balanced)
                stitched_a.append(entry_rw.aggressive)
                stitched_t.append(entry_rw.top_1_percent)

        try:
            assert len(stitched_b) == len(section_text.sub_entries), (
                f"RewriterAgent: stitched entry count {len(stitched_b)} != "
                f"sectioner entry count {len(section_text.sub_entries)} for section '{section}'"
            )
        except AssertionError as exc:
            logging.warning("%s", exc)
            fallback = section_text.full_text or f"[{section} rewrite unavailable]"
            return SectionRewrite(
                balanced=fallback,
                aggressive=fallback,
                top_1_percent=fallback,
            ).model_dump()

        sep = "\n\n"
        balanced = sep.join(stitched_b) or f"[{section} rewrite unavailable]"
        aggressive = sep.join(stitched_a) or f"[{section} rewrite unavailable]"
        top_1 = sep.join(stitched_t) or f"[{section} rewrite unavailable]"

        if section == "experience":
            n_markers = balanced.count(COMPANY_HEADER_START)
            n_entries = len(section_text.sub_entries)
            if n_markers != n_entries:
                logging.error(
                    "RewriterAgent: experience marker count %d != sub_entries %d — verbatim rebuild",
                    n_markers,
                    n_entries,
                )
                verbatim_parts = [
                    _ensure_experience_markers(e.verbatim_text, e.label)
                    for e in section_text.sub_entries
                ]
                fallback = sep.join(verbatim_parts)
                balanced = aggressive = top_1 = fallback

        return SectionRewrite(
            balanced=balanced,
            aggressive=aggressive,
            top_1_percent=top_1,
        ).model_dump()

    def _rewrite_sub_entry(
        self,
        section: str,
        sub: dict,
        section_context: str,
        original_verbatim: str = "",
    ) -> SectionRewrite:
        """
        Rewrites a SINGLE resume sub-entry with a focused LLM call.

        Args:
            section: Parent section name (e.g. 'experience').
            sub: SubLocationChange dict with rewrite_instruction, missing_keywords.
            section_context: Section-level rewrite instruction for additional context.

        Returns:
            SectionRewrite with balanced, aggressive, top_1_percent rewrites for this entry only.

        Fallback: if LLM call fails after retry, returns original verbatim text for all 3 styles.
        """
        original_text = original_verbatim or sub.get("original_text", "")
        rewrite_hint = sub.get("rewrite_instruction", "")
        missing_kw = sub.get("missing_keywords", [])

        prompt = (
            "You are rewriting ONE entry that will be stitched back into the full section.\n"
            f"Section: {section}\n"
            f"Entry label: {sub.get('sub_label', 'unknown')}\n"
            f"Original entry:\n{original_text}\n\n"
            f"Entry-level instruction: {rewrite_hint}\n"
            f"Section-level instruction: {section_context or 'N/A'}\n"
            f"Missing keywords to add: {', '.join(missing_kw[:10])}\n\n"
            'Return ONLY JSON: {"balanced":"...","aggressive":"...","top_1_percent":"..."}\n'
            "No markdown, no fences, no extra keys. Max 150 words per style.\n"
            "Anti-hallucination: Never invent companies, degrees, metrics, or projects.\n"
            "OUTPUT STRUCTURE FOR EXPERIENCE ENTRIES:\n"
            "Line 1: Company name and location (e.g. 'Flipkart  Bengaluru, India')\n"
            "Line 2: Role title and dates (e.g. 'Engineering Manager  2021–present')\n"
            "Lines 3+: Bullet points starting with •\n"
            "Last line: Tech Stack: lang1, lang2 (only if present in original)\n"
            "Do NOT add any other headers or labels.\n"
            "Use placeholders [X%], [N users], [Xms], [INR X Cr] for missing metrics only."
        )

        for attempt in range(2):
            try:
                raw = self._call_llm(SYSTEM_PROMPT, prompt)
                parsed = self._parse_json(raw)
                return SectionRewrite(**parsed)
            except Exception as exc:
                if attempt == 1:
                    logging.warning(
                        "RewriterAgent: sub-entry '%s' failed after 2 attempts, using original. Error: %s",
                        sub.get("sub_id", "unknown"),
                        exc,
                    )
                    return SectionRewrite(
                        balanced=original_text or f"[{section} entry unavailable]",
                        aggressive=original_text or f"[{section} entry unavailable]",
                        top_1_percent=original_text or f"[{section} entry unavailable]",
                    )

    def _rewrite_monolithic(self, section: str, original_content: str, gap: dict) -> dict:
        """
        Rewrites a whole section monolithically (fallback when no sub_changes available).

        Uses the existing per-section LLM call pattern. Max 2 attempts with fallback.

        Args:
            section: Canonical section name.
            original_content: The section's verbatim text from sectioner.
            gap: Section gap dict with rewrite hints and missing keywords.

        Returns:
            Dict with balanced, aggressive, top_1_percent keys.
        """
        if section == "summary":
            prompt = (
                "Rewrite this professional summary. "
                "Write 3-5 sentences covering: "
                "(1) current role and org scope, "
                "(2) core technical expertise with 2-3 specific technologies, "
                "(3) key career achievement with a metric, "
                "(4) value the candidate brings to the next role. "
                "First person. Present tense. No evaluation labels. "
                'Return ONLY JSON: {"balanced":"...","aggressive":"...","top_1_percent":"..."}\n\n'
                f"Original summary:\n{original_content}\n\n"
                f"Instruction: {gap.get('rewrite_instruction', 'Strengthen this summary.')}\n"
                f"Missing keywords: {', '.join((gap.get('missing_keywords') or [])[:10])}"
            )
        else:
            prompt = (
                "Rewrite this resume section using the instruction below.\n"
                'Return ONLY JSON: {"balanced":"...","aggressive":"...","top_1_percent":"..."}\n'
                "No markdown, no fences, no extra keys. Max 150 words per style.\n\n"
                f"Section: {section}\n"
                "Original:\n"
                f"{(original_content[:2000] or '[Section not present - write from scratch]')}\n\n"
                f"Instruction: {gap.get('rewrite_instruction', gap.get('suggestion', 'Improve this section.'))}\n"
                f"Missing keywords to add: {', '.join((gap.get('missing_keywords') or [])[:10])}\n\n"
                "Anti-hallucination: Never invent companies, degrees, metrics, or projects.\n"
                "Use placeholders [X%], [N users], [Xms], [INR X Cr] for missing metrics only."
            )

        for attempt in range(2):
            try:
                raw = self._call_llm(SYSTEM_PROMPT, prompt)
                parsed = self._parse_json(raw)
                return SectionRewrite(**parsed).model_dump()
            except Exception as exc:
                if attempt == 1:
                    logging.warning(
                        "RewriterAgent: section '%s' failed, using fallback. Error: %s",
                        section, exc,
                    )
                    return SectionRewrite(
                        balanced=original_content or f"[{section} rewrite unavailable]",
                        aggressive=original_content or f"[{section} rewrite unavailable]",
                        top_1_percent=original_content or f"[{section} rewrite unavailable]",
                    ).model_dump()

    def _resolve_sub_text(self, section_text: SectionText | None, sub_label: str) -> str:
        if not section_text:
            return ""
        # 1. Exact match
        for entry in section_text.sub_entries:
            if entry.label == sub_label:
                return entry.verbatim_text
        # 2. Case-insensitive substring
        lowered = sub_label.lower()
        for entry in section_text.sub_entries:
            if lowered in entry.label.lower() or entry.label.lower() in lowered:
                return entry.verbatim_text
        # 3. First significant word match
        words = [w for w in sub_label.split() if len(w) > 3]
        for entry in section_text.sub_entries:
            if any(w.lower() in entry.label.lower() for w in words):
                return entry.verbatim_text
        # 4. Last resort: full section text (never return empty)
        return section_text.full_text

    def _labels_match(self, a: str, b: str) -> bool:
        """Return true when two sub-entry labels refer to the same original entry."""
        stopwords = {
            "engineer", "engineering", "manager", "senior", "lead", "software",
            "consultant", "developer", "architect", "principal", "staff",
            "bengaluru", "bangalore", "india", "remote", "hybrid", "onsite",
            "company", "experience", "payroll", "altran",
        }

        def normalized(value: str) -> str:
            value = _re.sub(r"\d{4}", "", value.lower())
            return _re.sub(r"[^a-z0-9]+", " ", value).strip()

        def tokens(value: str) -> set[str]:
            value = _re.sub(r"\d{4}", "", value)
            return {
                token.lower()
                for token in _re.split(r"[\s|,.\-()]+", value)
                if len(token) > 3 and token.lower() not in stopwords
            }

        na = normalized(a)
        nb = normalized(b)
        if na and nb and (na in nb or nb in na):
            return True

        ta = tokens(a)
        tb = tokens(b)
        if not ta or not tb:
            return False
        return bool(ta & tb) and len(ta & tb) / min(len(ta), len(tb)) > 0.6

    def _resolve_section_text(
        self,
        resume_sections: Dict[str, SectionText],
        section: str,
    ) -> SectionText | None:
        """Resolve a section by canonical name, then common aliases."""
        section_text = resume_sections.get(section)
        if section_text:
            return section_text

        aliases = {
            "skills": ["technical_skills", "core_competencies", "key_skills"],
            "experience": ["work_experience", "professional_experience", "employment"],
            "education": ["academic_background", "academics"],
            "certifications": ["certificates", "credentials"],
            "awards": ["achievements", "honors"],
            "summary": ["professional_summary", "objective", "profile"],
            "projects": ["project_experience", "personal_projects"],
        }
        for alias in aliases.get(section, []):
            section_text = resume_sections.get(alias)
            if section_text:
                return section_text
        return None

    def _build_legacy_styles(self, rewrites: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        styles: Dict[str, Dict[str, Any]] = {
            "balanced": {"summary": "", "skills": "", "experience": [], "projects": []},
            "aggressive": {"summary": "", "skills": "", "experience": [], "projects": []},
            "top_1_percent": {"summary": "", "skills": "", "experience": [], "projects": []},
        }

        for section_name, variants in rewrites.items():
            for style_name, section_text in variants.items():
                if section_name == "summary":
                    styles[style_name]["summary"] = section_text
                elif section_name == "skills":
                    styles[style_name]["skills"] = section_text
                elif section_name == "experience":
                    styles[style_name]["experience"] = [{
                        "company": "Experience",
                        "role": "",
                        "rewritten_bullets": self._split_bullets(section_text) or [section_text],
                    }]
                elif section_name == "projects":
                    styles[style_name]["projects"] = [{
                        "name": "Projects",
                        "tech_stack": [],
                        "rewritten_description": section_text,
                    }]

        return styles

    def _split_bullets(self, text: str) -> list[str]:
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip().lstrip("-*").strip()
            if line:
                lines.append(line)
        return lines
