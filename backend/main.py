"""FastAPI backend for Resume Intelligence Platform V2."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import queue
import threading
from typing import Any, Dict, Generator, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.auth import get_current_user_id
from backend.agents.jd_fetcher import JDFetcherAgent
from backend.agents.interview_agent import InterviewAgent
from backend.db import get_db
from backend.interview_persistence import (
    cache_model_answer,
    complete_interview_session,
    get_interview_session_row,
    insert_interview_session,
    list_completed_interview_sessions,
    sync_interview_session_progress,
)
from backend.limit_checker import check_upload_limit, get_upload_usage, reset_user_limit
from backend.corpus_persistence import record_patch_decisions, save_corpus_run
from backend.persistence import save_analysis
from engine.resume_builder import build_final_docx
from validator.rewriter_validator import assert_structural_completeness
from orchestrator import Orchestrator
from backend.utils.question_ledger import (
    get_available_dimensions,
    get_excluded_dimensions,
    get_ledger,
    resume_fingerprint,
    update_ledger,
)
from parser import parse_resume
from backend.schemas.jd_fetch_schema import FetchJDRequest, FetchJDResponse
from backend.schemas.interview_schema import (
    InterviewQuestionsRequest,
    InterviewQuestionsResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)
from backend.api.routes.coaching import configure_coaching_routes, router as coaching_router
from backend.feedback import router as feedback_router
from backend.api.score_journey import router as score_journey_router
from backend.api.company_readiness import router as company_readiness_router


logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Intelligence Platform V2")
job_store: Dict[str, Dict[str, Any]] = {}

# ── Interview session store (in-memory; keyed by session_id) ─────────────────
# Schema per entry:
#   session_id:        str
#   company:           str
#   seniority:         str
#   question_mode:     str   (behavioral | scenario | mixed)
#   questions:         list[dict]   (InterviewQuestion[])
#   answers:           list[dict]   (AnswerTurn[])
#   feedback:          list[dict]   (PerQuestionFeedback[])
#   compressed_turns:  list[str]    (grows after each evaluation — Day 3)
#   active_follow_ups: dict[str, dict]  (question_id → last FollowUpQuestion returned)
#   created_at:        str          (ISO timestamp)
_interview_sessions: Dict[str, Dict[str, Any]] = {}

_interview_agent = InterviewAgent()

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
app.include_router(feedback_router)
app.include_router(score_journey_router)
app.include_router(company_readiness_router)


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
    target_company: Optional[str] = None,
    jd_source: str = "pasted",
) -> Generator[str, None, None]:
    """Worker thread pushes SSE payloads; main generator yields JSON lines."""

    q: queue.Queue = queue.Queue()
    job_id = str(uuid.uuid4())

    def worker() -> None:
        pipeline_started = time.perf_counter()
        try:
            job_store[job_id] = {
                "status": "running",
                "progress": [],
                "result": None,
                "error": None,
                "resume_text": "",
                "jd_text": jd_text,
                "user_id": user_id,
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

            def partial_result_cb(chunk: dict) -> None:
                """Stream incremental analysis slices for the loading-screen live feed."""
                payload = {"event": "partial", **chunk}
                job_store[job_id]["progress"].append(payload)
                q.put({"action": "yield", "data": payload})

            orch = Orchestrator(user_id=user_id)
            result = orch.run_full_evaluation(
                resume_text=resume_text,
                jd_text=jd_text,
                target_company=target_company,
                jd_source=jd_source,
                run_sim=run_sim,
                progress_cb=lambda _e: None,
                partial_result_cb=partial_result_cb,
                cached_stage_data=cached_stage_data,
                stage_cache_cb=stage_cache_cb,
                sse_step_cb=sse_step_cb,
            )
            merged = dict(result)
            merged["job_id"] = job_id
            # Coaching APIs key off job_store; expose same id as session_id for the UI.
            merged["session_id"] = job_id
            elapsed_ms = int((time.perf_counter() - pipeline_started) * 1000)
            try:
                corpus_ids = save_corpus_run(
                    user_id=user_id,
                    run_id=job_id,
                    resume_text=resume_text,
                    file_name=file_name,
                    resume_und=result.get("resume") or {},
                    jd_text=jd_text,
                    jd_source=jd_source,
                    target_company=target_company,
                    final_result=merged,
                    elapsed_ms=elapsed_ms,
                )
                merged["run_id"] = corpus_ids.get("run_id") or job_id
                merged["resume_id"] = corpus_ids.get("resume_id")
                merged["jd_id"] = corpus_ids.get("jd_id")
            except Exception as exc:
                logger.warning("save_corpus_run failed (non-blocking): %s", exc)
                merged["run_id"] = job_id
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
                    target_company=target_company,
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
    target_company: str = Form(""),
    jd_source: str = Form("pasted"),
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
            temp_path, resume.filename or "resume.txt", jd_text, run_sim, resume_hash, jd_hash, user_id,
            target_company=target_company or None, jd_source=jd_source or "pasted",
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
        **({"role_family": req.role_family} if req.role_family else {}),
        **({"seniority_rank": req.seniority_rank} if req.seniority_rank else {}),
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

    try:
        result_payload = job.get("result") or {}
        record_patch_decisions(
            run_id=result_payload.get("run_id") or req.job_id,
            user_id=job.get("user_id") or "",
            gap_result=result_payload.get("gap"),
            patches=patches_raw,
            applied_ids=applied,
            rejected_ids=rejected,
        )
    except Exception as exc:
        logger.warning("record_patch_decisions failed (non-blocking): %s", exc)

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


# ── Interview endpoints ───────────────────────────────────────────────────────

@app.post("/api/interview/questions", response_model=InterviewQuestionsResponse)
async def generate_interview_questions(request: InterviewQuestionsRequest):
    """
    Standalone question generation (Day 2). Does not create a session.

    Body: { resume_text, company, seniority, question_mode? }
    Returns: { questions: InterviewQuestion[] }
    """
    company_key = request.company.lower().strip().replace(" ", "_")
    result = _interview_agent.generate_questions({
        "resume_text": request.resume_text,
        "company": company_key,
        "seniority": request.seniority,
        "question_mode": request.question_mode,
    })
    return InterviewQuestionsResponse(questions=result["questions"])


@app.post("/api/interview/session/start", response_model=StartInterviewResponse)
async def start_interview_session(
    request: StartInterviewRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Start a new mock interview session.

    Calls InterviewAgent.generate_questions() with the candidate's resume and
    target company. Returns 3 questions + a session_id for subsequent /answer calls.

    Body:
      resume_text:    str      — candidate's resume (plain text)
      company:        str      — company key (e.g. "amazon") or display name
      seniority:      str      — junior | mid | senior | staff | em
      question_mode:  str      — behavioral | scenario | mixed (default: mixed)

    Returns:
      { session_id: str, questions: InterviewQuestion[] }
    """
    session_id = str(uuid.uuid4())
    company_key = request.company.lower().strip().replace(" ", "_")
    resume_fp = resume_fingerprint(request.resume_text)
    question_ledger = get_ledger(user_id, resume_fp)
    excluded_dimensions = get_excluded_dimensions(user_id, resume_fp)

    result = _interview_agent.generate_questions({
        "resume_text": request.resume_text,
        "company": company_key,
        "seniority": request.seniority,
        "question_mode": request.question_mode,
        "question_ledger": question_ledger,
        "excluded_dimensions": excluded_dimensions,
    })

    _interview_sessions[session_id] = {
        "session_id":       session_id,
        "user_id":          user_id,
        "company":          company_key,
        "seniority":        request.seniority,
        "question_mode":    request.question_mode,
        "questions":        result["questions"],
        "answers":          [],
        "feedback":         [],
        "compressed_turns": [],
        "active_follow_ups": {},
        "resume_fingerprint": resume_fp,
        "created_at":       datetime.now(timezone.utc).isoformat(),
    }

    insert_interview_session(
        session_id=session_id,
        user_id=user_id,
        company=company_key,
        seniority=request.seniority,
        question_mode=request.question_mode,
        questions=result["questions"],
        run_id=request.run_id,
        resume_id=request.resume_id,
    )

    return StartInterviewResponse(
        session_id=session_id,
        questions=result["questions"],
    )


# ── Interview Day 3 — request schemas ────────────────────────────────────────

class SubmitAnswerRequest(BaseModel):
    """Body for the /answer and /answer/stream endpoints."""

    question_id: str
    answer_text: str
    is_follow_up: bool = False
    follow_up_id: str | None = None


class FollowUpRequest(BaseModel):
    """Body for the /follow-up probe endpoint."""

    question_id: str
    answer_text: str
    follow_up_count: int = 0


# ── Interview helper functions ────────────────────────────────────────────────

def _get_question(session: dict, question_id: str) -> dict | None:
    """Look up a question by id from the session's question list."""
    for q in session.get("questions", []):
        if q.get("id") == question_id:
            return q
    return None


def _get_question_index(session: dict, question_id: str) -> int:
    """Return the 1-indexed position of a question in the session (1 if not found)."""
    for i, q in enumerate(session.get("questions", []), start=1):
        if q.get("id") == question_id:
            return i
    return 1


def _sync_session_to_db(session_id: str) -> None:
    """Write current in-memory answers + feedback to Supabase."""
    session = _interview_sessions.get(session_id)
    if not session:
        return
    sync_interview_session_progress(
        session_id,
        answers=session.get("answers", []),
        feedback=session.get("feedback", []),
    )


def _resolve_interview_session(session_id: str) -> dict | None:
    """Load session from memory, falling back to Supabase."""
    session = _interview_sessions.get(session_id)
    if session:
        return session

    row = get_interview_session_row(session_id)
    if not row:
        return None

    session = {
        "session_id": row["session_id"],
        "user_id": row.get("user_id"),
        "company": row.get("company", ""),
        "seniority": row.get("seniority", "senior"),
        "question_mode": row.get("question_mode", "mixed"),
        "questions": row.get("questions") or [],
        "answers": row.get("answers") or [],
        "feedback": row.get("feedback") or [],
        "compressed_turns": [],
        "active_follow_ups": {},
        "summary": row.get("summary"),
        "model_answers": row.get("model_answers") or {},
        "resume_fingerprint": None,
        "created_at": row.get("created_at"),
    }
    _interview_sessions[session_id] = session
    return session


def _feedback_for_question(session: dict, question_id: str) -> dict | None:
    """Return the most recent feedback entry for a question."""
    matches = [
        fb
        for fb in session.get("feedback", [])
        if fb.get("question_id") == question_id
    ]
    return matches[-1] if matches else None


def _answer_for_question(session: dict, question_id: str) -> dict | None:
    """Return the main answer turn for a question."""
    for turn in session.get("answers", []):
        if turn.get("question_id") == question_id:
            return turn
    return None


def _persist_answer(
    session_id: str,
    request: SubmitAnswerRequest,
    feedback: dict,
    follow_up_question: dict | None = None,
) -> dict:
    """
    Persists answer, feedback, and compressed turn to session store.
    Called from both /answer and /answer/stream after evaluation completes.

    Returns the stored feedback dict (includes question_id).
    """
    session = _interview_sessions.get(session_id)
    if not session or not feedback:
        return feedback

    stored_feedback = {**feedback, "question_id": request.question_id}
    session["feedback"].append(stored_feedback)

    if request.is_follow_up:
        follow_up_entry = {
            "question": follow_up_question or {
                "id": request.follow_up_id or str(uuid.uuid4()),
                "text": "",
                "trigger_reason": "follow_up",
            },
            "answer_text": request.answer_text,
        }
        for turn in session["answers"]:
            if turn.get("question_id") == request.question_id:
                turn.setdefault("follow_ups", []).append(follow_up_entry)
                break
    else:
        session["answers"].append({
            "question_id": request.question_id,
            "answer_text": request.answer_text,
            "follow_ups": [],
        })

    q_index = _get_question_index(session, request.question_id)
    compressed = InterviewAgent.compress_turn(
        q_index, request.answer_text, stored_feedback
    )
    session["compressed_turns"].append(compressed)
    _sync_session_to_db(session_id)
    return stored_feedback


def _session_complete(session: dict) -> bool:
    """True when all main questions have an AnswerTurn with answer_text."""
    answered_ids = {
        turn.get("question_id")
        for turn in session.get("answers", [])
        if turn.get("answer_text")
    }
    question_ids = [q.get("id") for q in session.get("questions", [])]
    return all(qid in answered_ids for qid in question_ids)


def _follow_up_count(session: dict, question_id: str) -> int:
    """Count follow-up answers already stored for a question (max 2 cap)."""
    for turn in session.get("answers", []):
        if turn.get("question_id") == question_id:
            return len(turn.get("follow_ups", []))
    return 0


# ── POST /api/interview/evaluate — non-streaming (kept for retry + summary) ──

@app.post("/api/interview/evaluate")
async def evaluate_answer(session_id: str, request: SubmitAnswerRequest):
    """
    Non-streaming evaluation endpoint. Used by the retry flow (Day 6) and
    the session summary endpoint (Day 4).

    Body: { question_id, answer_text, is_follow_up, follow_up_id? }

    Returns PerQuestionFeedback dict.  Persists feedback + compressed turn
    into the session store.
    """
    session = _interview_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = _get_question(session, request.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in session")

    compressed_turns = session.get("compressed_turns", [])

    feedback = _interview_agent.evaluate_answer({
        "question": question,
        "answer_text": request.answer_text,
        "compressed_turns": compressed_turns,
        "seniority": session["seniority"],
    })

    stored_feedback = _persist_answer(session_id, request, feedback)
    return stored_feedback


# ── POST /api/interview/follow-up ─────────────────────────────────────────────

@app.post("/api/interview/follow-up")
async def generate_follow_up(session_id: str, request: FollowUpRequest):
    """
    Generate a follow-up probe question when the original answer is incomplete.

    Body: { question_id, answer_text, follow_up_count }

    Returns { follow_up: FollowUpQuestion | null }
    """
    session = _interview_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = _get_question(session, request.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in session")

    follow_up = _interview_agent.generate_follow_up({
        "question": question,
        "answer_text": request.answer_text,
        "follow_up_count": request.follow_up_count,
    })

    return {"follow_up": follow_up}


# ── POST /api/interview/session/{id}/answer — non-streaming (retry + tests) ──

@app.post("/api/interview/session/{session_id}/answer")
async def submit_answer(session_id: str, request: SubmitAnswerRequest):
    """
    Evaluates an answer (non-streaming). Persists feedback and compressed turn.
    Generates follow-up probe if warranted.

    Returns:
    {
      feedback:         PerQuestionFeedback,
      follow_up:        FollowUpQuestion | null,
      session_complete: bool
    }
    """
    session = _interview_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = _get_question(session, request.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in session")

    feedback = _interview_agent.evaluate_answer({
        "question": question,
        "answer_text": request.answer_text,
        "compressed_turns": session["compressed_turns"],
        "seniority": session["seniority"],
    })

    follow_up_question = None
    if request.is_follow_up and request.follow_up_id:
        follow_up_question = session.get("active_follow_ups", {}).get(request.question_id)

    stored_feedback = _persist_answer(
        session_id,
        request,
        feedback,
        follow_up_question=follow_up_question,
    )

    follow_up = None
    if not request.is_follow_up:
        follow_up = _interview_agent.generate_follow_up({
            "question": question,
            "answer_text": request.answer_text,
            "follow_up_count": _follow_up_count(session, request.question_id),
        })
        if follow_up:
            session.setdefault("active_follow_ups", {})[request.question_id] = follow_up

    return {
        "feedback": stored_feedback,
        "follow_up": follow_up,
        "session_complete": _session_complete(session),
    }


# ── POST /api/interview/session/{id}/summary ──────────────────────────────────

@app.post("/api/interview/session/{session_id}/summary")
async def get_summary(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Generates the post-session summary. Call once, after session_complete=true.

    Returns: SessionSummary dict
    """
    session = _resolve_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("user_id") and session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this session")

    if not _session_complete(session):
        raise HTTPException(
            status_code=400,
            detail="Session not complete — answer all questions before requesting summary",
        )

    summary = _interview_agent.generate_summary({
        "questions": session["questions"],
        "answers": session["answers"],
        "all_feedback": session["feedback"],
        "compressed_turns": session["compressed_turns"],
        "seniority": session["seniority"],
        "company": session["company"],
    })

    complete_interview_session(session_id, summary)
    session["summary"] = summary

    resume_fp = session.get("resume_fingerprint")
    if resume_fp and session.get("user_id"):
        update_ledger(
            session["user_id"],
            resume_fp,
            session.get("questions") or [],
        )

    return summary


@app.get("/api/interview/sessions")
async def list_interview_sessions(
    user_id: str = Depends(get_current_user_id),
    limit: int = 10,
):
    """
    Return the N most recent completed sessions for the authenticated user.
    Only sessions with a non-null summary are included.
    """
    rows = list_completed_interview_sessions(user_id, limit=limit)
    sessions = []
    for row in rows:
        summary = row.get("summary") or {}
        if not isinstance(summary, dict):
            continue
        sessions.append(
            {
                "session_id": row["session_id"],
                "company": row.get("company", ""),
                "seniority": row.get("seniority", ""),
                "created_at": row.get("created_at"),
                "top_strength": summary.get("top_strength", ""),
                "top_gap": summary.get("top_gap", ""),
                "recommended_next_dimension": summary.get(
                    "recommended_next_dimension", "growth_mindset"
                ),
                "dimension_scorecard": summary.get("dimension_scorecard", []),
                "anti_pattern_report": summary.get("anti_pattern_report", []),
            }
        )
    return {"sessions": sessions}


@app.post("/api/interview/session/{session_id}/model-answer/{question_id}")
async def get_model_answer(
    session_id: str,
    question_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Lazy-load a model answer for one question. Cached in Supabase model_answers jsonb.
    """
    session = _resolve_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("user_id") and session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this session")

    cached = (session.get("model_answers") or {}).get(question_id)
    if cached:
        return cached

    question = _get_question(session, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    answer_turn = _answer_for_question(session, question_id)
    if not answer_turn:
        raise HTTPException(status_code=400, detail="Question not yet answered")

    answer_text = str(answer_turn.get("answer_text", ""))
    if len(answer_text.split()) < 50:
        return {"text": None, "what_changed": None, "skipped": True}

    feedback = _feedback_for_question(session, question_id)
    if not feedback:
        raise HTTPException(status_code=400, detail="Feedback not available yet")

    result = _interview_agent.generate_model_answer({
        "question": question,
        "answer_text": answer_text,
        "feedback": feedback,
        "seniority": session["seniority"],
        "company": session["company"],
    })

    cache_model_answer(session_id, question_id, result)
    session.setdefault("model_answers", {})[question_id] = result

    return result


# ── POST /api/interview/session/{id}/answer/stream — primary evaluation ───────

@app.post("/api/interview/session/{session_id}/answer/stream")
async def submit_answer_stream(session_id: str, request: SubmitAnswerRequest):
    """
    Primary session evaluation endpoint — streaming.

    Body: { question_id, answer_text, is_follow_up, follow_up_id? }

    Emits structured SSE chunks. Chunk types (in order):
      verdict → best_line → level_signal → presence → dimension → missing (if not strong)
      → ap_fired × N → coaching_close → done
      error on failure.

    The non-streaming /evaluate endpoint is kept for the retry flow.
    """
    session = _interview_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = _get_question(session, request.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in session")

    compressed_turns = session.get("compressed_turns", [])

    async def event_stream():
        collected_chunks: list[dict] = []
        try:
            async for chunk in _interview_agent.evaluate_answer_stream({
                "question": question,
                "answer_text": request.answer_text,
                "compressed_turns": compressed_turns,
                "seniority": session["seniority"],
            }):
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.05)
                collected_chunks.append(chunk)

                if chunk["type"] == "done":
                    feedback = _reconstruct_feedback(collected_chunks)
                    follow_up_question = None
                    if request.is_follow_up and request.follow_up_id:
                        follow_up_question = session.get("active_follow_ups", {}).get(
                            request.question_id
                        )
                    stored = _persist_answer(
                        session_id,
                        request,
                        feedback,
                        follow_up_question=follow_up_question,
                    )
                    if stored and not request.is_follow_up:
                        probe = _interview_agent.generate_follow_up({
                            "question": question,
                            "answer_text": request.answer_text,
                            "follow_up_count": _follow_up_count(
                                session, request.question_id
                            ),
                        })
                        if probe:
                            session.setdefault("active_follow_ups", {})[
                                request.question_id
                            ] = probe

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _reconstruct_feedback(chunks: list[dict]) -> dict | None:
    """
    Reconstruct a PerQuestionFeedback dict from the ordered SSE chunks emitted
    by evaluate_answer_stream.  Returns None if any required chunk is missing.
    """
    feedback: dict = {}
    anti_patterns: list[dict] = []

    for chunk in chunks:
        t = chunk.get("type")
        c = chunk.get("content")
        if t == "verdict":
            feedback["overall_verdict"] = c
        elif t == "best_line":
            feedback["best_line"] = c
        elif t == "level_signal":
            feedback["level_signal"] = c
        elif t == "presence" and isinstance(c, dict):
            feedback["executive_presence"] = c.get("executive_presence", "not_assessable")
            feedback["authenticity_note"] = c.get("authenticity_note", "")
        elif t == "dimension":
            feedback["dimension_score"] = c
        elif t == "ap_fired":
            anti_patterns.append(c)
        elif t == "coaching_close":
            feedback["coaching_close"] = c

    required = ("overall_verdict", "best_line", "dimension_score", "level_signal")
    if not all(k in feedback for k in required):
        return None

    feedback["anti_patterns_fired"] = anti_patterns
    feedback.setdefault("executive_presence", "not_assessable")
    feedback.setdefault("authenticity_note", "")
    feedback.setdefault("coaching_close", "")
    return feedback
