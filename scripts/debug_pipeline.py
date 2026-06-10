#!/usr/bin/env python3
"""Debug fix_plan pipeline from job cache or session memory."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _latest_job(cache_dir: Path) -> Path | None:
    jobs = [p for p in cache_dir.glob("*.json") if p.name != "stage_cache.json"]
    return max(jobs, key=lambda p: p.stat().st_mtime) if jobs else None


def analyze_result(result: dict, label: str) -> dict:
    fp = result.get("fix_plan") or []
    gap = result.get("gap") or {}
    pf = [x for x in (gap.get("priority_fixes") or []) if isinstance(x, dict)]
    patches = result.get("patches") or []
    sg = gap.get("section_gaps") or []

    surgical = [i for i in fp if i.get("kind") == "surgical_patch"]
    coaching = [i for i in fp if i.get("kind") == "coaching"]
    null_patch = [i for i in surgical if not i.get("patch_id")]
    evidence_mismatch = [
        i for i in fp if i.get("gap_type") == "evidence" and i.get("kind") != "coaching"
    ]

    patch_by_entry = {
        p.get("sub_entry_id", "").lower(): p for p in patches if p.get("sub_entry_id")
    }

    print(f"\n{'='*72}")
    print(f"PIPELINE DEBUG: {label}")
    print(f"{'='*72}")
    print(f"api_version:     {result.get('api_version')}")
    print(f"fix_plan:        {len(fp)}")
    print(f"priority_fixes:  {len(pf)}")
    print(f"patches:         {len(patches)}")
    print(f"section_gaps:    {len(sg)}")
    print(f"kinds:           {dict(Counter(i.get('kind') for i in fp))}")
    print(f"gap_types:       {dict(Counter(i.get('gap_type') for i in fp))}")
    print()
    print("ISSUES:")
    print(f"  surgical null patch_id:        {len(null_patch)}")
    print(f"  surgical no after_text:        {sum(1 for i in surgical if not i.get('after_text'))}")
    print(f"  surgical no before_text:       {sum(1 for i in surgical if not i.get('before_text'))}")
    print(f"  evidence -> non-coaching:      {len(evidence_mismatch)}")
    print(f"  coaching items:                {len(coaching)}")
    print(f"  coaching missing question:     {sum(1 for i in coaching if not i.get('coaching_question'))}")

    # Health verdict
    api_v = result.get("api_version") or 1
    patch_linked = sum(1 for i in fp if i.get("patch_id"))
    if api_v < 2 or not fp:
        verdict = "RED"
    elif null_patch or evidence_mismatch:
        verdict = "AMBER"
    elif patch_linked == len(surgical) and len(coaching) > 0:
        verdict = "GREEN"
    else:
        verdict = "AMBER"
    print(f"\nVERDICT: {verdict}")

    print("\n--- fix_plan items ---")
    for idx, item in enumerate(fp):
        flags = []
        if item.get("kind") == "surgical_patch" and not item.get("patch_id"):
            flags.append("NO_PATCH_ID")
        if item.get("kind") == "surgical_patch" and not item.get("after_text"):
            flags.append("NO_AFTER")
        if item.get("gap_type") == "evidence" and item.get("kind") != "coaching":
            flags.append("EVID_MISMATCH")
        sub = (item.get("sub_label") or "")[:40]
        after = (item.get("after_text") or "")[:70]
        before = (item.get("before_text") or "")[:50]
        print(
            f"[{idx}] {item.get('kind'):16} {item.get('gap_type'):10} "
            f"{item.get('section')} | {sub}"
        )
        print(
            f"     entry_id={item.get('entry_id')} conf={item.get('entry_id_confidence')} "
            f"patch_id={item.get('patch_id')}"
        )
        print(f"     after={after!r} before={before!r}")
        if flags:
            print(f"     FLAGS: {','.join(flags)}")

    print("\n--- priority_fixes ---")
    for fix in pf:
        sub = (fix.get("sub_label") or "")[:35]
        print(f"{fix.get('gap_type'):10} {fix.get('section')} | {sub}")
        print(
            f"  entry_id={fix.get('entry_id')} conf={fix.get('entry_id_confidence', '?')} "
            f"req={fix.get('requires_user_input')}"
        )
        gr = (fix.get("gap_reason") or "")[:55]
        ri = (fix.get("rewrite_instruction") or "")[:55]
        print(f"  gap_reason={gr!r}")
        print(f"  rewrite_instruction={ri!r}")
        print(
            f"  original_text={'yes' if fix.get('original_text') else 'NO'} "
            f"coaching_q={'yes' if fix.get('coaching_question') else 'NO'}"
        )

    print("\n--- patches ---")
    for p in patches:
        print(
            f"  {p.get('sub_entry_id')} | {p.get('section')} | "
            f"orig={len(p.get('original_text') or '')} repl={len(p.get('replacement_text') or '')}"
        )

    if null_patch:
        print("\n--- NULL PATCH cross-check ---")
        for item in null_patch:
            eid = (item.get("entry_id") or "").lower()
            print(f"  lookup={eid!r} match={eid in patch_by_entry} sub={item.get('sub_label')}")
            near = [
                k
                for k in patch_by_entry
                if eid and (k.startswith(eid[:15]) or eid.startswith(k[:15]))
            ]
            if near:
                print(f"    near-miss keys: {near}")

    return {
        "verdict": verdict,
        "null_patch": len(null_patch),
        "evidence_mismatch": len(evidence_mismatch),
        "coaching": len(coaching),
    }


def main() -> None:
    job_arg = sys.argv[1] if len(sys.argv) > 1 else None
    cache = ROOT / "backend" / ".job_cache"

    if job_arg:
        job_path = cache / job_arg if not job_arg.endswith(".json") else Path(job_arg)
        if not job_path.exists():
            job_path = cache / f"{job_arg}.json"
    else:
        job_path = _latest_job(cache)

    if job_path and job_path.exists():
        job = json.loads(job_path.read_text(encoding="utf-8"))
        result = job.get("result") or job
        analyze_result(result, job_path.name)
        # Export trimmed JSON for Pipeline Inspector paste
        out = ROOT / "scripts" / "pipeline_inspector_payload.json"
        payload = {
            k: result.get(k)
            for k in (
                "api_version",
                "job_id",
                "session_id",
                "ats",
                "resume",
                "gap",
                "patches",
                "fix_plan",
                "rewrites",
                "sim",
                "percentile",
                "positioning",
                "role_fit",
            )
            if result.get(k) is not None
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nExported inspector payload -> {out}")
        return

    print("No job cache file found.")


if __name__ == "__main__":
    main()
