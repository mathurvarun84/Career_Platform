"""Write before/after surgical-fix JSON snapshots to tempjsons/ for debugging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TEMPJSONS_ROOT = Path(__file__).resolve().parents[1] / "tempjsons"


def _unwrap_rewrites(rewrites: Any) -> dict:
    if not isinstance(rewrites, dict):
        return {}
    if "rewrites" in rewrites and isinstance(rewrites.get("rewrites"), dict):
        return rewrites["rewrites"]
    return rewrites


def build_surgical_snapshot(job: dict[str, Any], phase: str) -> dict[str, Any]:
    """Build a JSON-serializable snapshot for surgical-fix debugging."""
    result = job.get("result") or {}
    resume = result.get("resume") or {}
    rs = resume.get("resume_sections") or {}
    exp = rs.get("experience") if isinstance(rs, dict) else {}
    subs = exp.get("sub_entries", []) if isinstance(exp, dict) else []
    rw = _unwrap_rewrites(job.get("rewrites") or result.get("rewrites") or {})
    exp_rw = rw.get("experience") if isinstance(rw, dict) else {}
    balanced = exp_rw.get("balanced", "") if isinstance(exp_rw, dict) else ""

    patches = result.get("patches") or []
    exp_full = (exp.get("full_text") or "") if isinstance(exp, dict) else ""
    return {
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job.get("job_id") or job.get("id"),
        "resume_text_original": job.get("resume_text") or "",
        "resume_text_patched": job.get("resume_text_patched") or "",
        "patches": patches,
        "experience_sub_entries": subs,
        "experience_original_full_text": exp_full,
        "experience_original_full_text_preview": exp_full[:4000],
        "rewrites_experience_balanced_preview": balanced[:4000],
        "experience_sub_entry_count": len(subs),
        "experience_sub_entry_labels": [
            (s.get("label", "")[:80] if isinstance(s, dict) else str(s)[:80])
            for s in subs
        ],
        "experience_original_full_text_len": len(exp_full),
        "rewrites_experience_balanced_len": len(balanced),
        "rewrites_experience_marker_count": balanced.count("##COMPANY##"),
        "resume_sections_keys": list(rs.keys()) if isinstance(rs, dict) else [],
    }


def write_surgical_snapshot(
    job_id: str,
    job: dict[str, Any],
    phase: str,
    *,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Persist snapshot to tempjsons/{job_id}_{phase}.json."""
    _TEMPJSONS_ROOT.mkdir(parents=True, exist_ok=True)
    payload = build_surgical_snapshot(job, phase)
    if extra:
        payload["extra"] = extra
    path = _TEMPJSONS_ROOT / f"{job_id}_{phase}.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logging.info("Surgical debug JSON written: %s", path)
    return path


def write_before_after_pair(job_id: str, job: dict[str, Any]) -> tuple[Path, Path]:
    """Write paired before_fix and after_fix JSON files."""
    before = write_surgical_snapshot(job_id, job, "before_fix")
    after = write_surgical_snapshot(job_id, job, "after_fix")
    return before, after
