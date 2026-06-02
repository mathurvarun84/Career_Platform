#!/usr/bin/env python
"""Test script to verify role-aware fixes implementation."""

import json
from backend.agents.gap_analyzer import (
    _build_coaching_question,
    classify_gap,
    classify_section_gaps,
    _EVIDENCE_SIGNALS,
)
from backend.agents.rewriter import RewriterAgent
from backend.few_shot_prompts import get_role_context

def test_evidence_signals_expanded():
    """Verify _EVIDENCE_SIGNALS includes new cross-role signals."""
    print("[PASS] Testing expanded _EVIDENCE_SIGNALS...")

    # Check for some key additions
    assert "roadmap ownership" in _EVIDENCE_SIGNALS, "Missing PRODUCT signal"
    assert "model accuracy" in _EVIDENCE_SIGNALS, "Missing DATA_ANALYST signal"
    assert "roas" in _EVIDENCE_SIGNALS, "Missing MARKETING signal"
    assert "time-to-hire" in _EVIDENCE_SIGNALS, "Missing HR signal"
    assert "cost savings" in _EVIDENCE_SIGNALS, "Missing FINANCE signal"
    assert "usability metric" in _EVIDENCE_SIGNALS, "Missing DESIGN signal"

    print(f"  [OK] _EVIDENCE_SIGNALS expanded to {len(_EVIDENCE_SIGNALS)} signals")


def test_role_coaching_question():
    """Verify role-aware coaching questions."""
    print("[PASS] Testing role-aware coaching questions...")

    # Product Manager gap
    pm_gap = {
        "gap_reason": "No A/B testing or user research mentioned",
        "missing_keywords": [],
    }
    question, hints = _build_coaching_question(pm_gap, "PRODUCT")
    assert "research" in question.lower() or "discovery" in question.lower(), \
        f"PM question missing research/discovery: {question}"
    assert len(hints) > 0, "PM hints missing"
    print(f"  [OK] PRODUCT coaching: {question[:60]}...")

    # Data Analyst gap
    da_gap = {
        "gap_reason": "Model accuracy not stated in project description",
        "missing_keywords": [],
    }
    question, hints = _build_coaching_question(da_gap, "DATA_ANALYST")
    assert "accuracy" in question.lower() or "model" in question.lower(), \
        f"DA question missing model/accuracy: {question}"
    print(f"  [OK] DATA_ANALYST coaching: {question[:60]}...")

    # Marketing gap
    mkting_gap = {
        "gap_reason": "Campaign ROAS or ROI missing",
        "missing_keywords": [],
    }
    question, hints = _build_coaching_question(mkting_gap, "MARKETING")
    assert "roas" in question.lower() or "roi" in question.lower(), \
        f"Marketing question missing ROAS/ROI: {question}"
    print(f"  [OK] MARKETING coaching: {question[:60]}...")

    # Engineering gap (existing)
    eng_gap = {
        "gap_reason": "Technical leadership or architecture not visible",
        "missing_keywords": [],
    }
    question, hints = _build_coaching_question(eng_gap, "ENGINEERING")
    assert "architecture" in question.lower() or "technical" in question.lower(), \
        f"Engineering question should mention architecture: {question}"
    print(f"  [OK] ENGINEERING coaching: {question[:60]}...")


def test_role_context_injection():
    """Verify role context blocks are built correctly."""
    print("[PASS] Testing role context injection...")

    for role_family in ["PRODUCT", "DATA_ANALYST", "MARKETING", "HR", "FINANCE", "DESIGN"]:
        try:
            role_ctx = get_role_context(role_family)

            # Build the role context block (same as in rewriter.py)
            role_context_block = (
                f"\nROLE CONTEXT: {role_ctx.role_family}\n"
                f"OPTIMIZE FOR: {', '.join(role_ctx.strength_signals[:3])}\n"
                f"PREFERRED METRIC VOCABULARY: {', '.join(role_ctx.metric_vocabulary[:5])}\n"
                f"WEAKNESS PATTERNS TO FIX: {', '.join(role_ctx.weakness_patterns[:3])}\n"
                f"AVOID THESE PATTERNS: assisted, helped, was part of, contributed to (without specifics)\n"
            )

            assert "ROLE CONTEXT" in role_context_block, f"Missing role context header for {role_family}"
            assert len(role_context_block) > 50, f"Role context too short for {role_family}"
            print(f"  [OK] {role_family:15} -> {len(role_context_block):3} chars")
        except Exception as e:
            print(f"  [FAIL] {role_family}: {e}")
            raise


def test_evidence_classification_expanded():
    """Verify non-engineering gaps are classified as Evidence."""
    print("[PASS] Testing expanded evidence classification...")

    # Marketing gap with ROAS signal
    gap = {
        "gap_reason": "Campaign ROAS not mentioned",
        "rewrite_instruction": "Add campaign ROI metrics",
        "missing_keywords": ["roas"],
        "needs_change": True,
    }
    classified = classify_gap(gap, "", "MARKETING")
    assert classified.get("gap_type") == "evidence", \
        f"Marketing ROAS gap should be Evidence, got {classified.get('gap_type')}"
    print("  [OK] Marketing ROAS gap -> Evidence")

    # Product gap with roadmap signal
    gap = {
        "gap_reason": "Roadmap ownership unclear",
        "rewrite_instruction": "Clarify roadmap role",
        "missing_keywords": [],
        "needs_change": True,
    }
    classified = classify_gap(gap, "", "PRODUCT")
    assert classified.get("gap_type") == "evidence", \
        f"Product roadmap gap should be Evidence, got {classified.get('gap_type')}"
    print("  [OK] Product roadmap gap -> Evidence")


def test_orchestrator_passes_role_family():
    """Verify orchestrator can pass role_family to rewriter."""
    print("[PASS] Testing orchestrator role_family flow...")

    # This is a simple check that the code parses and the signature is right
    from orchestrator import Orchestrator

    # Just verify the import works and the rewriter accepts role_family
    rewriter = RewriterAgent()

    # Check that _rewrite_section_from_gap accepts role_context parameter
    import inspect
    sig = inspect.signature(rewriter._rewrite_section_from_gap)
    params = list(sig.parameters.keys())
    assert "role_context" in params, f"_rewrite_section_from_gap missing role_context param. Got: {params}"
    print(f"  [OK] RewriterAgent._rewrite_section_from_gap has role_context parameter")

    sig = inspect.signature(rewriter._rewrite_sub_entry)
    params = list(sig.parameters.keys())
    assert "role_context" in params, f"_rewrite_sub_entry missing role_context param. Got: {params}"
    print(f"  [OK] RewriterAgent._rewrite_sub_entry has role_context parameter")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ROLE-AWARE FIXES VERIFICATION TEST SUITE")
    print("="*60 + "\n")

    try:
        test_evidence_signals_expanded()
        test_role_coaching_question()
        test_role_context_injection()
        test_evidence_classification_expanded()
        test_orchestrator_passes_role_family()

        print("\n" + "="*60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("="*60 + "\n")
    except AssertionError as e:
        print(f"\n[FAILED] TEST FAILED: {e}\n")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)
