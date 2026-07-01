"""
Regression test for the docx generation pipeline.

build_final_docx() must never corrupt tokens that are already clean
(LLM rewrite output, structured contact/skills text). Past incidents:
_clean_text()'s camelCase splitter mangled "LangGraph" -> "Lang Graph",
and the run-on-token splitter inserted spaces inside emails/URLs
("mathurvarun84@gmail.com" -> "m at hurvarun84@gmail.com").
"""

import io
import sys
from pathlib import Path

import pytest
from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def build_final_docx():
    # test_jd_fetcher.py and test_jd_fetch_endpoint.py stub sys.modules["engine"]/
    # ["engine.resume_builder"] with a fake `lambda **kwargs: b""` — in
    # test_jd_fetcher.py this happens inside a test function with no teardown,
    # so the stub can still be cached when this fixture runs later in the same
    # session. Force-purge any cached engine.* modules so this always imports
    # the real package fresh from disk.
    for name in list(sys.modules):
        if name == "engine" or name.startswith("engine."):
            del sys.modules[name]
    from engine.resume_builder import build_final_docx as fn

    return fn


GOLDEN_TOKENS = [
    "LangGraph",
    "LangChain",
    "CrewAI",
    "OpenAI",
    "GitHub",
    "DevOps",
    "mathurvarun84@gmail.com",
    "linkedin.com/in/mathurvarun84",
]


def _full_text(docx_bytes: bytes) -> str:
    doc = Document(io.BytesIO(docx_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def test_skills_and_contact_survive_build_with_no_rewrites(build_final_docx):
    structured = {
        "name": "Test Candidate",
        "title": "Engineer",
        "contact": (
            "Bengaluru, KA | +91-9611522744 | mathurvarun84@gmail.com | "
            "linkedin.com/in/mathurvarun84"
        ),
        "skills": "Agentic Architecture: LangGraph, LangChain, CrewAI, OpenAI, GitHub, DevOps",
    }
    docx_bytes = build_final_docx(structured, rewrites={}, style="balanced")
    text = _full_text(docx_bytes)
    for token in GOLDEN_TOKENS:
        assert token in text, f"{token!r} was corrupted in generated docx"


def test_skills_survive_build_with_rewrite_content(build_final_docx):
    structured = {
        "name": "Test Candidate",
        "title": "Engineer",
        "contact": "mathurvarun84@gmail.com | linkedin.com/in/mathurvarun84",
        "skills": "Old skills text",
    }
    rewrites = {
        "skills": {
            "balanced": "Agentic Architecture: LangGraph, LangChain, CrewAI, OpenAI, GitHub, DevOps",
        }
    }
    docx_bytes = build_final_docx(structured, rewrites=rewrites, style="balanced")
    text = _full_text(docx_bytes)
    for token in ["LangGraph", "LangChain", "CrewAI", "OpenAI", "GitHub", "DevOps"]:
        assert token in text, f"{token!r} was corrupted in generated docx"


def test_low_confidence_experience_text_falls_back_to_structured_entries(build_final_docx):
    """A flat experience block with no '|<year>' pattern should not be
    heuristically mis-split into bogus company/role lines when a structured
    experience list with clean fields is available."""
    structured = {
        "name": "Test Candidate",
        "title": "Engineer",
        "contact": "test@example.com",
        "experience": [
            {
                "title": "Engineering Manager",
                "company": "Flipkart",
                "location": "Bengaluru, KA",
                "dates": "Sep 2020 - Jan 2026",
                "bullets": ["Led 7 teams across platform engineering"],
            }
        ],
    }
    rewrites = {
        "experience": {
            "balanced": "Engineering Manager\nFlipkart\nBengaluru, KA\nSep 2020 - Jan 2026\n- Led 7 teams across platform engineering",
        }
    }
    docx_bytes = build_final_docx(structured, rewrites=rewrites, style="balanced")
    text = _full_text(docx_bytes)
    assert "Flipkart" in text
    assert "Engineering Manager" in text


def test_contaminated_skills_rewrite_is_rejected_for_clean_structured_text(build_final_docx):
    structured = {
        "name": "Test Candidate",
        "title": "Engineer",
        "contact": "test@example.com",
        "skills": "Agentic Architecture: LangGraph, LangChain, CrewAI, OpenAI, GitHub, DevOps",
    }
    rewrites = {
        "skills": {
            "balanced": (
                "Agentic Architecture: Lang Graph, Lang Chain\n"
                "PROFESSIONAL EXPERIENCE\n"
                "Engineering Manager | Flipkart | Bengaluru, KA"
            )
        }
    }
    docx_bytes = build_final_docx(structured, rewrites=rewrites, style="balanced")
    text = _full_text(docx_bytes)
    assert "LangGraph" in text
    assert "LangChain" in text
    assert "Engineering Manager | Flipkart" not in text


def test_contaminated_summary_rewrite_is_rejected_for_clean_structured_text(build_final_docx):
    structured = {
        "name": "Test Candidate",
        "title": "Engineer",
        "contact": "Bengaluru | test@example.com | linkedin.com/in/test",
        "summary": "Built distributed systems for marketplaces and improved platform reliability.",
    }
    rewrites = {
        "summary": {
            "balanced": (
                "Bengaluru | test@example.com | linkedin.com/in/test\n"
                "PROFESSIONAL EXPERIENCE"
            )
        }
    }
    docx_bytes = build_final_docx(structured, rewrites=rewrites, style="balanced")
    text = _full_text(docx_bytes)
    assert "Built distributed systems for marketplaces" in text
    assert "PROFESSIONAL EXPERIENCE" not in text


def test_low_confidence_experience_uses_resume_sections_sub_entries(build_final_docx):
    structured = {
        "name": "Test Candidate",
        "title": "Engineer",
        "contact": "test@example.com",
        "resume_sections": {
            "experience": {
                "full_text": "",
                "sub_entries": [
                    {
                        "label": "Flipkart",
                        "verbatim_text": (
                            "Engineering Manager | Flipkart | Bengaluru, KA Sep 2020 - Jan 2026\n"
                            "- Led 7 teams across platform engineering"
                        ),
                    }
                ],
            }
        },
    }
    rewrites = {
        "experience": {
            "balanced": "Engineering Manager\nFlipkart\nBengaluru, KA\nSep 2020 - Jan 2026"
        }
    }
    docx_bytes = build_final_docx(structured, rewrites=rewrites, style="balanced")
    text = _full_text(docx_bytes)
    assert "Engineering Manager" in text
    assert "Flipkart" in text
    assert "Led 7 teams across platform engineering" in text
