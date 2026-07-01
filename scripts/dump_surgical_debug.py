#!/usr/bin/env python3
"""Dump surgical-fix before/after JSON to tempjsons/ and inspect a downloaded DOCX."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.surgical_debug import write_surgical_snapshot, _TEMPJSONS_ROOT
from engine.surgical_export import prepare_surgical_export
from engine.resume_builder import build_final_docx


def _latest_job_file(cache_dir: Path) -> Path | None:
    jobs = [p for p in cache_dir.glob("*.json") if p.name != "stage_cache.json"]
    if not jobs:
        return None
    return max(jobs, key=lambda p: p.stat().st_mtime)


def dump_job(job_path: Path) -> None:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job_id = job_path.stem
    job.setdefault("job_id", job_id)

    before = write_surgical_snapshot(job_id, job, "before_fix_manual")
    patched = job.get("resume_text_patched") or ""
    if patched.strip():
        after = write_surgical_snapshot(job_id, job, "after_fix_manual")
        result = job.get("result") or {}
        structured = result.get("resume") or {}
        rs = (
            (structured.get("resume_sections") if isinstance(structured, dict) else None)
            or {}
        )
        export_structured = prepare_surgical_export(structured, rs, patched)
        export_preview = _TEMPJSONS_ROOT / f"{job_id}_export_structured_preview.json"
        exp_sec = (export_structured.get("resume_sections") or {}).get("experience", {})
        export_preview.write_text(
            json.dumps(
                {
                    "experience_full_text_preview": (
                        exp_sec.get("full_text", "")[:5000]
                        if isinstance(exp_sec, dict)
                        else ""
                    ),
                    "experience_marker_count": (
                        exp_sec.get("full_text", "").count("##COMPANY##")
                        if isinstance(exp_sec, dict)
                        else 0
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {before}\nWrote {after}\nWrote {export_preview}")
    else:
        print(f"Wrote {before} (no resume_text_patched on job)")


def inspect_docx(docx_path: Path) -> None:
    from docx import Document

    doc = Document(str(docx_path))
    lines = []
    for i, p in enumerate(doc.paragraphs):
        style = p.style.name if p.style else "None"
        text = p.text or ""
        lines.append(f"[{i:03d}] {style:20s} {text}")

    out = _TEMPJSONS_ROOT / f"docx_inspect_{docx_path.stem}.txt"
    _TEMPJSONS_ROOT.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} ({len(lines)} paragraphs)")


def main() -> None:
    cache = ROOT / "backend" / ".job_cache"
    job_file = _latest_job_file(cache) if cache.is_dir() else None
    if job_file:
        print(f"Latest job: {job_file.name}")
        dump_job(job_file)
    else:
        print("No job cache files found.")

    docx_arg = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\mathu\Downloads\resume (6).docx"
    docx_path = Path(docx_arg)
    if docx_path.is_file():
        inspect_docx(docx_path)
    else:
        print(f"DOCX not found: {docx_path}")


if __name__ == "__main__":
    main()
