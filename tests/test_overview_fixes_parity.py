"""Overview ↔ Fixes tab parity for resume-only mode."""

from orchestrator import Orchestrator

from tests.test_no_jd_rewrite import A1_OUTPUT_NO_SUMMARY, _make_resume_sections


def test_weakness_matches_smartviz_label_fuzzy():
    from orchestrator import Orchestrator

    orch = Orchestrator()
    resume_und = {
        **A1_OUTPUT_NO_SUMMARY,
        "weaknesses": [
            "Smart Viz X role lacks explicit team size and hiring signals "
            "→ include team size and hiring metrics",
            "Flipkart EM bullets 3-5 lack quantified latency/scale signals "
            "→ add system scale (QPS, users, SLA)",
            "Apttus role lacks specific metrics on chatbot deployment "
            "→ quantify user growth or revenue impact",
        ],
        "improvement_areas": [],
    }
    resume_sections = _make_resume_sections(
        {
            **A1_OUTPUT_NO_SUMMARY,
            "resume_sections": {
                "experience": {
                    "header": "experience",
                    "full_text": "FLIPKART\nSMARTVIZX\nAPTTUS",
                    "sub_entries": [
                        {
                            "label": "FLIPKART | Engineering Manager",
                            "verbatim_text": "FLIPKART | Engineering Manager\n• Led teams",
                        },
                        {
                            "label": "SMARTVIZX | Director",
                            "verbatim_text": "SMARTVIZX | Director\n• Built product",
                        },
                        {
                            "label": "APTTUS | Senior Manager",
                            "verbatim_text": "APTTUS | Senior Manager\n• Deployed chatbot",
                        },
                    ],
                }
            },
        }
    )
    built = orch._build_no_jd_gaps(resume_und, resume_sections)
    exp_gap = next(g for g in built["section_gaps"] if g["section"] == "experience")
    sub_labels = [s["sub_label"] for s in exp_gap.get("sub_changes", [])]
    assert len(sub_labels) == 3, f"expected 3 role-level sub_changes, got {sub_labels!r}"
