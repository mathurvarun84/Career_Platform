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
from backend.schemas.common import GapType, SectionText

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

You will receive:
1. Structured resume understanding (experience years, skills, seniority, domains).
2. JD intelligence (must-have/nice-to-have skills, hidden signals, company type).

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


def _build_coaching_question(gap: dict) -> tuple[str, list[str]]:
    """
    Generate a focused coaching question and hint examples for an evidence gap.
    Maps gap_reason to a targeted question. Zero LLM calls.
    """
    reason = (gap.get("gap_reason") or "").lower()

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


def _apply_gap_type_metadata(gap: dict, gap_type: str) -> dict:
    """Attach coaching/auto_apply fields for a known gap_type without re-classifying."""
    if gap_type == GapType.EVIDENCE.value:
        question, hints = _build_coaching_question(gap)
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


def classify_gap(gap: dict, resume_text: str = "") -> dict:
    """
    Classify a gap as surface / structural / evidence.
    Pure heuristic — zero LLM calls.

    When the LLM already set gap_type, trust it and only attach UX metadata.
    Heuristics run only when gap_type is absent or null.

    Args:
        gap: Section gap dict from Agent 3 enrichment.
        resume_text: Full resume text (reserved for future heuristics).

    Returns:
        Gap dict with gap_type, coaching fields, and auto_apply set.
    """
    del resume_text  # reserved; classification is text-in-gap only today

    llm_type = _normalize_gap_type(gap.get("gap_type"))
    if llm_type:
        return _apply_gap_type_metadata(gap, llm_type)

    reason = (gap.get("gap_reason") or "").lower()
    instruction = (gap.get("rewrite_instruction") or "").lower()
    keywords = [k.lower() for k in (gap.get("missing_keywords") or [])]
    combined = reason + " " + instruction + " " + " ".join(keywords)

    if any(signal in combined for signal in _EVIDENCE_SIGNALS):
        return _apply_gap_type_metadata(gap, GapType.EVIDENCE.value)

    if _is_no_change_gap(gap):
        return _apply_gap_type_metadata(gap, GapType.SURFACE.value)

    if _has_surface_signal(gap) and (gap.get("needs_change") or instruction.strip()):
        gap_with_surface = _apply_gap_type_metadata(gap, GapType.SURFACE.value)
        gap_with_surface["auto_apply"] = True
        return gap_with_surface

    return _apply_gap_type_metadata(gap, GapType.STRUCTURAL.value)


def classify_section_gaps(gaps: list[dict], resume_text: str = "") -> list[dict]:
    """Run classify_gap over every section gap and its sub_changes."""
    classified = []
    for gap in gaps:
        classified_gap = classify_gap(gap, resume_text)
        sub_changes = gap.get("sub_changes") or []
        if sub_changes:
            classified_gap["sub_changes"] = [
                classify_gap(sub, resume_text) for sub in sub_changes
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


def _apply_phantom_gap_filter(
    section_gaps: list[dict],
    resume_analysis: dict,
    jd_analysis: dict,
    resume_text: str,
) -> list[dict]:
    """
    On qualified matches, suppress experience gaps whose missing keywords
    are already covered by semantic equivalents in the resume.
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
        super().__init__(model="gpt-4o-mini", max_tokens=4000, provider="openai")

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

        sub_entry_manifest: dict[str, list[str]] = {}
        for sec_name, sec_text in resume_sections.items():
            if sec_text and sec_text.sub_entries:
                sub_entry_manifest[sec_name] = [e.label for e in sec_text.sub_entries]

        user_message = (
            f"Resume understanding:\n{json.dumps(resume_analysis, indent=2)}\n\n"
            f"JD intelligence:\n{json.dumps(jd_analysis, indent=2)}\n\n"
            f"EXACT sub_entry labels per section (use VERBATIM as sub_label values):\n"
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
        enriched_gaps = _apply_phantom_gap_filter(
            enriched_gaps,
            resume_analysis or {},
            jd_analysis or {},
            resume_text,
        )
        enriched_gaps = _ensure_minimum_gap_floor(
            enriched_gaps,
            resume_analysis or {},
            jd_analysis or {},
        )
        if not resume_text:
            resume_text = (resume_analysis or {}).get("raw_text", "") or ""
        classified = classify_section_gaps(enriched_gaps, resume_text)
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
