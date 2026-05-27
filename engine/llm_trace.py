"""
LLM and pipeline phase timing for latency diagnosis.

Every orchestrator run writes a trace file under logs/llm_traces/ (override with
LLM_TRACE_DIR). Set LLM_TRACE_FILE=0 to disable file output.

Console grep (when logging level is INFO):
  LLM_TRACE   — individual model calls
  PHASE_TRACE — non-LLM pipeline steps
  TRACE_SUMMARY — ranked breakdown at end of run
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_llm_records: list[dict[str, Any]] = []
_phase_records: list[dict[str, Any]] = []
_run_label: str = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def trace_output_dir() -> Path:
    """Directory for per-run trace JSON and text summaries."""
    raw = (os.getenv("LLM_TRACE_DIR") or "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "logs" / "llm_traces"


def trace_file_enabled() -> bool:
    """True unless LLM_TRACE_FILE is explicitly disabled."""
    return (os.getenv("LLM_TRACE_FILE") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def reset_trace(run_label: str = "") -> None:
    """Clear accumulators at the start of an orchestrator run."""
    global _run_label
    with _lock:
        _llm_records.clear()
        _phase_records.clear()
        _run_label = run_label


def record_llm_call(
    *,
    agent: str,
    provider: str,
    model: str,
    duration_ms: float,
    prompt_chars: int,
    call_label: str = "",
) -> None:
    """Record one LLM round-trip (logged immediately and kept for summary)."""
    entry = {
        "agent": agent,
        "provider": provider,
        "model": model,
        "duration_ms": round(duration_ms, 1),
        "prompt_chars": prompt_chars,
        "call_label": call_label,
    }
    with _lock:
        _llm_records.append(entry)

    label_suffix = f" label={call_label}" if call_label else ""
    logger.info(
        "LLM_TRACE agent=%s provider=%s model=%s duration_ms=%.0f prompt_chars=%d%s",
        agent,
        provider,
        model,
        duration_ms,
        prompt_chars,
        label_suffix,
    )


def record_phase(name: str, duration_ms: float) -> None:
    """Record a completed phase (for manual timing outside context managers)."""
    entry = {"name": name, "duration_ms": round(duration_ms, 1)}
    with _lock:
        _phase_records.append(entry)
    logger.info("PHASE_TRACE phase=%s duration_ms=%.0f", name, duration_ms)


@dataclass
class PhaseTimer:
    """Context manager for timing a pipeline phase."""

    name: str
    _start: float = field(default=0.0, init=False)

    def __enter__(self) -> PhaseTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        duration_ms = (time.perf_counter() - self._start) * 1000
        with _lock:
            _phase_records.append(
                {"name": self.name, "duration_ms": round(duration_ms, 1)}
            )
        logger.info("PHASE_TRACE phase=%s duration_ms=%.0f", self.name, duration_ms)


def build_trace_summary() -> dict[str, Any]:
    """Build ranked LLM + phase breakdown for the current run."""
    with _lock:
        llm = list(_llm_records)
        phases = list(_phase_records)
        run_label = _run_label

    llm_ranked = sorted(llm, key=lambda r: r["duration_ms"], reverse=True)
    phases_ranked = sorted(phases, key=lambda r: r["duration_ms"], reverse=True)

    for rank, rec in enumerate(llm_ranked, start=1):
        rec["rank"] = rank

    total_llm_ms = sum(r["duration_ms"] for r in llm)
    total_phase_ms = sum(r["duration_ms"] for r in phases)

    slowest_llm = llm_ranked[0] if llm_ranked else None
    slowest_phase = phases_ranked[0] if phases_ranked else None

    return {
        "run_id": run_label or "unknown",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "llm_calls": len(llm),
            "total_llm_ms": round(total_llm_ms, 1),
            "phases": len(phases),
            "total_phase_ms": round(total_phase_ms, 1),
        },
        "slowest_llm": slowest_llm,
        "slowest_phase": slowest_phase,
        "llm_calls": llm_ranked,
        "phases": phases_ranked,
    }


def _format_trace_text(summary: dict[str, Any]) -> str:
    """Human-readable trace report for logs/llm_traces/*.txt."""
    totals = summary["totals"]
    lines = [
        f"TRACE SUMMARY run={summary['run_id']}",
        f"recorded_at={summary['recorded_at']}",
        "",
        (
            f"Total LLM time: {totals['total_llm_ms']:.0f} ms "
            f"({totals['llm_calls']} calls)"
        ),
        (
            f"Total phase time: {totals['total_phase_ms']:.0f} ms "
            f"({totals['phases']} phases)"
        ),
        "",
        "LLM calls (slowest first):",
    ]

    if summary["llm_calls"]:
        for rec in summary["llm_calls"]:
            label = rec.get("call_label") or ""
            label_part = f" [{label}]" if label else ""
            lines.append(
                f"  #{rec['rank']} {rec['agent']} ({rec['model']}) "
                f"{rec['duration_ms']:.0f} ms "
                f"prompt_chars={rec['prompt_chars']}{label_part}"
            )
    else:
        lines.append("  (none)")

    lines.extend(["", "Pipeline phases (slowest first):"])
    if summary["phases"]:
        for rec in summary["phases"]:
            lines.append(
                f"  {rec['name']} {rec['duration_ms']:.0f} ms"
            )
    else:
        lines.append("  (none)")

    slowest = summary.get("slowest_llm")
    if slowest:
        lines.extend(
            [
                "",
                (
                    f"Slowest LLM: {slowest['agent']} "
                    f"({slowest['duration_ms']:.0f} ms)"
                ),
            ]
        )

    return "\n".join(lines) + "\n"


def _safe_run_filename(run_id: str) -> str:
    """Filesystem-safe stem from run id."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in run_id)
    return safe[:120] or "unknown"


def write_trace_summary_file(summary: dict[str, Any]) -> Path | None:
    """
    Persist trace summary as JSON + text under trace_output_dir().

    Also writes latest.json and latest.txt for quick inspection.
    """
    if not trace_file_enabled():
        return None

    out_dir = trace_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = _safe_run_filename(str(summary["run_id"]))
    json_path = out_dir / f"{stem}.json"
    text_path = out_dir / f"{stem}.txt"

    payload = json.dumps(summary, indent=2, ensure_ascii=False)
    json_path.write_text(payload + "\n", encoding="utf-8")
    text_path.write_text(_format_trace_text(summary), encoding="utf-8")

    (out_dir / "latest.json").write_text(payload + "\n", encoding="utf-8")
    (out_dir / "latest.txt").write_text(_format_trace_text(summary), encoding="utf-8")

    logger.info("TRACE_FILE json=%s txt=%s", json_path, text_path)
    return json_path


def log_trace_summary() -> Path | None:
    """Emit ranked LLM + phase breakdown to logs and trace files."""
    summary = build_trace_summary()
    totals = summary["totals"]

    logger.info(
        "TRACE_SUMMARY run=%s llm_calls=%d total_llm_ms=%.0f phases=%d total_phase_ms=%.0f",
        summary["run_id"],
        totals["llm_calls"],
        totals["total_llm_ms"],
        totals["phases"],
        totals["total_phase_ms"],
    )

    for rec in summary["llm_calls"]:
        label = rec.get("call_label") or ""
        label_part = f" [{label}]" if label else ""
        logger.info(
            "  LLM #%d agent=%s model=%s duration_ms=%.0f prompt_chars=%d%s",
            rec["rank"],
            rec["agent"],
            rec["model"],
            rec["duration_ms"],
            rec["prompt_chars"],
            label_part,
        )

    for rec in summary["phases"]:
        logger.info(
            "  PHASE %s duration_ms=%.0f",
            rec["name"],
            rec["duration_ms"],
        )

    return write_trace_summary_file(summary)
