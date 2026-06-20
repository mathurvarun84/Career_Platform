"""Company Readiness scoring — deterministic A1+A3 signals, zero LLM calls."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from backend.models.readiness import CompanyReadinessResult, DimensionResult

logger = logging.getLogger(__name__)

TIER_ORDER = ["service", "startup_early", "product_mid", "product_unicorn", "faang"]

DIMENSION_LABELS = {
    "ownership": "Ownership Language",
    "impact_and_scale": "Impact & Scale",
    "problem_solving": "Problem Solving",
    "influence_without_authority": "Influence Without Authority",
    "collaboration": "Collaboration",
    "data_driven": "Data-Driven Decisions",
    "growth_mindset": "Growth Mindset",
    "cross_functional": "Cross-Functional Scope",
    "consumer_intuition": "Consumer Intuition",
}

IC_SENIORITY_LEVELS = {"junior", "mid", "senior", "staff"}
MGMT_SENIORITY_LEVELS = {"em", "senior_em", "director"}

SENIORITY_ORDER = ["junior", "mid", "senior", "staff", "em", "senior_em", "director"]

_DISPLAY_LABELS = {
    "strong": "Signal Found",
    "developing": "Partial Signal",
    "weak": "Signal Not Found",
}

READINESS_DISCLAIMER = (
    "This reflects language patterns found in your resume, not a guarantee of interview "
    "outcome. Use it to identify what to strengthen, not as a verdict on your readiness."
)

CROSS_FUNCTIONAL_TERMS = {
    "stakeholder", "alignment", "design", "product", "ops",
    "cross-functional", "cross-team", "collaborated",
}

DATA_TERMS = {
    "sql", "a/b test", "a/b testing", "experiment", "metric", "analytics",
    "dashboard", "funnel", "cohort", "bigquery", "redshift", "looker",
}

CONSUMER_TERMS = {
    "user research", "nps", "feedback", "usability", "customer interview",
    "user interview", "a/b test", "retention", "churn", "dau", "mau",
}

_COMPANY_VALUES_CACHE: dict | None = None


@dataclass
class _DimScore:
    strength: str
    evidence: str


def load_company_values(company_key: str) -> dict | None:
    """Load one company entry from company_values.json (cached)."""
    global _COMPANY_VALUES_CACHE
    if _COMPANY_VALUES_CACHE is None:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "company_values.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _COMPANY_VALUES_CACHE = json.load(fh)
        except Exception as exc:
            logger.warning("Failed to load company_values.json: %s", exc)
            _COMPANY_VALUES_CACHE = {}
    key = company_key.lower().strip().replace(" ", "")
    entry = (_COMPANY_VALUES_CACHE or {}).get(key)
    return entry if isinstance(entry, dict) else None


def load_company_keys() -> set[str]:
    """Return known company keys (lowercase) that have readiness data."""
    if _COMPANY_VALUES_CACHE is None:
        load_company_values("__probe__")
    return {
        k for k, v in (_COMPANY_VALUES_CACHE or {}).items()
        if isinstance(v, dict) and v.get("display_name")
    }


def _resume_text(resume_und: dict) -> str:
    sections = resume_und.get("resume_sections") or resume_und.get("sections") or {}
    parts: list[str] = []
    for sec in sections.values():
        if isinstance(sec, dict):
            parts.append(sec.get("full_text") or "")
        elif hasattr(sec, "full_text"):
            parts.append(sec.full_text or "")
    return " ".join(parts).lower()


def _has_impact_metrics(resume_und: dict) -> bool:
    if resume_und.get("impact_metrics") is not None:
        return bool(resume_und.get("impact_metrics"))
    return bool(resume_und.get("has_metrics"))


def _score_ownership(resume_und: dict) -> _DimScore:
    health = resume_und.get("resume_health") or {}
    signals = health.get("expected_signals") or []
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        label = (sig.get("signal") or "").lower()
        if "ownership" not in label:
            continue
        present = sig.get("present", False)
        strength = (sig.get("strength") or "").lower()
        if present and strength == "strong":
            return _DimScore("strong", "Ownership signals found in resume_health.")
        if present:
            return _DimScore("developing", "Ownership signal present but not strong.")
    return _DimScore("weak", "No ownership signal found in resume_health expected_signals.")


def _score_impact_and_scale(resume_und: dict, ats_impact_subscore: int | None) -> _DimScore:
    has_metrics = _has_impact_metrics(resume_und)
    subscore_ok = (ats_impact_subscore or 0) >= 18
    if has_metrics and subscore_ok:
        return _DimScore("strong", "Impact metrics present and ATS sub-score ≥ 18.")
    if has_metrics:
        return _DimScore("developing", "Impact metrics present but ATS sub-score < 18.")
    return _DimScore("weak", "No quantified impact metrics found.")


def _gap_text(item) -> str:
    if isinstance(item, str):
        return item.lower()
    if isinstance(item, dict):
        return (
            (item.get("gap_reason") or "")
            + " "
            + (item.get("rewrite_instruction") or "")
        ).lower()
    return ""


def _score_problem_solving(gap_result: dict) -> _DimScore:
    fixes = gap_result.get("priority_fixes") or []
    depth_gaps = sum(1 for f in fixes if "technical depth" in _gap_text(f))
    if depth_gaps == 0:
        return _DimScore("strong", "No technical depth gaps flagged.")
    if depth_gaps == 1:
        return _DimScore("developing", "One technical depth gap flagged.")
    return _DimScore("weak", f"{depth_gaps} technical depth gaps flagged.")


def _score_influence(resume_und: dict) -> _DimScore:
    text = _resume_text(resume_und)
    sentences = [s.strip() for s in re.split(r"[.\n•–-]", text) if s.strip()]
    rich_count = sum(
        1 for s in sentences
        if sum(1 for t in CROSS_FUNCTIONAL_TERMS if t in s) >= 2
    )
    if rich_count >= 3:
        return _DimScore("strong", f"{rich_count} cross-functional bullets found.")
    if rich_count >= 1:
        return _DimScore("developing", f"{rich_count} cross-functional bullet(s) found.")
    return _DimScore("weak", "No cross-functional collaboration signals found.")


def _score_collaboration(resume_und: dict) -> _DimScore:
    sections_present = resume_und.get("sections_present") or []
    normalized = [str(s).lower() for s in sections_present]
    if "projects" in normalized:
        return _DimScore("strong", "Projects section found.")
    text = _resume_text(resume_und)
    if any(t in text for t in ("cross-team", "cross-functional", "collaborated with")):
        return _DimScore("developing", "Cross-team language present but no projects section.")
    return _DimScore("weak", "No collaboration signals found.")


def _score_data_driven(resume_und: dict) -> _DimScore:
    text = _resume_text(resume_und)
    found = {t for t in DATA_TERMS if t in text}
    if len(found) >= 3:
        return _DimScore("strong", f"Data signals found: {', '.join(sorted(found)[:3])}.")
    if len(found) >= 1:
        return _DimScore("developing", f"Partial data signals: {', '.join(sorted(found))}.")
    return _DimScore("weak", "No data-driven signals found.")


def _score_growth_mindset(resume_und: dict) -> _DimScore:
    sections_present = resume_und.get("sections_present") or []
    normalized = [str(s).lower() for s in sections_present]
    if "certifications" in normalized:
        return _DimScore("strong", "Certifications section present.")
    text = _resume_text(resume_und)
    growth_terms = {"learning", "scaled", "new domain", "reskill", "upskill", "self-taught", "course"}
    if any(t in text for t in growth_terms):
        return _DimScore("developing", "Growth language present but no certifications section.")
    return _DimScore("weak", "No growth mindset signals found.")


def _score_cross_functional(resume_und: dict) -> _DimScore:
    return _score_influence(resume_und)


def _score_consumer_intuition(resume_und: dict) -> _DimScore:
    text = _resume_text(resume_und)
    found = {t for t in CONSUMER_TERMS if t in text}
    if len(found) >= 2:
        return _DimScore("strong", f"Consumer signals: {', '.join(sorted(found)[:2])}.")
    if len(found) == 1:
        return _DimScore("developing", f"Partial consumer signal: {', '.join(found)}.")
    return _DimScore("weak", "No consumer intuition signals found.")


def _score_single_dimension(
    dim_id: str,
    resume_und: dict,
    gap_result: dict,
    ats_impact_subscore: int | None = None,
) -> _DimScore:
    dispatch = {
        "ownership": lambda: _score_ownership(resume_und),
        "impact_and_scale": lambda: _score_impact_and_scale(resume_und, ats_impact_subscore),
        "problem_solving": lambda: _score_problem_solving(gap_result),
        "influence_without_authority": lambda: _score_influence(resume_und),
        "collaboration": lambda: _score_collaboration(resume_und),
        "data_driven": lambda: _score_data_driven(resume_und),
        "growth_mindset": lambda: _score_growth_mindset(resume_und),
        "cross_functional": lambda: _score_cross_functional(resume_und),
        "consumer_intuition": lambda: _score_consumer_intuition(resume_und),
    }
    fn = dispatch.get(dim_id)
    if fn is None:
        return _DimScore("weak", f"Unknown dimension: {dim_id}")
    return fn()


def _compute_seniority_component(resume_seniority: str, jd_intel: dict) -> int:
    """Soft seniority modifier — Role Fit Gate handles hard gates."""
    _ = jd_intel
    resume_idx = SENIORITY_ORDER.index(resume_seniority) if resume_seniority in SENIORITY_ORDER else 2
    if resume_idx >= 2:
        return 100
    if resume_idx == 1:
        return 75
    return 50


def _readiness_label(score: int) -> str:
    if score >= 80:
        return "Highly Ready"
    if score >= 60:
        return "Ready"
    if score >= 40:
        return "Partially Ready"
    return "Not Ready"


def compute_readiness_score(
    run_id: str,
    resume_und: dict,
    gap_result: dict,
    ats_result: dict,
    company_key: str,
    seniority: str,
) -> CompanyReadinessResult | None:
    """
    Zero LLM calls. Computes readiness from existing A1 + A3 + ATS output.
    Returns None if company_key is not in company_values.json.
    """
    _ = run_id
    company = load_company_values(company_key)
    if not company:
        return None

    ats_score = int(ats_result.get("score") or 0)
    jd_match = gap_result.get("jd_match_score_before")
    if jd_match is None:
        jd_match = gap_result.get("jd_match_score")
    ats_impact_subscore = (ats_result.get("breakdown") or {}).get("impact_metrics")

    ats_component = int(min(ats_score / 80, 1.0) * 100)
    jd_component = int(jd_match) if jd_match is not None else None

    seniority_str = str(seniority or "mid").lower()
    seniority_component = _compute_seniority_component(seniority_str, gap_result)

    focus_dims = (
        company.get("em_focus_dimensions", [])
        if seniority_str in MGMT_SENIORITY_LEVELS
        else company.get("ic_focus_dimensions", [])
    )
    expectations = company.get("readiness_expectations", {})
    fix_hints = company.get("fix_hints", {})

    dimensions: list[DimensionResult] = []
    for dim_id in focus_dims:
        result = _score_single_dimension(dim_id, resume_und, gap_result, ats_impact_subscore)
        dimensions.append(DimensionResult(
            dimension_id=dim_id,
            label=DIMENSION_LABELS.get(dim_id, dim_id),
            company_expectation=expectations.get(dim_id, ""),
            resume_evidence=result.evidence,
            signal_strength=result.strength,
            passes=result.strength == "strong",
            fix_hint=fix_hints.get(dim_id) if result.strength != "strong" else None,
            display_label=_DISPLAY_LABELS.get(result.strength, "Signal Not Found"),
        ))

    dimensions_passing = sum(1 for d in dimensions if d.passes)
    dimensions_total = len(dimensions)
    company_signal_component = (
        int((dimensions_passing / dimensions_total) * 100)
        if dimensions_total > 0 else 0
    )

    jd_weight_score = (jd_component or 0) * 0.30
    readiness_score = int(
        ats_component * 0.20
        + jd_weight_score
        + seniority_component * 0.20
        + company_signal_component * 0.30
    )
    readiness_score = max(0, min(100, readiness_score))
    readiness_label = _readiness_label(readiness_score)

    from engine.career_positioning import get_positioning_statement

    positioning = get_positioning_statement(
        seniority=seniority_str,
        ats_score=ats_score,
        jd_match_score=int(jd_match or 0),
    )

    failing = [d for d in dimensions if not d.passes and d.fix_hint]
    top_fix = (
        sorted(failing, key=lambda d: ["strong", "developing", "weak"].index(d.signal_strength))[-1]
        if failing else None
    )

    return CompanyReadinessResult(
        company_key=company_key.lower().strip().replace(" ", ""),
        company_display_name=company.get("display_name", company_key),
        readiness_score=readiness_score,
        readiness_label=readiness_label,
        readiness_pct_string=f"{readiness_score}% Ready",
        dimensions=dimensions,
        dimensions_passing=dimensions_passing,
        dimensions_total=dimensions_total,
        ats_component=ats_component,
        jd_component=jd_component,
        seniority_component=seniority_component,
        company_signal_component=company_signal_component,
        current_ctc_min=positioning.get("current_ctc_min"),
        current_ctc_max=positioning.get("current_ctc_max"),
        target_ctc_min=positioning.get("potential_ctc_min"),
        target_ctc_max=positioning.get("potential_ctc_max"),
        ctc_delta_min=positioning.get("ctc_delta_min"),
        ctc_delta_max=positioning.get("ctc_delta_max"),
        top_fix=top_fix,
        disclaimer=READINESS_DISCLAIMER,
    )
