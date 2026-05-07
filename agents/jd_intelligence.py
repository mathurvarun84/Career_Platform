"""
JDIntelligenceAgent - Agent 2 of the Resume Intelligence Platform.

Analyzes a job description text and extracts:
- Target role title
- Must-have and nice-to-have skills
- Hidden signals (implied but unstated requirements)
- Semantic skill map (equivalent technologies for each requirement)
- Expected seniority level
- Company type

Uses semantic understanding: e.g., 'event streaming' implies Kafka/Pulsar,
'fast APIs' implies low-latency knowledge, not just REST frameworks.

Validates input and output against Pydantic schemas defined in schemas/agent2_schema.py.
Provider: OpenAI (gpt-4o-mini)
Max tokens: 4000
"""

import json
from typing import Dict, List

from .base_agent import BaseAgent
from schemas.agent2_schema import JDIntelligenceInput, JDIntelligenceOutput, HiddenSignal
from schemas.common import Seniority, CompanyType


class JDIntelligenceAgent(BaseAgent):
    """
    Agent 2: Job Description Analyst.

    Extracts hiring intent and skill requirements from raw job description text.
    Validates input against JDIntelligenceInput, calls LLM, parses JSON response,
    validates output against JDIntelligenceOutput.

    Model: gpt-4o-mini
    Max tokens: 4000
    Provider: OpenAI
    """

    def __init__(self):
        super().__init__(model="gpt-4o-mini", max_tokens=4000, provider="openai")

    def run(self, input_dict: dict) -> dict:
        """
        Analyze a job description and extract hiring intent.

        Args:
            input_dict: Must contain 'jd_text' (str).

        Returns:
            Validated JDIntelligenceOutput serialized as dict.

        Raises:
            ValueError: If LLM response is missing required keys or validation fails.
            RuntimeError: If LLM call fails after retries or API key is missing.
        """
        # Validate input
        inp = JDIntelligenceInput(**input_dict)
        jd_text = inp.jd_text

        # JDs are rarely long, but cap very large inputs to leave room for the prompt and JSON response.
        max_chars = 500000
        if len(jd_text) > max_chars:
            jd_text = jd_text[:max_chars] + "...[truncated]"

        # System prompt with semantic understanding instructions
        system_prompt = (
            "You are a job description analyst for Indian software engineering roles. You receive raw JD text and must extract structured information about the role, required skills, hidden signals, and seniority/company type. "
            "Use deep semantic understanding to read between the lines — infer implied requirements and signals, not just explicit keywords.\n\n"
            "Extract hiring intent with semantic understanding — read between the lines, not just keywords.\n\n"
            "Semantic expansion rules:\n"
            "- 'event streaming' → Kafka, Pulsar, Kinesis\n"
            "- 'fast APIs' → low-latency, sub-100ms, high-throughput (not just REST)\n"
            "- 'owns the roadmap' → no PM, engineer owns product decisions (seniority signal)\n"
            "- 'mentor junior engineers' → staff/lead-level expectation even if title says senior\n"
            "- 'immediate joiner' → backfill role, likely urgent or attrition-driven\n"
            "- 'work with global teams' → overlapping hours with US/EU, communication signal\n\n"
            "Return ONLY valid JSON with these exact keys:\n"
            "- role_title (string): exact title as written in the JD\n"
            "- must_have_skills (list of strings): explicitly required, dealbreaker if missing\n"
            "- nice_to_have_skills (list of strings): preferred or bonus, not dealbreakers\n"
            "- hidden_signals (list of dicts): each dict has 'signal' (string) and 'implication' (string) — "
            "  e.g. {\"signal\": \"owns roadmap\", \"implication\": \"no PM, high ownership expected\"}\n"
            "- semantic_skill_map (dict): maps each JD skill/phrase → list of resume terms a candidate might use instead — "
            "  e.g. {\"event streaming\": [\"Kafka\", \"Pulsar\", \"Kinesis\", \"message queue\"]}\n"
            "- seniority_expected (string): one of 'junior','mid','senior','staff' — "
            "  infer from responsibilities and expectations, not just the title\n"
            "- company_type (string): one of 'faang','product-unicorn','funded-startup','enterprise','service-based','unknown'\n\n"
            "No extra keys. No markdown fences. No explanations."
        )

        user_message = jd_text

        # Call LLM and parse JSON response
        raw_response = self._call_llm(system_prompt, user_message)
        parsed_output = self._parse_json(raw_response)
        # Validate and structure using Pydantic model
        # Pydantic will coerce seniority_expected and company_type to enums
        output = JDIntelligenceOutput(**parsed_output)
 
        return output.model_dump()
