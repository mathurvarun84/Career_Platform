"""
Contract tests for GapAnalyzer output shape.

These tests validate structural invariants on the data that flows from
gap_analyzer → frontend. They use realistic fixture data and test the
Python-side pipeline (classify_section_gaps + priority_fixes_from_gaps)
without making any LLM calls.

Why: unit tests on classify_gap pass but cross-layer mismatches (e.g. sub_label
missing on an experience fix) are invisible until they produce wrong UI content.
"""

import pytest
from backend.agents.gap_analyzer import (
    classify_section_gaps,
    priority_fixes_from_gaps,
    _dedupe_priority_fixes,
)


# ---------------------------------------------------------------------------
# Fixtures — realistic gap output for a senior EM applying to Meesho/Razorpay
# ---------------------------------------------------------------------------

EXPERIENCE_SECTION_GAPS = [
    {
        "section": "experience",
        "needs_change": True,
        "gap_reason": "No Kafka/real-time streaming mentioned",
        "rewrite_instruction": "Mention stream processing explicitly",
        "missing_keywords": ["Kafka", "streaming"],
        "original_content": "Led platform team at Flipkart. Built data pipelines.",
        "present_in_resume": True,
        "sub_changes": [
            {
                "sub_id": "flipkart_em",
                "sub_label": "Flipkart — EM (2021–present)",
                "needs_change": True,
                "gap_reason": "No streaming tech mentioned",
                "rewrite_instruction": "Add Kafka/streaming context",
                "missing_keywords": ["Kafka"],
                "original_text": "Led platform team. Built data pipelines.",
            },
            {
                "sub_id": "razorpay_se",
                "sub_label": "Razorpay — SE (2019–2021)",
                "needs_change": True,
                "gap_reason": "Lacks collaboration signals",
                "rewrite_instruction": "Highlight cross-functional collaboration",
                "missing_keywords": ["collaboration"],
                "original_text": "Built payment gateway integrations.",
            },
        ],
    },
    {
        "section": "skills",
        "needs_change": True,
        "gap_reason": "Missing keyword for Kubernetes",
        "rewrite_instruction": "Add Kubernetes to skills section",
        "missing_keywords": ["Kubernetes"],
        "original_content": "Python, Java, AWS",
        "present_in_resume": True,
        "sub_changes": [],
    },
    {
        "section": "summary",
        "needs_change": True,
        "gap_reason": "No professional summary",
        "rewrite_instruction": "Write a 3-5 sentence summary",
        "missing_keywords": ["engineering leadership", "scalability"],
        "original_content": "",
        "present_in_resume": False,
        "sub_changes": [],
    },
    {
        "section": "education",
        "needs_change": False,
        "gap_reason": "No change needed",
        "rewrite_instruction": "",
        "missing_keywords": [],
        "original_content": "B.Tech Computer Science, IIT Delhi",
        "present_in_resume": True,
        "sub_changes": [],
    },
]

REQUIRED_FIX_FIELDS = {
    "section", "gap_reason", "rewrite_instruction", "missing_keywords",
    "needs_change", "gap_type", "requires_user_input", "auto_apply", "sub_label",
}


@pytest.fixture
def classified_gaps():
    return classify_section_gaps(EXPERIENCE_SECTION_GAPS, resume_text="")


@pytest.fixture
def priority_fixes(classified_gaps):
    return priority_fixes_from_gaps(classified_gaps)


# ---------------------------------------------------------------------------
# Invariant 1: every fix has all required fields
# ---------------------------------------------------------------------------

def test_every_fix_has_required_fields(priority_fixes):
    for fix in priority_fixes:
        missing = REQUIRED_FIX_FIELDS - set(fix.keys())
        assert not missing, f"Fix missing fields {missing}: {fix}"


# ---------------------------------------------------------------------------
# Invariant 2: gap_type is always a valid enum value
# ---------------------------------------------------------------------------

def test_gap_type_is_valid_enum(priority_fixes):
    valid = {"surface", "structural", "evidence"}
    for fix in priority_fixes:
        assert fix["gap_type"] in valid, (
            f"Invalid gap_type '{fix['gap_type']}' in fix: {fix['section']}"
        )


# ---------------------------------------------------------------------------
# Invariant 3: sub_label key exists on every fix (may be None)
# ---------------------------------------------------------------------------

def test_sub_label_key_always_present(priority_fixes):
    for fix in priority_fixes:
        assert "sub_label" in fix, (
            f"sub_label key missing from fix: {fix['section']} / {fix.get('gap_reason')}"
        )


# ---------------------------------------------------------------------------
# Invariant 4: experience sub_changes each produce a fix with the correct sub_label
# ---------------------------------------------------------------------------

def test_experience_sub_changes_expand_to_individual_fixes(priority_fixes):
    experience_fixes = [f for f in priority_fixes if f["section"] == "experience"]
    sub_labels = [f["sub_label"] for f in experience_fixes]
    assert "Flipkart — EM (2021–present)" in sub_labels, (
        "Expected Flipkart sub_label in experience fixes"
    )
    assert "Razorpay — SE (2019–2021)" in sub_labels, (
        "Expected Razorpay sub_label in experience fixes"
    )


# ---------------------------------------------------------------------------
# Invariant 5: surface gaps always have auto_apply=True and no coaching_question
# ---------------------------------------------------------------------------

def test_surface_gaps_are_auto_apply(priority_fixes):
    for fix in priority_fixes:
        if fix["gap_type"] == "surface":
            assert fix["auto_apply"] is True, (
                f"Surface gap should have auto_apply=True: {fix['section']}"
            )
            assert not fix.get("coaching_question"), (
                f"Surface gap should not have coaching_question: {fix['section']}"
            )


# ---------------------------------------------------------------------------
# Invariant 6: evidence gaps always have coaching_question set
# ---------------------------------------------------------------------------

def test_evidence_gaps_have_coaching_question(priority_fixes):
    for fix in priority_fixes:
        if fix["gap_type"] == "evidence":
            assert fix.get("coaching_question"), (
                f"Evidence gap missing coaching_question: {fix['section']} / {fix.get('gap_reason')}"
            )
            assert fix["requires_user_input"] is True, (
                f"Evidence gap should require user input: {fix['section']}"
            )


# ---------------------------------------------------------------------------
# Invariant 7: max 12 fixes returned
# ---------------------------------------------------------------------------

def test_max_12_fixes_returned(priority_fixes):
    assert len(priority_fixes) <= 12, (
        f"priority_fixes_from_gaps returned {len(priority_fixes)} fixes, expected ≤12"
    )


# ---------------------------------------------------------------------------
# Invariant 8: no fix has needs_change=False
# ---------------------------------------------------------------------------

def test_no_fix_has_needs_change_false(priority_fixes):
    for fix in priority_fixes:
        assert fix["needs_change"] is True, (
            f"Fix with needs_change=False should not appear in priority_fixes: {fix['section']}"
        )


# ---------------------------------------------------------------------------
# Invariant 9: Razorpay and Flipkart fixes are independent — different sub_labels
# ---------------------------------------------------------------------------

def test_experience_sub_labels_are_distinct(priority_fixes):
    experience_fixes = [f for f in priority_fixes if f["section"] == "experience"]
    sub_labels = [f["sub_label"] for f in experience_fixes]
    # All sub_labels must be unique — no two experience cards for the same entry
    assert len(sub_labels) == len(set(sub_labels)), (
        f"Duplicate sub_labels in experience fixes: {sub_labels}"
    )


def test_dedupe_collapses_same_sub_label_keyword_gaps():
    """Multiple sub_changes for one role block → one fix card."""
    raw_fixes = [
        {
            "section": "experience",
            "sub_label": "Razorpay | EM",
            "gap_reason": "Missing fintech keyword",
            "missing_keywords": ["fintech"],
            "gap_type": "surface",
            "auto_apply": True,
            "needs_change": True,
            "rewrite_instruction": "Add fintech",
        },
        {
            "section": "experience",
            "sub_label": "Razorpay | EM",
            "gap_reason": "Missing payment systems keyword",
            "missing_keywords": ["payment systems"],
            "gap_type": "surface",
            "auto_apply": True,
            "needs_change": True,
            "rewrite_instruction": "Add payment systems",
        },
        {
            "section": "experience",
            "sub_label": "Razorpay | EM",
            "gap_reason": "Missing commerce keyword",
            "missing_keywords": ["commerce"],
            "gap_type": "surface",
            "auto_apply": True,
            "needs_change": True,
            "rewrite_instruction": "Add commerce",
        },
    ]
    deduped = _dedupe_priority_fixes(raw_fixes)
    assert len(deduped) == 1
    assert set(deduped[0]["missing_keywords"]) == {"fintech", "payment systems", "commerce"}
