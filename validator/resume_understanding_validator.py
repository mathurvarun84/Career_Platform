"""
ResumeUnderstandingValidator — post-processes A1 output.

Validates and repairs ALL canonical sections:
  experience   — sub_entries per company (previously built)
  education    — sub_entries per degree, detects missing degrees
  certifications — sub_entries per cert, detects missing certs
  projects     — sub_entries per project, detects missing projects
  skills       — full_text completeness, category line count
  summary      — full_text non-empty when summary header detected
  awards       — full_text completeness
  publications — full_text completeness
  extracurriculars — full_text completeness
  sections_present — cross-check all extracted sections are listed
  experience_years — recompute from date ranges if 0
  tech_stack       — verify non-empty if skills section present

No LLM calls. Pure regex + heuristic. Runs in <15ms.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any

# ─────────────────────────────────────────────
# Section boundary detection
# ─────────────────────────────────────────────

# All section headers we recognise (maps canonical → aliases)
SECTION_ALIASES: dict[str, list[str]] = {
    "summary":         ["summary", "professional summary", "objective",
                        "profile", "about", "career objective"],
    "skills":          ["skills", "technical skills", "core competencies",
                        "key skills", "competencies", "technologies",
                        "technical expertise"],
    "experience":      ["experience", "work experience", "professional experience",
                        "employment history", "employment", "career history",
                        "work history"],
    "education":       ["education", "academic background", "academics",
                        "qualifications", "academic qualifications"],
    "certifications":  ["certifications", "certificates", "licenses",
                        "credentials", "professional certifications"],
    "projects":        ["projects", "personal projects", "side projects",
                        "key projects", "academic projects"],
    "awards":          ["awards", "achievements", "honors", "honours",
                        "awards and achievements", "accomplishments"],
    "publications":    ["publications", "research", "papers",
                        "research papers", "journal articles"],
    "extracurriculars":["extracurriculars", "activities", "volunteer",
                        "community service", "extra curricular"],
}

# Reverse map: alias → canonical
_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canon
    for canon, aliases in SECTION_ALIASES.items()
    for alias in aliases
}

_ALL_SECTION_HEADERS = sorted(
    [a for aliases in SECTION_ALIASES.values() for a in aliases],
    key=len, reverse=True,
)

_SECTION_HEADER_RE = re.compile(
    r'(?im)^\s*(' +
    '|'.join(re.escape(h) for h in _ALL_SECTION_HEADERS) +
    r')\s*:?\s*$'
)

_DATE_RANGE_RE = re.compile(
    r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?'
    r'(\d{4})\s*(?:–|—|-|to)\s*'
    r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?'
    r'(\d{4}|\bPresent\b|\bpresent\b|\bCurrent\b|\bcurrent\b)',
    re.IGNORECASE
)

# Core date-range token (do NOT use [-–—to]+ — that wrongly matches letters t/o inside words)
_DATE_RANGE_CORE = (
    r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?'
    r'(?:(?:0?[1-9]|1[0-2])/)?'
    r'(?:19|20)\d{2}'
    r'\s*(?:–|—|-|to)\s*'
    r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?'
    r'(?:(?:0?[1-9]|1[0-2])/)?'
    r'(?:(?:19|20)\d{2}|\bPresent\b|\bCurrent\b|\bTill\s+Date\b|\bOn\s?Going\b)'
)

_DATE_RANGE_LINE_RE = re.compile(_DATE_RANGE_CORE, re.IGNORECASE)

# PDF/DOCX often merges role header + dates on one line (tab or spaces before month)
_INLINE_HEADER_DATE_SUFFIX_RE = re.compile(
    r'^(.+?)\s+(' + _DATE_RANGE_CORE + r')\s*$',
    re.IGNORECASE,
)

# Structural signal: any non-bullet line with a separator between role and company.
# Do not enumerate role titles — that breaks non-engineering personas.
_ROLE_HEADER_HINT_RE = re.compile(r'.+[|–—].+')


# ─────────────────────────────────────────────
# Section text extraction from raw resume
# ─────────────────────────────────────────────

# Pre-computed collapsed (no-spaces) forms of every known section alias.
# Used by _normalize_spaced_heading Case 2 to handle PDFs that split a
# single heading word: "EXPERI ENCE" → "EXPERIENCE", "AW ARDS" → "AWARDS".
_COLLAPSED_SECTION_KEYWORDS: frozenset[str] = frozenset(
    alias.replace(' ', '')
    for aliases in SECTION_ALIASES.values()
    for alias in aliases
)


def _normalize_spaced_heading(line: str) -> str:
    """Collapse spaced-character headings to their solid form.

    Handles two PDF extraction artifacts:

    Case 1 — every letter spaced: 'C E R T I F I C A T I O N S' → 'CERTIFICATIONS'
    Case 2 — partial word splits: 'EXPERI ENCE' → 'EXPERIENCE', 'AW ARDS' → 'AWARDS'
      Only collapses when the result (lowercased) is a known section keyword so
      two-word phrases like 'WORK EXPERIENCE' are never collapsed.
    """
    stripped = line.strip()
    # Case 1: every single uppercase letter separated by one space
    if re.match(r'^([A-Z] ){2,}[A-Z]$', stripped):
        return stripped.replace(' ', '')
    # Case 2: all-uppercase line with spaces — collapse if it forms a known heading
    if re.match(r'^[A-Z][A-Z ]{2,}[A-Z]$', stripped):
        collapsed = stripped.replace(' ', '')
        if collapsed.lower() in _COLLAPSED_SECTION_KEYWORDS:
            return collapsed
    return stripped


def _extract_all_sections_from_text(resume_text: str) -> dict[str, str]:
    """
    Splits raw resume_text into canonical section blocks using header detection.
    Returns dict of {canonical_name: section_body_text}.
    Only includes sections actually found in the text.
    """
    lines = resume_text.splitlines()
    sections: dict[str, str] = {}
    current_canon: str | None = None
    current_lines: list[str] = []

    for line in lines:
        # Normalise spaced headings before matching (e.g. "C E R T I F I C A T I O N S")
        stripped = _normalize_spaced_heading(line)
        # Check if this line is a section header
        m = _SECTION_HEADER_RE.match(stripped)
        if m:
            # Save previous section
            if current_canon and current_lines:
                body = '\n'.join(current_lines).strip()
                if body:
                    # Keep the longest body if section appears twice
                    if current_canon not in sections or len(body) > len(sections[current_canon]):
                        sections[current_canon] = body
            header_text = m.group(1).strip().lower()
            current_canon = _ALIAS_TO_CANONICAL.get(header_text, header_text)
            current_lines = []
        else:
            if current_canon is not None:
                current_lines.append(line)

    # Save last section
    if current_canon and current_lines:
        body = '\n'.join(current_lines).strip()
        if body:
            if current_canon not in sections or len(body) > len(sections[current_canon]):
                sections[current_canon] = body

    return sections


def _empty_section(section_name: str) -> dict[str, Any]:
    """Return a SectionText-compatible dict for a canonical section."""
    return {"header": section_name, "full_text": "", "sub_entries": []}


def _coerce_section_dict(section_name: str, section_data: Any) -> dict[str, Any]:
    """Normalize dict/Pydantic section values into plain SectionText-compatible dicts."""
    if hasattr(section_data, "model_dump"):
        section_data = section_data.model_dump()
    elif hasattr(section_data, "dict"):
        section_data = section_data.dict()

    if not isinstance(section_data, dict):
        section_data = {}

    normalized = {
        "header": section_data.get("header") or section_name,
        "full_text": section_data.get("full_text") or "",
        "sub_entries": [],
    }

    for entry in section_data.get("sub_entries") or []:
        if hasattr(entry, "model_dump"):
            entry = entry.model_dump()
        elif hasattr(entry, "dict"):
            entry = entry.dict()
        if not isinstance(entry, dict):
            continue
        normalized["sub_entries"].append({
            "label": entry.get("label") or "",
            "verbatim_text": entry.get("verbatim_text") or "",
        })

    return normalized


def _coerce_sections(raw_sections: Any) -> dict[str, dict[str, Any]]:
    """Normalize the A1 section container, regardless of whether it is sections/resume_sections."""
    if hasattr(raw_sections, "model_dump"):
        raw_sections = raw_sections.model_dump()
    elif hasattr(raw_sections, "dict"):
        raw_sections = raw_sections.dict()

    if not isinstance(raw_sections, dict):
        return {}

    return {
        section_name: _coerce_section_dict(section_name, section_data)
        for section_name, section_data in raw_sections.items()
    }


# ─────────────────────────────────────────────
# Sub-entry detection per section type
# ─────────────────────────────────────────────

# EXPERIENCE: detects company block start lines
_COMPANY_BLOCK_PATTERNS = [
    r'^([A-Z][A-Za-z0-9& .,\-]+)\s*[|–—]\s*.+\s*[|–—]\s*\d{4}',
    r'^([A-Z][A-Za-z0-9& .,\-]+)\s*\(\d{4}',
    r'^([A-Z][A-Z0-9 &,.\-]{4,})\s*$',
    r'(?:Engineer|Manager|Lead|Developer|Analyst|Architect|Consultant|Director'
    r'|Intern|Associate|Principal|Staff|Head)\s*[,@at]+\s*([A-Z][A-Za-z0-9& .,]+)',
]

# EDUCATION: detects degree block start lines
_DEGREE_PATTERNS = [
    # Universal degree abbreviations
    r'\b(B\.?[A-Z]{1,3}|M\.?[A-Z]{1,3}|PhD|Ph\.D\.?|Doctor\w*|'
    r'Bachelor\w*|Master\w*|Diploma|Graduate|Postgraduate|Associate)\b',
    # Institution line: capitalised name + University/College/Institute/School + year
    r'(?i)(University|College|Institute|School|Academy)\b.{0,60}\d{4}',
    r'(?i)\d{4}.{0,60}(University|College|Institute|School|Academy)\b',
]

# CERTIFICATIONS: detects cert block start lines
_CERT_PATTERNS = [
    r'Certif\w+\b',        # Certified, Certificate, Certification
    r'Licen[sc]\w+\b',     # License, Licensed, Licensure
    r'Accreditat\w+\b',
    r'Pursuing\b',
    r'Completed\b',
    # Structural: issuer | date  OR  name, date
    r'\|\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?\d{4}',
    r'[,\-–—]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?\d{4}\s*$',
]

# PROJECTS: detects project block start lines
_PROJECT_PATTERNS = [
    r'^\s*\d+\.\s+[A-Z]',              # "1. Project Name"
    r'^[A-Z][A-Za-z0-9 _\-]{3,60}:',   # "ProjectName:"
    r'^\*\*[A-Z]',                      # "**ProjectName"
    r'^#{1,3}\s+[A-Z]',                 # "### ProjectName"
    # Title | Anything — no hardcoded tech stack
    r'^[A-Z][A-Za-z0-9 _\-]{3,60}\s*[|–—]\s*\S',
]


_MONTH_PAT = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
_YEAR_PAT = r'(?:19|20)\d{2}'
_PRESENT_PAT = r'(?:Present|Current|Till\s+Date|OnGoing)'

_FULL_DATE_RE = re.compile(
    rf'(?:{_MONTH_PAT}\.?\s+)?{_YEAR_PAT}'
    rf'\s*[–—-]\s*'
    rf'(?:{_MONTH_PAT}\.?\s+)?(?:{_YEAR_PAT}|{_PRESENT_PAT})',
    re.IGNORECASE,
)
_BARE_DATE_RE = re.compile(
    rf'^[–—]?\s*(?:{_MONTH_PAT}\.?\s+)?(?:{_YEAR_PAT}|{_PRESENT_PAT})\s*$',
    re.IGNORECASE,
)
_SECTION_HDR_RE = re.compile(r'^[A-Z][A-Z &]{3,}$')
_BULLET_START_RE = re.compile(r'^[•\-\*·●]')


def _is_pdf_fragment(line: str, prev_line: str) -> bool:
    """
    Returns True when `line` is a PDF soft-wrap fragment that belongs
    to the end of `prev_line` rather than being an independent unit.

    Rules (in order, all purely structural — no hardcoded content):

    1. Bullet lines are never fragments.
    2. Section headers (ALL CAPS, short) are never fragments.
    3. Complete role headers (contain | AND a full date range) are never fragments.
    4. Starts with lowercase → fragment (soft-wrap continuation).
    5. Starts with – or — → fragment (split date range, second half).
    6. Is a bare date/month string → fragment (split date range, second half).
    7. Starts with a digit AND prev line is a bullet ending without terminal
       punctuation → fragment (metric continuation, e.g. "20% MTTR reduction.").
    8. Starts with uppercase AND prev line is a bullet ending without terminal
       punctuation → fragment (sentence continuation, e.g. "GMV growth...").
    """
    s = line.strip()
    if not s:
        return False
    # Rule 1
    if _BULLET_START_RE.match(s):
        return False
    # Rule 2
    if _SECTION_HDR_RE.match(s):
        return False
    # Rule 3
    if '|' in s and _FULL_DATE_RE.search(s):
        return False
    # Rule 4
    if s[0].islower():
        return True
    # Rule 5
    if re.match(r'^[–—]', s):
        return True
    # Rule 6
    if _BARE_DATE_RE.match(s):
        return True
    # Rules 7 & 8: digit or uppercase start after an unterminated bullet
    prev = prev_line.strip()
    if prev and _BULLET_START_RE.match(prev) and not re.search(r'[.!?:]\s*$', prev):
        if s[0].isdigit() or s[0].isupper():
            return True
    return False


def _normalize_experience_section_text(section_text: str) -> str:
    """
    Normalize PDF-extracted experience text before block detection.

    Pass 0 — Fragment rejoining (generic, zero hardcoded strings):
      Rejoins PDF soft-wrap continuations and split date ranges so that
      every role header becomes a single complete line before anchor
      detection runs.

    Pass 1 — Existing normalization (unchanged):
      Splits inline-date headers, collapses whitespace.
    """
    # ── Pass 0: rejoin PDF line fragments ────────────────────────────
    raw_lines = section_text.splitlines()
    joined: list[str] = []
    for line in raw_lines:
        if joined and _is_pdf_fragment(line, joined[-1]):
            joined[-1] = joined[-1].rstrip() + ' ' + line.strip()
        else:
            joined.append(line)
    section_text = '\n'.join(joined)

    # ── Pass 1: existing normalization (keep exactly as-is) ──────────
    out_lines: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.replace('\t', ' ').strip()
        line = re.sub(r' {2,}', ' ', line)
        if not line:
            out_lines.append('')
            continue
        if line.startswith(('•', '-', '*', '·', '●')):
            out_lines.append(line)
            continue
        m = _INLINE_HEADER_DATE_SUFFIX_RE.match(line)
        if m and _ROLE_HEADER_HINT_RE.search(m.group(1)):
            header = m.group(1).strip()
            dates = m.group(2).strip()
            out_lines.append(header)
            out_lines.append(dates)
            continue
        out_lines.append(line)
    return '\n'.join(out_lines)


def _is_experience_date_anchor_line(line: str) -> bool:
    """
    True when a line is a job date-range anchor (not a long bullet with stray digits).

    Rejects bullet lines and prose lines where a substring looks like a date range.
    """
    s = line.strip()
    if not s or s.startswith(('•', '-', '*', '·', '●')):
        return False
    m = _DATE_RANGE_LINE_RE.search(s)
    if not m:
        return False
    # Standalone date line (common when PDF splits header / dates)
    if len(s) <= 55 and not s.startswith('•'):
        return True
    # Role header with inline dates: ``Role | Co — City Sep 2020 – Present``
    if _INLINE_HEADER_DATE_SUFFIX_RE.match(s) and _ROLE_HEADER_HINT_RE.search(s):
        return True
    if '|' in s and _ROLE_HEADER_HINT_RE.search(s) and len(s) <= 160:
        return True
    # Long prose / bullets must not anchor a block
    if len(s) > 100:
        return False
    return bool(_ROLE_HEADER_HINT_RE.search(s))


def _is_role_header_line(line: str) -> bool:
    """True when a line structurally looks like a role/company header."""
    s = line.strip()
    if not s or s.startswith(('•', '-', '*', '·', '●')):
        return False
    if _is_experience_date_anchor_line(s):
        return False
    if len(s) > 160:
        return False
    if _ROLE_HEADER_HINT_RE.search(s):
        return True
    if re.search(r'\s(?:at|@)\s+[A-Z]', s):
        return True
    # Role title and company on one line separated by wide space
    if re.match(r'^[A-Z][^\n]{2,80}\s{2,}[A-Z]', s):
        return True
    return False


def _detect_experience_by_role_headers(section_text: str) -> list[dict]:
    """
    Detect experience entry boundaries by role-title header lines.
    Used when date-range detection finds fewer than 2 blocks.

    Matches lines with structural role|company separators or Role  Company spacing.

    Returns list of {'label': str, 'text': str} dicts.
    """
    lines = section_text.splitlines()
    block_starts: list[int] = []

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if s.startswith(('•', '-', '*')):
            continue
        if _is_role_header_line(s):
            block_starts.append(i)

    if len(block_starts) < 2:
        return []

    blocks: list[dict] = []
    for i, start in enumerate(block_starts):
        end = block_starts[i + 1] if i + 1 < len(block_starts) else len(lines)
        block_lines = lines[start:end]
        while block_lines and not block_lines[-1].strip():
            block_lines.pop()
        label = lines[start].strip()
        text = '\n'.join(block_lines).strip()
        if text:
            blocks.append({'label': label, 'text': text})

    return blocks


def _detect_experience_by_date_ranges(section_text: str) -> list[dict]:
    """
    Fallback experience entry detector using date-range lines as block anchors.

    Algorithm:
      1. Find every line that contains a date range (e.g. "2020 – Present").
      2. For each such line, look back up to 3 non-empty, non-bullet lines to
         find the company/role header that precedes the date.
      3. Use the identified header line as the block start.
      4. Split the section text into blocks at those start positions.

    This handles resumes where company names appear on their own line (not matched
    by the all-caps Pattern 3), e.g.:

        Acme Corp
        Product Manager  |  Remote  |  Jan 2022 – Present
        • Led a team of 12…

    Returns list of {'label': str, 'text': str} dicts, same shape as
    _detect_sub_entries.
    """
    if not section_text.strip():
        return []

    section_text = _normalize_experience_section_text(section_text)
    lines = section_text.splitlines()

    # Collect indices of lines that are date-range anchors (not bullet false positives)
    date_line_indices: list[int] = []
    for i, line in enumerate(lines):
        if _is_experience_date_anchor_line(line):
            date_line_indices.append(i)

    if len(date_line_indices) < 2:
        # Only one date range means we can't split into multiple blocks
        return []

    # For each date-range line, walk back to find the topmost header line.
    # Walk backward: stop at a blank line, a bullet, or another date range.
    # Update block_start on every valid header line so the topmost company name
    # line (e.g. company name alone) becomes the start even when a role title sits
    # between it and the date line.
    block_starts: list[int] = []
    for date_idx in date_line_indices:
        block_start = date_idx
        for back in range(1, 6):
            candidate_idx = date_idx - back
            if candidate_idx < 0:
                break
            candidate = lines[candidate_idx].strip()
            if not candidate:
                break  # blank line separates entries — stop here
            if candidate.startswith(('•', '-', '*')):
                break  # bullet from previous block — stop (not '–'/'—': those appear mid-line in role headers)
            if _DATE_RANGE_LINE_RE.search(candidate):
                break  # another date range — this belongs to a different entry
            # Valid non-bullet, non-date, non-blank header line
            block_start = candidate_idx  # keep walking back to the topmost line

        # Deduplicate: only append if it advances past the previous start
        if not block_starts or block_start > block_starts[-1]:
            block_starts.append(block_start)

    if len(block_starts) < 2:
        return []

    blocks: list[dict] = []
    for i, start in enumerate(block_starts):
        end = block_starts[i + 1] if i + 1 < len(block_starts) else len(lines)
        block_lines = lines[start:end]
        # Trim trailing blank lines
        while block_lines and not block_lines[-1].strip():
            block_lines.pop()
        label = lines[start].strip()
        text = '\n'.join(block_lines).strip()
        if text:
            blocks.append({'label': label, 'text': text})

    return blocks


def _detect_sub_entries(section_text: str, section_type: str) -> list[dict]:
    """
    Detects sub-entries within a section block using type-specific patterns.
    Returns list of {label, text} dicts.
    section_type: 'experience' | 'education' | 'certifications' | 'projects'

    For 'experience', falls back to date-range based detection when the primary
    regex patterns detect fewer than 2 entries (handles mixed-case company names
    that don't match all-caps Pattern 3).
    """
    if not section_text.strip():
        return []

    lines = section_text.splitlines()

    if section_type == 'certifications':
        cert_entries: list[dict] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            for pat in _CERT_PATTERNS:
                if re.search(pat, stripped):
                    cert_entries.append({'label': stripped, 'text': stripped})
                    break
        return cert_entries

    if section_type == 'experience':
        patterns = _COMPANY_BLOCK_PATTERNS
    elif section_type == 'education':
        patterns = _DEGREE_PATTERNS
    elif section_type == 'certifications':
        patterns = _CERT_PATTERNS
    elif section_type == 'projects':
        patterns = _PROJECT_PATTERNS
    else:
        return []

    entry_start_indices: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for pat in patterns:
            if re.search(pat, stripped):
                # Avoid double-counting lines very close together
                if entry_start_indices and i - entry_start_indices[-1] < 2:
                    break
                entry_start_indices.append(i)
                break

    if not entry_start_indices:
        primary_blocks: list[dict] = []
    else:
        primary_blocks = []
        for idx, start in enumerate(entry_start_indices):
            end = entry_start_indices[idx + 1] if idx + 1 < len(entry_start_indices) else len(lines)
            block_lines = lines[start:end]
            label = lines[start].strip()
            text = '\n'.join(block_lines).strip()
            if text:
                primary_blocks.append({'label': label, 'text': text})

    if section_type == 'experience':
        fallback_date = _detect_experience_by_date_ranges(section_text)
        fallback_role = _detect_experience_by_role_headers(section_text)
        best = primary_blocks
        if len(fallback_date) > len(best):
            best = fallback_date
        if len(fallback_role) > len(best):
            best = fallback_role
        return best

    if not primary_blocks:
        return []

    return primary_blocks


def _labels_overlap(a: str, b: str) -> bool:
    """True if two label strings share enough tokens to be the same entry."""
    stopwords = {
        # Locations only — do NOT include role titles
        "india", "remote", "hybrid", "onsite",
        "bangalore", "bengaluru", "mumbai", "delhi",
        "hyderabad", "chennai", "pune", "gurugram", "noida",
        # Structural filler only
        "company", "experience", "via", "consulting", "engagement",
        "present", "current",
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


def _normalize_entry_text(text: str) -> str:
    """Normalize entry text for duplicate and containment checks."""
    return re.sub(r'\s+', ' ', str(text).lower()).strip()


def _dedupe_entries(entries: list[dict]) -> list[dict]:
    """Remove duplicate section sub_entries while preserving first occurrence."""
    seen: set[str] = set()
    deduped: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = _normalize_entry_text(entry.get('verbatim_text') or entry.get('label') or '')
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _block_already_present(block: dict, existing_entries: list[dict]) -> bool:
    """True when a detected raw block is already represented in sub_entries."""
    block_label = block.get('label', '')
    block_text = _normalize_entry_text(block.get('text', ''))

    for entry in existing_entries:
        entry_label = entry.get('label', '')
        entry_text = _normalize_entry_text(entry.get('verbatim_text', ''))
        if block_text and entry_text and (block_text in entry_text or entry_text in block_text):
            return True
        if _labels_overlap(block_label, entry_label):
            return True
    return False


# Minimum ratio of A1 verbatim length vs regex-detected block (below → truncated).
_TRUNCATION_LENGTH_RATIO = 0.72


def _find_matching_detected_block(
    entry: dict,
    detected_blocks: list[dict],
) -> dict | None:
    """Best regex block for an A1 sub_entry (label overlap + text containment)."""
    entry_label = entry.get('label', '')
    entry_text = _normalize_entry_text(entry.get('verbatim_text', ''))
    best: dict | None = None
    best_score = -1

    for block in detected_blocks:
        block_label = block.get('label', '')
        block_text = _normalize_entry_text(block.get('text', ''))
        if not block_text:
            continue
        score = 0
        if _labels_overlap(entry_label, block_label):
            score += 50
        if entry_text and block_text:
            if entry_text == block_text:
                score += 100
            elif entry_text in block_text:
                score += 80
            elif block_text in entry_text:
                score += 40
        if score > best_score:
            best_score = score
            best = block
    return best if best_score >= 50 else None


def _entry_looks_truncated(verbatim: str, block_text: str) -> bool:
    """True when A1 verbatim is clearly shorter than the source block."""
    if not verbatim or not block_text:
        return False
    if '...' in verbatim or '…' in verbatim:
        return True
    v_norm = _normalize_entry_text(verbatim)
    b_norm = _normalize_entry_text(block_text)
    if not v_norm or not b_norm:
        return False
    if len(v_norm) < len(b_norm) * _TRUNCATION_LENGTH_RATIO:
        return True
    if v_norm in b_norm and len(b_norm) - len(v_norm) > 40:
        return True
    return False


def _repair_truncated_sub_entries(
    existing_entries: list[dict],
    detected_blocks: list[dict],
    section_name: str,
) -> tuple[list[dict], list[str]]:
    """
    Replace A1 sub_entries that are truncated vs regex-detected raw blocks.

    A1 is still preferred when complete; regex is used only to recover missing text.
    """
    anomalies: list[str] = []
    if not existing_entries or not detected_blocks:
        return existing_entries, anomalies

    repaired: list[dict] = []
    for entry in existing_entries:
        if not isinstance(entry, dict):
            continue
        verbatim = str(entry.get('verbatim_text') or '')
        match = _find_matching_detected_block(entry, detected_blocks)
        if match and _entry_looks_truncated(verbatim, str(match.get('text') or '')):
            block_text = str(match['text'])
            label = str(entry.get('label') or match.get('label') or '')
            anomalies.append(
                f"{section_name}: truncated sub_entry '{label[:50]}' "
                f"({len(verbatim)} chars) — replaced with detected block "
                f"({len(block_text)} chars)"
            )
            logging.warning(
                "ResumeUnderstandingValidator: %s entry '%s' truncated "
                "(%d vs %d chars) — using regex block",
                section_name,
                label[:50],
                len(verbatim),
                len(block_text),
            )
            repaired.append({**entry, 'verbatim_text': block_text})
        else:
            repaired.append(entry)

    return repaired, anomalies


# ─────────────────────────────────────────────
# Skills-specific checks
# ─────────────────────────────────────────────

def _skill_like_tokens(text: str, min_len: int = 3) -> list[str]:
    """Comma/line-separated tokens that look like skills or tools (persona-agnostic)."""
    return [
        t.strip() for t in re.split(r'[,\n|•\-]+', text)
        if len(t.strip()) >= min_len
        and not t.strip().isdigit()
        and re.match(r'^[A-Za-z]', t.strip())
    ]


# Common skills category headers seen in Indian resumes
_SKILLS_CATEGORY_HEADERS = re.compile(
    r'(?i)^(languages?|frontend|backend|databases?|cloud|tools?|frameworks?'
    r'|platforms?|devops|mobile|testing|others?|core\s+skills?|tech\s+stack'
    r'|programming|infrastructure|architect)\s*:',
    re.MULTILINE
)

def _validate_skills_section(
    section_text: str,
    tech_stack_from_a1: list[str],
) -> list[str]:
    """
    Returns list of anomaly descriptions for the skills section.
    Checks:
    1. full_text non-empty
    2. At least 3 skills visible in text
    3. Each tech in A1.tech_stack appears somewhere in skills full_text
       (catches A1 inventing skills not in the resume)
    """
    anomalies = []

    if not section_text.strip():
        anomalies.append("skills: full_text is empty despite section being present")
        return anomalies

    skill_tokens = _skill_like_tokens(section_text, min_len=3)
    if len(skill_tokens) < 3:
        anomalies.append(
            f"skills: only {len(skill_tokens)} skill tokens detected in full_text — "
            "text may be truncated"
        )

    # Cross-check A1.tech_stack items appear in skills text
    skills_lower = section_text.lower()
    phantom_skills = [
        tech for tech in tech_stack_from_a1
        if tech.lower() not in skills_lower
    ]
    if phantom_skills:
        anomalies.append(
            f"skills: A1.tech_stack contains items not found in skills text "
            f"(possible hallucination): {phantom_skills}"
        )

    return anomalies


# ─────────────────────────────────────────────
# Summary-specific checks
# ─────────────────────────────────────────────

def _validate_summary_section(section_text: str) -> list[str]:
    """
    Returns anomaly descriptions for summary section.
    Checks:
    1. full_text non-empty when has_summary=True
    2. Minimum length (at least 50 chars to be a real summary)
    3. Not just the candidate's name repeated (common parse failure)
    """
    anomalies = []

    if not section_text.strip():
        anomalies.append(
            "summary: full_text is empty but has_summary=True — "
            "summary text was likely merged into another section by parser"
        )
        return anomalies

    if len(section_text.strip()) < 50:
        anomalies.append(
            f"summary: full_text is only {len(section_text.strip())} chars — "
            "likely truncated or mis-parsed"
        )

    return anomalies


# ─────────────────────────────────────────────
# Awards-specific checks
# ─────────────────────────────────────────────

_AWARD_LINE_PATTERN = re.compile(
    r'(?i)(award|achiev|recogni|winner|champion|rank|topper|merit|honour|honor'
    r'|scholarship|fellow|best|gold|silver|national|state|district)',
)

def _validate_awards_section(
    section_text: str,
    resume_text: str,
) -> tuple[str, list[str]]:
    """
    Returns (repaired_full_text, anomalies).
    Checks:
    1. full_text non-empty when awards header detected
    2. Detects award lines in resume_text that may have been missed
    """
    anomalies = []

    detected_sections = _extract_all_sections_from_text(resume_text)
    raw_awards_text = detected_sections.get('awards', '')

    if not section_text.strip() and raw_awards_text:
        anomalies.append(
            "awards: A1 returned empty full_text but awards section detected in resume"
        )
        return raw_awards_text, anomalies

    if section_text.strip() and raw_awards_text:
        # Check A1 text is at least 60% of what we detected
        if len(section_text.strip()) < len(raw_awards_text) * 0.6:
            anomalies.append(
                f"awards: A1 full_text ({len(section_text)} chars) appears truncated "
                f"vs detected ({len(raw_awards_text)} chars) — using detected text"
            )
            return raw_awards_text, anomalies

    return section_text, anomalies


# ─────────────────────────────────────────────
# Experience-specific checks
# ─────────────────────────────────────────────

_EXPERIENCE_HEADER_LINE_RE = re.compile(
    r"""
    (?:\+\d[\d\s\-]{9,}\d)   # phone with country code
    |(?:\b\d{10,}\b)          # bare phone
    |@                         # email
    |linkedin\.com
    |github\.com
    |medium\.com
    |gmail\.com
    """,
    re.IGNORECASE | re.VERBOSE,
)

_EXPERIENCE_BULLET_RE = re.compile(r"(?m)^[\s]*[•\-\*·●]\s")


def _strip_resume_header_lines_from_verbatim(verbatim: str) -> str:
    """Remove contact/header lines mistakenly included in an experience entry."""
    lines = verbatim.splitlines()
    kept: list[str] = []
    stripped_header = False
    for line in lines:
        if not line.strip():
            if kept:
                kept.append(line)
            continue
        if not kept and _EXPERIENCE_HEADER_LINE_RE.search(line):
            stripped_header = True
            continue
        kept.append(line)
    result = "\n".join(kept).strip()
    if stripped_header and not result:
        return ""
    return result


def _experience_entry_has_structure(verbatim: str) -> bool:
    """True when verbatim looks like a real experience block, not a stray fragment."""
    text = verbatim.strip()
    if not text:
        return False
    if _DATE_RANGE_RE.search(text):
        return True
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if "|" in first_line:
        return True
    if _EXPERIENCE_BULLET_RE.search(text):
        return True
    return False


def _validate_experience_section(
    section_data: dict,
) -> tuple[dict, list[str]]:
    """
    Repair experience sub_entries before they are finalized.

    - Strip resume header lines (phone, email, LinkedIn) from verbatim_text
    - Drop entries that become empty after stripping
    - Merge bullet-continuation fragments into the preceding entry
    """
    anomalies: list[str] = []
    entries = section_data.get("sub_entries") or []
    if not entries:
        return section_data, anomalies

    cleaned: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "")
        verbatim = _strip_resume_header_lines_from_verbatim(
            str(entry.get("verbatim_text") or "")
        )
        if not verbatim:
            anomalies.append(
                f"experience: dropped header ghost entry '{label[:50]}'"
            )
            continue
        cleaned.append({**entry, "verbatim_text": verbatim})

    merged: list[dict] = []
    for entry in cleaned:
        verbatim = entry.get("verbatim_text", "")
        if not _experience_entry_has_structure(verbatim) and merged:
            prev = merged[-1]
            prev_text = str(prev.get("verbatim_text") or "").rstrip()
            frag = str(verbatim).strip()
            prev["verbatim_text"] = f"{prev_text}\n{frag}" if prev_text else frag
            anomalies.append(
                f"experience: merged fragment into '{str(prev.get('label', ''))[:40]}'"
            )
            continue
        merged.append(dict(entry))

    section_data = dict(section_data)
    section_data["sub_entries"] = _dedupe_entries(merged)
    section_data["full_text"] = "\n\n".join(
        e.get("verbatim_text", "")
        for e in section_data["sub_entries"]
        if e.get("verbatim_text")
    )
    return section_data, anomalies


# ─────────────────────────────────────────────
# Education-specific checks
# ─────────────────────────────────────────────

def _validate_education_section(
    section_data: dict,
    resume_text: str,
) -> tuple[dict, list[str]]:
    """
    Returns (repaired_section_data, anomalies).
    Checks:
    1. sub_entries count matches detected degree blocks
    2. full_text completeness
    3. Graduation year plausibility (not in future, not before 1970)
    """
    anomalies = []
    detected_sections = _extract_all_sections_from_text(resume_text)
    raw_edu_text = detected_sections.get('education', '')

    existing_entries = _dedupe_entries(section_data.get('sub_entries', []))

    # Detect degree blocks from raw text
    detected_blocks = _detect_sub_entries(raw_edu_text, 'education')

    if existing_entries and detected_blocks:
        existing_entries, trunc_anomalies = _repair_truncated_sub_entries(
            existing_entries, detected_blocks, 'education',
        )
        anomalies.extend(trunc_anomalies)

    missing_blocks = []
    for block in detected_blocks:
        if not _block_already_present(block, existing_entries):
            missing_blocks.append(block)

    if missing_blocks:
        anomalies.append(
            f"education: A1 missing {len(missing_blocks)} degree entries: "
            f"{[b['label'][:60] for b in missing_blocks]}"
        )
        for block in missing_blocks:
            existing_entries.append({
                'label': block['label'],
                'verbatim_text': block['text'],
            })
    section_data['sub_entries'] = _dedupe_entries(existing_entries)

    # full_text completeness
    if raw_edu_text and not section_data.get('full_text', '').strip():
        anomalies.append("education: full_text empty — injecting from detected text")
        section_data['full_text'] = raw_edu_text
    elif raw_edu_text and len(section_data.get('full_text', '')) < len(raw_edu_text) * 0.5:
        anomalies.append("education: full_text appears truncated — using detected text")
        section_data['full_text'] = raw_edu_text

    # Year plausibility check
    current_year = datetime.datetime.now().year
    all_years_in_edu = [
        int(m) for m in re.findall(r'\b(19\d{2}|20\d{2})\b',
                                    section_data.get('full_text', ''))
    ]
    for yr in all_years_in_edu:
        if yr > current_year:
            anomalies.append(
                f"education: graduation year {yr} is in the future — "
                "likely a parse error"
            )
        elif yr < 1970:
            anomalies.append(
                f"education: year {yr} is implausibly old — likely a parse error"
            )

    return section_data, anomalies


# ─────────────────────────────────────────────
# Certifications-specific checks
# ─────────────────────────────────────────────

def _validate_certifications_section(
    section_data: dict,
    resume_text: str,
) -> tuple[dict, list[str]]:
    """
    Returns (repaired_section_data, anomalies).
    Checks:
    1. sub_entries count matches detected cert blocks
    2. full_text non-empty
    3. Expiry dates not in the past (warning only)
    """
    anomalies = []
    detected_sections = _extract_all_sections_from_text(resume_text)
    raw_cert_text = detected_sections.get('certifications', '')

    existing_entries = _dedupe_entries(section_data.get('sub_entries', []))

    detected_blocks = _detect_sub_entries(raw_cert_text, 'certifications')

    missing_blocks = []
    for block in detected_blocks:
        if not _block_already_present(block, existing_entries):
            missing_blocks.append(block)

    if missing_blocks:
        anomalies.append(
            f"certifications: A1 missing {len(missing_blocks)} cert entries: "
            f"{[b['label'][:60] for b in missing_blocks]}"
        )
        for block in missing_blocks:
            existing_entries.append({
                'label': block['label'],
                'verbatim_text': block['text'],
            })
    section_data['sub_entries'] = _dedupe_entries(existing_entries)

    # full_text completeness
    if raw_cert_text and not section_data.get('full_text', '').strip():
        anomalies.append("certifications: full_text empty — injecting from detected text")
        section_data['full_text'] = raw_cert_text

    # Expiry date warning (certs expiring > 3 years ago are stale)
    current_year = datetime.datetime.now().year
    cert_full = section_data.get('full_text', '')
    expiry_matches = re.findall(r'(?i)expir\w*\s*:?\s*(20\d{2})', cert_full)
    for yr_str in expiry_matches:
        yr = int(yr_str)
        if yr < current_year - 3:
            anomalies.append(
                f"certifications: cert expired {current_year - yr} years ago ({yr}) — "
                "flag for user review"
            )

    return section_data, anomalies


# ─────────────────────────────────────────────
# Projects-specific checks
# ─────────────────────────────────────────────

def _validate_projects_section(
    section_data: dict,
    resume_text: str,
) -> tuple[dict, list[str]]:
    """
    Returns (repaired_section_data, anomalies).
    Checks:
    1. sub_entries count matches detected project blocks
    2. full_text non-empty
    3. Each project has at least one tech stack mention
    """
    anomalies = []
    detected_sections = _extract_all_sections_from_text(resume_text)
    raw_proj_text = detected_sections.get('projects', '')

    existing_entries = _dedupe_entries(section_data.get('sub_entries', []))

    detected_blocks = _detect_sub_entries(raw_proj_text, 'projects')

    if existing_entries and detected_blocks:
        existing_entries, trunc_anomalies = _repair_truncated_sub_entries(
            existing_entries, detected_blocks, 'projects',
        )
        anomalies.extend(trunc_anomalies)

    missing_blocks = []
    for block in detected_blocks:
        if not _block_already_present(block, existing_entries):
            missing_blocks.append(block)

    if missing_blocks:
        anomalies.append(
            f"projects: A1 missing {len(missing_blocks)} project entries: "
            f"{[b['label'][:60] for b in missing_blocks]}"
        )
        for block in missing_blocks:
            existing_entries.append({
                'label': block['label'],
                'verbatim_text': block['text'],
            })
    section_data['sub_entries'] = _dedupe_entries(existing_entries)

    # full_text completeness
    if raw_proj_text and not section_data.get('full_text', '').strip():
        anomalies.append("projects: full_text empty — injecting from detected text")
        section_data['full_text'] = raw_proj_text

    # Delimited skill/tool tokens in each project (warning only)
    for entry in section_data.get('sub_entries', []):
        if len(_skill_like_tokens(entry.get('verbatim_text', ''), min_len=2)) < 2:
            anomalies.append(
                f"projects: entry '{entry.get('label', '')[:40]}' has few skill/tool "
                "tokens — user should add technologies or tools used"
            )

    return section_data, anomalies


# ─────────────────────────────────────────────
# Flat section checks (awards, publications, extracurriculars)
# ─────────────────────────────────────────────

def _validate_flat_section(
    section_name: str,
    section_data: dict,
    resume_text: str,
) -> tuple[dict, list[str]]:
    """
    For sections with no sub_entries structure (awards, publications, extracurriculars).
    Checks full_text completeness only.
    """
    anomalies = []
    detected_sections = _extract_all_sections_from_text(resume_text)
    raw_text = detected_sections.get(section_name, '')

    current_text = section_data.get('full_text', '') if isinstance(section_data, dict) else ''

    if raw_text and not current_text.strip():
        anomalies.append(
            f"{section_name}: full_text empty but section detected — injecting"
        )
        if isinstance(section_data, dict):
            section_data['full_text'] = raw_text
        else:
            section_data = {'header': section_name, 'full_text': raw_text, 'sub_entries': []}

    elif raw_text and len(current_text.strip()) < len(raw_text.strip()) * 0.5:
        anomalies.append(
            f"{section_name}: full_text appears truncated "
            f"({len(current_text)} vs {len(raw_text)} detected chars) — using detected"
        )
        if isinstance(section_data, dict):
            section_data['full_text'] = raw_text

    return section_data, anomalies


# ─────────────────────────────────────────────
# Main validator class
# ─────────────────────────────────────────────

class ResumeUnderstandingValidator:
    """
    Validates and repairs A1 (ResumeUnderstanding) output for ALL sections.

    Runs all section-specific checks in sequence.
    Zero LLM calls. All fixes use data already in resume_text.

    Usage:
        validator = ResumeUnderstandingValidator()
        repaired = validator.validate_and_fix(a1_output, resume_text)
    """

    def validate_and_fix(
        self,
        a1_output: dict[str, Any],
        resume_text: str,
    ) -> dict[str, Any]:
        """
        Entry point. Runs all section validators and returns repaired A1 output.

        Args:
            a1_output: Raw dict returned by ResumeUnderstandingAgent.run()
            resume_text: Full cleaned resume text from parser.py

        Returns:
            Repaired dict. If all checks pass, returns input unchanged.
        """
        output = dict(a1_output)
        sections = _coerce_sections(
            output.get('resume_sections') or output.get('sections') or {}
        )
        all_anomalies: list[str] = []

        # ── 1. EXPERIENCE ─────────────────────────────────────────────
        exp_data = sections.get('experience', _empty_section('experience'))
        if isinstance(exp_data, dict):
            detected_sections_raw = _extract_all_sections_from_text(resume_text)
            raw_exp_text = detected_sections_raw.get('experience', '')
            if not raw_exp_text.strip():
                raw_exp_text = resume_text
            detected_blocks = _detect_sub_entries(raw_exp_text, 'experience')
            existing_entries = _dedupe_entries(exp_data.get('sub_entries', []))

            logging.info(
                "ResumeUnderstandingValidator: experience A1=%d blocks, "
                "detected=%d from raw text",
                len(existing_entries),
                len(detected_blocks),
            )

            # A1 is the source of truth — it used an LLM to extract sub_entries.
            # Regex (_detect_sub_entries) is only a fallback for when A1 failed.
            if len(existing_entries) > 0:
                # A1 is source of truth when complete; repair truncation from raw blocks.
                existing_entries, trunc_anomalies = _repair_truncated_sub_entries(
                    existing_entries, detected_blocks, 'experience',
                )
                all_anomalies.extend(trunc_anomalies)
                if len(detected_blocks) != len(existing_entries):
                    all_anomalies.append(
                        f"experience: A1={len(existing_entries)} entries, "
                        f"regex={len(detected_blocks)} — keeping A1 (source of truth)"
                    )
            else:
                # A1 returned 0 entries — it failed. Fall back to regex.
                if detected_blocks:
                    all_anomalies.append(
                        f"experience: A1 returned 0 entries — "
                        f"falling back to regex ({len(detected_blocks)} blocks found)"
                    )
                    existing_entries = [
                        {'label': b['label'], 'verbatim_text': b['text']}
                        for b in detected_blocks
                    ]
                else:
                    all_anomalies.append(
                        "experience: both A1 and regex returned 0 entries — "
                        "section may be missing or unparseable"
                    )

            exp_data['sub_entries'] = _dedupe_entries(existing_entries)
            exp_data, exp_anomalies = _validate_experience_section(exp_data)
            all_anomalies.extend(exp_anomalies)
            sections['experience'] = exp_data

        # ── 2. EDUCATION ──────────────────────────────────────────────
        edu_data = sections.get('education', _empty_section('education'))
        if isinstance(edu_data, dict):
            edu_data, anomalies = _validate_education_section(edu_data, resume_text)
            all_anomalies.extend(anomalies)
            sections['education'] = edu_data

        # ── 3. CERTIFICATIONS ─────────────────────────────────────────
        cert_data = sections.get('certifications', _empty_section('certifications'))
        if isinstance(cert_data, dict):
            cert_data, anomalies = _validate_certifications_section(cert_data, resume_text)
            all_anomalies.extend(anomalies)
            sections['certifications'] = cert_data

        # ── 4. PROJECTS ───────────────────────────────────────────────
        proj_data = sections.get('projects', _empty_section('projects'))
        if isinstance(proj_data, dict):
            proj_data, anomalies = _validate_projects_section(proj_data, resume_text)
            all_anomalies.extend(anomalies)
            sections['projects'] = proj_data

        # ── 5. SKILLS ─────────────────────────────────────────────────
        skills_data = sections.get('skills', _empty_section('skills'))
        skills_text = skills_data.get('full_text', '') if isinstance(skills_data, dict) else ''
        tech_stack = output.get('tech_stack', [])
        skills_anomalies = _validate_skills_section(skills_text, tech_stack)

        if skills_anomalies:
            all_anomalies.extend(skills_anomalies)
            # If full_text empty, inject from raw detected
            detected_secs = _extract_all_sections_from_text(resume_text)
            raw_skills = detected_secs.get('skills', '')
            if not skills_text.strip() and raw_skills:
                if isinstance(skills_data, dict):
                    skills_data['full_text'] = raw_skills
                else:
                    skills_data = {'header': 'skills', 'full_text': raw_skills, 'sub_entries': []}
                sections['skills'] = skills_data

        # ── 6. SUMMARY ────────────────────────────────────────────────
        summary_data = sections.get('summary', _empty_section('summary'))
        summary_text = summary_data.get('full_text', '') if isinstance(summary_data, dict) else ''
        has_summary = output.get('has_summary', False)

        if has_summary:
            summary_anomalies = _validate_summary_section(summary_text)
            if summary_anomalies:
                all_anomalies.extend(summary_anomalies)
                detected_secs = _extract_all_sections_from_text(resume_text)
                raw_summary = detected_secs.get('summary', '')
                if not summary_text.strip() and raw_summary:
                    if isinstance(summary_data, dict):
                        summary_data['full_text'] = raw_summary
                    else:
                        summary_data = {'header': 'summary', 'full_text': raw_summary, 'sub_entries': []}
                    sections['summary'] = summary_data

        # ── 7. AWARDS ─────────────────────────────────────────────────
        awards_data = sections.get('awards', _empty_section('awards'))
        if isinstance(awards_data, dict):
            awards_text = awards_data.get('full_text', '')
            repaired_text, anomalies = _validate_awards_section(awards_text, resume_text)
            if anomalies:
                all_anomalies.extend(anomalies)
                awards_data['full_text'] = repaired_text
                sections['awards'] = awards_data

        # ── 8. PUBLICATIONS ───────────────────────────────────────────
        pub_data = sections.get('publications', _empty_section('publications'))
        if isinstance(pub_data, dict):
            pub_data, anomalies = _validate_flat_section('publications', pub_data, resume_text)
            all_anomalies.extend(anomalies)
            sections['publications'] = pub_data

        # ── 9. EXTRACURRICULARS ───────────────────────────────────────
        extra_data = sections.get('extracurriculars', _empty_section('extracurriculars'))
        if isinstance(extra_data, dict):
            extra_data, anomalies = _validate_flat_section('extracurriculars', extra_data, resume_text)
            all_anomalies.extend(anomalies)
            sections['extracurriculars'] = extra_data

        output['resume_sections'] = sections
        output['sections'] = sections

        # ── 10. SECTIONS_PRESENT cross-check ──────────────────────────
        sections_present = list(output.get('sections_present', []))
        detected_all = _extract_all_sections_from_text(resume_text)
        for detected_name, detected_body in detected_all.items():
            if detected_body.strip() and detected_name not in sections_present:
                all_anomalies.append(
                    f"sections_present: '{detected_name}' detected in resume but missing from list"
                )
                sections_present.append(detected_name)
        output['sections_present'] = sections_present

        # ── 11. EXPERIENCE_YEARS recompute ────────────────────────────
        declared_years = output.get('experience_years', 0)
        if declared_years == 0:
            exp_text_for_dates = sections.get('experience', {})
            exp_text_for_dates = (
                exp_text_for_dates.get('full_text', '')
                if isinstance(exp_text_for_dates, dict) else ''
            )
            matches = _DATE_RANGE_RE.findall(exp_text_for_dates or resume_text)
            all_years: list[int] = []
            current_year = datetime.datetime.now().year
            for m in matches:
                try:
                    all_years.append(int(m[1]))
                    end = m[3]
                    all_years.append(
                        current_year if end.lower() in ('present', 'current')
                        else int(end)
                    )
                except ValueError:
                    pass
            if all_years:
                computed = max(all_years) - min(all_years)
                if computed > 0:
                    all_anomalies.append(
                        f"experience_years=0 but date ranges suggest {computed}y — corrected"
                    )
                    output['experience_years'] = computed

        # ── 12. TECH_STACK non-empty when skills present ──────────────
        if sections.get('skills') and not output.get('tech_stack'):
            skills_full = sections['skills'].get('full_text', '') \
                if isinstance(sections['skills'], dict) else ''
            detected_techs = _skill_like_tokens(skills_full, min_len=2)
            if detected_techs:
                all_anomalies.append(
                    f"tech_stack empty but {len(detected_techs)} techs detected "
                    f"in skills section — injecting"
                )
                output['tech_stack'] = list(dict.fromkeys(detected_techs))  # dedup, preserve order

        # ── Final logging ──────────────────────────────────────────────
        if all_anomalies:
            logging.warning(
                "ResumeUnderstandingValidator: %d anomalies fixed:\n  %s",
                len(all_anomalies),
                '\n  '.join(f"[{i+1}] {a}" for i, a in enumerate(all_anomalies))
            )
        else:
            logging.info("ResumeUnderstandingValidator: all checks passed (0 anomalies)")

        if not output.get("role_family"):
            from backend.few_shot_prompts import detect_role_family

            output["role_family"] = detect_role_family(resume_text)

        return output
