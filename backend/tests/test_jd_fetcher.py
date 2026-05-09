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

from backend.agents.jd_fetcher import JDFetcherAgent, JDFetchResult
from backend.services.serper_client import SearchResult, SerperError


def _agent_with_mocks() -> JDFetcherAgent:
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
    agent.model = "gpt-4.1-mini"
    agent.serper = MagicMock()
    agent.openai_client = MagicMock()
    return agent


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


class TestJDFetcherParse:
    """Tests for parse logic."""

    def setup_method(self):
        self.agent = _agent_with_mocks()

    def _make_message(self, text: str):
        block = MagicMock()
        block.type = "text"
        block.text = text
        msg = MagicMock()
        msg.content = [block]
        return msg

    def test_parse_found_status(self):
        payload = json.dumps({
            "status": "found",
            "jd_text": "We are looking for a Software Engineer...",
            "source_url": "https://careers.google.com/jobs/123",
            "alternatives": None,
        })
        result = self.agent._parse(self._make_message(payload), "Google India", "SDE")
        assert result.status == "found"
        assert "Software Engineer" in result.jd_text
        assert result.source_url == "https://careers.google.com/jobs/123"
        assert result.company == "Google India"
        assert result.role == "SDE"

    def test_parse_not_found_status(self):
        payload = json.dumps({
            "status": "not_found",
            "jd_text": None,
            "source_url": None,
            "alternatives": None,
        })
        result = self.agent._parse(self._make_message(payload), "BYJU'S", "Data Scientist")
        assert result.status == "not_found"
        assert result.jd_text is None
        assert result.company == "BYJU'S"

    def test_parse_multiple_status(self):
        payload = json.dumps({
            "status": "multiple",
            "jd_text": None,
            "source_url": None,
            "alternatives": [
                {"title": "SDE-1", "level": "0-2 years", "url": "https://flipkart.com/jobs/1"},
                {"title": "SDE-2", "level": "3-6 years", "url": "https://flipkart.com/jobs/2"},
            ],
        })
        result = self.agent._parse(self._make_message(payload), "Flipkart", "Software Engineer")
        assert result.status == "multiple"
        assert len(result.alternatives) == 2
        assert result.alternatives[0]["title"] == "SDE-1"
        assert result.alternatives[1]["level"] == "3-6 years"

    def test_parse_strips_markdown_fences(self):
        inner = json.dumps({"status": "found", "jd_text": "Some JD text here", "source_url": None})
        wrapped = f"```json\n{inner}\n```"
        result = self.agent._parse(self._make_message(wrapped), "TCS", "Backend Developer")
        assert result.status == "found"
        assert result.jd_text == "Some JD text here"

    def test_parse_strips_plain_fences(self):
        inner = json.dumps({"status": "not_found", "jd_text": None, "source_url": None})
        wrapped = f"```\n{inner}\n```"
        result = self.agent._parse(self._make_message(wrapped), "Infosys", "QA Engineer")
        assert result.status == "not_found"

    def test_parse_fallback_long_non_json(self):
        long_text = "We are seeking a talented engineer. " * 20
        result = self.agent._parse(self._make_message(long_text), "Amazon India", "SDE")
        assert result.status == "found"
        assert result.jd_text == long_text
        assert result.error_message is not None

    def test_parse_error_on_short_non_json(self):
        result = self.agent._parse(self._make_message("Something went wrong"), "Paytm", "PM")
        assert result.status == "error"
        assert result.error_message is not None

    def test_parse_empty_response(self):
        result = self.agent._parse(self._make_message(""), "Ola", "Mobile Developer")
        assert result.status == "error"

    def test_parse_preserves_company_and_role(self):
        payload = json.dumps({"status": "not_found", "jd_text": None, "source_url": None})
        result = self.agent._parse(self._make_message(payload), "PhonePe", "Full Stack Developer")
        assert result.company == "PhonePe"
        assert result.role == "Full Stack Developer"


class TestJDFetcherBuildPrompt:
    """Tests for prompt construction."""

    def setup_method(self):
        self.agent = _agent_with_mocks()

    def test_build_queries_returns_three(self):
        queries = self.agent._build_queries("Google India", "Software Engineer / SDE")
        assert len(queries) == 3
        assert all(query.strip() for query in queries)
        joined = " ".join(queries).lower()
        assert ("careers" in joined) or ("jobs" in joined)
        assert "linkedin" in joined
        assert ("naukri" in joined) or ("indeed" in joined)

    def test_build_queries_normalizes_other_type_manually(self):
        queries = self.agent._build_queries("Other (type manually)", "Data Scientist")
        joined = " ".join(queries)
        assert "Other (type manually)" not in joined

    def test_format_results_contains_titles_urls_and_snippets(self):
        formatted = self.agent._format_results([
            SearchResult("Title 1", "https://a.com", "Snippet 1"),
            SearchResult("Title 2", "https://b.com", "Snippet 2"),
        ])
        assert "Title 1" in formatted
        assert "https://a.com" in formatted
        assert "Snippet 2" in formatted

    def test_parse_gpt_response_strips_fences(self):
        raw = '```json\n{"status":"found","jd_text":"Some JD","source_url":null,"alternatives":null}\n```'
        result = self.agent._parse_gpt_response(raw, "TCS", "SDE")
        assert result.status == "found"

    def test_parse_gpt_response_fallback_long_text(self):
        raw = "A" * 500
        result = self.agent._parse_gpt_response(raw, "Google", "SDE")
        assert result.status == "found"
        assert result.jd_text == raw

    def test_parse_gpt_response_error_for_short_text(self):
        result = self.agent._parse_gpt_response("Sorry, I could not find a JD.", "Google", "SDE")
        assert result.status == "error"


class TestJDFetcherFetch:
    """Integration tests for fetch() with mocked Serper + OpenAI."""

    def setup_method(self):
        self.agent = _agent_with_mocks()

    def _completion(self, content: str) -> MagicMock:
        return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])

    def _search_results(self) -> list[SearchResult]:
        return [
            SearchResult("t1", "https://a.com/1", "s1"),
            SearchResult("t2", "https://a.com/2", "s2"),
            SearchResult("t3", "https://a.com/3", "s3"),
        ]

    def test_fetch_found_success(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"found","jd_text":"We are looking for a skilled SDE...","source_url":"https://careers.google.com/jobs/456","alternatives":null}'
        )
        result = self.agent.fetch("Google India", "Software Engineer")
        assert result.status == "found"
        assert result.jd_text is not None
        assert result.company == "Google India"
        assert result.role == "Software Engineer"

    def test_fetch_not_found(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"not_found","jd_text":null,"source_url":null,"alternatives":null}'
        )
        result = self.agent.fetch("BYJU'S", "Data Scientist")
        assert result.status == "not_found"
        assert result.jd_text is None

    def test_fetch_multiple_roles(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"multiple","jd_text":null,"source_url":null,"alternatives":[{"title":"SDE-1","level":"0-2 years"},{"title":"SDE-2","level":"3-6 years"}]}'
        )
        result = self.agent.fetch("Flipkart", "Software Engineer")
        assert result.status == "multiple"
        assert result.alternatives is not None
        assert len(result.alternatives) == 2

    def test_fetch_catches_serper_exception(self):
        self.agent.serper.search_multi.side_effect = SerperError("API timeout")
        result = self.agent.fetch("Swiggy", "ML Engineer")
        assert result.status == "error"
        assert "API timeout" in result.error_message

    def test_fetch_catches_openai_exception(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.side_effect = RuntimeError("OpenAI failed")
        result = self.agent.fetch("Amazon India", "Backend Developer")
        assert result.status == "error"
        assert result.error_message is not None

    def test_fetch_api_is_called_with_correct_model(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"found","jd_text":"Some JD","source_url":null,"alternatives":null}'
        )
        self.agent.fetch("Paytm", "Product Manager")
        call_kwargs = self.agent.openai_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4.1-mini"

    def test_fetch_result_is_jdfetchresult_type(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"found","jd_text":"Some JD text","source_url":null,"alternatives":null}'
        )
        result = self.agent.fetch("TCS", "Technical Lead")
        assert isinstance(result, JDFetchResult)

    def test_fetch_with_special_characters_in_company_name(self):
        self.agent.serper.search_multi.return_value = self._search_results()
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"not_found","jd_text":null,"source_url":null,"alternatives":null}'
        )
        result = self.agent.fetch("BYJU'S", "Business Analyst")
        assert result.company == "BYJU'S"
        assert result.status == "not_found"

    def test_direct_url_skips_serper(self):
        self.agent.openai_client.chat.completions.create.return_value = self._completion(
            '{"status":"found","jd_text":"' + ("abc " * 80) + '","source_url":"https://u","alternatives":null}'
        )
        with patch.object(self.agent, "_fetch_url_content", return_value="job content"):
            result = self.agent.fetch("Google India", "SDE", direct_url="https://careers.google.com/jobs/12345")
        self.agent.serper.search_multi.assert_not_called()
        assert result.status == "found"

    def test_direct_url_returns_error_when_fetch_fails(self):
        with patch.object(self.agent, "_fetch_url_content", side_effect=RuntimeError("URL fetch failure: connection")):
            result = self.agent.fetch("Google India", "SDE", direct_url="https://careers.google.com/jobs/12345")
        assert result.status == "error"
        assert result.error_message is not None and "URL fetch failure" in result.error_message


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
    not (os.getenv("OPENAI_API_KEY") and os.getenv("SERPER_API_KEY")),
    reason="Integration test requires OPENAI_API_KEY and SERPER_API_KEY",
)
def test_real_fetch_api():
    agent = JDFetcherAgent()
    result = agent.fetch("Google India", "Software Engineer / SDE")
    assert result.status in ["found", "multiple", "not_found"]
    assert result.status != "error"
