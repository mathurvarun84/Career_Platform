from parser import _build_structured_resume
from validator.resume_understanding_validator import ResumeUnderstandingValidator


RAW_RESUME_TEXT = """VARUN MATHUR
Engineering Manager | Distributed Systems | Gen AI & Agentic Architecture
Bengaluru, KA | +91-9611522744 | mathurvarun84@gmail.com | linkedin.com/in/mathurvarun84
PROFESSIONAL SUMMARY
Engineering leader with 17 years building distributed backend systems for high-scale platforms.
SKILLS
Agentic Architecture: LangGraph, LangChain, CrewAI, OpenAI, GitHub, DevOps
PROFESSIONAL EXPERIENCE
Engineering Manager | Flipkart | Bengaluru, KA Sep 2020 - Jan 2026
- Led 7 teams across platform engineering
EDUCATION
Executive MBA | IIM Bangalore | 2017 - 2018
"""


def test_build_structured_resume_title_with_pipes_is_not_contact() -> None:
    structured = _build_structured_resume(RAW_RESUME_TEXT)
    assert structured["title"] == "Engineering Manager | Distributed Systems | Gen AI & Agentic Architecture"
    assert structured["contact"].startswith("Bengaluru, KA | +91-9611522744")


def test_validator_replaces_contaminated_summary_and_skills_from_raw_sections() -> None:
    validator = ResumeUnderstandingValidator()
    a1_output = {
        "has_summary": True,
        "tech_stack": ["LangGraph", "LangChain", "OpenAI", "GitHub", "DevOps"],
        "resume_sections": {
            "summary": {
                "header": "summary",
                "full_text": (
                    "Bengaluru, KA | +91-9611522744 | mathurvarun84@gmail.com | linkedin.com/in/mathurvarun84\n"
                    "PROFESSIONAL SUMMARY"
                ),
                "sub_entries": [],
            },
            "skills": {
                "header": "skills",
                "full_text": (
                    "Agentic Architecture: LangGraph, LangChain\n"
                    "PROFESSIONAL EXPERIENCE\n"
                    "Engineering Manager | Flipkart | Bengaluru, KA Sep 2020 - Jan 2026"
                ),
                "sub_entries": [],
            },
            "experience": {
                "header": "experience",
                "full_text": "Engineering Manager | Flipkart | Bengaluru, KA Sep 2020 - Jan 2026",
                "sub_entries": [],
            },
        },
        "sections_present": ["summary", "skills", "experience"],
        "experience_years": 17,
    }

    repaired = validator.validate_and_fix(a1_output, RAW_RESUME_TEXT)
    sections = repaired["resume_sections"]

    assert sections["summary"]["full_text"].startswith(
        "Engineering leader with 17 years building distributed backend systems"
    )
    assert "mathurvarun84@gmail.com" not in sections["summary"]["full_text"]

    assert sections["skills"]["full_text"] == (
        "Agentic Architecture: LangGraph, LangChain, CrewAI, OpenAI, GitHub, DevOps"
    )
    assert "PROFESSIONAL EXPERIENCE" not in sections["skills"]["full_text"]
