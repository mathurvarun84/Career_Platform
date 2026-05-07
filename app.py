import json
import os
import tempfile

import streamlit as st

from agents.gap_analyzer import GapAnalyzerAgent
from agents.jd_intelligence import JDIntelligenceAgent
from agents.recruiter_sim import RecruiterSimulatorAgent
from agents.resume_understanding import ResumeUnderstandingAgent
from agents.rewriter import RewriterAgent
from agents.sectioner_agent import SectionerAgent
from schemas.common import SectionText, SubEntry
from engine.ats_scorer import score_resume
from engine.resume_builder import build_final_docx
from orchestrator import Orchestrator
from validators import ResumeUnderstandingValidator, RewriterValidator


EXPECTED_RECRUITER_SIM_MODEL = "claude-haiku-4-5-20251001"

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()
else:
    current_sim = getattr(st.session_state.orchestrator, "recruiter_sim", None)
    if getattr(current_sim, "model", None) != EXPECTED_RECRUITER_SIM_MODEL:
        st.session_state.orchestrator = Orchestrator()


@st.cache_data(show_spinner=False)
def read_upload(file) -> str:
    if file is None:
        return ""
    try:
        suffix = os.path.splitext(file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name

        from parser import parse_resume

        text = parse_resume(tmp_path)
        os.unlink(tmp_path)
        return text
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        return ""


def _extract_header_info(resume_text: str) -> tuple[str, str]:
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    candidate_name = lines[0] if lines else "Candidate"
    contact_line = ""
    for line in lines[1:6]:
        lowered = line.lower()
        if any(token in lowered for token in ("@", "|", "+91", "+1", "linkedin", "github", ".com")):
            contact_line = line
            break
    return candidate_name, contact_line


st.set_page_config(page_title="Resume Intelligence Platform", layout="wide")
tabs = st.tabs(["Evaluate", "Recruiter Sim", "Gap Closer"])


# ══════════════════════════════════════════════════════
# TAB 0 — EVALUATE: standalone resume health check
# Answers: "How strong is this resume as a document?"
# ══════════════════════════════════════════════════════
with tabs[0]:
    st.title("Resume Evaluation")
    col1, col2 = st.columns([1, 1])

    with col1:
        resume_file = st.file_uploader("Upload Resume (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"], key="upload_resume")
        jd_text = st.text_area("Job Description (optional)", key="jd_text")
        run_simulation = st.checkbox("Run Recruiter Simulation", value=False)

        if st.button("Evaluate Resume"):
            status = st.empty()
            bar = st.progress(0)
            status.info("Step 1/5: Reading uploaded resume...")
            resume_text = read_upload(resume_file)
            if not resume_text:
                bar.empty()
                status.empty()
                st.error("Please upload a resume file.")
            else:
                try:
                    bar.progress(15)
                    status.info("Step 2/5: Scoring ATS and sectioning resume...")
                    bar.progress(30)

                    status.info("Step 3/5: Running resume intelligence analysis...")
                    result = st.session_state.orchestrator.run_full_evaluation(
                        resume_text=resume_text,
                        jd_text=jd_text if jd_text.strip() else None,
                        run_sim=run_simulation,
                    )
                    bar.progress(75)

                    status.info("Step 4/5: Saving analysis results...")
                    st.session_state.eval_result = result
                    st.session_state["ats_output"] = result.get("ats", {})
                    st.session_state["resume_health"] = result.get("resume", {}).get("resume_health", {})
                    st.session_state["parsed_resume_text"] = resume_text
                    st.session_state["candidate_name"], st.session_state["contact_line"] = _extract_header_info(resume_text)
                    st.session_state["agent1_output"] = result.get("resume", {})
                    if result.get("sim"):
                        st.session_state["sim_result"] = result.get("sim")
                    if jd_text.strip():
                        status.info("Step 5/5: Preparing JD intelligence cache...")
                        st.session_state["agent2_output"] = JDIntelligenceAgent().run({"jd_text": jd_text})
                        st.session_state["gap_jd"] = jd_text
                    st.session_state["resume_text_cached"] = resume_text
                    bar.progress(100)
                    status.success("Evaluation complete.")
                except Exception as e:
                    status.empty()
                    bar.empty()
                    st.error(f"Evaluation failed: {e}")
                    st.exception(e)

    if st.session_state.get("ats_output") and st.session_state.get("resume_health"):
        ats    = st.session_state["ats_output"]
        health = st.session_state["resume_health"]
        agent2 = st.session_state.get("agent2_output", {})

        eval_result = st.session_state.get("eval_result", {}) or {}

        # VerdictBanner
        ats_score = (eval_result.get("ats") or {}).get("score")
        gap_data = eval_result.get("gap") or {}
        jd_score = gap_data.get("jd_match_score_before", gap_data.get("match_score"))
        percentile_data = eval_result.get("percentile") or {}
        market_rank = percentile_data.get("label", percentile_data.get("percentile"))
        has_jd = bool(st.session_state.get("agent2_output"))

        def verdict_color(score):
            if score is None:
                return "#9ca3af"
            if score >= 75:
                return "#22c55e"
            if score >= 50:
                return "#f9a825"
            return "#ef4444"

        ats_display = f"{ats_score}" if ats_score is not None else "--"
        jd_display = f"{jd_score}%" if has_jd and jd_score is not None else "--"
        jd_color = verdict_color(jd_score) if has_jd else "#9ca3af"
        market_display = str(market_rank) if market_rank is not None else "--"

        st.markdown(
            f"""
            <div style="
                background:#1a1a2e;
                border:1px solid rgba(255,255,255,0.08);
                border-radius:8px;
                padding:18px 20px;
                display:grid;
                grid-template-columns:repeat(3,1fr);
                gap:16px;
                text-align:center;
                margin-bottom:18px;
            ">
                <div>
                    <div style="font-size:34px;font-weight:800;color:{verdict_color(ats_score)};line-height:1;">{ats_display}</div>
                    <div style="font-size:13px;color:#aab0c0;margin-top:8px;">ATS Score</div>
                </div>
                <div>
                    <div style="font-size:34px;font-weight:800;color:{jd_color};line-height:1;">{jd_display}</div>
                    <div style="font-size:13px;color:#aab0c0;margin-top:8px;">JD Match</div>
                </div>
                <div>
                    <div style="font-size:34px;font-weight:800;color:#9ca3af;line-height:1;">{market_display}</div>
                    <div style="font-size:13px;color:#aab0c0;margin-top:8px;">Market Rank</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Why this Market Rank? →"):
            rank_rationale = (eval_result.get("positioning") or {}).get("rank_rationale")
            if rank_rationale:
                st.markdown(
                    f'<div style="background:#1a1a2e;border-left:4px solid #f9a825;border-radius:8px;'
                    f'padding:14px 16px;margin-bottom:14px;color:#f5f7fb;font-size:14px;line-height:1.45;">'
                    f'{rank_rationale}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            ats_breakdown = (eval_result.get("ats") or {}).get("breakdown", {}) or {}
            subscore_labels = {
                "keyword_match": "Keyword Match",
                "formatting": "Formatting",
                "readability": "Readability",
                "impact_metrics": "Impact Metrics",
            }
            subscore_cards = []
            for key, label in subscore_labels.items():
                score = ats_breakdown.get(key, 0) or 0
                bar_color = "#22c55e" if score >= 18 else "#f9a825" if score >= 12 else "#ef4444"
                bar_width = min(max(score, 0), 25) * 4
                subscore_cards.append(
                    f'<div style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:12px;">'
                    f'<div style="font-size:12px;color:#aab0c0;margin-bottom:6px;">{label}</div>'
                    f'<div style="font-size:22px;font-weight:800;color:{bar_color};line-height:1;">{score}/25</div>'
                    f'<div style="background:rgba(255,255,255,0.08);height:5px;border-radius:999px;margin-top:10px;overflow:hidden;">'
                    f'<div style="background:{bar_color};width:{bar_width}%;height:5px;border-radius:999px;"></div>'
                    f'</div>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;">'
                f'{"".join(subscore_cards)}'
                f'</div>',
                unsafe_allow_html=True,
            )

            ats_issues = (eval_result.get("ats") or {}).get("ats_issues", []) or []
            if ats_issues:
                issues_html = "".join(
                    f'<li style="margin-bottom:4px;">{issue}</li>'
                    for issue in ats_issues
                )
                st.markdown(
                    f'<div style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:14px 16px;">'
                    f'<div style="font-size:14px;font-weight:700;color:#f5f7fb;margin-bottom:8px;">What to fix:</div>'
                    f'<ul style="font-size:13px;color:#d1d5db;margin:0;padding-left:18px;">'
                    f'{issues_html}'
                    f'</ul>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        # CareerPositioning
        positioning = eval_result.get("positioning")
        if positioning is not None:
            priority_fixes = (eval_result.get("gap") or {}).get("priority_fixes", []) or []
            if priority_fixes:
                fix_header = "Top fixes to close the gap:"
                fixes = priority_fixes[:3]
            else:
                resume_health = (
                    (eval_result.get("resume") or {}).get("resume_health")
                    or eval_result.get("resume_health")
                    or health
                    or {}
                )
                signals = resume_health.get("expected_signals", []) or []
                fixes = [
                    s["inline_fix"]
                    for s in signals
                    if not s.get("present") and s.get("inline_fix")
                ][:3]
                fix_header = "Top fixes to strengthen your resume:"

            fix_items_html = ""
            if fixes:
                fix_items_html = (
                    f'<div style="font-size:14px;font-weight:700;color:#f5f7fb;margin-top:14px;margin-bottom:6px;">{fix_header}</div>'
                    '<ol style="margin:0;padding-left:20px;">'
                    + "".join(
                        f'<li style="font-size:13px;color:#f9a825;margin-bottom:4px;">{fix}</li>'
                        for fix in fixes
                    )
                    + "</ol>"
                )

            st.markdown(
                f"""
                <div style="
                    background:#1a1a2e;
                    border-left:4px solid #f9a825;
                    border-radius:8px;
                    padding:18px 20px;
                    margin-bottom:18px;
                    border-top:1px solid rgba(255,255,255,0.06);
                    border-right:1px solid rgba(255,255,255,0.06);
                    border-bottom:1px solid rgba(255,255,255,0.06);
                ">
                    <div style="font-size:20px;font-weight:700;color:#f5f7fb;margin-bottom:8px;">
                        {positioning.get("positioning_line", "")}
                    </div>
                    <div style="font-size:14px;font-weight:600;color:#f9a825;margin-bottom:6px;">
                        {positioning.get("delta_line", "")}
                    </div>
                    <div style="font-size:13px;color:#9ca3af;font-style:italic;">
                        {positioning.get("cta_line", "")}
                    </div>
                    {fix_items_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        # ── SECTION 1: ATS Score Breakdown ──
        st.subheader("ATS Score Breakdown")

        total = ats.get("score", 0)
        breakdown = ats.get("breakdown", {})

        color = "#43a047" if total >= 75 else "#f9a825" if total >= 50 else "#e53935"
        st.markdown(
            f'<div style="background:#f5f5f5;border-radius:8px;padding:16px;'
            f'text-align:center;margin-bottom:16px">'
            f'<div style="font-size:48px;font-weight:bold;color:{color}">{total}</div>'
            f'<div style="font-size:14px;color:#666">ATS Score / 100</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        SUB_LABELS = {
            "keyword_match": "Keyword Match",
            "formatting": "Formatting",
            "readability": "Readability",
            "impact_metrics": "Impact Metrics",
        }
        for key, label in SUB_LABELS.items():
            val = breakdown.get(key, 0)
            pct = int((val / 25) * 100)
            bar_color = "#43a047" if pct >= 75 else "#f9a825" if pct >= 50 else "#e53935"
            st.markdown(
                f'<div style="display:flex;align-items:center;margin:6px 0">'
                f'<div style="width:160px;font-size:13px">{label}</div>'
                f'<div style="flex:1;background:#f0f0f0;border-radius:4px;height:18px">'
                f'<div style="width:{pct}%;background:{bar_color};height:18px;'
                f'border-radius:4px"></div></div>'
                f'<div style="width:60px;text-align:right;font-size:13px;font-weight:bold;'
                f'margin-left:8px">{val}/25</div></div>',
                unsafe_allow_html=True,
            )

        issues = ats.get("ats_issues", [])
        if issues:
            st.markdown("**ATS Issues Detected:**")
            for issue in issues:
                st.markdown(
                    f'<div style="background:#fff3e0;border-left:3px solid #f57c00;'
                    f'padding:6px 12px;border-radius:4px;margin:3px 0;font-size:13px">'
                    f'\u2022 {issue}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── SECTION 2: Seniority Health Check ──
        st.subheader("Seniority Health Check")
        st.caption(
            f"Evaluated against signals expected at "
            f"**{health.get('seniority_detected', '').upper()}** level."
        )

        signals = health.get("expected_signals", [])
        present_count = sum(1 for s in signals if s.get("present"))
        total_count = len(signals)

        for sig in signals:
            icon = "\u2705" if sig.get("present") else "\u274C"
            bg = "#f1f8e9" if sig.get("present") else "#fff3f3"
            border = "#43a047" if sig.get("present") else "#e53935"
            fix_html = ""
            if not sig.get("present") and sig.get("inline_fix"):
                fix_html = (
                    f'<div style="font-size:11px;color:#e53935;margin-top:3px">'
                    f'\u2192 {sig["inline_fix"]}</div>'
                )
            location_html = ""
            if sig.get("location"):
                location_html = (
                    f'<span style="font-size:11px;color:#888;margin-left:8px">'
                    f'[{sig["location"]}]</span>'
                )
            st.markdown(
                f'<div style="background:{bg};border-left:3px solid {border};'
                f'padding:8px 12px;border-radius:4px;margin:4px 0">'
                f'{icon} <strong>{sig["signal"]}</strong>{location_html}'
                f'{fix_html}</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div style="font-size:13px;color:#555;margin-top:8px">'
            f'Signals present: {present_count}/{total_count}</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # ── SECTION 3: Strengths & Weaknesses ──
        st.subheader("Resume Assessment")
        st.caption(health.get("overall_health", ""))

        col_s, col_w = st.columns(2)
        with col_s:
            st.markdown("**Strengths**")
            for s in health.get("strengths", []):
                st.markdown(
                    f'<div style="background:#f1f8e9;border-left:3px solid #43a047;'
                    f'padding:8px 12px;border-radius:4px;margin:4px 0;font-size:13px">'
                    f'\u2022 {s}</div>',
                    unsafe_allow_html=True,
                )

        with col_w:
            st.markdown("**Weaknesses & Fixes**")
            for w in health.get("weaknesses", []):
                parts = w.split("\u2192", 1)
                weakness_text = parts[0].strip()
                fix_text = parts[1].strip() if len(parts) > 1 else ""
                fix_html = ""
                if fix_text:
                    fix_html = (
                        f"<div style='font-size:11px;color:#e53935;margin-top:4px'>"
                        f"\u2192 {fix_text}</div>"
                    )
                st.markdown(
                    f'<div style="background:#fff3f3;border-left:3px solid #e53935;'
                    f'padding:8px 12px;border-radius:4px;margin:4px 0;font-size:13px">'
                    f'\u2022 {weakness_text}'
                    f'{fix_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── SECTION 4: JD CTA (if JD provided) ──
        if agent2:
            jd_score = (
                st.session_state.get("gap_output", {})
                .get("jd_match_score_before")
            )
            if jd_score:
                score_html = f'JD Match Score: <strong>{jd_score}%</strong> \u2014 '
            else:
                score_html = ""
            st.markdown(
                f'<div style="background:#e8f4fd;border:1px solid #90caf9;'
                f'border-radius:8px;padding:16px;text-align:center">'
                f'<div style="font-size:14px;color:#1565c0;margin-bottom:8px">'
                f'JD detected. {score_html}'
                f'Go to <strong>Gap Closer</strong> to see exact rewrites for this JD.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#f5f5f5;border:1px solid #ddd;border-radius:8px;'
                'padding:16px;text-align:center;font-size:13px;color:#666">'
                'Paste a Job Description in the sidebar to unlock JD match score '
                'and targeted rewrites in the Gap Closer tab.</div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════
# TAB 1 — RECRUITER SIM
# ══════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Recruiter Simulator")
    st.caption(
        "Simulates 5 recruiter personas evaluating your resume. "
        "Optionally add a JD to get role-specific verdicts."
    )

    with st.expander("Add Job Description (optional - for role-specific simulation)", expanded=False):
        sim_jd_text = st.text_area(
            "Paste JD here",
            height=200,
            key="sim_jd_text",
            placeholder="Leave blank to run general market simulation...",
        )
        if sim_jd_text.strip():
            st.info(
                "JD detected - simulation will evaluate fit against this "
                "specific role across all 5 personas."
            )
        else:
            st.info(
                "No JD - simulation will evaluate resume against general "
                "Indian tech market standards."
            )

    run_sim = st.button("Run Recruiter Simulation", type="primary")

    if run_sim:
        if "agent1_output" not in st.session_state:
            st.error("Upload and analyze a resume first (Evaluate tab).")
            st.stop()

        status = st.empty()
        bar = st.progress(0)
        try:
            status.info("Step 1/4: Preparing JD context...")
            bar.progress(15)
            sim_jd_intel = None
            if sim_jd_text.strip():
                if (
                    st.session_state.get("gc_jd_cached") == sim_jd_text.strip()
                    and "agent2_output" in st.session_state
                ):
                    sim_jd_intel = st.session_state["agent2_output"]
                else:
                    sim_jd_intel = JDIntelligenceAgent().run(
                        {"jd_text": sim_jd_text.strip()}
                    )
            bar.progress(35)

            status.info("Step 2/4: Formatting resume sections...")
            if "resume_sections" not in st.session_state:
                resume_text = st.session_state.get("parsed_resume_text", "")
                if resume_text:
                    st.session_state["resume_sections"] = SectionerAgent().run({
                        "resume_text": resume_text,
                    })
            bar.progress(55)

            status.info("Step 3/4: Simulating 5 recruiter personas...")
            sim_result = RecruiterSimulatorAgent().run({
                "resume_text": st.session_state.get("parsed_resume_text", ""),
                "resume_sections": st.session_state.get("resume_sections", {}),
                "jd_intelligence": sim_jd_intel,
            })
            bar.progress(90)

            status.info("Step 4/4: Building verdict dashboard...")
            st.session_state["sim_result"] = sim_result
            bar.progress(100)
            status.success("Recruiter simulation complete.")

        except Exception as e:
            status.empty()
            bar.empty()
            st.error(f"Simulation failed: {e}")
            st.stop()

    sim_result = st.session_state.get("sim_result")
    if not sim_result:
        st.info("Run the simulation to see recruiter verdicts.")
    else:
        rate = sim_result.get("shortlist_rate", 0)
        personas = sim_result.get("personas", [])
        avg_fit = round(
            sum(p.get("fit_score", 0) for p in personas) / len(personas), 1
        ) if personas else 0

        col1, col2 = st.columns(2)
        col1.metric(
            "Shortlist Rate",
            f"{int(rate * 100)}%",
            help="% of 5 personas who would shortlist you",
        )
        col2.metric(
            "Avg Fit Score",
            f"{avg_fit}/100",
            help="Average fit score across all personas",
        )

        fix_priority = sim_result.get("fix_priority", [])
        if fix_priority:
            st.subheader("Priority Fixes")
            st.caption(
                "Ranked by how many personas each fix would unblock. "
                "Fix the top item first."
            )
            for i, fix in enumerate(fix_priority[:5], 1):
                persona_names = ", ".join(fix["personas"])
                with st.expander(
                    f"#{i} - Unblocks {fix['persona_count']} personas "
                    f"(avg fit: {fix['avg_fit_score']}/100)",
                    expanded=(i == 1),
                ):
                    st.write(fix["fix"])
                    st.caption(f"Blocked personas: {persona_names}")

        st.divider()

        st.subheader("Persona Verdicts")
        cols = st.columns(2)
        for i, persona in enumerate(personas):
            col = cols[i % 2]
            with col:
                shortlisted = persona.get("shortlist_decision", False)
                fit = persona.get("fit_score", 0)
                decision_label = "Shortlisted" if shortlisted else "Rejected"

                with st.container(border=True):
                    st.markdown(
                        f"**{persona.get('persona', '')}** - "
                        f"{decision_label} | Fit: {fit}/100"
                    )
                    st.caption(persona.get("first_impression", ""))

                    if persona.get("noticed"):
                        st.markdown("**Noticed:**")
                        for n in persona["noticed"]:
                            st.markdown(f"- {n}")

                    if not shortlisted:
                        if persona.get("rejection_reason"):
                            st.markdown(
                                f"**Rejection reason:** {persona['rejection_reason']}"
                            )
                        if persona.get("flip_condition"):
                            st.markdown(
                                f"**To flip this verdict:** {persona['flip_condition']}"
                            )

        st.divider()

        st.subheader("Consensus")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Strengths (3+ personas)**")
            for s in sim_result.get("consensus_strengths", []):
                st.markdown(f"- {s}")
        with c2:
            st.markdown("**Weaknesses (3+ personas)**")
            for w in sim_result.get("consensus_weaknesses", []):
                st.markdown(f"- {w}")

        st.info(f"**Most critical fix:** {sim_result.get('most_critical_fix', '')}")


# ══════════════════════════════════════════════════════
# TAB 2 — GAP CLOSER: JD-specific rewrite workflow
# Answers: "How do I rewrite this for THIS JD?"
# ══════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Gap Closer")
    st.caption("Paste a JD to see exactly what to change and get a rewritten resume.")

    jd_text      = st.text_area("Job Description", height=180, key="gc_jd")
    style_choice = st.selectbox(
        "Rewrite Style",
        ["balanced", "aggressive", "top_1_percent"],
        format_func=lambda x: {
            "balanced":      "Balanced \u2014 honest and strong",
            "aggressive":    "Aggressive \u2014 maximum keyword density",
            "top_1_percent": "Top 1% \u2014 tier-1 company framing",
        }[x]
    )

    if st.button("Find & Close Gaps", type="primary"):
        status = st.empty()
        bar = st.progress(0)
        status.info("Starting gap closer...")

        if not st.session_state.get("parsed_resume_structured"):
            # Build structured resume from parsed text
            resume_text = st.session_state.get("parsed_resume_text", "")
            if resume_text:
                status.info("Preparing your parsed resume...")
                bar.progress(5)
                from parser import _build_structured_resume
                st.session_state["parsed_resume_structured"] = _build_structured_resume(resume_text)
                # Also build agent1_output if missing
                resume_text = st.session_state.get("parsed_resume_text", "")
                if not st.session_state.get("agent1_output"):
                    status.info("Reading resume strengths and weaknesses...")
                    bar.progress(10)
                    st.session_state["agent1_output"] = ResumeUnderstandingAgent().run({
                        "resume_text": resume_text,
                        "user_id": "streamlit_gc",
                    })
                    st.session_state["agent1_output"] = ResumeUnderstandingValidator().validate_and_fix(
                        st.session_state["agent1_output"],
                        resume_text,
                    )
            else:
                st.error("Upload a resume first in the Evaluate tab.")
                st.stop()

        # Generate sectioner data for gap analysis and rewriter
        if st.session_state.get("agent1_output") and st.session_state.get("parsed_resume_text"):
            st.session_state["agent1_output"] = ResumeUnderstandingValidator().validate_and_fix(
                st.session_state["agent1_output"],
                st.session_state["parsed_resume_text"],
            )

        if "resume_sections" not in st.session_state:
            resume_text = st.session_state.get("parsed_resume_text", "")
            if resume_text:
                status.info("Splitting resume into sections...")
                bar.progress(12)
                resume_sections = st.session_state.get("agent1_output", {}).get("resume_sections", {})
                if not resume_sections:
                    resume_sections = SectionerAgent().run({"resume_text": resume_text})
                # Fallback if sectioner returns empty dict
                if not resume_sections:
                    # Build minimal sections from parsed_resume_structured
                    structured = st.session_state.get("parsed_resume_structured", {})
                    resume_sections = {}
                    for section_name in ["summary", "skills", "experience", "education", "certifications", "awards"]:
                        content = structured.get(section_name, "")
                        if isinstance(content, list):
                            content = "\n".join(str(item) for item in content)
                        resume_sections[section_name] = SectionText(
                            header=section_name,
                            full_text=str(content) if content else "",
                            sub_entries=[]
                        )
                st.session_state["resume_sections"] = resume_sections
            else:
                st.error("Resume text missing.")
                st.stop()

        if not jd_text.strip():
            st.error("Paste a job description above.")
            st.stop()

        try:
            # Ensure agent2_output (JD analysis)
            if "agent2_output" not in st.session_state or st.session_state.get("gc_jd_cached") != jd_text:
                status.info("Reading the job description...")
                bar.progress(14)
                st.session_state["agent2_output"] = JDIntelligenceAgent().run({"jd_text": jd_text})
                st.session_state["gc_jd_cached"] = jd_text

            status.info("Step 1/3: Analyzing gaps between resume and JD...")
            bar.progress(15)

            # Agent 3 evaluate mode -> DetailedEvalOutput (per-change cards)
            eval_output = GapAnalyzerAgent().run({
                "resume_analysis": st.session_state["agent1_output"],
                "jd_analysis":     st.session_state["agent2_output"],
                "resume_text":     st.session_state.get("parsed_resume_text", ""),
                "jd_text":         jd_text,
                "resume_sections": st.session_state["resume_sections"],
                "mode": "evaluate",
            })
            st.session_state["eval_output"] = eval_output
            bar.progress(35)

            # Agent 3 gap_closer mode -> GapAnalyzerOutput (section rewrites)
            status.info("Step 2/3: Building section-level rewrite plan...")
            gap_output = GapAnalyzerAgent().run({
                "resume_analysis": st.session_state["agent1_output"],
                "jd_analysis":     st.session_state["agent2_output"],
                "resume_text":     st.session_state.get("parsed_resume_text", ""),
                "jd_text":         jd_text,
                "resume_sections": st.session_state["resume_sections"],
                "mode": "gap_closer",
            })
            st.session_state["gap_output"] = gap_output
            # DEBUG
            #st.write("gap_output keys:", list(gap_output.keys()))
            #st.write("section_gaps length:", len(gap_output.get("section_gaps", [])))
            bar.progress(55)

            # Agent 4 -> rewrites only changed sections
            status.info("Step 3/3: Rewriting sections that need changes...")
            rewrite_output = RewriterAgent().run({
                "resume_text":       st.session_state.get("parsed_resume_text", ""),
                "resume_sections":   st.session_state["resume_sections"],
                "gaps":              gap_output.get("section_gaps", []),
                "style_fingerprint": st.session_state.get("style_fingerprint", ""),
            })
            rewrite_output = RewriterValidator().validate_and_fix(
                rewrite_output,
                st.session_state["resume_sections"],
                st.session_state.get("parsed_resume_text", ""),
            )
            st.session_state["rewrite_output"] = rewrite_output
            # DEBUG
            #st.write("rewrite_output keys:", list(rewrite_output.keys()))
            #st.write("sections in rewrites:", list(rewrite_output.get("rewrites", {}).keys()))
            #st.write("sections in resume_sections:", list(st.session_state["resume_sections"].keys()))
            bar.progress(85)

            # ATS score after rewrite (deterministic, no LLM)
            assembled = {
                s: rewrite_output["rewrites"].get(s, {}).get(style_choice, "")
                for s in rewrite_output["rewrites"]
            }
            score_after = score_resume(
                " ".join(assembled.values()),
                jd_text if jd_text.strip() else None,
            )["score"]
            st.session_state.update({
                "score_after":         score_after,
                "assembled_sections":  assembled,
                "gap_closer_complete": True,
                "gap_closer_style":    style_choice,
            })
            bar.progress(100)
            status.success("Done! Review your changes below.")

        except Exception as e:
            st.error(f"Failed: {e}")
            st.exception(e)
            st.stop()

    # ══════════════════════════════════════════════════
    # RESULTS — shown after button completes
    # ══════════════════════════════════════════════════
    if st.session_state.get("gap_closer_complete"):
        eval_out = st.session_state.get("eval_output", {})
        gap_out  = st.session_state["gap_output"]
        agent2   = st.session_state.get("agent2_output", {})
        before   = eval_out.get("jd_match_score_before", 0)
        estimated_after = eval_out.get("estimated_score_after", 0)
        changes  = eval_out.get("changes", [])
        critical = [c for c in changes if c.get("priority") == "critical"]
        high     = [c for c in changes if c.get("priority") == "high"]

        # ── BLOCK A: JD Screening Radar ──
        st.subheader("What This JD Is Screening For")
        must_have    = agent2.get("must_have_skills", [])
        nice_to_have = agent2.get("nice_to_have_skills", [])
        resume_text  = st.session_state.get("parsed_resume_text", "").lower()

        col_must, col_nice = st.columns(2)
        with col_must:
            st.markdown("**Must-Have (Dealbreakers)**")
            for skill in must_have:
                present = skill.lower() in resume_text
                icon = "\u2705" if present else "\u274C"
                bg   = "#e8f5e9" if present else "#ffebee"
                bdr  = "#43a047" if present else "#e53935"
                st.markdown(
                    f'<div style="background:{bg};border-left:3px solid {bdr};'
                    f'padding:6px 12px;border-radius:4px;margin:3px 0;font-size:13px">'
                    f'{icon} {skill}</div>',
                    unsafe_allow_html=True,
                )
        with col_nice:
            st.markdown("**Nice-to-Have**")
            for skill in nice_to_have[:6]:
                present = skill.lower() in resume_text
                icon = "\u2705" if present else "\u2196"
                bg   = "#e8f5e9" if present else "#fff8e1"
                bdr  = "#43a047" if present else "#f9a825"
                st.markdown(
                    f'<div style="background:{bg};border-left:3px solid {bdr};'
                    f'padding:6px 12px;border-radius:4px;margin:3px 0;font-size:13px">'
                    f'{icon} {skill}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── BLOCK B: Score Delta ──
        st.subheader("Score Impact")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("JD Match Now", f"{before}%")
        c2.metric("After Fixing Critical", f"{estimated_after}%",
                  delta=f"+{estimated_after - before}%" if estimated_after else None)
        c3.metric("Critical", len(critical))
        c4.metric("High Impact", len(high))

        st.divider()

        # ── BLOCK C: Per-Change Cards ──
        st.subheader("Actionable Changes — What to Fix & How")
        st.caption("Every card shows the exact original text and a complete ready-to-paste rewrite.")

        PRIORITY_ICON  = {"critical": "\U0001F534", "high": "\U0001F7E0", "medium": "\U0001F7E1"}
        PRIORITY_LABEL = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM"}
        PRIORITY_BG    = {"critical": "#ffebee", "high": "#fff3e0", "medium": "#fffde7"}
        PRIORITY_BDR   = {"critical": "#e53935", "high": "#f57c00", "medium": "#f9a825"}

        # Count pills
        st.markdown(
            f'<div style="display:flex;gap:10px;margin-bottom:12px">'
            + "".join([
                f'<div style="background:{PRIORITY_BG[p]};border:1px solid {PRIORITY_BDR[p]};'
                f'border-radius:6px;padding:5px 14px;font-size:13px">'
                f'{PRIORITY_ICON[p]} {sum(1 for c in changes if c.get("priority") == p)} {p.capitalize()}</div>'
                for p in ["critical", "high", "medium"]
            ])
            + '</div>',
            unsafe_allow_html=True,
        )

        pf = st.radio("Show:", ["All", "Critical only", "Critical + High"],
                      horizontal=True, key="gc_priority_filter")
        filtered = changes
        if pf == "Critical only":
            filtered = [c for c in changes if c.get("priority") == "critical"]
        elif pf == "Critical + High":
            filtered = [c for c in changes if c.get("priority") in ("critical", "high")]

        st.caption(f"Showing {len(filtered)} of {len(changes)} changes")

        for change in filtered:
            pri = change.get("priority", "medium")
            loc = change.get("location", {})
            cid = change.get("change_id", "?")
            section_name = loc.get("section", "unknown").upper()
            sub_location = loc.get("sub_location", "")
            title = (
                f"{PRIORITY_ICON.get(pri, '\u26AA')} #{cid} "
                f"[{PRIORITY_LABEL.get(pri, 'MEDIUM')}]  "
                f"{section_name} \u203A {sub_location}"
            )

            with st.expander(title, expanded=(pri == "critical")):
                col_why, col_type = st.columns([3, 1])
                with col_why:
                    st.markdown(f"**Why this matters:** {change.get('why', '')}")
                with col_type:
                    st.markdown(
                        f'<div style="background:{PRIORITY_BG.get(pri, "#fffde7")};'
                        f'border:1px solid {PRIORITY_BDR.get(pri, "#f9a825")};padding:3px 8px;'
                        f'border-radius:4px;font-size:12px;text-align:center">'
                        f'{change.get("change_type", "")}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div style="background:#e8f5e9;border-radius:4px;padding:6px 10px;'
                    f'font-size:12px;margin:6px 0;color:#2e7d32">'
                    f'Fixing this contributes toward: {before}% \u2192 '
                    f'{estimated_after}% JD match</div>',
                    unsafe_allow_html=True,
                )

                if change.get("keywords_added"):
                    pills = " ".join(
                        f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;'
                        f'border-radius:10px;font-size:12px;margin:2px;display:inline-block">'
                        f'{kw}</span>'
                        for kw in change["keywords_added"]
                    )
                    st.markdown(f"**Keywords added:** {pills}", unsafe_allow_html=True)

                st.markdown("---")
                col_orig, col_sugg = st.columns(2)

                with col_orig:
                    st.markdown("**Original (from your resume)**")
                    orig = (
                        change.get("original_text", "")
                        if change.get("original_text")
                        else "<em style='color:#999'>[Not present \u2014 new section]</em>"
                    )
                    st.markdown(
                        f'<div style="background:#fff3f3;border-left:4px solid #e53935;'
                        f'padding:12px;border-radius:4px;font-size:13px;'
                        f'white-space:pre-wrap;min-height:90px">{orig}</div>',
                        unsafe_allow_html=True,
                    )

                with col_sugg:
                    st.markdown("**Suggested Rewrite (ready to paste)**")
                    suggested = change.get("suggested_text", "")
                    st.markdown(
                        f'<div style="background:#f1f8e9;border-left:4px solid #43a047;'
                        f'padding:12px;border-radius:4px;font-size:13px;'
                        f'white-space:pre-wrap;min-height:90px">{suggested}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("**Copy this:**")
                st.code(suggested, language=None)

        st.divider()

        # ── BLOCK D: Section Review + Download ──
        st.subheader("Review & Edit Rewritten Sections")
        final_sections = {}
        rewrite_out = st.session_state.get("rewrite_output", {})
        # Fall back to structured resume for unchanged sections
        structured = st.session_state.get("parsed_resume_structured", {})

        # Helper to get original section text from structured resume
        def _original(key):
            val = structured.get(key, "")
            if not val:
                return ""
            if key == "experience":
                # List of role dicts -> text
                lines = []
                for role in val:
                    for k in ("title", "company", "location", "dates"):
                        if role.get(k):
                            lines.append(str(role[k]))
                    for b in role.get("bullets", []) or []:
                        lines.append(f"- {b}")
                return "\n".join(lines)
            if key == "education":
                return "\n".join(
                    " | ".join(str(item.get(k, "")) for k in ("degree", "institution", "years") if item.get(k))
                    for item in val if any(item.get(k) for k in ("degree", "institution", "years"))
                )
            if key in ("certifications", "awards"):
                return "\n".join(str(x) for x in val if x)
            return str(val)

        covered_sections = set()
        for g in gap_out.get("section_gaps", []):
            key = g.get("section", "unknown")
            if key in covered_sections:
                continue
            covered_sections.add(key)
            needs = g.get("needs_change", False)
            # Priority: rewriter output > gap original_content > structured resume
            content = rewrite_out.get("rewrites", {}).get(key, {}).get(style_choice, "")
            if not content:
                content = g.get("original_content", "")
            if not content:
                content = _original(key)
            label = f"{key.upper()} \u2014 REWRITTEN" if needs else f"{key.upper()} \u2014 unchanged"
            with st.expander(label, expanded=needs):
                final_sections[key] = st.text_area(
                    "",
                    value=content,
                    key=f"gc_edit_{key}",
                    height=150,
                )

        # Include unchanged sections the sectioner found but Agent 3 omitted.
        for section_name, section_text_obj in st.session_state.get("resume_sections", {}).items():
            if section_name in covered_sections:
                continue
            if isinstance(section_text_obj, dict):
                full_text = section_text_obj.get("full_text", "")
            else:
                full_text = getattr(section_text_obj, "full_text", "")
            if not full_text.strip():
                continue
            label = f"{section_name.upper()} — unchanged (from original)"
            with st.expander(label, expanded=False):
                final_sections[section_name] = st.text_area(
                    "",
                    value=full_text,
                    key=f"gc_edit_{section_name}",
                    height=150,
                )

        #st.write("final_sections keys:", list(final_sections.keys()))
        st.divider()

        if st.button("Generate & Download Resume", type="primary"):
            try:
                structured = st.session_state["parsed_resume_structured"]
                rewrites_for_builder = {
                    k: {style_choice: v} for k, v in final_sections.items()
                }
                docx_bytes = build_final_docx(
                    structured,
                    rewrites_for_builder,
                    style_choice,
                )
                assert len(docx_bytes) > 5000, f"Docx too small: {len(docx_bytes)} bytes"
                name = structured.get("name", "candidate").replace(" ", "_")
                st.download_button(
                    "Download Rewritten Resume (.docx)",
                    data=docx_bytes,
                    file_name=f"{name}_rewritten.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                st.success("Resume ready!")
            except Exception as e:
                st.error(f"Docx generation failed: {e}")
                st.exception(e)



# ══════════════════════════════════════════════════════
# TAB 4 — MY PROGRESS
# ══════════════════════════════════════════════════════
