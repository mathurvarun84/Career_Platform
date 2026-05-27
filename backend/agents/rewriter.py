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

_BULLET_SEP = _re.compile(r"\s*[•\-\*]\s+")

# Sections that carry sub_entries — content must be built from sub_entries, not full_text
_SUB_ENTRY_SECTIONS = frozenset({"experience", "projects", "education", "certifications"})

# Monolithic sections (summary, skills, …) emit one REPLACE_TEXT patch for surgical apply
_MONOLITHIC_PATCH_SECTIONS = frozenset({"summary", "skills", "objective", "projects"})


def _resolve_patch_target_in_resume(
    section: str,
    original_content: str,
    resume_text: str,
) -> str:
    """Pick original_text anchor that exists verbatim in the full resume."""
    original = (original_content or "").strip()
    if not original:
        return ""
    if resume_text and original in resume_text:
        return original
    if resume_text:
        try:
            from parser import _extract_section_blocks

            block = (_extract_section_blocks(resume_text).get(section) or "").strip()
            if block and block in resume_text:
                return block
        except Exception:
            pass
    return original


def _finalize_sub_entry_patch(
    patch_raw: dict | None,
    anchor_text: str,
    *,
    resume_text: str = "",
) -> dict | None:
    """
    Ensure sub-entry patches anchor on verbatim resume text.

    LLMs sometimes return patch.original_text as empty; without an anchor the
    patch engine cannot apply the change.
    """
    if not patch_raw:
        return None
    replacement = (patch_raw.get("replacement_text") or "").strip()
    if not replacement:
        return None
    anchor = anchor_text.strip()
    if not anchor:
        return None

    original = (patch_raw.get("original_text") or "").strip()
    if not original:
        patch_raw["original_text"] = anchor
    elif resume_text and original not in resume_text:
        if anchor in resume_text:
            patch_raw["original_text"] = anchor
        elif original in anchor:
            pass
        else:
            logging.warning(
                "RewriterAgent: dropping patch — original_text not in resume"
            )
            return None
    elif original not in anchor and anchor not in original:
        logging.warning(
            "RewriterAgent: dropping patch — original_text not in entry anchor"
        )
        return None
    return patch_raw


def _build_monolithic_section_patch(
    section: str,
    original_content: str,
    rewrite_dict: dict,
    gap: dict,
    resume_text: str = "",
) -> dict | None:
    """Build a surgical REPLACE_TEXT patch for monolithic section rewrites."""
    if section not in _MONOLITHIC_PATCH_SECTIONS:
        return None
    balanced = (rewrite_dict.get("balanced") or "").strip()
    if not balanced:
        return None
    if section == "skills":
        from engine.ats_scorer import normalize_skills_layout

        balanced = normalize_skills_layout(balanced)
    target = _resolve_patch_target_in_resume(section, original_content, resume_text)
    if not target:
        return None
    if resume_text and target not in resume_text:
        logging.warning(
            "RewriterAgent: skip patch for '%s' — anchor not found in resume_text",
            section,
        )
        return None
    if balanced == target:
        return None
    return {
        "op": "replace_text",
        "section": section,
        "original_text": target,
        "replacement_text": balanced,
        "issue_detected": (
            gap.get("description")
            or gap.get("gap_reason")
            or f"Improve {section} section"
        ),
        "fix_rationale": (
            gap.get("rewrite_instruction")
            or gap.get("suggestion")
            or "Monolithic section rewrite for surgical apply."
        ),
    }

# Canonical alias map — maps any raw section key to its canonical name
_SECTION_CANONICAL_MAP: dict[str, str] = {
    # awards variants
    "awards & achievements":    "awards",
    "awards and achievements":  "awards",
    "honours":                  "awards",
    "accomplishments":          "awards",
    "achievements":             "awards",
    "honors":                   "awards",
    # projects variants
    "projects & side work":     "projects",
    "projects and side work":   "projects",
    "side projects":            "projects",
    "project work":             "projects",
    "key projects":             "projects",
    "personal projects":        "projects",
    # experience variants
    "work experience":          "experience",
    "professional experience":  "experience",
    "employment history":       "experience",
    "employment":               "experience",
    "career history":           "experience",
    "work history":             "experience",
    # skills variants
    "technical skills":         "skills",
    "core competencies":        "skills",
    "key skills":               "skills",
    "technologies":             "skills",
    "technical expertise":      "skills",
    # summary variants
    "professional summary":     "summary",
    "objective":                "summary",
    "profile":                  "summary",
    "about":                    "summary",
    "career objective":         "summary",
    # education variants
    "academic background":      "education",
    "academics":                "education",
    "qualifications":           "education",
    # certifications variants
    "certificates":             "certifications",
    "credentials":              "certifications",
    "licenses":                 "certifications",
}


def _canonicalize_key(raw_key: str) -> str:
    """Map any raw section key to its canonical name. Returns raw_key if no match."""
    return _SECTION_CANONICAL_MAP.get(raw_key.lower().strip(), raw_key.lower().strip())


# Date range pattern — matches any of:
#   "Feb 2017 – Nov 2018", "Sep 2020 – Present", "2013 – 2017", "Nov 2013 – Jan 2017"
_DATE_RANGE_RE = _re.compile(
    r'(?:'
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}'
        r'|\d{4}'
    r')'
    r'\s*[–—\-]+\s*'
    r'(?:'
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}'
        r'|[Pp]resent|[Cc]urrent|\d{4}'
    r')',
    _re.IGNORECASE,
)

# Separators that commonly divide role from company, or company from location
_PIPE_OR_DASH_RE = _re.compile(r'\s*[\|]\s*|\s+[–—]\s+')
# Whitespace/comma gaps on company lines (used after pipe/dash split)
_CO_LOC_SEP_RE = _re.compile(r'\s{2,}|\s*[,]\s+(?=[A-Z])')
# "Company Name City, Country" — split from the right on City, Country
_COMPANY_CITY_COUNTRY_RE = _re.compile(r"^(.*)\s+([^,]+,\s*[^,]+)$")


def _split_company_line_location(company_line: str) -> tuple[str, str]:
    """
    Split a company-only header line into company name and location.

    Handles: "Vimeo Bengaluru, India", "BT India Bengaluru, India",
    "Company | Location", and double-space separators.
    """
    line = (company_line or "").strip()
    if not line:
        return "", ""
    parts = _PIPE_OR_DASH_RE.split(line, maxsplit=1)
    if len(parts) > 1:
        return parts[0].strip(), parts[1].strip()
    city_country = _COMPANY_CITY_COUNTRY_RE.match(line)
    if city_country:
        return city_country.group(1).strip(), city_country.group(2).strip()
    gap_match = _re.search(r"\s{2,}", line)
    if gap_match:
        return line[: gap_match.start()].strip(), line[gap_match.end() :].strip()
    return line, ""


def _reconcile_company_with_sub_label(
    company: str,
    location: str,
    sub_label: str,
) -> tuple[str, str]:
    """Prefer sub_label company prefix when parsed company absorbed city text."""
    label_company = ""
    if " — " in sub_label:
        label_company = sub_label.split(" — ", 1)[0].strip()
    elif " - " in sub_label:
        label_company = sub_label.split(" - ", 1)[0].strip()

    if not label_company:
        return company, location

    lc = label_company.lower()
    co = company.lower()
    if not company:
        return label_company, location
    if co == lc:
        return company, location
    if co.startswith(lc) and co != lc:
        rest = company[len(label_company) :].strip()
        company = label_company
        if rest:
            if location and rest.lower() not in location.lower():
                location = f"{rest}, {location}"
            elif not location:
                location = rest
    return company, location


def _parse_experience_header_from_verbatim(text: str) -> dict[str, str]:
    """
    Extract company, role, location, and dates from the first non-empty lines
    of an experience entry's verbatim text.

    Fixed-format path (LLM output):
      Line 0: COMPANY_NAME_ONLY
      Line 1: Role Title | Location | Start_Date – End_Date

    Legacy-format fallback (original verbatim resume text):
      Scans up to 4 lines for a date-range pattern; whichever line has dates
      is treated as the role line, preceding line(s) as company/location.

    Returns dict with keys: company, role, location, dates (all str, "" if not found).
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()][:4]
    company = role = location = dates = ""

    if not lines:
        return dict(company=company, role=role, location=location, dates=dates)

    # Fixed-format path (LLM): company-only line 0, role|location|dates on line 1
    if (
        len(lines) >= 2
        and _DATE_RANGE_RE.search(lines[1])
        and not _DATE_RANGE_RE.search(lines[0])
        and "|" not in lines[0]
    ):
        company, location = _split_company_line_location(lines[0])
        role_line = lines[1]
        date_match = _DATE_RANGE_RE.search(role_line)
        dates = date_match.group(0).strip()
        role_part = role_line[:date_match.start()].strip().rstrip("|–—-").strip()
        if " | " in role_part:
            parts = role_part.split(" | ", 1)
            role = parts[0].strip()
            location = parts[1].strip()
        else:
            role = role_part
        return dict(company=company, role=role, location=location, dates=dates)

    # Legacy-format: scan for first date-bearing line
    date_line_idx = -1
    date_match = None
    for i, line in enumerate(lines):
        m = _DATE_RANGE_RE.search(line)
        if m:
            date_line_idx = i
            date_match = m
            break

    if date_line_idx < 0 or not date_match:
        return dict(company=company, role=role, location=location, dates=dates)

    dates = date_match.group(0).strip()
    date_line = lines[date_line_idx]
    before_dates = date_line[:date_match.start()].strip().rstrip("|–—-").strip()

    def _split_role_company_location(header: str) -> tuple[str, str, str]:
        """Parse 'Role | Company — Location' into role, company, location."""
        if " | " not in header:
            return "", "", ""
        role_part, company_loc = header.split(" | ", 1)
        r = role_part.strip()
        if " — " in company_loc:
            c, loc = company_loc.split(" — ", 1)
            return r, c.strip(), loc.strip()
        return r, company_loc.strip(), ""

    if " | " in before_dates:
        # Single-line legacy: "Role | Company — Location  Dates"
        role, company, location = _split_role_company_location(before_dates)
    elif date_line_idx > 0:
        # Two-line legacy: header on line above date-only line
        role, company, location = _split_role_company_location(lines[date_line_idx - 1])
    elif before_dates:
        role = before_dates
    else:
        # Fallback: company on line 0, partial role text before dates on date line
        company_line = lines[0]
        parts = _PIPE_OR_DASH_RE.split(company_line, maxsplit=1)
        company = parts[0].strip()
        location = parts[1].strip() if len(parts) > 1 else ""
        if not location:
            gap_match = _CO_LOC_SEP_RE.search(company_line)
            if gap_match:
                company = company_line[:gap_match.start()].strip()
                location = company_line[gap_match.end():].strip()

    return dict(company=company, role=role, location=location, dates=dates)


def _fallback_from_sub_entries(
    section: str,
    section_text: SectionText | None = None,
    *,
    sub_entries: list | None = None,
    sep: str = "\n\n",
) -> str:
    """Rebuild section content from sub_entries only (no full_text)."""
    entries = sub_entries if sub_entries is not None else (
        section_text.sub_entries if section_text else []
    )
    if not entries:
        return ""
    parts: list[str] = []
    for entry in entries:
        t = entry.verbatim_text.strip()
        if not t:
            continue
        if section == "experience":
            t = _ensure_experience_markers(t, entry.label)
        parts.append(t)
    return sep.join(parts)


def _build_content_from_sub_entries(
    section: str,
    sub_entries: list,
    full_text_fallback: str = "",
) -> str:
    """
    Build section content string exclusively from sub_entries.
    Falls back to full_text_fallback only when sub_entries is empty or all blank.

    For experience entries, wraps each entry in ##COMPANY## markers.
    For all other sub-entry sections, joins verbatim_text with double newline.

    Args:
        section:             Canonical section name.
        sub_entries:         List of SubEntry objects from SectionText.
        full_text_fallback:  Used ONLY when sub_entries is empty or all blank.

    Returns:
        Assembled content string ready for the rewrites dict.
    """
    if sub_entries:
        built = _fallback_from_sub_entries(section, sub_entries=sub_entries)
        if built.strip():
            return built
    return full_text_fallback


def _line_is_experience_header(s: str, is_first_nonbullet: bool) -> bool:
    """
    Return True when s is a structural header line in a fixed-format experience entry.

    Fixed format: Line 0 = company name only, Line 1 = role | location | dates.
      - Bullet lines are never headers.
      - A line containing a date range is the role/date header (Line 1).
      - The very first non-empty non-bullet line is the company header (Line 0).
    """
    if not s or s.startswith(('•', '-', '*', 'Tech Stack')):
        return False
    if _DATE_RANGE_RE.search(s):
        return True
    if is_first_nonbullet:
        return True
    return False


def _is_bare_sentence_fragment(text: str) -> bool:
    """
    True when text is a bullet continuation or mid-sentence fragment.

    Such fragments must not be wrapped in ##COMPANY## markers.
    """
    if _DATE_RANGE_RE.search(text) or "|" in text:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    # Multi-line blocks with bullets are structured experience entries, not fragments.
    if len(lines) >= 2 and any(
        ln.startswith(("•", "-", "*")) or ln.lower().startswith("tech stack")
        for ln in lines
    ):
        return False
    first = lines[0]
    if len(first) >= 120:
        return False
    if len(first) < 20 and len(lines) == 1:
        return True
    if first[0].islower() or first[0].isdigit():
        return True
    return False


def _ensure_experience_markers(text: str, sub_label: str) -> str:
    """
    Wraps an experience sub-entry in structural markers for the docx writer.
    If text already starts with COMPANY_HEADER_START, returns unchanged.

    Parsing hierarchy:
      1. Parse company/role/location/dates from verbatim_text lines (primary — format-agnostic).
      2. Fill any gaps from sub_label (secondary fallback).

    Marker format produced:
      ##COMPANY##Company Name | Location##ROLE##Role Title | Dates##END_HEADER##
      • bullet 1
      • bullet 2
      Tech Stack: lang1, lang2
    """
    if text.startswith(COMPANY_HEADER_START):
        return text
    if _is_bare_sentence_fragment(text):
        return text

    # Step 1: Parse from verbatim_text — works for any resume format
    parsed = _parse_experience_header_from_verbatim(text)
    company  = parsed["company"]
    role     = parsed["role"]
    location = parsed["location"]
    dates    = parsed["dates"]

    # Step 2: Fill gaps from sub_label — secondary source only
    if not company:
        if " — " in sub_label:
            label_parts = sub_label.split(" — ", 1)
            company = label_parts[0].strip()
            role_dates_str = label_parts[1].strip()
            if not role and not dates:
                m = _re.search(r'\(([^)]+)\)$', role_dates_str)
                if m:
                    dates = m.group(1)
                    role = role_dates_str[:m.start()].strip()
                else:
                    role = role_dates_str
        else:
            company = sub_label.strip()

    company, location = _reconcile_company_with_sub_label(company, location, sub_label)

    # Build the marker header
    co_loc = f"{company} | {location}" if location else company
    ro_dt  = f"{role} | {dates}"       if dates    else role
    header = f"{COMPANY_HEADER_START}{co_loc}{COMPANY_ROLE_START}{ro_dt}{HEADER_END}"

    # Strip the header lines from body to avoid duplication in the docx.
    # Uses _line_is_experience_header() — format-aware, handles fixed (LLM) and
    # legacy (verbatim) formats. Blank lines are skipped without breaking the scan.
    text_lines = text.splitlines()
    content_start = 0
    first_nonbullet_found = False
    for i, line in enumerate(text_lines[:4]):
        s = line.strip()
        if not s:
            continue
        is_bullet = s.startswith(('•', '-', '*', 'Tech Stack'))
        is_first = not first_nonbullet_found and not is_bullet
        if _line_is_experience_header(s, is_first):
            if is_first:
                first_nonbullet_found = True
            content_start = i + 1
        else:
            break
    content = '\n'.join(text_lines[content_start:]).strip()

    # PDF parser produces single-line verbatim_text (no \n). Recover inline bullets.
    if not content and len(text_lines) == 1:
        raw = text_lines[0]
        first_bullet = raw.find('•')
        if first_bullet > 0:
            bullet_parts = raw[first_bullet:].split('•')
            content = '\n'.join(
                f'• {b.strip()}' for b in bullet_parts if b.strip()
            )

    return f"{header}\n{content}"


SYSTEM_PROMPT = """You are rewriting a SINGLE resume entry. You will receive exactly one entry's text.

RULES:
1. Rewrite ONLY the entry you are given. Do NOT add entries from other companies or roles.
2. Return ONLY valid JSON. No markdown, no backticks, no explanation before or after.
3. Max 150 words per style variant. Be specific and impact-focused.
4. Never invent companies, roles, degrees, metrics, or dates not present in the original.
5. Do NOT invent architectural patterns, technology choices, frameworks, tools, or capability
   claims not present in the original text (e.g. do not add Kafka, event-driven, async/await,
   microservices, queue-based processing, or cloud platforms unless they appear in the entry).
6. Use placeholders [X%], [N users], [Xms] ONLY for metrics the original left blank.
7. Output JSON must be parseable by Python json.loads() with zero post-processing.

Output format — exactly these 4 keys, nothing else:
{"balanced": "...", "aggressive": "...", "top_1_percent": "...", "patch": {...}}
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
        all_patches: list[dict] = []

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
            section = self._canonicalize_section_key(str(gap.get("section", "other")))
            if section in seen_sections:
                continue
            seen_sections.add(section)
            gap = dict(gap)
            gap["section"] = section
            unique_gaps.append((section, gap))

        resume_text = inp.resume_text or normalized_input.get("resume_text", "")
        jd_intelligence = inp.jd_intelligence or normalized_input.get("jd_intelligence")

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(
                    self._rewrite_section_from_gap,
                    section,
                    gap,
                    resume_sections,
                    resume_text,
                    jd_intelligence,
                ): section
                for section, gap in unique_gaps
            }
            for future in as_completed(futures):
                section = futures[future]
                rewrite_dict, patches = future.result()
                rewrites[section] = rewrite_dict
                all_patches.extend(patches)

        from validator.rewriter_validator import collapse_rewrites_to_canonical

        rewrites = collapse_rewrites_to_canonical(rewrites)

        # SECOND PASS — ensure every section the sectioner extracted appears in rewrites.
        # Drives from resume_sections.items() (not a hardcoded list) to catch any key the
        # sectioner used, including non-canonical ones like "awards & achievements".
        # Uses _build_content_from_sub_entries to enforce Invariant B (sub_entries first).
        for raw_key, sec_text in resume_sections.items():
            canonical = _canonicalize_key(str(raw_key))
            if canonical in rewrites:
                continue
            if isinstance(sec_text, dict):
                try:
                    sec_text = SectionText(**sec_text)
                except Exception:
                    continue
            if not sec_text:
                continue
            # Check there is something to preserve
            has_content = (
                (sec_text.sub_entries and any(e.verbatim_text.strip() for e in sec_text.sub_entries))
                or sec_text.full_text.strip()
            )
            if not has_content:
                continue
            logging.info("RewriterAgent: '%s' → '%s' not in gaps — preserving verbatim", raw_key, canonical)
            content = _build_content_from_sub_entries(
                canonical,
                sec_text.sub_entries or [],
                full_text_fallback=sec_text.full_text,
            )
            if not content.strip():
                continue
            rewrites[canonical] = SectionRewrite(
                balanced=content,
                aggressive=content,
                top_1_percent=content,
            ).model_dump()

        rewrites = collapse_rewrites_to_canonical(rewrites)

        logging.info(
            "RewriterAgent: final sections in rewrites: %s",
            list(rewrites.keys()),
        )
        missing = [
            self._canonicalize_section_key(str(key))
            for key in resume_sections
            if self._canonicalize_section_key(str(key)) not in rewrites
        ]
        if missing:
            logging.warning(
                "RewriterAgent: sectioner sections not in rewrites: %s",
                missing,
            )

        return {
            "rewrites": rewrites,
            "styles": self._build_legacy_styles(rewrites),
            "patches": all_patches,
        }

    def _rewrite_section_from_gap(
        self,
        section: str,
        gap: dict,
        resume_sections: Dict[str, SectionText],
        resume_text: str = "",
        jd_intelligence: dict | None = None,
    ) -> tuple[dict, list[dict]]:
        """
        Compute one section rewrite from one section gap.
        Returns: (section_rewrite_dict, patches_list)
        """
        section_text = self._resolve_section_text(resume_sections, section)
        original_content = section_text.full_text if section_text else ""
        if not original_content:
            original_content = gap.get("original_content", "")

        needs_change = gap.get("needs_change", gap.get("must_rewrite", True))
        if (
            section == "summary"
            and not (original_content or "").strip()
            and gap.get("present_in_resume") is False
        ):
            needs_change = True

        if not needs_change:
            logging.info("RewriterAgent: copying verbatim section '%s'", section)
            if section_text and section in _SUB_ENTRY_SECTIONS and section_text.sub_entries:
                content = _build_content_from_sub_entries(
                    section,
                    section_text.sub_entries,
                    full_text_fallback=section_text.full_text,
                )
                if section == "experience":
                    logging.info(
                        "RewriterAgent: experience verbatim stitch — %d entries, %d markers",
                        len(section_text.sub_entries),
                        content.count(COMPANY_HEADER_START),
                    )
                return (SectionRewrite(
                    balanced=content or f"[{section} section unavailable]",
                    aggressive=content or f"[{section} section unavailable]",
                    top_1_percent=content or f"[{section} section unavailable]",
                ).model_dump(), [])
            return (SectionRewrite(
                balanced=original_content or f"[{section} section unavailable]",
                aggressive=original_content or f"[{section} section unavailable]",
                top_1_percent=original_content or f"[{section} section unavailable]",
            ).model_dump(), [])

        sub_changes = gap.get("sub_changes")
        if sub_changes:
            logging.info(
                "RewriterAgent: sub-location rewrite for section '%s' (%d entries)",
                section,
                len(sub_changes),
            )
            return self._rewrite_with_sub_changes(
                section, sub_changes, gap, section_text or None, resume_text
            )

        # Never monolithic-rewrite experience when sub_entries exist — LLM drops entries.
        if (
            section == "experience"
            and section_text
            and section_text.sub_entries
        ):
            logging.warning(
                "RewriterAgent: experience gap has no sub_changes but %d sub_entries — "
                "using ordered per-entry path (avoids monolithic truncation)",
                len(section_text.sub_entries),
            )
            return self._rewrite_with_sub_changes(
                section, [], gap, section_text, resume_text
            )

        # Pre-marked experience block with no sub_entries — preserve verbatim (no monolithic).
        if (
            section == "experience"
            and COMPANY_HEADER_START in (original_content or "")
            and not (section_text and section_text.sub_entries)
        ):
            oc = original_content
            return (SectionRewrite(
                balanced=oc,
                aggressive=oc,
                top_1_percent=oc,
            ).model_dump(), [])

        rewrite_dict = self._rewrite_monolithic(
            section,
            original_content,
            gap,
            resume_text=resume_text,
            jd_intelligence=jd_intelligence,
        )
        patch_raw = _build_monolithic_section_patch(
            section, original_content, rewrite_dict, gap, resume_text
        )
        return (rewrite_dict, [patch_raw] if patch_raw else [])

    def _build_add_summary_prompt(
        self,
        gap: dict,
        jd_intelligence: dict | None,
        resume_text: str,
    ) -> str:
        """Prompt when the resume has no summary — write one from scratch."""
        jd = jd_intelligence or {}
        role = str(jd.get("role_title") or "the target role").strip()
        must_have = ", ".join(
            str(k) for k in (jd.get("must_have_skills") or [])[:8] if str(k).strip()
        ) or "none"
        nice_have = ", ".join(
            str(k) for k in (jd.get("nice_to_have_skills") or [])[:5] if str(k).strip()
        ) or "none"
        instruction = (
            gap.get("rewrite_instruction")
            or "Write a JD-tailored professional summary."
        )
        missing_kw = ", ".join((gap.get("missing_keywords") or [])[:10]) or "none"
        resume_excerpt = (resume_text or "")[:3500].strip() or "[Resume text unavailable]"

        return (
            "TASK: The resume has NO professional summary section. "
            "Write a NEW summary from scratch.\n\n"
            "RULES:\n"
            "- 3-5 sentences, first person, present tense, 80-120 words total\n"
            "- Use ONLY employers, roles, technologies, and achievements from the resume excerpt\n"
            "- Never invent companies, degrees, titles, or metrics\n"
            "- Use [X%], [N users], [Xms] only for metrics genuinely absent\n"
            f"- Target role (JD): {role}\n"
            f"- Must-have skills (JD): {must_have}\n"
            f"- Nice-to-have skills (JD): {nice_have}\n"
            f"- Rewrite instruction: {instruction}\n"
            f"- Keywords to weave in: {missing_kw}\n\n"
            f"RESUME EXCERPT (source of truth):\n{resume_excerpt}\n\n"
            'Return ONLY JSON: {"balanced":"...","aggressive":"...","top_1_percent":"..."}\n'
            "No markdown, no fences, no extra keys."
        )

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
        resume_text: str = "",
    ) -> tuple[dict, list[dict]]:
        """
        Rewrites a section entry-by-entry.

        INVARIANT: iterates section_text.sub_entries as the master list.
        sub_changes from the gap agent is an annotation map — it never drives
        the loop. Entries the gap agent didn't mention are copied verbatim.

        For each sub_entry:
          - Find matching sub_change by entry_index (preferred) or fuzzy label.
          - If no match or needs_change=False → verbatim copy, zero LLM.
          - If needs_change=True → focused LLM call for this ONE entry.

        Returns:
            Tuple of (section_rewrite_dict, patches_list).
        """
        sep = "\n\n"
        collected_patches: list[dict] = []

        # If no sub_entries in sectioner data, fall back to the sub_changes list
        # (degraded mode — gap agent labels used as entry source)
        if not section_text or not section_text.sub_entries:
            logging.warning(
                "RewriterAgent: section '%s' has no sub_entries — iterating sub_changes only",
                section,
            )
            stitched_b, stitched_a, stitched_t = [], [], []
            for sub in sub_changes:
                original_text = (sub.get("original_text") or "").strip()
                if not original_text and section_text:
                    original_text = self._resolve_sub_text(
                        section_text, str(sub.get("sub_label", "") or "")
                    )
                if not sub.get("needs_change", True):
                    text = original_text
                    if section == "experience":
                        text = _ensure_experience_markers(text, sub.get("sub_label", ""))
                    stitched_b.append(text)
                    stitched_a.append(text)
                    stitched_t.append(text)
                elif not original_text:
                    logging.warning(
                        "RewriterAgent: no verbatim anchor for sub_label '%s' — skipping",
                        sub.get("sub_label", "unknown"),
                    )
                    continue
                else:
                    entry_rw, patch_raw = self._rewrite_sub_entry(
                        section,
                        sub,
                        gap.get("rewrite_instruction", ""),
                        original_text,
                        resume_text=resume_text,
                        section_text=section_text,
                    )
                    if patch_raw:
                        patch_raw.setdefault("gap_id", gap.get("gap_id", ""))
                        patch_raw.setdefault("section", section)
                        patch_raw.setdefault("sub_entry_label", sub.get("sub_label", ""))
                        collected_patches.append(patch_raw)
                    if section == "experience":
                        stitched_b.append(_ensure_experience_markers(entry_rw.balanced, sub.get("sub_label", "")))
                        stitched_a.append(_ensure_experience_markers(entry_rw.aggressive, sub.get("sub_label", "")))
                        stitched_t.append(_ensure_experience_markers(entry_rw.top_1_percent, sub.get("sub_label", "")))
                    else:
                        stitched_b.append(entry_rw.balanced)
                        stitched_a.append(entry_rw.aggressive)
                        stitched_t.append(entry_rw.top_1_percent)
            fallback = _build_content_from_sub_entries(section, [], full_text_fallback=f"[{section} rewrite unavailable]")
            return (SectionRewrite(
                balanced=sep.join(stitched_b) or fallback,
                aggressive=sep.join(stitched_a) or fallback,
                top_1_percent=sep.join(stitched_t) or fallback,
            ).model_dump(), collected_patches)

        # Build annotation map: entry_index → sub_change
        sub_change_map: dict[int, dict] = {}
        unmatched_sub_changes = list(sub_changes)

        # Pass 1: explicit entry_index
        still_unmatched = []
        for sub in unmatched_sub_changes:
            idx = sub.get("entry_index")
            if isinstance(idx, int) and 0 <= idx < len(section_text.sub_entries):
                sub_change_map[idx] = sub
            else:
                still_unmatched.append(sub)

        # Pass 2: fuzzy label match for remaining
        for sub in still_unmatched:
            sub_label = sub.get("sub_label", "").lower()
            words = [w for w in sub_label.split() if len(w) > 3]
            for i, entry in enumerate(section_text.sub_entries):
                if i in sub_change_map:
                    continue
                entry_label = entry.label.lower()
                if sub_label in entry_label or entry_label in sub_label:
                    sub_change_map[i] = sub
                    break
                if words and any(w in entry_label for w in words):
                    sub_change_map[i] = sub
                    break

        # Master loop — drives from sectioner sub_entries
        stitched_b, stitched_a, stitched_t = [], [], []

        for i, entry in enumerate(section_text.sub_entries):
            verbatim = entry.verbatim_text.strip()
            if not verbatim:
                logging.warning("RewriterAgent: sub_entry[%d] for '%s' has empty verbatim_text — skipping", i, section)
                continue

            sub = sub_change_map.get(i)

            # No matching sub_change OR needs_change=False → verbatim copy
            if sub is None or not sub.get("needs_change", True):
                text = verbatim
                if section == "experience":
                    text = _ensure_experience_markers(text, entry.label)
                stitched_b.append(text)
                stitched_a.append(text)
                stitched_t.append(text)
                continue

            # needs_change=True → LLM rewrite
            entry_rw, patch_raw = self._rewrite_sub_entry(
                section,
                sub,
                gap.get("rewrite_instruction", ""),
                verbatim,
                resume_text=resume_text,
                section_text=section_text,
            )
            if patch_raw:
                patch_raw.setdefault("gap_id", gap.get("gap_id", ""))
                patch_raw.setdefault("section", section)
                patch_raw.setdefault("sub_entry_label", entry.label)
                collected_patches.append(patch_raw)

            if section == "experience":
                stitched_b.append(_ensure_experience_markers(entry_rw.balanced, entry.label))
                stitched_a.append(_ensure_experience_markers(entry_rw.aggressive, entry.label))
                stitched_t.append(_ensure_experience_markers(entry_rw.top_1_percent, entry.label))
            else:
                stitched_b.append(entry_rw.balanced)
                stitched_a.append(entry_rw.aggressive)
                stitched_t.append(entry_rw.top_1_percent)

        if len(stitched_b) != len([e for e in section_text.sub_entries if e.verbatim_text.strip()]):
            logging.warning(
                "RewriterAgent: stitched count %d != non-empty sub_entry count %d for section '%s'",
                len(stitched_b),
                len([e for e in section_text.sub_entries if e.verbatim_text.strip()]),
                section,
            )

        balanced = sep.join(s for s in stitched_b if s.strip())
        aggressive = sep.join(s for s in stitched_a if s.strip())
        top = sep.join(s for s in stitched_t if s.strip())

        if not balanced.strip():
            logging.error(
                "RewriterAgent: stitched output empty for section '%s' — "
                "falling back to verbatim sub_entries",
                section,
            )
            fallback = _fallback_from_sub_entries(section, section_text, sep=sep)
            balanced = aggressive = top = fallback or f"[{section} rewrite unavailable]"

        return (SectionRewrite(
            balanced=balanced,
            aggressive=aggressive,
            top_1_percent=top,
        ).model_dump(), collected_patches)

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
            fallback = _fallback_from_sub_entries(section, section_text) or f"[{section} rewrite unavailable]"
            return SectionRewrite(
                balanced=fallback,
                aggressive=fallback,
                top_1_percent=fallback,
            ).model_dump()

        sep = "\n\n"
        balanced = sep.join(stitched_b)
        aggressive = sep.join(stitched_a)
        top_1 = sep.join(stitched_t)
        if not balanced.strip():
            fallback = _fallback_from_sub_entries(section, section_text, sep=sep)
            balanced = aggressive = top_1 = fallback or f"[{section} rewrite unavailable]"

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
        *,
        resume_text: str = "",
        section_text: SectionText | None = None,
    ) -> tuple[SectionRewrite, dict | None]:
        """
        Rewrites a SINGLE resume sub-entry with a focused LLM call.

        Args:
            section: Parent section name (e.g. 'experience').
            sub: SubLocationChange dict with rewrite_instruction, missing_keywords.
            section_context: Section-level rewrite instruction for additional context.

        Returns:
            Tuple of (SectionRewrite, patch_dict or None).
            patch_dict contains: op, original_text, replacement_text, issue_detected, fix_rationale.

        Fallback: if LLM call fails after retry, returns original verbatim text for all 3 styles.
        """
        original_text = (original_verbatim or sub.get("original_text", "")).strip()
        if not original_text and section_text:
            original_text = self._resolve_sub_text(
                section_text, str(sub.get("sub_label", "") or "")
            )
        if not original_text:
            logging.warning(
                "RewriterAgent: no verbatim anchor for sub_label '%s' in '%s' — skipping LLM",
                sub.get("sub_label", "unknown"),
                section,
            )
            return SectionRewrite(
                balanced="",
                aggressive="",
                top_1_percent="",
            ), None

        rewrite_hint = sub.get("rewrite_instruction", "")
        missing_kw = sub.get("missing_keywords", [])

        _LENGTH_KEYWORDS = {
            "shorten", "shorter", "concise", "trim",
            "brief", "verbose", "reduce", "≤20", "≤15",
        }
        is_shorten_instruction = any(
            kw in rewrite_hint.lower() for kw in _LENGTH_KEYWORDS
        )
        original_word_count = len(original_text.split()) if original_text else 0

        prompt = (
            f"TASK: Rewrite this single {section} entry. Output only this entry — nothing else.\n\n"

            "ENTRY TO REWRITE:\n"
            f"{original_text}\n\n"

            f"Entry label: {sub.get('sub_label', 'unknown')}\n"
            f"Rewrite instruction: {rewrite_hint}\n"
            f"Section context: {section_context or 'N/A'}\n"
            f"Keywords to weave in: {', '.join(missing_kw[:10]) or 'none'}\n\n"

            "OUTPUT STRUCTURE FOR EXPERIENCE ENTRIES — MANDATORY FORMAT:\n"
            "Line 1: COMPANY_NAME_ONLY (no location, no dates, no separators)\n"
            "Line 2: Role Title | Location | Start_Date – End_Date\n"
            "Lines 3+: Bullet points, each starting with • \n"
            "Last line (optional): Tech Stack: lang1, lang2 — include ONLY if present in original\n"
            "CRITICAL: Line 1 must be the company name alone. Never put dates on Line 1.\n"
            "CRITICAL: Never add information not present in the original entry.\n"
            "CRITICAL: Do NOT invent architectural patterns, technologies, tools, or capabilities "
            "(Kafka, event-driven, async/await, microservices, queue-based, Redis, Kubernetes, etc.) "
            "unless they already appear in ENTRY TO REWRITE.\n\n"

            "RULES:\n"
            "- Do NOT output any other company, role, or entry — only the one above\n"
            "- Do NOT add a company or role that is not in the original entry\n"
            "- Do NOT bold, italicise, or add markdown formatting\n"
            "- Max 150 words per style\n"
            "- Use [X%], [N users], [Xms] for missing metrics only — never fabricate numbers\n"
            "- Reframe existing content only — never introduce new tech stacks or patterns\n\n"

            "Return ONLY JSON with exactly these keys:\n"
            '{"balanced":"...","aggressive":"...","top_1_percent":"...","patch":{...}}\n\n'

            "patch field:\n"
            '{"op":"replace_text",'
            '"original_text":"verbatim substring you changed (empty string if unsure)",'
            '"replacement_text":"same as balanced",'
            '"issue_detected":"one sentence",'
            '"fix_rationale":"one sentence"}'
        )

        for attempt in range(2):
            try:
                raw = self._call_llm(SYSTEM_PROMPT, prompt)
                parsed = self._parse_json(raw)
                result = SectionRewrite(**parsed)
                patch_raw = _finalize_sub_entry_patch(
                    parsed.get("patch"),
                    original_text,
                    resume_text=resume_text,
                )

                if (
                    is_shorten_instruction
                    and attempt == 0
                    and original_word_count > 0
                ):
                    output_word_count = len(result.balanced.split())
                    if output_word_count >= original_word_count * 0.9:
                        logging.info(
                            "RewriterAgent: shorten instruction not followed "
                            "(%d → %d words), retrying sub-entry '%s'",
                            original_word_count,
                            output_word_count,
                            sub.get("sub_id", "unknown"),
                        )
                        continue

                return result, patch_raw

            except Exception as exc:
                if attempt == 1:
                    logging.warning(
                        "RewriterAgent: sub-entry '%s' failed after 2 attempts, "
                        "using original. Error: %s",
                        sub.get("sub_id", "unknown"),
                        exc,
                    )
                    return SectionRewrite(
                        balanced=original_text or f"[{section} entry unavailable]",
                        aggressive=original_text or f"[{section} entry unavailable]",
                        top_1_percent=original_text or f"[{section} entry unavailable]",
                    ), None

    def _rewrite_monolithic(
        self,
        section: str,
        original_content: str,
        gap: dict,
        *,
        resume_text: str = "",
        jd_intelligence: dict | None = None,
    ) -> dict:
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
            if not (original_content or "").strip():
                prompt = self._build_add_summary_prompt(
                    gap, jd_intelligence, resume_text
                )
            else:
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
                "Never invent architectural patterns, technologies, tools, or capability claims "
                "not in the original (Kafka, event-driven, async, microservices, etc.).\n"
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
                    fallback = original_content
                    if section == "summary" and not (fallback or "").strip():
                        fallback = (
                            f"[{section} rewrite unavailable — "
                            "re-run analysis with resume + JD]"
                        )
                    return SectionRewrite(
                        balanced=fallback or f"[{section} rewrite unavailable]",
                        aggressive=fallback or f"[{section} rewrite unavailable]",
                        top_1_percent=fallback or f"[{section} rewrite unavailable]",
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
        # 4. Shared fuzzy label rescue (same as gap_analyzer)
        from backend.agents.gap_analyzer import _fuzzy_match_label

        valid_labels = {entry.label for entry in section_text.sub_entries if entry.label}
        rescued = _fuzzy_match_label(sub_label, valid_labels)
        if rescued:
            for entry in section_text.sub_entries:
                if entry.label == rescued:
                    return entry.verbatim_text
        logging.warning(
            "RewriterAgent: _resolve_sub_text failed for sub_label '%s'",
            sub_label,
        )
        return ""

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
        """Resolve a section by canonical name, then by alias map."""
        result = resume_sections.get(section)
        if result:
            return result if isinstance(result, SectionText) else SectionText(**result) if isinstance(result, dict) else None
        for raw_key, value in resume_sections.items():
            if _canonicalize_key(raw_key) == section:
                if isinstance(value, SectionText):
                    return value
                if isinstance(value, dict):
                    try:
                        return SectionText(**value)
                    except Exception:
                        pass
        return None

    def _canonicalize_section_key(self, raw_key: str) -> str:
        """Map sectioner/raw section keys to canonical section names."""
        normalized = raw_key.lower().strip()
        if normalized in _SECTION_CANONICAL_MAP:
            return _SECTION_CANONICAL_MAP[normalized]
        underscore_aliases = {
            "technical_skills": "skills",
            "core_competencies": "skills",
            "key_skills": "skills",
            "work_experience": "experience",
            "professional_experience": "experience",
            "professional_summary": "summary",
            "project_experience": "projects",
            "personal_projects": "projects",
            "academic_background": "education",
        }
        return underscore_aliases.get(normalized, normalized)

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
        if _BULLET_SEP.search(text):
            parts = [
                _re.sub(r"^[•\-\*]\s*", "", part.strip())
                for part in _BULLET_SEP.split(text)
                if part.strip()
            ]
            return [part for part in parts if part]
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip().lstrip("-*").strip()
            if line:
                lines.append(line)
        return lines
