"""
Pydantic schemas for Agent 1 — Resume Understanding.

Input: raw resume text (pre-cleaned by parser.py)
Output: structured resume data for downstream agents
"""

from pydantic import BaseModel, Field
from typing import List, Optional

from .common import Seniority, ResumeSection


class ResumeUnderstandingInput(BaseModel):
    """Input contract for Agent 1. resume_text must be pre-cleaned by parser.py."""
    resume_text: str = Field(..., description="Raw text extracted from resume by parser.py")
    user_id: Optional[str] = Field(None, description="Unique identifier for session memory tracking")


class SenioritySignal(BaseModel):
    """A single seniority-level signal and whether it is present in the resume."""
    signal: str = Field(..., description="What is expected at this seniority level")
    present: bool = Field(..., description="True if this signal is found in the resume")
    location: str = Field(..., description="Where found, or where it should be added")
    inline_fix: str = Field(..., description="One-line fix if present=False; empty if present=True")


class ResumeUnderstandingOutput(BaseModel):
    """
    Structured representation of a parsed resume.

    All fields are required — Agent 1 must populate every key.
    Downstream agents (Gap Analyzer, Rewriter) depend on this schema.
    """
    experience_years: int = Field(..., ge=0, description="Total professional experience excluding internships")
    seniority: Seniority = Field(..., description="Inferred from both YoE AND title")
    tech_stack: List[str] = Field(..., description="Languages, frameworks, databases, cloud platforms only")
    domains: List[str] = Field(..., description="Business domains e.g. fintech, supply chain, e-commerce")
    has_metrics: bool = Field(..., description="True if resume has at least one quantified impact")
    has_summary: bool = Field(..., description="True if resume has a summary or objective section at top")
    sections_present: List[ResumeSection] = Field(..., description="Canonical section names found in resume")
    strengths: List[str] = Field(..., description="what the candidate has that stands out (metrics, scale, leadership, breadth)")
    weaknesses: List[str] = Field(..., description="what is missing or weak (no summary, weak bullets, no metrics, thin keyword density)")
    improvement_areas: List[str] = Field(..., description="top 3 actionable fixes even without a JD")
    keyword_density_verdict: str = Field(..., description="\"low\"|\"medium\"|\"high\" keyword density verdict")
    formatting_signals: List[str] = Field(..., description="formatting issues inferred from text (e.g. \"no summary section\", \"bullets missing\")")


class ResumeHealthOutput(BaseModel):
    """Seniority-aware resume health — does not require a JD."""
    seniority_detected: str = Field(..., description="junior/mid/senior/staff")
    expected_signals: List[SenioritySignal] = Field(
        ..., min_length=5, max_length=7,
        description="5-7 signals expected at this seniority level and whether they are present",
    )
    strengths: List[str] = Field(
        ..., max_length=5,
        description="Max 5 strengths — must cite specific metric/company/role",
    )
    weaknesses: List[str] = Field(
        ..., max_length=5,
        description="Max 5 weaknesses — format: 'location + gap → inline fix'",
    )
    overall_health: str = Field(..., description="One sentence verdict on resume quality")
