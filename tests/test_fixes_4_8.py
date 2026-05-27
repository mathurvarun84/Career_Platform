"""Regression tests for fixes #4–#8."""

from backend.agents.rewriter import RewriterAgent
from backend.role_fit import compute_role_fit
from backend.schemas.common import SectionText, SubEntry
from orchestrator import _ensure_jd_match_score_after
from validator.rewriter_validator import (
    assert_structural_completeness,
    backfill_missing_rewrite_sections,
    _split_bullets,
)


def test_role_fit_counts_unanswerable_gaps_after_a3() -> None:
    resume = {"experience_years": 8, "seniority": "senior"}
    jd = {"min_years_required": 6, "jd_seniority_level": "senior"}
    pre = compute_role_fit(resume, jd)
    post = compute_role_fit(
        resume,
        jd,
        {
            "section_gaps": [
                {"gap_reason": "No executive stakeholder management evidence"},
                {"gap_reason": "Missing board-level strategy experience"},
            ]
        },
    )
    assert pre["unanswerable_evidence_gaps"] == 0
    assert post["unanswerable_evidence_gaps"] >= 2


def test_resolve_sub_text_returns_empty_on_label_miss() -> None:
    agent = RewriterAgent()
    section = SectionText(
        header="experience",
        full_text="Flipkart block\n\nInfosys block",
        sub_entries=[
            SubEntry(label="Flipkart — EM", verbatim_text="Flipkart block"),
            SubEntry(label="Infosys — SE", verbatim_text="Infosys block"),
        ],
    )
    assert agent._resolve_sub_text(section, "Amazon — VP") == ""
    assert agent._resolve_sub_text(section, "Flipkart") == "Flipkart block"


def test_split_bullets_handles_inline_bullet_separators() -> None:
    agent = RewriterAgent()
    text = "Led team • Shipped fraud model • Built Kafka pipeline"
    bullets = agent._split_bullets(text)
    assert len(bullets) == 3
    assert "Kafka" in bullets[-1]


def test_backfill_missing_rewrite_sections_injects_verbatim() -> None:
    resume_sections = {
        "skills": {
            "header": "skills",
            "full_text": "Python, SQL, Kafka",
            "sub_entries": [],
        }
    }
    rewrites: dict = {"experience": {"balanced": "x", "aggressive": "x", "top_1_percent": "x"}}
    missing = assert_structural_completeness(rewrites, resume_sections)
    assert "skills" in missing
    repaired = backfill_missing_rewrite_sections(rewrites, resume_sections, missing)
    assert "Python" in repaired["skills"]["balanced"]


def test_ensure_jd_match_score_after_defaults_when_missing() -> None:
    gap = {"jd_match_score_before": 68}
    _ensure_jd_match_score_after(gap)
    assert gap["jd_match_score_after"] == 73


def test_validator_split_bullets_handles_inline_separators() -> None:
    text = "Led team • Shipped model • Built pipeline"
    bullets = _split_bullets(text)
    assert len(bullets) == 3
