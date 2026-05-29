"""Tests for deterministic seniority reconciliation from job titles."""

from backend.seniority_from_titles import infer_seniority_from_titles, reconcile_seniority


def test_engineering_manager_not_staff():
    resume = """
    EXPERIENCE
    Flipkart — Bengaluru
    Engineering Manager Sep 2020 – Present
    Lead 32 engineers across 5 teams.
    """
    assert infer_seniority_from_titles(resume) == "em"
    final, corrected = reconcile_seniority("staff", resume, 17)
    assert corrected is True
    assert final == "em"


def test_staff_ic_unchanged():
    resume = """
    EXPERIENCE
    Flipkart
    Staff Engineer 2018 – 2024
    Architected orchestration layer.
    """
    assert infer_seniority_from_titles(resume) is None
    final, corrected = reconcile_seniority("staff", resume, 12)
    assert corrected is False
    assert final == "staff"


def test_director_title():
    resume = "Director of Engineering | Acme 2022 – Present"
    assert infer_seniority_from_titles(resume) == "director"
    final, corrected = reconcile_seniority("staff", resume, 17)
    assert final == "director"
