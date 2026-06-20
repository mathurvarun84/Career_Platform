"""Pydantic models for Company Readiness — deterministic A1+A3 signal scoring."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DimensionResult(BaseModel):
    dimension_id: str
    label: str
    company_expectation: str
    resume_evidence: str
    signal_strength: str  # "strong" | "developing" | "weak"
    passes: bool
    fix_hint: Optional[str] = None
    display_label: str


class CompanyReadinessResult(BaseModel):
    company_key: str
    company_display_name: str
    readiness_score: int
    readiness_label: str
    readiness_pct_string: str
    dimensions: list[DimensionResult]
    dimensions_passing: int
    dimensions_total: int
    ats_component: int
    jd_component: Optional[int]
    seniority_component: int
    company_signal_component: int
    current_ctc_min: Optional[int] = None
    current_ctc_max: Optional[int] = None
    target_ctc_min: Optional[int] = None
    target_ctc_max: Optional[int] = None
    ctc_delta_min: Optional[int] = None
    ctc_delta_max: Optional[int] = None
    top_fix: Optional[DimensionResult] = None
    disclaimer: str
