"""
Pydantic schemas for Agent 2 — JD Intelligence.

Input: raw job description text pasted by user
Output: structured JD intelligence for downstream agents
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from .common import Seniority, CompanyType


class HiddenSignal(BaseModel):
    """A single implicit signal extracted from JD language."""
    signal: str = Field(..., description="The phrase or pattern found in JD")
    implication: str = Field(..., description="What it means for the candidate e.g. 'no PM, high ownership'")


class JDIntelligenceInput(BaseModel):
    """Input contract for Agent 2."""
    jd_text: str = Field(..., description="Raw job description text pasted by user")


class JDIntelligenceOutput(BaseModel):
    """
    Structured representation of a parsed job description.

    semantic_skill_map direction: JD term → list of resume equivalents.
    hidden_signals captures non-obvious hiring intent beyond stated requirements.
    """
    role_title: str = Field(..., description="Exact title as written in JD")
    must_have_skills: List[str] = Field(..., description="Dealbreaker requirements if missing")
    nice_to_have_skills: List[str] = Field(..., description="Preferred but not blocking skills")
    hidden_signals: List[HiddenSignal] = Field(..., description="Implicit signals in JD language")
    semantic_skill_map: Dict[str, List[str]] = Field(
        ...,
        description="Maps JD skill/phrase → resume terms candidate might use. E.g. {'event streaming': ['Kafka', 'Pulsar']}"
    )
    seniority_expected: Seniority = Field(..., description="Inferred from responsibilities, not just title")
    company_type: CompanyType = Field(..., description="Canonical company category")
