"""
Unit tests for ATS rewrite scoring and validation summary.
Run: pytest tests/test_ats_validation.py -v
"""

from engine.ats_scorer import build_validation_summary, score_resume, score_rewrites

ORIGINAL_RESUME = """
EXPERIENCE
Software Engineer at Acme Corp
• Built backend services using Python
• Maintained internal tooling

SKILLS
Python, JavaScript
"""

IMPROVED_REWRITES = {
    "experience": {
        "balanced": (
            "EXPERIENCE\n"
            "Software Engineer at Acme Corp\n"
            "• Led backend services using Python, AWS, Docker, and Kubernetes\n"
            "• Reduced API latency by 40% and improved throughput to 5k TPS\n"
            "• Shipped microservices with CI/CD and observability tooling"
        ),
        "aggressive": "unused",
        "top_1_percent": "unused",
    },
    "skills": {
        "balanced": (
            "SKILLS\n"
            "Python, JavaScript, AWS, Docker, Kubernetes, PostgreSQL, Redis, Kafka, CI/CD"
        ),
        "aggressive": "unused",
        "top_1_percent": "unused",
    },
}


def test_score_resume_strips_structural_markers() -> None:
    """Markers must not lower ATS vs the same text without markers."""
    clean = (
        "EXPERIENCE\n"
        "Flipkart\n"
        "Engineering Manager | Bengaluru, KA Sep 2020 – Present\n"
        "• Led backend services using Python and reduced latency by 40%\n"
        "• Shipped microservices on AWS with 5k TPS throughput"
    )
    marked = clean.replace(
        "Flipkart\nEngineering Manager",
        "##COMPANY##Flipkart##ROLE##Engineering Manager##END_HEADER##",
    )
    clean_score = score_resume(clean)["score"]
    marked_score = score_resume(marked)["score"]
    assert marked_score >= clean_score


def test_score_rewrites_returns_positive_ats_for_improved_text():
    result = score_rewrites(ORIGINAL_RESUME, IMPROVED_REWRITES)

    assert result["safe_fix"]["ats_score"] > 0
    assert result["full_rewrite"]["ats_score"] > 0
    assert result["safe_fix"]["ats_score"] > result["original_ats"]
    assert "keyword_match" in result["safe_fix"]["ats_breakdown"]


def test_build_validation_summary_fails_on_placeholders():
    rewrites = {
        "summary": {
            "balanced": "Led platform delivery with [X%] latency reduction for [N users].",
            "aggressive": "",
            "top_1_percent": "",
        }
    }
    summary = build_validation_summary(
        original_resume_text=ORIGINAL_RESUME,
        rewrites=rewrites,
        patches=[],
        jd_match_before=70,
        jd_match_after=80,
    )

    assert summary["safe_fix"]["placeholder_check"] == "fail"
    assert summary["safe_fix"]["overall"] == "fail"
    assert summary["safe_fix"]["download_enabled"] is False


def test_build_validation_summary_fails_on_truncation():
    long_original = "EXPERIENCE\n" + ("• Built scalable backend systems.\n" * 40)
    rewrites = {
        "summary": {
            "balanced": "Short rewrite.",
            "aggressive": "",
            "top_1_percent": "",
        }
    }
    summary = build_validation_summary(
        original_resume_text=long_original,
        rewrites=rewrites,
        patches=[],
        jd_match_before=None,
        jd_match_after=None,
    )

    assert summary["safe_fix"]["truncation_check"] == "fail"
    assert summary["safe_fix"]["overall"] == "fail"


def test_run_full_evaluation_validation_none_when_skip_rewrite():
    from orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run_full_evaluation(
        resume_text=ORIGINAL_RESUME,
        jd_text=None,
        skip_rewrite=True,
    )

    assert result.get("validation") is None


def test_run_full_evaluation_validation_present_with_mocked_rewriter(monkeypatch):
    from orchestrator import Orchestrator

    mock_rewriter_output = {
        "rewrites": IMPROVED_REWRITES,
        "styles": {},
        "patches": [],
    }

    class MockRewriter:
        def run(self, _input_dict):
            return mock_rewriter_output

    orch = Orchestrator()
    monkeypatch.setattr(orch, "rewriter", MockRewriter())

    result = orch.run_full_evaluation(
        resume_text=ORIGINAL_RESUME,
        jd_text=None,
    )

    validation = result.get("validation")
    assert validation is not None
    assert validation["safe_fix"]["ats_check"] == "pass"
    assert validation["scores"]["safe_fix"]["ats_score"] > 0
