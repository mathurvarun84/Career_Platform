"""
Tests for the evaluator-optimizer loop in InterviewAgent.evaluate_answer().

Test matrix:
  1. Heavy "we", no numbers → we_default + vague_quantification, signal=weak
  2. Strong STAR, personal, quantified → no APs, signal=strong
  3. Good story, result in last sentence only → impact_buried, signal=developing
  4. Staff candidate, IC-level story → scope_collapse, signal=weak
  5. Injected hallucination → optimizer fires, corrects or drops bad excerpt

All tests except #5 mock _call_llm to avoid real API calls.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, call


# ── Shared fixtures ───────────────────────────────────────────────────────────

QUESTION_OWNERSHIP = {
    "id": "q1_test",
    "text": "Tell me about a time when you took end-to-end ownership of a project.",
    "question_type": "behavioral",
    "dimension": "ownership",
    "why_this_question": "testing ownership signals",
    "expected_signals": ["clear I-ownership", "measurable outcome", "conflict resolved"],
    "risky_anti_patterns": ["we_default", "vague_quantification"],
    "answer_risk_note": None,
    "company_value_ref": "Amazon LP: Ownership",
    "source": "generated",
}

QUESTION_IMPACT = {
    "id": "q2_test",
    "text": "Tell me about a project where you drove significant business impact.",
    "question_type": "behavioral",
    "dimension": "impact_and_scale",
    "why_this_question": "testing impact signals",
    "expected_signals": ["quantified outcome", "personal ownership", "scale"],
    "risky_anti_patterns": ["vague_quantification", "impact_buried"],
    "answer_risk_note": None,
    "company_value_ref": "Google: Impact",
    "source": "generated",
}

QUESTION_STAFF = {
    "id": "q3_test",
    "text": "Describe a time when you drove org-level change.",
    "question_type": "behavioral",
    "dimension": "impact_and_scale",
    "why_this_question": "testing staff-level scope",
    "expected_signals": ["cross-team influence", "architectural decision", "org tradeoffs"],
    "risky_anti_patterns": ["scope_collapse"],
    "answer_risk_note": None,
    "company_value_ref": "Meta: Impact",
    "source": "generated",
}


def _pad_answer(answer: str, min_words: int = 55) -> str:
    """Ensure answer meets evaluate_answer minimum word count."""
    words = answer.split()
    if len(words) >= min_words:
        return answer
    filler = (
        " I documented the timeline, stakeholders, and rollout plan so the team "
        "could execute without ambiguity."
    )
    padded = answer
    while len(padded.split()) < min_words:
        padded += filler
    return padded


def _make_feedback(
    signal: str,
    aps: list[dict],
    verdict: str = "Test verdict.",
    best: str = "Best line.",
    dimension: str = "ownership",
    seniority: str = "senior",
) -> dict:
    """Helper to build a minimal PerQuestionFeedback JSON string."""
    for ap in aps:
        ap.setdefault("interviewer_reads_as", "Ownership unclear to interviewer.")
    return json.dumps({
        "dimension_score": {
            "dimension": dimension,
            "signal_strength": signal,
            "score_delta": "0",
            "what_was_missing": "ownership clarity",
            "what_was_strong": "clear timeline",
        },
        "anti_patterns_fired": aps,
        "level_signal": {
            "signaled_level": seniority,
            "declared_level": seniority,
            "match": True,
            "note": "Level aligns with story scope.",
        },
        "executive_presence": "developing",
        "authenticity_note": "Mixed authentic and generic phrasing.",
        "overall_verdict": verdict,
        "best_line": best,
        "coaching_close": "Practice leading with I-decisions and one metric.",
    })


# ── Test 1: Heavy "we", no numbers ────────────────────────────────────────────

def test_we_default_and_vague_quantification():
    """
    Answer heavy on collective pronouns and vague adjectives.
    Expect we_default + vague_quantification fired, signal=weak.
    All triggered_excerpts are substrings of the answer — optimizer should NOT fire.
    """
    answer = _pad_answer(
        "We built a new pipeline that made things significantly faster. "
        "Our team decided to migrate the database and it greatly improved performance."
    )

    fake_feedback = _make_feedback(
        signal="weak",
        aps=[
            {
                "key": "we_default",
                "label": "We Default",
                "triggered_excerpt": "We built a new pipeline that made things significantly faster.",
                "interviewer_reads_as": "Ownership box left blank.",
                "rewrite_suggestion": "I designed and built a new pipeline that reduced latency by 40%.",
            },
            {
                "key": "vague_quantification",
                "label": "Vague Quantification",
                "triggered_excerpt": "made things significantly faster",
                "interviewer_reads_as": "Adjectives do not score on the impact field.",
                "rewrite_suggestion": "reduced p99 latency from 800ms to 120ms",
            },
        ],
    )

    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        return_value=fake_feedback,
    ) as mock_llm:
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.evaluate_answer({
            "question": QUESTION_OWNERSHIP,
            "answer_text": answer,
            "compressed_turns": [],
            "seniority": "mid",
        })

    # optimizer should not have fired (only 1 LLM call)
    assert mock_llm.call_count == 1, "Optimizer fired unexpectedly on valid excerpts"

    keys = {ap["key"] for ap in result["anti_patterns_fired"]}
    assert "we_default" in keys
    assert "vague_quantification" in keys
    assert result["dimension_score"]["signal_strength"] == "weak"

    # Verify excerpts are substrings of the answer
    for ap in result["anti_patterns_fired"]:
        assert ap["triggered_excerpt"] in answer, (
            f"excerpt not in answer: {ap['triggered_excerpt']!r}"
        )


# ── Test 2: Strong STAR, personal, quantified ─────────────────────────────────

def test_strong_star_no_anti_patterns():
    """
    Strong STAR answer with explicit I-ownership and hard numbers.
    Expect zero APs fired, signal=strong, single LLM call.
    """
    answer = _pad_answer(
        "I was the sole owner of our order-routing service. "
        "I redesigned the matching algorithm, reducing average latency from 450ms to 90ms. "
        "I shipped it in 6 weeks with zero production incidents."
    )

    fake_feedback = _make_feedback(
        signal="strong",
        aps=[],
        verdict="Excellent STAR structure with personal ownership and hard metrics.",
        best="I redesigned the matching algorithm, reducing average latency from 450ms to 90ms.",
    )

    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        return_value=fake_feedback,
    ) as mock_llm:
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.evaluate_answer({
            "question": QUESTION_OWNERSHIP,
            "answer_text": answer,
            "compressed_turns": [],
            "seniority": "senior",
        })

    assert mock_llm.call_count == 1
    assert result["anti_patterns_fired"] == []
    assert result["dimension_score"]["signal_strength"] == "strong"


# ── Test 3: Result buried in last sentence ────────────────────────────────────

def test_impact_buried_last_sentence():
    """
    Good story where the outcome only appears in the final sentence.
    Expect impact_buried fired, signal=developing.
    """
    answer = _pad_answer(
        "I identified a memory leak in our caching layer. "
        "I spent two weeks profiling and refactoring the cache eviction logic. "
        "I coordinated with the SRE team to roll out the fix safely. "
        "The fix reduced memory consumption by 60%."
    )

    last_sentence = "The fix reduced memory consumption by 60%."

    fake_feedback = _make_feedback(
        signal="developing",
        dimension="impact_and_scale",
        aps=[
            {
                "key": "impact_buried",
                "label": "Impact Buried",
                "triggered_excerpt": last_sentence,
                "rewrite_suggestion": (
                    "Lead with: 'I reduced memory consumption by 60% by fixing a cache leak.'"
                ),
            }
        ],
        verdict="Good execution detail but the impact only surfaces at the end.",
        best="I spent two weeks profiling and refactoring the cache eviction logic.",
    )

    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        return_value=fake_feedback,
    ) as mock_llm:
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.evaluate_answer({
            "question": QUESTION_IMPACT,
            "answer_text": answer,
            "compressed_turns": [],
            "seniority": "senior",
        })

    assert mock_llm.call_count == 1
    keys = {ap["key"] for ap in result["anti_patterns_fired"]}
    assert "impact_buried" in keys
    assert result["dimension_score"]["signal_strength"] == "developing"

    for ap in result["anti_patterns_fired"]:
        assert ap["triggered_excerpt"] in answer


# ── Test 4: Staff candidate, IC-level story ───────────────────────────────────

def test_scope_collapse_staff_candidate():
    """
    Staff-level candidate tells an individual contributor story.
    Expect scope_collapse fired, signal=weak.
    scope_collapse is ONLY valid for staff/em.
    """
    answer = _pad_answer(
        "I personally wrote all the migration scripts for our Postgres upgrade. "
        "It took me about three days and I tested each script manually before running it."
    )

    opening_sentence = "I personally wrote all the migration scripts for our Postgres upgrade."

    fake_feedback = _make_feedback(
        signal="weak",
        dimension="impact_and_scale",
        aps=[
            {
                "key": "scope_collapse",
                "label": "Scope Collapse",
                "triggered_excerpt": opening_sentence,
                "rewrite_suggestion": (
                    "Frame this as: I led the migration strategy across 3 services, "
                    "delegating script authoring to junior engineers while I owned risk mitigation."
                ),
            }
        ],
        verdict="IC-level story at staff seniority. Needs org leverage.",
        best="It took me about three days and I tested each script manually before running it.",
        seniority="staff",
    )

    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        return_value=fake_feedback,
    ) as mock_llm:
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.evaluate_answer({
            "question": QUESTION_STAFF,
            "answer_text": answer,
            "compressed_turns": [],
            "seniority": "staff",
        })

    assert mock_llm.call_count == 1
    keys = {ap["key"] for ap in result["anti_patterns_fired"]}
    assert "scope_collapse" in keys
    assert result["dimension_score"]["signal_strength"] == "weak"

    for ap in result["anti_patterns_fired"]:
        assert ap["triggered_excerpt"] in answer


# ── Test 5: Injected hallucination — optimizer must fire ─────────────────────

def test_optimizer_fires_on_hallucinated_excerpt():
    """
    Monkey-patch _call_llm to return a feedback dict where one triggered_excerpt
    is NOT present in the answer. Verify:
    1. The optimizer fires (second _call_llm call happens).
    2. The AP is either corrected (excerpt now in answer) or dropped entirely.
    3. No hallucinated excerpt is present in the final result.
    """
    answer = _pad_answer(
        "I built the entire search service from scratch and reduced query latency by 50%."
    )

    # First call: hallucinated excerpt — "We built" is NOT in the answer
    hallucinated_feedback = json.dumps({
        "dimension_score": {
            "dimension": "ownership",
            "signal_strength": "developing",
            "score_delta": "0",
            "what_was_missing": "clearer role delineation",
            "what_was_strong": "quantified impact",
        },
        "anti_patterns_fired": [
            {
                "key": "we_default",
                "label": "We Default",
                "triggered_excerpt": "Our manager approved the budget without my input.",  # NOT in answer
                "interviewer_reads_as": "Ownership unclear.",
                "rewrite_suggestion": "I built the entire search service from scratch.",
            }
        ],
        "level_signal": {
            "signaled_level": "senior",
            "declared_level": "senior",
            "match": True,
            "note": "Strong IC scope.",
        },
        "executive_presence": "developing",
        "authenticity_note": "Direct and specific.",
        "overall_verdict": "Decent answer with a quantified outcome.",
        "best_line": "I built the entire search service from scratch and reduced query latency by 50%.",
        "coaching_close": "Keep quantifying outcomes.",
    })

    # Second call: corrected — AP dropped (no excerpt found verbatim)
    corrected_feedback = json.dumps({
        "dimension_score": {
            "dimension": "ownership",
            "signal_strength": "developing",
            "score_delta": "0",
            "what_was_missing": "clearer role delineation",
            "what_was_strong": "quantified impact",
        },
        "anti_patterns_fired": [],  # AP dropped because no verbatim excerpt exists
        "level_signal": {
            "signaled_level": "senior",
            "declared_level": "senior",
            "match": True,
            "note": "Strong IC scope.",
        },
        "executive_presence": "developing",
        "authenticity_note": "Direct and specific.",
        "overall_verdict": "Decent answer with a quantified outcome.",
        "best_line": "I built the entire search service from scratch and reduced query latency by 50%.",
        "coaching_close": "Keep quantifying outcomes.",
    })

    call_responses = iter([hallucinated_feedback, corrected_feedback])

    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        side_effect=lambda *args, **kwargs: next(call_responses),
    ) as mock_llm:
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.evaluate_answer({
            "question": QUESTION_OWNERSHIP,
            "answer_text": answer,
            "compressed_turns": [],
            "seniority": "senior",
        })

    # Optimizer must have fired — second LLM call should have been made
    assert mock_llm.call_count == 2, (
        f"Expected 2 LLM calls (first + optimizer retry), got {mock_llm.call_count}"
    )

    # The hallucinated excerpt must NOT appear in any AP in the final result
    for ap in result.get("anti_patterns_fired", []):
        assert ap["triggered_excerpt"] in answer, (
            f"Hallucinated excerpt survived optimizer loop: {ap['triggered_excerpt']!r}"
        )


# ── Test: compress_turn output ────────────────────────────────────────────────

def test_compress_turn_format():
    """compress_turn output is under 150 tokens and contains required fields."""
    from backend.agents.interview_agent import InterviewAgent

    answer = "I led the migration of our monolith to microservices, cutting deploy time by 70%."
    feedback = {
        "dimension_score": {
            "dimension": "ownership",
            "signal_strength": "strong",
            "score_delta": "+1",
            "what_was_missing": "",
            "what_was_strong": "clear ownership",
        },
        "anti_patterns_fired": [
            {
                "key": "vague_quantification",
                "label": "Vague",
                "triggered_excerpt": "70%",
                "interviewer_reads_as": "n/a",
                "rewrite_suggestion": "",
            },
        ],
        "level_signal": {
            "signaled_level": "senior",
            "declared_level": "senior",
            "match": True,
            "note": "ok",
        },
        "executive_presence": "strong",
        "authenticity_note": "Specific metrics.",
        "overall_verdict": "Strong.",
        "best_line": answer,
        "coaching_close": "Reuse this story.",
    }

    compressed = InterviewAgent.compress_turn(1, answer, feedback)

    assert "Q1:" in compressed
    assert "dimension=ownership" in compressed
    assert "signal=strong" in compressed
    assert "anti_patterns=vague_quantification" in compressed
    assert "story_excerpt=" in compressed

    # Token estimate: rough approximation via word count × 1.3
    word_count = len(compressed.split())
    estimated_tokens = int(word_count * 1.3)
    assert estimated_tokens <= 150, (
        f"compress_turn output estimated at {estimated_tokens} tokens (>150): {compressed!r}"
    )


# ── Test: generate_follow_up hard cap ─────────────────────────────────────────

def test_generate_follow_up_hard_cap_no_llm_call():
    """generate_follow_up returns None immediately when follow_up_count >= 2."""
    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
    ) as mock_llm:
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.generate_follow_up({
            "question": QUESTION_OWNERSHIP,
            "answer_text": "Some answer.",
            "follow_up_count": 2,
        })

    assert result is None
    assert mock_llm.call_count == 0, "LLM should not be called when follow_up_count >= 2"


def test_generate_follow_up_returns_none_for_none_response():
    """generate_follow_up returns None when LLM returns NONE."""
    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        return_value="NONE",
    ):
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.generate_follow_up({
            "question": QUESTION_OWNERSHIP,
            "answer_text": "I took end-to-end ownership. I designed, built, and deployed "
                           "the service with 40% latency improvement. I learned to document "
                           "architectural decisions earlier.",
            "follow_up_count": 0,
        })

    assert result is None


def test_generate_follow_up_returns_probe_for_incomplete_answer():
    """generate_follow_up returns a probe dict for an answer missing ownership signal."""
    probe_text = "Can you clarify specifically what decisions you personally made?"

    with patch.object(
        __import__("backend.agents.interview_agent", fromlist=["InterviewAgent"]).InterviewAgent,
        "_call_llm",
        return_value=probe_text,
    ):
        from backend.agents.interview_agent import InterviewAgent
        agent = InterviewAgent.__new__(InterviewAgent)
        agent.model = "test"
        agent.max_tokens = 1500
        agent.provider = "anthropic"

        result = agent.generate_follow_up({
            "question": QUESTION_OWNERSHIP,
            "answer_text": "We built the pipeline together and it worked out well.",
            "follow_up_count": 0,
        })

    assert result is not None
    assert result["text"] == probe_text
    assert "id" in result
    assert result["trigger_reason"] == "ownership_or_impact_unclear"
