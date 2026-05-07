"""
Resume file parser - PDF, DOCX, and TXT to plain text.
"""

import os
import re
from typing import Any, Dict, List

import streamlit as st


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

    if "parsed_resume_structured" not in st.session_state:
        st.session_state["parsed_resume_structured"] = _build_structured_resume(raw_text)

    return raw_text


def _build_structured_resume(text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    section_blocks = _extract_section_blocks(text)

    name = lines[0] if lines else ""
    contact = _extract_contact_line(lines[1:6]) if len(lines) > 1 else ""
    title = ""
    if len(lines) > 1 and lines[1] != contact:
        title = lines[1]

    return {
        "name": name,
        "title": title,
        "contact": contact,
        "summary": section_blocks.get("summary", ""),
        "skills": section_blocks.get("skills", ""),
        "experience": _parse_experience_entries(section_blocks.get("experience", "")),
        "education": _parse_education_entries(section_blocks.get("education", "")),
        "certifications": _parse_simple_list(section_blocks.get("certifications", "")),
        "awards": _parse_simple_list(section_blocks.get("awards", "")),
    }


def _parse_pdf(file_path: str) -> str:
    import pdfplumber

    texts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
    extracted_text = _clean_text("\n".join(texts))
    if _is_text_meaningful(extracted_text):
        return extracted_text
    return _parse_pdf_ocr(file_path)


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


def _parse_docx(file_path: str) -> str:
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return _clean_text("\n".join(paragraphs))


def _parse_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return _clean_text(f.read())


def _clean_text(text: str) -> str:
    import re
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
    return text.strip()


def _fix_concatenated_words(text: str) -> str:
    fixed_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("-", "*", "\u2022", "http")) or ":" in stripped:
            fixed_lines.append(line)
        else:
            fixed = re.sub(
                r"(?<=[a-z])(of|in|and|for|at|to|with|the)(?=[A-Z'])",
                r" \1 ",
                line,
            )
            fixed_lines.append(re.sub(r"([a-z])([A-Z])", r"\1 \2", fixed))
    return "\n".join(fixed_lines)


def _extract_section_blocks(text: str) -> Dict[str, str]:
    headings = {
        "summary": ["summary", "professional summary", "objective", "profile"],
        "skills": ["skills", "technical skills", "core competencies", "key skills"],
        "experience": ["experience", "work experience", "professional experience", "employment"],
        "education": ["education", "academic background", "academics"],
        "certifications": ["certifications", "certificates"],
        "awards": ["awards", "achievements"],
    }
    blocks = {key: "" for key in headings}
    all_headings = [name for aliases in headings.values() for name in aliases]
    pattern = re.compile(
        rf"(?im)^(?:{'|'.join(re.escape(item) for item in sorted(all_headings, key=len, reverse=True))})\s*:?\s*$"
    )
    matches = list(pattern.finditer(text))

    for index, match in enumerate(matches):
        raw_heading = match.group(0).strip().rstrip(":").lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        for section_name, aliases in headings.items():
            if raw_heading in aliases:
                blocks[section_name] = content
                break

    if not blocks["summary"]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        blocks["summary"] = "\n".join(lines[2:5]).strip() if len(lines) > 2 else ""

    return blocks


def _extract_contact_line(lines: List[str]) -> str:
    for line in lines:
        lowered = line.lower()
        if any(token in lowered for token in ("@", "|", "+91", "+1", "linkedin", "github", ".com")):
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
