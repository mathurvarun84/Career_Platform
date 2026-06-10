"""
FixPlanBuilder — single action contract for the Fixes tab.

Takes already-classified priority_fixes (from build_complete_priority_fixes) and
classified_patches (from orchestrator patch classification) and emits fix_plan[]:
one FixPlanItem per actionable unit, with kind set deterministically and
patch_id resolved by exact entry_id match only.

Rules:
  1. fix_id = "{section}|{entry_id}" when entry_id present and confidence=canonical,
              "{section}|{slug(sub_label)}" when entry_id absent or confidence=derived,
              "{section}|__section__" for section-level fixes
  2. Patch lookup: exact sub_entry_id == entry_id match ONLY when entry_id_confidence=canonical.
     Derived entry_ids and absent entry_ids never trigger a patch lookup by entry_id.
     Section-level fixes (entry_id absent) use section-wide patch pool (patches with no
     sub_entry_id), first match only.
  3. kind dispatch (in priority order):
     - requires_user_input=True OR gap_type=evidence → COACHING  (even if patch exists)
     - patch found with usable original+replacement → SURGICAL_PATCH
     - gap_type=surface → SURFACE_KEYWORD
     - after_text resolvable from fix fields → REWRITE_BLOCK
     - otherwise → INFO_ONLY
  4. before_text: patch.original_text > A1 sub_entry verbatim_text (by entry_id) > None
  5. after_text: stripped of ##COMPANY##...##END_HEADER## markers
  6. Dedup by fix_id: first occurrence wins
  7. Coaching items never have patch_id set (they require user input first)
"""

from __future__ import annotations

import logging
import re
from typing import Any

_COMPANY_HEADER_RE = re.compile(r"##COMPANY##[^#]*##ROLE##[^#]*##END_HEADER##[ \t]*")
_STRAY_MARKER_RE = re.compile(r"##(?:COMPANY|ROLE|END_HEADER)##")


def _strip_rewrite_markers(text: str) -> str:
    text = _COMPANY_HEADER_RE.sub("", text)
    text = _STRAY_MARKER_RE.sub("", text)
    lines = [l for l in text.split("\n") if l.strip()]
    return "\n".join(lines).strip()


def _make_fix_id(section: str, entry_id: str | None, confidence: str, sub_label: str | None) -> str:
    sec = (section or "").lower().strip()
    if entry_id and confidence == "canonical":
        return f"{sec}|{entry_id}"
    if sub_label:
        slug = re.sub(r"[^a-z0-9]+", "_", sub_label.lower().strip())[:40]
        return f"{sec}|{slug}"
    return f"{sec}|__section__"


def _is_usable_patch(patch: Any) -> bool:
    return (
        getattr(patch, "op", "") == "replace_text"
        and bool((getattr(patch, "original_text", "") or "").strip())
        and bool((getattr(patch, "replacement_text", "") or "").strip())
    )


def _index_patches(patches: list) -> tuple[dict, dict]:
    """
    Returns:
        patches_by_entry_id: {sub_entry_id: patch} — canonical matches only
        patches_by_section:  {section: [patches without sub_entry_id]}
    """
    by_entry: dict[str, Any] = {}
    by_section: dict[str, list] = {}

    for patch in patches:
        if not _is_usable_patch(patch):
            continue
        sub_id = (getattr(patch, "sub_entry_id", "") or "").strip().lower()
        sec = (getattr(patch, "section", "") or "").lower().strip()
        if sub_id:
            if sub_id not in by_entry:   # first match wins (PatchEngine.dedup already ran)
                by_entry[sub_id] = patch
        else:
            by_section.setdefault(sec, []).append(patch)

    return by_entry, by_section


def _find_patch(
    fix: dict,
    by_entry: dict,
    by_section: dict,
) -> Any | None:
    entry_id = (fix.get("entry_id") or "").strip()
    confidence = fix.get("entry_id_confidence", "none")
    section = (fix.get("section") or "").lower().strip()

    # Canonical entry_id → exact lookup (normalised to lowercase to match _index_patches)
    if entry_id and confidence == "canonical":
        patch = by_entry.get(entry_id.lower())
        if patch is None and by_entry:
            candidates = [k for k in by_entry if k.startswith(entry_id.lower()[:15])]
            if candidates:
                logging.warning(
                    "FixPlanBuilder: patch near-miss for '%s'. Candidates: %s",
                    entry_id, candidates,
                )
        return patch

    # entry_id present but derived, OR entry_id absent:
    # section-level fallback only when fix itself has no sub_label (true section fix)
    sub_label = (fix.get("sub_label") or "").strip()
    if not sub_label:
        pool = by_section.get(section, [])
        return pool[0] if pool else None

    # Fix has a sub_label but derived/absent entry_id → no patch match (prevents wrong-company bleed)
    return None


def _resolve_before_text(fix: dict, patch: Any | None, resume_sections: dict) -> str | None:
    # 1. Patch original_text
    if patch:
        orig = (getattr(patch, "original_text", "") or "").strip()
        if orig:
            return orig
    # 2. A1 verbatim_text via canonical entry_id
    entry_id = (fix.get("entry_id") or "").strip()
    confidence = fix.get("entry_id_confidence", "none")
    section = (fix.get("section") or "").lower().strip()
    if entry_id and confidence == "canonical" and resume_sections:
        sec = resume_sections.get(section)
        if sec:
            entries = getattr(sec, "sub_entries", None) or sec.get("sub_entries", [])
            for entry in entries:
                eid = getattr(entry, "entry_id", None) or entry.get("entry_id", "")
                if eid == entry_id:
                    text = getattr(entry, "verbatim_text", None) or entry.get("verbatim_text", "")
                    return (text or "").strip() or None
    # 3. original_text stored on fix directly (set by _enrich_section_gaps)
    orig = (fix.get("original_text") or "").strip()
    return orig or None


def _resolve_after_text(fix: dict, patch: Any | None) -> str | None:
    # Evidence/coaching items collect user input first — do NOT set after_text.
    # If after_text is populated, _resolve_kind may misclassify the item as
    # surgical_patch instead of coaching when requires_user_input=False but
    # gap_type=evidence (e.g. after _suppress_evidence_gaps clears the flag).
    if fix.get("requires_user_input") or (fix.get("gap_type") or "") == "evidence":
        return None

    if patch:
        repl = (getattr(patch, "replacement_text", "") or "").strip()
        if repl:
            return _strip_rewrite_markers(repl)
    gap_reason = (fix.get("gap_reason") or "").strip().lower()
    for key in ("rewrite_instruction", "patch_text", "suggested_text"):
        val = (fix.get(key) or "").strip()
        if not val:
            continue
        # Only skip when it's a short duplicate — real rewrites are always longer
        if val.lower() == gap_reason and len(val) <= 60:
            continue
        return _strip_rewrite_markers(val)
    return None


def _resolve_why(fix: dict, patch: Any | None) -> str | None:
    if patch:
        why = (getattr(patch, "fix_rationale", "") or getattr(patch, "issue_detected", "") or "").strip()
        if why:
            return why
    ri = (fix.get("rewrite_instruction") or "").strip()
    gr = (fix.get("gap_reason") or "").strip()
    # ri > 100 chars is a full replacement text, not a rationale — fall back to gap_reason
    if ri and len(ri) > 100:
        return gr or None
    if ri and ri.lower() != gr.lower() and len(ri) > len(gr):
        return ri
    return None


def _resolve_kind(fix: dict, patch: Any | None, after_text: str | None) -> str:
    from backend.schemas.common import FixKind
    # Coaching takes priority — even if a patch exists, evidence gaps need user input first
    if fix.get("requires_user_input") or (fix.get("gap_type") or "") == "evidence":
        return FixKind.COACHING.value
    if patch is not None and after_text:
        return FixKind.SURGICAL_PATCH.value
    if (fix.get("gap_type") or "") == "surface":
        return FixKind.SURFACE_KEYWORD.value
    if after_text:
        return FixKind.REWRITE_BLOCK.value
    return FixKind.INFO_ONLY.value


def build_fix_plan(
    priority_fixes: list[dict],
    classified_patches: list,
    resume_sections: dict | None = None,
) -> list[dict]:
    """
    Build fix_plan[] from already-classified priority_fixes and patches.

    Args:
        priority_fixes:    list from build_complete_priority_fixes()
        classified_patches: list of ResumePatch objects from orchestrator classification
        resume_sections:   dict of {section_name: SectionText} from A1, used for before_text

    Returns:
        list of dicts (FixPlanItem.model_dump()) for JSON serialisation
    """
    if not priority_fixes:
        return []

    by_entry, by_section = _index_patches(classified_patches)
    plan: list[dict] = []
    seen: set[str] = set()

    for fix in priority_fixes:
        confidence = fix.get("entry_id_confidence", "none")
        fix_id = _make_fix_id(
            fix.get("section", ""),
            fix.get("entry_id"),
            confidence,
            fix.get("sub_label"),
        )
        if fix_id in seen:
            continue
        seen.add(fix_id)

        patch = _find_patch(fix, by_entry, by_section)

        before_text = _resolve_before_text(fix, patch, resume_sections or {})
        after_text = _resolve_after_text(fix, patch)
        kind = _resolve_kind(fix, patch, after_text)
        why = _resolve_why(fix, patch)

        # Coaching items must not have patch_id (they generate their own bullet via CoachingAgent)
        patch_id = None
        if kind != "coaching" and patch is not None:
            patch_id = getattr(patch, "patch_id", None)

        plan.append({
            "fix_id":               fix_id,
            "kind":                 kind,
            "section":              fix.get("section", ""),
            "entry_id":             fix.get("entry_id") or None,
            "entry_id_confidence":  confidence,
            "sub_label":            fix.get("sub_label") or None,
            "section_gap_id":       fix.get("section_gap_id") or None,
            "issue":                fix.get("gap_reason", ""),
            "missing_keywords":     fix.get("missing_keywords") or [],
            "patch_id":             patch_id,
            "before_text":          before_text,
            "after_text":           after_text,
            "why":                  why,
            "coaching_question":    fix.get("coaching_question"),
            "coaching_hints":       fix.get("coaching_hint") or [],
            "resume_grounded_hints": fix.get("resume_grounded_hints") or [],
            "requires_user_input":  fix.get("requires_user_input", False),
            "gap_type":             fix.get("gap_type", "structural"),
            "risk":                 "safe",
            "auto_apply":           fix.get("auto_apply", False),
            "status":               "pending",
        })

    logging.info("FixPlanBuilder: %d priority_fixes → %d fix_plan items", len(priority_fixes), len(plan))
    return plan
