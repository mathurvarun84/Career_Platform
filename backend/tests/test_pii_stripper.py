"""Unit tests for resume PII stripping."""

from backend.utils.pii_stripper import strip_pii


def test_strips_email():
    text = "varun@gmail.com\nSoftware Engineer"
    assert "[email removed]" in strip_pii(text)
    assert "varun@gmail.com" not in strip_pii(text)


def test_strips_indian_phone():
    text = "Contact: +91 98765 43210\nSkills: Python"
    cleaned = strip_pii(text)
    assert "[phone removed]" in cleaned
    assert "98765" not in cleaned


def test_strips_us_phone():
    text = "Phone (415) 555-0123\nExperience at Google"
    cleaned = strip_pii(text)
    assert "[phone removed]" in cleaned


def test_strips_linkedin_url():
    text = "Profile: https://linkedin.com/in/varunxyz\nSummary"
    cleaned = strip_pii(text)
    assert "[linkedin removed]" in cleaned


def test_strips_github_url():
    text = "Code: github.com/varunxyz\nProjects"
    cleaned = strip_pii(text)
    assert "[github removed]" in cleaned


def test_strips_street_address():
    text = "123 MG Road, Bengaluru 560001\nSoftware Engineer"
    cleaned = strip_pii(text)
    assert "[address removed]" in cleaned


def test_strips_header_name():
    text = "Varun Kumar Sharma\nvarun@gmail.com\nExperience"
    cleaned = strip_pii(text)
    assert cleaned.splitlines()[0] == "[name removed]"


def test_preserves_job_titles_and_companies():
    text = (
        "Rahul Mehta\n"
        "Senior Software Engineer at Flipkart\n"
        "- Built payment APIs serving 10M users\n"
        "B.Tech Computer Science, IIT Delhi"
    )
    cleaned = strip_pii(text)
    assert "Senior Software Engineer at Flipkart" in cleaned
    assert "Built payment APIs" in cleaned
    assert "IIT Delhi" in cleaned


def test_preserves_metrics_and_skills():
    text = (
        "Priya Nair\n"
        "Skills: Python, Kubernetes, AWS\n"
        "- Reduced latency by 40% across 12 microservices"
    )
    cleaned = strip_pii(text)
    assert "Python, Kubernetes, AWS" in cleaned
    assert "40%" in cleaned


def test_empty_and_whitespace_safe():
    assert strip_pii("") == ""
    assert strip_pii("   \n\n  ") == "   \n\n  "
