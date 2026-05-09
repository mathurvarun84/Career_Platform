"""
E2E smoke test for JD Auto-Fetch.
Run manually: pytest backend/tests/test_jd_fetch_e2e.py -v -s
Requires: OPENAI_API_KEY and SERPER_API_KEY set in environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.agents.jd_fetcher import JDFetcherAgent, JDFetchResult


pytestmark = pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("SERPER_API_KEY")),
    reason="OPENAI_API_KEY or SERPER_API_KEY not set — skipping live E2E tests",
)


class TestJDFetcherE2E:
    """Live API tests — only run when API keys are available."""

    def setup_method(self):
        self.agent = JDFetcherAgent()

    def test_e2e_fetch_google_sde(self):
        result = self.agent.fetch("Google India", "Software Engineer")
        assert isinstance(result, JDFetchResult)
        assert result.status in ("found", "multiple", "not_found")
        assert result.company == "Google India"
        assert result.role == "Software Engineer"
        if result.status == "found":
            assert result.jd_text is not None
            assert len(result.jd_text) > 200

    def test_e2e_fetch_nonexistent_role(self):
        result = self.agent.fetch("TCS", "Chief Astronaut Officer")
        assert result.status in ("not_found", "error")

    def test_e2e_result_shape(self):
        result = self.agent.fetch("Flipkart", "Data Scientist")
        assert result.status in ("found", "not_found", "multiple", "error")
        if result.status == "found":
            assert result.jd_text and len(result.jd_text.strip()) > 0
        if result.status == "multiple":
            assert isinstance(result.alternatives, list)
            assert len(result.alternatives) > 0
