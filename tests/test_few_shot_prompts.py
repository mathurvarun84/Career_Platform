"""Tests for role-aware few-shot prompt library."""

from backend.few_shot_prompts import (
    build_few_shot_block,
    build_role_gap_addendum,
    detect_role_family,
    get_gap_patterns,
    get_role_context,
)


def test_detect_engineering_from_resume():
    text = "Senior Software Engineer at Razorpay. Built microservices on Kubernetes."
    assert detect_role_family(text) == "ENGINEERING"


def test_detect_product_from_title():
    text = "Led roadmap and OKRs for checkout."
    assert detect_role_family(text, "Senior Product Manager") == "PRODUCT"


def test_get_role_context_fallback():
    ctx = get_role_context("UNKNOWN")
    assert ctx.role_family == "ENGINEERING"


def test_build_few_shot_block_includes_role():
    block = build_few_shot_block("PRODUCT", num_examples=2)
    assert "ROLE-SPECIFIC CONTEXT: PRODUCT" in block
    assert "PRODUCT MANAGEMENT" in block


def test_gap_patterns_cover_all_families():
    for family in (
        "ENGINEERING",
        "PRODUCT",
        "MARKETING",
        "DATA_ANALYST",
        "HR",
        "FINANCE",
        "DESIGN",
    ):
        patterns = get_gap_patterns(family)
        assert patterns["critical_gaps"]
        assert patterns["quick_wins"]


def test_build_role_gap_addendum():
    text = build_role_gap_addendum("HR")
    assert "ROLE-SPECIFIC GAP PATTERNS (HR)" in text
    assert "time-to-hire" in text.lower() or "attrition" in text.lower()
