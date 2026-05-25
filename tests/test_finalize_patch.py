"""Tests for rewriter sub-entry patch finalization."""

from backend.agents.rewriter import _finalize_sub_entry_patch
from backend.schemas.common import PatchOp, ResumePatch
from engine.patch_engine import PatchEngine


def test_finalize_empty_original_uses_anchor():
    anchor = "Software Engineer | Acme Corp\n• Did things."
    patch_raw = {
        "op": "replace_text",
        "original_text": "",
        "replacement_text": "Software Engineer | Acme Corp\n• Did better things.",
    }
    finalized = _finalize_sub_entry_patch(patch_raw, anchor, resume_text=anchor)
    assert finalized is not None
    assert finalized["original_text"] == anchor

    engine = PatchEngine(anchor)
    patch = ResumePatch(**{**finalized, "patch_id": "t1", "status": "pending"})
    outcome = engine.apply_with_result(patch)
    assert outcome["applied"] is True
    assert outcome["found_in_doc"] is True


def test_finalize_drops_patch_without_replacement():
    assert _finalize_sub_entry_patch({"original_text": "x"}, "anchor") is None
