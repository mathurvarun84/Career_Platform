"""
Resume file parser - PDF, DOCX, and TXT to plain text.
"""

import os
import re
from typing import Any, Dict, List


def parse_resume(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        raw_text = _parse_pdf(file_path)
    elif ext == ".docx":
        raw_text = _parse_docx(file_path)
    elif ext == ".txt":
        raw_text = _parse_txt(file_path)
    else:
        raise ValueError(f"Unsupported format: {ext}")

    return raw_text


def _build_structured_resume(text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    section_blocks = _extract_section_blocks(text)

    raw_name = lines[0] if lines else ""
    name = _normalize_spaced_heading(raw_name)
    contact = _extract_contact_line(lines[1:6]) if len(lines) > 1 else ""
    title = ""
    if len(lines) > 1 and lines[1] != contact:
        title = lines[1]

    return {
        "name": name,
        "title": title,
        "contact": contact,
        "summary": _strip_contact_artifacts(section_blocks.get("summary", "")),
        "skills": section_blocks.get("skills", ""),
        "experience": _parse_experience_entries(section_blocks.get("experience", "")),
        "education": _parse_education_entries(section_blocks.get("education", "")),
        "certifications": _parse_simple_list(section_blocks.get("certifications", "")),
        "awards": _parse_simple_list(section_blocks.get("awards", "")),
    }


def _parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file with word-boundary-aware reconstruction.

    Uses pdfplumber's extract_words() as the primary method to avoid the
    character-concatenation problem that occurs with tightly-kerned PDFs
    (e.g. 'Servingasasoftwareengineerforthe'). Falls back to extract_text()
    if no words are detected, then to OCR as a last resort.
    """
    import pdfplumber

    texts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = _extract_page_text(page)
            if page_text:
                texts.append(page_text)

    extracted_text = _clean_text("\n".join(texts))
    if _is_text_meaningful(extracted_text):
        return extracted_text
    return _parse_pdf_ocr(file_path)


def _extract_page_text(page) -> str:
    """Reconstruct a single PDF page's text preserving line breaks.

    Calls extract_words() to get bounding-box-aware word tokens, then groups
    them into lines by their vertical (top) coordinate. Characters that share
    a y-position within Y_TOLERANCE points are treated as the same line.
    Falls back to extract_text() if no words are found.
    """
    Y_TOLERANCE = 5  # points; lines within this vertical distance are merged

    # x_tolerance=2: word gaps in tightly-kerned PDFs are ~2.4 pts while
    # intra-word kerning gaps are 0–0.2 pts.  Default of 3 merges entire
    # lines into one token; 2 correctly splits at word boundaries.
    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=True,
    )

    if not words:
        return page.extract_text() or ""

    lines: list[list[str]] = []
    line_tops: list[float] = []

    for word in words:
        top = word["top"]
        # Find an existing line whose top is within Y_TOLERANCE
        matched = False
        for i, line_top in enumerate(line_tops):
            if abs(top - line_top) <= Y_TOLERANCE:
                lines[i].append(word["text"])
                matched = True
                break
        if not matched:
            lines.append([word["text"]])
            line_tops.append(top)

    return "\n".join(" ".join(line_words) for line_words in lines)


def _is_text_meaningful(text: str) -> bool:
    if len(text.strip()) < 100:
        return False
    printable = sum(1 for c in text if c.isprintable())
    total = len(text)
    if printable / total < 0.7:
        return False
    special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    if special_chars / total > 0.3:
        return False
    return True


def _parse_pdf_ocr(file_path: str) -> str:
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(file_path)
    texts = []
    for image in images:
        text = pytesseract.image_to_string(image)
        if text.strip():
            texts.append(text)
    return _clean_text("\n".join(texts))


def _docx_paragraph_style_name(paragraph) -> str:
    """Return lowercased style name, or empty string when style is unset."""
    style = paragraph.style
    if style is None or style.name is None:
        return ""
    return style.name.lower()


def _docx_paragraph_is_bullet(paragraph) -> bool:
    """True when a DOCX paragraph is a list/bullet line."""
    style_name = _docx_paragraph_style_name(paragraph)
    if "bullet" in style_name or "list" in style_name:
        return True
    p_pr = paragraph._element.pPr
    if p_pr is not None and p_pr.numPr is not None:
        return True
    text = paragraph.text.strip()
    return bool(text) and text[0] in "\u2022\u25cf\u25cb\u2013\u2014-*"


def _parse_docx(file_path: str) -> str:
    from docx import Document

    doc = Document(file_path)
    output_lines: list[str] = []
    prev_was_bullet = False

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            prev_was_bullet = False
            output_lines.append("")
            continue

        is_bullet = _docx_paragraph_is_bullet(p)

        if is_bullet:
            # Skip duplicate when List Bullet repeats preceding Normal paragraph text.
            if output_lines:
                prev = output_lines[-1].strip().lstrip("•").strip()
                if prev.lower() == text.lower():
                    prev_was_bullet = True
                    continue
            output_lines.append("• " + text)
            prev_was_bullet = True
        else:
            is_continuation = (
                prev_was_bullet
                and output_lines
                and text[0].islower()
            )
            if is_continuation:
                output_lines[-1] = output_lines[-1].rstrip() + " " + text
            else:
                output_lines.append(text)
                prev_was_bullet = False

    return _clean_text("\n".join(output_lines))


def _parse_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return _clean_text(f.read())


_COMMON_STANDALONE_WORDS = frozenset({
    "the", "and", "for", "are", "was", "were", "been", "have", "has", "had",
    "not", "but", "you", "your", "our", "can", "will", "may", "new", "york",
    "delhi", "india", "work", "team", "teams", "year", "years", "with", "from",
    "this", "that", "they", "their", "what", "when", "where", "which", "while",
})
_SKIP_AS_RUN_START = _COMMON_STANDALONE_WORDS | frozenset({
    "at", "by", "to", "of", "or", "an", "as",
})


def _should_collapse_split_token_run(tokens: list[str]) -> bool:
    """
    True when a run of short space-separated tokens is a PDF kerning artifact.

    Example: ['Eng', 'in', 'eer', 'in', 'g'] → collapse to 'Engineering'.
    """
    if len(tokens) < 3:
        return False
    # Real phrases rarely contain single-letter tokens; PDF shards do ("g", "t").
    if not any(len(t) == 1 for t in tokens):
        return False
    collapsed = "".join(tokens)
    if len(collapsed) < 5 or not collapsed.isalpha():
        return False
    # Real words are mostly longer tokens; artifacts are 1–3 char shards.
    short_count = sum(1 for t in tokens if len(t) <= 3)
    short_ratio = short_count / len(tokens)
    if short_ratio <= (0.66 if any(len(t) == 1 for t in tokens) else 0.75):
        return False
    avg_len = sum(len(t) for t in tokens) / len(tokens)
    if avg_len > 3.5:
        return False
    if all(t.lower() in _COMMON_STANDALONE_WORDS for t in tokens):
        return False
    # Proper-noun runs: "New York India" — multiple capitalized tokens
    if sum(1 for t in tokens if len(t) >= 4 and t[0].isupper()) >= 2:
        return False
    # Adjacent capitalized words (e.g. "Led Eng") are real phrases, not shards.
    if (
        len(tokens) >= 2
        and len(tokens[0]) >= 3
        and tokens[0][0].isupper()
        and tokens[1][0].isupper()
        and len(tokens[1]) >= 3
    ):
        return False
    return True


def _collapse_split_word_artifacts_in_line(line: str) -> str:
    """Collapse inter-character space artifacts on one line (PDF kerning)."""
    raw_words = line.split()
    if len(raw_words) < 3:
        return line
    # (raw_token, core_alpha) — core strips trailing sentence punctuation.
    words: list[tuple[str, str]] = [
        (w, re.sub(r"[^A-Za-z]+$", "", w)) for w in raw_words
    ]
    out: list[str] = []
    i = 0
    while i < len(words):
        raw, core = words[i]
        if not (core.isalpha() and len(core) <= 6):
            out.append(raw)
            i += 1
            continue
        if core.lower() in _SKIP_AS_RUN_START and (
            len(core) >= 4 or core.lower() in {"at", "by", "to", "of", "or", "an", "as"}
        ):
            out.append(raw)
            i += 1
            continue
        j = i + 1
        while j < len(words):
            _, nxt = words[j]
            if not (nxt.isalpha() and len(nxt) <= 6):
                break
            if len(nxt) >= 4 and nxt.islower():
                # Mid-word shards (e.g. "sacti") may precede short tails ("on s").
                k = j + 1
                while k < len(words) and len(words[k][1]) <= 3 and words[k][1].islower():
                    k += 1
                has_singleton_tail = (
                    k < len(words) and len(words[k][1]) == 1
                ) or (
                    k == len(words) and len(words[-1][1]) == 1
                )
                if not has_singleton_tail:
                    break
            j += 1
        run = [words[k][1] for k in range(i, j)]
        if _should_collapse_split_token_run(run):
            collapsed = "".join(run)
            # Preserve trailing punctuation from the last raw token in the run.
            tail = re.search(r"[^A-Za-z]+$", words[j - 1][0])
            out.append(collapsed + (tail.group(0) if tail else ""))
        else:
            out.extend(raw_words[i:j])
        i = j
    return " ".join(out)


def _collapse_split_word_artifacts(text: str) -> str:
    """Apply per-line collapse for PDF inter-character spacing artifacts."""
    return "\n".join(_collapse_split_word_artifacts_in_line(line) for line in text.splitlines())


def _clean_text(text: str) -> str:
    import re
    # Pass 0: collapse PDF inter-character spacing (before any other transforms)
    text = _collapse_split_word_artifacts(text)
    # Pass 1: rejoin PDF hyphen line-breaks BEFORE anything else
    # "end-to-\ndelivery" → "end-to-delivery"
    text = re.sub(r'([a-zA-Z])-\n([a-zA-Z])', r'\1-\2', text)
    # Pass 2: normalize whitespace per line
    lines = text.splitlines()
    cleaned = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    text = '\n'.join(cleaned)
    # Pass 3: space after commas (fixes "React,Next.js" → "React, Next.js")
    text = re.sub(r',([^\s\n])', r', \1', text)
    # Pass 4: space after colons except URLs
    text = re.sub(r':([^\s/\n])', r': \1', text)
    # Pass 5: fix camelCase on non-bullet, non-tech lines only
    SKIP_PREFIXES = ('-', '•', '*', 'http', 'Tech Stack',
                     'Languages:', 'Frontend:', 'Backend:',
                     'Tools:', 'Database', 'Architecture')
    fixed = []
    for line in text.splitlines():
        s = line.lstrip()
        if any(s.startswith(p) for p in SKIP_PREFIXES):
            fixed.append(line)
        else:
            fixed.append(re.sub(r'([a-z])([A-Z])', r'\1 \2', line))
    text = '\n'.join(fixed)
    # Pass 6: normalize multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Pass 7: tabs → spaces (PDF tables often use tabs between role and dates)
    text = text.replace('\t', ' ')
    # Pass 8: split any residual concatenated words using common English prepositions
    # (catches fallback OCR / extract_text() output where spaces were stripped)
    text = _fix_concatenated_words(text)
    # Pass 9: rejoin soft-wrapped bullet continuation lines
    lines = text.splitlines()
    sentence_enders = (".", "!", "?", ":")
    merged = []
    for line in lines:
        stripped = line.strip()
        is_bullet = stripped.startswith(("•", "-", "*"))
        if merged:
            prev = merged[-1].strip()
            prev_is_bullet = prev.startswith(("•", "-", "*"))
            prev_ends_open = prev and prev[-1] not in sentence_enders
            if (
                stripped
                and not is_bullet
                and prev_is_bullet
                and prev_ends_open
                and (stripped[0].islower() or stripped[0].isdigit())
            ):
                merged[-1] = merged[-1].rstrip() + " " + stripped
                continue
        merged.append(line)
    text = "\n".join(merged)
    return text.strip()


_EMAIL_OR_URL_RE = re.compile(r"@|\.(com|in|io|org|net|co)\b|linkedin|github", re.IGNORECASE)


def _split_runon_token(token: str) -> str:
    """Insert spaces into a single glued token (e.g. Servingasasoftwareengineer)."""
    if len(token) < 20 or " " in token:
        return token
    if _EMAIL_OR_URL_RE.search(token):
        return token
    glued = re.sub(
        r"(?<=[a-z])(of|in|and|for|at|to|with|the|as|by|on|or|an|is|are|was|were)(?=[a-z])",
        r" \1 ",
        token,
        flags=re.IGNORECASE,
    )
    glued = re.sub(r"([a-z])([A-Z])", r"\1 \2", glued)
    return re.sub(r"\s{2,}", " ", glued).strip()


def _fix_concatenated_words(text: str) -> str:
    """Split glued words on every line, including bullet lines."""
    fixed_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        prefix = line[: len(line) - len(stripped)]
        bullet_m = re.match(r"^([\u2022\-\*]\s*)", stripped)
        if bullet_m:
            prefix += bullet_m.group(1)
            stripped = stripped[bullet_m.end() :]

        if stripped.startswith("http"):
            fixed_lines.append(line)
            continue

        words = stripped.split()
        repaired = [_split_runon_token(w) for w in words]
        fixed_lines.append(prefix + " ".join(repaired))
    return "\n".join(fixed_lines)


_KNOWN_SECTION_COLLAPSED = frozenset({
    # Single-word forms of known headings — used by Case 2 below
    'experience', 'workexperience', 'professionalexperience',
    'employmenthistory', 'employment', 'careerhistory', 'workhistory',
    'education', 'academicbackground', 'academics', 'qualifications',
    'academicqualifications', 'skills', 'technicalskills',
    'corecompetencies', 'keyskills', 'competencies', 'technologies',
    'technicalexpertise', 'summary', 'professionalsummary', 'objective',
    'profile', 'about', 'careerobjective', 'certifications',
    'certificates', 'licenses', 'credentials', 'professionalcertifications',
    'projects', 'personalprojects', 'sideprojects', 'keyprojects',
    'academicprojects', 'awards', 'achievements', 'honors', 'honours',
    'awardsandachievements', 'accomplishments', 'publications', 'research',
    'papers', 'researchpapers', 'journalarticles', 'extracurriculars',
    'activities', 'volunteer', 'communityservice', 'extracurricular',
})


def _normalize_spaced_heading(line: str) -> str:
    """Collapse spaced-character headings to their solid form.

    Case 1 — every letter spaced: 'C E R T I F I C A T I O N S' → 'CERTIFICATIONS'
    Case 2 — partial word splits: 'EXPERI ENCE' → 'EXPERIENCE', 'AW ARDS' → 'AWARDS'
      Only collapses when the collapsed form matches a known section keyword so
      phrases like 'WORK EXPERIENCE' are not collapsed.
    """
    stripped = line.strip()
    # Case 1: every single uppercase letter separated by one space
    if re.match(r'^([A-Z] ){2,}[A-Z]$', stripped):
        return stripped.replace(' ', '')
    # Case 2: all-uppercase line with spaces — collapse only if known heading
    if re.match(r'^[A-Z][A-Z ]{2,}[A-Z]$', stripped):
        collapsed = stripped.replace(' ', '')
        if collapsed.lower() in _KNOWN_SECTION_COLLAPSED:
            return collapsed
    return stripped


def _extract_section_blocks(text: str) -> Dict[str, str]:
    headings = {
        "summary": ["summary", "professional summary", "objective", "profile"],
        "skills": ["skills", "technical skills", "core competencies", "key skills"],
        "experience": ["experience", "work experience", "professional experience", "employment"],
        "education": ["education", "academic background", "academics"],
        "certifications": ["certifications", "certificates"],
        "awards": [
            "awards",
            "achievements",
            "awards & achievements",
            "awards and achievements",
            "honours",
            "accomplishments",
        ],
        "projects": [
            "projects",
            "personal projects",
            "side projects",
            "key projects",
            "notable projects",
            "project highlights",
        ],
        "publications": ["publications", "research", "papers"],
        "extracurriculars": [
            "extracurriculars",
            "extra-curriculars",
            "activities",
            "volunteer",
            "volunteering",
            "interests",
        ],
    }
    blocks = {key: "" for key in headings}
    all_headings = [name for aliases in headings.values() for name in aliases]
    pattern = re.compile(
        rf"(?im)^(?:{'|'.join(re.escape(item) for item in sorted(all_headings, key=len, reverse=True))})\s*:?\s*$"
    )

    # Build a line-normalised copy of the text so spaced headings like
    # "C E R T I F I C A T I O N S" are collapsed before pattern matching.
    # We rebuild the text line-by-line, keeping character positions intact
    # by padding collapsed lines with spaces so downstream offsets stay valid.
    normalized_lines: list[str] = []
    for raw_line in text.splitlines():
        norm = _normalize_spaced_heading(raw_line)
        # Pad to original length so match.end() / match.start() stay correct
        normalized_lines.append(norm.ljust(len(raw_line)))
    normalized_text = '\n'.join(normalized_lines)

    matches = list(pattern.finditer(normalized_text))

    for index, match in enumerate(matches):
        raw_heading = match.group(0).strip().rstrip(":").lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        # Slice from the ORIGINAL text so content is never padded
        content = text[start:end].strip()
        for section_name, aliases in headings.items():
            if raw_heading in aliases:
                blocks[section_name] = content
                break

    if not blocks["summary"]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        blocks["summary"] = "\n".join(lines[2:5]).strip() if len(lines) > 2 else ""

    return blocks


_CONTACT_LINE_RE = re.compile(
    r"(@|\+91|\+1\d|linkedin\.com|github\.com)", re.IGNORECASE
)

_CONTACT_STRONG_SIGNAL_RE = re.compile(
    r"(@|\+?\d[\d\-\s]{7,}|linkedin\.com|github\.com|medium\.com|https?://|www\.)",
    re.IGNORECASE,
)


def _strip_contact_artifacts(text: str) -> str:
    """Drop lines that look like a contact line (email/phone/linkedin) that
    leaked into a section block during extraction, e.g. a header absorbed
    into the summary block when the parser couldn't separate them."""
    if not text:
        return text
    kept = [
        line for line in text.splitlines()
        if not (_CONTACT_LINE_RE.search(line) and ("|" in line or len(line) < 120))
    ]
    return "\n".join(kept).strip()


def _extract_contact_line(lines: List[str]) -> str:
    for line in lines:
        if _CONTACT_STRONG_SIGNAL_RE.search(line):
            return line
    return lines[0] if lines else ""


def _parse_simple_list(block: str) -> List[str]:
    if not block.strip():
        return []
    items = []
    for line in block.splitlines():
        cleaned = line.strip().lstrip("-*•").strip()
        if cleaned:
            items.append(cleaned)
    return items


def _parse_experience_entries(block: str) -> List[Dict[str, Any]]:
    if not block.strip():
        return []

    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("-", "*", "•")):
            if current is None:
                current = {"title": "", "company": "", "location": "", "dates": "", "bullets": []}
                entries.append(current)
            current["bullets"].append(line.lstrip("-*• ").strip())
            continue

        if current:
            if not current["company"]:
                current["company"] = line
            elif not current["dates"] and re.search(r"\b(19|20)\d{2}\b|present", line, flags=re.IGNORECASE):
                current["dates"] = line
            elif not current["location"]:
                current["location"] = line
            else:
                current["bullets"].append(line)
        else:
            current = {"title": line, "company": "", "location": "", "dates": "", "bullets": []}
            entries.append(current)

    return entries


def _parse_education_entries(block: str) -> List[Dict[str, str]]:
    if not block.strip():
        return []

    entries: List[Dict[str, str]] = []
    for line in block.splitlines():
        cleaned = line.strip().lstrip("-*•").strip()
        if not cleaned:
            continue
        years = ""
        year_match = re.findall(r"(?:19|20)\d{2}", cleaned)
        if year_match:
            years = " - ".join(year_match[:2])
        entries.append({
            "degree": cleaned,
            "institution": "",
            "years": years,
        })
    return entries
