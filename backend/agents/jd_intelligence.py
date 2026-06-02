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
from backend.schemas.agent2_schema import JDIntelligenceInput, JDIntelligenceOutput
from backend.schemas.common import CompanyType

# Few-shot block teaches the two seniority fields — primary fix for enum validation errors.
_JD_SENIORITY_FEW_SHOT = """
SENIORITY FIELD RULE (two separate fields — never swap them):
- seniority_expected: IC band ONLY → "junior" | "mid" | "senior" | "staff"
- jd_seniority_level: actual role level → includes "manager" | "director" | "vp" | "c-suite"

FEW-SHOT EXAMPLES (copy this split exactly):

Example A — JD: "Director of Engineering, 12+ years, define org-wide architecture, hire and mentor EMs"
CORRECT:
{"seniority_expected": "staff", "jd_seniority_level": "director", "min_years_required": 12}
WRONG (causes validation failure):
{"seniority_expected": "director", "jd_seniority_level": "director"}

Example B — JD: "Engineering Manager, 8+ years, people management, 1:1s, delivery ownership"
CORRECT:
{"seniority_expected": "senior", "jd_seniority_level": "manager", "min_years_required": 8}
WRONG:
{"seniority_expected": "manager", "jd_seniority_level": "unknown"}

Example C — JD: "Senior Software Engineer, 5+ years, hands-on coding, no people management"
CORRECT:
{"seniority_expected": "senior", "jd_seniority_level": "senior", "min_years_required": 5}

Example D — JD: "VP Engineering, 15+ years, board/exec stakeholder management"
CORRECT:
{"seniority_expected": "staff", "jd_seniority_level": "vp", "min_years_required": 15}
WRONG:
{"seniority_expected": "vp", "jd_seniority_level": "staff"}
"""

# Few-shot block for must_have vs nice_to_have bucketing (F008, F019 eval fixtures).
_JD_SKILL_BUCKET_FEW_SHOT = """
MUST-HAVE vs NICE-TO-HAVE BUCKETING (follow exactly):

RULE: If a skill appears in a JD section explicitly labeled "Requirements", "Required",
"Must Have", or "Qualifications" — it MUST go in must_have_skills, regardless of how
common or basic the skill seems (e.g. Python, SQL, JIRA, Git, Agile).

RULE: Skills only in "Nice to Have", "Preferred", "Good to have", "Bonus", or marked
"strong plus" / "ideally" go in nice_to_have_skills ONLY.

Example F008 — JD_002 Data Analyst (Requirements lists Python; Nice to Have lists dbt):
JD excerpt: "Requirements: ... Experience with Python or R for data wrangling ...
Nice to Have: Experience with dbt for data transformation"
CORRECT:
{"must_have_skills": ["SQL", "Python or R", "Tableau or Power BI", ...],
 "nice_to_have_skills": ["dbt", "Google BigQuery", "Redshift", "A/B testing methodology"]}
WRONG (Python in nice_to_have when Requirements explicitly require it):
{"must_have_skills": ["SQL", "Tableau"], "nice_to_have_skills": ["Python", "dbt"]}

Example F019 — JD_004 Business Analyst (domain exposure is "strong plus", not mandatory):
JD excerpt: "Requirements: ... Hands-on JIRA experience ... Working knowledge of SQL ...
Exposure to payments domain: UPI, NEFT, IMPS, or card networks is a strong plus"
CORRECT:
{"must_have_skills": ["JIRA", "SQL", "BRDs/FSDs", "Agile/Scrum", ...],
 "nice_to_have_skills": ["payments domain UPI/NEFT/IMPS", "Postman", "Microsoft D365", "PMP/CBAP"]}
WRONG (treating domain exposure as must_have):
{"must_have_skills": ["payments domain", "UPI", "NEFT", "JIRA"], "nice_to_have_skills": ["SQL"]}
"""

_IC_SENIORITY = frozenset({"junior", "mid", "senior", "staff"})
_MGMT_SENIORITY = frozenset({"em", "senior_em", "director"})
_LEADERSHIP_LEVELS = frozenset({"manager", "director", "vp", "c-suite"})


def _guard_seniority_fields(parsed: dict) -> dict:
    """Tiny fallback if the model still puts a leadership title in seniority_expected."""
    out = dict(parsed)
    exp_raw = str(out.get("seniority_expected") or "").lower().strip()
    exp = exp_raw.replace("_", "-")
    exp_key = exp_raw.replace("-", "_")
    jd = str(out.get("jd_seniority_level") or "").lower().strip().replace("_", "-")

    if exp_key in _MGMT_SENIORITY:
        # Backfill jd_seniority_level when the model left it as unknown.
        if jd in ("", "unknown"):
            out["jd_seniority_level"] = exp_key
    elif exp in _LEADERSHIP_LEVELS:
        if jd in ("", "unknown") or jd in _IC_SENIORITY or jd.replace("-", "_") in _MGMT_SENIORITY:
            out["jd_seniority_level"] = exp
        if exp == "manager":
            out["seniority_expected"] = "em"
        elif exp in ("director", "vp", "c-suite"):
            out["seniority_expected"] = "director"
        else:
            out["seniority_expected"] = "senior"

    try:
        out["min_years_required"] = int(out.get("min_years_required") or 0)
    except (TypeError, ValueError):
        out["min_years_required"] = 0

    return out


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
            "- 'work with global teams' → overlapping hours with US/EU, communication signal\n"
            "- 'manage a team of engineers' → Engineering Manager role (em), not IC senior\n"
            "- 'drive hiring plan / headcount' → Senior EM or Director signal\n"
            "- 'org-wide technical strategy' or 'build the engineering org' → Director-level scope\n\n"
            "Return ONLY valid JSON with these exact keys:\n"
            "- role_title (string): exact title as written in the JD\n"
            "- must_have_skills (list of strings): skills explicitly stated as REQUIRED in the JD. "
            "  Rules: "
            "  (0) If a skill appears under a section labeled 'Requirements', 'Required', 'Must Have', "
            "  or 'Qualifications', it MUST be in must_have_skills — never demote to nice_to_have. "
            "  (1) If JD says 'or' between two skills (e.g. 'Java or Python'), treat as ONE combined entry like 'Java or Python' — do NOT split into two separate must-haves. "
            "  (2) If JD uses phrases like 'strong plus', 'preferred', 'nice to have', 'ideally', or 'bonus' — place in nice_to_have_skills, NEVER in must_have_skills. "
            "  (3) Include ALL explicitly required skills from the Requirements section — do not skip items like REST API design, Git, code review, or Agile if they appear in Requirements. "
            "  (4) Do NOT include role-implied skills not stated in the JD text.\n"
            "- nice_to_have_skills (list of strings): skills the JD marks as preferred, bonus, or optional. "
            "  Always include items from 'Nice to Have' / 'Preferred' / 'Good to have' sections here, never in must_have_skills.\n"
            "- hidden_signals (list of dicts): each dict has 'signal' (string) and 'implication' (string) — "
            "  e.g. {\"signal\": \"owns roadmap\", \"implication\": \"no PM, high ownership expected\"}\n"
            "- semantic_skill_map (dict): maps each JD skill/phrase → list of resume terms a candidate might use instead — "
            "  e.g. {\"event streaming\": [\"Kafka\", \"Pulsar\", \"Kinesis\", \"message queue\"]}\n"
            "- seniority_expected (string): one of 'junior','mid','senior','staff','em','senior_em','director' — "
            "  IC track: infer from technical depth and YOE expectations in the JD. "
            "  Management track — use these signals:\n"
            "  'em' if JD mentions managing a team of engineers, conducting 1:1s, hiring, or performance reviews. "
            "  Title signals: 'Engineering Manager', 'EM', 'People Manager'.\n"
            "  'senior_em' if JD expects managing multiple teams, group-level delivery, or managing other EMs. "
            "  Title signals: 'Senior EM', 'Group Engineering Manager', 'Senior Engineering Manager'.\n"
            "  'director' if JD describes org-level ownership, VP-equivalent scope, multi-team org, or budget ownership. "
            "  Title signals: 'Director of Engineering', 'VP Engineering', 'Head of Engineering', 'Engineering Director'.\n"
            "  RULE: If the JD title contains 'Manager', 'Director', 'VP', or 'Head of Engineering', always use the management track.\n"
            "- company_type (string): one of 'faang','product-unicorn','funded-startup','enterprise','service-based','unknown'\n"
            "- min_years_required (int): minimum years of experience explicitly or implicitly required. "
            "  Infer from phrases like \"10+ years\", \"minimum 8 years\", \"senior IC with 5+ years\". "
            "  If completely unstated, estimate from jd_seniority_level: junior=0, mid=2, senior=5, staff=7, "
            "  manager=6, director=10, vp=14, c-suite=18. Return 0 if truly unknown.\n"
            "- jd_seniority_level (string): the ACTUAL role level — one of \"junior\",\"mid\",\"senior\",\"staff\","
            "\"manager\",\"director\",\"vp\",\"c-suite\",\"unknown\". "
            "  Put Director/VP/EM titles HERE, not in seniority_expected. "
            "  Infer from title AND responsibilities — use responsibilities over title.\n"
            + _JD_SENIORITY_FEW_SHOT
            + _JD_SKILL_BUCKET_FEW_SHOT
            + "\nNo extra keys. No markdown fences. No explanations."
        )

        user_message = jd_text

        # Call LLM and parse JSON response
        raw_response = self._call_llm(system_prompt, user_message)
        parsed_output = self._parse_json(raw_response)
        parsed_output = _guard_seniority_fields(parsed_output)
        output = JDIntelligenceOutput(**parsed_output)
 
        return output.model_dump()
