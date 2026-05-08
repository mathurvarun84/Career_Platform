"""
Pydantic schemas for Agent 4 — Rewriter.

Input: original resume text, gap analysis from Agent 3, JD intelligence from Agent 2, optional style fingerprint
Output: 3-style rewritten resume sections for gap_session and Streamlit UI
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from .common import RewriteStyle


class ProjectRewrite(BaseModel):
    """Structured rewrite of a single project entry."""
    name: str = Field(..., description="Original project name — never invented")
    tech_stack: List[str] = Field(..., description="Technologies used in this project")
    rewritten_description: str = Field(..., description="One to two sentence rewrite")


class ExperienceRewrite(BaseModel):
    """Rewritten bullets for a single role."""
    company: str = Field(..., description="Original company name — never invented")
    role: str = Field(..., description="Original job title — never modified")
    rewritten_bullets: List[str] = Field(
        ...,
        description="Each bullet: action verb + impact + scale, 20-35 words, minimum 5 bullets per role"
    )


class SkillsMap(BaseModel):
    """Skills grouped by category for consistent ATS keyword extraction."""
    Languages: List[str] = Field(default_factory=list)
    Frameworks: List[str] = Field(default_factory=list)
    Databases: List[str] = Field(default_factory=list)
    Cloud: List[str] = Field(default_factory=list)
    Tools: List[str] = Field(default_factory=list)


class StyleOutput(BaseModel):
    """Complete resume rewrite for one style."""
    summary: str = Field(..., description="4-6 sentences, minimum 80 words professional summary")
    skills: SkillsMap
    experience: List[ExperienceRewrite]
    projects: List[ProjectRewrite]


class RewriterInput(BaseModel):
    """Input contract for Agent 4."""
    resume_text: str = Field(..., description="Original resume text")
    gap_analysis: Dict[str, Any] = Field(..., description="GapAnalyzerOutput dict from Agent 3")
    jd_intelligence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JDIntelligenceOutput dict from Agent 2. None in resume-only mode."
    )
    style_fingerprint: str | None = Field(
        default=None,
        description="Optional user style preferences (max 200-token fingerprint from memory)"
    )


class RewriterOutput(BaseModel):
    """
    All three rewrite styles for the candidate's resume sections.

    gap_session.py and Streamlit Tab 3 render these side-by-side for user selection.
    All three styles must be present — Agent 4 failure is non-fatal per orchestrator rules.
    """
    rewrites: Dict[str, dict] = Field(
        ...,
        description="Keys are section names. Values are {balanced, aggressive, top_1_percent} dicts."
    )
    styles: Dict[str, Any] = Field(
        default_factory=dict,
        description="Legacy format — keys: balanced/aggressive/top_1_percent, values are nested dicts/lists"
    )
