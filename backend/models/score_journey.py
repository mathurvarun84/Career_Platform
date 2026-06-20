"""Pydantic models for Score Journey — cross-session score timeline."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SessionSnapshot(BaseModel):
    run_id: str
    user_id: str
    created_at: str
    ats_score: int
    jd_match_score: Optional[int] = None
    composite_score: int
    percentile_value: Optional[int] = None
    percentile_label: Optional[str] = None
    current_tier: Optional[str] = None
    current_tier_label: Optional[str] = None
    current_ctc_min: Optional[int] = None
    current_ctc_max: Optional[int] = None
    seniority: Optional[str] = None
    role_family: Optional[str] = None
    jd_company: Optional[str] = None
    jd_role_title: Optional[str] = None
    ats_keyword_match: Optional[int] = None
    ats_formatting: Optional[int] = None
    ats_readability: Optional[int] = None
    ats_impact_metrics: Optional[int] = None


class MilestoneEvent(BaseModel):
    run_id: str
    type: str
    label: str
    from_value: str
    to_value: str


class ScoreJourneyResult(BaseModel):
    sessions: list[SessionSnapshot]
    total_sessions: int
    first_score: int
    latest_score: int
    score_delta: int
    first_tier: Optional[str] = None
    latest_tier: Optional[str] = None
    tier_changed: bool
    first_ctc_min: Optional[int] = None
    latest_ctc_min: Optional[int] = None
    ctc_delta_min: Optional[int] = None
    milestones: list[MilestoneEvent]
