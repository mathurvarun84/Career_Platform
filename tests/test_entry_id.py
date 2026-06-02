"""Tests for stable entry_id derivation and propagation."""

import pytest

from backend.utils.entry_id import derive_entry_id
from backend.schemas.common import SubEntry


class TestDeriveEntryId:
    def test_flipkart_em_label(self):
        label = "Engineering Manager | Flipkart — Bengaluru, KA Sep 2020 – Present"
        entry_id = derive_entry_id(label)
        assert "flipkart" in entry_id
        assert "2020" in entry_id

    def test_oracle_label(self):
        label = "ORACLE | SENIOR SOFTWARE ENGINEER"
        entry_id = derive_entry_id(label)
        assert "oracle" in entry_id

    def test_same_label_same_id(self):
        label = "Engineering Manager | Flipkart — Bengaluru"
        assert derive_entry_id(label) == derive_entry_id(label)

    def test_empty_label(self):
        assert derive_entry_id("") == "entry_unknown"


class TestSubEntryAutoId:
    def test_auto_generates_entry_id(self):
        entry = SubEntry(
            label="ORACLE | SENIOR SOFTWARE ENGINEER",
            verbatim_text="ORACLE | SENIOR SOFTWARE ENGINEER\n• Built feature",
        )
        assert entry.entry_id
        assert "oracle" in entry.entry_id

    def test_preserves_explicit_entry_id(self):
        entry = SubEntry(
            label="Flipkart — EM",
            entry_id="flipkart_em_2020",
            verbatim_text="Flipkart text",
        )
        assert entry.entry_id == "flipkart_em_2020"


def test_no_jd_sub_changes_carry_entry_id():
    """Orchestrator no-JD path must propagate entry_id into sub_changes."""
    from orchestrator import Orchestrator
    from tests.test_no_jd_rewrite import A1_OUTPUT_NO_SUMMARY, _make_resume_sections

    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    result = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)

    exp_gap = next(g for g in result["section_gaps"] if g["section"] == "experience")
    assert exp_gap["sub_changes"], "Expected experience sub_changes from Oracle weakness"

    for sub in exp_gap["sub_changes"]:
        assert sub.get("entry_id"), f"sub_change missing entry_id: {sub}"
        assert sub["entry_id"] == sub["sub_id"]
        assert sub["sub_label"]


def test_priority_fixes_carry_entry_id():
    """priority_fixes_from_gaps must preserve entry_id from sub_changes."""
    from backend.agents.gap_analyzer import priority_fixes_from_gaps

    section_gaps = [{
        "section": "experience",
        "needs_change": True,
        "gap_reason": "Missing metrics",
        "rewrite_instruction": "Add metrics",
        "missing_keywords": [],
        "gap_type": "structural",
        "sub_changes": [{
            "sub_id": "oracle_senior_software",
            "entry_id": "oracle_senior_software",
            "sub_label": "ORACLE | SENIOR SOFTWARE ENGINEER",
            "needs_change": True,
            "gap_reason": "Oracle bullets lack scale → add QPS metrics",
            "rewrite_instruction": "add QPS metrics",
            "missing_keywords": [],
            "original_text": "ORACLE text",
        }],
    }]
    fixes = priority_fixes_from_gaps(section_gaps)
    assert len(fixes) == 1
    assert fixes[0]["entry_id"] == "oracle_senior_software"
