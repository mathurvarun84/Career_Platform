"""
Pydantic schemas for Agent 3 - Gap Analyzer.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class SubLocationChange(BaseModel):
    """
    A single sub-entry within a multi-entry resume section (e.g. one company in Experience,
    one degree in Education). Enables surgical, entry-level targeting instead of monolithic
    section rewrites.

    original_text is backfilled in Python from sectioner data — the LLM does NOT provide it.
    """
    sub_id: str = Field(..., description="Slugified identifier e.g. 'flipkart_em', 'iim_mba'")
    sub_label: str = Field(..., description="Human-readable label e.g. 'Flipkart — EM (2021–present)'")
    original_text: str = Field(
        default="",
        description="Backfilled in Python from sectioner SubEntry — not expected from LLM"
    )
    needs_change: bool = Field(..., description="True only if THIS specific entry has a gap")
    gap_reason: str = Field(default="", description="Why this entry needs change — empty if needs_change=False")
    rewrite_instruction: str = Field(default="", description="Non-empty only when needs_change=True")
    missing_keywords: List[str] = Field(default_factory=list, description="JD keywords scoped to this entry only")


class SectionGap(BaseModel):
    section: str = Field(..., description="Canonical section name")
    needs_change: bool = Field(..., description="True if the section should be rewritten")
    gap_reason: str = Field(..., description="One sentence reason for the gap")
    missing_keywords: List[str] = Field(default_factory=list)
    rewrite_instruction: str = Field(default="")
    original_content: str = Field(
        default="",
        description="Backfilled in Python from sectioner data — not expected from LLM output"
    )
    present_in_resume: bool = Field(
        default=True,
        description="True if section exists — set to True when sectioner provides it"
    )
    sub_changes: List[SubLocationChange] = Field(
        default_factory=list,
        description="Per-entry decomposition for multi-entry sections (experience, education, etc.)"
    )


class GapAnalyzerInput(BaseModel):
    jd_text: Optional[str] = Field(default=None)
    jd_analysis: Dict = Field(default_factory=dict)
    jd_intelligence: Dict = Field(default_factory=dict)
    resume_analysis: Dict = Field(default_factory=dict)
    resume_understanding: Dict = Field(default_factory=dict)
    resume_text: str = Field(default="")

    @model_validator(mode="after")
    def normalize_aliases(self) -> "GapAnalyzerInput":
        if not self.jd_analysis and self.jd_intelligence:
            self.jd_analysis = self.jd_intelligence
        if not self.jd_intelligence and self.jd_analysis:
            self.jd_intelligence = self.jd_analysis
        if not self.resume_analysis and self.resume_understanding:
            self.resume_analysis = self.resume_understanding
        if not self.resume_understanding and self.resume_analysis:
            self.resume_understanding = self.resume_analysis
        return self


class ChangeLocation(BaseModel):
    section: str = Field(..., description="Exact section name (summary/skills/experience/education/certifications)")
    sub_location: str = Field(
        ...,
        description="Pinpoint location — role+company+date+bullet number, sentence number, or skills sub-block"
    )


class ActionableChange(BaseModel):
    change_id: int = Field(..., description="Sequential ID for this change")
    location: ChangeLocation = Field(..., description="Where in the resume this change applies")
    change_type: str = Field(
        ...,
        description="One of: rewrite_bullet, add_keyword, rewrite_section, add_section, remove_content, strengthen_metric"
    )
    priority: str = Field(..., description="One of: critical, high, medium")
    why: str = Field(..., description="One sentence connecting change to specific JD requirement")
    original_text: str = Field(
        ...,
        description="VERBATIM text from resume at that location; empty string only for new content"
    )
    suggested_text: str = Field(
        ...,
        description="COMPLETE ready-to-paste text — never a hint or instruction"
    )
    keywords_added: List[str] = Field(default_factory=list, description="JD keywords this change introduces")


class OverallAssessment(BaseModel):
    strengths: List[str] = Field(
        ...,
        description="Max 5 items — cite specific resume content, metrics, company names"
    )
    weaknesses: List[str] = Field(
        ...,
        description="Max 5 items — name exact section and gap, never generic"
    )
    jd_fit_summary: str = Field(..., description="2 sentences on overall fit for THIS specific JD")


class DetailedEvalOutput(BaseModel):
    overall: OverallAssessment = Field(..., description="Overall assessment summary")
    changes: List[ActionableChange] = Field(
        ...,
        description="Ordered: critical → high → medium, max 12 changes"
    )
    jd_match_score_before: int = Field(..., ge=0, le=100, description="0-100 score before changes")
    estimated_score_after: int = Field(..., ge=0, le=100, description="0-100 estimated score if all critical+high changes applied")


class GapAnalyzerOutput(BaseModel):
    jd_match_score_before: int = Field(..., ge=0, le=100)
    section_gaps: List[SectionGap] = Field(...)
    missing_keywords: List[str] = Field(default_factory=list)
    priority_fixes: List[str] = Field(default_factory=list)
    sections_changed: List[str] = Field(default_factory=list)
    sections_unchanged: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_lists(self) -> "GapAnalyzerOutput":
        if not self.sections_changed:
            self.sections_changed = [gap.section for gap in self.section_gaps if gap.needs_change]
        if not self.sections_unchanged:
            self.sections_unchanged = [gap.section for gap in self.section_gaps if not gap.needs_change]
        if not self.missing_keywords:
            deduped: List[str] = []
            seen = set()
            for gap in self.section_gaps:
                for keyword in gap.missing_keywords:
                    lowered = keyword.lower()
                    if lowered not in seen:
                        seen.add(lowered)
                        deduped.append(keyword)
            self.missing_keywords = deduped
        if not self.priority_fixes:
            self.priority_fixes = [
                gap.rewrite_instruction
                for gap in self.section_gaps
                if gap.needs_change and gap.rewrite_instruction
            ][:3]
        return self
