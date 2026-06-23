"""
Tests for no-JD summary generation and rewrite path.
Run: pytest tests/test_no_jd_rewrite.py -v
"""
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────

RESUME_NO_SUMMARY = """
Gauri Dhawan
gauri.dhawan@nyu.edu | +1(917-325-5187)

SKILLS
Programming: Java, Python, JavaScript | Cloud: AWS, Docker

EXPERIENCE
ORACLE | SENIOR SOFTWARE ENGINEER
Sept 2024 – Present | Austin, Texas
• Designed Pooled Usage feature adopted by 20+ enterprise clients
• Resolved customer issues blocking $89M in revenue
Tech Stack: Java, SQL, JavaScript

ORACLE | SOFTWARE ENGINEER
June 2021 – Aug 2024 | Austin, Texas
• Led design of partial invoicing feature
• Fixed critical bug causing $1M in extra charges for a key customer
Tech Stack: Java, SQL, JavaScript

EDUCATION
NEW YORK UNIVERSITY | Masters of Science in Computer Science | 2021 | GPA 3.83
"""

A1_OUTPUT_NO_SUMMARY = {
    "has_summary": False,
    "seniority": "senior",
    "role_family": "ENGINEERING",
    "experience_years": 7,
    "tech_stack": ["Java", "SQL", "JavaScript", "AWS"],
    "domains": ["enterprise software", "billing"],
    "strengths": ["7 years at Oracle", "Led Pooled Usage feature for 20+ clients"],
    "weaknesses": [
        "Oracle Sr Eng bullets lack scale metrics (QPS, users) → add system scale",
        "No professional summary → add 3-4 sentence summary highlighting Oracle tenure",
    ],
    "improvement_areas": [
        "Add quantified scale metrics to Oracle experience bullets",
        "Add professional summary section",
        "Highlight cloud architecture work more prominently",
    ],
    "resume_sections": {
        "experience": {
            "header": "experience",
            "full_text": "ORACLE | SENIOR SOFTWARE ENGINEER\nSept 2024–Present\n• Built feature",
            "sub_entries": [
                {
                    "label": "ORACLE | SENIOR SOFTWARE ENGINEER",
                    "verbatim_text": (
                        "ORACLE | SENIOR SOFTWARE ENGINEER\n"
                        "Sept 2024 – Present | Austin, Texas\n"
                        "• Designed Pooled Usage feature adopted by 20+ clients\n"
                        "Tech Stack: Java, SQL, JavaScript"
                    ),
                },
                {
                    "label": "ORACLE | SOFTWARE ENGINEER",
                    "verbatim_text": (
                        "ORACLE | SOFTWARE ENGINEER\n"
                        "June 2021 – Aug 2024 | Austin, Texas\n"
                        "• Led design of partial invoicing feature\n"
                        "Tech Stack: Java, SQL, JavaScript"
                    ),
                },
            ],
        }
    },
}


# ── _build_no_jd_gaps unit tests ──────────────────────────────────────────

def _make_resume_sections(a1_output: dict):
    from backend.schemas.common import SectionText, SubEntry
    raw = a1_output.get("resume_sections", {})
    sections = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            sub_entries = [
                SubEntry(label=e["label"], verbatim_text=e["verbatim_text"])
                for e in v.get("sub_entries", [])
                if isinstance(e, dict)
            ]
            sections[k] = SectionText(
                header=v.get("header", k),
                full_text=v.get("full_text", ""),
                sub_entries=sub_entries,
            )
    return sections


def test_build_no_jd_gaps_has_section_gaps_key():
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    result = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)

    assert "section_gaps" in result, "Must have section_gaps key"
    assert isinstance(result["section_gaps"], list)
    assert len(result["section_gaps"]) >= 1


def test_build_no_jd_gaps_also_has_gaps_key():
    """Rewriter reads either 'gaps' or 'section_gaps' — both must be present."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    result = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)

    assert "gaps" in result, "Must also expose 'gaps' key for rewriter compatibility"
    assert result["gaps"] == result["section_gaps"]


def test_build_no_jd_gaps_summary_missing_is_needs_change():
    """When has_summary=False, summary gap must have needs_change=True."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_und = {"has_summary": False, "improvement_areas": [], "weaknesses": []}
    result = orch._build_no_jd_gaps(resume_und, {})

    summary_gap = next(
        (g for g in result["section_gaps"] if g["section"] == "summary"), None
    )
    assert summary_gap is not None, "Summary gap must be present"
    assert summary_gap["needs_change"] is True
    assert summary_gap["present_in_resume"] is False
    assert len(summary_gap["rewrite_instruction"]) > 20


def test_build_no_jd_gaps_summary_present_is_not_needs_change():
    """When has_summary=True and no summary instruction, needs_change=False."""
    from orchestrator import Orchestrator
    from backend.schemas.common import SectionText
    orch = Orchestrator()
    resume_und = {"has_summary": True, "improvement_areas": [], "weaknesses": []}
    resume_sections = {
        "summary": SectionText(
            header="summary",
            full_text="Senior engineer with 7 years at Oracle.",
            sub_entries=[],
        )
    }
    result = orch._build_no_jd_gaps(resume_und, resume_sections)

    summary_gap = next(
        (g for g in result["section_gaps"] if g["section"] == "summary"), None
    )
    assert summary_gap is not None
    assert summary_gap["needs_change"] is False


def test_build_no_jd_gaps_experience_sub_changes_from_weaknesses():
    """Oracle mention in weaknesses must produce sub_changes for Oracle entry."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    result = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)

    exp_gap = next(
        (g for g in result["section_gaps"] if g["section"] == "experience"), None
    )
    assert exp_gap is not None
    assert exp_gap["needs_change"] is True
    assert len(exp_gap["sub_changes"]) >= 1, (
        "Oracle mention in weaknesses must produce at least one sub_change"
    )


def test_build_no_jd_gaps_all_canonical_sections_present():
    """All canonical sections must appear in section_gaps."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    result = orch._build_no_jd_gaps(
        {"has_summary": False, "improvement_areas": [], "weaknesses": []}, {}
    )
    present = {g["section"] for g in result["section_gaps"]}
    for canon in ["summary", "skills", "experience", "education"]:
        assert canon in present, f"{canon} must be in section_gaps"


def test_build_no_jd_gaps_each_gap_has_section_key():
    """Every gap dict must have a 'section' key for the rewriter to canonicalize."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    result = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)

    for gap in result["section_gaps"]:
        assert "section" in gap, f"Gap missing 'section' key: {gap}"
        assert gap["section"] != "other", (
            f"Gap section must not be 'other': {gap}"
        )


def test_improvement_areas_route_to_experience():
    """'Add quantified metrics to Oracle bullets' must route to experience."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_und = {
        "has_summary": True,
        "improvement_areas": ["Add quantified metrics to Oracle experience bullets"],
        "weaknesses": [],
    }
    result = orch._build_no_jd_gaps(resume_und, {})

    exp_gap = next(
        (g for g in result["section_gaps"] if g["section"] == "experience"), None
    )
    assert exp_gap is not None
    assert exp_gap["needs_change"] is True
    assert "metrics" in exp_gap["rewrite_instruction"].lower() or \
           "oracle" in exp_gap["rewrite_instruction"].lower()


def test_improvement_areas_route_to_summary():
    """'Add professional summary section' must route to summary."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_und = {
        "has_summary": True,  # exists but instruction says to improve it
        "improvement_areas": ["Strengthen professional summary with specific achievements"],
        "weaknesses": [],
    }
    result = orch._build_no_jd_gaps(resume_und, {})

    summary_gap = next(
        (g for g in result["section_gaps"] if g["section"] == "summary"), None
    )
    assert summary_gap is not None
    assert summary_gap["needs_change"] is True


def test_weakness_location_preserved_in_gap_reason():
    """Full weakness (location → fix) must survive to gap_reason; rewriter gets fix half only."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    weakness = (
        "Smart Viz X bullets 3-5 lack quantified impact → add revenue growth figures"
    )
    resume_und = {
        "has_summary": True,
        "improvement_areas": [],
        "weaknesses": [weakness],
    }
    result = orch._build_no_jd_gaps(resume_und, {})

    exp_gap = next(
        (g for g in result["section_gaps"] if g["section"] == "experience"), None
    )
    assert exp_gap is not None
    assert "→" in exp_gap["gap_reason"]
    assert "Smart Viz X" in exp_gap["gap_reason"]
    assert exp_gap["rewrite_instruction"] == "add revenue growth figures"


def test_no_jd_actionable_fixes_tab_has_content():
    """
    Frontend smoke test: verify classified no-JD gap_result for the Fixes tab.
    priority_fixes must be structured objects (not stripped by overview dedupe).
    """
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    built = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)
    overview_strings = (
        list(A1_OUTPUT_NO_SUMMARY.get("improvement_areas") or [])
        + list(A1_OUTPUT_NO_SUMMARY.get("weaknesses") or [])
    )
    result = orch._apply_gap_classification(
        built,
        "",
        structured_priority_fixes=True,
        overview_strings=overview_strings,
    )

    priority_fixes = result.get("priority_fixes", [])
    assert len(priority_fixes) > 0, "priority_fixes must be non-empty for Fixes tab"

    for fix in priority_fixes:
        assert isinstance(fix, dict), (
            f"No-JD priority_fixes must be structured dicts, got: {type(fix)} — {fix!r}"
        )
        assert fix.get("gap_type") in ("structural", "surface", "evidence"), fix
        if fix.get("gap_type") == "evidence":
            assert fix.get("coaching_question"), fix

    needs_change_gaps = [
        g for g in result["section_gaps"] if g.get("needs_change")
    ]
    assert len(needs_change_gaps) > 0, (
        "section_gaps must have at least one needs_change=True for fix cards to render"
    )

    for gap in needs_change_gaps:
        assert gap.get("gap_reason"), (
            f"gap_reason missing on section '{gap['section']}'"
        )
        assert gap.get("rewrite_instruction"), (
            f"rewrite_instruction missing on section '{gap['section']}'"
        )


def test_no_jd_fix_plan_kinds_are_all_valid():
    """fix_plan items in no-JD mode must include actionable kinds, not all info_only."""
    from backend.engine.fix_plan_builder import build_fix_plan
    from orchestrator import Orchestrator

    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    built = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)
    overview_strings = (
        list(A1_OUTPUT_NO_SUMMARY.get("improvement_areas") or [])
        + list(A1_OUTPUT_NO_SUMMARY.get("weaknesses") or [])
    )
    result = orch._apply_gap_classification(
        built,
        "",
        structured_priority_fixes=True,
        overview_strings=overview_strings,
    )

    priority_fixes = result.get("priority_fixes", [])
    fix_plan = build_fix_plan(priority_fixes, [])
    actionable = [f for f in fix_plan if f["kind"] != "info_only"]
    assert len(actionable) > 0, (
        f"No actionable fixes in no-JD fix_plan. Kinds: {[f['kind'] for f in fix_plan]}"
    )


def test_resume_only_keeps_priority_fixes_when_overlapping_overview():
    """Overview dedupe must not empty priority_fixes in resume-only mode."""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    resume_sections = _make_resume_sections(A1_OUTPUT_NO_SUMMARY)
    built = orch._build_no_jd_gaps(A1_OUTPUT_NO_SUMMARY, resume_sections)
    overview_strings = (
        list(A1_OUTPUT_NO_SUMMARY.get("improvement_areas") or [])
        + list(A1_OUTPUT_NO_SUMMARY.get("weaknesses") or [])
    )
    result = orch._apply_gap_classification(
        built,
        "",
        structured_priority_fixes=True,
        overview_strings=overview_strings,
    )
    assert result.get("resume_only_mode") is True
    assert len(result.get("priority_fixes") or []) >= 1

# ── Integration test: full no-JD pipeline ─────────────────────────────────

@pytest.mark.integration
def test_no_jd_pipeline_produces_summary_in_rewrites():
    """
    Full pipeline: upload resume without JD, verify summary appears in rewrites.
    Requires live LLM calls — mark with @pytest.mark.integration.
    """
    from orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run_full_evaluation(
        resume_text=RESUME_NO_SUMMARY,
        jd_text=None,
    )

    rewrites = result.get("rewrites") or {}
    rewrites_inner = rewrites.get("rewrites", rewrites)

    # Summary must be present and non-empty
    summary_rw = rewrites_inner.get("summary", {})
    summary_text = (
        summary_rw.get("balanced", "") if isinstance(summary_rw, dict) else ""
    )
    assert summary_text.strip(), \
        "Summary must be in rewrites for no-JD case with missing summary"
    assert len(summary_text.strip()) >= 50, \
        f"Summary too short ({len(summary_text)} chars): {summary_text!r}"

    # Summary must read like prose, not a skills list
    lines = [l.strip() for l in summary_text.splitlines() if l.strip()]
    bullet_lines = sum(1 for l in lines if l.startswith(("•", "-", "*")))
    assert bullet_lines == 0, \
        f"Summary must not contain bullet lines — looks like skills bleed: {summary_text!r}"


@pytest.mark.integration
def test_no_jd_pipeline_rewrites_experience():
    """Experience section must be rewritten (not just verbatim) without JD."""
    from orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run_full_evaluation(
        resume_text=RESUME_NO_SUMMARY,
        jd_text=None,
    )

    rewrites = result.get("rewrites") or {}
    rewrites_inner = rewrites.get("rewrites", rewrites)

    exp_rw = rewrites_inner.get("experience", {})
    assert exp_rw, "experience must be in rewrites"

    exp_text = (
        exp_rw.get("balanced", "") if isinstance(exp_rw, dict) else ""
    )
    assert exp_text.strip(), "experience balanced rewrite must be non-empty"
