from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FetchJDRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    # Optional: if provided, skip Serper and fetch this URL directly.
    direct_url: Optional[str] = Field(default=None)
    # Optional taxonomy fields from the role dropdown — when present, enable
    # company-specific internal title aliasing in the search and scoring steps.
    # Absent on free-text "Other" entries; absent callers get pre-alias behavior.
    role_family: Optional[str] = Field(default=None, max_length=50)
    seniority_rank: Optional[str] = Field(default=None, max_length=50)

    @field_validator("company", "role")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class AlternativeRole(BaseModel):
    title: str
    level: str
    url: Optional[str] = None


class FetchJDResponse(BaseModel):
    status: Literal["found", "not_found", "multiple", "error"]
    jd_text: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None
    is_cached: bool = False
    company: str
    role: str
    alternatives: Optional[list[AlternativeRole]] = None
    error_message: Optional[str] = None
