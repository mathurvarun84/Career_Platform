"""Tests for FixPlanBuilder — contract tests for the single action contract."""
import pytest
from backend.engine.fix_plan_builder import build_fix_plan
from backend.schemas.common import FixKind


def _make_patch(patch_id, section, sub_entry_id, original, replacement):
    """Minimal ResumePatch-like object."""
    class P:
        pass
    p = P()
    p.patch_id = patch_id
    p.section = section
    p.sub_entry_id = sub_entry_id
    p.op = "replace_text"
    p.original_text = original
    p.replacement_text = replacement
    p.fix_rationale = ""
    p.issue_detected = ""
    return p


def _make_fix(section, entry_id, confidence, gap_type, sub_label=None,
              gap_reason="Missing X", requires_user_input=False, coaching_question=None):
    return {
        "section": section,
        "entry_id": entry_id,
        "entry_id_confidence": confidence,
        "sub_label": sub_label,
        "gap_reason": gap_reason,
        "gap_type": gap_type,
        "rewrite_instruction": "Rewrite to mention X",
        "missing_keywords": ["X"],
        "needs_change": True,
        "requires_user_input": requires_user_input,
        "coaching_question": coaching_question,
        "coaching_hint": [],
        "resume_grounded_hints": [],
        "auto_apply": False,
        "original_text": "Led team projects",
        "section_gap_id": f"{section}|0",
    }


class TestFixKindDispatch:
    def test_surgical_patch_kind(self):
        fix = _make_fix("experience", "flipkart_em_2020", "canonical", "structural")
        patch = _make_patch("p1", "experience", "flipkart_em_2020", "Led team", "Led architecture reviews")
        plan = build_fix_plan([fix], [patch])
        assert len(plan) == 1
        assert plan[0]["kind"] == FixKind.SURGICAL_PATCH.value
        assert plan[0]["patch_id"] == "p1"

    def test_coaching_kind_evidence_gap(self):
        fix = _make_fix("experience", "flipkart_em_2020", "canonical", "evidence",
                        requires_user_input=True, coaching_question="Describe your architecture ownership")
        patch = _make_patch("p1", "experience", "flipkart_em_2020", "Led team", "Led architecture reviews")
        plan = build_fix_plan([fix], [patch])
        # Coaching wins over surgical_patch even when a patch exists
        assert plan[0]["kind"] == FixKind.COACHING.value
        assert plan[0]["patch_id"] is None

    def test_surface_keyword_kind(self):
        fix = _make_fix("skills", None, "none", "surface", gap_reason="Missing Kafka keyword")
        plan = build_fix_plan([fix], [])
        assert plan[0]["kind"] == FixKind.SURFACE_KEYWORD.value

    def test_info_only_when_no_action_data(self):
        fix = _make_fix("experience", None, "none", "structural", gap_reason="No change needed")
        fix["rewrite_instruction"] = "No change needed"  # identical to gap_reason
        fix["patch_text"] = ""
        fix["suggested_text"] = ""
        plan = build_fix_plan([fix], [])
        assert plan[0]["kind"] == FixKind.INFO_ONLY.value


class TestEntryIdIsolation:
    def test_canonical_entry_id_matches_patch(self):
        fix = _make_fix("experience", "flipkart_em_2020", "canonical", "structural")
        patch = _make_patch("p1", "experience", "flipkart_em_2020", "Led team", "Led architecture reviews")
        plan = build_fix_plan([fix], [patch])
        assert plan[0]["patch_id"] == "p1"

    def test_derived_entry_id_does_not_match_patch(self):
        """Derived entry_id must not trigger a patch lookup — prevents wrong-company bleed."""
        fix = _make_fix("experience", "cleartax_pm_2022", "derived", "structural",
                        sub_label="Cleartax — PM (2022–2023)")
        patch = _make_patch("p2", "experience", "cleartax_pm_2022", "Built features", "Shipped X")
        plan = build_fix_plan([fix], [patch])
        # Derived confidence → no exact lookup → no patch → kind is REWRITE_BLOCK or INFO_ONLY
        assert plan[0]["patch_id"] is None

    def test_wrong_company_patch_never_bleeds(self):
        """Flipkart fix must not get Cleartax patch — the exact Flipkart/Cleartax bug."""
        flipkart_fix = _make_fix("experience", "flipkart_em_2020", "canonical", "structural")
        cleartax_patch = _make_patch("p_ct", "experience", "cleartax_pm_2022",
                                     "Built Cleartax feature", "Shipped Cleartax X")
        plan = build_fix_plan([flipkart_fix], [cleartax_patch])
        assert plan[0]["patch_id"] is None  # No bleed from different entry_id


class TestPatchIdResolvability:
    def test_surgical_patch_id_resolves_in_patches_array(self):
        """
        Every fix_plan item with kind=surgical_patch must have a patch_id
        that resolves in the patches[] array. This is the contract that
        prevents the Flipkart/Cleartax routing bug from recurring.
        """
        fixes = [
            _make_fix("experience", "flipkart_em_2020", "canonical", "structural"),
            _make_fix("experience", "amazon_sde_2018", "canonical", "structural"),
        ]
        patches = [
            _make_patch("p1", "experience", "flipkart_em_2020", "Led team", "Led arch reviews"),
            _make_patch("p2", "experience", "amazon_sde_2018", "Built service", "Architected service"),
        ]
        plan = build_fix_plan(fixes, patches)
        patch_ids = {p.patch_id for p in patches}
        for item in plan:
            if item["kind"] == FixKind.SURGICAL_PATCH.value:
                assert item["patch_id"] is not None, f"surgical_patch {item['fix_id']} has no patch_id"
                assert item["patch_id"] in patch_ids, (
                    f"surgical_patch {item['fix_id']} references patch_id={item['patch_id']} "
                    f"which does not exist in patches[]"
                )


class TestCrossTabIdentity:
    def test_same_fix_id_in_gap_and_fixes_slice(self):
        """
        Every fix_id in the fixes slice (kind != info_only) must also be present
        in the full plan (gap slice). This prevents 'visible in Gap, missing in Fixes'.
        """
        fixes = [
            _make_fix("experience", "flipkart_em_2020", "canonical", "structural"),
            _make_fix("skills", None, "none", "surface", gap_reason="Missing Kafka"),
        ]
        patches = [
            _make_patch("p1", "experience", "flipkart_em_2020", "Led team", "Led arch reviews"),
        ]
        plan = build_fix_plan(fixes, patches)
        all_ids = {item["fix_id"] for item in plan}
        fixes_slice_ids = {item["fix_id"] for item in plan if item["kind"] != "info_only"}
        assert fixes_slice_ids.issubset(all_ids)

    def test_no_duplicate_fix_ids(self):
        fixes = [
            _make_fix("experience", "flipkart_em_2020", "canonical", "structural"),
            _make_fix("experience", "flipkart_em_2020", "canonical", "structural"),  # duplicate
        ]
        plan = build_fix_plan(fixes, [])
        ids = [item["fix_id"] for item in plan]
        assert len(ids) == len(set(ids))


class TestSectionGapIdPropagation:
    def test_section_gap_id_copied_to_plan(self):
        fix = _make_fix("experience", "flipkart_em_2020", "canonical", "structural")
        fix["section_gap_id"] = "experience|0"
        plan = build_fix_plan([fix], [])
        assert plan[0]["section_gap_id"] == "experience|0"
