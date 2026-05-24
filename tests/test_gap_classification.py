"""Tests for deterministic coach gap classification (zero LLM)."""

from backend.agents.gap_analyzer import classify_gap


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
        "gap_reason": "Passive voice, no impact metric",
        "rewrite_instruction": "Rewrite bullets with active voice and metrics",
        "missing_keywords": ["impact", "metrics", "scale"],
        "needs_change": True,
    }
    result = classify_gap(gap, "")
    assert result["gap_type"] == "structural"
    assert result["auto_apply"] is False
    assert result["requires_user_input"] is False
