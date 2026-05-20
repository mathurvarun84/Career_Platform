"""Tests for PatchEngine separator normalisation, re-anchoring, and classify_patch."""

from backend.schemas.common import PatchOp, PatchRisk, ResumePatch
from engine.patch_engine import (
    PatchEngine,
    _find_normalised_span,
    _has_hallucinated_sentences,
    classify_patch,
)


def test_normalised_span_bullet_newline_mismatch():
    doc = "Role header\n• First bullet about platform.\n• Second bullet here."
    needle = "Role header • First bullet about platform."
    span = _find_normalised_span(needle, doc)
    assert span is not None
    start, end = span
    assert doc[start:end] == "Role header\n• First bullet about platform."


def test_three_bullet_entry_inline_vs_newline_separators():
    """Patch original uses • between bullets; resume uses newlines."""
    doc = (
        "Engineering Manager | Acme\n"
        "• Bullet one about platform.\n"
        "• Bullet two about scale.\n"
        "• Bullet three about impact."
    )
    original = (
        "Engineering Manager | Acme • Bullet one about platform. "
        "• Bullet two about scale. • Bullet three about impact."
    )
    patch = ResumePatch(
        patch_id="exp3",
        op=PatchOp.REPLACE_TEXT,
        section="experience",
        original_text=original,
        replacement_text=(
            "Engineering Manager | Acme\n"
            "• Bullet one IMPROVED.\n"
            "• Bullet two about scale.\n"
            "• Bullet three about impact."
        ),
        status="pending",
    )
    engine = PatchEngine(doc)
    outcome = engine.apply_with_result(patch)
    assert outcome["applied"] is True
    assert outcome["found_in_doc"] is True
    assert "Bullet one IMPROVED" in engine.get_current_text()


def test_apply_with_result_invariant():
    patch = ResumePatch(
        patch_id="inv1",
        op=PatchOp.REPLACE_TEXT,
        original_text="MISSING TEXT",
        replacement_text="SHOULD NOT STAY",
        status="pending",
    )
    engine = PatchEngine("hello world")
    outcome = engine.apply_with_result(patch)
    assert outcome["applied"] is False
    assert outcome["found_in_doc"] is False
    assert "SHOULD NOT STAY" not in engine.get_current_text()


def test_rollback_then_reapply_three_bullets():
    doc = (
        "• Alpha bullet here.\n"
        "• Beta bullet here.\n"
        "• Gamma bullet here."
    )
    p1 = ResumePatch(
        patch_id="r1",
        op=PatchOp.REPLACE_TEXT,
        original_text="• Alpha bullet here. • Beta bullet here.",
        replacement_text="• Alpha UPDATED.\n• Beta bullet here.",
        status="pending",
    )
    engine = PatchEngine(doc)
    assert engine.apply_with_result(p1)["found_in_doc"]
    assert engine.rollback("r1")
    assert "UPDATED" not in engine.get_current_text()
    p1.status = "pending"
    assert engine.apply_with_result(p1)["found_in_doc"]


def test_reanchor_updates_pending_original_text():
    engine = PatchEngine("header OLD block\nfooter PREFIX OLD SUFFIX")
    applied_patch = ResumePatch(
        patch_id="p1",
        op=PatchOp.REPLACE_TEXT,
        original_text="OLD",
        replacement_text="NEW",
        status="applied",
    )
    pending = ResumePatch(
        patch_id="p2",
        op=PatchOp.REPLACE_TEXT,
        original_text="footer PREFIX OLD SUFFIX",
        replacement_text="footer PREFIX NEW SUFFIX",
        status="pending",
    )
    engine._reanchor_remaining(applied_patch, [pending])
    assert pending.original_text == "footer PREFIX NEW SUFFIX"


def test_apply_batch_two_non_overlapping_bullets():
    doc = "• First bullet alpha.\n• Second bullet beta."
    p1 = ResumePatch(
        patch_id="p1",
        op=PatchOp.REPLACE_TEXT,
        original_text="First bullet alpha.",
        replacement_text="First bullet ALPHA.",
        status="pending",
    )
    p2 = ResumePatch(
        patch_id="p2",
        op=PatchOp.REPLACE_TEXT,
        original_text="Second bullet beta.",
        replacement_text="Second bullet BETA.",
        status="pending",
    )
    engine = PatchEngine(doc)
    applied = engine.apply_batch([p1, p2])
    assert applied == ["p1", "p2"]
    assert "ALPHA" in engine.get_current_text()
    assert "BETA" in engine.get_current_text()


def test_classify_hallucination_before_expansion():
    patch = ResumePatch(
        op=PatchOp.REPLACE_TEXT,
        original_text="Built APIs for payments.",
        replacement_text=(
            "Built APIs for payments. Designed rendering pipeline."
        ),
        status="pending",
    )
    out = classify_patch(patch)
    assert out.risk == PatchRisk.NEEDS_CONFIRMATION
    assert out.hallucination_risk is True


def test_classify_paraphrase_not_expansion_flag():
    patch = ResumePatch(
        op=PatchOp.REPLACE_TEXT,
        original_text="Led team of five engineers on backend.",
        replacement_text="Led team of five engineers on backend platform work.",
        status="pending",
    )
    out = classify_patch(patch)
    assert out.risk == PatchRisk.SAFE


def test_rebuild_ranges_after_rollback():
    doc = "alpha TARGET beta"
    patch = ResumePatch(
        patch_id="rb1",
        op=PatchOp.REPLACE_TEXT,
        original_text="TARGET",
        replacement_text="REPLACED",
        status="pending",
    )
    engine = PatchEngine(doc)
    assert engine.apply(patch)
    assert engine.rollback("rb1")
    assert engine.get_current_text() == doc
    patch2 = ResumePatch(
        patch_id="rb2",
        op=PatchOp.REPLACE_TEXT,
        original_text="beta",
        replacement_text="BETA2",
        status="pending",
    )
    assert engine.apply(patch2)


def test_has_hallucinated_sentences_two_word_fragment_skipped():
    assert not _has_hallucinated_sentences(
        "Built APIs.",
        "Built APIs. Fast delivery.",
    )


def test_has_hallucinated_sentences_grounded_three_token_overlap():
    assert not _has_hallucinated_sentences(
        "Built rendering pipeline APIs for video.",
        "Built rendering pipeline APIs for video. Designed rendering pipeline.",
    )
