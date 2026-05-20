"""
Tests for ATS semantic booster.
Run: pytest tests/test_ats_semantic_booster.py -v
"""

import copy
import os

import pytest

from engine.ats_semantic_booster import (
    _extract_experience_bullets,
    semantic_boost,
)

BASELINE_ATS = {
    "score": 65,
    "breakdown": {
        "keyword_match": 12,
        "formatting": 20,
        "readability": 18,
        "impact_metrics": 15,
    },
    "ats_issues": ["Few quantified achievements"],
    "details": [],
}

HIGH_QUALITY_BULLETS = {
    "experience": {
        "header": "experience",
        "full_text": "",
        "sub_entries": [
            {
                "label": "Acme — Staff Engineer (2022–present)",
                "verbatim_text": (
                    "• Reduced API latency by 65% by migrating from synchronous Django ORM "
                    "calls to async PostgreSQL with connection pooling, serving 2M RPM.\n"
                    "• Built distributed Python microservices on Kubernetes with Kafka event "
                    "pipelines and observability dashboards."
                ),
            }
        ],
    }
}

NOISE_BULLETS = {
    "experience": {
        "header": "experience",
        "full_text": "",
        "sub_entries": [
            {
                "label": "Acme — Engineer (2022)",
                "verbatim_text": (
                    "• Worked with a team of 4 engineers on 3 different projects over 6 months "
                    "in Q3 2022 and Q4 2022.\n"
                    "• Attended weekly standups and wrote documentation."
                ),
            }
        ],
    }
}


def _mock_llm_response(monkeypatch, payload: dict):
    def fake_call(_user_prompt: str):
        return payload, {
            "prompt_tokens": 120,
            "completion_tokens": 40,
            "total_tokens": 160,
        }

    monkeypatch.setattr(
        "engine.ats_semantic_booster._call_semantic_llm",
        fake_call,
    )


def test_high_quality_bullets_positive_delta(monkeypatch):
    _mock_llm_response(
        monkeypatch,
        {
            "impact_quality_delta": 4,
            "keyword_centrality_delta": 3,
            "rationale": "Bullets show clear causal ownership with performance metrics.",
        },
    )

    result = semantic_boost(
        copy.deepcopy(BASELINE_ATS),
        HIGH_QUALITY_BULLETS,
    )

    assert result["semantic_boost"]["applied"] is True
    assert result["semantic_boost"]["impact_quality_delta"] >= 2
    assert result["breakdown"]["impact_metrics"] > BASELINE_ATS["breakdown"]["impact_metrics"]


def test_noise_numbers_non_positive_delta(monkeypatch):
    _mock_llm_response(
        monkeypatch,
        {
            "impact_quality_delta": -3,
            "keyword_centrality_delta": -1,
            "rationale": "Numbers describe team size and dates, not outcomes.",
        },
    )

    result = semantic_boost(
        copy.deepcopy(BASELINE_ATS),
        NOISE_BULLETS,
    )

    assert result["semantic_boost"]["impact_quality_delta"] <= 0


def test_llm_failure_graceful_fallback(monkeypatch):
    def boom(_user_prompt: str):
        raise RuntimeError("API timeout")

    monkeypatch.setattr("engine.ats_semantic_booster._call_semantic_llm", boom)

    original = copy.deepcopy(BASELINE_ATS)
    result = semantic_boost(original, HIGH_QUALITY_BULLETS)

    assert result["score"] == original["score"]
    assert result["breakdown"] == original["breakdown"]
    assert result["semantic_boost"]["applied"] is False
    assert "API timeout" in result["semantic_boost"]["error"]


def test_score_recalculated_correctly(monkeypatch):
    _mock_llm_response(
        monkeypatch,
        {
            "impact_quality_delta": 3,
            "keyword_centrality_delta": 2,
            "rationale": "Strong engineering impact and keyword centrality.",
        },
    )

    result = semantic_boost(copy.deepcopy(BASELINE_ATS), HIGH_QUALITY_BULLETS)

    assert result["breakdown"]["impact_metrics"] == 18
    assert result["breakdown"]["keyword_match"] == 14
    assert result["breakdown"]["formatting"] == 20
    assert result["breakdown"]["readability"] == 18
    assert result["score"] == 70


def test_empty_experience_skips_llm(monkeypatch):
    called = {"value": False}

    def should_not_run(_user_prompt: str):
        called["value"] = True
        return {}, {}

    monkeypatch.setattr("engine.ats_semantic_booster._call_semantic_llm", should_not_run)

    result = semantic_boost(copy.deepcopy(BASELINE_ATS), {"skills": {"full_text": "Python"}})

    assert called["value"] is False
    assert result["semantic_boost"]["applied"] is False
    assert result["semantic_boost"]["error"] == "no_experience_bullets"


def test_extract_experience_bullets_uses_sub_entries_only():
    sections = {
        "summary": {"full_text": "Generic summary with Python keyword dump."},
        "experience": {
            "sub_entries": [
                {
                    "label": "Flipkart — EM",
                    "verbatim_text": "• Led checkout latency reduction by 30%",
                }
            ]
        },
        "projects": {
            "sub_entries": [
                {
                    "label": "Side project",
                    "verbatim_text": "• Built Kafka pipeline",
                }
            ]
        },
    }
    text = _extract_experience_bullets(sections)

    assert "Flipkart — EM" in text
    assert "Side project" in text
    assert "Generic summary" not in text


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_live_llm_high_quality_bullets_integration():
    result = semantic_boost(copy.deepcopy(BASELINE_ATS), HIGH_QUALITY_BULLETS)

    assert result["semantic_boost"]["applied"] is True
    assert result["semantic_boost"]["impact_quality_delta"] >= 0
