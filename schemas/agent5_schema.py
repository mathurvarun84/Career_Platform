"""
Pydantic schemas for Agent 5 — Recruiter Simulator.

Input: resume text and/or Agent 1 output
Output: 10 persona verdicts with aggregate metrics for Streamlit Tab 2
"""

from pydantic import BaseModel, Field
from typing import List


class PersonaVerdict(BaseModel):
    """
    Shortlist decision and reasoning from a single recruiter persona.

    each persona returns a structured verdict with strengths, weaknesses, and decision.
    """
    persona: str = Field(..., description="Persona name e.g. 'FAANG Technical Screener'")
    first_impression: str = Field(..., description="First reaction to resume in 1–2 sentences")
    noticed: List[str] = Field(..., description="Positive signals the persona picked up")
    ignored: List[str] = Field(..., description="Resume content this persona ignored or discounted")
    rejection_reason: str = Field(
        ...,
        description="Primary reason for rejection if applicable; empty string if shortlisted"
    )
    shortlist_decision: bool = Field(..., description="True if this persona would shortlist the candidate")
    fit_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="0-100 fit score for THIS persona's specific criteria",
    )
    flip_condition: str = Field(
        ...,
        description=(
            "Single most impactful change that would make this persona shortlist. "
            "Must be specific and actionable. Empty string if already shortlisted."
        ),
    )


class RecruiterSimInput(BaseModel):
    """Input contract for Agent 5."""
    resume_text: str = Field(..., description="Original resume text")
    resume_understanding: dict | None = Field(
        default=None,
        description="Optional Agent 1 output for richer simulation"
    )


class RecruiterSimOutput(BaseModel):
    """
    Aggregate recruiter simulation across all 10 personas.

    shortlist_rate is the primary signal shown in Streamlit Tab 2.
    most_critical_fix drives the top recommendation card.
    """
    personas: List[PersonaVerdict] = Field(..., min_length=10, max_length=10)
    shortlist_rate: float = Field(..., ge=0.0, le=1.0, description="Fraction of personas who would shortlist (0.0–1.0)")
    consensus_strengths: List[str] = Field(..., description="Signals praised by 3+ personas")
    consensus_weaknesses: List[str] = Field(..., description="Issues flagged by 3+ personas")
    most_critical_fix: str = Field(..., description="Single highest-priority improvement across all personas")
    fix_priority: List[dict] = Field(
        default_factory=list,
        description=(
            "Ranked list of fixes ordered by how many personas they unblock. "
            "Each entry: fix (str), persona_count (int), personas (list), "
            "avg_fit_score (float). Pure Python - not from LLM."
        ),
    )
