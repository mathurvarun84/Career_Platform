"""
Unit tests for _parse_experience_header_from_verbatim (Bug 1).

Covers all 7 legacy experience entries (two-line and single-line) plus LLM fixed-format.
Run: pytest tests/test_parse_experience_header.py -v
"""

from __future__ import annotations

import pytest

from backend.agents.rewriter import _parse_experience_header_from_verbatim

# Two-line legacy entries (header line + date-only line)
_LEGACY_TWO_LINE = [
    (
        "Engineering Manager | Flipkart — Bengaluru, KA\nSep 2020 – Present",
        {
            "role": "Engineering Manager",
            "company": "Flipkart",
            "location": "Bengaluru, KA",
            "dates": "Sep 2020 – Present",
        },
    ),
    (
        "Head of Engineering | SmartVizX — Bengaluru, KA\nDec 2019 – Sep 2020",
        {
            "role": "Head of Engineering",
            "company": "SmartVizX",
            "location": "Bengaluru, KA",
            "dates": "Dec 2019 – Sep 2020",
        },
    ),
    (
        "Engineering Manager | Apttus (via Altran) — Bengaluru, KA\nNov 2018 – Dec 2019",
        {
            "role": "Engineering Manager",
            "company": "Apttus (via Altran)",
            "location": "Bengaluru, KA",
            "dates": "Nov 2018 – Dec 2019",
        },
    ),
    (
        "Engineering Manager | ClearTax (via Altran) — Bengaluru, KA\nDec 2016 – Oct 2018",
        {
            "role": "Engineering Manager",
            "company": "ClearTax (via Altran)",
            "location": "Bengaluru, KA",
            "dates": "Dec 2016 – Oct 2018",
        },
    ),
    (
        "Senior Consultant | British Telecom — Bengaluru, KA\nSep 2013 – Dec 2016",
        {
            "role": "Senior Consultant",
            "company": "British Telecom",
            "location": "Bengaluru, KA",
            "dates": "Sep 2013 – Dec 2016",
        },
    ),
    (
        "Tech Consultant | Microsoft — Bengaluru, KA\nSep 2011 – Sep 2013",
        {
            "role": "Tech Consultant",
            "company": "Microsoft",
            "location": "Bengaluru, KA",
            "dates": "Sep 2011 – Sep 2013",
        },
    ),
    (
        "Lead Software Engineer | Mindtree — Bengaluru, KA\nJul 2007 – Oct 2011",
        {
            "role": "Lead Software Engineer",
            "company": "Mindtree",
            "location": "Bengaluru, KA",
            "dates": "Jul 2007 – Oct 2011",
        },
    ),
]

# Single-line legacy (pipe on line 0 must NOT trigger fixed-format path)
_LEGACY_SINGLE_LINE = (
    "Engineering Manager | Flipkart — Bengaluru, KA Sep 2020 – Present",
    {
        "role": "Engineering Manager",
        "company": "Flipkart",
        "location": "Bengaluru, KA",
        "dates": "Sep 2020 – Present",
    },
)

# LLM fixed-format: company-only line 0, role|location|dates on line 1
_LLM_FIXED_FORMAT = (
    "Flipkart\nEngineering Manager | Bengaluru, KA Sep 2020 – Present",
    {
        "company": "Flipkart",
        "role": "Engineering Manager",
        "location": "Bengaluru, KA",
        "dates": "Sep 2020 – Present",
    },
)


@pytest.mark.parametrize("verbatim,expected", _LEGACY_TWO_LINE)
def test_parse_legacy_two_line_entries(verbatim: str, expected: dict[str, str]) -> None:
    result = _parse_experience_header_from_verbatim(verbatim)
    for key, value in expected.items():
        assert result[key] == value, f"{key}: got {result[key]!r}, want {value!r}"


def test_parse_legacy_single_line_flipkart() -> None:
    verbatim, expected = _LEGACY_SINGLE_LINE
    result = _parse_experience_header_from_verbatim(verbatim)
    for key, value in expected.items():
        assert result[key] == value, f"{key}: got {result[key]!r}, want {value!r}"


def test_parse_llm_fixed_format() -> None:
    verbatim, expected = _LLM_FIXED_FORMAT
    result = _parse_experience_header_from_verbatim(verbatim)
    for key, value in expected.items():
        assert result[key] == value, f"{key}: got {result[key]!r}, want {value!r}"
