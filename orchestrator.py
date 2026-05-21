"""
Orchestrator module for Resume Intelligence Platform V2.
"""

from __future__ import annotations

import logging
import re
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from memory.session_store import (
    generate_run_id,
    save_agent_output,
    save_full_run_result,
)
from backend.agents.gap_analyzer import GapAnalyzerAgent
from backend.agents.jd_intelligence import JDIntelligenceAgent
from backend.agents.recruiter_sim import RecruiterSimulatorAgent
from backend.agents.resume_understanding import ResumeUnderstandingAgent
from backend.agents.sectioner_agent import SectionerAgent
from backend.agents.rewriter import RewriterAgent
from backend.role_fit import compute_role_fit
from engine.ats_scorer import score_resume
from engine.percentile import get_percentile
from validators import ResumeUnderstandingValidator
from validator.rewriter_validator import assert_structural_completeness
from validator.experience_audit import (
    ensure_experience_completeness,
    log_experience_audit,
)


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

        # Accumulate per-section rewrite instructions
        section_instructions: dict[str, list[str]] = {s: [] for s in canonical_sections}

        for area in improvement_areas:
            section_instructions[_route_to_section(area)].append(area)

        for weakness in weaknesses:
            # Extract the fix suggestion after → if present; otherwise use the full text
            fix = weakness.split("→", 1)[-1].strip() if "→" in weakness else weakness
            section_instructions[_route_to_section(weakness)].append(fix)

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
                    # Find weaknesses that mention this entry's company
                    company_token = (
                        entry_label.split("|")[0]
                        .split("—")[0]
                        .strip()
                        .lower()
                    )
                    matching = [
                        w for w in weaknesses
                        if company_token and len(company_token) > 2
                        and company_token in w.lower()
                    ]
                    if matching:
                        fix = (
                            matching[0].split("→", 1)[-1].strip()
                            if "→" in matching[0]
                            else "Improve impact clarity and add quantified metrics."
                        )
                        sub_changes.append({
                            "sub_id": f"{company_token}_no_jd",
                            "sub_label": entry_label,
                            "needs_change": True,
                            "gap_reason": matching[0],
                            "rewrite_instruction": fix,
                            "missing_keywords": [],
                            "original_text": entry_verbatim,
                        })

            needs_change = bool(instructions) or bool(sub_changes)
            rewrite_instruction = " ".join(instructions[:3]) if instructions else ""

            section_gaps.append({
                "section": section,
                "needs_change": needs_change,
                "gap_reason": rewrite_instruction or "No change needed",
                "missing_keywords": [],
                "rewrite_instruction": rewrite_instruction,
                "original_content": original_content,
                "present_in_resume": bool(original_content),
                "sub_changes": sub_changes,
            })

        # Top-level result — matches GapAnalyzerOutput shape
        priority_fixes = improvement_areas[:3]

        return {
            "section_gaps": section_gaps,
            "gaps": section_gaps,           # rewriter reads either key
            "missing_keywords": [],
            "priority_fixes": priority_fixes,
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
        if progress_cb: progress_cb({"step":1,"label":"Reading your resume...","pct":10})
        has_jd = bool(jd_text and jd_text.strip())
        ats_result = score_resume(resume_text, jd_text if has_jd else None)
        if partial_result_cb:
            partial_result_cb({"ats": ats_result})

        cache_hit = bool(cached_stage_data)
        if cache_hit:
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
                    resume_sections[sec_name] = SectionText(
                        header=sec_name,
                        full_text=sec_text.strip(),
                        sub_entries=[],
                    )
        else:
            if has_jd:
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
                resume_und = self.resume_understanding.run({
                    "resume_text": resume_text,
                    "user_id": uid,
                })
                jd_intel = None

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
                    resume_sections[sec_name] = SectionText(
                        header=sec_name,
                        full_text=sec_text.strip(),
                        sub_entries=[],
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

        if has_jd:
            if progress_cb: progress_cb({"step":2,"label":"Analyzing gaps against JD...","pct":45})
            resume_sections = self._merge_sectioner_into_sections(
                resume_sections, resume_text, resume_und
            )
            resume_sections = self._sync_experience_sections(
                resume_sections, resume_text, resume_und
            )
            gap_result = self.gap_analyzer.run({
                "resume_understanding": resume_und,
                "jd_intelligence": jd_intel,
                "resume_text": resume_text,
                "resume_sections": resume_sections,
                "jd_text": jd_text,
                "mode": "gap_closer",
            })
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

        rewrites = None
        eval_gap = None
        sim_result = None
        patches_raw = []
        validation_summary = None
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
            if run_sim:
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
                        log_experience_audit(
                            "post_rewriter_validator",
                            resume_text,
                            resume_sections,
                            rewrites.get("rewrites") if isinstance(rewrites, dict) else rewrites,
                        )
                        missing_sections = assert_structural_completeness(
                            rewrites.get("rewrites", {}),
                            resume_sections,
                        )
                        if missing_sections:
                            logging.error(
                                "Structural completeness FAILED — sections missing from "
                                "rewrites: %s. Docx will be incomplete.",
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
                except Exception as exc:
                    logging.warning("Gap evaluate scoring failed: %s", exc)

            if fut_sim:
                try:
                    sim_result = fut_sim.result()
                    # Save A5 output to session store
                    try:
                        save_agent_output(uid, run_id, "recruiter_sim", sim_result)
                    except Exception as e:
                        logging.warning("Failed to save recruiter_sim to session store: %s", e)
                except Exception as exc:
                    logging.warning("Recruiter Sim (Agent 5) failed: %s. Continuing without simulation.", exc)
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
                        classify_patch(patch)
                        classified_patches.append(patch)
                    except Exception as e:
                        logging.warning("Invalid patch skipped: %s", e)

                classified_patches = PatchEngine.dedup([p for p in classified_patches])
            except Exception as exc:
                logging.warning("Patch classification failed: %s", exc)
                classified_patches = []

        role_fit = None
        try:
            if has_jd and jd_intel and resume_und:
                role_fit = compute_role_fit(resume_und, jd_intel, gap_result or {})
                logging.info(
                    "Role fit — fitness: %s, score: %s, exp_gap: %s, seniority_gap: %s",
                    role_fit["fitness"],
                    role_fit["score"],
                    role_fit["experience_gap"],
                    role_fit["seniority_gap"],
                )
        except Exception as exc:
            logging.warning("Role fit computation failed: %s", exc)

        final_result = {
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
        return final_result
