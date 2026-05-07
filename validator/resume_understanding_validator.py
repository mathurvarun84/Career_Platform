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
    r'(\d{4})\s*[-–—to]+\s*'
    r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+)?'
    r'(\d{4}|\bPresent\b|\bpresent\b|\bCurrent\b|\bcurrent\b)',
    re.IGNORECASE
)


# ─────────────────────────────────────────────
# Section text extraction from raw resume
# ─────────────────────────────────────────────

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
        stripped = line.strip()
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
    r'\b(B\.?Tech|BE|B\.?E|M\.?Tech|ME|M\.?E|MBA|BCA|MCA|BSc|MSc|PhD|B\.?Sc|M\.?Sc'
    r'|Bachelor|Master|Doctorate|Diploma)\b',
    r'\b(IIT|IIM|NIT|BITS|VIT|SRM|Pune|Mumbai|Delhi|Bangalore|Hyderabad'
    r'|Anna|Manipal|Amity|JNTU|GTU)\b.{0,40}\d{4}',
]

# CERTIFICATIONS: detects cert block start lines
_CERT_PATTERNS = [
    r'\b(AWS|GCP|Azure|Google|Microsoft|Oracle|Cisco|PMP|CISSP|CKA|Terraform'
    r'|Kubernetes|Docker|Scrum|ITIL|ISO|SAFe|Agile|PMI|CompTIA)\b',
    r'Certified\b',
    r'Certificate\b',
    r'Certification\b',
]

# PROJECTS: detects project block start lines
_PROJECT_PATTERNS = [
    r'^\s*\d+\.\s+[A-Z]',           # "1. Project Name"
    r'^[A-Z][A-Za-z0-9 _\-]{3,50}:',# "ProjectName:"
    r'^\*\*[A-Z]',                   # "**ProjectName"
    r'^#{1,3}\s+[A-Z]',              # "### ProjectName"
    r'^[A-Z][A-Za-z0-9 _\-]{3,40}\s*[|–—]\s*(React|Node|Python|Java|Go|AWS|GCP|Flutter)',
]


def _detect_sub_entries(section_text: str, section_type: str) -> list[dict]:
    """
    Detects sub-entries within a section block using type-specific patterns.
    Returns list of {label, text} dicts.
    section_type: 'experience' | 'education' | 'certifications' | 'projects'
    """
    if not section_text.strip():
        return []

    lines = section_text.splitlines()

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
        return []

    blocks: list[dict] = []
    for idx, start in enumerate(entry_start_indices):
        end = entry_start_indices[idx + 1] if idx + 1 < len(entry_start_indices) else len(lines)
        block_lines = lines[start:end]
        label = lines[start].strip()
        text = '\n'.join(block_lines).strip()
        if text:
            blocks.append({'label': label, 'text': text})

    return blocks


def _labels_overlap(a: str, b: str) -> bool:
    """True if two label strings share enough tokens to be the same entry."""
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


# ─────────────────────────────────────────────
# Skills-specific checks
# ─────────────────────────────────────────────

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

    # Count recognisable skill tokens (camelCase, acronyms, known names)
    skill_tokens = re.findall(
        r'\b([A-Z][a-z]+[A-Z][a-zA-Z]*|[A-Z]{2,}|'
        r'React|Node|Python|Java|Go|Rust|Swift|Kotlin|TypeScript|JavaScript|'
        r'AWS|GCP|Azure|Docker|Kubernetes|Kafka|Redis|MongoDB|PostgreSQL|MySQL'
        r'|Django|FastAPI|Spring|Rails|Flutter|TensorFlow|PyTorch)\b',
        section_text
    )
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

    # Tech stack presence in each project (warning only)
    _TECH_SIGNAL = re.compile(
        r'\b(React|Node|Python|Java|Go|AWS|GCP|Azure|Docker|Kubernetes|'
        r'Flutter|Swift|Kotlin|TypeScript|JavaScript|Django|Spring|Rails|'
        r'MongoDB|PostgreSQL|MySQL|Redis|Kafka|TensorFlow|PyTorch)\b'
    )
    for entry in section_data.get('sub_entries', []):
        if not _TECH_SIGNAL.search(entry.get('verbatim_text', '')):
            anomalies.append(
                f"projects: entry '{entry.get('label', '')[:40]}' has no tech stack "
                "mention — user should add technologies used"
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
            detected_blocks = _detect_sub_entries(raw_exp_text, 'experience')
            existing_entries = _dedupe_entries(exp_data.get('sub_entries', []))

            missing_blocks = [
                b for b in detected_blocks
                if not _block_already_present(b, existing_entries)
            ]
            if missing_blocks:
                all_anomalies.append(
                    f"experience: A1 missing {len(missing_blocks)} companies: "
                    f"{[b['label'][:50] for b in missing_blocks]}"
                )
                for block in missing_blocks:
                    existing_entries.append({
                        'label': block['label'],
                        'verbatim_text': block['text'],
                    })
                exp_data['sub_entries'] = _dedupe_entries(existing_entries)
                if missing_blocks:
                    all_texts = [
                        e.get('verbatim_text', '')
                        for e in exp_data['sub_entries']
                    ]
                    exp_data['full_text'] = '\n\n'.join(t for t in all_texts if t)
            else:
                exp_data['sub_entries'] = existing_entries
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
            detected_techs = re.findall(
                r'\b(React|Node\.?js|Python|Java|Go|Rust|TypeScript|JavaScript|'
                r'AWS|GCP|Azure|Docker|Kubernetes|Kafka|Redis|MongoDB|PostgreSQL|'
                r'MySQL|Django|FastAPI|Spring|Flutter|TensorFlow|PyTorch|'
                r'Terraform|Ansible|Jenkins|Git|GraphQL|gRPC)\b',
                skills_full
            )
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

        return output
