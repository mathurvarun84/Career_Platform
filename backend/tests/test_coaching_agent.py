"""Tests for coaching bullet parsing (no LLM calls)."""

import pytest

from backend.agents.coaching_agent import (
    _bullet_from_raw_answer,
    _extract_bullet_fields,
    _parse_llm_json,
    bullet_is_meaningful,
)


def test_parse_llm_json_strips_markdown_fence():
    raw = '```json\n{"bullet": "• Led Kafka rollout", "grounding": true}\n```'
    data = _parse_llm_json(raw)
    bullet, grounding = _extract_bullet_fields(data)
    assert bullet.startswith("•")
    assert "Kafka" in bullet
    assert grounding is True


def test_extract_bullet_accepts_generated_bullet_key():
    bullet, _ = _extract_bullet_fields(
        {"generated_bullet": "Led platform migration", "grounding": False}
    )
    assert bullet.startswith("•")
    assert "migration" in bullet


def test_bullet_is_meaningful_rejects_parser_artifact():
    assert bullet_is_meaningful("• :") is False
    assert bullet_is_meaningful("• Led Kafka integration, cutting latency 20%") is True


def test_raw_answer_fallback():
    bullet = _bullet_from_raw_answer(
        "I created a Kafka roadmap that reduced latencies by 20%."
    )
    assert bullet_is_meaningful(bullet)
    assert "20%" in bullet
