"""
Agent 5 - Recruiter Simulator.

Simulates 4 fixed recruiter personas plus 1 conditional persona evaluating a
candidate's resume in a single LLM call. Returns individual verdicts and
aggregate statistics.

Uses Anthropic Claude via the Anthropic SDK (provider='anthropic').
"""

import json
import logging

from agents.base_agent import BaseAgent


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


def _build_system_prompt(active_personas: dict) -> str:
    prompt = """You are a recruiter evaluation system simulating 5 different recruiter personas
assessing an Indian software engineering candidate's resume.

For each persona, evaluate the resume independently using that persona's specific priorities and biases.

PERSONAS:
"""
    for i, (name, text) in enumerate(active_personas.items(), 1):
        prompt += f"{i}. {name} - {text}\n\n"

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

RESPONSE FORMAT - return ONLY this JSON, no markdown, no preamble:

{
  "personas": [
    {
      "persona": "exact persona name from the numbered list above",
      "first_impression": "1-2 sentence first reaction from this persona's perspective",
      "noticed": ["specific positive signals this persona values - at least 2"],
      "ignored": ["specific things this persona discounted - at least 1"],
      "rejection_reason": "primary reason for rejection, or empty string if shortlisted",
      "shortlist_decision": true or false,
      "fit_score": 0-100 integer representing fit against THIS persona's criteria,
      "flip_condition": "ONE specific actionable change that would flip this persona to shortlist. Empty string if already shortlisted."
    }
  ],
  "shortlist_rate": 0.0,
  "consensus_strengths": ["only signals praised by 3 or more personas"],
  "consensus_weaknesses": ["only issues flagged by 3 or more personas"],
  "most_critical_fix": "single highest-priority improvement derived from the most common flip_conditions above"
}

The personas array must have exactly 5 entries in the same order as the numbered list."""
    return prompt


class RecruiterSimulatorAgent(BaseAgent):
    """
    Agent 5 - Recruiter Simulator.

    Evaluates a candidate's resume through the lens of 5 recruiter personas
    in a single LLM call. Returns individual verdicts and aggregate statistics.
    """

    def __init__(self):
        """
        Initialize Agent 5 with claude-haiku-4-5-20251001, 4000 max tokens, Anthropic provider.

        Agent 5 is the only agent that uses Anthropic - all others use OpenAI.
        """
        super().__init__(model="claude-haiku-4-5-20251001", max_tokens=4000, provider="anthropic")

    def run(self, input_dict: dict) -> dict:
        """
        Evaluate resume through 5 recruiter personas.

        Args:
            input_dict: Must contain 'resume_text' (str), and may contain
                'resume_sections' and 'jd_intelligence'.

        Returns:
            Dict with keys: personas, shortlist_rate, consensus_strengths,
            consensus_weaknesses, most_critical_fix, fix_priority.
        """
        resume_text = input_dict.get("resume_text", "")
        resume_sections = input_dict.get("resume_sections", {})
        jd_intelligence = input_dict.get("jd_intelligence")
        conditional_name, conditional_prompt = _select_conditional_persona(resume_text, resume_sections)
        active_personas = {**PERSONA_PROMPTS, conditional_name: conditional_prompt}

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

        system_prompt = _build_system_prompt(active_personas)
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
