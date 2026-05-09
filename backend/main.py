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
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from backend.agents.jd_fetcher import JDFetcherAgent
from engine.resume_builder import build_final_docx
from orchestrator import Orchestrator
from parser import parse_resume
from backend.schemas.jd_fetch_schema import FetchJDRequest, FetchJDResponse


logger = logging.getLogger(__name__)

app = FastAPI(title="Resume Intelligence Platform V2")
job_store: Dict[str, Dict[str, Any]] = {}

# Persist completed jobs so download still works after uvicorn reload / process restart.
_JOB_CACHE_DIR = Path(__file__).resolve().parent / ".job_cache"
_STAGE_CACHE_PATH = _JOB_CACHE_DIR / "stage_cache.json"


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


def _load_stage_cache() -> Dict[str, Dict[str, Any]]:
    if not _STAGE_CACHE_PATH.is_file():
        return {}
    try:
        raw = json.loads(_STAGE_CACHE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _persist_stage_cache(stage_cache: Dict[str, Dict[str, Any]]) -> None:
    try:
        _JOB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _STAGE_CACHE_PATH.write_text(
            json.dumps(stage_cache, default=str),
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


def _json_event(payload: dict) -> str:
    """Serialize one SSE data event."""
    return f"data: {json.dumps(payload, default=str)}\n\n"


def run_pipeline_task(
    job_id: str,
    temp_path: str,
    jd_text: str,
    run_sim: bool,
    resume_hash: str,
    jd_hash: str,
) -> None:
    """Run the full pipeline in a background task and update job_store."""
    try:
        resume_text = parse_resume(temp_path)
        job_store[job_id]["resume_text"] = resume_text

        def progress_cb(event: dict) -> None:
            event = {**event, "status": "running"}
            job_store[job_id]["progress"].append(event)

        def partial_result_cb(partial: dict) -> None:
            if not isinstance(partial, dict):
                return
            current = job_store[job_id].get("result") or {}
            merged = {**current, **partial}
            job_store[job_id]["result"] = merged
            job_store[job_id]["progress"].append({
                "status": "running",
                "type": "partial",
                "partial_result": partial,
            })

        cache_key = f"{resume_hash}:{jd_hash or 'none'}"
        cached_stage_data = stage_cache.get(cache_key)

        def stage_cache_cb(stage_data: dict) -> None:
            stage_cache[cache_key] = stage_data
            _persist_stage_cache(stage_cache)

        result = Orchestrator(user_id=job_id).run_full_evaluation(
            resume_text=resume_text,
            jd_text=jd_text,
            run_sim=run_sim,
            progress_cb=progress_cb,
            partial_result_cb=partial_result_cb,
            cached_stage_data=cached_stage_data,
            stage_cache_cb=stage_cache_cb,
        )
        job_store[job_id]["result"] = result
        job_store[job_id]["status"] = "complete"
        job_store[job_id]["progress"].append({
            "step": 4,
            "label": "Analysis complete",
            "pct": 100,
            "status": "complete",
            "result": result,
        })
    except Exception as exc:
        logger.exception("Analysis failed for job %s", job_id)
        job_store[job_id]["status"] = "error"
        job_store[job_id]["error"] = str(exc)
        job_store[job_id]["progress"].append({
            "step": 0,
            "label": str(exc),
            "pct": 100,
            "status": "error",
            "error": str(exc),
        })
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        _persist_job(job_id)


@app.post("/api/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    resume: UploadFile = File(...),
    jd_text: str = Form(""),
    run_sim: bool = Form(False),
) -> dict:
    """Accept a resume upload and start analysis."""
    suffix = os.path.splitext(resume.filename or "resume.txt")[1] or ".txt"
    resume_bytes = await resume.read()
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as tmp:
        tmp.write(resume_bytes)

    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "running",
        "progress": [{"step": 1, "label": "Queued", "pct": 1, "status": "running"}],
        "result": None,
        "error": None,
        "resume_text": "",
    }
    resume_hash = hashlib.sha256(resume_bytes).hexdigest()
    jd_hash = hashlib.sha256((jd_text or "").encode("utf-8")).hexdigest() if jd_text else ""
    background_tasks.add_task(run_pipeline_task, job_id, temp_path, jd_text, run_sim, resume_hash, jd_hash)
    return {"job_id": job_id}


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
