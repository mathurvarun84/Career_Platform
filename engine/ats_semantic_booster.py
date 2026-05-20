"""
ATS semantic booster — post-processes deterministic ATS scores with one LLM pass.

Adjusts only keyword_match and impact_metrics subscores based on experience/project
bullet quality. formatting and readability are never modified.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "gpt-5-mini"
MAX_COMPLETION_TOKENS = 400
IMPACT_DELTA_RANGE = (-8, 8)
KEYWORD_DELTA_RANGE = (-6, 6)

_SYSTEM_PROMPT = """You are an ATS scoring auditor. You receive resume bullet points from the experience
section and two baseline scores from a deterministic scorer.

Your job is to return two ADJUSTMENT values (integers, can be negative) that correct
for what the regex scorer gets wrong:

1. impact_quality_delta: Adjust impact_metrics score (range: -8 to +8)
   - POSITIVE when: bullets show clear causal impact ("Reduced X by Y% by doing Z")
   - NEGATIVE when: numbers are noise (team sizes, dates, task counts with no outcome)
   - ZERO when: impact is average/mixed

2. keyword_centrality_delta: Adjust keyword_match score (range: -6 to +6)
   - POSITIVE when: tech keywords are central to engineering work described
   - NEGATIVE when: keywords appear as decorative mentions or in a skills list dump
   - ZERO when: keyword usage is typical

Rules:
- Evaluate the OVERALL pattern across all bullets, not individual lines
- Small adjustments are better than large ones — be conservative
- If a JD is provided, weight adjustments toward JD-relevant signals
- Return ONLY valid JSON, no explanation, no markdown

Output format:
{"impact_quality_delta": <int>, "keyword_centrality_delta": <int>, "rationale": "<one sentence>"}"""


def _extract_experience_bullets(resume_sections: dict) -> str:
    """Pull sub_entry verbatim_text from experience and projects sections."""
    bullets: list[str] = []
    for section_name in ("experience", "projects"):
        section = resume_sections.get(section_name)
        if section is None:
            continue
        sub_entries = (
            getattr(section, "sub_entries", None)
            or (section.get("sub_entries") if isinstance(section, dict) else None)
            or []
        )
        for entry in sub_entries:
            label = (
                getattr(entry, "label", None)
                or (entry.get("label") if isinstance(entry, dict) else "")
                or ""
            )
            text = (
                getattr(entry, "verbatim_text", None)
                or (entry.get("verbatim_text") if isinstance(entry, dict) else "")
                or ""
            )
            if text:
                bullets.append(f"[{label}]\n{text}")
    return "\n\n".join(bullets)


def _build_user_prompt(experience_bullets: str, baseline: dict, jd_text: str | None) -> str:
    jd_block = f"\nJOB DESCRIPTION (use for context):\n{jd_text[:800]}" if jd_text else ""
    return f"""BASELINE SCORES (from deterministic scorer):
- impact_metrics: {baseline['impact_metrics']}/25
- keyword_match: {baseline['keyword_match']}/25

EXPERIENCE BULLETS TO EVALUATE:
{experience_bullets[:2000]}
{jd_block}

Return your adjustments as JSON."""


def _apply_delta(baseline_val: int, delta: int, lo: int = 0, hi: int = 25) -> int:
    return max(lo, min(hi, baseline_val + delta))


def _clamp_delta(delta: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(delta)))


def _parse_boost_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.index("{")
        end = cleaned.rindex("}") + 1
        return json.loads(cleaned[start:end])


def _call_semantic_llm(user_prompt: str) -> tuple[dict[str, Any], dict[str, int | None]]:
    """
    Call OpenAI for semantic score adjustments.

    Returns:
        Tuple of (parsed JSON dict, usage dict with prompt/completion/total tokens).
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")

    client = OpenAI(api_key=api_key)
    request_kwargs: dict[str, Any] = {
        "model": MODEL,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    if not MODEL.lower().startswith("gpt-5"):
        request_kwargs["temperature"] = 0
    response = client.chat.completions.create(**request_kwargs)
    raw = response.choices[0].message.content or "{}"
    usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
        "completion_tokens": getattr(response.usage, "completion_tokens", None),
        "total_tokens": getattr(response.usage, "total_tokens", None),
    }
    return _parse_boost_json(raw), usage


def _fallback_result(ats_result: dict, error: str) -> dict:
    result = copy.deepcopy(ats_result)
    result["semantic_boost"] = {"applied": False, "error": error}
    return result


def semantic_boost(
    ats_result: dict,
    resume_sections: dict,
    jd_text: str | None = None,
) -> dict:
    """
    Post-process deterministic ATS scores with one semantic LLM pass.

    Adjusts keyword_match and impact_metrics only. Never raises — returns the
    original scores on any failure path.

    Args:
        ats_result: Output dict from score_resume().
        resume_sections: A1 resume_sections mapping section names to SectionText/dict.
        jd_text: Optional raw JD text for centrality context.

    Returns:
        Copy of ats_result with adjusted breakdown/score and semantic_boost metadata.
    """
    experience_bullets = _extract_experience_bullets(resume_sections)
    if not experience_bullets.strip():
        logger.info("[ATS_BOOST] skipped — no experience bullets")
        return _fallback_result(ats_result, "no_experience_bullets")

    breakdown = (ats_result or {}).get("breakdown") or {}
    baseline = {
        "impact_metrics": int(breakdown.get("impact_metrics", 0) or 0),
        "keyword_match": int(breakdown.get("keyword_match", 0) or 0),
    }
    user_prompt = _build_user_prompt(experience_bullets, baseline, jd_text)

    try:
        parsed, usage = _call_semantic_llm(user_prompt)
        impact_delta = _clamp_delta(
            int(parsed.get("impact_quality_delta", 0) or 0),
            *IMPACT_DELTA_RANGE,
        )
        keyword_delta = _clamp_delta(
            int(parsed.get("keyword_centrality_delta", 0) or 0),
            *KEYWORD_DELTA_RANGE,
        )
        rationale = str(parsed.get("rationale") or "").strip()
    except Exception as exc:
        logger.warning("[ATS_BOOST] LLM call failed: %s", exc)
        return _fallback_result(ats_result, str(exc))

    logger.info(
        "[ATS_BOOST] model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s "
        "impact_delta=%s keyword_delta=%s",
        MODEL,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
        impact_delta,
        keyword_delta,
    )

    result = copy.deepcopy(ats_result)
    new_breakdown = dict(result.get("breakdown") or {})
    new_breakdown["impact_metrics"] = _apply_delta(baseline["impact_metrics"], impact_delta)
    new_breakdown["keyword_match"] = _apply_delta(baseline["keyword_match"], keyword_delta)
    result["breakdown"] = new_breakdown
    result["score"] = sum(int(v or 0) for v in new_breakdown.values())
    result["semantic_boost"] = {
        "applied": True,
        "impact_quality_delta": impact_delta,
        "keyword_centrality_delta": keyword_delta,
        "rationale": rationale,
        "model": MODEL,
        "usage": usage,
    }
    return result
