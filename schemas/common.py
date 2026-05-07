"""
Shared enums and base types used across all agent schemas.

These define canonical values for fields that appear in multiple agents.
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class Seniority(str, Enum):
    """Canonical seniority levels used across all agents and benchmarks."""
    JUNIOR = "junior"   # 0–2 years professional experience
    MID = "mid"         # 3–5 years
    SENIOR = "senior"   # 6–10 years
    STAFF = "staff"     # 11+ years OR explicit Staff/Principal/Director title


class CompanyType(str, Enum):
    """Canonical company categories for Indian tech market JD classification."""
    FAANG = "faang"
    PRODUCT_UNICORN = "product-unicorn"
    FUNDED_STARTUP = "funded-startup"
    ENTERPRISE = "enterprise"
    SERVICE_BASED = "service-based"
    UNKNOWN = "unknown"


class RewriteStyle(str, Enum):
    """Rewrite tone styles available from Agent 4."""
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    TOP_1_PERCENT = "top_1_percent"


class GapSeverity(str, Enum):
    """Severity levels for gap analysis."""
    CRITICAL = "critical"  # dealbreaker
    MAJOR = "major"        # significant impact
    MINOR = "minor"        # nice to fix


class GapType(str, Enum):
    """Types of gaps identified by Agent 3."""
    MISSING_SKILL = "missing_skill"
    WEAK_EXPERIENCE = "weak_experience"
    POOR_WORDING = "poor_wording"
    MISSING_METRICS = "missing_metrics"
    MISSING_SECTION = "missing_section"  # JD requires this section, not in resume


class ResumeSection(str, Enum):
    """Canonical section names in a resume."""
    SUMMARY = "summary"
    OBJECTIVE = "objective"
    EXPERIENCE = "experience"
    SKILLS = "skills"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"
    PUBLICATIONS = "publications"
    AWARDS = "awards"
    DECLARATION = "declaration"
    EXTRACURRICULARS = "extracurriculars"
    OTHER = "other"


class SubLocationChange(BaseModel):
    """
    A single sub-entry change within a multi-entry resume section
    (e.g. one company in Experience, one degree in Education).
    Enables surgical, entry-level targeting instead of monolithic section rewrites.
    """
    sub_id: str = Field(..., description="Slugified identifier e.g. 'flipkart_em', 'iim_mba'")
    sub_label: str = Field(..., description="Human-readable label e.g. 'Flipkart — EM (2021–present)'")
    needs_change: bool = Field(..., description="True only if THIS specific entry has a gap")
    gap_reason: str = Field(default="", description="Why this entry needs change — empty if needs_change=False")
    rewrite_instruction: str = Field(default="", description="One-sentence instruction for rewriter — empty if needs_change=False")
    missing_keywords: List[str] = Field(default_factory=list, description="JD keywords scoped to this entry only")


class ScoreDelta(BaseModel):
    """Tracks ATS/JD match score improvement from before-rewrite to after-rewrite.

    Used by gap_session and Streamlit UI to display concrete improvement metrics.

    Attributes:
        score_before: ATS or JD match score before rewrite (0-100).
        score_after: Score after user accepts/rejects rewrite sections (0-100).
        delta: Difference score_after - score_before. Negative if score declined.
        keywords_added: List of valuable keywords introduced in the rewrite.
        sections_improved: Resume sections that saw meaningful changes.
        remaining_gaps: High-priority gaps not yet addressed.
        manual_suggestions: Improvements user can make manually (e.g., add certifications, projects).
    """

    score_before: int
    score_after: int
    delta: int
    keywords_added: list[str]
    sections_improved: list[str]
    remaining_gaps: list[str]
    manual_suggestions: list[str]

    class Config:
        """Allow serialization from dicts."""
        from_attributes = True


class SubEntry(BaseModel):
    """A single sub-entry within a resume section (one company role, one degree, one cert).

    Represents the LLM's extraction of structured entries from a section like
    experience (per-company), education (per-degree), or certifications (per-cert).
    """
    label: str = Field(..., description="Human-readable label e.g. 'Flipkart — EM (2021–present)'")
    verbatim_text: str = Field(..., description="Exact character-for-character text of this entry from the resume")


class SectionText(BaseModel):
    """One canonical section of a parsed resume with verbatim text and sub-entries."""
    header: str = Field(..., description="Canonical section name e.g. 'experience', 'education', 'summary'")
    full_text: str = Field(..., description="Verbatim full text of the entire section")
    sub_entries: List[SubEntry] = Field(
        default_factory=list,
        description="Per-company/degree/cert entries. Empty for summary, skills, and other monolithic sections."
    )


class ResumeSections(BaseModel):
    """Full structured decomposition of a resume into verbatim sections."""
    sections: List[SectionText] = Field(..., description="All sections found in the resume")
