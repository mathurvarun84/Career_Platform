"""
Agent 5 - Recruiter Simulator.

Simulates 4 fixed recruiter personas plus 1 conditional persona evaluating a
candidate's resume in a single LLM call. Returns individual verdicts and
aggregate statistics.

Uses Anthropic Claude via the Anthropic SDK (provider='anthropic').
"""

import json
import logging

from backend.few_shot_prompts import build_recruiter_role_addendum
from .base_agent import BaseAgent


logger = logging.getLogger(__name__)


PERSONA_PROMPTS = {
    "FAANG Technical Screener": (
        "You are a FAANG Technical Screener at Google, Meta, Flipkart, or Swiggy. "
        "You care about system design signals, scale numbers, and technical depth. "
        "You look for large-scale ownership: crore-level business impact, lakh-scale "
        "users, QPS metrics, SLA numbers. You expect distributed systems depth - "
        "Kafka, gRPC, sharding, rate limiting, observability. "
        "Vague descriptions without INR/scale figures make you skeptical. "
        "A candidate without at least one system-design war story is a pass."
    ),
    "High-Volume Agency Recruiter": (
        "You are a High-Volume Agency Recruiter in the Indian market, sourcing "
        "from Naukri, LinkedIn, and IIMJobs simultaneously for 50+ JDs. "
        "You spend under 30 seconds on a resume. You scan for: years of experience "
        "in the first 3 lines, current company tier, tech stack keyword match, "
        "and notice period signals. CTC trajectory matters - you infer it from "
        "company progression. Service-to-product transitions catch your eye as "
        "a positive signal worth a call."
    ),
    "Startup Hiring Manager": (
        "You are a Startup Hiring Manager at a Series B-D Indian startup "
        "(Bengaluru, Hyderabad, or Mumbai). You want ownership language, breadth, "
        "and scrappy execution. You look for end-to-end product shipping with "
        "minimal oversight. Service-company background (TCS, Infosys, Wipro, "
        "Cognizant) without a product-company transition is a yellow flag. "
        "You want to see: 'I built', 'I owned', 'I shipped' - not 'I worked on'."
    ),
    "Senior IC Evaluator": (
        "You are a Senior IC Evaluator (Staff/Principal Engineer) at a product "
        "company. You look for technical depth, architecture ownership, and "
        "mentorship evidence. You want: complex system design with explicit "
        "tradeoffs, code ownership at scale, influence on engineering culture. "
        "You distrust resumes that list 15 technologies without showing depth "
        "in any. One deep system ownership story beats five shallow feature mentions."
    ),
}


CONDITIONAL_PERSONAS = {
    "fintech": (
        "Fintech Risk-Aware Recruiter",
        "You are a Fintech Risk-Aware Recruiter hiring for Razorpay, Zepto, "
        "PhonePe, or a NBFC. You flag vague compliance and security experience. "
        "You look for: PCI-DSS, SOC2, RBI compliance signals, UPI/payment stack "
        "familiarity, fraud detection systems, SEBI-adjacent experience. "
        "Data privacy signals (DPDP Act awareness) matter. General backend "
        "experience without fintech specifics is not enough."
    ),
    "enterprise": (
        "Legacy Enterprise Recruiter",
        "You are a Legacy Enterprise Recruiter hiring for large Indian IT "
        "(TCS, Infosys, Wipro, HCL) or BFSI companies. "
        "You value: certifications (AWS, Azure, PMP, ITIL, TOGAF), long tenures "
        "(3+ years per company), formal credentials, CMM/process compliance signals. "
        "Frequent job changes (under 2 years) are a red flag. SAP, Oracle, "
        "Mainframe, or established enterprise stack experience is a strong positive. "
        "Startup-only background without enterprise delivery experience is a concern."
    ),
    "default": (
        "Product Company PM-adjacent Recruiter",
        "You are a Product Company PM-adjacent Recruiter at a B2C or B2B SaaS "
        "company. You want customer impact framing and cross-functional "
        "collaboration evidence. You look for how the candidate's work affected "
        "users, NPS, revenue, or product metrics. Task-executor language "
        "('worked on', 'helped with', 'assisted') is a red flag. "
        "You want to see the candidate's product thinking, not just execution."
    ),
}


FINTECH_SIGNALS = {"razorpay", "phonepe", "paytm", "zepto", "upi", "payments",
                   "fintech", "nbfc", "banking", "insurance", "pci", "rbi"}
ENTERPRISE_SIGNALS = {"tcs", "infosys", "wipro", "hcl", "cognizant", "accenture",
                      "capgemini", "tech mahindra", "mphasis", "hexaware"}

DIMENSION_LABELS = {
    "keyword_match": "keyword and tech stack coverage",
    "formatting": "resume formatting and structure",
    "readability": "sentence clarity and readability",
    "impact_metrics": "quantified impact and metrics",
}

DIMENSION_BENCHMARKS = {
    "keyword_match": 20,
    "formatting": 21,
    "readability": 19,
    "impact_metrics": 18,
}

# Maps weakest dimension -> the persona name that should probe it.
# All four persona names are keys in PERSONA_PROMPTS (always present).
PROBING_PERSONA_MAP = {
    "keyword_match": "High-Volume Agency Recruiter",
    "formatting": "High-Volume Agency Recruiter",
    "readability": "Senior IC Evaluator",
    "impact_metrics": "FAANG Technical Screener",
}

# Tie-break order when multiple dimensions share the same max gap.
# impact_metrics first because it is most visible to all recruiter types.
_WEAKNESS_TIE_PRIORITY = [
    "impact_metrics", "keyword_match", "formatting", "readability"
]


def _select_conditional_persona(resume_text: str, resume_sections: dict) -> tuple[str, str]:
    """
    Select the 5th persona based on resume content signals.
    Returns (persona_name, persona_prompt).
    Checks resume_text + experience section full_text for domain signals.
    """
    check_text = resume_text.lower()
    exp_section = resume_sections.get("experience")
    if exp_section:
        exp_text = getattr(exp_section, "full_text", "") or ""
        check_text += " " + exp_text.lower()

    if any(signal in check_text for signal in FINTECH_SIGNALS):
        return CONDITIONAL_PERSONAS["fintech"]
    if any(signal in check_text for signal in ENTERPRISE_SIGNALS):
        return CONDITIONAL_PERSONAS["enterprise"]
    return CONDITIONAL_PERSONAS["default"]


def _find_weakest_dimension(
    ats_breakdown: dict,
) -> tuple[str | None, int | None, int | None]:
    """
    Identify the ATS dimension with the largest gap from its benchmark.

    Returns (dimension_key, user_score, benchmark).
    Returns (None, None, None) when the candidate meets or exceeds all benchmarks
    - in that case no weakness injection is needed.

    Tie-breaking: when multiple dimensions share the same max gap, the dimension
    appearing earliest in _WEAKNESS_TIE_PRIORITY wins.
    """
    gaps = {
        dim: max(0, DIMENSION_BENCHMARKS[dim] - score)
        for dim, score in ats_breakdown.items()
        if dim in DIMENSION_BENCHMARKS
    }

    if not gaps:
        return None, None, None

    max_gap = max(gaps.values())
    if max_gap == 0:
        return None, None, None

    for dim in _WEAKNESS_TIE_PRIORITY:
        if gaps.get(dim, 0) == max_gap:
            return dim, ats_breakdown[dim], DIMENSION_BENCHMARKS[dim]

    # Fallback - should not be reached if ats_breakdown keys are correct
    dim = max(gaps, key=lambda d: gaps[d])
    return dim, ats_breakdown[dim], DIMENSION_BENCHMARKS[dim]


def _extract_missing_evidence(dim_key: str, resume_text: str) -> str:
    """
    Return a short, concrete description of what is missing for the given dimension.
    Pure regex - zero LLM calls. Used inside the weakness injection prompt to give
    the probing persona something specific to cite.
    """
    import re
    text_lower = resume_text.lower()

    if dim_key == "impact_metrics":
        number_count = len(re.findall(r"\b\d+[%kKmMbB]?\b", resume_text))
        if number_count < 3:
            return "there are fewer than 3 quantified outcomes in the entire resume"
        return (
            "impact bullets are vague - no throughput (QPS/TPS), "
            "cost savings, or INR/scale numbers visible"
        )

    if dim_key == "keyword_match":
        weak_openers = re.findall(
            r"\b(worked on|helped|assisted|participated|involved in|responsible for)\b",
            text_lower,
        )
        if weak_openers:
            return (
                f"action verbs are weak - phrases like '{weak_openers[0]}' "
                f"appear multiple times instead of strong ownership verbs"
            )
        return (
            "tech stack keywords are thin - "
            "missing core stack terms expected at this seniority level"
        )

    if dim_key == "formatting":
        missing = [
            s for s in ["summary", "skills", "experience", "education"]
            if s not in text_lower
        ]
        if missing:
            return f"missing standard sections: {', '.join(missing)}"
        return (
            "bullet structure is inconsistent - "
            "mixing full sentences and fragments within the same section"
        )

    if dim_key == "readability":
        sentences = re.split(r"[.!?]", resume_text)
        long_count = sum(1 for s in sentences if len(s.split()) > 30)
        if long_count > 0:
            return (
                f"{long_count} bullet(s) exceed 30 words - "
                "too dense to parse in a 30-second skim"
            )
        return (
            "sentence complexity is high - "
            "recruiter has to re-read bullets to extract the actual contribution"
        )

    return "this dimension is below the benchmark for candidates at this level"


def _build_weakness_injection(
    dim_key: str,
    user_score: int,
    benchmark: int,
    resume_text: str,
) -> str:
    """
    Build the text paragraph that is appended to the probing persona's prompt.
    Cites the actual score, benchmark, gap, and a concrete missing-evidence hint.
    """
    label = DIMENSION_LABELS[dim_key]
    gap = benchmark - user_score
    evidence_hint = _extract_missing_evidence(dim_key, resume_text)

    return (
        f"\n\nWEAKNESS TARGET - PROBING INSTRUCTION:\n"
        f"Before evaluating anything else, you have already noticed that this resume "
        f"scores {user_score}/25 on {label} (the benchmark is {benchmark}/25 - "
        f"a gap of {gap} points). "
        f"Your first_impression MUST open by calling out this specific gap. "
        f"Be concrete: {evidence_hint}. "
        f"Do not soften this observation. "
        f"If you reject this candidate, your rejection_reason must cite this gap directly."
    )


def _build_system_prompt(
    active_personas: dict,
    weakness_injection: dict | None = None,
    role_family: str = "ENGINEERING",
) -> str:
    prompt = """You are a recruiter evaluation system simulating 5 different recruiter personas
assessing an Indian candidate's resume.

For each persona, evaluate the resume independently using that persona's specific priorities and biases.
"""
    prompt += build_recruiter_role_addendum(role_family)
    prompt += """
PERSONAS:
"""
    for i, (name, text) in enumerate(active_personas.items(), 1):
        persona_text = text
        if weakness_injection and name == weakness_injection["persona_name"]:
            persona_text = text + weakness_injection["injection"]
        prompt += f"{i}. {name} - {persona_text}\n\n"

    prompt += """
EVALUATION RULES:
- Each persona must evaluate independently - do not let personas influence each other
- consensus_strengths: only include signals explicitly noticed by 3 or more personas
- consensus_weaknesses: only include issues flagged by 3 or more personas
- rejection_reason: use empty string "" (not null) when shortlist_decision is true
- fit_score: score against THIS persona's criteria only, not general quality.
  0-30: clear mismatch, 31-60: partial match with significant gaps,
  61-80: good fit with addressable gaps, 81-100: strong match
- Return personas array in the same order as the numbered list above

LENGTH LIMITS (HARD - do not exceed):
- first_impression: under 25 words
- each noticed item: under 12 words
- each ignored item: under 12 words
- rejection_reason: under 20 words (empty "" when shortlisted)
- flip_condition: under 18 words (empty "" when shortlisted)
- each consensus_strengths item: under 14 words
- each consensus_weaknesses item: under 14 words
- most_critical_fix: under 20 words
- noticed: 2-3 items max | ignored: 1-2 items max
- consensus_strengths: 2-4 items | consensus_weaknesses: 2-4 items

RESPONSE FORMAT - return ONLY this JSON, no markdown, no preamble:

{
  "personas": [
    {
      "persona": "exact persona name from the numbered list above",
      "first_impression": "under 25 words",
      "noticed": ["2-3 short items, each under 12 words"],
      "ignored": ["1-2 short items, each under 12 words"],
      "rejection_reason": "under 20 words, or empty string if shortlisted",
      "shortlist_decision": true or false,
      "fit_score": 0-100 integer representing fit against THIS persona's criteria,
      "flip_condition": "under 18 words; empty string if already shortlisted"
    }
  ],
  "shortlist_rate": 0.0,
  "consensus_strengths": ["only signals praised by 3 or more personas"],
  "consensus_weaknesses": ["only issues flagged by 3 or more personas"],
  "most_critical_fix": "single highest-priority improvement under 20 words"
}

The personas array must have exactly 5 entries in the same order as the numbered list.
Be terse - the JSON must fit within strict token budgets. Cut adjectives, no preamble."""
    return prompt


class RecruiterSimulatorAgent(BaseAgent):
    """
    Agent 5 - Recruiter Simulator.

    Evaluates a candidate's resume through the lens of 5 recruiter personas
    in a single LLM call. Returns individual verdicts and aggregate statistics.
    """

    def __init__(self):
        """
        Initialize Agent 5 with claude-haiku-4-5-20251001, 6000 max tokens, Anthropic provider.

        Agent 5 is the only agent that uses Anthropic - all others use OpenAI.

        max_tokens bumped from 4000 to 6000: 5 detailed personas with 7 fields each
        plus consensus arrays were exceeding the previous ceiling, causing mid-string
        truncation and unrecoverable JSON. 6000 gives ~50% headroom while staying
        well within claude-haiku-4-5's output capacity.
        """
        super().__init__(model="claude-haiku-4-5-20251001", max_tokens=6000, provider="anthropic")

    def run(self, input_dict: dict) -> dict:
        """
        Evaluate resume through 5 recruiter personas.

        Args:
            input_dict: Must contain 'resume_text' (str), and may contain
                'resume_sections' and 'jd_intelligence'.

        Returns:
            Dict with keys: personas, shortlist_rate, consensus_strengths,
            consensus_weaknesses, most_critical_fix, fix_priority.
            probing_persona: str | None - name of the persona given the weakness injection, or None
            probing_dimension: str | None - ATS dimension key that was targeted, or None
        """
        resume_text = input_dict.get("resume_text", "")
        resume_sections = input_dict.get("resume_sections", {})
        jd_intelligence = input_dict.get("jd_intelligence")
        role_family = str(
            input_dict.get("role_family")
            or input_dict.get("resume_understanding", {}).get("role_family")
            or "ENGINEERING"
        ).upper()
        conditional_name, conditional_prompt = _select_conditional_persona(resume_text, resume_sections)
        active_personas = {**PERSONA_PROMPTS, conditional_name: conditional_prompt}

        weakness_injection = None
        probing_dimension = None
        ats_result = input_dict.get("ats_result")
        if ats_result and isinstance(ats_result.get("breakdown"), dict):
            dim_key, user_score, benchmark = _find_weakest_dimension(ats_result["breakdown"])
            if dim_key is not None:
                probing_persona = PROBING_PERSONA_MAP[dim_key]
                injection_text = _build_weakness_injection(
                    dim_key, user_score, benchmark, resume_text
                )
                weakness_injection = {
                    "persona_name": probing_persona,
                    "injection": injection_text,
                }
                probing_dimension = dim_key

        if not resume_text or not isinstance(resume_text, str):
            raise ValueError("RecruiterSimulatorAgent: resume_text must be a non-empty string")

        max_chars = 300000
        if len(resume_text) > max_chars:
            resume_text = resume_text[:max_chars] + "...[truncated]"

        user_message = self._format_resume_for_personas(resume_text, resume_sections)
        if jd_intelligence:
            user_message += f"\n\nJOB DESCRIPTION INTELLIGENCE:\n{json.dumps(jd_intelligence, indent=2)}"
        else:
            user_message += "\n\nNO JOB DESCRIPTION - evaluate against general market."

        system_prompt = _build_system_prompt(
            active_personas, weakness_injection, role_family=role_family
        )
        raw_response = self._call_llm(system_prompt, user_message)
        parsed = self._parse_json(raw_response)

        required_keys = [
            "personas", "shortlist_rate", "consensus_strengths",
            "consensus_weaknesses", "most_critical_fix",
        ]
        self.validate_output(parsed, required_keys)

        if len(parsed["personas"]) > 5:
            logger.warning(
                "%s: LLM returned %d personas, trimming to 5",
                self.__class__.__name__,
                len(parsed["personas"]),
            )
            parsed["personas"] = parsed["personas"][:5]
        elif len(parsed["personas"]) < 5:
            raise ValueError(
                f"RecruiterSimulatorAgent: expected 5 personas, got {len(parsed['personas'])}"
            )

        parsed["fix_priority"] = self._build_fix_priority(parsed["personas"])
        parsed["probing_persona"] = (
            weakness_injection["persona_name"] if weakness_injection else None
        )
        parsed["probing_dimension"] = probing_dimension
        return parsed

    def _format_resume_for_personas(self, resume_text: str, resume_sections: dict) -> str:
        """
        Formats resume as a clean labelled document for persona evaluation.
        Uses SectionText from sectioner if available, falls back to raw text.
        """
        if not resume_sections:
            return f"CANDIDATE RESUME:\n{resume_text}"

        section_order = [
            "summary", "skills", "experience",
            "education", "certifications", "awards",
        ]
        lines = ["CANDIDATE RESUME:", ""]

        for section_name in section_order:
            section = resume_sections.get(section_name)
            full_text = getattr(section, "full_text", "")
            if not full_text.strip():
                continue
            lines.append(f"{section_name.upper()}:")
            lines.append(full_text.strip())
            lines.append("")

        return "\n".join(lines)

    def _build_fix_priority(self, personas: list) -> list:
        """
        Aggregates flip_conditions from rejecting personas into a ranked fix list.
        Pure Python - zero LLM calls.
        """
        from collections import defaultdict

        rejects = [
            p for p in personas
            if not p.get("shortlist_decision") and p.get("flip_condition", "").strip()
        ]

        if not rejects:
            return []

        stopwords = {
            "a", "an", "the", "to", "and", "or", "in", "of", "for",
            "with", "this", "that", "add", "include", "show", "use",
        }

        def _group_key(text: str) -> str:
            words = [
                w.lower().strip(".,;:") for w in text.split()
                if w.lower().strip(".,;:") not in stopwords and len(w) > 2
            ]
            return " ".join(words[:4])

        groups: dict = defaultdict(lambda: {
            "fixes": [], "personas": [], "fit_scores": [],
        })

        for p in rejects:
            key = _group_key(p["flip_condition"])
            groups[key]["fixes"].append(p["flip_condition"])
            groups[key]["personas"].append(p["persona"])
            groups[key]["fit_scores"].append(p.get("fit_score", 0))

        result = []
        for data in groups.values():
            representative = max(data["fixes"], key=len)
            result.append({
                "fix": representative,
                "persona_count": len(data["personas"]),
                "personas": data["personas"],
                "avg_fit_score": round(
                    sum(data["fit_scores"]) / len(data["fit_scores"]), 1
                ),
            })

        return sorted(result, key=lambda x: x["persona_count"], reverse=True)
