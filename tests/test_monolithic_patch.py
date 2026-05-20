"""Tests for monolithic section patch emission (summary/skills)."""

import json
from pathlib import Path

from backend.agents.rewriter import _build_monolithic_section_patch
from engine.patch_engine import PatchEngine


def test_summary_patch_applies_against_resume():
    data = json.loads(
        Path("tempjsons/c3e843db-ee9b-4920-b255-938f1809eccb_before_fix.json").read_text(
            encoding="utf-8"
        )
    )
    resume = data["resume_text_original"]
    from parser import _extract_section_blocks

    original = _extract_section_blocks(resume)["summary"]
    replacement = original.replace(
        "distributed backend platforms",
        "distributed backend platforms and architecture evaluation",
    )
    patch_raw = _build_monolithic_section_patch(
        "summary",
        original,
        {"balanced": replacement},
        {"rewrite_instruction": "Add architecture evaluation"},
        resume,
    )
    assert patch_raw is not None
    from backend.schemas.common import ResumePatch, PatchOp

    patch = ResumePatch(**patch_raw, status="pending")
    engine = PatchEngine(resume)
    assert engine.apply(patch)
    assert "architecture evaluation" in engine.get_current_text()
