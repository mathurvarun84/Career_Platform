"""FastAPI backend for Resume Intelligence Platform V2."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
import hashlib
from pathlib import Path
import queue
import threading
from typing import Any, Dict, Generator

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.auth import get_current_user_id
from backend.agents.jd_fetcher import JDFetcherAgent
from backend.db import get_db
from backend.limit_checker import check_upload_limit, get_upload_usage, reset_user_limit
from backend.persistence import save_analysis
from engine.resume_builder import build_final_docx
from validator.rewriter_validator import assert_structural_completeness
from orchestrator import Orchestrator
from parser import parse_resume
from backend.schemas.jd_fetch_schema import FetchJDRequest, FetchJDResponse
from backend.api.routes.coaching import configure_coaching_routes, router as coaching_router


logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Intelligence Platform V2")
job_store: Dict[str, Dict[str, Any]] = {}

# Persist completed jobs so download still works after uvicorn reload / process restart.
_JOB_CACHE_DIR = Path(__file__).resolve().parent / ".job_cache"
_STAGE_CACHE_PATH = _JOB_CACHE_DIR / "stage_cache.json"
# TTL for A1/A2 stage cache (seconds). 0 = disabled. Default 1 hour.
_DEFAULT_STAGE_CACHE_TTL = 3600


def _stage_cache_ttl_seconds() -> int:
    raw = os.getenv("STAGE_CACHE_TTL_SECONDS", str(_DEFAULT_STAGE_CACHE_TTL))
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_STAGE_CACHE_TTL


def _persist_job(job_id: str) -> None:
    if job_id not in job_store:
        return
    try:
        _JOB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _JOB_CACHE_DIR / f"{job_id}.json"
        path.write_text(json.dumps(job_store[job_id], default=str), encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Persist job %s failed: %s", job_id, exc)


def _try_restore_job(job_id: str) -> bool:
    if job_id in job_store:
        return True
    path = _JOB_CACHE_DIR / f"{job_id}.json"
    if not path.is_file():
        return False
    try:
        job_store[job_id] = json.loads(path.read_text(encoding="utf-8"))
        return True
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Restore job %s failed: %s", job_id, exc)
        return False


def _require_job(job_id: str) -> Dict[str, Any]:
    if not _try_restore_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return job_store[job_id]


configure_coaching_routes(_require_job, _persist_job)
app.include_router(coaching_router)


def _is_stage_payload(entry: Dict[str, Any]) -> bool:
    """True when dict is raw stage data (legacy on-disk format)."""
    return isinstance(entry, dict) and (
        "resume_und" in entry or "resume_sections" in entry or "jd_intel" in entry
    )


def _prune_expired_stage_cache(
    stage_cache: Dict[str, Dict[str, Any]],
    ttl: int,
) -> Dict[str, Dict[str, Any]]:
    """Drop expired wrapped entries; legacy unwrapped entries are removed (force refresh)."""
    if ttl <= 0:
        return {}
    now = time.time()
    kept: Dict[str, Dict[str, Any]] = {}
    for key, entry in stage_cache.items():
        if not isinstance(entry, dict):
            continue
        if _is_stage_payload(entry):
            continue
        cached_at = entry.get("cached_at")
        data = entry.get("data")
        if not isinstance(cached_at, (int, float)) or not isinstance(data, dict):
            continue
        if now - float(cached_at) <= ttl:
            kept[key] = entry
    return kept


def _get_stage_cache_entry(
    stage_cache: Dict[str, Dict[str, Any]],
    cache_key: str,
) -> Dict[str, Any] | None:
    """Return stage payload if present and not expired; None on miss or TTL disabled."""
    ttl = _stage_cache_ttl_seconds()
    if ttl <= 0:
        return None
    entry = stage_cache.get(cache_key)
    if not entry or not isinstance(entry, dict):
        return None
    if _is_stage_payload(entry):
        logger.info("Stage cache miss (legacy entry): %s", cache_key[:24])
        return None
    cached_at = entry.get("cached_at")
    data = entry.get("data")
    if not isinstance(data, dict):
        return None
    if not isinstance(cached_at, (int, float)):
        return None
    age = time.time() - float(cached_at)
    if age > ttl:
        logger.info(
            "Stage cache expired for %s (age %.0fs > ttl %ds)",
            cache_key[:24],
            age,
            ttl,
        )
        return None
    return data


def _set_stage_cache_entry(
    stage_cache: Dict[str, Dict[str, Any]],
    cache_key: str,
    stage_data: Dict[str, Any],
) -> None:
    """Store stage payload with timestamp; no-op when TTL disabled."""
    ttl = _stage_cache_ttl_seconds()
    if ttl <= 0:
        return
    stage_cache[cache_key] = {
        "cached_at": time.time(),
        "data": stage_data,
    }


def _merge_stage_cache_entry(
    stage_cache: Dict[str, Dict[str, Any]],
    cache_key: str,
    updates: Dict[str, Any],
) -> None:
    """Merge keys into an existing stage cache entry (e.g. add recruiter_sim after A5)."""
    existing = _get_stage_cache_entry(stage_cache, cache_key) or {}
    merged = {**existing, **updates}
    _set_stage_cache_entry(stage_cache, cache_key, merged)


def _load_stage_cache() -> Dict[str, Dict[str, Any]]:
    if not _STAGE_CACHE_PATH.is_file():
        return {}
    try:
        raw = json.loads(_STAGE_CACHE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return _prune_expired_stage_cache(raw, _stage_cache_ttl_seconds())
    except (OSError, json.JSONDecodeError):
        return {}


def _persist_stage_cache(stage_cache: Dict[str, Dict[str, Any]]) -> None:
    try:
        _JOB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        pruned = _prune_expired_stage_cache(stage_cache, _stage_cache_ttl_seconds())
        _STAGE_CACHE_PATH.write_text(
            json.dumps(pruned, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Persist stage cache failed: %s", exc)


stage_cache: Dict[str, Dict[str, Any]] = _load_stage_cache()

_DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]


def _get_allowed_origins() -> list[str]:
    """Resolve CORS origins from environment with safe localhost defaults."""
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    from_env = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return from_env or _DEFAULT_ALLOWED_ORIGINS


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """Basic root endpoint for platform health checks."""
    return {"status": "ok", "service": "resume-intelligence-platform"}


@app.get("/health")
def health() -> dict:
    """Explicit health endpoint for Railway and uptime probes."""
    return {"status": "healthy"}


class GapCloseRequest(BaseModel):
    """Gap close request payload."""

    job_id: str
    jd_text: str = ""
    style: str = "balanced"


class ApplyPatchesRequest(BaseModel):
    """Apply patches request."""
    job_id: str
    patch_ids: list[str]
    user_confirmed: bool = False


class RollbackRequest(BaseModel):
    """Rollback patches request."""
    job_id: str
    patch_id: str = "all"


def _json_event(payload: dict) -> str:
    """Serialize one SSE data event."""
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _analyze_event_stream(
    temp_path: str,
    file_name: str,
    jd_text: str,
    run_sim: bool,
    resume_hash: str,
    jd_hash: str,
    user_id: str,
) -> Generator[str, None, None]:
    """Worker thread pushes SSE payloads; main generator yields JSON lines."""

    q: queue.Queue = queue.Queue()
    job_id = str(uuid.uuid4())

    def worker() -> None:
        try:
            job_store[job_id] = {
                "status": "running",
                "progress": [],
                "result": None,
                "error": None,
                "resume_text": "",
            }
            q.put(
                {
                    "action": "yield",
                    "data": {"event": "started", "job_id": job_id},
                }
            )

            try:
                db = get_db()
                check_upload_limit(db, user_id)
            except HTTPException as exc:
                detail_payload = (
                    exc.detail
                    if isinstance(exc.detail, dict)
                    else {"message": str(exc.detail)}
                )
                job_store[job_id]["status"] = "error"
                job_store[job_id]["error"] = detail_payload.get(
                    "message", "Upload limit reached"
                )
                q.put(
                    {
                        "action": "yield",
                        "data": {
                            "event": "error",
                            "message": detail_payload.get(
                                "message", "Upload limit reached"
                            ),
                            "status": exc.status_code,
                            "detail": detail_payload,
                        },
                    }
                )
                q.put({"action": "stop"})
                return

            resume_text = parse_resume(temp_path)
            job_store[job_id]["resume_text"] = resume_text

            # Keep /api/stream compatible progress payloads.
            job_store[job_id]["progress"].append(
                {
                    "status": "running",
                    "step": 0,
                    "label": "Resume parsed",
                    "pct": 20,
                }
            )
            q.put(
                {
                    "action": "yield",
                    "data": {
                        "event": "step_complete",
                        "step": 0,
                        "label": "Resume parsed",
                    },
                }
            )

            # v3: invalidate caches created before bullet-continuation parser fix
            cache_key = f"v3:{resume_hash}:{jd_hash or 'none'}"
            cached_stage_data = _get_stage_cache_entry(stage_cache, cache_key)
            if cached_stage_data:
                logger.info("Stage cache hit: %s", cache_key[:32])
            elif _stage_cache_ttl_seconds() > 0:
                logger.info("Stage cache miss: %s", cache_key[:32])

            def stage_cache_cb(stage_data: dict) -> None:
                _merge_stage_cache_entry(stage_cache, cache_key, stage_data)
                _persist_stage_cache(stage_cache)

            def sse_step_cb(step: int, label: str) -> None:
                job_store[job_id]["progress"].append(
                    {
                        "status": "running",
                        "step": step,
                        "label": label,
                        "pct": 20 if step == 0 else 45 if step == 1 else 72 if step == 2 else 88,
                    }
                )
                q.put(
                    {
                        "action": "yield",
                        "data": {
                            "event": "step_complete",
                            "step": step,
                            "label": label,
                        },
                    }
                )

            orch = Orchestrator(user_id=user_id)
            result = orch.run_full_evaluation(
                resume_text=resume_text,
                jd_text=jd_text,
                run_sim=run_sim,
                progress_cb=lambda _e: None,
                partial_result_cb=None,
                cached_stage_data=cached_stage_data,
                stage_cache_cb=stage_cache_cb,
                sse_step_cb=sse_step_cb,
            )
            merged = dict(result)
            merged["job_id"] = job_id
            # Coaching APIs key off job_store; expose same id as session_id for the UI.
            merged["session_id"] = job_id
            job_store[job_id]["result"] = merged
            job_store[job_id]["status"] = "complete"

            job_store[job_id]["progress"].append(
                {
                    "status": "complete",
                    "pct": 100,
                }
            )
            q.put({"action": "yield", "data": {"event": "analysis_complete", "result": merged}})

            try:
                file_size = os.path.getsize(temp_path)
                target_role = None
                if jd_text:
                    jd_intel = result.get("jd_intelligence") or {}
                    target_role = jd_intel.get("role_title")
                save_analysis(
                    user_id=user_id,
                    file_name=file_name,
                    file_size=file_size,
                    jd_text=jd_text,
                    target_company=None,
                    target_role=target_role,
                    result=merged,
                )
            except Exception as exc:
                logger.warning("save_analysis failed (non-blocking): %s", exc)

            q.put({"action": "stop"})
        except Exception as exc:
            logger.exception("Streaming analysis failed for job %s", job_id)
            if job_id in job_store:
                job_store[job_id]["status"] = "error"
                job_store[job_id]["error"] = str(exc)
            q.put(
                {
                    "action": "yield",
                    "data": {"event": "error", "message": str(exc)},
                }
            )
            if job_id in job_store:
                job_store[job_id]["progress"].append(
                    {
                        "status": "error",
                        "error": str(exc),
                    }
                )
            q.put({"action": "stop"})
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            _persist_job(job_id)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = q.get()
        if item["action"] == "yield":
            yield _json_event(item["data"])
        elif item["action"] == "stop":
            break


@app.get("/api/usage-limit")
def usage_limit(user_id: str = Depends(get_current_user_id)) -> dict:
    """Lightweight pre-check before starting a paid analysis pipeline."""
    db = get_db()
    return get_upload_usage(db, user_id)


@app.post("/api/analyze")
async def analyze(
    resume: UploadFile = File(...),
    jd_text: str = Form(""),
    run_sim: bool = Form(False),
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """Stream analysis progress as SSE; final payload includes full result JSON."""
    print(f"analyze user_id={user_id}", flush=True)
    suffix = os.path.splitext(resume.filename or "resume.txt")[1] or ".txt"
    resume_bytes = await resume.read()
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as tmp:
        tmp.write(resume_bytes)

    resume_hash = hashlib.sha256(resume_bytes).hexdigest()
    jd_hash = hashlib.sha256((jd_text or "").encode("utf-8")).hexdigest() if jd_text else ""

    return StreamingResponse(
        _analyze_event_stream(
            temp_path, resume.filename or "resume.txt", jd_text, run_sim, resume_hash, jd_hash, user_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/stream/{job_id}")
def stream(job_id: str):
    """Stream job progress as Server-Sent Events."""
    _require_job(job_id)

    def event_generator():
        index = 0
        while True:
            job = job_store[job_id]
            events = job.get("progress", [])
            while index < len(events):
                yield _json_event(events[index])
                index += 1
            if job.get("status") in {"complete", "error"}:
                break
            time.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/result/{job_id}")
def result(job_id: str) -> dict:
    """Return current job status and result for polling fallback."""
    job = _require_job(job_id)
    return {
        "status": job.get("status"),
        "result": job.get("result"),
        "error": job.get("error"),
        "progress": job.get("progress", [])[-1] if job.get("progress") else None,
    }


@app.post("/api/gap-close")
def gap_close(req: GapCloseRequest) -> dict:
    """Run gap-close rewrite for an existing job and cache rewrites."""
    job = _require_job(req.job_id)
    resume_text = job.get("resume_text")
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text not available")

    result = Orchestrator(user_id=req.job_id).run_full_evaluation(
        resume_text=resume_text,
        jd_text=req.jd_text,
        run_sim=False,
        skip_rewrite=False,
    )
    job["gap_result"] = result.get("gap")
    raw_rewrites = result.get("rewrites") or {}
    # Orchestrator returns A4 output as {"rewrites": {...}, "styles": {...}}.
    # Persist the inner map for downstream consumers like DOCX builder.
    job["rewrites"] = (
        raw_rewrites.get("rewrites")
        if isinstance(raw_rewrites, dict) and "rewrites" in raw_rewrites
        else raw_rewrites
    )
    job["result"] = {**(job.get("result") or {}), **result}
    _persist_job(req.job_id)
    return {"gap": result.get("gap"), "rewrites": result.get("rewrites")}


@app.post("/api/fetch-jd", response_model=FetchJDResponse)
async def fetch_jd(req: FetchJDRequest):
    """
    Accepts company name and role title.
    Returns extracted JD text via LLM + web search.
    Expected latency: 3-8 seconds.
    """
    agent = JDFetcherAgent()
    result = agent.fetch(
        company=req.company,
        role=req.role,
        direct_url=req.direct_url,
    )
    return FetchJDResponse(**result.model_dump())


@app.get("/api/download/{job_id}")
def download(job_id: str, style: str = "balanced") -> Response:
    """Download a generated resume docx for a completed job."""
    job = _require_job(job_id)
    result = job.get("result") or {}
    structured = result.get("resume") or {}
    rewrites = job.get("rewrites") or result.get("rewrites") or {}
    # Normalize possible outer container shape {"rewrites": {...}, "styles": {...}}
    if isinstance(rewrites, dict) and "rewrites" in rewrites and isinstance(rewrites.get("rewrites"), dict):
        rewrites = rewrites["rewrites"]
    resume_text = job.get("resume_text") or ""
    resume_sections = (
        (structured.get("resume_sections") if isinstance(structured, dict) else None)
        or result.get("resume_sections")
        or {}
    )
    from validator.experience_audit import (
        log_experience_audit,
        repair_experience_for_export,
    )

    resume_sections, rewrites, repaired = repair_experience_for_export(
        resume_text,
        resume_sections,
        rewrites,
    )
    missing_sections = assert_structural_completeness(rewrites, resume_sections)
    if missing_sections:
        logging.error(
            "Structural completeness FAILED after repair — missing: %s",
            missing_sections,
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Resume export incomplete",
                "missing": missing_sections,
            },
        )
    if repaired and isinstance(structured, dict):
        structured = dict(structured)
        structured["resume_sections"] = resume_sections

    audit = log_experience_audit(
        "pre_docx_download",
        resume_text,
        resume_sections,
        rewrites,
        style=style,
    )
    if audit.get("ground_truth_count", 0) > audit.get("sub_entries_count", 0):
        logging.warning(
            "ExperienceAudit: docx may still omit %d role(s) after repair — "
            "ground-truth detector found extra date blocks or labels did not match",
            audit["ground_truth_count"] - audit["sub_entries_count"],
        )
    patched_text = job.get("resume_text_patched") or ""
    original_text = job.get("resume_text") or ""
    has_surgical_patches = patched_text.strip() and patched_text != original_text
    # Use surgical export for any non-aggressive download when patches were applied.
    if has_surgical_patches and style != "aggressive":
        from backend.surgical_debug import write_surgical_snapshot
        from engine.surgical_export import prepare_surgical_export

        write_surgical_snapshot(
            job_id,
            job,
            "before_download",
            extra={"download_style": style, "path": "surgical_patched"},
        )
        structured_for_export = prepare_surgical_export(
            structured if isinstance(structured, dict) else {},
            resume_sections,
            patched_text,
        )
        docx = build_final_docx(
            structured=structured_for_export,
            rewrites={},
            style="balanced",
            resume_text=patched_text,
        )
        write_surgical_snapshot(
            job_id,
            job,
            "after_download",
            extra={
                "download_style": style,
                "experience_markers": (
                    (structured_for_export.get("resume_sections") or {})
                    .get("experience", {})
                    .get("full_text", "")
                    if isinstance(structured_for_export.get("resume_sections"), dict)
                    else ""
                ).count("##COMPANY##"),
            },
        )
    else:
        docx = build_final_docx(
            structured=structured,
            rewrites=rewrites,
            style=style,
            resume_text=resume_text,
        )
    return Response(
        content=docx,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="resume.docx"'},
    )


@app.post("/api/reset-limit")
def reset_limit(user_id: str = None) -> dict:
    """Admin/dev endpoint: reset user's monthly upload counter. Useful for testing."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    try:
        db = get_db()
        result = reset_user_limit(db, user_id)
        return {"success": True, "user_id": user_id, "uploads_this_month": 0}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/session/{session_id}/rescore")
def rescore_session(session_id: str) -> dict:
    """Recalculate ATS score from current document state."""
    job = _require_job(session_id)
    from engine.patch_engine import PatchEngine, rescore

    original = job.get("result", {}).get("ats", {})
    original_score = original.get("score", 0)
    current_text = job.get("resume_text_patched") or job.get("resume_text", "")
    resume_sections = job.get("result", {}).get("resume", {}).get("resume_sections", {})
    jd_text = job.get("jd_text")
    engine = PatchEngine(current_text, resume_sections=resume_sections)
    score = rescore(engine, jd_text, baseline_score=original_score)

    return {
        "ats_score": score.get("score", original_score),
        "raw_ats_score": score.get("raw_score", score.get("score", original_score)),
        "delta_from_original": score.get("score", original_score) - original_score,
        "breakdown": score.get("breakdown", original.get("breakdown", {})),
        "ats_issues": score.get("ats_issues", original.get("ats_issues", [])),
    }


@app.get("/api/session/{session_id}/download")
def get_download_verification(session_id: str) -> dict:
    """Verify applied patches and approved coaching bullets exist in current document."""
    job = _require_job(session_id)
    current_text = job.get("resume_text_patched") or job.get("resume_text", "")
    patches = job.get("result", {}).get("patches", []) or []
    coaching_answers = job.get("coaching_answers", {}) or {}

    missing_patches = []
    for patch in patches:
        if patch.get("status") != "applied":
            continue
        replacement = (patch.get("replacement_text") or "").strip()
        if replacement and replacement not in current_text:
            missing_patches.append(patch.get("patch_id", "unknown"))

    approved_answers = [
        answer for answer in coaching_answers.values()
        if answer.get("user_approved") and answer.get("generated_bullet")
    ]
    missing_bullets = []
    for answer in approved_answers:
        bullet_text = str(answer.get("generated_bullet", ""))
        clean_bullet = bullet_text.strip("• ").strip()
        if clean_bullet and clean_bullet not in current_text and bullet_text not in current_text:
            missing_bullets.append(bullet_text[:60])

    total_applied = len([p for p in patches if p.get("status") == "applied"]) + len(approved_answers)
    total_verified = max(total_applied - len(missing_patches) - len(missing_bullets), 0)

    return {
        "clean": len(missing_patches) == 0 and len(missing_bullets) == 0,
        "missing_patches": missing_patches,
        "missing_bullets": missing_bullets,
        "total_applied": total_applied,
        "total_verified": total_verified,
    }


@app.post("/api/patches/apply")
async def apply_patches(req: ApplyPatchesRequest):
    """Apply patches to resume text and return updated text + rescored result."""
    job = _require_job(req.job_id)
    # Use patched version if patches were already applied, otherwise use original
    resume_text = job.get("resume_text_patched") or job.get("resume_text", "")
    patches_raw = job.get("result", {}).get("patches", [])
    jd_text = job.get("jd_text")
    resume_sections = job.get("result", {}).get("resume", {}).get("resume_sections", {})

    from engine.patch_engine import PatchEngine, rescore
    from backend.schemas.common import ResumePatch

    from backend.surgical_debug import write_surgical_snapshot

    write_surgical_snapshot(req.job_id, job, "before_fix")

    engine = PatchEngine(resume_text, resume_sections=resume_sections)
    all_patches = {p["patch_id"]: ResumePatch(**p) for p in patches_raw}

    applied, rejected, results = [], [], []
    for pid in req.patch_ids:
        patch = all_patches.get(pid)
        if not patch:
            results.append({
                "patch_id": pid,
                "applied": False,
                "found_in_doc": False,
                "rejection_reason": "patch_id not found",
            })
            rejected.append(pid)
            continue
        if patch.risk == "needs_confirmation" and not req.user_confirmed:
            rejected.append(pid)
            results.append({
                "patch_id": pid,
                "applied": False,
                "found_in_doc": False,
                "rejection_reason": "needs_confirmation",
            })
            continue
        outcome = engine.apply_with_result(patch)
        results.append({
            "patch_id": pid,
            "applied": outcome["applied"],
            "found_in_doc": outcome["found_in_doc"],
            "rejection_reason": outcome.get("rejection_reason"),
        })
        if outcome["applied"]:
            applied.append(pid)
        else:
            rejected.append(pid)

    original_ats = job.get("result", {}).get("ats", {}).get("score", 0)
    score = rescore(engine, jd_text, baseline_score=original_ats)
    updated_text = engine.get_current_text()

    # Persist updated text and patch states back to job cache
    job["resume_text_patched"] = updated_text
    for p in patches_raw:
        if p["patch_id"] in applied:
            p["status"] = "applied"
        elif p["patch_id"] in rejected:
            p["status"] = "rejected"
    _persist_job(req.job_id)

    write_surgical_snapshot(
        req.job_id,
        job,
        "after_fix",
        extra={"applied": applied, "rejected": rejected, "results": results},
    )

    return {
        "applied": applied,
        "rejected": rejected,
        "results": results,
        "resume_text": updated_text,
        "score": score,
    }


@app.post("/api/patches/rollback")
async def rollback_patch(req: RollbackRequest):
    """Rollback one or all patches and return updated text + rescored result."""
    job = _require_job(req.job_id)
    resume_text = job.get("resume_text", "")
    patches_raw = job.get("result", {}).get("patches", [])
    jd_text = job.get("jd_text")
    resume_sections = job.get("result", {}).get("resume", {}).get("resume_sections", {})

    from engine.patch_engine import PatchEngine, rescore
    from backend.schemas.common import ResumePatch

    # Reconstruct engine from original text + re-apply all still-applied patches
    # except the rolled-back one
    patches_to_keep = [
        ResumePatch(**p) for p in patches_raw
        if p["status"] == "applied" and p["patch_id"] != req.patch_id
    ] if req.patch_id != "all" else []

    engine = PatchEngine(resume_text, resume_sections=resume_sections)
    engine.apply_batch(patches_to_keep)

    original_ats = job.get("result", {}).get("ats", {}).get("score", 0)
    score = rescore(engine, jd_text, baseline_score=original_ats)
    updated_text = engine.get_current_text()

    # Update status
    for p in patches_raw:
        if req.patch_id == "all" or p["patch_id"] == req.patch_id:
            if p["status"] == "applied":
                p["status"] = "rolled_back"
    job["resume_text_patched"] = updated_text
    _persist_job(req.job_id)

    return {"resume_text": updated_text, "score": score}

