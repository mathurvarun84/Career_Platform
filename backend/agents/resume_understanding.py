"""
ResumeUnderstandingAgent - Agent 1 of the Resume Intelligence Platform.

Analyzes a resume text and extracts structured information including:
- Years of experience
- Seniority level (junior/mid/senior/staff)
- Tech stack
- Professional domains
- Presence of metrics (quantified achievements)
- Presence of a summary section
- List of sections present in the resume
- Seniority-aware resume health signals

Uses OpenAI's gpt-4o-mini model with JSON output enforcement.
Validates input and output against Pydantic schemas defined in schemas/agent1_schema.py.
"""

import json
from typing import Dict, List, Optional

from .base_agent import BaseAgent
from backend.schemas.common import Seniority, ResumeSection
from backend.few_shot_prompts import (
    VALID_ROLE_FAMILIES,
    build_few_shot_block,
    detect_role_family,
)
from backend.schemas.agent1_schema import (
    ResumeUnderstandingInput,
    ResumeUnderstandingOutput,
    ResumeHealthOutput,
    SenioritySignal,
)


class ResumeUnderstandingAgent(BaseAgent):
    """
    Agent 1: Resume Parser.

    Extracts structured data from raw resume text for downstream processing.
    Validates input against ResumeUnderstandingInput, calls LLM with
    structured system prompt, parses JSON response, validates output
    against ResumeUnderstandingOutput, and returns model_dump() with
    an additional 'resume_health' key for the Evaluate tab.

    Model: gpt-4o-mini
    Max tokens: 7000
    Provider: OpenAI
    """

    def __init__(self):
        super().__init__(model="gpt-4o-mini", max_tokens=7000, provider="openai")

    def run(self, input_dict: dict) -> dict:
        """
        Extract structured data from a resume, including seniority health signals.

        Validates input against ResumeUnderstandingInput, calls LLM with
        structured system prompt, parses JSON response, validates output
        against ResumeUnderstandingOutput and ResumeHealthOutput separately,
        and returns a combined dict with a 'resume_health' key.

        Args:
            input_dict: Must contain 'resume_text' (str). 'user_id' is optional.

        Returns:
            Validated ResumeUnderstandingOutput serialized as dict,
            with an extra 'resume_health' key containing ResumeHealthOutput.

        Raises:
            ValueError: If LLM response fails JSON parsing after 1 retry.
            ValidationError: If input_dict is missing required fields.
        """
        # Validate input — raises pydantic.ValidationError on bad input
        inp = ResumeUnderstandingInput(**input_dict)

        resume_text = inp.resume_text
        job_title = str(input_dict.get("job_title") or input_dict.get("role_title") or "")
        detected_role = detect_role_family(resume_text, job_title)
        # Cap very large resumes to leave room for the system prompt and JSON response.
        max_chars = 500000
        if len(resume_text) > max_chars:
            resume_text = resume_text[:max_chars] + "...[truncated]"

        # System prompt defines the expected JSON schema explicitly
        system_prompt = (
            "You are a resume parser and health evaluator for Indian professional resumes. "
            "You receive raw resume text and must extract structured information and seniority-specific health signals. "
            "You have deep expertise in Indian resume norms and seniority signals across junior/mid/senior/staff levels."
            " Extract structured data and return ONLY valid JSON with these exact keys:\n\n"
            "- experience_years (int): total professional experience in years, excluding internships\n"
            "- seniority (string): infer from BOTH title AND years — "
            "  'junior' (0-2 yrs), 'mid' (3-5 yrs), 'senior' (6-10 yrs), 'staff' (11+ yrs or explicit Staff/Principal/Director title)\n"
            "- tech_stack (list of strings): programming languages, frameworks, databases, and cloud platforms ONLY — "
            "  exclude soft skills, methodologies (Agile/Scrum), and generic tools (MS Office, Jira, Excel, PowerPoint). "
            "  CRITICAL: only include technologies EXPLICITLY named in the resume text. "
            "  Never infer or assume tools based on the candidate's role or industry. "
            "  An HR professional's resume that does not mention Tableau does NOT have Tableau in tech_stack.\n"
            "- domains (list of strings): business domains only, e.g. 'fintech', 'e-commerce', 'supply chain', 'healthtech'\n"
            "- has_metrics (bool): true only if resume contains at least one quantified impact (numbers, %, ₹, latency, scale)\n"
            "- has_summary (bool): true if resume has a professional summary or objective section at the top\n"
            "- sections_present (list of strings): normalized section names found — "
            "  use canonical names: 'experience', 'education', 'skills', 'projects', 'certifications', "
            "  'publications', 'awards', 'summary', 'objective', 'declaration', 'extracurriculars'\n"
            "- strengths (list[str], max 5): what the candidate has that stands out. "
            "  Cite SPECIFIC evidence: metric, company name, role. "
            '  BAD: "strong leadership". '
            '  GOOD: "Leads 32 engineers across 5 teams at Flipkart — org scale directly visible, '
            '  strong signal for Director-level roles"\n'
            "- weaknesses (list[str], max 8): what is missing or weak. "
            "  FORMAT each weakness as: 'location + what is missing → one-line fix suggestion'. "
            '  BAD: "weak bullets in experience". '
            '  GOOD: "Flipkart EM bullets 3-5 lack quantified latency/scale signals expected at '
            "  Staff level → add system scale (QPS, users, SLA) and business outcome (₹ impact)\"\n"
            "- improvement_areas (list[str]): top 5 actionable fixes even without a JD\n"
            "- keyword_density_verdict (str: \"low\"|\"medium\"|\"high\")\n"
            "- formatting_signals (list[str]): formatting issues inferred from text (e.g. \"no summary section\", \"bullets missing\")\n"
            "- role_family (string): exactly one of "
            "ENGINEERING, PRODUCT, MARKETING, DATA_ANALYST, HR, FINANCE, DESIGN — "
            "infer from job titles and domain vocabulary in the resume\n\n"
            # Seniority health signals
            "- expected_signals (list of objects, 5-7 items): seniority-aware signals for this candidate's level. "
            "  Each signal has: { signal (str), present (bool), location (str), inline_fix (str) }.\n"
            '  Use these seniority-specific expectations:\n'
            "  junior (0-2yr): action verbs in bullets, project outcomes visible, "
            "tech stack clearly listed, learning agility, CS fundamentals\n"
            "  mid (3-5yr): quantified impact with numbers/percentages, "
            "ownership language ('led', 'designed', 'owned'), "
            "specific deliverables shipped, cross-functional collaboration\n"
            "  senior (6-10yr): scale metrics (users/QPS/latency/revenue), "
            "cross-team influence and mentorship, architectural decisions "
            "with tradeoffs, technical strategy involvement\n"
            "  staff (11+yr): org-level scale (team size, budget, hiring), "
            "business outcomes (₹/$/% revenue impact), multi-team delivery leadership, "
            "executive communication signals, hiring/building team capability\n"
            '  inline_fix: non-empty if present=False (what to add where), empty if present=True\n\n'
            "- overall_health (str): one sentence verdict on overall resume quality as a document\n\n"
            "- sections (object): section index for downstream agents. Keys: "
            "  summary | skills | experience | education | certifications | awards | projects\n"
            "  Each key maps to: {full_text: \"\", sub_entries: [{label: string, verbatim_text: string}]}\n"
            "  full_text: ALWAYS empty string \"\" — the parser populates this separately; do not repeat text here.\n"
            "  sub_entries rules:\n"
            "    experience — one entry per employer block (EVERY employer, no merging, no skipping).\n"
            "      Count date-range lines (e.g. 'Jan 2020 – Present') to determine how many.\n"
            "      sub_entries.length MUST equal that count. Missing even one entry is a critical failure.\n"
            "      label: first line of the block (role | company — location).\n"
            "      verbatim_text: COMPLETE block text including all bullets. "
            "        Copy every character. Never truncate, abbreviate, or use ellipsis. "
            "        If the entry has 6 bullets, all 6 must appear in full.\n"
            "    education — one entry per degree. label: degree | institution. verbatim_text: full block.\n"
            "    certifications — one per cert. label: cert name. verbatim_text: full line.\n"
            "    summary/skills/awards — sub_entries: [] (no sub-entries for these sections).\n"
            "  Only include sections that exist. Omit missing section keys entirely.\n"
            "No extra keys. No markdown fences. No explanations."
        )
        system_prompt += build_few_shot_block(detected_role, num_examples=2)

        # Call LLM and parse JSON response
        raw_response = self._call_llm(system_prompt, resume_text)
        parsed_output = self._parse_json(raw_response)

        llm_role = str(parsed_output.get("role_family") or "").upper()
        if llm_role not in VALID_ROLE_FAMILIES:
            parsed_output["role_family"] = detected_role
        else:
            parsed_output["role_family"] = llm_role
        
        # Validate and structure the data using pydantic model
        # Pydantic v2 will coerce strings to enums (e.g., "senior" → Seniority.SENIOR)
        output = ResumeUnderstandingOutput(**parsed_output)

        # Build ResumeHealthOutput from the same parsed response
        seniority_str = parsed_output.get("seniority", "")
        seniority_value = seniority_str.value if hasattr(seniority_str, 'value') else str(seniority_str)

        # Parse SenioritySignal objects from expected_signals
        raw_signals = parsed_output.get("expected_signals", [])
        signals = []
        for sig in raw_signals:
            if isinstance(sig, dict):
                signals.append(SenioritySignal(**sig))
            elif isinstance(sig, SenioritySignal):
                signals.append(sig)
        signals = signals[:7]

        health_output = ResumeHealthOutput(
            seniority_detected=seniority_value,
            expected_signals=signals,
            strengths=self._limit_strings(parsed_output.get("strengths", output.strengths), 5),
            weaknesses=self._limit_strings(parsed_output.get("weaknesses", output.weaknesses), 5),
            overall_health=parsed_output.get("overall_health", ""),
        )

        from backend.schemas.common import SectionText, SubEntry
        raw_sections = parsed_output.get("sections", {})
        resume_sections: dict = {}
        for sec_name, sec_data in raw_sections.items():
            if isinstance(sec_data, dict):
                sub_entries = [
                    SubEntry(
                        label=e.get("label", ""),
                        verbatim_text=e.get("verbatim_text", "")
                    )
                    for e in sec_data.get("sub_entries", [])
                    if isinstance(e, dict)
                ]
                resume_sections[sec_name] = SectionText(
                    header=sec_name,
                    full_text=sec_data.get("full_text", ""),
                    sub_entries=sub_entries,
                ).model_dump()

        result = {
            **output.model_dump(),
            "resume_health": health_output.model_dump(),
            "resume_sections": resume_sections,
        }
        from validator.resume_understanding_validator import ResumeUnderstandingValidator

        return ResumeUnderstandingValidator().validate_and_fix(result, inp.resume_text)

    def _limit_strings(self, values, limit: int) -> list[str]:
        """Keep schema-bounded LLM lists from failing validation."""
        if not isinstance(values, list):
            return []
        return [str(value) for value in values if str(value).strip()][:limit]
