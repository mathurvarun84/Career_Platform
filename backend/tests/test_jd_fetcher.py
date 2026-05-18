"""
Tests for JD Fetcher Agent — JD Auto-Fetch Feature
Tests cover: unit, integration (mocked), parse logic, API endpoint.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from backend.agents import jd_fetcher as jf
from backend.agents.jd_fetcher import JDFetcherAgent, JDFetchResult


def _agent_with_mocks() -> JDFetcherAgent:
    with patch.dict(
        os.environ,
        {"ANTHROPIC_API_KEY": "test-anthropic-key", "SERPER_API_KEY": "test-serper-key"},
    ):
        agent = JDFetcherAgent()
    agent.anthropic = MagicMock()
    return agent


def _haiku_message(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    return msg


def _load_main_module():
    engine_module = types.ModuleType("engine")
    resume_builder_module = types.ModuleType("engine.resume_builder")
    resume_builder_module.build_final_docx = lambda **kwargs: b""
    engine_module.resume_builder = resume_builder_module
    sys.modules["engine"] = engine_module
    sys.modules["engine.resume_builder"] = resume_builder_module

    orchestrator_module = types.ModuleType("orchestrator")
    orchestrator_module.Orchestrator = MagicMock()
    sys.modules["orchestrator"] = orchestrator_module

    parser_module = types.ModuleType("parser")
    parser_module.parse_resume = lambda *_args, **_kwargs: ""
    sys.modules["parser"] = parser_module

    spec = importlib.util.spec_from_file_location("main", BACKEND_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["main"] = module
    spec.loader.exec_module(module)
    return module


class TestParseHaikuJson:
    """Tests for Haiku JSON parsing helpers."""

    def test_parse_found_payload(self):
        payload = json.dumps({
            "status": "found",
            "employer": "Google India",
            "jd_text": "We are looking for a Software Engineer with Python experience.",
        })
        parsed = JDFetcherAgent._parse_haiku_json(payload)
        assert parsed is not None
        assert parsed["status"] == "found"
        assert "Software Engineer" in parsed["jd_text"]

    def test_parse_strips_markdown_fences(self):
        inner = json.dumps({"status": "found", "employer": "TCS", "jd_text": "Some JD text here"})
        parsed = JDFetcherAgent._parse_haiku_json(f"```json\n{inner}\n```")
        assert parsed is not None
        assert parsed["jd_text"] == "Some JD text here"

    def test_parse_empty_returns_none(self):
        assert JDFetcherAgent._parse_haiku_json("") is None


class TestComputeConfidence:
    """Tests for heuristic JD confidence scoring."""

    def test_long_jd_with_sections_scores_high(self):
        text = (
            "Responsibilities: build APIs. Requirements: Python, Kubernetes. "
            "We need a Software Engineer at Google India. " * 30
        )
        score = JDFetcherAgent._compute_confidence(text, "Google India", "Software Engineer")
        assert score >= 0.55

    def test_empty_text_scores_zero(self):
        assert JDFetcherAgent._compute_confidence("", "Google", "SDE") == 0.0


class TestJDFetcherBuildQueries:
    """Tests for ATS-first Serper query construction."""

    def test_build_queries_returns_five(self):
        queries = JDFetcherAgent._build_queries("Google India", "Software Engineer / SDE")
        assert len(queries) == 5
        joined = " ".join(queries).lower()
        assert "greenhouse" in joined or "lever" in joined or "workday" in joined

    def test_build_queries_normalizes_other_type_manually(self):
        queries = JDFetcherAgent._build_queries("Other (type manually)", "Data Scientist")
        joined = " ".join(queries)
        assert "Other (type manually)" not in joined


class TestJDFetcherFetch:
    """Integration tests for fetch() with mocked Serper + Anthropic."""

    def setup_method(self):
        self.agent = _agent_with_mocks()

    def _serper_organic(self) -> list[dict]:
        return [
            {"title": "SDE", "link": "https://boards.greenhouse.io/acme/jobs/1", "snippet": "s1"},
        ]

    def _found_haiku_payload(self) -> str:
        return json.dumps({
            "status": "found",
            "employer": "Google India",
            "jd_text": (
                "Responsibilities: build scalable services. "
                "Requirements: Python, distributed systems. "
                "Software Engineer role at Google India."
            ) * 5,
        })

    def test_fetch_found_success(self):
        jd_text = (
            "Responsibilities: build scalable services. "
            "Requirements: Python, distributed systems. "
            "Software Engineer role at Google India."
        ) * 8
        candidate = jf._Candidate(
            url="https://boards.greenhouse.io/acme/jobs/1",
            text=jd_text,
            score=0.9,
            method="test",
        )
        with patch.object(self.agent, "_serper_search", return_value=self._serper_organic()):
            with patch.object(self.agent, "_extract_for_url", return_value=candidate):
                result = self.agent.fetch("Google India", "Software Engineer")
        assert result.status == "found"
        assert result.jd_text is not None
        assert result.company == "Google India"

    def test_fetch_not_found_when_no_urls(self):
        with patch.object(self.agent, "_serper_search", return_value=[]):
            result = self.agent.fetch("BYJU'S", "Data Scientist")
        assert result.status == "not_found"

    def test_fetch_error_without_anthropic_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            agent = JDFetcherAgent()
        result = agent.fetch("Google India", "SDE")
        assert result.status == "error"
        assert "ANTHROPIC" in (result.error_message or "")

    def test_fetch_result_is_jdfetchresult_type(self):
        with patch.object(self.agent, "_serper_search", return_value=[]):
            result = self.agent.fetch("TCS", "Technical Lead")
        assert isinstance(result, JDFetchResult)

    def test_direct_url_skips_serper(self):
        jd_text = (
            "Responsibilities: ship features. Requirements: Python. "
            "Software Engineer at Google India."
        ) * 8
        candidate = jf._Candidate(
            url="https://boards.greenhouse.io/google/jobs/12345",
            text=jd_text,
            score=0.9,
            method="test",
        )
        with patch.object(self.agent, "_fetch_single_url") as mock_direct:
            mock_direct.return_value = JDFetchResult(
                status="found",
                jd_text=jd_text,
                source_url="https://boards.greenhouse.io/google/jobs/12345",
                company="Google India",
                role="SDE",
            )
            with patch.object(self.agent, "_serper_search") as mock_serper:
                result = self.agent.fetch(
                    "Google India",
                    "SDE",
                    direct_url="https://boards.greenhouse.io/google/jobs/12345",
                )
        mock_serper.assert_not_called()
        mock_direct.assert_called_once()
        assert result.status == "found"

    def test_direct_url_returns_not_found_when_extraction_empty(self):
        with patch.object(self.agent, "_fetch_jina", return_value=""):
            result = self.agent.fetch(
                "Google India",
                "SDE",
                direct_url="https://example.com/jobs/1",
            )
        assert result.status == "not_found"


class TestFetchJDEndpoint:
    """Tests for the FastAPI endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        module = _load_main_module()
        return TestClient(module.app)

    def test_endpoint_returns_200_on_valid_request(self, client):
        with patch("main.JDFetcherAgent") as mock_agent:
            mock_result = JDFetchResult(
                status="found",
                jd_text="Test JD content here",
                source_url="https://example.com/jobs/1",
                company="Google India",
                role="Software Engineer",
            )
            mock_agent.return_value.fetch.return_value = mock_result
            response = client.post("/api/fetch-jd", json={
                "company": "Google India",
                "role": "Software Engineer",
            })
        assert response.status_code == 200

    def test_endpoint_returns_correct_shape(self, client):
        with patch("main.JDFetcherAgent") as mock_agent:
            mock_result = JDFetchResult(
                status="found",
                jd_text="Test JD",
                source_url="https://example.com",
                company="TCS",
                role="SDE",
            )
            mock_agent.return_value.fetch.return_value = mock_result
            response = client.post("/api/fetch-jd", json={"company": "TCS", "role": "SDE"})
        data = response.json()
        assert "status" in data
        assert "jd_text" in data
        assert "source_url" in data
        assert "company" in data
        assert "role" in data
        assert "alternatives" in data
        assert "error_message" in data

    def test_endpoint_passes_company_and_role_to_agent(self, client):
        with patch("main.JDFetcherAgent") as mock_agent:
            mock_result = JDFetchResult(
                status="not_found",
                jd_text=None,
                source_url=None,
                company="Flipkart",
                role="ML Engineer",
            )
            mock_agent.return_value.fetch.return_value = mock_result
            client.post("/api/fetch-jd", json={"company": "Flipkart", "role": "ML Engineer"})
            mock_agent.return_value.fetch.assert_called_once_with(
                company="Flipkart",
                role="ML Engineer",
                direct_url=None,
            )

    def test_endpoint_passes_direct_url_to_agent(self, client):
        with patch("main.JDFetcherAgent") as mock_agent:
            mock_result = JDFetchResult(
                status="found",
                jd_text="Test JD",
                source_url="https://example.com/job",
                company="Google India",
                role="SDE",
            )
            mock_agent.return_value.fetch.return_value = mock_result
            client.post(
                "/api/fetch-jd",
                json={
                    "company": "Google India",
                    "role": "SDE",
                    "direct_url": "https://example.com/job",
                },
            )
            mock_agent.return_value.fetch.assert_called_once_with(
                company="Google India",
                role="SDE",
                direct_url="https://example.com/job",
            )

    def test_endpoint_rejects_missing_company(self, client):
        response = client.post("/api/fetch-jd", json={"role": "SDE"})
        assert response.status_code == 422

    def test_endpoint_rejects_missing_role(self, client):
        response = client.post("/api/fetch-jd", json={"company": "Google India"})
        assert response.status_code == 422

    def test_endpoint_rejects_empty_body(self, client):
        response = client.post("/api/fetch-jd", json={})
        assert response.status_code == 422

    def test_endpoint_status_values(self, client):
        for status in ["found", "not_found", "multiple", "error"]:
            with patch("main.JDFetcherAgent") as mock_agent:
                mock_result = JDFetchResult(
                    status=status,
                    jd_text=None,
                    source_url=None,
                    company="Test Co",
                    role="Test Role",
                )
                mock_agent.return_value.fetch.return_value = mock_result
                response = client.post("/api/fetch-jd", json={
                    "company": "Test Co",
                    "role": "Test Role",
                })
            assert response.status_code == 200
            assert response.json()["status"] == status


class TestJDFetchData:
    """Validate backend constants mirror frontend selection data."""

    def test_top_companies_has_15_entries(self):
        from constants.jd_fetch_data import TOP_COMPANIES

        assert len(TOP_COMPANIES) == 15

    def test_top_companies_includes_required_entries(self):
        from constants.jd_fetch_data import TOP_COMPANIES

        required = ["TCS", "Infosys", "Google India", "Flipkart", "Zomato"]
        for company in required:
            assert company in TOP_COMPANIES, f"Missing required company: {company}"

    def test_top_roles_covers_all_groups(self):
        from constants.jd_fetch_data import TOP_ROLES_BY_GROUP

        assert "Engineering" in TOP_ROLES_BY_GROUP
        assert "Data & AI" in TOP_ROLES_BY_GROUP
        assert "Product & Business" in TOP_ROLES_BY_GROUP

    def test_top_roles_engineering_has_minimum_entries(self):
        from constants.jd_fetch_data import TOP_ROLES_BY_GROUP

        assert len(TOP_ROLES_BY_GROUP["Engineering"]) >= 10

    def test_total_roles_count(self):
        from constants.jd_fetch_data import TOP_ROLES_BY_GROUP

        total = sum(len(value) for value in TOP_ROLES_BY_GROUP.values())
        assert total == 15


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("ANTHROPIC_API_KEY") and os.getenv("SERPER_API_KEY")),
    reason="Integration test requires ANTHROPIC_API_KEY and SERPER_API_KEY",
)
def test_real_fetch_api():
    agent = JDFetcherAgent()
    result = agent.fetch("Google India", "Software Engineer / SDE")
    assert result.status in ["found", "not_found"]
    assert result.status != "error"
