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
      "gap_reason": "JD requires Kafka experience not shown in current wording",
      "missing_keywords": ["Kafka"],
      "rewrite_instruction": "Reframe event-driven work to mention streaming platforms",
      "present_in_resume": true,
      "sub_changes": [
        {
          "sub_id": "flipkart_em",
          "sub_label": "Flipkart — EM (2021–present)",
          "needs_change": true,
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
- If a section does not need changes, set needs_change=false, gap_reason="No change needed",
  missing_keywords=[], rewrite_instruction="", sub_changes=[].
- For multi-entry sections, decompose into SubLocationChange entries:
  experience: one entry per company/role block
  education: one entry per degree
  certification: one entry per cert
  For summary, skills, awards: sub_changes should be empty list [].
- missing_keywords must be section-specific for section_gaps.
- priority_fixes should contain the top 3 highest-impact actions.
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
}

_SURFACE_SIGNALS = {
    "missing keyword", "typo", "spelling", "abbreviation", "acronym",
    "add keyword", "include term", "mention", "lacks the word", "not present",
}


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


def classify_gap(gap: dict, resume_text: str = "") -> dict:
    """
    Classify a gap as surface / structural / evidence.
    Pure heuristic — zero LLM calls.

    Args:
        gap: Section gap dict from Agent 3 enrichment.
        resume_text: Full resume text (reserved for future heuristics).

    Returns:
        Gap dict with gap_type, coaching fields, and auto_apply set.
    """
    del resume_text  # reserved; classification is text-in-gap only today
    reason = (gap.get("gap_reason") or "").lower()
    instruction = (gap.get("rewrite_instruction") or "").lower()
    keywords = [k.lower() for k in (gap.get("missing_keywords") or [])]
    combined = reason + " " + instruction + " " + " ".join(keywords)

    if any(signal in combined for signal in _EVIDENCE_SIGNALS):
        question, hints = _build_coaching_question(gap)
        return {
            **gap,
            "gap_type": GapType.EVIDENCE.value,
            "requires_user_input": True,
            "coaching_question": question,
            "coaching_hint": hints,
            "auto_apply": False,
        }

    missing_kw = gap.get("missing_keywords") or []
    if (
        any(signal in combined for signal in _SURFACE_SIGNALS)
        or (len(missing_kw) <= 2 and not gap.get("needs_change", True))
    ):
        return {
            **gap,
            "gap_type": GapType.SURFACE.value,
            "requires_user_input": False,
            "coaching_question": None,
            "coaching_hint": [],
            "auto_apply": True,
        }

    return {
        **gap,
        "gap_type": GapType.STRUCTURAL.value,
        "requires_user_input": False,
        "coaching_question": None,
        "coaching_hint": [],
        "auto_apply": False,
    }


def classify_section_gaps(gaps: list[dict], resume_text: str = "") -> list[dict]:
    """Run classify_gap over every section gap."""
    return [classify_gap(g, resume_text) for g in gaps]


def priority_fixes_from_gaps(section_gaps: list[dict]) -> list[dict]:
    """
    Build structured priority_fixes for the Fixes tab from classified section gaps.
    """
    fixes: list[dict] = []
    for gap in section_gaps:
        if not gap.get("needs_change"):
            continue
        sub_label = gap.get("sub_label")
        if not sub_label:
            for sub in gap.get("sub_changes") or []:
                if sub.get("needs_change"):
                    sub_label = sub.get("sub_label")
                    break
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
            "sub_label": sub_label,
        })
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
        """True when sectioner/A1 provided non-empty section text."""
        if not section_text:
            return False
        return bool((section_text.full_text or "").strip())

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

            # Backfill original_content from sectioner full_text
            gap["original_content"] = section_text.full_text if section_text else ""
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
                    "original_content": section_text.full_text if section_text else "",
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
