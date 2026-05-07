# DEPRECATED — merged into ResumeUnderstandingAgent (A1) as of this session.
# Kept for CLI/testing only. Not called by orchestrator.
"""
SectionerAgent — extracts a resume into verbatim sections and sub-entries.

Provider: OpenAI (gpt-5.4-mini)
Max tokens: 3000
"""

from __future__ import annotations

import json
import logging
from typing import Dict

from .base_agent import BaseAgent
from schemas.common import ResumeSections, SectionText


SECTIONER_SYSTEM_PROMPT = """You are a resume parser. Your only job is to extract each section's text verbatim.
Have deep expertise in Indian resume norms and section header variations.You have seen many resumes and you know the patterns of each section.
Do not evaluate, improve, or summarize. Return ONLY valid JSON with sections array.
Each section: header (canonical lowercase), full_text (verbatim), sub_entries (one per
company/degree/cert — empty list for summary and skills).
verbatim_text must be copied character-for-character. No paraphrasing. No extra keys."""

# Canonical section headers the LLM should map to
SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "objective", "profile", "about"],
    "skills": ["skills", "technical skills", "core competencies", "key skills", "competencies"],
    "experience": ["experience", "work experience", "professional experience", "employment history", "employment", "career"],
    "education": ["education", "academic background", "academics", "qualifications"],
    "certifications": ["certifications", "certificates", "licenses", "credentials"],
    "projects": ["projects", "personal projects", "side projects"],
    "awards": ["awards", "achievements", "honors", "honours", "awards and achievements"],
    "publications": ["publications", "research", "papers"],
    "extracurriculars": ["extracurriculars", "activities", "volunteer", "community service"],
}


class SectionerAgent(BaseAgent):
    """
    Extracts a resume into canonical sections with verbatim text and sub-entries.

    Does NOT analyse, evaluate, or improve any content. Pure extraction only.
    Provider: OpenAI gpt-4o-mini. Max tokens: 2000.

    Returns a dict of {canonical_section_name: SectionText} keyed by header.
    """

    def __init__(self):
        super().__init__(model="gpt-5.4-mini", max_tokens=3000, provider="openai")

    def run(self, input_dict: dict) -> Dict[str, SectionText]:
        """
        Entry point for Agent Sectioner.

        Args:
            input_dict: Must contain 'resume_text' (str).

        Returns:
            Dict keyed by canonical section name (e.g. 'experience', 'summary')
            with SectionText values containing verbatim text and sub-entries.
        """
        resume_text = input_dict["resume_text"]

        user_message = self._build_extraction_prompt(resume_text)

        for attempt in range(2):
            try:
                raw = self._call_llm(SECTIONER_SYSTEM_PROMPT, user_message)
                parsed = self._parse_json(raw)
                result = ResumeSections(**parsed)
                return self._build_section_dict(result.sections)
            except Exception as e:
                if attempt == 1:
                    logging.error("SectionerAgent: JSON parse failed after 2 attempts: %s", e)
                    # Degrade gracefully — return empty sections dict
                    return {}
                continue

    def _build_extraction_prompt(self, resume_text: str) -> str:
        """
        Builds the user prompt with full resume text and canonical section mapping.

        Args:
            resume_text: Full cleaned resume text from parser.py.

        Returns:
            Prompt string instructing the LLM to extract verbatim sections.
        """
        aliases_text = json.dumps(SECTION_ALIASES, indent=2)
        return (
            f"Extract the resume below into canonical sections.\n\n"
            f"Canonical section names (map aliases to these):\n{aliases_text}\n\n"
            f"Rules:\n"
            f"1. header: use lowercase canonical name from the list above\n"
            f"2. full_text: copy EVERYTHING under that section header verbatim — character-for-character\n"
            f"3. sub_entries: for experience (one per company), education (one per degree), "
            f"certifications (one per cert), projects (one per project). "
            f"For summary, skills, awards, extracurriculars, publications — use empty list [].\n"
            f"4. label: human-readable e.g. 'Flipkart — Engineering Manager (2021–present)'\n"
            f"5. verbatim_text: exact text of that entry, copied character-for-character\n\n"
            f"Return ONLY JSON with this shape:\n"
            f'{{"sections": [{{"header": "...", "full_text": "...", "sub_entries": [...]}}]}}\n\n'
            f"Resume text:\n{resume_text}"
        )

    def _build_section_dict(self, sections: list) -> Dict[str, SectionText]:
        """
        Converts the LLM's list output into a dict keyed by canonical section name.

        Args:
            sections: List of SectionText models from the LLM response.

        Returns:
            Dict mapping section header (e.g. 'experience') to SectionText.
        """
        return {s.header: s for s in sections}
