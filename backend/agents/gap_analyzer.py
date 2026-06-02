"""
GapAnalyzerAgent - Agent 3 of the Resume Intelligence Platform.

Compares structured resume data (from Agent 1) against JD intelligence
(from Agent 2) to produce a prioritized gap list for Agent 4 (Rewriter).

Provider: OpenAI (gpt-4o-mini)
Max tokens: 4000
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from backend.schemas.agent3_schema import (
    GapAnalyzerInput,
    GapAnalyzerOutput,
    DetailedEvalOutput,
    SectionGap,
    SubLocationChange,
)
from backend.few_shot_prompts import build_role_gap_addendum
from backend.role_fit import compute_role_fit
from backend.schemas.common import GapType, SectionText, SubEntry

# Canonical sections every analysis must cover
CANONICAL_SECTIONS = [
    "summary",
    "skills",
    "experience",
    "education",
    "certifications",
    "awards",
]

GAP_SYSTEM_PROMPT = """You are a Gap Analyzer for a resume-to-JD comparison. You receive structured resume understanding and JD intelligence, and your task is to identify and prioritize gaps in the resume relative to the JD.
These gaps will inform targeted rewrites to improve JD fit. Focus on actionable, high-impact changes that directly address specific JD requirements.

**CRITICAL INSTRUCTION: Check every gap against the FULL RESUME TEXT before outputting it. If a JD requirement is already demonstrated ANYWHERE in the resume (even with different wording), DO NOT create a gap for it.**

You will receive:
1. Structured resume understanding (experience years, skills, seniority, domains).
2. JD intelligence (must-have/nice-to-have skills, hidden signals, company type).
3. The FULL RESUME TEXT so you can verify every gap against real content.

Your job is to produce ONE JSON object that matches this shape exactly:
{
  "jd_match_score_before": 65,
  "section_gaps": [
    {
      "section": "experience",
      "needs_change": true,
      "gap_type": "Surface",
      "gap_reason": "JD requires Kafka experience not shown in current wording",
      "missing_keywords": ["Kafka"],
      "rewrite_instruction": "Reframe event-driven work to mention streaming platforms",
      "present_in_resume": true,
      "sub_changes": [
        {
          "sub_id": "flipkart_em",
          "sub_label": "Flipkart — EM (2021–present)",
          "needs_change": true,
          "gap_type": "Surface",
          "gap_reason": "No Kafka/real-time streaming mentioned",
          "rewrite_instruction": "Mention stream processing explicitly",
          "missing_keywords": ["Kafka", "streaming"]
        }
      ]
    }
  ],
  "missing_keywords": ["keyword1"],
  "priority_fixes": ["fix 1", "fix 2", "fix 3"]
}

Rules:
- Include ALL canonical sections: summary, skills, experience, education, certifications, awards.
- MISMATCH DETECTION: If the candidate's role family and the JD's role family are
  completely different domains (e.g. HR applying to SWE, Finance applying to DevOps,
  intern applying to Senior role), you MUST flag ALL sections as needs_change=true and
  produce a minimum of 6 section gaps. A domain mismatch is never a 3-gap situation.
- GAP COUNT CALIBRATION:
  Strong match (resume clearly fits JD): 0–3 gaps expected.
  Partial match (overlapping skills, wrong seniority or missing some requirements): 4–7 gaps.
  Mismatch (wrong domain, critically underqualified, or missing 50%+ of requirements): 8+ gaps.
  Never produce fewer than 6 gaps when the resume's domain does not match the JD's domain.
- GAP TYPE RULES (follow these precisely):
  Surface gap: The required skill IS present in the resume but uses different keywords.
    Example: Resume says "event-driven systems", JD says "Kafka". Keyword swap only.
    DO NOT use Surface for skills that are completely absent.
  Structural gap: The required experience EXISTS in the resume but is framed/positioned
    incorrectly. The content is there; only the narrative framing needs to change.
    Example: Candidate led cross-functional projects but never used "stakeholder management"
    language.
    DO NOT use Structural when the content is genuinely absent.
  Evidence gap: The required skill, technology, or experience is COMPLETELY ABSENT from
    the resume. No amount of reframing can fix it — new content is needed.
    Example: JD requires Kubernetes experience; resume never mentions containers at all.
    USE Evidence whenever the skill is not demonstrated anywhere in the resume.
  RULE: When in doubt between Structural and Evidence, choose Evidence. It is better
  to flag a gap as needing new content than to incorrectly suggest reframing absent content.
- SEMANTIC EQUIVALENCE (critical — prevents phantom gaps on strong matches):
  Before flagging a skill as missing, ask: "Is there any term in the resume that is
  functionally equivalent to this missing keyword?" Examples:
  MLflow / experiment tracking ≈ MLOps; CI/CD pipeline ≈ deployment automation;
  K8s / Kubernetes ≈ container orchestration; Spark ≈ big data / distributed processing;
  event-driven / message queue ≈ streaming; Power BI ≈ Tableau (BI tools).
  If equivalent coverage exists anywhere in the resume, set needs_change=false for that gap.
  Use the JD semantic_skill_map equivalents when provided in the input.
- HOLISTIC JD MATCHING (critical for multi-entry sections):
  You have access to the FULL RESUME TEXT below. Before creating a gap for any experience
  entry, read the full resume to understand the complete picture across ALL roles.

  **STRICT RULE: If this JD requirement (e.g., "team leadership", "real-time systems",
  "quantified impact", "architecture", "cross-functional") is ALREADY demonstrated ANYWHERE
  in the resume, do NOT create a gap for that specific entry.** Only flag a role if that
  particular role needs to showcase the skill for context.

  SEMANTIC EQUIVALENCE EXAMPLES:
  - "real-time systems" ≈ "billions in transactions", "high-scale", "transaction-heavy"
  - "architecture evaluation" ≈ "architected", "architectural enhancements", "system design"
  - "team leadership" ≈ "led N engineers", "cross-functional teams", "led team"
  - "quantified impact" ≈ any ₹/$ amount, %, "N users", "N increase", "growth", "efficiency"

  APPLICATION:
  Example 1: If resume shows "Led 32 engineers" in Flipkart, do NOT flag BT for lacking team leadership.
  Example 2: If Microsoft role shows "billions in transactions", do NOT flag Flipkart for lacking "real-time systems".
  Example 3: If any role shows "Generated ₹4 Cr, 30% increase", do NOT flag others for missing metrics.
  Example 4: If the word "architected" OR "architecture" OR "system design" appears anywhere,
             do NOT flag entries for lacking "architecture evaluation".
- PHANTOM GAP RULE: On strong matches (candidate clearly qualified for the role),
  require HIGH confidence before setting needs_change=true. Do not flag gaps for skills
  already demonstrated under different wording. Prefer 0–3 total gaps on strong matches.
- If a section does not need changes, set needs_change=false, gap_reason="No change needed",
  missing_keywords=[], rewrite_instruction="", sub_changes=[].
- For multi-entry sections, decompose into SubLocationChange entries:
  experience: one entry per company/role block
  education: one entry per degree
  certification: one entry per cert
  For summary, skills, awards: sub_changes should be empty list [].
- missing_keywords must be section-specific for section_gaps.
- priority_fixes should contain the top 3 highest-impact actions.
- ACTIONABILITY RULES for rewrite_instruction (critical — follow exactly):
  Every rewrite_instruction MUST contain all three of these elements:
  (1) WHERE: the exact section and sub-location to modify
      (e.g. "In the Experience section, Capgemini bullet 3")
  (2) WHAT: the specific technology, metric type, or skill to add or reframe
      (e.g. "add Kafka as the message broker for the event pipeline")
  (3) HOW: the concrete change to make
      (e.g. "rewrite as: 'Built Kafka-based event pipeline processing 500K msgs/day'")
  BAD instruction: "Add relevant skills to the skills section"
  GOOD instruction: "Add Kafka, Redis, and Docker to the Skills section under Backend
    Technologies, after the existing Python and Django entries"
  BAD instruction: "Improve experience section to highlight technical depth"
  GOOD instruction: "In Experience > Capgemini bullet 2, add the scale metric for the
    Python application: specify daily transaction volume (e.g. '10K+ transactions/day')
    and the async processing pattern used"
  Never use vague verbs like 'improve', 'enhance', 'add relevant', 'highlight'.
  Always name the specific item to add and its target location.
- Output pure JSON only. No markdown, no extra keys.

ANTI-HALLUCINATION: Do NOT include original_content or original_text in your output —
those are handled by the extraction pipeline. Only provide needs_change, gap_reason,
rewrite_instruction, and missing_keywords.

LABEL CONTRACT: sub_label values in sub_changes MUST be copied VERBATIM from the
"EXACT sub_entry labels" list in the input. Do NOT abbreviate, slugify, or paraphrase.
If a sub_entry label is not in that list, do not create a sub_change for it.
"""

EVAL_SYSTEM_PROMPT = """You are a senior technical recruiter evaluating a resume against a specific JD.
Return a DetailedEvalOutput JSON object with this exact structure:

{
  "overall": {
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "jd_fit_summary": "2 sentences summary"
  },
  "changes": [
    {
      "change_id": 1,
      "location": {"section": "experience", "sub_location": "Senior Engineer at XYZ Corp (2020-2022), bullet 3"},
      "change_type": "rewrite_bullet",
      "priority": "critical",
      "why": "two sentence reason",
      "original_text": "Original bullet text",
      "suggested_text": "Complete rewritten bullet text",
      "keywords_added": ["keyword1"]
    }
  ],
  "jd_match_score_before": 65,
  "estimated_score_after": 85
}

PART 1 — overall: OverallAssessment
strengths rules:
- Max 5 items. Cite SPECIFIC evidence: metric, company name, initiative name.
- BAD: "strong leadership"
- GOOD: "Leads 32 engineers across 5 teams at Flipkart — ₹2,500 Cr business impact"

weaknesses rules:
- Max 5 items. Name EXACT section and gap. Never generic.
- BAD: "thin keyword density"
- GOOD: "Experience bullets at ClearTax (2016–2018) do not mention distributed systems
         or event-driven architecture despite running a 1M+ req/hour platform"

jd_fit_summary: 2 sentences — overall fit verdict for THIS specific JD only.

PART 2 — changes: List[ActionableChange]
For every change:
- location.section: exact section name (summary/skills/experience/education/certifications)
- location.sub_location: pinpoint location — role+company+date+bullet number,
  sentence number in summary, or sub-category in skills block.
  NEVER use vague sub_locations like "experience section" — be specific.
- change_type: rewrite_bullet | add_keyword | rewrite_section |
               add_section | remove_content | strengthen_metric
- priority: critical (dealbreaker JD gap) | high (significant miss) | medium (nice to have)
- why: one sentence connecting this change to a specific JD requirement — not generic
- original_text: VERBATIM text from resume at that exact location.
  Use empty string ONLY for add_section or add_keyword with no existing text.
- suggested_text: THE COMPLETE REWRITTEN TEXT — ready to paste into resume.
  For bullets: write the full rewritten bullet.
  For sections: write the full section.
  For skills: write the complete updated line or block.
  NEVER write hints like "add details here" or "mention X technology".
  NEVER write instructions — write the actual content.
- keywords_added: JD keywords this specific change introduces

STRICT RULES:
- suggested_text length must be > 50 characters — never a one-liner hint
- Every change must have original_text (unless truly new content)
- Max 12 changes — prioritise ruthlessly, critical gaps only
- Order: critical first, then high, then medium
- Anti-hallucination: never invent companies, degrees, projects not in resume.
  Use [X%] [N users] [Xms] [₹X Cr] ONLY for metrics genuinely absent from original.
- Return valid JSON only — no markdown, no fences, no preamble.
"""

_EVIDENCE_SIGNALS = {
    "mentor", "coaching", "coach", "1:1", "one-on-one", "performance management",
    "promotion", "career development", "technical guidance", "knowledge transfer",
    "conflict resolution", "stakeholder", "executive communication", "board",
    "p&l ownership", "budget", "hiring decision", "interview", "org design",
    "succession planning", "vision", "strategy", "roadmap ownership",
    # EM / director role signals
    "leading engineering", "lead engineering", "engineering leadership",
    "people management", "engineering management", "direct report",
    "architecture evaluation", "technical leadership", "technical direction",
    "cross-functional", "operational risk", "performance review",
    # Collaboration, impact, and ownership gaps that need user-provided context
    "collaboration", "cross-team", "collaborated", "architectural decision",
    "system design decision", "quantified", "impact metric", "on-call", "oncall",
    "incident response", "ownership", "led the", "drove", "spearheaded",
    # Product signals
    "roadmap ownership", "user research", "discovery", "a/b test", "north star",
    "product strategy", "user story", "feature adoption", "product metric",
    "prd", "hypothesis", "okr", "go-to-market", "gtm launch",
    # Data / Analytics signals
    "model accuracy", "auc", "f1 score", "experiment", "lift", "significance",
    "dashboard adoption", "business impact of", "cohort", "inference",
    # Marketing signals
    "roas", "cac", "cpl", "campaign roi", "demand generation",
    "pipeline contribution", "brand awareness", "mql", "sql conversion",
    # HR signals
    "time-to-hire", "offer acceptance", "attrition rate", "enps",
    "headcount supported", "hrbp", "succession planning hr",
    # Finance signals
    "cost savings", "budget managed", "forecast accuracy", "ebitda impact",
    "unit economics", "fp&a ownership",
    # Design signals
    "usability metric", "task completion", "design system adoption",
    "accessibility score", "conversion lift from redesign",
}

_SURFACE_SIGNALS = {
    "missing keyword", "typo", "spelling", "abbreviation", "acronym",
    "add keyword", "include term", "mention", "lacks the word", "not present",
    "readability", "shorter", "clearer", "concise", "scannab", "sentence",
    "word-spacing", "runon", "dense", "filler",
}

_NO_CHANGE_PHRASES = (
    "no change needed",
    "no changes needed",
    "no change required",
    "unchanged",
    "looks good",
    "well-optimised",
    "well optimized",
)


def _is_no_change_gap(gap: dict) -> bool:
    """True when the analyzer marked this section as OK — must not appear on Fixes tab."""
    reason = (gap.get("gap_reason") or "").lower().strip()
    if any(phrase in reason for phrase in _NO_CHANGE_PHRASES):
        return True
    instruction = (gap.get("rewrite_instruction") or "").strip()
    return not gap.get("needs_change", True) and not instruction


def _has_surface_signal(gap: dict) -> bool:
    reason = (gap.get("gap_reason") or "").lower()
    instruction = (gap.get("rewrite_instruction") or "").lower()
    keywords = [k.lower() for k in (gap.get("missing_keywords") or [])]
    combined = reason + " " + instruction + " " + " ".join(keywords)
    return any(signal in combined for signal in _SURFACE_SIGNALS)


def _is_actionable_gap(gap: dict) -> bool:
    """
    Gaps that should surface as fix cards on the Fixes tab.

    Excludes 'no change needed' placeholders. Surface quick-wins require an
    explicit surface signal plus a non-empty rewrite instruction.
    """
    if _is_no_change_gap(gap):
        return False
    if gap.get("needs_change"):
        return True
    if (
        gap.get("gap_type") == GapType.SURFACE.value
        and gap.get("auto_apply")
        and _has_surface_signal(gap)
        and (gap.get("rewrite_instruction") or "").strip()
    ):
        return True
    return False


def _build_role_coaching_question(
    role_family: str,
    reason: str,
    ctx,
) -> tuple[str, list[str]]:
    """Role-specific coaching question builder for non-engineering roles."""
    rf = role_family.upper()

    if rf == "PRODUCT":
        if any(w in reason for w in ["metric", "outcome", "retention", "adoption", "dau", "mau"]):
            return (
                "What was the measurable business outcome of this feature or initiative?",
                [
                    "Grew D30 retention from X% to Y% over N months",
                    "Feature drove ₹X Cr incremental GMV in first quarter",
                    "Activation rate improved from X% to Y% post-launch",
                    "Reduced churn by X% through targeted intervention",
                ],
            )
        if any(w in reason for w in ["research", "discovery", "user", "insight"]):
            return (
                "What user research or discovery process did you run before building this?",
                [
                    "Ran N user interviews; identified top 3 unmet needs",
                    "Analysed funnel drop-off data across X cohorts",
                    "Conducted usability tests with N participants; task completion improved X%",
                    "Led discovery sprint with design and engineering to validate hypothesis",
                ],
            )
        if any(w in reason for w in ["roadmap", "ownership", "prioritiz", "strategy"]):
            return (
                "Did you own the roadmap and prioritization for this product area?",
                [
                    "Defined 6-month roadmap for X product area; aligned with business OKRs",
                    "Owned backlog prioritization using RICE/ICE scoring across N features",
                    "Set north star metric and designed experiments to move it",
                    "Drove roadmap alignment with 3 stakeholder groups across engineering, design, and business",
                ],
            )

    if rf == "DATA_ANALYST":
        if any(w in reason for w in ["model", "accuracy", "ml", "prediction", "forecast"]):
            return (
                "What was the accuracy of the model and what business decision did it support?",
                [
                    "Model achieved AUC of X, reducing false positives by Y%",
                    "Churn prediction model identified at-risk segment; retention campaign saved ₹X Cr",
                    "Forecast accuracy improved from X% to Y%; reduced inventory waste by Z%",
                    "Recommendation engine drove X% lift in click-through rate",
                ],
            )
        if any(w in reason for w in ["dashboard", "report", "bi", "analytics"]):
            return (
                "How many teams or users adopted the dashboard, and what decisions did it enable?",
                [
                    "Dashboard used by N teams (X MAU); replaced N ad hoc reports",
                    "Self-serve analytics tooling saved N analyst hours per week",
                    "Report directly informed quarterly business review decision on X",
                ],
            )
        if any(w in reason for w in ["a/b", "experiment", "test", "significance"]):
            return (
                "What was the measured lift from this experiment, and was it statistically significant?",
                [
                    "A/B test showed X% lift in conversion (p < 0.05, N = X users)",
                    "Experiment ran for N days; treatment group showed Y% improvement in retention",
                    "Multi-variate test across 3 variants; identified winning design with X% significance",
                ],
            )

    if rf == "MARKETING":
        if any(w in reason for w in ["roas", "cac", "cpl", "campaign", "paid", "performance"]):
            return (
                "What was the ROAS, CAC, or ROI of this campaign?",
                [
                    "Paid campaign achieved ROAS of X:1 on ₹Y budget",
                    "Reduced CAC from ₹X to ₹Y while maintaining conversion volume",
                    "Lead generation campaign delivered N MQLs at ₹X CPL",
                    "Performance marketing drove ₹X pipeline contribution in Q",
                ],
            )
        if any(w in reason for w in ["brand", "awareness", "content", "organic"]):
            return (
                "What was the measurable brand or content impact — reach, engagement, or conversion?",
                [
                    "Content strategy grew organic traffic by X% YoY",
                    "Brand campaign lifted unaided awareness from X% to Y% (survey, N = X)",
                    "Email nurture sequence achieved X% open rate, Y% conversion to demo",
                ],
            )

    if rf == "HR":
        if any(w in reason for w in ["hire", "recruit", "talent", "acquisition"]):
            return (
                "What were your time-to-hire and offer acceptance metrics?",
                [
                    "Reduced time-to-hire from X to Y days for technical roles",
                    "Achieved X% offer acceptance rate across N hires in FY",
                    "Built campus hiring program; hired N graduates at ₹X cost-per-hire",
                ],
            )
        if any(w in reason for w in ["attrition", "retention", "engagement", "enps"]):
            return (
                "What was the before/after attrition rate or eNPS improvement?",
                [
                    "Voluntary attrition reduced from X% to Y% in 12 months",
                    "eNPS improved from X to Y over 2 survey cycles",
                    "Engagement intervention reduced regrettable attrition by X%",
                ],
            )

    if rf == "FINANCE":
        if any(w in reason for w in ["cost", "saving", "optimization", "reduction"]):
            return (
                "What was the ₹ value of cost savings and what initiative drove it?",
                [
                    "Cost optimisation initiative saved ₹X Cr annually through vendor renegotiation",
                    "Working capital improvement freed ₹X Cr by reducing DSO from X to Y days",
                    "Capex reduction of ₹X Cr by consolidating X infrastructure contracts",
                ],
            )
        if any(w in reason for w in ["budget", "forecast", "fp&a", "p&l"]):
            return (
                "What was the budget size you managed and how accurate were your forecasts?",
                [
                    "Managed ₹X Cr annual opex budget across N business units",
                    "Forecast accuracy improved to X% (from Y%) over 4 quarters",
                    "Led annual operating plan for P&L of ₹X Cr",
                ],
            )

    if rf == "DESIGN":
        if any(w in reason for w in ["redesign", "conversion", "task", "usability", "ux"]):
            return (
                "What was the usability or conversion improvement from this redesign?",
                [
                    "Checkout redesign reduced abandonment from X% to Y%",
                    "Task completion rate improved from X% to Y% post redesign (usability test, N = X)",
                    "Onboarding flow redesign improved activation by X% in 30 days",
                ],
            )
        if any(w in reason for w in ["design system", "component", "token"]):
            return (
                "How many teams or products adopted the design system?",
                [
                    "Design system adopted by N product teams; covers X% of UI surface area",
                    "Reduced design-to-dev handoff time by X% through component library",
                    "System covers N components; accessibility score improved to WCAG AA",
                ],
            )

    # Fallback for unmatched non-engineering signals
    return (
        f"Can you share a specific example with measurable outcome related to: {reason or 'this area'}?",
        [
            "Describe the situation and your specific ownership",
            "Include a quantified outcome (metric, ₹ value, or % improvement)",
            "Note the timeframe and scale involved",
        ],
    )


def _build_coaching_question(gap: dict, role_family: str = "ENGINEERING") -> tuple[str, list[str]]:
    """
    Generate a focused coaching question and hint examples for an evidence gap.
    Maps gap_reason to a targeted question. Zero LLM calls.
    """
    reason = (gap.get("gap_reason") or "").lower()

    # Role-aware dispatch for non-engineering roles
    if role_family.upper() != "ENGINEERING":
        from backend.few_shot_prompts import get_role_context
        try:
            ctx = get_role_context(role_family)
            # Check if any domain vocabulary or metric vocabulary from this role matches the gap
            all_signals = [s.lower() for s in (ctx.domain_vocabulary or []) + (ctx.metric_vocabulary or [])]
            if any(sig in reason for sig in all_signals):
                return _build_role_coaching_question(role_family, reason, ctx)
        except Exception:
            # Fallback to engineering coaching if role context unavailable
            pass

    if any(w in reason for w in ["mentor", "coach", "guidance", "develop"]):
        return (
            "Did you mentor, coach, or develop engineers on your team?",
            [
                "Conducted regular 1:1s with direct reports",
                "Mentored junior engineers through architecture decisions",
                "Helped team members get promoted",
                "Ran knowledge-sharing sessions or tech talks",
                "Built onboarding plans for new hires",
            ],
        )

    if any(w in reason for w in [
        "leading engineering", "lead engineering", "people management",
        "engineering management", "engineering leadership", "direct report",
    ]):
        return (
            "Can you describe your experience leading and managing engineering teams?",
            [
                "Managed a team of N engineers across multiple squads",
                "Led hiring, onboarding, and performance reviews for direct reports",
                "Set team OKRs and tracked delivery against them",
                "Resolved conflicts and unblocked delivery bottlenecks",
                "Built high-performing teams through mentoring and goal-setting",
            ],
        )

    if any(w in reason for w in [
        "architecture evaluation", "technical leadership", "technical direction",
        "operational risk",
    ]):
        return (
            "Can you share how you shaped technical architecture or direction at your org?",
            [
                "Led architecture reviews for major platform redesigns",
                "Defined technical standards and engineering best practices",
                "Evaluated and approved technology choices across teams",
                "Drove technical risk assessment and mitigation strategies",
                "Set the architectural direction for a new product or platform",
            ],
        )

    if any(w in reason for w in ["stakeholder", "executive", "leadership", "communication"]):
        return (
            "Did you present to or work directly with senior leadership or external stakeholders?",
            [
                "Presented quarterly OKR reviews to VP/C-suite",
                "Aligned with cross-functional stakeholders on roadmap",
                "Represented engineering in business planning discussions",
                "Managed escalations with external clients or vendors",
            ],
        )

    if any(w in reason for w in ["p&l", "budget", "cost", "business ownership", "revenue"]):
        return (
            "Did you have ownership of budget, costs, or business outcomes?",
            [
                "Managed team headcount and hiring budget",
                "Made build-vs-buy decisions with cost implications",
                "Tracked and reported engineering cost metrics",
                "Owned cost optimisation initiatives",
            ],
        )

    if any(w in reason for w in ["strategy", "vision", "roadmap", "direction"]):
        return (
            "Did you define or significantly shape the technical strategy or roadmap?",
            [
                "Defined the 6-month or annual engineering roadmap",
                "Proposed and drove adoption of a new technical direction",
                "Led architecture reviews that shaped the product strategy",
            ],
        )

    return (
        f"Can you share a specific example related to: {gap.get('gap_reason', 'this area')}?",
        [
            "Describe a situation where this was relevant",
            "Include the outcome and your specific contribution",
        ],
    )


def _normalize_gap_type(raw: Any) -> str | None:
    """Map LLM gap_type strings to canonical GapType values."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    val = str(raw).lower().strip().replace("-", "_").replace(" ", "_")
    for gap_type in GapType:
        if val == gap_type.value or val == gap_type.name.lower():
            return gap_type.value
    return None


def _apply_gap_type_metadata(gap: dict, gap_type: str, role_family: str = "ENGINEERING") -> dict:
    """Attach coaching/auto_apply fields for a known gap_type without re-classifying."""
    if gap_type == GapType.EVIDENCE.value:
        question, hints = _build_coaching_question(gap, role_family)
        return {
            **gap,
            "gap_type": gap_type,
            "requires_user_input": True,
            "coaching_question": question,
            "coaching_hint": hints,
            "auto_apply": False,
        }

    if gap_type == GapType.SURFACE.value:
        instruction = (gap.get("rewrite_instruction") or "").strip()
        auto_apply = (
            not _is_no_change_gap(gap)
            and (_has_surface_signal(gap) or gap.get("needs_change"))
            and bool(instruction)
        )
        return {
            **gap,
            "gap_type": gap_type,
            "requires_user_input": False,
            "coaching_question": None,
            "coaching_hint": [],
            "auto_apply": auto_apply,
        }

    return {
        **gap,
        "gap_type": GapType.STRUCTURAL.value,
        "requires_user_input": False,
        "coaching_question": None,
        "coaching_hint": [],
        "auto_apply": False,
    }


def classify_gap(gap: dict, resume_text: str = "", role_family: str = "ENGINEERING") -> dict:
    """
    Classify a gap as surface / structural / evidence.
    Pure heuristic — zero LLM calls.

    When the LLM already set gap_type, trust it and only attach UX metadata.
    Heuristics run only when gap_type is absent or null.

    Args:
        gap: Section gap dict from Agent 3 enrichment.
        resume_text: Full resume text (reserved for future heuristics).
        role_family: Role family (ENGINEERING, PRODUCT, etc.) for role-aware coaching.

    Returns:
        Gap dict with gap_type, coaching fields, and auto_apply set.
    """
    del resume_text  # reserved; classification is text-in-gap only today

    llm_type = _normalize_gap_type(gap.get("gap_type"))
    if llm_type:
        return _apply_gap_type_metadata(gap, llm_type, role_family)

    reason = (gap.get("gap_reason") or "").lower()
    instruction = (gap.get("rewrite_instruction") or "").lower()
    keywords = [k.lower() for k in (gap.get("missing_keywords") or [])]
    combined = reason + " " + instruction + " " + " ".join(keywords)

    if any(signal in combined for signal in _EVIDENCE_SIGNALS):
        return _apply_gap_type_metadata(gap, GapType.EVIDENCE.value, role_family)

    if _is_no_change_gap(gap):
        return _apply_gap_type_metadata(gap, GapType.SURFACE.value, role_family)

    if _has_surface_signal(gap) and (gap.get("needs_change") or instruction.strip()):
        gap_with_surface = _apply_gap_type_metadata(gap, GapType.SURFACE.value, role_family)
        gap_with_surface["auto_apply"] = True
        return gap_with_surface

    return _apply_gap_type_metadata(gap, GapType.STRUCTURAL.value, role_family)


def classify_section_gaps(gaps: list[dict], resume_text: str = "", role_family: str = "ENGINEERING") -> list[dict]:
    """Run classify_gap over every section gap and its sub_changes."""
    classified = []
    for gap in gaps:
        classified_gap = classify_gap(gap, resume_text, role_family)
        sub_changes = gap.get("sub_changes") or []
        if sub_changes:
            classified_gap["sub_changes"] = [
                classify_gap(sub, resume_text, role_family) for sub in sub_changes
            ]
        classified.append(classified_gap)
    return classified


def reclassify_gaps_for_resume_only(gaps: list[dict]) -> list[dict]:
    """
    In resume-only mode, A4 rewrites address metric/improvement gaps.

    Heuristic evidence classification (quantified, impact, etc.) should render
    as structural patches, not coaching cards.
    """
    reclassified: list[dict] = []
    for gap in gaps:
        updated = dict(gap)
        if (
            updated.get("gap_type") == GapType.EVIDENCE.value
            and (updated.get("rewrite_instruction") or "").strip()
        ):
            updated = _apply_gap_type_metadata(updated, GapType.STRUCTURAL.value)

        sub_changes = gap.get("sub_changes") or []
        if sub_changes:
            new_subs: list[dict] = []
            for sub in sub_changes:
                sub_copy = dict(sub)
                if (
                    sub_copy.get("gap_type") == GapType.EVIDENCE.value
                    and (sub_copy.get("rewrite_instruction") or "").strip()
                ):
                    sub_copy = _apply_gap_type_metadata(
                        sub_copy, GapType.STRUCTURAL.value
                    )
                new_subs.append(sub_copy)
            updated["sub_changes"] = new_subs
        reclassified.append(updated)
    return reclassified


_GAP_TYPE_ORDER: dict[str, int] = {
    GapType.EVIDENCE.value: 0,
    GapType.STRUCTURAL.value: 1,
    GapType.SURFACE.value: 2,
}


def _include_in_priority_fixes(gap_entry: dict) -> bool:
    """Include only gaps that need a real user-visible fix."""
    return _is_actionable_gap(gap_entry)


def _priority_fix_location_key(fix: dict) -> str:
    """One fix card per section + sub_entry (not per missing keyword)."""
    section = str(fix.get("section") or "").lower().strip()
    entry_id = str(fix.get("entry_id") or fix.get("sub_id") or "").strip()
    if entry_id:
        return f"{section}|{entry_id}"
    sub = str(fix.get("sub_label") or "").lower().strip()
    return f"{section}|{sub or '__section__'}"


def _merge_priority_fix(existing: dict, incoming: dict) -> dict:
    """Merge duplicate location fixes — combine keywords, keep strongest gap_type."""
    merged = dict(existing)
    merged_keywords = list(dict.fromkeys(
        (existing.get("missing_keywords") or [])
        + (incoming.get("missing_keywords") or [])
    ))
    merged["missing_keywords"] = merged_keywords

    existing_type = existing.get("gap_type", GapType.STRUCTURAL.value)
    incoming_type = incoming.get("gap_type", GapType.STRUCTURAL.value)
    if _GAP_TYPE_ORDER.get(incoming_type, 1) < _GAP_TYPE_ORDER.get(existing_type, 1):
        merged["gap_type"] = incoming_type
        merged["requires_user_input"] = incoming.get("requires_user_input", False)
        merged["coaching_question"] = incoming.get("coaching_question")
        merged["coaching_hint"] = incoming.get("coaching_hint") or []
        merged["auto_apply"] = incoming.get("auto_apply", False)

    if incoming.get("rewrite_instruction") and len(str(incoming["rewrite_instruction"])) > len(
        str(existing.get("rewrite_instruction") or "")
    ):
        merged["rewrite_instruction"] = incoming["rewrite_instruction"]

    if not str(existing.get("original_text") or "").strip():
        merged["original_text"] = incoming.get("original_text", "")

    return merged


def _dedupe_priority_fixes(fixes: list[dict]) -> list[dict]:
    """
    Collapse multiple sub_changes for the same experience entry into one fix card.

    A3 often emits one sub_change per missing keyword on the same role block;
    without dedupe the Fixes tab shows identical patches 3–4 times.
    """
    merged_map: dict[str, dict] = {}
    order: list[str] = []
    for fix in fixes:
        key = _priority_fix_location_key(fix)
        if key not in merged_map:
            merged_map[key] = dict(fix)
            order.append(key)
        else:
            merged_map[key] = _merge_priority_fix(merged_map[key], fix)
    return [merged_map[k] for k in order]


def priority_fixes_from_gaps(section_gaps: list[dict]) -> list[dict]:
    """
    Build structured priority_fixes for the Fixes tab from classified section gaps.

    Expands sub_changes into individual fix cards so each company/role block in
    experience gets its own card. Sorts by gap_type: evidence → structural → surface.
    """
    fixes: list[dict] = []
    for gap in section_gaps:
        if not _include_in_priority_fixes(gap):
            continue
        sub_changes = gap.get("sub_changes") or []
        if sub_changes:
            for sub in sub_changes:
                if not _include_in_priority_fixes(sub):
                    continue
                entry_id = sub.get("entry_id") or sub.get("sub_id") or ""
                if not entry_id and sub.get("sub_label"):
                    from backend.utils.entry_id import derive_entry_id
                    entry_id = derive_entry_id(sub.get("sub_label"))
                fixes.append({
                    "section": gap.get("section", ""),
                    "gap_reason": sub.get("gap_reason") or gap.get("gap_reason", ""),
                    "rewrite_instruction": (
                        sub.get("rewrite_instruction") or gap.get("rewrite_instruction", "")
                    ),
                    "missing_keywords": (
                        sub.get("missing_keywords") or gap.get("missing_keywords") or []
                    ),
                    "needs_change": True,
                    "gap_type": sub.get("gap_type") or gap.get("gap_type", GapType.STRUCTURAL.value),
                    "requires_user_input": sub.get("requires_user_input", False),
                    "coaching_question": sub.get("coaching_question"),
                    "coaching_hint": sub.get("coaching_hint") or [],
                    "auto_apply": sub.get("auto_apply", False),
                    "sub_label": sub.get("sub_label", ""),
                    "entry_id": entry_id,
                    "original_text": sub.get("original_text", ""),
                    "patch_text": sub.get("rewrite_instruction") or sub.get("patch_text", ""),
                })
        else:
            fixes.append({
                "section": gap.get("section", ""),
                "gap_reason": gap.get("gap_reason", ""),
                "rewrite_instruction": gap.get("rewrite_instruction", ""),
                "missing_keywords": gap.get("missing_keywords") or [],
                "needs_change": True,
                "gap_type": gap.get("gap_type", GapType.STRUCTURAL.value),
                "requires_user_input": gap.get("requires_user_input", False),
                "coaching_question": gap.get("coaching_question"),
                "coaching_hint": gap.get("coaching_hint") or [],
                "auto_apply": gap.get("auto_apply", False),
                "sub_label": None,
                "original_text": gap.get("original_content", ""),
                "patch_text": gap.get("rewrite_instruction", ""),
            })
    fixes = _dedupe_priority_fixes(fixes)
    fixes.sort(key=lambda f: _GAP_TYPE_ORDER.get(f.get("gap_type", GapType.STRUCTURAL.value), 1))
    return fixes[:12]


def _infer_section_from_text(text: str) -> str:
    """Route free-form issue text to a canonical resume section."""
    lower = (text or "").lower()
    if any(w in lower for w in ("experience", "bullet", "role")):
        return "experience"
    if any(w in lower for w in ("skill", "keyword")):
        return "skills"
    if any(w in lower for w in ("summary", "objective")):
        return "summary"
    if "education" in lower:
        return "education"
    if "certification" in lower:
        return "certifications"
    return "experience"


def _infer_gap_type_from_text(text: str) -> str:
    """Classify free-form fix text into surface / structural / evidence."""
    lower = (text or "").lower()
    if re.search(
        r"readability|shorter|clearer|concise|scannab|dense|sentence|word.?spacing|runon|filler",
        lower,
    ):
        return GapType.SURFACE.value
    if re.search(r"missing keyword|typo|spelling|add keyword|include term", lower):
        return GapType.SURFACE.value
    if (
        re.search(
            r"mentor|evidence|collaborat|architectur|roadmap|ownership|quantif|cross-team|stakeholder",
            lower,
        )
        and re.search(r"no mention|lacks|missing|share a specific|user input", lower)
    ):
        return GapType.EVIDENCE.value
    return GapType.STRUCTURAL.value


def _compact_alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _extract_company_from_weakness(weakness: str) -> str:
    """Company/role head from A1 weakness format: 'Flipkart EM bullets …'."""
    head = (weakness.split("→")[0] if "→" in weakness else weakness).strip()
    match = re.match(
        r"^([A-Za-z][A-Za-z0-9\s.&-]{1,48}?)"
        r"(?:\s+(?:EM|role|bullets|bullet|section|lacks|lack|missing|needs))",
        head,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    words = head.split()
    return " ".join(words[: min(3, len(words))])


def _label_matches_company(label: str, company: str) -> bool:
    label_lower = (label or "").lower()
    company_lower = (company or "").lower().strip()
    if not company_lower or len(company_lower) < 2:
        return False
    if company_lower in label_lower:
        return True
    first_word = company_lower.split()[0] if company_lower else ""
    if len(first_word) > 2 and first_word in label_lower:
        return True
    cl = _compact_alnum(label)
    cc = _compact_alnum(company)
    return (cc and cc in cl) or (cl and cl in cc)


def _resolve_verbatim_for_entry(
    resume_sections: dict | None,
    section: str,
    entry_id: str,
    sub_label: str | None,
) -> str:
    """Return verbatim sub_entry text when entry_id or sub_label matches."""
    sec_obj = (resume_sections or {}).get(section) or {}
    sub_entries = (
        list(sec_obj.sub_entries)
        if hasattr(sec_obj, "sub_entries")
        else (sec_obj.get("sub_entries") or [])
    )
    if entry_id:
        for entry in sub_entries:
            eid = entry.entry_id if hasattr(entry, "entry_id") else entry.get("entry_id", "")
            if eid and eid == entry_id:
                text = (
                    entry.verbatim_text if hasattr(entry, "verbatim_text")
                    else entry.get("verbatim_text", "")
                )
                return (text or "").strip()
    if sub_label:
        for entry in sub_entries:
            label = entry.label if hasattr(entry, "label") else entry.get("label", "")
            if label and _label_matches_company(label, sub_label):
                text = (
                    entry.verbatim_text if hasattr(entry, "verbatim_text")
                    else entry.get("verbatim_text", "")
                )
                return (text or "").strip()
    return ""


def _match_eval_change(text: str, eval_changes: list[dict]) -> dict | None:
    """
    Match a weakness or gap_reason string to an eval-mode ActionableChange.

    Uses company token overlap on sub_location/why plus head-token overlap.
    """
    if not text or not eval_changes:
        return None
    head = (text.split("→")[0] if "→" in text else text).strip().lower()
    company = _extract_company_from_weakness(text).lower()
    head_tokens = {t for t in re.split(r"\W+", head) if len(t) > 3}

    best: dict | None = None
    best_score = 0
    for change in eval_changes:
        loc = change.get("location") or {}
        sub_loc = (loc.get("sub_location") or "").lower()
        why = (change.get("why") or "").lower()
        score = 0
        if company and len(company) > 2:
            if company in sub_loc:
                score += 4
            if company in why:
                score += 3
            first = company.split()[0]
            if len(first) > 2 and (first in sub_loc or first in why):
                score += 2
        pool_tokens = {
            t for t in re.split(r"\W+", sub_loc + " " + why) if len(t) > 3
        }
        overlap = len(head_tokens & pool_tokens)
        if overlap >= 2:
            score += overlap
        elif overlap == 1:
            score += 1
        if score > best_score:
            best_score, best = score, change
    return best if best_score >= 3 else None


def enrich_priority_fixes_from_eval_changes(
    fixes: list[dict],
    eval_changes: list[dict],
    resume_sections: dict | None = None,
) -> list[dict]:
    """
    Upgrade priority_fixes with eval ActionableChange original_text + suggested_text.

    Eval mode produces paste-ready rewrites; this turns overview-style cards into
    structural patches the Fixes tab can apply in one click.
    """
    if not eval_changes:
        return fixes

    enriched: list[dict] = []
    used_change_ids: set[int] = set()

    for fix in fixes:
        updated = dict(fix)
        matched = _match_eval_change(
            updated.get("gap_reason") or "",
            eval_changes,
        )
        if not matched:
            matched = _match_eval_change(
                updated.get("rewrite_instruction") or "",
                eval_changes,
            )
        if matched:
            change_id = matched.get("change_id")
            if change_id is not None:
                used_change_ids.add(int(change_id))
            suggested = (matched.get("suggested_text") or "").strip()
            original = (matched.get("original_text") or "").strip()
            loc = matched.get("location") or {}
            if suggested and len(suggested) > 50:
                updated["rewrite_instruction"] = suggested
                updated["patch_text"] = suggested
            if original:
                updated["original_text"] = original
            if original and suggested and len(suggested) > 50:
                updated = _apply_gap_type_metadata(updated, GapType.STRUCTURAL.value)
            elif (
                (updated.get("rewrite_instruction") or "").strip().casefold()
                == (updated.get("gap_reason") or "").strip().casefold()
            ):
                updated = _apply_gap_type_metadata(updated, GapType.EVIDENCE.value)
            if loc.get("section") and not updated.get("section"):
                updated["section"] = loc["section"]
            if loc.get("sub_location") and not updated.get("sub_label"):
                updated["sub_label"] = loc["sub_location"]
        enriched.append(updated)

    existing_reason_heads = {
        (f.get("gap_reason") or "").lower()[:60] for f in enriched
    }
    for change in eval_changes:
        change_id = change.get("change_id")
        if change_id is not None and int(change_id) in used_change_ids:
            continue
        why = (change.get("why") or "").strip()
        suggested = (change.get("suggested_text") or "").strip()
        original = (change.get("original_text") or "").strip()
        if not why or not suggested or len(suggested) <= 50:
            continue
        if any(why.lower()[:60] in head or head in why.lower()[:60] for head in existing_reason_heads):
            continue
        loc = change.get("location") or {}
        section = loc.get("section") or _infer_section_from_text(why)
        sub_label = loc.get("sub_location") or None
        entry_id = ""
        if sub_label and resume_sections:
            _, entry_id = _resolve_sub_label_for_weakness(why, resume_sections)
        enriched.append({
            "section": section,
            "gap_reason": why,
            "rewrite_instruction": suggested,
            "missing_keywords": change.get("keywords_added") or [],
            "needs_change": True,
            "gap_type": GapType.STRUCTURAL.value,
            "requires_user_input": False,
            "coaching_question": None,
            "coaching_hint": [],
            "auto_apply": False,
            "sub_label": sub_label,
            "entry_id": entry_id or None,
            "original_text": original,
            "patch_text": suggested,
        })
        existing_reason_heads.add(why.lower()[:60])

    return _dedupe_priority_fixes(enriched)[:12]


def _resolve_sub_label_for_weakness(
    weakness: str,
    resume_sections: dict | None,
) -> tuple[str | None, str]:
    """
    Match a weakness to an A1 sub_entry label and entry_id.

    Returns:
        (sub_label, entry_id) — entry_id empty when no sub_entry match.
    """
    company = _extract_company_from_weakness(weakness)
    section = _infer_section_from_text(weakness.split("→")[0] if "→" in weakness else weakness)
    sec_obj = (resume_sections or {}).get(section) or {}
    sub_entries = (
        list(sec_obj.sub_entries)
        if hasattr(sec_obj, "sub_entries")
        else (sec_obj.get("sub_entries") or [])
    )
    for entry in sub_entries:
        label = entry.label if hasattr(entry, "label") else entry.get("label", "")
        entry_id = entry.entry_id if hasattr(entry, "entry_id") else entry.get("entry_id", "")
        if label and _label_matches_company(label, company):
            if not entry_id and label:
                from backend.utils.entry_id import derive_entry_id
                entry_id = derive_entry_id(label)
            return label, entry_id or ""
    return (company or None), ""


def _weakness_covered_by_fix(weakness: str, fix: dict) -> bool:
    """True when an existing priority_fix already addresses this overview string."""
    w = (weakness or "").lower().strip()
    reason = (fix.get("gap_reason") or "").lower().strip()
    instruction = (fix.get("rewrite_instruction") or "").lower().strip()
    if not w:
        return False
    if reason == w or instruction == w:
        return True
    w_head = w[:55]
    if w_head in reason or reason[:55] in w:
        return True
    company = _extract_company_from_weakness(weakness).lower()
    if len(company) > 2:
        if company in reason or company in instruction:
            return True
        sub_label = (fix.get("sub_label") or "").lower()
        first_word = company.split()[0] if company else ""
        if first_word and first_word in sub_label:
            return True
        entry_id = (fix.get("entry_id") or "").lower()
        if company.replace(" ", "_") in entry_id or first_word in entry_id:
            return True
    return False


def _build_overview_weakness_fix(
    weakness: str,
    resume_only_mode: bool,
    resume_sections: dict | None,
    eval_changes: list[dict] | None = None,
) -> dict:
    """Build a structured priority_fix from an A1 weakness or improvement_area."""
    parts = weakness.split("→")
    gap_reason = (parts[0] if parts else weakness).strip()
    rewrite_instruction = (parts[1] if len(parts) > 1 else parts[0]).strip() if parts else weakness
    section = _infer_section_from_text(gap_reason)
    sub_label, entry_id = _resolve_sub_label_for_weakness(weakness, resume_sections)
    original_text = _resolve_verbatim_for_entry(
        resume_sections, section, entry_id, sub_label
    )

    matched_change = _match_eval_change(weakness, eval_changes or [])
    if matched_change:
        suggested = (matched_change.get("suggested_text") or "").strip()
        change_original = (matched_change.get("original_text") or "").strip()
        if suggested and len(suggested) > 50:
            rewrite_instruction = suggested
        if change_original:
            original_text = change_original
        loc = matched_change.get("location") or {}
        if loc.get("sub_location"):
            sub_label = loc["sub_location"]

    gap_type = GapType.STRUCTURAL.value if resume_only_mode else GapType.EVIDENCE.value
    is_coaching = not resume_only_mode and gap_type == GapType.EVIDENCE.value

    # No distinct instruction after → split — coaching, not a broken structural card.
    if rewrite_instruction.strip().casefold() == gap_reason.strip().casefold():
        gap_type = GapType.EVIDENCE.value
        is_coaching = True
    elif (
        original_text
        and rewrite_instruction.strip()
        and len(rewrite_instruction.strip()) > 50
        and matched_change
    ):
        gap_type = GapType.STRUCTURAL.value
        is_coaching = False
    elif (
        resume_only_mode
        and _infer_gap_type_from_text(gap_reason) == GapType.EVIDENCE.value
        and len(rewrite_instruction.strip()) <= 80
    ):
        gap_type = GapType.EVIDENCE.value
        is_coaching = True

    coaching_question: str | None = None
    coaching_hint: list[str] = []
    if is_coaching:
        coaching_question, coaching_hint = _build_coaching_question(
            {"gap_reason": gap_reason}
        )

    fix = {
        "section": section,
        "gap_reason": gap_reason,
        "rewrite_instruction": rewrite_instruction,
        "missing_keywords": [],
        "needs_change": True,
        "gap_type": gap_type,
        "requires_user_input": is_coaching,
        "coaching_question": coaching_question,
        "coaching_hint": coaching_hint,
        "auto_apply": False,
        "sub_label": sub_label,
        "entry_id": entry_id or None,
        "original_text": original_text,
        "patch_text": rewrite_instruction,
    }
    if gap_type == GapType.EVIDENCE.value:
        return _apply_gap_type_metadata(fix, GapType.EVIDENCE.value)
    if gap_type == GapType.STRUCTURAL.value and original_text and len(rewrite_instruction) > 50:
        return _apply_gap_type_metadata(fix, GapType.STRUCTURAL.value)
    return fix


def _merge_overview_backfill(
    fixes: list[dict],
    overview_strings: list[str],
    resume_sections: dict | None,
    resume_only_mode: bool,
    eval_changes: list[dict] | None = None,
) -> list[dict]:
    """Resume-only: guarantee every Overview weakness/improvement_area has a fix card."""
    if not resume_only_mode or not overview_strings:
        return fixes
    merged = list(fixes)
    seen: set[str] = set()
    for raw in overview_strings:
        weakness = str(raw).strip()
        if not weakness or weakness in seen:
            continue
        seen.add(weakness)
        if any(_weakness_covered_by_fix(weakness, f) for f in merged):
            continue
        merged.append(
            _build_overview_weakness_fix(
                weakness,
                resume_only_mode,
                resume_sections,
                eval_changes=eval_changes,
            )
        )
    return merged


def _merge_ats_issue_fixes(fixes: list[dict], ats_issues: list[str]) -> list[dict]:
    """Add ATS issues not already represented in priority_fixes."""
    if not ats_issues:
        return fixes
    existing_heads = {
        (f.get("gap_reason") or "").lower()[:50]
        for f in fixes
        if f.get("gap_reason")
    }
    merged = list(fixes)
    for issue in ats_issues:
        text = str(issue).strip()
        if not text:
            continue
        head = text.lower()[:50]
        if head in existing_heads:
            continue
        gap_type = _infer_gap_type_from_text(text)
        merged.append({
            "section": _infer_section_from_text(text),
            "gap_reason": text,
            "rewrite_instruction": text,
            "missing_keywords": [],
            "needs_change": True,
            "gap_type": gap_type,
            "requires_user_input": False,
            "coaching_question": None,
            "coaching_hint": [],
            "auto_apply": gap_type == GapType.SURFACE.value,
            "sub_label": None,
            "entry_id": None,
            "original_text": "",
            "patch_text": text,
        })
        existing_heads.add(head)
    return merged


def build_complete_priority_fixes(
    section_gaps: list[dict],
    *,
    ats_issues: list[str] | None = None,
    overview_strings: list[str] | None = None,
    resume_only_mode: bool = False,
    resume_sections: dict | None = None,
    eval_changes: list[dict] | None = None,
) -> list[dict]:
    """
    Single authoritative priority_fixes builder for the Fixes tab.

    Expands classified section_gaps, backfills resume-only overview items,
    and merges unaddressed ATS issues. Frontend reads only this list (+ patches).
    """
    fixes = priority_fixes_from_gaps(section_gaps)

    if overview_strings and not resume_only_mode:
        overview_lower = [s.lower() for s in overview_strings]
        fixes = [
            f for f in fixes
            if not any(
                (f.get("gap_reason") or "").lower()[:60] in ov
                for ov in overview_lower
            )
        ]

    fixes = _merge_overview_backfill(
        fixes,
        overview_strings or [],
        resume_sections,
        resume_only_mode,
        eval_changes=eval_changes,
    )
    fixes = _merge_ats_issue_fixes(fixes, ats_issues or [])
    if eval_changes:
        fixes = enrich_priority_fixes_from_eval_changes(
            fixes, eval_changes, resume_sections
        )
    fixes = _dedupe_priority_fixes(fixes)
    fixes.sort(key=lambda f: _GAP_TYPE_ORDER.get(f.get("gap_type", GapType.STRUCTURAL.value), 1))
    return fixes[:12]


def _fuzzy_match_label(sub_label: str, valid_labels: set[str]) -> str | None:
    """
    Match an LLM-invented sub_label to the closest known A1/sectioner label.

    Uses exact match, case-insensitive containment, then token overlap (≥2 tokens).
    """
    if not sub_label or not valid_labels:
        return None
    if sub_label in valid_labels:
        return sub_label
    lower_sub = sub_label.lower()
    for label in valid_labels:
        lower_entry = label.lower()
        if lower_sub in lower_entry or lower_entry in lower_sub:
            return label
    sub_tokens = {t for t in re.split(r"\W+", lower_sub) if len(t) > 3}
    if not sub_tokens:
        return None
    best_label: str | None = None
    best_score = 0
    for label in valid_labels:
        entry_tokens = {t for t in re.split(r"\W+", label.lower()) if len(t) > 3}
        score = len(sub_tokens & entry_tokens)
        if score > best_score:
            best_score, best_label = score, label
    if best_score >= 2 and best_label:
        return best_label
    return None


# Built-in semantic equivalents for phantom-gap suppression (qualified matches).
_BUILTIN_EQUIVALENTS: dict[str, list[str]] = {
    "mlops": ["mlflow", "kubeflow", "sagemaker", "vertex", "model monitoring", "ci/cd", "experiment tracking"],
    "kubernetes": ["k8s", "container orchestration", "eks", "gke", "docker swarm"],
    "kafka": ["event-driven", "streaming", "message queue", "pulsar", "kinesis", "pub/sub"],
    "tableau": ["power bi", "looker", "metabase", "bi tool", "dashboard"],
    "power bi": ["tableau", "looker", "metabase", "bi tool", "dashboard"],
    "microservices": ["distributed services", "service-oriented", "soa"],
    "terraform": ["infrastructure as code", "iac", "cloudformation", "pulumi"],
    "redis": ["caching", "cache layer", "memcached"],
    "architecture": ["system design", "architectural", "technical design"],
}


def _resume_text_blob(resume_analysis: dict, resume_text: str) -> str:
    """Combined lowercase resume text for keyword presence checks."""
    parts = [resume_text or ""]
    for sec in (resume_analysis or {}).get("resume_sections") or {}:
        if isinstance(sec, dict):
            parts.append(sec.get("full_text") or "")
            for sub in sec.get("sub_entries") or []:
                if isinstance(sub, dict):
                    parts.append(sub.get("verbatim_text") or "")
    parts.append(" ".join(str(t) for t in (resume_analysis or {}).get("tech_stack") or []))
    return " ".join(parts).lower()


def _equivalent_terms(keyword: str, semantic_map: dict) -> set[str]:
    """Expand a missing keyword with JD semantic map + built-in equivalents."""
    kw = keyword.lower().strip()
    terms = {kw}
    for jd_term, equivalents in (semantic_map or {}).items():
        jd_lower = str(jd_term).lower()
        equiv_lower = [str(e).lower() for e in (equivalents or [])]
        if kw == jd_lower or kw in equiv_lower:
            terms.add(jd_lower)
            terms.update(equiv_lower)
    for canonical, aliases in _BUILTIN_EQUIVALENTS.items():
        pool = {canonical, *aliases}
        if kw in pool:
            terms.update(pool)
    return terms


def _keyword_covered_in_resume(keyword: str, resume_blob: str, semantic_map: dict) -> bool:
    """True when keyword or a semantic equivalent appears in resume text."""
    if not keyword.strip():
        return True
    for term in _equivalent_terms(keyword, semantic_map):
        if term and term in resume_blob:
            return True
    return False


def _suppress_cross_entry_duplicate_gaps(
    section_gaps: list[dict],
    resume_sections: dict | None = None,
) -> list[dict]:
    """
    For experience section, suppress sub_changes when the same gap is already
    addressed in a stronger/earlier entry.

    Example: If BT and SmartViz both lack "team leadership clarity" but Flipkart
    demonstrates it strongly, suppress the gap for BT and SmartViz (weaker entries).

    This catches cross-entry duplication that the LLM may create despite the
    "holistic JD matching" rule.
    """
    # Note: resume_sections is not actually used in this logic; it's here for symmetry
    # with other post-LLM filters. The suppression is based on the order of sub_changes,
    # not on their content.

    filtered: list[dict] = []
    for gap in section_gaps:
        section = (gap.get("section") or "").lower()
        if section != "experience":
            filtered.append(gap)
            continue

        gap = dict(gap)
        sub_changes = gap.get("sub_changes") or []
        if not sub_changes:
            filtered.append(gap)
            continue

        # Track which gap_reasons have been seen across all entries
        # Group by gap_reason (case-insensitive, e.g., "lacks team leadership", "missing metrics")
        gap_reason_to_entries: dict[str, list[str]] = {}
        for sub in sub_changes:
            if not sub.get("needs_change"):
                continue
            reason_raw = sub.get("gap_reason") or ""
            reason = reason_raw.lower().strip()
            if reason:
                if reason not in gap_reason_to_entries:
                    gap_reason_to_entries[reason] = []
                gap_reason_to_entries[reason].append(sub.get("sub_label", ""))

        # For each gap_reason appearing in multiple entries, keep only the first (strongest)
        # and suppress the rest
        suppressed_labels_for_reason: dict[str, set[str]] = {}
        for reason, labels in gap_reason_to_entries.items():
            if len(labels) > 1:
                # Keep first, suppress rest
                suppressed_labels_for_reason[reason] = set(labels[1:])
                logging.debug(
                    "GapAnalyzer: will suppress %d duplicates for reason '%s'",
                    len(labels) - 1, reason[:60]
                )

        # Filter sub_changes
        filtered_subs = []
        for sub in sub_changes:
            reason = (sub.get("gap_reason") or "").lower().strip()
            sub_label = sub.get("sub_label", "")

            if reason in suppressed_labels_for_reason and sub_label in suppressed_labels_for_reason[reason]:
                logging.info(
                    "GapAnalyzer: cross-entry duplicate gap suppressed: %s (reason: %s) — "
                    "already addressed in another entry",
                    sub_label, reason[:60],
                )
                sub["needs_change"] = False
                sub["gap_reason"] = "No change needed — gap already addressed in another entry"
                sub["rewrite_instruction"] = ""

            filtered_subs.append(sub)

        gap["sub_changes"] = filtered_subs
        filtered.append(gap)

    return filtered


def _apply_phantom_gap_filter(
    section_gaps: list[dict],
    resume_analysis: dict,
    jd_analysis: dict,
    resume_text: str,
) -> list[dict]:
    """
    On qualified matches, suppress experience gaps whose missing keywords
    are already covered by semantic equivalents in the resume.

    Also suppresses gaps when a sub_change's requirement is demonstrated
    ANYWHERE else in the resume (holistic matching).
    """
    role_fit = compute_role_fit(resume_analysis or {}, jd_analysis or {}, {"section_gaps": section_gaps})
    if role_fit.get("fitness") != "qualified":
        return section_gaps

    resume_blob = _resume_text_blob(resume_analysis or {}, resume_text)
    semantic_map = (jd_analysis or {}).get("semantic_skill_map") or {}
    filtered: list[dict] = []

    for gap in section_gaps:
        gap = dict(gap)
        if not gap.get("needs_change"):
            filtered.append(gap)
            continue

        section = (gap.get("section") or "").lower()

        # For experience section, also check sub_changes for global coverage
        if section == "experience":
            sub_changes = gap.get("sub_changes") or []
            filtered_subs = []

            for sub in sub_changes:
                sub = dict(sub)
                if not sub.get("needs_change"):
                    filtered_subs.append(sub)
                    continue

                # Check if this sub_change's missing keywords appear anywhere in resume
                missing = [str(k) for k in (sub.get("missing_keywords") or []) if str(k).strip()]
                reason = (sub.get("gap_reason") or "").lower()

                # If this requirement is already shown globally, suppress it for this entry
                if missing and all(_keyword_covered_in_resume(kw, resume_blob, semantic_map) for kw in missing):
                    logging.info(
                        "GapAnalyzer: cross-entry gap suppressed (global coverage): %s → %s",
                        sub.get("sub_label", "")[:40],
                        reason[:50],
                    )
                    sub["needs_change"] = False
                    sub["gap_reason"] = f"No change needed — {reason.split(':')[0]} already demonstrated in another role"
                    sub["rewrite_instruction"] = ""
                    sub["missing_keywords"] = []

                filtered_subs.append(sub)

            gap["sub_changes"] = filtered_subs
            filtered.append(gap)
            continue

        if section != "experience":
            filtered.append(gap)
            continue

        missing = [str(k) for k in (gap.get("missing_keywords") or []) if str(k).strip()]
        if missing and all(_keyword_covered_in_resume(kw, resume_blob, semantic_map) for kw in missing):
            logging.info(
                "GapAnalyzer: phantom experience gap suppressed (qualified match): %s",
                gap.get("gap_reason", "")[:80],
            )
            gap["needs_change"] = False
            gap["gap_reason"] = "No change needed — skill covered under equivalent wording"
            gap["rewrite_instruction"] = ""
            gap["missing_keywords"] = []
            gap["sub_changes"] = []

        filtered.append(gap)

    return filtered


_MIN_MISMATCH_GAPS = 5


def _count_actionable_gaps(section_gaps: list[dict]) -> int:
    """Count section gaps that need a real user-visible fix."""
    count = 0
    for gap in section_gaps:
        if gap.get("needs_change"):
            count += 1
            continue
        for sub in gap.get("sub_changes") or []:
            if isinstance(sub, dict) and sub.get("needs_change"):
                count += 1
    return count


def _ensure_minimum_gap_floor(
    section_gaps: list[dict],
    resume_analysis: dict,
    jd_analysis: dict,
) -> list[dict]:
    """
    Enforce minimum gap count for underqualified/stretch role fits.

    If the LLM returns too few gaps on a bad-fit pair, inject a catch-all
    seniority/domain gap so users are not misled by an overly optimistic report.
    """
    role_fit = compute_role_fit(resume_analysis or {}, jd_analysis or {}, {"section_gaps": section_gaps})
    fitness = role_fit.get("fitness")
    if fitness not in ("underqualified", "stretch"):
        return section_gaps

    if _count_actionable_gaps(section_gaps) >= _MIN_MISMATCH_GAPS:
        return section_gaps

    role_title = str((jd_analysis or {}).get("role_title") or "target role").strip()
    candidate_years = int(
        (resume_analysis or {}).get("experience_years")
        or (resume_analysis or {}).get("total_years")
        or 0
    )
    jd_min = int((jd_analysis or {}).get("min_years_required") or 0)
    exp_gap = role_fit.get("experience_gap", max(0, jd_min - candidate_years))

    catch_all = {
        "section": "experience",
        "needs_change": True,
        "gap_type": GapType.EVIDENCE.value,
        "gap_reason": (
            f"Overall seniority and domain fit gap: resume profile does not meet "
            f"{role_title} requirements ({candidate_years}y experience vs {jd_min}+y required, "
            f"fitness={fitness})"
        ),
        "missing_keywords": (jd_analysis or {}).get("must_have_skills", [])[:5],
        "rewrite_instruction": (
            f"Address the overall qualification gap for {role_title}: "
            f"candidate has {candidate_years} years vs {jd_min}+ required "
            f"({exp_gap} year shortfall). Highlight transferable skills or consider "
            "a more appropriate target role."
        ),
        "present_in_resume": True,
        "sub_changes": [],
    }

    logging.warning(
        "GapAnalyzer: %d actionable gaps on %s match — injecting catch-all seniority gap",
        _count_actionable_gaps(section_gaps),
        fitness,
    )
    return section_gaps + [catch_all]


class GapAnalyzerAgent(BaseAgent):
    """
    Agent 3 — Gap Analyzer.

    Compares structured resume data (from Agent 1) against JD intelligence
    (from Agent 2) to produce a prioritized section gap list for Agent 4 (Rewriter).

    Runs sequentially after Agents 1 and 2. Cannot run without both upstream outputs.
    Uses gpt-4o-mini via OpenAI SDK. Returns GapAnalyzerOutput or DetailedEvalOutput as dict.

    Invariants:
        - Input must contain validated Agent 1 and Agent 2 output dicts
        - jd_match_score_before must be 0–100 (enforced by Pydantic)
        - section_gaps list covers ALL canonical sections
        - original_content and original_text are backfilled in Python from sectioner data
        - LLM output only contains: needs_change, gap_reason, rewrite_instruction, missing_keywords
    """

    def __init__(self):
        super().__init__(model="gpt-4o", max_tokens=4000, provider="openai")

    def run(self, input_dict: dict) -> dict:
        """
        Entry point for Agent 3 — supports two modes.

        Args:
            input_dict: Must contain 'resume_analysis'/'resume_understanding' and
                       'jd_analysis'/'jd_intelligence'. Optional 'resume_sections'
                       dict from sectioner (SectionText keyed by canonical name).
                       Optional 'mode' key: 'evaluate' or 'gap_closer' (default).

        Returns:
            For 'evaluate': DetailedEvalOutput as dict with per-change cards.
            For 'gap_closer': GapAnalyzerOutput as dict with section gaps.

        Raises:
            ValidationError: If input_dict is missing required fields.
            ValueError: If LLM response fails JSON parsing after 2 retries.
        """
        mode = input_dict.get("mode", "gap_closer")

        inp = GapAnalyzerInput(**input_dict)
        resume_sections_raw = input_dict.get("resume_sections", {})
        resume_sections: Dict[str, SectionText] = {
            k: SectionText(**v) if isinstance(v, dict) else v
            for k, v in resume_sections_raw.items()
        }

        jd_analysis = inp.jd_analysis or inp.jd_intelligence
        resume_analysis = inp.resume_analysis or inp.resume_understanding

        role_family = str(
            input_dict.get("role_family")
            or (resume_analysis or {}).get("role_family")
            or "ENGINEERING"
        ).upper()

        if mode == "evaluate":
            system_prompt = EVAL_SYSTEM_PROMPT + build_role_gap_addendum(role_family)
            output_model = DetailedEvalOutput
        else:
            system_prompt = GAP_SYSTEM_PROMPT + build_role_gap_addendum(role_family)
            output_model = GapAnalyzerOutput

        # Build sub_entry manifest with just labels (LLM has full resume text to verify content)
        sub_entry_manifest: dict[str, list[str]] = {}
        for sec_name, sec_text in resume_sections.items():
            if sec_text and sec_text.sub_entries:
                sub_entry_manifest[sec_name] = [e.label for e in sec_text.sub_entries]

        user_message = (
            f"FULL RESUME TEXT (for holistic context):\n"
            f"{'='*60}\n"
            f"{inp.resume_text or resume_analysis.get('raw_text', '')[:10000]}\n"
            f"{'='*60}\n\n"
            f"Resume understanding:\n{json.dumps(resume_analysis, indent=2)}\n\n"
            f"JD intelligence:\n{json.dumps(jd_analysis, indent=2)}\n\n"
            f"EXACT sub_entry labels per section (use VERBATIM as sub_label values in gaps):\n"
            f"{json.dumps(sub_entry_manifest, indent=2)}"
        )

        for attempt in range(2):
            try:
                raw = self._call_llm(system_prompt, user_message)
                parsed = self._parse_json(raw)

                # Post-process in gap_closer mode: backfill original_content/original_text
                # from sectioner data and normalize missing fields
                if mode == "gap_closer":
                    parsed = self._enrich_section_gaps(
                        parsed,
                        resume_sections,
                        resume_analysis=resume_analysis,
                        jd_analysis=jd_analysis or {},
                        resume_text=inp.resume_text or "",
                        role_family=role_family,
                    )
                elif mode == "evaluate":
                    if not isinstance(parsed.get("estimated_score_after"), int):
                        before = parsed.get("jd_match_score_before") or 0
                        try:
                            before = int(before)
                        except (TypeError, ValueError):
                            before = 0
                        parsed["estimated_score_after"] = min(100, before + 5)

                output = output_model(**parsed)
                return output.model_dump()
            except Exception as e:
                if attempt == 1:
                    raise ValueError(
                        f"GapAnalyzerAgent ({mode}): failed after 2 attempts — {e}"
                    )

    def _build_concrete_instruction(
        self,
        gap_type: str,
        rewrite_instruction: str,
        verbatim_text: str,
    ) -> str:
        """
        For length/readability gaps, prepend the verbatim target bullet
        and a concrete word-count target to the instruction.
        This gives A4 an unambiguous operation instead of a prose hint.
        Never invented content — only quotes from verbatim_text.
        """
        if not verbatim_text:
            return rewrite_instruction

        length_keywords = {
            "shorten", "shorter", "readability", "concise",
            "brief", "verbose", "long", "trim", "reduce",
        }
        instruction_lower = rewrite_instruction.lower()
        is_length_gap = any(kw in instruction_lower for kw in length_keywords)

        if not is_length_gap:
            return rewrite_instruction

        bullets = [
            line.strip() for line in verbatim_text.splitlines()
            if line.strip().startswith(("•", "-", "*"))
        ]
        if not bullets:
            return rewrite_instruction

        longest_bullet = max(bullets, key=lambda b: len(b.split()))
        word_count = len(longest_bullet.split())

        if word_count <= 20:
            return rewrite_instruction

        return (
            f"SHORTEN: The following bullet is {word_count} words. "
            f"Rewrite to ≤20 words. Keep the core metric. Same voice and tense.\n"
            f"TARGET BULLET: {longest_bullet}\n"
            f"ADDITIONAL CONTEXT: {rewrite_instruction}"
        )

    def _section_has_content(self, section_text: Optional[SectionText]) -> bool:
        """True when sectioner/A1 provided non-empty section text.

        Checks full_text first; falls back to sub_entries so sections whose
        full_text is populated by the parser (rather than A1 verbatim copy)
        still register as present.
        """
        if not section_text:
            return False
        if (section_text.full_text or "").strip():
            return True
        return bool(
            section_text.sub_entries
            and any((e.verbatim_text or "").strip() for e in section_text.sub_entries)
        )

    def _section_original_content(self, section_text: Optional[SectionText]) -> str:
        """Return best available original text for a section.

        Prefers full_text (parser-backed); falls back to sub_entries concat so
        sections like projects that get sub_entries from A1 but no full_text
        still expose their original content to the UI Fixes tab.
        """
        if not section_text:
            return ""
        if (section_text.full_text or "").strip():
            return section_text.full_text
        if section_text.sub_entries:
            parts = [
                (e.verbatim_text or "").strip()
                for e in section_text.sub_entries
                if (e.verbatim_text or "").strip()
            ]
            return "\n\n".join(parts)
        return ""

    def _ensure_missing_summary_gap(
        self,
        enriched_gaps: list[dict],
        resume_sections: Dict[str, SectionText],
        resume_analysis: dict,
        jd_analysis: dict,
    ) -> list[dict]:
        """
        When the resume has no summary block, force a summary gap so A4 creates one.

        LLM gap output often sets needs_change=false for missing summary; auto-added
        canonical gaps do the same. This post-step overrides that when JD is present.
        """
        if not jd_analysis:
            return enriched_gaps

        summary_text = resume_sections.get("summary")
        has_content = self._section_has_content(summary_text)
        has_summary_flag = bool(resume_analysis.get("has_summary", False))
        if has_summary_flag and has_content:
            return enriched_gaps

        role = str(jd_analysis.get("role_title") or "the target role").strip()
        must_kw = [
            str(k).strip()
            for k in (jd_analysis.get("must_have_skills") or [])[:6]
            if str(k).strip()
        ]
        kw_hint = ", ".join(must_kw) if must_kw else "relevant JD keywords"
        default_instruction = (
            f"Write a new 3-5 sentence professional summary tailored to {role}. "
            f"Weave in: {kw_hint}. Use only facts from experience and skills — "
            "do not invent companies, roles, or metrics."
        )

        found = False
        for gap in enriched_gaps:
            if gap.get("section") != "summary":
                continue
            found = True
            if not has_content:
                gap["needs_change"] = True
                gap["present_in_resume"] = False
                gap["original_content"] = ""
                if not str(gap.get("gap_reason") or "").strip():
                    gap["gap_reason"] = "Resume has no professional summary section"
                if not str(gap.get("rewrite_instruction") or "").strip():
                    gap["rewrite_instruction"] = default_instruction
                if not gap.get("missing_keywords") and must_kw:
                    gap["missing_keywords"] = must_kw[:5]
            break

        if not found:
            enriched_gaps.append({
                "section": "summary",
                "needs_change": True,
                "gap_reason": "Resume has no professional summary section",
                "missing_keywords": must_kw[:5],
                "rewrite_instruction": default_instruction,
                "original_content": "",
                "present_in_resume": False,
                "sub_changes": [],
            })

        return enriched_gaps

    def _enrich_section_gaps(
        self,
        parsed: dict,
        resume_sections: Dict[str, SectionText],
        resume_analysis: dict | None = None,
        jd_analysis: dict | None = None,
        resume_text: str = "",
        role_family: str = "ENGINEERING",
    ) -> dict:
        """
        Backfills original_content on SectionGap and original_text on SubLocationChange
        from sectioner data. LLM never provides these — it's a Python post-processing step.

        Args:
            parsed: Raw dict from LLM JSON response (section_gaps key present).
            resume_sections: Dict of {canonical_section_name: SectionText} from sectioner.

        Returns:
            Same dict with original_content and original_text populated.
        """
        section_gaps = parsed.get("section_gaps", [])

        enriched_gaps = []
        for gap in section_gaps:
            section_name = gap.get("section", "")
            section_text = resume_sections.get(section_name)

            gap["original_content"] = self._section_original_content(section_text)
            gap["present_in_resume"] = self._section_has_content(section_text)

            valid_labels = (
                {e.label for e in section_text.sub_entries}
                if section_text and section_text.sub_entries
                else set()
            )
            # Backfill original_text on each sub_change from matching sub_entry
            for sub_change in gap.get("sub_changes", []):
                sub_label = sub_change.get("sub_label", "")
                if valid_labels and sub_label not in valid_labels:
                    rescued = _fuzzy_match_label(sub_label, valid_labels)
                    if rescued:
                        logging.warning(
                            "GapAnalyzer: sub_label '%s' rescued → '%s'",
                            sub_label,
                            rescued,
                        )
                        sub_change["sub_label"] = rescued
                    else:
                        logging.warning(
                            "GapAnalyzer: sub_label '%s' has no match in %s",
                            sub_label,
                            section_name,
                        )
                sub_change["original_text"] = self._find_verbatim_text(
                    section_text, sub_change.get("sub_label", "")
                )
                matched_entry = self._find_sub_entry(
                    section_text, sub_change.get("sub_label", "")
                )
                if matched_entry:
                    sub_change["entry_id"] = matched_entry.entry_id
                    if not sub_change.get("sub_id"):
                        sub_change["sub_id"] = matched_entry.entry_id
                sub_change["rewrite_instruction"] = self._build_concrete_instruction(
                    gap_type=sub_change.get("gap_reason", ""),
                    rewrite_instruction=sub_change.get("rewrite_instruction", ""),
                    verbatim_text=sub_change.get("original_text", ""),
                )

            enriched_gaps.append(gap)

        parsed["section_gaps"] = enriched_gaps

        # Ensure canonical sections are all present (add any the LLM missed)
        existing_sections = {g["section"] for g in enriched_gaps}
        for section in CANONICAL_SECTIONS:
            if section not in existing_sections:
                section_text = resume_sections.get(section)
                enriched_gaps.append({
                    "section": section,
                    "needs_change": False,
                    "gap_reason": "No change needed",
                    "missing_keywords": [],
                    "rewrite_instruction": "",
                    "original_content": self._section_original_content(section_text),
                    "present_in_resume": self._section_has_content(section_text),
                    "sub_changes": [],
                })

        # Ensure lists are populated at top level
        if not parsed.get("missing_keywords"):
            all_kw: List[str] = []
            for g in enriched_gaps:
                all_kw.extend(g.get("missing_keywords", []))
            parsed["missing_keywords"] = list(dict.fromkeys(all_kw))  # dedupe preserving order
        if not parsed.get("jd_match_score_before") and parsed.get("jd_match_score_before") != 0:
            parsed["jd_match_score_before"] = 0
        parsed["priority_fixes"] = [
            str(f).strip() for f in (parsed.get("priority_fixes") or []) if str(f).strip()
        ]
        parsed["sections_changed"] = [
            g["section"] for g in enriched_gaps if g.get("needs_change")
        ]
        parsed["sections_unchanged"] = [
            g["section"] for g in enriched_gaps if not g.get("needs_change")
        ]

        enriched_gaps = self._ensure_missing_summary_gap(
            enriched_gaps,
            resume_sections,
            resume_analysis or {},
            jd_analysis or {},
        )
        enriched_gaps = _suppress_cross_entry_duplicate_gaps(
            enriched_gaps,
            resume_sections,
        )
        enriched_gaps = _ensure_minimum_gap_floor(
            enriched_gaps,
            resume_analysis or {},
            jd_analysis or {},
        )
        if not resume_text:
            resume_text = (resume_analysis or {}).get("raw_text", "") or ""
        classified = classify_section_gaps(enriched_gaps, resume_text, role_family)
        parsed["section_gaps"] = classified
        parsed["sections_changed"] = [
            g["section"] for g in classified if g.get("needs_change")
        ]
        parsed["sections_unchanged"] = [
            g["section"] for g in classified if not g.get("needs_change")
        ]
        structured_fixes = priority_fixes_from_gaps(classified)
        if structured_fixes:
            parsed["priority_fixes"] = structured_fixes

        return parsed

    def _build_jd_text_from_analysis(self, jd_analysis: dict) -> str:
        """
        Builds a human-readable JD text string from JD analysis dict.

        Used as fallback when raw JD text is not available.

        Args:
            jd_analysis: Dict from Agent 2 with role_title, must_have_skills, etc.

        Returns:
            Formatted string suitable for LLM consumption.
        """
        if not jd_analysis:
            return ""
        return (
            f"Role: {jd_analysis.get('role_title', '')}\n"
            f"Must-Have Skills: {', '.join(jd_analysis.get('must_have_skills', []))}\n"
            f"Nice-to-Have Skills: {', '.join(jd_analysis.get('nice_to_have_skills', []))}\n"
            f"Hidden Signals: {jd_analysis.get('hidden_signals', [])}\n"
        )

    def _find_sub_entry(
        self, section: Optional[SectionText], sub_label: str
    ) -> Optional[SubEntry]:
        """
        Looks up a SubEntry by label using exact, containment, then token overlap.

        Args:
            section: SectionText from sectioner, or None if section missing.
            sub_label: Label string to match against sub_entries.

        Returns:
            Matching SubEntry if found, None otherwise.
        """
        if not section or not sub_label:
            return None
        for entry in section.sub_entries:
            if entry.label == sub_label:
                return entry
        lower_sub = sub_label.lower()
        for entry in section.sub_entries:
            lower_entry = entry.label.lower()
            if lower_sub in lower_entry or lower_entry in lower_sub:
                return entry
        sub_tokens = {t for t in re.split(r"\W+", lower_sub) if len(t) > 3}
        if not sub_tokens:
            return None
        best_entry = None
        best_score = 0
        for entry in section.sub_entries:
            entry_tokens = {
                t for t in re.split(r"\W+", entry.label.lower()) if len(t) > 3
            }
            score = len(sub_tokens & entry_tokens)
            if score > best_score:
                best_score, best_entry = score, entry
        if best_score >= 2 and best_entry:
            return best_entry
        return None

    def _find_verbatim_text(self, section: Optional[SectionText], sub_label: str) -> str:
        """
        Looks up verbatim text from a section's sub_entry by sub_label.

        Three-pass match: exact, case-insensitive containment, token overlap.

        Args:
            section: SectionText from sectioner, or None if section missing.
            sub_label: Label string to match against sub_entries.

        Returns:
            verbatim_text if found, empty string otherwise.
        """
        if not section or not sub_label:
            return ""
        # 1. Exact match
        for entry in section.sub_entries:
            if entry.label == sub_label:
                return entry.verbatim_text
        # 2. Case-insensitive containment (both directions)
        lower_sub = sub_label.lower()
        for entry in section.sub_entries:
            lower_entry = entry.label.lower()
            if lower_sub in lower_entry or lower_entry in lower_sub:
                return entry.verbatim_text
        # 3. Token overlap — significant tokens (len > 3), need ≥2 matches
        sub_tokens = {t for t in re.split(r"\W+", lower_sub) if len(t) > 3}
        if not sub_tokens:
            return ""
        best_entry = None
        best_score = 0
        for entry in section.sub_entries:
            entry_tokens = {
                t for t in re.split(r"\W+", entry.label.lower()) if len(t) > 3
            }
            score = len(sub_tokens & entry_tokens)
            if score > best_score:
                best_score, best_entry = score, entry
        if best_score >= 2 and best_entry:
            return best_entry.verbatim_text
        return ""
