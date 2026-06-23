"""Tests for experience_audit ground-truth backfill and rebuild.

A1 trust hierarchy (experience entry count):
  - When A1 returns N > 0 sub_entries and regex detects M != N: A1 wins (regex logged only)
  - When N = 0 and M > 0: regex backfills
  - When both are 0: error state
"""

from __future__ import annotations

import json
from unittest.mock import patch

from backend.agents.rewriter import COMPANY_HEADER_START, RewriterAgent
from backend.schemas.common import SectionText, SubEntry
from engine.resume_builder import build_final_docx
from orchestrator import Orchestrator
from validator.experience_audit import (
    count_experience_markers,
    detect_ground_truth_entries,
    ensure_experience_completeness,
    log_experience_audit,
)
from validator.resume_understanding_validator import ResumeUnderstandingValidator
from validator.rewriter_validator import RewriterValidator


EXPERIENCE_TEXT = """Engineering Manager | Flipkart — Bengaluru, KA
Sep 2020 – Present
• Led platform team

Head of Engineering | SmartVizX — Bengaluru, KA
Dec 2019 – Sep 2020
• Built product

Engineering Manager | Apttus (via Altran) — Bengaluru, KA
Nov 2018 – Dec 2019
• Delivery

Engineering Manager | ClearTax (via Altran) — Bengaluru, KA
Dec 2016 – Oct 2018
• Tax platform

Senior Consultant | British Telecom — Bengaluru, KA
Sep 2013 – Dec 2016
• OSS

Tech Consultant | Microsoft — Bengaluru, KA
Sep 2011 – Sep 2013
• SharePoint

Lead Software Engineer | Mindtree — Bengaluru, KA
Jul 2007 – Oct 2011
• Enterprise apps
"""

RESUME_WITH_HEADER = f"""Varun Mathur
varun@test.com

EXPERIENCE
{EXPERIENCE_TEXT}
"""

# ---------------------------------------------------------------------------
# Varun Mathur resume — full production experience block (ground truth)
# ---------------------------------------------------------------------------
VARUN_EXPERIENCE_TEXT = """Engineering Manager  |  Flipkart  —  Bengaluru, KA
Sep 2020 – Present
• Lead 5 teams with 32 engineers; previously scaled to 7 teams / ~50 engineers over 4 years — accountable for full delivery lifecycle, roadmap execution, and engineering quality across supply chain and logistics verticals.
• Owned 6 strategic supply chain and logistics platform initiatives end-to-end, driving ₹2,500+ crore in cost savings, 100 bps checkout conversion improvement, and 20 bps reduction in supply chain fraud.
• Delivered three high-impact OKRs across commerce and reverse-logistics verticals, contributing ₹1,500+ crore GMV growth and ₹240 crore bottom-line improvement.
• Spearheaded org-wide hiring initiative to recruit 65 engineers in 2 months for Flipkart Minutes launch — defined hiring bar, built interview pipeline, and trained interviewers to enable accelerated time-to-market.
• Drove AI-assisted development adoption (Copilot, Cursor, Windsurf) across teams, improving engineering productivity by 20% and reducing PR cycle times measurably.
• Designed and executed platform scalability initiatives including DB sharding, Kubernetes adoption, and queue migration — scaling systems to 15K QPS and reducing MTTR by 30% through improved observability.
• Built an AI-powered incident response system with in-context runbook retrieval, independently delivering a further 20% MTTR reduction.
• Deployed a Workflow Management Platform using Temporal and IWF, delivering 20% reduction in KTLO overhead for two teams and improving overall engineering throughput.

Head of Engineering  |  SmartVizX  —  Bengaluru, KA
Dec 2019 – Sep 2020
• Led cross-functional teams (UX, backend, QA) for a 3D design SaaS platform; delivered product features for architects and designers that generated ₹4 Cr in incremental revenue.
• Architected and launched a multi-user VR collaboration platform for architects, reducing client mock-up costs by 25% and opening a new enterprise sales channel.

Engineering Manager  |  Apttus (via Altran — Consulting Engagement)  —  Bengaluru, KA
Nov 2018 – Dec 2019
• Led architecture and delivery of a multi-tenant B2B chatbot on a microservices-based backend; drove IBM Cloud migration that scaled the user base from 100+ to 6,500+ within 12 months.

Engineering Manager  |  ClearTax (via Altran — Consulting Engagement)  —  Bengaluru, KA
Dec 2016 – Oct 2018
• Architected a microservices-based, event-driven distributed backend in .NET with MySQL and distributed caching, handling 1M+ requests/hour for ClearTax's core tax-filing platform.
• Conceptualised and delivered the one-page e-filing product from inception to launch, growing the user base by 50% within one fiscal year.

Senior Consultant  |  British Telecom  —  Bengaluru, KA
Sep 2013 – Dec 2016
• Led BOSS application migration to BT Cloud, saving £3.5 million annually and delivering 2 months ahead of schedule — early delivery alone saved an additional £600K.
• Designed and optimised distributed backend systems for mission-critical telco workloads; diagnosed and resolved performance bottlenecks under high-traffic production conditions.

Tech Consultant  |  Microsoft  —  Bengaluru, KA
Sep 2011 – Sep 2013
• Provided technical leadership across system design, architecture, and prototyping for 8 Fortune 500 clients including Citigroup, Wells Fargo, and VISA — covering financial platforms processing billions in transactions.

Lead Software Engineer  |  Mindtree  —  Bengaluru, KA
Jul 2007 – Oct 2011
• Supervised a team of 6 delivering software features across enterprise clients including Volvo and Arcelor Mittal; secured a $1M follow-on maintenance contract by exceeding delivery SLAs across 17 production applications.
"""

VARUN_RESUME_TEXT = f"""Varun Mathur
varun@example.com | +91-9999999999

E X P E R I E N C E
{VARUN_EXPERIENCE_TEXT}
"""

VARUN_COMPANIES = (
    "Flipkart",
    "SmartVizX",
    "Apttus",
    "ClearTax",
    "British Telecom",
    "Microsoft",
    "Mindtree",
)

# Distinctive bullets — each must appear in rewritten output (verbatim preservation)
VARUN_DISTINCTIVE_SNIPPETS = (
    "Flipkart Minutes",
    "6,500+",
    "one-page e-filing",
    "£3.5 million",
    "Citigroup, Wells Fargo, and VISA",
    "Arcelor Mittal",
)


def test_ground_truth_detects_seven_entries() -> None:
    blocks = detect_ground_truth_entries(RESUME_WITH_HEADER)
    assert len(blocks) == 7, f"expected 7, got {len(blocks)}: {[b['label'] for b in blocks]}"


def test_ensure_completeness_backfills_partial_a1() -> None:
    partial = SectionText(
        header="experience",
        full_text="only two",
        sub_entries=[
            SubEntry(label="Flipkart", verbatim_text="Flipkart\n• one"),
            SubEntry(label="SmartVizX", verbatim_text="SmartVizX\n• two"),
        ],
    )
    fixed = ensure_experience_completeness(partial, RESUME_WITH_HEADER)
    assert fixed is not None
    assert len(fixed.sub_entries) == 7


def test_rewriter_skips_monolithic_when_sub_entries_exist() -> None:
    entries = [
        SubEntry(label=f"Corp{i}", verbatim_text=f"Corp{i}\nRole\n• b{i}")
        for i in range(5)
    ]
    section = SectionText(
        header="experience",
        full_text="\n\n".join(e.verbatim_text for e in entries),
        sub_entries=entries,
    )
    gaps = [{
        "section": "experience",
        "needs_change": True,
        "rewrite_instruction": "Improve",
        "sub_changes": [],
    }]
    agent = RewriterAgent()
    with patch.object(RewriterAgent, "_call_llm") as mock_llm:
        out = agent.run({
            "gap_analysis": {"gaps": gaps},
            "resume_sections": {"experience": section.model_dump()},
            "resume_text": "",
        })
    mock_llm.assert_not_called()
    balanced = out["rewrites"]["experience"]["balanced"]
    assert balanced.count(COMPANY_HEADER_START) == 5


def test_pdf_merged_header_lines_detect_seven_not_bullets() -> None:
    """
    Simulate pdfplumber output: role + dates on ONE line (tab or space), plus long bullets.

    Must detect 7 companies — not bullet lines like '50% within one fiscal year'.
    """
    pdf_like = "\n".join(
        line.replace("\t", "  ")
        for line in (
            "Engineering Manager  |  Flipkart  —  Bengaluru, KA  Sep 2020 – Present",
            "• Lead 5 teams with 32 engineers; Flipkart Minutes launch in 2 months.",
            "• Owned 6 strategic supply chain initiatives; 50% within one fiscal year.",
            "",
            "Head of Engineering  |  SmartVizX  —  Bengaluru, KA  Dec 2019 – Sep 2020",
            "• Led cross-functional teams; VR collaboration platform.",
            "",
            "Engineering Manager  |  Apttus (via Altran)  —  Bengaluru, KA  Nov 2018 – Dec 2019",
            "• IBM Cloud migration scaled users from 100+ to 6,500+ within 12 months.",
            "",
            "Engineering Manager  |  ClearTax (via Altran)  —  Bengaluru, KA  Dec 2016 – Oct 2018",
            "• one-page e-filing product; performance bottlenecks under high-traffic production conditions.",
            "",
            "Senior Consultant  |  British Telecom  —  Bengaluru, KA  Sep 2013 – Dec 2016",
            "• Led BOSS migration saving £3.5 million annually.",
            "",
            "Tech Consultant  |  Microsoft  —  Bengaluru, KA  Sep 2011 – Sep 2013",
            "• Citigroup, Wells Fargo, and VISA — covering financial platforms.",
            "",
            "Lead Software Engineer  |  Mindtree  —  Bengaluru, KA  Jul 2007 – Oct 2011",
            "• Volvo and Arcelor Mittal; 17 production applications.",
        )
    )
    resume = f"EXPERIENCE\n{pdf_like}"
    blocks = detect_ground_truth_entries(resume)
    labels = [b["label"] for b in blocks]
    assert len(blocks) == 7, f"expected 7, got {len(blocks)}: {labels}"
    for company in VARUN_COMPANIES:
        assert any(company.lower() in lbl.lower() for lbl in labels), (
            f"missing {company} in {labels}"
        )
    bad_labels = ("fiscal year", "production condit", "6,500+", "overhead for two")
    for bad in bad_labels:
        assert not any(bad in lbl for lbl in labels), f"bullet falsely used as label: {labels}"


def test_varun_experience_ground_truth_seven_entries() -> None:
    """Full Varun resume block must yield exactly 7 experience sub-entries."""
    blocks = detect_ground_truth_entries(VARUN_RESUME_TEXT)
    labels = [b["label"] for b in blocks]
    assert len(blocks) == 7, f"expected 7 entries, got {len(blocks)}: {labels}"
    for company in VARUN_COMPANIES:
        assert any(company.lower() in lbl.lower() for lbl in labels), (
            f"missing company '{company}' in labels: {labels}"
        )


def test_varun_a1_validator_restores_all_seven_entries() -> None:
    """Simulate A1 returning only 2 entries; validator must restore all 7."""
    partial_a1 = {
        "experience_years": 18,
        "seniority": "staff",
        "tech_stack": ["Python", "Kubernetes"],
        "domains": ["e-commerce"],
        "has_metrics": True,
        "has_summary": False,
        "sections_present": ["experience"],
        "resume_sections": {
            "experience": {
                "header": "experience",
                "full_text": "",
                "sub_entries": [
                    {
                        "label": "Engineering Manager | Flipkart",
                        "verbatim_text": (
                            "Engineering Manager | Flipkart\nSep 2020 – Present\n"
                            "• Lead 5 teams with 32 engineers"
                        ),
                    },
                    {
                        "label": "Head of Engineering | SmartVizX",
                        "verbatim_text": (
                            "Head of Engineering | SmartVizX\nDec 2019 – Sep 2020\n"
                            "• VR collaboration platform"
                        ),
                    },
                ],
            },
        },
    }
    repaired = ResumeUnderstandingValidator().validate_and_fix(
        partial_a1, VARUN_RESUME_TEXT
    )
    exp = repaired["resume_sections"]["experience"]
    subs = exp.get("sub_entries") or []
    assert len(subs) == 7, (
        f"A1 validator: expected 7 sub_entries, got {len(subs)}: "
        f"{[s.get('label', '')[:50] for s in subs]}"
    )


def test_varun_rewritten_resume_preserves_all_seven_companies_verbatim() -> None:
    """
    End-to-end: partial A1 → backfill → rewriter (verbatim) → validator.

    All 7 companies and every distinctive bullet from the original must appear
    unchanged when experience needs_change=False.
    """
    partial_a1 = {
        "resume_sections": {
            "experience": {
                "header": "experience",
                "full_text": "",
                "sub_entries": [
                    {
                        "label": "Engineering Manager | Flipkart",
                        "verbatim_text": VARUN_EXPERIENCE_TEXT.split(
                            "Head of Engineering"
                        )[0].strip(),
                    },
                    {
                        "label": "Head of Engineering | SmartVizX",
                        "verbatim_text": (
                            "Head of Engineering | SmartVizX\nDec 2019 – Sep 2020\n"
                            "• VR collaboration platform"
                        ),
                    },
                ],
            },
        },
    }
    a1_fixed = ResumeUnderstandingValidator().validate_and_fix(
        partial_a1, VARUN_RESUME_TEXT
    )
    section_text = SectionText(**a1_fixed["resume_sections"]["experience"])
    assert len(section_text.sub_entries) == 7

    gaps = [{
        "section": "experience",
        "needs_change": False,
        "rewrite_instruction": "",
        "sub_changes": [],
    }]

    agent = RewriterAgent()
    with patch.object(RewriterAgent, "_call_llm") as mock_llm:
        rewriter_out = agent.run({
            "gap_analysis": {"gaps": gaps, "strengths": [], "quick_wins": []},
            "resume_sections": {"experience": section_text.model_dump()},
            "resume_text": VARUN_RESUME_TEXT,
        })
    mock_llm.assert_not_called()

    repaired = RewriterValidator().validate_and_fix(
        rewriter_out,
        {"experience": section_text.model_dump()},
        VARUN_RESUME_TEXT,
    )
    balanced = repaired["rewrites"]["experience"]["balanced"]
    _assert_varun_experience_complete(balanced, section_text, check_all_snippets=True)


def test_varun_rewritten_resume_preserves_all_seven_companies() -> None:
    """
    End-to-end: partial A1 → backfill → rewriter (1 entry LLM) → validator → DOCX.

    All 7 companies must appear; non-rewritten entries keep original bullets.
    """
    # Step 1: ground truth + A1 validator
    partial_a1 = {
        "resume_sections": {
            "experience": {
                "header": "experience",
                "full_text": "",
                "sub_entries": [
                    {
                        "label": "Engineering Manager | Flipkart",
                        "verbatim_text": VARUN_EXPERIENCE_TEXT.split(
                            "Head of Engineering"
                        )[0].strip(),
                    },
                    {
                        "label": "Head of Engineering | SmartVizX",
                        "verbatim_text": (
                            "Head of Engineering | SmartVizX\nDec 2019 – Sep 2020\n"
                            "• VR collaboration platform"
                        ),
                    },
                ],
            },
        },
    }
    a1_fixed = ResumeUnderstandingValidator().validate_and_fix(
        partial_a1, VARUN_RESUME_TEXT
    )
    section_dict = a1_fixed["resume_sections"]["experience"]
    section_text = SectionText(**section_dict)

    log_experience_audit("varun_test_post_a1", VARUN_RESUME_TEXT, a1_fixed["resume_sections"])

    assert len(section_text.sub_entries) == 7

    # Step 2: rewriter — only Flipkart targeted; others must stay verbatim
    flipkart_label = section_text.sub_entries[0].label

    def _mock_flipkart_rewrite(*_args, **_kwargs) -> str:
        return json.dumps({
            "balanced": (
                "##COMPANY##Flipkart##ROLE##Engineering Manager | Sep 2020–Present"
                "##END_HEADER##\n• Rewritten Flipkart bullet with metrics"
            ),
            "aggressive": (
                "##COMPANY##Flipkart##ROLE##Engineering Manager | Sep 2020–Present"
                "##END_HEADER##\n• Aggressive Flipkart bullet"
            ),
            "top_1_percent": (
                "##COMPANY##Flipkart##ROLE##Engineering Manager | Sep 2020–Present"
                "##END_HEADER##\n• Top Flipkart bullet"
            ),
        })

    gaps = [{
        "section": "experience",
        "needs_change": True,
        "rewrite_instruction": "Strengthen Flipkart bullets with scale metrics.",
        "sub_changes": [{
            "sub_id": "flipkart",
            "sub_label": flipkart_label,
            "entry_index": 0,
            "needs_change": True,
            "rewrite_instruction": "Add QPS and team scale.",
            "missing_keywords": ["Kubernetes"],
        }],
    }]

    agent = RewriterAgent()
    with patch.object(RewriterAgent, "_call_llm", side_effect=_mock_flipkart_rewrite):
        rewriter_out = agent.run({
            "gap_analysis": {"gaps": gaps, "strengths": [], "quick_wins": []},
            "resume_sections": {"experience": section_text.model_dump()},
            "resume_text": VARUN_RESUME_TEXT,
            "jd_intelligence": None,
            "style_fingerprint": None,
        })

    repaired = RewriterValidator().validate_and_fix(
        rewriter_out,
        {"experience": section_text.model_dump()},
        VARUN_RESUME_TEXT,
    )

    balanced = repaired["rewrites"]["experience"]["balanced"]

    log_experience_audit(
        "varun_test_post_rewrite",
        VARUN_RESUME_TEXT,
        a1_fixed["resume_sections"],
        repaired.get("rewrites"),
    )

    _assert_varun_experience_complete(
        balanced,
        section_text,
        check_all_snippets=False,
    )
    assert "rewritten flipkart" in balanced.lower()

    structured = {
        "name": "Varun Mathur",
        "contact": "varun@example.com",
        "resume_sections": a1_fixed["resume_sections"],
    }
    docx_bytes = build_final_docx(
        structured=structured,
        rewrites=repaired["rewrites"],
        style="balanced",
        resume_text=VARUN_RESUME_TEXT,
    )
    assert len(docx_bytes) > 5000


def _assert_varun_experience_complete(
    balanced: str,
    section_text: SectionText,
    *,
    check_all_snippets: bool,
) -> None:
    """Shared assertions for Varun 7-entry experience output."""
    marker_count = count_experience_markers(balanced)
    assert marker_count == 7, (
        f"expected 7 ##COMPANY## blocks, got {marker_count}; "
        f"labels={[e.label[:45] for e in section_text.sub_entries]}"
    )

    balanced_lower = balanced.lower()
    for company in VARUN_COMPANIES:
        assert company.lower() in balanced_lower, (
            f"rewritten resume missing company '{company}'"
        )

    snippets = VARUN_DISTINCTIVE_SNIPPETS if check_all_snippets else VARUN_DISTINCTIVE_SNIPPETS[1:]
    for snippet in snippets:
        assert snippet.lower() in balanced_lower or snippet in balanced, (
            f"rewritten resume missing bullet snippet: {snippet!r}"
        )


def test_validator_rebuilds_partial_rewrite() -> None:
    entries = [
        SubEntry(label=f"Corp{i} — Role", verbatim_text=f"Corp{i}\nRole\n• bullet")
        for i in range(6)
    ]
    section = SectionText(
        header="experience",
        full_text="\n\n".join(e.verbatim_text for e in entries[:2]),
        sub_entries=entries[:2],
    )
    partial_rewrite = {
        "balanced": "##COMPANY##Corp0##ROLE##r##END_HEADER##\n• b0",
        "aggressive": "##COMPANY##Corp0##ROLE##r##END_HEADER##\n• b0",
        "top_1_percent": "##COMPANY##Corp0##ROLE##r##END_HEADER##\n• b0",
    }
    resume_text = "\n".join(
        f"Corp{i} — Role\nJan {2010+i} – Dec {2011+i}\n• bullet"
        for i in range(6)
    )
    repaired = RewriterValidator().validate_and_fix(
        {"rewrites": {"experience": partial_rewrite}},
        {"experience": section.model_dump()},
        resume_text,
    )
    balanced = repaired["rewrites"]["experience"]["balanced"]
    assert balanced.count(COMPANY_HEADER_START) >= 6


MMYYYY_EXPERIENCE_TEXT = """Senior Developer | Infosys — Bengaluru
06/2019 - 08/2022
• Built microservices platform

Software Engineer | Wipro — Pune
03/2016 - 05/2019
• Delivered client projects

Junior Developer | TCS — Chennai
01/2014 - 02/2016
• Maintained enterprise apps
"""

MMYYYY_RESUME_TEXT = f"""Ravi Kumar
ravi@example.com

EXPERIENCE
{MMYYYY_EXPERIENCE_TEXT}
"""

_SECTIONER_GATE = Orchestrator()


def test_mm_yyyy_date_ranges_detect_three_entries() -> None:
    """Indian MM/YYYY date formats must count toward ground-truth entry detection."""
    blocks = detect_ground_truth_entries(MMYYYY_RESUME_TEXT)
    assert len(blocks) == 3, f"expected 3, got {len(blocks)}: {[b['label'] for b in blocks]}"


def test_needs_sectioner_true_when_a1_misses_more_than_one() -> None:
    """6 ground-truth jobs vs 3 A1 entries should trigger Sectioner."""
    partial_sections = {
        "experience": {
            "header": "experience",
            "full_text": "",
            "sub_entries": [
                {"label": "Infosys", "verbatim_text": "Infosys\n• one"},
                {"label": "Wipro", "verbatim_text": "Wipro\n• two"},
                {"label": "TCS", "verbatim_text": "TCS\n• three"},
            ],
        }
    }
    assert _SECTIONER_GATE._needs_sectioner(partial_sections, VARUN_RESUME_TEXT) is True


def test_needs_sectioner_false_when_a1_matches_ground_truth() -> None:
    """Clean A1 output with all 7 entries should skip Sectioner."""
    ground = detect_ground_truth_entries(VARUN_RESUME_TEXT)
    sections = {
        "experience": {
            "header": "experience",
            "full_text": "\n\n".join(b["text"] for b in ground),
            "sub_entries": [
                {"label": b["label"], "verbatim_text": b["text"]} for b in ground
            ],
        }
    }
    assert len(ground) == 7
    assert _SECTIONER_GATE._needs_sectioner(sections, VARUN_RESUME_TEXT) is False


def test_needs_sectioner_false_when_missing_only_one_entry() -> None:
    """Tolerance: off-by-one mismatch should not trigger Sectioner."""
    ground = detect_ground_truth_entries(VARUN_RESUME_TEXT)
    assert len(ground) == 7
    sections = {
        "experience": {
            "header": "experience",
            "full_text": "",
            "sub_entries": [
                {"label": b["label"], "verbatim_text": b["text"]} for b in ground[:6]
            ],
        }
    }
    assert _SECTIONER_GATE._needs_sectioner(sections, VARUN_RESUME_TEXT) is False


def test_needs_sectioner_true_for_mm_yyyy_when_a1_truncated() -> None:
    """MM/YYYY resumes must not false-negative the gate when A1 truncates heavily."""
    partial_sections = {
        "experience": {
            "header": "experience",
            "full_text": "",
            "sub_entries": [
                {"label": "Infosys", "verbatim_text": "Infosys\n• one"},
            ],
        }
    }
    assert _SECTIONER_GATE._needs_sectioner(partial_sections, MMYYYY_RESUME_TEXT) is True


if __name__ == "__main__":
    test_ground_truth_detects_seven_entries()
    test_ensure_completeness_backfills_partial_a1()
    test_rewriter_skips_monolithic_when_sub_entries_exist()
    test_pdf_merged_header_lines_detect_seven_not_bullets()
    test_varun_experience_ground_truth_seven_entries()
    test_varun_a1_validator_restores_all_seven_entries()
    test_varun_rewritten_resume_preserves_all_seven_companies_verbatim()
    test_varun_rewritten_resume_preserves_all_seven_companies()
    test_validator_rebuilds_partial_rewrite()
    print("OK — experience_audit tests passed (including Varun Mathur 7-entry suite)")
