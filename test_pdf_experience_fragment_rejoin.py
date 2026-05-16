"""
Regression: PDF soft-wrap fragments must be rejoined before experience block detection.

Uses the real resume PDF when VARUN_RESUME_PDF is set (or a default Downloads path).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from parser import _extract_section_blocks, _parse_pdf
from validator.resume_understanding_validator import _detect_experience_by_date_ranges

_DEFAULT_PDF = Path(
    r"C:\Users\mathu\Downloads\VARUN_MATHUR_Resume_New.pdf"
)
VARUN_RESUME_PDF = os.environ.get("VARUN_RESUME_PDF", str(_DEFAULT_PDF))

# Substrings expected in role-header labels after full rejoin (acceptance ground truth).
_EXPECTED_LABEL_MARKERS = (
    "Flipkart",
    "SmartViz",
    "Apttus",
    "Tax",
    "Telecom",
    "Microsoft",
    "Mindtree",
)


@pytest.fixture(scope="module")
def experience_text_from_pdf() -> str:
    pdf_path = Path(VARUN_RESUME_PDF)
    if not pdf_path.is_file():
        pytest.skip(f"Resume PDF not found: {pdf_path}")
    resume_text = _parse_pdf(str(pdf_path))
    blocks = _extract_section_blocks(resume_text)
    experience = blocks.get("experience", "").strip()
    if not experience:
        pytest.skip("No experience section extracted from PDF")
    return experience


def test_pdf_fragment_rejoin_finds_seven_experience_blocks(
    experience_text_from_pdf: str,
) -> None:
    blocks = _detect_experience_by_date_ranges(experience_text_from_pdf)
    labels = [b["label"] for b in blocks]

    assert len(blocks) == 7, f"expected 7 experience blocks, got {len(blocks)}: {labels}"
    for name in _EXPECTED_LABEL_MARKERS:
        assert any(name.replace(" ", "") in label.replace(" ", "") for label in labels), (
            f"no label contains {name!r}; labels={labels}"
        )
