"""
Regression tests for docx corruption fixes (PDF spacing, header ghosts, fragment markers).
Run: pytest tests/test_docx_corruption_fixes.py -v
"""

from __future__ import annotations

from backend.agents.rewriter import (
    COMPANY_HEADER_START,
    _ensure_experience_markers,
)
from parser import _clean_text, _collapse_split_word_artifacts
from validator.resume_understanding_validator import (
    _experience_entry_has_structure,
    _strip_resume_header_lines_from_verbatim,
    _validate_experience_section,
)


def test_collapse_pdf_word_spacing_artifacts() -> None:
    samples = {
        "Eng in eer in g Manager": "Engineering Manager",
        "Micros of t": "Microsoft",
        "includ in g": "including",
        "tr an sacti on s": "transactions",
    }
    for broken, expected_word in samples.items():
        fixed = _collapse_split_word_artifacts(broken)
        assert expected_word in fixed, f"{broken!r} → {fixed!r}, expected {expected_word!r}"


def test_clean_text_applies_spacing_fix() -> None:
    out = _clean_text("Eng in eer in g teams at Micros of t.")
    assert "Engineering" in out
    assert "Microsoft" in out
    assert "Eng in eer" not in out
    # Must not glue real multi-word phrases
    assert "for two teams" in _clean_text(
        "overhead for two teams and improving overall engineering throughput."
    )


def test_strip_contact_header_from_experience_verbatim() -> None:
    verbatim = (
        "Bengaluru, KA | +91-9611522744 | mathurvarun84@gmail.com\n"
        "linkedin.com/in/mathurvarun84 | github.com/user\n"
        "Engineering Manager | Flipkart — Bengaluru, KA\n"
        "Sep 2020 – Present\n"
        "• Led platform teams"
    )
    cleaned = _strip_resume_header_lines_from_verbatim(verbatim)
    assert "+91" not in cleaned.split("\n")[0]
    assert "@" not in cleaned.split("\n")[0]
    assert "linkedin.com" not in cleaned.split("\n")[0]
    assert cleaned.startswith("Engineering Manager")


def test_header_only_entry_dropped_by_validate_experience() -> None:
    section = {
        "header": "experience",
        "full_text": "",
        "sub_entries": [
            {
                "label": "ghost",
                "verbatim_text": (
                    "Bengaluru, KA | +91-9611522744 | user@gmail.com\n"
                    "linkedin.com/in/user"
                ),
            },
            {
                "label": "Flipkart",
                "verbatim_text": (
                    "Engineering Manager | Flipkart — Bengaluru, KA\n"
                    "Sep 2020 – Present\n"
                    "• Bullet one"
                ),
            },
        ],
    }
    repaired, anomalies = _validate_experience_section(section)
    assert len(repaired["sub_entries"]) == 1
    assert "Flipkart" in repaired["sub_entries"][0]["verbatim_text"]
    assert any("ghost" in a or "header" in a for a in anomalies)


def test_fragment_merged_into_preceding_entry() -> None:
    section = {
        "header": "experience",
        "full_text": "",
        "sub_entries": [
            {
                "label": "Flipkart",
                "verbatim_text": (
                    "Engineering Manager | Flipkart — Bengaluru, KA\n"
                    "Sep 2020 – Present\n"
                    "• Drove migration"
                ),
            },
            {
                "label": "continuation",
                "verbatim_text": "scaling systems to 15K QPS and reducing MTTR by 30%",
            },
        ],
    }
    repaired, anomalies = _validate_experience_section(section)
    assert len(repaired["sub_entries"]) == 1
    assert "scaling systems" in repaired["sub_entries"][0]["verbatim_text"]
    assert any("merged fragment" in a for a in anomalies)
    assert not _experience_entry_has_structure("scaling systems to 15K QPS")


def test_ensure_experience_markers_skips_sentence_fragment() -> None:
    fragment = "migration scaling systems to 15K QPS and reducing MTTR by 30%"
    out = _ensure_experience_markers(fragment, "Flipkart — EM")
    assert out == fragment
    assert COMPANY_HEADER_START not in out
