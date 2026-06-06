"""
Orchestrator module for Resume Intelligence Platform V2.
"""

from __future__ import annotations

import logging
import re
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from memory.session_store import (
    generate_run_id,
    save_agent_output,
    save_full_run_result,
)
from backend.agents.gap_analyzer import (
    GapAnalyzerAgent,
    build_complete_priority_fixes,
    classify_section_gaps,
    enrich_priority_fixes_from_eval_changes,
    priority_fixes_from_gaps,
    reclassify_gaps_for_resume_only,
)
from backend.agents.jd_intelligence import JDIntelligenceAgent
from backend.agents.recruiter_sim import RecruiterSimulatorAgent
from backend.agents.resume_understanding import ResumeUnderstandingAgent
from backend.agents.sectioner_agent import SectionerAgent
from backend.agents.rewriter import RewriterAgent
from backend.role_fit import compute_role_fit
from engine.ats_scorer import score_resume
from engine.llm_trace import PhaseTimer, log_trace_summary, record_phase, reset_trace
from engine.percentile import get_percentile
from validators import ResumeUnderstandingValidator
from validator.rewriter_validator import (
    assert_structural_completeness,
    backfill_missing_rewrite_sections,
)
from validator.experience_audit import (
    ensure_experience_completeness,
    log_experience_audit,
)


def _ensure_jd_match_score_after(gap_result: dict) -> None:
    """Default JD after-score when evaluate output omits estimated_score_after."""
    if gap_result.get("jd_match_score_after") is not None:
        return
    before = gap_result.get("jd_match_score_before") or gap_result.get("match_score") or 0
    try:
        before = int(before)
    except (TypeError, ValueError):
        before = 0
    gap_result["jd_match_score_after"] = min(100, before + 5)


def _dedupe_sub_entries(section_text) -> Any:
    """Remove duplicate SubEntry rows (same label + first-line fingerprint)."""
    from backend.schemas.common import SectionText, SubEntry

    if not section_text or not getattr(section_text, "sub_entries", None):
        return section_text

    seen: set[str] = set()
    deduped: list = []
    for entry in section_text.sub_entries:
        verbatim_key = re.sub(
            r"\s+", " ", entry.verbatim_text
        ).lower().strip()[:300]
        first_line = ""
        if entry.verbatim_text.strip():
            first_line = entry.verbatim_text.strip().splitlines()[0]
        label_key = re.sub(
            r"\s+", " ", f"{entry.label}|{first_line}"
        ).lower().strip()
        key = verbatim_key if verbatim_key else label_key
        if key in seen:
            logging.warning(
                "Orchestrator: duplicate sub_entry removed: '%s'",
                entry.label[:60],
            )
            continue
        seen.add(key)
        deduped.append(entry)

    if len(deduped) == len(section_text.sub_entries):
        return section_text

    return SectionText(
        header=section_text.header,
        full_text=section_text.full_text,
        sub_entries=deduped,
    )


def _dedupe_resume_sections(resume_sections: Dict[str, Any]) -> Dict[str, Any]:
    """Dedupe sub_entries for sections that use per-entry lists."""
    for key in list(resume_sections.keys()):
        canon = str(key).lower().strip()
        if canon not in ("experience", "education", "certifications", "projects"):
            continue
        val = resume_sections[key]
        if val is not None:
            resume_sections[key] = _dedupe_sub_entries(val)
    return resume_sections


class Orchestrator:
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id
        self.resume_understanding = ResumeUnderstandingAgent()
        self.sectioner = SectionerAgent()
        self.jd_intelligence = JDIntelligenceAgent()
        self.gap_analyzer = GapAnalyzerAgent()
        self.rewriter = RewriterAgent()
        self.recruiter_sim = RecruiterSimulatorAgent()

    def _build_merged_resume_sections(self, resume_und: dict, resume_text: str):
        """Merge A1 and Sectioner sections; keep richer section payload."""
        from backend.schemas.common import SectionText

        a1_raw = resume_und.get("resume_sections", {})
        a1_sections = {
            k: SectionText(**v) if isinstance(v, dict) else v
            for k, v in a1_raw.items()
        }

        merged = dict(a1_sections)
        try:
            sectioner_raw = self.sectioner.run({"resume_text": resume_text}) or {}
            sectioner_sections = {
                k: SectionText(**v) if isinstance(v, dict) else v
                for k, v in sectioner_raw.items()
            }
        except Exception as exc:
            logging.warning("Sectioner merge skipped: %s", exc)
            sectioner_sections = {}

        for name, sec in sectioner_sections.items():
            cur = merged.get(name)
            if not cur:
                merged[name] = sec
                continue
            cur_count = len(cur.sub_entries or [])
            new_count = len(sec.sub_entries or [])
            cur_len = len(cur.full_text or "")
            new_len = len(sec.full_text or "")
            if (new_count > cur_count) or (new_count == cur_count and new_len > cur_len):
                merged[name] = sec

        return merged

    def _dump_sections(self, sections: Dict[str, Any]) -> Dict[str, Any]:
        """Convert SectionText mapping to plain dictionaries."""
        return {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in sections.items()
        }

    def _needs_sectioner(self, resume_sections: dict, resume_text: str) -> bool:
        """
        Returns True when SectionerAgent should run as a fallback.

        Fires when log_experience_audit detects that A1 is missing more than
        one experience entry compared to the ground-truth count from the raw
        resume text. Skips Sectioner on clean resumes where A1 delivered all
        entries correctly.
        """
        try:
            audit = log_experience_audit(
                "sectioner_gate",
                resume_text,
                resume_sections,
            )
            ground_truth = audit.get("ground_truth_count", 0)
            a1_count = audit.get("sub_entries_count", 0)

            # Diagnostic: log what keys and sub_entry counts are actually in resume_sections
            section_debug = {
                k: len(getattr(v, "sub_entries", None) or v.get("sub_entries", []) if isinstance(v, dict) else [])
                if v is not None else 0
                for k, v in resume_sections.items()
            }
            logging.info(
                "SectionerGate: section_keys=%s sub_entry_counts=%s",
                list(resume_sections.keys()),
                section_debug,
            )

            # Allow a tolerance of 1 — A1 missing exactly 1 entry doesn't
            # justify a full Sectioner LLM call.
            needs = (ground_truth - a1_count) > 1

            logging.info(
                "SectionerGate: ground_truth=%d a1_count=%d needs_sectioner=%s",
                ground_truth,
                a1_count,
                needs,
            )
            return needs
        except Exception as exc:
            # If the gate itself errors, default to running Sectioner (safe fallback).
            logging.warning(
                "SectionerGate check failed (%s) — defaulting to run Sectioner.", exc
            )
            return True

    def _merge_sectioner_into_sections(
        self,
        resume_sections: Dict[str, Any],
        resume_text: str,
        resume_und: dict,
    ) -> Dict[str, Any]:
        """Run sectioner and merge richer sub_entries into resume_sections before A3."""
        from backend.schemas.common import SectionText

        try:
            sectioner_raw = self.sectioner.run({"resume_text": resume_text}) or {}
            sectioner_sections = {
                k: SectionText(**v) if isinstance(v, dict) else v
                for k, v in sectioner_raw.items()
            }
            for name, sec in sectioner_sections.items():
                cur = resume_sections.get(name)
                if not cur:
                    resume_sections[name] = sec
                    continue
                cur_count = len(cur.sub_entries or [])
                new_count = len(sec.sub_entries or [])
                cur_len = len(cur.full_text or "")
                new_len = len(sec.full_text or "")
                if (new_count > cur_count) or (
                    new_count == cur_count and new_len > cur_len
                ):
                    resume_sections[name] = sec
            resume_und["resume_sections"] = self._dump_sections(resume_sections)
        except Exception as exc:
            logging.warning("Sectioner merge skipped: %s", exc)
        return resume_sections

    def _sync_experience_sections(
        self,
        resume_sections: Dict[str, Any],
        resume_text: str,
        resume_und: dict | None = None,
    ) -> Dict[str, Any]:
        """
        Backfill experience sub_entries from raw resume and log counts.

        Must run before A4 rewriter so stitch order includes every company.
        """
        from backend.schemas.common import SectionText

        exp = resume_sections.get("experience")
        if exp is None:
            for key, val in list(resume_sections.items()):
                if str(key).lower().strip() in (
                    "experience",
                    "work experience",
                    "professional experience",
                    "employment",
                ):
                    exp = val
                    break

        augmented = ensure_experience_completeness(exp, resume_text)
        if augmented is not None:
            resume_sections["experience"] = _dedupe_sub_entries(augmented)
            if resume_und is not None:
                rs = resume_und.setdefault("resume_sections", {})
                if isinstance(rs, dict):
                    rs["experience"] = (
                        resume_sections["experience"].model_dump()
                        if hasattr(resume_sections["experience"], "model_dump")
                        else resume_sections["experience"]
                    )

        resume_sections = _dedupe_resume_sections(resume_sections)

        log_experience_audit(
            "orchestrator_pre_rewrite",
            resume_text,
            resume_sections,
        )
        return resume_sections

    def _extract_a1_sections(self, resume_und: dict) -> Dict[str, Any]:
        """Extract resume sections available directly in A1 output."""
        from backend.schemas.common import SectionText
        a1_raw = resume_und.get("resume_sections", {})
        return {
            k: SectionText(**v) if isinstance(v, dict) else v
            for k, v in a1_raw.items()
        }

    def _infer_strengths_from_resume(
        self,
        resume_und: dict,
        resume_sections: dict | None = None,
    ) -> dict:
        """
        Build gap_result from A1 output alone (no JD).
        Delegates to _build_no_jd_gaps for the correct section_gaps shape.
        Kept for backward compatibility — run_full_evaluation calls
        _build_no_jd_gaps directly.
        """
        return self._build_no_jd_gaps(resume_und, resume_sections or {})

    def _apply_gap_classification(
        self,
        gap_result: dict,
        resume_text: str,
        *,
        structured_priority_fixes: bool = True,
        overview_strings: list[str] | None = None,
        ats_issues: list[str] | None = None,
        resume_sections: dict | None = None,
    ) -> dict:
        """
        Classify every section gap and rebuild priority_fixes for the UI.

        overview_strings: strings already surfaced in the Overview tab (A1 weaknesses +
        improvement_areas). JD mode filters overlapping fixes; resume-only backfills any
        overview item missing from section_gaps.
        """
        section_gaps = gap_result.get("section_gaps") or gap_result.get("gaps") or []
        classified = classify_section_gaps(section_gaps, resume_text)
        if gap_result.get("resume_only_mode"):
            classified = reclassify_gaps_for_resume_only(classified)
        gap_result["section_gaps"] = classified
        gap_result["gaps"] = classified
        if structured_priority_fixes:
            fixes = build_complete_priority_fixes(
                classified,
                ats_issues=ats_issues,
                overview_strings=overview_strings,
                resume_only_mode=bool(gap_result.get("resume_only_mode")),
                resume_sections=resume_sections,
            )
            if fixes:
                gap_result["priority_fixes"] = fixes
        return gap_result

    def _build_actionable_changes(self, gap_result: dict) -> list:
        """Convert section_gaps into ActionableChange objects for the UI.

        Creates detailed per-change suggestions from section-level gaps.
        """
        from backend.schemas.agent3_schema import ActionableChange

        changes = []
        change_id = 0
        section_gaps = gap_result.get("section_gaps", [])

        for gap in section_gaps:
            if not gap.get("needs_change"):
                continue

            section = gap.get("section", "unknown")
            gap_reason = gap.get("gap_reason", "Section needs improvement")
            rewrite_instr = gap.get("rewrite_instruction", "")
            missing_kw = gap.get("missing_keywords", [])

            # For sections with sub_changes (experience, education), create per-entry changes
            sub_changes = gap.get("sub_changes", [])
            if sub_changes:
                for sub in sub_changes:
                    if not sub.get("needs_change"):
                        continue
                    change_id += 1
                    changes.append(ActionableChange(
                        change_id=change_id,
                        location={
                            "section": section,
                            "sub_location": sub.get("sub_label", "")
                        },
                        change_type="rewrite_bullet",
                        priority="high" if "critical" in str(gap_reason).lower() else "medium",
                        why=sub.get("gap_reason", gap_reason),
                        original_text=sub.get("original_text", ""),
                        suggested_text=rewrite_instr or f"Improve: {gap_reason}",
                        keywords_added=sub.get("missing_keywords", missing_kw),
                    ).model_dump())
            else:
                # For monolithic sections (summary, skills), one change per section
                change_id += 1
                changes.append(ActionableChange(
                    change_id=change_id,
                    location={
                        "section": section,
                        "sub_location": ""
                    },
                    change_type="rewrite_section",
                    priority="high" if "critical" in str(gap_reason).lower() else "medium",
                    why=gap_reason,
                    original_text=gap.get("original_content", ""),
                    suggested_text=rewrite_instr or f"Improve {section}",
                    keywords_added=missing_kw,
                ).model_dump())

        return changes

    def _build_no_jd_gaps(
        self,
        resume_und: dict,
        resume_sections: dict,
    ) -> dict:
        """
        Build section_gaps from A1's improvement_areas and weaknesses
        when no JD is present.

        A1 (ResumeUnderstandingAgent) already identifies what needs fixing.
        This converts those findings into the section_gaps format that
        RewriterAgent.run() consumes — so the rewriter can act without a JD.

        Returns a dict shaped like GapAnalyzerOutput. The rewriter reads
        either 'gaps' or 'section_gaps' — both are populated here.
        """
        from backend.schemas.common import SectionText

        improvement_areas: list[str] = [
            str(a).strip()
            for a in (resume_und.get("improvement_areas") or [])
            if str(a).strip()
        ]
        weaknesses: list[str] = [
            str(w).strip()
            for w in (resume_und.get("weaknesses") or [])
            if str(w).strip()
        ]
        has_summary: bool = bool(resume_und.get("has_summary", False))

        # Canonical sections to cover — same order as GapAnalyzerAgent
        canonical_sections = [
            "summary", "skills", "experience",
            "education", "certifications", "awards",
        ]

        # Route improvement_areas and weaknesses to sections by keyword
        _section_keywords: dict[str, list[str]] = {
            "summary":        ["summary", "objective", "profile", "introduction", "header"],
            "skills":         ["skill", "technology", "tech stack", "keyword",
                               "tool", "framework", "language"],
            "experience":     ["experience", "bullet", "impact", "metric", "achievement",
                               "quantif", "result", "wording", "action verb", "role",
                               "company", "oracle", "optimizely", "sheroes"],
            "education":      ["education", "degree", "institution", "gpa", "university"],
            "certifications": ["certif", "license", "credential"],
            "awards":         ["award", "achievement", "honor", "recognit"],
        }

        def _route_to_section(text: str) -> str:
            lowered = text.lower()
            for section, keywords in _section_keywords.items():
                if any(kw in lowered for kw in keywords):
                    return section
            return "experience"  # default — most improvements are experience-related

        def _weakness_matches_entry(weakness: str, entry_label: str) -> bool:
            """Match A1 weakness text to a resume sub_entry label (fuzzy)."""
            w_lower = weakness.lower()
            label_lower = (entry_label or "").lower()
            company_token = (
                entry_label.split("|")[0].split("—")[0].strip().lower()
                if entry_label
                else ""
            )
            if company_token and len(company_token) > 2 and company_token in w_lower:
                return True
            compact_w = re.sub(r"[^a-z0-9]", "", w_lower)
            compact_label = re.sub(r"[^a-z0-9]", "", label_lower)
            compact_company = re.sub(r"[^a-z0-9]", "", company_token)
            if compact_company and len(compact_company) > 2:
                if compact_company in compact_w or compact_w in compact_company:
                    return True
                if compact_label and compact_company in compact_label:
                    return True
            if compact_label and len(compact_label) > 2 and compact_label in compact_w:
                return True
            wm = re.match(
                r"^(.+?)(?:\s+(?:em|role|bullets|bullet|lacks|lack|missing)\b)",
                w_lower,
            )
            if wm and compact_company:
                w_company_compact = re.sub(r"[^a-z0-9]", "", wm.group(1))
                if w_company_compact and (
                    w_company_compact in compact_company
                    or compact_company in w_company_compact
                ):
                    return True
            first_word = company_token.split()[0] if company_token else ""
            if len(first_word) > 2 and first_word in w_lower:
                return True
            return False

        # Accumulate per-section rewrite instructions
        section_instructions: dict[str, list[str]] = {s: [] for s in canonical_sections}

        for area in improvement_areas:
            section_instructions[_route_to_section(area)].append(area)

        for weakness in weaknesses:
            # Preserve full weakness — location context before → must not be lost
            section_instructions[_route_to_section(weakness)].append(weakness)

        # Build section_gaps list
        section_gaps: list[dict] = []

        for section in canonical_sections:
            instructions = section_instructions.get(section, [])

            # Resolve section text from resume_sections
            sec_obj = resume_sections.get(section)
            original_content = ""
            sub_entries = []
            if sec_obj is not None:
                if hasattr(sec_obj, "full_text"):
                    original_content = sec_obj.full_text or ""
                    sub_entries = list(sec_obj.sub_entries or [])
                elif isinstance(sec_obj, dict):
                    original_content = sec_obj.get("full_text", "") or ""
                    sub_entries = sec_obj.get("sub_entries", []) or []

            # Summary: always needs_change when missing
            if section == "summary" and not has_summary:
                section_gaps.append({
                    "section": "summary",
                    "needs_change": True,
                    "gap_reason": (
                        "No professional summary found — "
                        "generating one improves recruiter first impression"
                    ),
                    "missing_keywords": [],
                    "rewrite_instruction": (
                        "Write a professional summary for this candidate based solely on "
                        "their experience, seniority, and tech stack in the resume. "
                        "3-4 sentences: (1) current role/level and years of experience, "
                        "(2) core technical expertise naming 2-3 specific technologies, "
                        "(3) key career achievement or domain impact, "
                        "(4) value the candidate brings to the next role. "
                        "First person. Present tense. No evaluation labels."
                    ),
                    "original_content": "",
                    "present_in_resume": False,
                    "sub_changes": [],
                })
                continue

            # Build sub_changes for experience by matching weakness company mentions
            sub_changes: list[dict] = []
            if section == "experience" and sub_entries:
                for entry in sub_entries:
                    entry_label = (
                        entry.label if hasattr(entry, "label")
                        else entry.get("label", "")
                    )
                    entry_verbatim = (
                        entry.verbatim_text if hasattr(entry, "verbatim_text")
                        else entry.get("verbatim_text", "")
                    )
                    entry_id = (
                        entry.entry_id if hasattr(entry, "entry_id")
                        else entry.get("entry_id", "")
                    )
                    if not entry_id:
                        from backend.utils.entry_id import derive_entry_id
                        entry_id = derive_entry_id(entry_label)
                    matching = [
                        w for w in weaknesses
                        if _weakness_matches_entry(w, entry_label)
                    ]
                    if matching:
                        fix = (
                            matching[0].split("→", 1)[-1].strip()
                            if "→" in matching[0]
                            else "Improve impact clarity and add quantified metrics."
                        )
                        sub_changes.append({
                            "sub_id": entry_id,
                            "entry_id": entry_id,
                            "sub_label": entry_label,
                            "needs_change": True,
                            "gap_reason": matching[0],
                            "rewrite_instruction": fix,
                            "missing_keywords": [],
                            "original_text": entry_verbatim,
                        })

            needs_change = bool(instructions) or bool(sub_changes)

            # Display: most specific instruction (prefer full weakness with →)
            display_reason = next(
                (i for i in instructions if "→" in i),
                instructions[0] if instructions else "",
            )
            # Rewriter: fix halves only (after →)
            rewrite_instruction = " ".join(
                (i.split("→", 1)[-1].strip() if "→" in i else i)
                for i in instructions[:3]
            ) if instructions else ""

            section_gaps.append({
                "section": section,
                "needs_change": needs_change,
                "gap_reason": display_reason or "No change needed",
                "missing_keywords": [],
                "rewrite_instruction": rewrite_instruction,
                "original_content": original_content,
                "present_in_resume": bool(original_content),
                "sub_changes": sub_changes,
            })

        return {
            "section_gaps": section_gaps,
            "gaps": section_gaps,           # rewriter reads either key
            "missing_keywords": [],
            "priority_fixes": [],           # populated by priority_fixes_from_gaps() post-classification
            "sections_changed": [
                g["section"] for g in section_gaps if g.get("needs_change")
            ],
            "sections_unchanged": [
                g["section"] for g in section_gaps if not g.get("needs_change")
            ],
            "jd_match_score_before": 0,
            "resume_only_mode": True,
            "strengths": resume_und.get("strengths", []),
            "weaknesses": weaknesses,
            "quick_wins": improvement_areas,
            "match_score": None,
            "confidence_score": None,
        }

    def _build_gap_fallback_rewrites(self, gap_output: Dict[str, Any]) -> Dict[str, Any]:
        fallback_rewrites: Dict[str, Dict[str, str]] = {}
        for gap in gap_output.get("section_gaps") or gap_output.get("gaps") or []:
            section = gap.get("section", "unknown")
            hint = (
                gap.get("rewrite_instruction")
                or gap.get("rewrite_hint")
                or gap.get("suggestion")
                or "Improve this section."
            )
            fallback_rewrites[section] = {
                "balanced": f"[Rewrite unavailable - {hint}]",
                "aggressive": f"[Rewrite unavailable - {hint}]",
                "top_1_percent": f"[Rewrite unavailable - {hint}]",
            }

        fallback_styles = {
            "balanced": {"summary": "", "skills": "", "experience": [], "projects": []},
            "aggressive": {"summary": "", "skills": "", "experience": [], "projects": []},
            "top_1_percent": {"summary": "", "skills": "", "experience": [], "projects": []},
        }

        for section, variants in fallback_rewrites.items():
            for style_name, text in variants.items():
                if section == "summary":
                    fallback_styles[style_name]["summary"] = text
                elif section == "skills":
                    fallback_styles[style_name]["skills"] = text
                elif section == "experience":
                    fallback_styles[style_name]["experience"] = [{
                        "company": "Experience",
                        "role": "",
                        "rewritten_bullets": [text],
                    }]
                elif section == "projects":
                    fallback_styles[style_name]["projects"] = [{
                        "name": "Projects",
                        "tech_stack": [],
                        "rewritten_description": text,
                    }]

        return {"rewrites": fallback_rewrites, "styles": fallback_styles}

    @staticmethod
    def _build_role_fit_gate_gap(role_fit: dict, jd_intel: dict | None) -> dict:
        """
        Lightweight gap payload when role-fit pre-check exits before A3.
        Keeps Overview/Gap tabs functional without running GapAnalyzer.
        """
        role_title = (jd_intel or {}).get("role_title", "Target role")
        fitness = role_fit.get("fitness", "underqualified")
        sen_gap = int(role_fit.get("seniority_gap", 0))
        exp_gap = int(role_fit.get("experience_gap", 0))
        fit_score = int(role_fit.get("score", 0))

        parts = [f"Role fit pre-check: {fitness} for {role_title}."]
        if sen_gap:
            parts.append(f"Seniority gap: {sen_gap} level(s) below JD expectation.")
        if exp_gap:
            parts.append(f"Experience gap: {exp_gap} year(s) below minimum.")
        parts.append(
            "Full JD gap analysis and recruiter simulation were skipped to save cost."
        )
        gate_reason = " ".join(parts)

        section_gaps = [
            {
                "section": "summary",
                "gap_reason": gate_reason,
                "rewrite_instruction": (
                    "Target a role closer to your current seniority, or pick a recommended "
                    "role from the role-fit panel before re-running analysis."
                ),
                "missing_keywords": [],
                "needs_change": True,
                "gap_type": "role_fit",
                "requires_user_input": False,
                "auto_apply": False,
                "sub_changes": [],
            }
        ]
        priority_fixes = priority_fixes_from_gaps(section_gaps)

        return {
            "resume_only_mode": False,
            "jd_match_score_before": fit_score,
            "jd_match_score_after": None,
            "match_score": fit_score,
            "section_gaps": section_gaps,
            "gaps": section_gaps,
            "priority_fixes": priority_fixes,
            "missing_keywords": [],
            "changes": [],
            "role_fit_gate": True,
        }

    def _compute_deterministic_insights(
        self,
        ats_result: dict,
        resume_und: dict,
        gap_result: dict | None,
    ) -> tuple[dict | None, dict | None]:
        """Percentile + positioning without LLM (used on role-fit early exit too)."""
        from engine.career_positioning import get_positioning_statement

        percentile = None
        positioning = None
        seniority = resume_und.get("seniority", "mid")
        if hasattr(seniority, "value"):
            seniority = seniority.value

        match_score = 0
        if isinstance(gap_result, dict):
            match_score = (
                gap_result.get("jd_match_score_before")
                or gap_result.get("match_score")
                or 0
            )

        try:
            ats_score = int(ats_result.get("score", 0))
            resume_only = isinstance(gap_result, dict) and gap_result.get(
                "resume_only_mode", False
            )
            if resume_only:
                composite = float(ats_score)
            else:
                composite = (ats_score * 0.4) + (float(match_score) * 0.6)
            percentile = get_percentile(composite, str(seniority))
        except Exception as exc:
            logging.warning(
                "Percentile calculation failed (early exit): %s", exc
            )

        try:
            positioning = get_positioning_statement(
                seniority=str(seniority),
                ats_score=int(ats_result.get("score", 0)),
                jd_match_score=int(match_score or 0),
                sections_changed=0,
                ats_breakdown=ats_result.get("breakdown", {}),
                ats_issues=ats_result.get("ats_issues", []),
                expected_signals=resume_und.get("resume_health", {}).get(
                    "expected_signals", []
                ),
                percentile=percentile,
            )
        except Exception as exc:
            logging.warning(
                "Career positioning failed (early exit): %s", exc
            )

        return percentile, positioning

    def run_full_evaluation(
        self,
        resume_text: str,
        jd_text: Optional[str] = None,
        run_sim: bool = False,
        skip_rewrite: bool = False,
        user_id: Optional[str] = None,
        progress_cb: Optional[callable] = None,
        partial_result_cb: Optional[callable] = None,
        cached_stage_data: Optional[Dict[str, Any]] = None,
        stage_cache_cb: Optional[callable] = None,
        sse_step_cb: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        uid = user_id or self.user_id or "anonymous"
        run_id = generate_run_id()
        reset_trace(run_id)
        if progress_cb: progress_cb({"step":1,"label":"Reading your resume...","pct":10})
        has_jd = bool(jd_text and jd_text.strip())
        with PhaseTimer("ats_score"):
            ats_result = score_resume(resume_text, jd_text if has_jd else None)
        if partial_result_cb:
            partial_result_cb({"ats": ats_result})

        cache_hit = bool(cached_stage_data)
        if cache_hit:
            logging.info("SectionerGate: cache_hit — Sectioner skipped.")
            resume_und = dict(cached_stage_data.get("resume_und") or {})
            jd_intel = cached_stage_data.get("jd_intel")
            resume_sections = cached_stage_data.get("resume_sections") or {}
            # Re-merge parser output so cached A1 sections pick up PDF spacing fixes.
            from parser import _extract_section_blocks
            from backend.schemas.common import SectionText

            det_blocks = _extract_section_blocks(resume_text)
            for sec_name, sec_text in det_blocks.items():
                if not sec_text.strip():
                    continue
                existing = resume_sections.get(sec_name)
                existing_text = ""
                if isinstance(existing, dict):
                    existing_text = str(existing.get("full_text") or "")
                elif hasattr(existing, "full_text"):
                    existing_text = str(existing.full_text or "")
                if len(sec_text.strip()) >= len(existing_text.strip()):
                    # Preserve sub_entries from A1 — only patch full_text from parser.
                    existing_subs = []
                    if isinstance(existing, dict):
                        existing_subs = existing.get("sub_entries") or []
                    elif hasattr(existing, "sub_entries"):
                        existing_subs = existing.sub_entries or []
                    resume_sections[sec_name] = SectionText(
                        header=sec_name,
                        full_text=sec_text.strip(),
                        sub_entries=existing_subs,
                    )
        else:
            if has_jd:
                with PhaseTimer("a1_a2_parallel"):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        fut_resume = executor.submit(
                            self.resume_understanding.run,
                            {"resume_text": resume_text, "user_id": uid},
                        )
                        fut_jd = executor.submit(
                            self.jd_intelligence.run,
                            {"jd_text": jd_text},
                        )
                        resume_und = fut_resume.result()
                        jd_intel = fut_jd.result()
                if jd_intel:
                    from backend.few_shot_prompts import detect_role_family

                    resume_und["role_family"] = detect_role_family(
                        resume_text,
                        str(jd_intel.get("role_title") or ""),
                    )
                # Save A2 output to session store
                try:
                    save_agent_output(uid, run_id, "jd_intelligence", jd_intel)
                except Exception as e:
                    logging.warning("Failed to save jd_intelligence to session store: %s", e)
            else:
                with PhaseTimer("a1_only"):
                    resume_und = self.resume_understanding.run({
                        "resume_text": resume_text,
                        "user_id": uid,
                    })
                jd_intel = None

            with PhaseTimer("a1_validator_and_sections"):
                resume_und = ResumeUnderstandingValidator().validate_and_fix(resume_und, resume_text)
                resume_sections = self._extract_a1_sections(resume_und)
            # Save A1 output to session store
            try:
                save_agent_output(uid, run_id, "resume_understanding", resume_und)
            except Exception as e:
                logging.warning("Failed to save resume_understanding to session store: %s", e)
            # Harden resume_sections: backfill any empty sections from deterministic parser.
            from parser import _extract_section_blocks
            from backend.schemas.common import SectionText

            det_blocks = _extract_section_blocks(resume_text)
            for sec_name, sec_text in det_blocks.items():
                existing = resume_sections.get(sec_name)
                existing_text = (existing.full_text if hasattr(existing, "full_text") else "") if existing else ""
                if sec_text.strip() and (not existing or not str(existing_text).strip()):
                    # Preserve sub_entries from A1 — only patch full_text from parser.
                    existing_subs = []
                    if existing is not None:
                        if isinstance(existing, dict):
                            existing_subs = existing.get("sub_entries") or []
                        elif hasattr(existing, "sub_entries"):
                            existing_subs = existing.sub_entries or []
                    resume_sections[sec_name] = SectionText(
                        header=sec_name,
                        full_text=sec_text.strip(),
                        sub_entries=existing_subs,
                    )
            resume_sections = self._sync_experience_sections(
                resume_sections, resume_text, resume_und
            )
            log_experience_audit("post_a1_validator", resume_text, resume_sections)
            if stage_cache_cb:
                stage_cache_cb({
                    "resume_und": dict(resume_und),
                    "jd_intel": jd_intel,
                    "resume_sections": self._dump_sections(resume_sections),
                })

        if isinstance(resume_sections, dict):
            from backend.schemas.common import SectionText
            resume_sections = {
                k: SectionText(**v) if isinstance(v, dict) else v
                for k, v in resume_sections.items()
            }
        resume_sections = self._sync_experience_sections(
            resume_sections, resume_text, resume_und
        )
        resume_und["resume_sections"] = self._dump_sections(resume_sections)
        if partial_result_cb:
            partial_result_cb({"resume": resume_und})
        if progress_cb: progress_cb({"step":1,"label":"Resume parsed successfully","pct":30})

        # ── Role Fit Gate ────────────────────────────────────────────────────
        # Compute before A3/A4/A5. If underqualified, return early to save
        # ~75% of token cost (skips GapAnalyzer, Sectioner, Rewriter, RecruiterSim).
        role_fit: dict | None = None
        role_fit_precheck: dict | None = None
        if has_jd and jd_intel and resume_und:
            try:
                role_fit_precheck = compute_role_fit(resume_und, jd_intel)
                logging.info(
                    "Role fit (pre-A3) — fitness=%s score=%s exp_gap=%s seniority_gap=%s",
                    role_fit_precheck["fitness"], role_fit_precheck["score"],
                    role_fit_precheck["experience_gap"], role_fit_precheck["seniority_gap"],
                )
            except Exception as _rf_exc:
                logging.warning("compute_role_fit pre-check failed (non-fatal): %s", _rf_exc)
                role_fit_precheck = None

        # Early exit: underqualified → skip A3, Sectioner, A4, A5 entirely.
        # A1 + A2 output is enough for the frontend gate screen.
        if (
            has_jd
            and role_fit_precheck is not None
            and role_fit_precheck.get("fitness") == "underqualified"
        ):
            logging.info("Role fit: underqualified — early exit, skipping A3/A4/A5")
            if progress_cb:
                progress_cb({"step": 2, "label": "Analysis complete", "pct": 100})
            if sse_step_cb:
                sse_step_cb(3, "Insights ready")
            gate_gap = self._build_role_fit_gate_gap(role_fit_precheck, jd_intel)
            early_percentile, early_positioning = self._compute_deterministic_insights(
                ats_result, resume_und, gate_gap
            )
            early_result = {
                "ats": ats_result,
                "resume": resume_und,
                "gap": gate_gap,
                "rewrites": None,
                "sim": None,
                "percentile": early_percentile,
                "positioning": early_positioning,
                "jd_intelligence": jd_intel,
                "patches": [],
                "validation": None,
                "role_fit": role_fit_precheck,
            }
            try:
                save_full_run_result(uid, run_id, early_result)
            except Exception as _save_exc:
                logging.warning("Failed to save early_result to session store: %s", _save_exc)
            log_trace_summary()
            return early_result
        # ─────────────────────────────────────────────────────────────────────

        if has_jd:
            if progress_cb: progress_cb({"step":2,"label":"Analyzing gaps against JD...","pct":45})
            run_sectioner = (not cache_hit) and self._needs_sectioner(
                resume_sections, resume_text
            )
            with PhaseTimer("a3_sectioner_parallel"):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    fut_gap = executor.submit(
                        self.gap_analyzer.run,
                        {
                            "resume_understanding": resume_und,
                            "jd_intelligence": jd_intel,
                            "resume_text": resume_text,
                            "resume_sections": resume_sections,
                            "jd_text": jd_text,
                            "mode": "gap_closer",
                            "role_family": resume_und.get("role_family", "ENGINEERING"),
                        },
                    )
                    fut_sectioner = (
                        executor.submit(
                            self.sectioner.run,
                            {"resume_text": resume_text},
                        )
                        if run_sectioner
                        else None
                    )
                    gap_result = fut_gap.result()

                    if fut_sectioner is not None:
                        try:
                            from backend.schemas.common import SectionText

                            sectioner_raw = fut_sectioner.result() or {}
                            sectioner_sections = {
                                k: SectionText(**v) if isinstance(v, dict) else v
                                for k, v in sectioner_raw.items()
                            }
                            for name, sec in sectioner_sections.items():
                                cur = resume_sections.get(name)
                                if not cur:
                                    resume_sections[name] = sec
                                    continue
                                cur_count = len(cur.sub_entries or [])
                                new_count = len(sec.sub_entries or [])
                                cur_len = len(cur.full_text or "")
                                new_len = len(sec.full_text or "")
                                if (new_count > cur_count) or (
                                    new_count == cur_count and new_len > cur_len
                                ):
                                    resume_sections[name] = sec
                            resume_und["resume_sections"] = self._dump_sections(
                                resume_sections
                            )
                            logging.info(
                                "SectionerGate: Sectioner ran and merged successfully."
                            )
                        except Exception as exc:
                            logging.warning("Sectioner merge skipped: %s", exc)
                    else:
                        logging.info(
                            "SectionerGate: Sectioner skipped — A1 sub_entries "
                            "count matches ground truth."
                        )
            resume_sections = self._sync_experience_sections(
                resume_sections, resume_text, resume_und
            )
            log_experience_audit("post_sectioner_merge", resume_text, resume_sections)
            if progress_cb: progress_cb({"step":2,"label":"Gap analysis complete","pct":65})
            if sse_step_cb:
                sse_step_cb(1, "JD matched")
        else:
            # No JD: convert A1's improvement_areas and weaknesses into section_gaps
            # so the rewriter can act on them. Also generates summary if missing.
            gap_result = self._build_no_jd_gaps(resume_und, resume_sections)
            if sse_step_cb:
                sse_step_cb(1, "Resume analysed")
        if isinstance(gap_result, dict):
            overview_strings = (
                list(resume_und.get("improvement_areas") or [])
                + list(resume_und.get("weaknesses") or [])
            )
            gap_result = self._apply_gap_classification(
                gap_result,
                resume_text,
                structured_priority_fixes=True,
                overview_strings=overview_strings,
                ats_issues=ats_result.get("ats_issues") or [],
                resume_sections=resume_sections,
            )
        # Build actionable changes from section gaps
        try:
            if isinstance(gap_result, dict):
                changes = self._build_actionable_changes(gap_result)
                gap_result["changes"] = changes
                logging.info("Built %d actionable changes from section gaps", len(changes))
                if not changes:
                    logging.warning(
                        "No actionable changes built. Section gaps with needs_change: %s",
                        [g.get("section") for g in gap_result.get("section_gaps", []) if g.get("needs_change")]
                    )
        except Exception as e:
            logging.warning("Failed to build actionable changes: %s", e)
            gap_result["changes"] = []

        # Save A3 output to session store
        try:
            save_agent_output(uid, run_id, "gap_analyzer", gap_result)
        except Exception as e:
            logging.warning("Failed to save gap_analyzer to session store: %s", e)
        if partial_result_cb:
            partial_result_cb({"gap": gap_result, "resume": resume_und})

        if has_jd and jd_intel and resume_und and isinstance(gap_result, dict):
            try:
                role_fit = compute_role_fit(resume_und, jd_intel, gap_result)
                logging.info(
                    "Role fit (post-A3) — fitness=%s score=%s unanswerable=%s",
                    role_fit["fitness"],
                    role_fit["score"],
                    role_fit.get("unanswerable_evidence_gaps", 0),
                )
            except Exception as _rf_exc:
                logging.warning("compute_role_fit post-A3 failed (non-fatal): %s", _rf_exc)
                role_fit = role_fit_precheck

        rewrites = None
        eval_gap = None
        sim_result = None
        patches_raw = []
        validation_summary = None
        _parallel_t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_rewrite = None
            fut_eval = None
            fut_sim = None
            if not skip_rewrite:
                if progress_cb: progress_cb({"step":3,"label":"Rewriting changed sections...","pct":75})
                resume_sections = self._sync_experience_sections(
                    resume_sections, resume_text, resume_und
                )
                fut_rewrite = executor.submit(
                    self.rewriter.run,
                    {
                        "resume_text": resume_text,
                        "resume_sections": self._dump_sections(resume_sections),
                        "gap_analysis": gap_result,
                        "jd_intelligence": jd_intel,
                        "style_fingerprint": None,
                        "role_family": resume_und.get("role_family", "ENGINEERING"),
                    },
                )
            if has_jd and isinstance(gap_result, dict):
                fut_eval = executor.submit(
                    self.gap_analyzer.run,
                    {
                        "resume_understanding": resume_und,
                        "jd_intelligence": jd_intel,
                        "resume_text": resume_text,
                        "resume_sections": resume_sections,
                        "jd_text": jd_text,
                        "mode": "evaluate",
                    },
                )
            cached_sim = None
            if cached_stage_data and isinstance(cached_stage_data, dict):
                raw_sim = cached_stage_data.get("recruiter_sim")
                if (
                    isinstance(raw_sim, dict)
                    and isinstance(raw_sim.get("personas"), list)
                    and len(raw_sim["personas"]) > 0
                ):
                    cached_sim = raw_sim

            if run_sim:
                if cached_sim:
                    sim_result = cached_sim
                    logging.info(
                        "Recruiter sim cache hit — skipping Agent 5 LLM call"
                    )
                else:
                    fut_sim = executor.submit(
                        self.recruiter_sim.run,
                        {
                            "resume_text": resume_text,
                            "resume_sections": resume_sections,
                            "jd_intelligence": jd_intel or {},
                            "ats_result": ats_result,
                            "role_family": resume_und.get("role_family", "ENGINEERING"),
                        },
                    )

            if fut_rewrite:
                try:
                    rewrites = fut_rewrite.result()
                    # Save A4 output to session store
                    try:
                        save_agent_output(uid, run_id, "rewriter", rewrites)
                    except Exception as e:
                        logging.warning("Failed to save rewriter to session store: %s", e)
                    if progress_cb: progress_cb({"step":3,"label":"Resume rewritten successfully","pct":90})
                    patches_raw = (rewrites or {}).get("patches", [])
                    if rewrites:
                        try:
                            from validator.rewriter_validator import RewriterValidator

                            validator = RewriterValidator()
                            rewrites = validator.validate_and_fix(
                                rewriter_output=rewrites,
                                resume_sections=resume_sections,
                                resume_text=resume_text,
                            )
                            resume_und["resume_sections"] = self._dump_sections(
                                resume_sections
                            )
                            if progress_cb: progress_cb({"step":3,"label":"Rewrite validated","pct":95})
                        except Exception as exc:
                            logging.warning(
                                "RewriterValidator failed: %s. Using raw rewriter output.",
                                exc,
                            )
                            if isinstance(rewrites, dict):
                                rewrite_map = rewrites.get("rewrites", {})
                                missing_sections = assert_structural_completeness(
                                    rewrite_map,
                                    resume_sections,
                                )
                                if missing_sections:
                                    rewrites["rewrites"] = backfill_missing_rewrite_sections(
                                        rewrite_map,
                                        resume_sections,
                                        missing_sections,
                                    )
                        log_experience_audit(
                            "post_rewriter_validator",
                            resume_text,
                            resume_sections,
                            rewrites.get("rewrites") if isinstance(rewrites, dict) else rewrites,
                        )
                        rewrite_map = rewrites.get("rewrites", {})
                        missing_sections = assert_structural_completeness(
                            rewrite_map,
                            resume_sections,
                        )
                        if missing_sections:
                            logging.error(
                                "Structural completeness FAILED — backfilling sections: %s",
                                missing_sections,
                            )
                            rewrites["rewrites"] = backfill_missing_rewrite_sections(
                                rewrite_map,
                                resume_sections,
                                missing_sections,
                            )
                        try:
                            from engine.ats_scorer import build_validation_summary

                            jd_match_before = (
                                gap_result.get("jd_match_score_before")
                                if has_jd else None
                            )
                            jd_match_after = (
                                gap_result.get("jd_match_score_after")
                                if has_jd else None
                            )
                            validation_summary = build_validation_summary(
                                original_resume_text=resume_text,
                                rewrites=(
                                    rewrites.get("rewrites", {})
                                    if isinstance(rewrites, dict) else {}
                                ),
                                patches=patches_raw,
                                jd_match_before=jd_match_before,
                                jd_match_after=jd_match_after,
                                jd_text=jd_text if has_jd else None,
                            )
                            logging.info(
                                "Validation summary — safe_fix: %s, full_rewrite: %s",
                                validation_summary["safe_fix"]["overall"],
                                validation_summary["full_rewrite"]["overall"],
                            )
                        except Exception as exc:
                            logging.warning(
                                "Validation summary failed: %s. Continuing without it.",
                                exc,
                            )
                except Exception as exc:
                    logging.warning("Rewriter failed: %s. Using gap-based fallback.", exc)
                    rewrites = self._build_gap_fallback_rewrites(gap_result)
                    patches_raw = []

            if fut_eval:
                try:
                    eval_gap = fut_eval.result()
                    estimated_after = eval_gap.get("estimated_score_after")
                    if isinstance(estimated_after, int):
                        gap_result["jd_match_score_after"] = estimated_after
                    else:
                        _ensure_jd_match_score_after(gap_result)
                    eval_changes = eval_gap.get("changes") or []
                    if eval_changes and isinstance(gap_result, dict):
                        gap_result["changes"] = eval_changes
                        gap_result["priority_fixes"] = enrich_priority_fixes_from_eval_changes(
                            gap_result.get("priority_fixes") or [],
                            eval_changes,
                            resume_sections,
                        )
                        if eval_gap.get("overall"):
                            gap_result["eval_overall"] = eval_gap["overall"]
                except Exception as exc:
                    logging.warning("Gap evaluate scoring failed: %s", exc)
                    if isinstance(gap_result, dict):
                        _ensure_jd_match_score_after(gap_result)

            if fut_sim:
                try:
                    sim_result = fut_sim.result()
                    # Save A5 output to session store
                    try:
                        save_agent_output(uid, run_id, "recruiter_sim", sim_result)
                    except Exception as e:
                        logging.warning("Failed to save recruiter_sim to session store: %s", e)
                    if stage_cache_cb and sim_result:
                        try:
                            stage_cache_cb({"recruiter_sim": sim_result})
                        except Exception as exc:
                            logging.warning(
                                "Failed to persist recruiter_sim to stage cache: %s",
                                exc,
                            )
                except Exception as exc:
                    logging.warning("Recruiter Sim (Agent 5) failed: %s. Continuing without simulation.", exc)

        record_phase("parallel_a4_eval_sim", (time.perf_counter() - _parallel_t0) * 1000)

        if has_jd and isinstance(gap_result, dict):
            _ensure_jd_match_score_after(gap_result)
        if partial_result_cb:
            partial_result_cb({"rewrites": rewrites, "gap": gap_result, "sim": sim_result})

        percentile = None
        try:
            seniority = resume_und.get("seniority", "mid")
            if hasattr(seniority, "value"):
                seniority = seniority.value
            match_score = (
                gap_result.get("match_score")
                or gap_result.get("jd_match_score_before")
                or 0
            )
            resume_only = (
                not has_jd
                or (
                    isinstance(gap_result, dict)
                    and gap_result.get("resume_only_mode", False)
                )
            )
            if resume_only:
                composite = float(ats_result["score"])
            else:
                composite = (ats_result["score"] * 0.4) + (match_score * 0.6)
            percentile = get_percentile(composite, seniority)
        except Exception as exc:
            logging.warning("Percentile calculation failed: %s. Returning null.", exc)

        if sse_step_cb:
            sse_step_cb(2, "Scores calculated")

        from engine.career_positioning import get_positioning_statement
        positioning = None
        try:
            _sen = resume_und.get("seniority", "mid")
            if hasattr(_sen, "value"): _sen = _sen.value
            positioning = get_positioning_statement(
                seniority=str(_sen),
                ats_score=ats_result.get("score", 0),
                jd_match_score=gap_result.get("jd_match_score_before", 0) if has_jd else 0,
                sections_changed=len(gap_result.get("sections_changed", [])),
                ats_breakdown=ats_result.get("breakdown", {}),
                ats_issues=ats_result.get("ats_issues", []),
                expected_signals=resume_und.get("resume_health", {}).get("expected_signals", []),
                percentile=percentile,
            )
        except Exception as e:
            logging.warning("Career positioning failed: %s", e)
        if partial_result_cb:
            partial_result_cb({"percentile": percentile, "positioning": positioning})

        if sse_step_cb:
            sse_step_cb(3, "Insights ready")

        # Classify and deduplicate patches
        classified_patches = []
        if patches_raw:
            try:
                from engine.patch_engine import PatchEngine, classify_patch
                from backend.schemas.common import ResumePatch

                for p in patches_raw:
                    try:
                        patch = ResumePatch(**p)
                        if not (patch.original_text or "").strip():
                            logging.warning(
                                "Invalid patch skipped (empty original_text): %s",
                                patch.patch_id,
                            )
                            continue
                        classify_patch(patch)
                        classified_patches.append(patch)
                    except Exception as e:
                        logging.warning("Invalid patch skipped: %s", e)

                classified_patches = PatchEngine.dedup([p for p in classified_patches])
            except Exception as exc:
                logging.warning("Patch classification failed: %s", exc)
                classified_patches = []

        final_result = {
            "api_version": 2,
            "session_id": run_id,
            "ats": ats_result,
            "resume": resume_und,
            "gap": gap_result,
            "rewrites": rewrites,
            "sim": sim_result,
            "percentile": percentile,
            "positioning": positioning,
            "jd_intelligence": jd_intel,
            "patches": [p.model_dump() if hasattr(p, "model_dump") else p for p in classified_patches],
            "validation": validation_summary,
            "role_fit": role_fit,
        }
        # Save full result to session store
        try:
            save_full_run_result(uid, run_id, final_result)
        except Exception as e:
            logging.warning("Failed to save full run result to session store: %s", e)
        log_trace_summary()
        return final_result
