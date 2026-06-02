"""Week 3 regression fixtures — Fixes tab contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.gap_analyzer import build_complete_priority_fixes, priority_fixes_from_gaps

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _entry_verbatim(resume: dict, entry_id: str) -> str:
    for entry in resume["resume_sections"]["experience"]["sub_entries"]:
        if entry.get("entry_id") == entry_id:
            return entry["verbatim_text"]
    return ""


class TestFixtureAMultiCompanyJd:
    """Multi-company JD — no cross-company contamination, no duplicate cards."""

    @pytest.fixture
    def data(self):
        return _load("fixture_a_multi_company_jd.json")

    def test_one_card_per_company_entry_id(self, data):
        fixes = data["gap"]["priority_fixes"]
        entry_ids = [f["entry_id"] for f in fixes if f.get("entry_id")]
        assert len(entry_ids) == 4
        assert len(entry_ids) == len(set(entry_ids))

    def test_before_text_belongs_to_own_company(self, data):
        companies = {
            "flipkart_engineering_manager_2020": "FLIPKART",
            "apttus_senior_consultant_2019": "APTTUS",
            "british_telecom_lead_software_2017": "BRITISH TELECOM",
            "mindtree_lead_software_2015": "MINDTREE",
        }
        for entry_id, marker in companies.items():
            verbatim = _entry_verbatim(data["resume"], entry_id)
            assert marker in verbatim.upper()

    def test_patches_scoped_by_sub_entry_id(self, data):
        patches = data["patches"]
        for patch in patches:
            assert patch.get("sub_entry_id")
            verbatim = _entry_verbatim(data["resume"], patch["sub_entry_id"])
            assert patch["original_text"] in verbatim

    def test_no_foreign_company_in_patch_replacement(self, data):
        foreign = {
            "flipkart_engineering_manager_2020": ["apttus", "british telecom", "mindtree"],
            "apttus_senior_consultant_2019": ["flipkart", "british telecom", "mindtree"],
            "british_telecom_lead_software_2017": ["flipkart", "apttus", "mindtree"],
            "mindtree_lead_software_2015": ["flipkart", "apttus", "british telecom"],
        }
        for patch in data["patches"]:
            entry_id = patch["sub_entry_id"]
            replacement = patch["replacement_text"].lower()
            for other in foreign[entry_id]:
                assert other not in replacement


class TestFixtureBResumeOnly:
    """Resume-only — scoped InfoOnly cards, no generic echo titles."""

    @pytest.fixture
    def data(self):
        return _load("fixture_b_resume_only.json")

    def test_resume_only_mode_flag(self, data):
        assert data["gap"]["resume_only_mode"] is True

    def test_weakness_cards_use_arrow_format(self, data):
        fixes = [
            f for f in data["gap"]["priority_fixes"]
            if "→" in f.get("gap_reason", "")
        ]
        assert len(fixes) >= 2

    def test_smartviz_scope_not_generic_echo(self, data):
        fix = next(
            f for f in data["gap"]["priority_fixes"]
            if f.get("entry_id") == "smart_viz_director_2018"
        )
        assert "Smart Viz X" in fix["gap_reason"]
        assert fix["gap_reason"] != fix.get("sub_label")
        assert "→" in fix["gap_reason"]

    def test_build_complete_priority_fixes_includes_overview_backfill(self, data):
        built = build_complete_priority_fixes(
            [],
            overview_strings=(
                list(data["resume"].get("weaknesses") or [])
                + list(data["resume"].get("improvement_areas") or [])
            ),
            resume_only_mode=True,
            resume_sections=data["resume"]["resume_sections"],
        )
        assert any("Smart Viz X" in (f.get("gap_reason") or "") for f in built)

    def test_no_change_replacement_not_actionable(self, data):
        from backend.agents.gap_analyzer import _is_actionable_gap

        refusal = {
            "section": "experience",
            "gap_reason": "Looks good",
            "rewrite_instruction": "No changes required; original entry contains sufficient metrics",
            "needs_change": True,
            "missing_keywords": [],
        }
        assert _is_actionable_gap(refusal) is False


class TestFixtureCUnderqualifiedGate:
    """Role fit gate — tabs locked, no fix cards."""

    @pytest.fixture
    def data(self):
        return _load("fixture_c_underqualified_gate.json")

    def test_underqualified_fitness(self, data):
        assert data["role_fit"]["fitness"] == "underqualified"

    def test_role_fit_gate_empty_priority_fixes(self, data):
        assert data["gap"].get("role_fit_gate") is True
        assert data["gap"]["priority_fixes"] == []

    def test_priority_fixes_from_gaps_empty(self, data):
        assert priority_fixes_from_gaps(data["gap"]["section_gaps"]) == []

    def test_no_patches_or_rewrites(self, data):
        assert data["patches"] == []
        assert data["rewrites"] is None
        assert data["sim"] is None
