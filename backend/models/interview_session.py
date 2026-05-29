"""Pydantic model for interview_sessions Supabase rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InterviewSessionRecord(BaseModel):
    """Shape of an interview_sessions table row."""

    session_id: str
    user_id: str
    company: str
    seniority: str
    question_mode: str
    questions: list[dict[str, Any]] = Field(default_factory=list)
    answers: list[dict[str, Any]] = Field(default_factory=list)
    feedback: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    model_answers: dict[str, Any] | None = None
    created_at: datetime | str
    completed_at: datetime | str | None = None
