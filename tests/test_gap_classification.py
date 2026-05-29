"""Tests for deterministic coach gap classification (zero LLM)."""

from backend.agents.gap_analyzer import (
    classify_gap,
    classify_section_gaps,
    priority_fixes_from_gaps,
    reclassify_gaps_for_resume_only,
)


def test_classify_surface_missing_keyword():
    gap = {
        "section": "skills",
        "gap_reason": "Missing keyword for React",
        "rewrite_instruction": "Add React to skills line",
        "missing_keywords": ["React"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "surface"
    assert result["auto_apply"] is True
    assert result["requires_user_input"] is False


def test_classify_evidence_mentoring():
    gap = {
        "section": "experience",
        "gap_reason": "No mention of mentoring",
        "rewrite_instruction": "Add mentorship evidence",
        "missing_keywords": [],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "evidence"
    assert result["requires_user_input"] is True
    assert result["coaching_question"]
    assert len(result["coaching_hint"]) >= 3


def test_classify_structural_passive_voice():
    gap = {
        "section": "experience",
        "gap_reason": "Passive voice, weak action verbs",
        "rewrite_instruction": "Rewrite bullets with active voice and stronger verbs",
        "missing_keywords": ["active voice", "strong verbs", "scale"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "structural"
    assert result["auto_apply"] is False
    assert result["requires_user_input"] is False


def test_classify_evidence_cross_team_collaboration():
    gap = {
        "section": "experience",
        "gap_reason": "No examples of cross-team collaboration",
        "rewrite_instruction": "Highlight cross-functional projects",
        "missing_keywords": ["cross-team collaboration"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "evidence"
    assert result["requires_user_input"] is True
    assert result["coaching_question"]


def test_classify_evidence_quantified_impact_and_architecture():
    gap = {
        "section": "experience",
        "gap_reason": "Lacks quantified impact metrics and architectural decisions",
        "rewrite_instruction": "Add metrics and design tradeoffs",
        "missing_keywords": ["quantified impact", "architectural decisions"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "evidence"
    assert result["requires_user_input"] is True


def test_reclassify_resume_only_promotes_metric_gaps_to_structural():
    classified = classify_section_gaps(
        [
            {
                "section": "experience",
                "gap_reason": "Oracle bullets lack quantified impact metrics",
                "rewrite_instruction": "Add QPS and user scale to bullets",
                "missing_keywords": [],
                "needs_change": True,
                "sub_changes": [],
            }
        ],
        "",
    )
    assert classified[0]["gap_type"] == "evidence"
    promoted = reclassify_gaps_for_resume_only(classified)
    assert promoted[0]["gap_type"] == "structural"
    assert promoted[0]["requires_user_input"] is False


def test_classify_trusts_llm_evidence_over_surface_heuristic():
    """LLM-set gap_type must not be overridden by keyword heuristics."""
    gap = {
        "section": "skills",
        "gap_type": "Evidence",
        "gap_reason": "Missing keyword for stakeholder management",
        "rewrite_instruction": "Add stakeholder examples",
        "missing_keywords": ["stakeholder"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "evidence"
    assert result["requires_user_input"] is True
    assert result["auto_apply"] is False


def test_classify_trusts_llm_surface_over_evidence_heuristic():
    """LLM Surface classification must win over mentoring signal in reason text."""
    gap = {
        "section": "experience",
        "gap_type": "surface",
        "gap_reason": "Missing keyword mentor — add the word mentor",
        "rewrite_instruction": "Add mentor keyword to bullet 2",
        "missing_keywords": ["mentor"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "surface"
    assert result["auto_apply"] is True


def test_priority_fixes_include_surface_auto_apply_without_needs_change():
    gaps = classify_section_gaps(
        [
            {
                "section": "skills",
                "needs_change": False,
                "gap_reason": "Readability needs improvement — shorter sentences",
                "rewrite_instruction": "Tighten skills line wording",
                "missing_keywords": [],
                "sub_changes": [],
            }
        ],
        resume_text="",
    )
    fixes = priority_fixes_from_gaps(gaps)
    assert len(fixes) == 1
    assert fixes[0]["gap_type"] == "surface"
    assert fixes[0]["auto_apply"] is True


def test_priority_fixes_exclude_no_change_sections():
    gaps = classify_section_gaps(
        [
            {
                "section": "education",
                "needs_change": False,
                "gap_reason": "No change needed",
                "rewrite_instruction": "",
                "missing_keywords": [],
                "sub_changes": [],
            },
            {
                "section": "certifications",
                "needs_change": False,
                "gap_reason": "No change needed",
                "rewrite_instruction": "",
                "missing_keywords": [],
                "sub_changes": [],
            },
            {
                "section": "awards",
                "needs_change": False,
                "gap_reason": "No change needed",
                "rewrite_instruction": "",
                "missing_keywords": [],
                "sub_changes": [],
            },
        ],
        resume_text="",
    )
    fixes = priority_fixes_from_gaps(gaps)
    assert fixes == []
