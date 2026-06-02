"""Tests for build_complete_priority_fixes — single authoritative fix source."""

from backend.agents.gap_analyzer import (
    _build_overview_weakness_fix,
    _match_eval_change,
    build_complete_priority_fixes,
    enrich_priority_fixes_from_eval_changes,
)


def _experience_gap_with_sub(sub_label: str, entry_id: str, gap_reason: str) -> dict:
    return {
        "section": "experience",
        "needs_change": True,
        "gap_reason": gap_reason,
        "rewrite_instruction": "add metrics",
        "missing_keywords": [],
        "gap_type": "structural",
        "sub_changes": [{
            "sub_id": entry_id,
            "entry_id": entry_id,
            "sub_label": sub_label,
            "needs_change": True,
            "gap_reason": gap_reason,
            "rewrite_instruction": "add metrics",
            "missing_keywords": [],
            "original_text": f"{sub_label}\n• bullet",
        }],
    }


def test_resume_only_backfills_uncovered_overview_weakness():
    """Overview items not in section_gaps must appear in priority_fixes."""
    section_gaps = [_experience_gap_with_sub(
        "ORACLE | SENIOR SOFTWARE ENGINEER",
        "oracle_senior_software",
        "Oracle bullets lack scale → add QPS metrics",
    )]
    overview = [
        "Oracle bullets lack scale → add QPS metrics",
        "Highlight cloud architecture work more prominently",
    ]
    fixes = build_complete_priority_fixes(
        section_gaps,
        overview_strings=overview,
        resume_only_mode=True,
        resume_sections={},
    )
    reasons = " ".join(f.get("gap_reason", "") for f in fixes).lower()
    assert "cloud architecture" in reasons or any(
        "cloud" in (f.get("gap_reason") or "").lower() for f in fixes
    )


def test_ats_issues_merged_when_not_in_gaps():
    """ATS issues not covered by gap fixes are added to priority_fixes."""
    section_gaps = [{
        "section": "summary",
        "needs_change": True,
        "gap_reason": "Summary lacks keywords",
        "rewrite_instruction": "Add keywords",
        "missing_keywords": [],
        "gap_type": "structural",
        "sub_changes": [],
    }]
    ats_issues = ["Improve bullet readability — sentences too long"]
    fixes = build_complete_priority_fixes(
        section_gaps,
        ats_issues=ats_issues,
        resume_only_mode=False,
    )
    assert any("readability" in (f.get("gap_reason") or "").lower() for f in fixes)


def test_jd_mode_filters_overview_overlap():
    """JD mode strips priority fixes whose gap_reason overlaps overview strings."""
    section_gaps = [{
        "section": "experience",
        "needs_change": True,
        "gap_reason": "Add quantified metrics to Oracle experience bullets",
        "rewrite_instruction": "Add metrics",
        "missing_keywords": [],
        "gap_type": "structural",
        "sub_changes": [],
    }]
    overview = ["Add quantified metrics to Oracle experience bullets"]
    fixes = build_complete_priority_fixes(
        section_gaps,
        overview_strings=overview,
        resume_only_mode=False,
    )
    assert not any(
        "oracle experience bullets" in (f.get("gap_reason") or "").lower()
        for f in fixes
    )


def test_overview_backfill_resolves_entry_id():
    """Resume-only overview backfill attaches entry_id from matched sub_entry."""
    resume_sections = {
        "experience": {
            "full_text": "FLIPKART\nAPTTUS",
            "sub_entries": [
                {
                    "label": "FLIPKART | Engineering Manager",
                    "entry_id": "flipkart_engineering_manager",
                    "verbatim_text": "FLIPKART | Engineering Manager\n• Led teams",
                },
            ],
        }
    }
    weakness = (
        "Flipkart EM bullets lack quantified latency/scale signals "
        "→ add system scale (QPS, users, SLA)"
    )
    fixes = build_complete_priority_fixes(
        [],
        overview_strings=[weakness],
        resume_only_mode=True,
        resume_sections=resume_sections,
    )
    assert len(fixes) == 1
    assert fixes[0].get("entry_id") == "flipkart_engineering_manager"
    assert fixes[0].get("sub_label") == "FLIPKART | Engineering Manager"


def test_identical_gap_reason_demoted_to_evidence_with_coaching():
    """Overview weakness without → split becomes evidence, not broken structural."""
    fix = _build_overview_weakness_fix(
        "Structure experience section for clearer role delineation",
        resume_only_mode=True,
        resume_sections={},
    )
    assert fix["gap_type"] == "evidence"
    assert fix["coaching_question"]
    assert not fix["coaching_question"].startswith("How would you address:")


def test_overview_backfill_populates_original_text_from_entry():
    resume_sections = {
        "experience": {
            "sub_entries": [{
                "label": "FLIPKART | Engineering Manager",
                "entry_id": "flipkart_engineering_manager",
                "verbatim_text": "FLIPKART | EM\n• Led checkout",
            }],
        }
    }
    fix = _build_overview_weakness_fix(
        "Flipkart EM bullets lack QPS → add throughput metrics",
        resume_only_mode=True,
        resume_sections=resume_sections,
    )
    assert "FLIPKART" in fix.get("original_text", "")
    assert fix.get("entry_id") == "flipkart_engineering_manager"


def test_eval_change_enriches_priority_fix_with_suggested_text():
    fixes = [{
        "section": "experience",
        "gap_reason": "Flipkart EM bullets lack QPS and scale metrics",
        "rewrite_instruction": "add throughput",
        "missing_keywords": [],
        "needs_change": True,
        "gap_type": "structural",
        "entry_id": "flipkart_engineering_manager",
    }]
    eval_changes = [{
        "change_id": 1,
        "location": {
            "section": "experience",
            "sub_location": "Engineering Manager at Flipkart, bullet 2",
        },
        "why": "Flipkart EM bullets lack QPS and scale metrics",
        "original_text": "• Improved checkout latency by 35%",
        "suggested_text": (
            "• Improved checkout latency by 35% serving 12K QPS peak traffic "
            "with 99.9% SLA across 50M monthly users"
        ),
        "keywords_added": ["QPS"],
    }]
    enriched = enrich_priority_fixes_from_eval_changes(fixes, eval_changes)
    assert len(enriched) == 1
    assert len(enriched[0]["rewrite_instruction"]) > 50
    assert enriched[0]["original_text"].startswith("• Improved")
    assert enriched[0]["gap_type"] == "structural"


def test_match_eval_change_by_company_token():
    changes = [{
        "change_id": 1,
        "location": {"section": "experience", "sub_location": "Flipkart EM bullet 3"},
        "why": "Missing scale metrics",
        "original_text": "bullet",
        "suggested_text": "x" * 60,
    }]
    matched = _match_eval_change(
        "Flipkart EM bullets 3-5 lack quantified user scale signals",
        changes,
    )
    assert matched is not None
    assert matched["change_id"] == 1
