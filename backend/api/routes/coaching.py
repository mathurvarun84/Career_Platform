"""Coaching endpoints: bullet generation and career memory."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.coaching_agent import CoachingAgent, bullet_is_meaningful
from backend.agents.gap_analyzer import _fuzzy_match_label
from backend.schemas.career_memory import CareerMemoryEntry, career_memory_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coaching", tags=["coaching"])
_agent = CoachingAgent()

# Injected from main.py so routes can access job_store without circular imports.
_require_job: Callable[[str], dict[str, Any]] | None = None
_persist_job: Callable[[str], None] | None = None


def configure_coaching_routes(
    require_job: Callable[[str], dict[str, Any]],
    persist_job: Callable[[str], None],
) -> None:
    """Wire job store helpers from the FastAPI app module."""
    global _require_job, _persist_job
    _require_job = require_job
    _persist_job = persist_job


class GenerateBulletRequest(BaseModel):
    session_id: str
    gap_id: str
    section: str
    gap_reason: str = ""
    sub_label: str | None = None
    raw_answer: str
    coaching_question: str = ""
    skill_category: str = "technical"
    company: str | None = None
    role: str | None = None


class GenerateBulletResponse(BaseModel):
    generated_bullet: str
    grounding_check: bool
    career_memory_id: str
    warning: str | None = None
    error: str | None = None


class AddBulletRequest(BaseModel):
    session_id: str
    career_memory_id: str
    gap_id: str = ""
    section: str = ""
    sub_label: str | None = None
    bullet_text: str = ""
    placement: str = "end"


class AddBulletResponse(BaseModel):
    inserted: bool
    found_in_doc: bool
    success: bool = False
    career_memory_id: str = ""


class CareerMemoryResponse(BaseModel):
    entries: list[dict[str, Any]]
    total: int


def _normalise_skill(
    raw: str,
) -> Literal["leadership", "technical", "delivery", "communication"]:
    lower = (raw or "").lower()
    if "leader" in lower:
        return "leadership"
    if "deliver" in lower:
        return "delivery"
    if "commun" in lower:
        return "communication"
    return "technical"


def _insert_bullet_in_verbatim(verbatim: str, bullet_line: str, placement: str) -> str:
    """Insert bullet_line at the start or end of a sub-entry verbatim block."""
    if placement == "start":
        first_nl = verbatim.find("\n")
        if first_nl != -1:
            return (
                verbatim[: first_nl + 1]
                + bullet_line
                + "\n"
                + verbatim[first_nl + 1 :]
            )
        if verbatim.strip():
            return bullet_line + "\n" + verbatim
        return bullet_line
    return verbatim.rstrip() + "\n" + bullet_line


def _sync_legacy_job_answer(job: dict[str, Any], entry: CareerMemoryEntry) -> None:
    """Keep job_store coaching_answers in sync for download verification."""
    answers = job.setdefault("coaching_answers", {})
    answers[entry.id] = {
        "gap_id": entry.gap_id,
        "section": entry.section,
        "sub_label": entry.sub_label,
        "raw_answer": entry.raw_answer,
        "generated_bullet": entry.generated_bullet,
        "skill_category": entry.skill_category,
        "company": entry.company,
        "user_approved": entry.user_approved,
        "timestamp": time.time(),
    }


@router.post("/generate-bullet", response_model=GenerateBulletResponse)
def generate_bullet(req: GenerateBulletRequest) -> GenerateBulletResponse:
    if len((req.raw_answer or "").strip()) < 15:
        raise HTTPException(status_code=400, detail="raw_answer too short (min 15 chars)")

    if _require_job is None:
        raise HTTPException(status_code=500, detail="Coaching routes not configured")

    gap_reason = (req.gap_reason or req.coaching_question or "strengthen this skill").strip()
    coaching_question = (req.coaching_question or gap_reason).strip()

    result = _agent.generate_bullet(
        section=req.section,
        gap_reason=gap_reason,
        raw_answer=req.raw_answer,
        coaching_question=coaching_question,
        skill_category=req.skill_category or req.section,
    )

    if result.get("error") == "generation_timeout":
        return GenerateBulletResponse(
            generated_bullet="",
            grounding_check=False,
            career_memory_id="",
            error="generation_timeout",
        )

    generated = (result.get("generated_bullet") or "").strip()
    if not generated or not bullet_is_meaningful(generated):
        raise HTTPException(
            status_code=500,
            detail="Bullet generation failed — please try again or add more detail.",
        )

    # Save to career memory — best-effort: still return bullet if session expired/missing.
    career_memory_id = ""
    try:
        job = _require_job(req.session_id)
        entry = CareerMemoryEntry(
            session_id=req.session_id,
            skill_category=_normalise_skill(req.skill_category),
            gap_reason=gap_reason,
            company=req.company,
            role=req.role,
            section=req.section,
            coaching_question=coaching_question,
            raw_answer=req.raw_answer,
            generated_bullet=generated,
            grounding_check=bool(result.get("grounding_check", True)),
            gap_id=req.gap_id,
            sub_label=req.sub_label,
        )
        career_memory_store.add(entry)
        _sync_legacy_job_answer(job, entry)
        if _persist_job:
            _persist_job(req.session_id)
        career_memory_id = entry.id
    except HTTPException:
        logger.warning(
            "generate_bullet: session %s not in job_store — bullet returned, memory skipped",
            req.session_id,
        )

    grounded = bool(result.get("grounding_check", True))
    return GenerateBulletResponse(
        generated_bullet=generated,
        grounding_check=grounded,
        career_memory_id=career_memory_id,
        warning="We added some language — please review" if not grounded else None,
        error=result.get("error"),
    )


@router.post("/add-bullet", response_model=AddBulletResponse)
def add_bullet(req: AddBulletRequest) -> AddBulletResponse:
    if _require_job is None:
        raise HTTPException(status_code=500, detail="Coaching routes not configured")

    if not req.session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    job = _require_job(req.session_id)
    approved = career_memory_store.approve(req.session_id, req.career_memory_id)

    legacy = job.get("coaching_answers", {}).get(req.career_memory_id)
    bullet_text = (req.bullet_text or "").strip()
    if not bullet_text and legacy:
        bullet_text = str(legacy.get("generated_bullet", "")).strip()

    section = req.section or (legacy or {}).get("section", "")
    placement = req.placement if req.placement in ("start", "end") else "start"

    inserted = False
    found_in_doc = False
    if bullet_text and section:
        bullet_line = bullet_text if bullet_text.startswith("•") else f"• {bullet_text}"
        resume_sections = job.get("result", {}).get("resume", {}).get("resume_sections", {})
        section_key = section.lower()
        sec_data = resume_sections.get(section_key, {})
        matched_entry: dict[str, Any] | None = None

        if isinstance(sec_data, dict) and req.sub_label:
            sub_entries = sec_data.get("sub_entries") or []
            valid_labels = {
                e.get("label", "")
                for e in sub_entries
                if isinstance(e, dict) and e.get("label")
            }
            matched_label = _fuzzy_match_label(req.sub_label, valid_labels)
            if matched_label:
                for entry in sub_entries:
                    if isinstance(entry, dict) and entry.get("label") == matched_label:
                        matched_entry = entry
                        break

        if matched_entry is not None:
            old_verbatim = matched_entry.get("verbatim_text", "")
            new_verbatim = _insert_bullet_in_verbatim(old_verbatim, bullet_line, placement)
            matched_entry["verbatim_text"] = new_verbatim

            full_text = sec_data.get("full_text", "")
            if old_verbatim and old_verbatim in full_text:
                sec_data["full_text"] = full_text.replace(old_verbatim, new_verbatim, 1)

            current_text = job.get("resume_text_patched") or job.get("resume_text", "")
            if old_verbatim and old_verbatim in current_text:
                job["resume_text_patched"] = current_text.replace(
                    old_verbatim, new_verbatim, 1
                )
            inserted = True
            found_in_doc = bullet_line in new_verbatim or bullet_text in new_verbatim
        elif isinstance(sec_data, dict) and not req.sub_label:
            old_full = sec_data.get("full_text", "")
            if old_full.strip():
                new_full = _insert_bullet_in_verbatim(old_full, bullet_line, placement)
                sec_data["full_text"] = new_full
                current_text = job.get("resume_text_patched") or job.get("resume_text", "")
                if old_full in current_text:
                    job["resume_text_patched"] = current_text.replace(
                        old_full, new_full, 1
                    )
                inserted = True
                found_in_doc = bullet_line in new_full or bullet_text in new_full

    if approved or legacy:
        if legacy:
            legacy["user_approved"] = True
        if _persist_job:
            _persist_job(req.session_id)

    return AddBulletResponse(
        inserted=inserted,
        found_in_doc=found_in_doc,
        success=approved or bool(legacy),
        career_memory_id=req.career_memory_id,
    )


@router.get("/career-memory", response_model=CareerMemoryResponse)
def get_career_memory(session_id: str) -> CareerMemoryResponse:
    if _require_job is None:
        raise HTTPException(status_code=500, detail="Coaching routes not configured")

    _require_job(session_id)
    entries: list[dict[str, Any]] = []

    for entry in career_memory_store.get(session_id):
        payload = entry.model_dump()
        payload["gap_id"] = entry.gap_id
        entries.append(payload)

    if not entries:
        job = _require_job(session_id)
        for memory_id, data in (job.get("coaching_answers") or {}).items():
            entries.append(
                {
                    "id": memory_id,
                    "session_id": session_id,
                    "gap_id": data.get("gap_id", ""),
                    "section": data.get("section", ""),
                    "sub_label": data.get("sub_label"),
                    "raw_answer": data.get("raw_answer", ""),
                    "generated_bullet": data.get("generated_bullet", ""),
                    "skill_category": data.get("skill_category", "technical"),
                    "company": data.get("company"),
                    "gap_reason": data.get("gap_reason", ""),
                    "coaching_question": data.get("coaching_question", ""),
                    "grounding_check": data.get("grounding_check", True),
                    "user_approved": data.get("user_approved", False),
                    "timestamp": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ",
                        time.gmtime(data.get("timestamp", 0)),
                    ),
                }
            )

    entries.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return CareerMemoryResponse(entries=entries, total=len(entries))
