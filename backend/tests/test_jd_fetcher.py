from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.agents.jd_fetcher import JDFetcherAgent
from backend.schemas.jd_fetch_schema import FetchJDResponse
from backend.services.serper_client import SearchResult, SerperError


def _agent_with_mocks() -> JDFetcherAgent:
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
    agent.model = "gpt-4.1-mini"
    agent.serper = MagicMock()
    agent.openai_client = MagicMock()
    return agent


def _completion(content: str) -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def _search_results() -> list[SearchResult]:
    return [
        SearchResult("t1", "https://a.com/1", "s1"),
        SearchResult("t2", "https://a.com/2", "s2"),
        SearchResult("t3", "https://a.com/3", "s3"),
    ]


def test_tc_f_01_fetch_found():
    agent = _agent_with_mocks()
    agent.serper.search_multi.return_value = _search_results()
    long_jd = "Software Engineer role. " * 20
    agent.openai_client.chat.completions.create.return_value = _completion(
        f'{{"status":"found","jd_text":"{long_jd}","source_url":"https://a.com/1","alternatives":null}}'
    )
    res = agent.fetch("Google India", "Software Engineer / SDE")
    assert res.status == "found"
    assert res.jd_text is not None and len(res.jd_text) > 200


def test_tc_f_02_fetch_multiple():
    agent = _agent_with_mocks()
    agent.serper.search_multi.return_value = _search_results()
    agent.openai_client.chat.completions.create.return_value = _completion(
        '{"status":"multiple","jd_text":null,"source_url":null,"alternatives":[{"title":"SDE-1","level":"0-2 years","url":"https://x/1"},{"title":"SDE-2","level":"3-6 years","url":"https://x/2"}]}'
    )
    res = agent.fetch("Google India", "Software Engineer / SDE")
    assert res.status == "multiple"
    assert res.alternatives is not None and len(res.alternatives) == 2
    assert res.jd_text is None


def test_tc_f_03_fetch_not_found():
    agent = _agent_with_mocks()
    agent.serper.search_multi.return_value = _search_results()
    agent.openai_client.chat.completions.create.return_value = _completion(
        '{"status":"not_found","jd_text":null,"source_url":null,"alternatives":null}'
    )
    res = agent.fetch("Google India", "Software Engineer / SDE")
    assert res.status == "not_found"


def test_tc_f_04_fetch_error_on_serper_error():
    agent = _agent_with_mocks()
    agent.serper.search_multi.side_effect = SerperError("API key invalid")
    res = agent.fetch("Google India", "Software Engineer / SDE")
    assert res.status == "error"
    assert res.error_message is not None and "API key invalid" in res.error_message


def test_tc_f_05_fetch_error_on_openai_exception():
    agent = _agent_with_mocks()
    agent.serper.search_multi.return_value = _search_results()
    agent.openai_client.chat.completions.create.side_effect = RuntimeError("OpenAI failed")
    res = agent.fetch("Google India", "Software Engineer / SDE")
    assert res.status == "error"


def test_tc_f_06_direct_url_skips_serper():
    agent = _agent_with_mocks()
    with patch.object(agent, "_fetch_url_content", return_value="job content"):
        agent.openai_client.chat.completions.create.return_value = _completion(
            '{"status":"found","jd_text":"' + ("abc " * 80) + '","source_url":"https://u","alternatives":null}'
        )
        res = agent.fetch("Google India", "SDE", direct_url="https://careers.google.com/jobs/12345")
    agent.serper.search_multi.assert_not_called()
    assert res.status == "found"


def test_tc_f_07_direct_url_returns_error_when_fetch_fails():
    agent = _agent_with_mocks()
    with patch.object(agent, "_fetch_url_content", side_effect=RuntimeError("URL fetch failure: connection")):
        res = agent.fetch("Google India", "SDE", direct_url="https://careers.google.com/jobs/12345")
    assert res.status == "error"
    assert res.error_message is not None and "URL fetch failure" in res.error_message


def test_tc_f_08_parse_strips_markdown_fences():
    agent = _agent_with_mocks()
    raw = '```json\n{"status":"found","jd_text":"' + ("x" * 250) + '","source_url":"https://a","alternatives":null}\n```'
    res = agent._parse_gpt_response(raw, "Google", "SDE")
    assert res.status == "found"


def test_tc_f_09_parse_fallback_for_non_json_long_blob():
    agent = _agent_with_mocks()
    raw = "A" * 500
    res = agent._parse_gpt_response(raw, "Google", "SDE")
    assert res.status == "found"
    assert res.jd_text == raw


def test_tc_f_10_parse_error_for_non_json_short_blob():
    agent = _agent_with_mocks()
    res = agent._parse_gpt_response("Sorry, I could not find a JD.", "Google", "SDE")
    assert res.status == "error"


def test_tc_f_11_build_queries_returns_three():
    agent = _agent_with_mocks()
    queries = agent._build_queries("Google India", "Software Engineer / SDE")
    assert len(queries) == 3
    assert all(q.strip() for q in queries)
    joined = " ".join(queries).lower()
    assert ("careers" in joined) or ("jobs" in joined)
    assert "linkedin" in joined
    assert ("naukri" in joined) or ("indeed" in joined)


def test_tc_f_12_build_queries_normalizes_other_type_manually():
    agent = _agent_with_mocks()
    queries = agent._build_queries("Other (type manually)", "Data Scientist")
    joined = " ".join(queries)
    assert "Other (type manually)" not in joined


def test_tc_f_13_fetch_includes_company_and_role_in_prompt():
    agent = _agent_with_mocks()
    agent.serper.search_multi.return_value = _search_results()
    agent.openai_client.chat.completions.create.return_value = _completion(
        '{"status":"not_found","jd_text":null,"source_url":null,"alternatives":null}'
    )
    agent.fetch("Flipkart", "Data Scientist")
    _, kwargs = agent.openai_client.chat.completions.create.call_args
    user_prompt = kwargs["messages"][1]["content"]
    assert "Flipkart" in user_prompt
    assert "Data Scientist" in user_prompt


@pytest.mark.parametrize(
    "scenario",
    ["serper_error", "openai_error", "parse_short_text", "direct_url_error"],
)
def test_tc_f_14_fetch_never_raises(scenario: str):
    agent = _agent_with_mocks()
    if scenario == "serper_error":
        agent.serper.search_multi.side_effect = SerperError("bad key")
        result = agent.fetch("X", "Y")
    elif scenario == "openai_error":
        agent.serper.search_multi.return_value = _search_results()
        agent.openai_client.chat.completions.create.side_effect = RuntimeError("boom")
        result = agent.fetch("X", "Y")
    elif scenario == "parse_short_text":
        agent.serper.search_multi.return_value = _search_results()
        agent.openai_client.chat.completions.create.return_value = _completion("not json")
        result = agent.fetch("X", "Y")
    else:
        with patch.object(agent, "_fetch_url_content", side_effect=RuntimeError("URL fetch failure")):
            result = agent.fetch("X", "Y", direct_url="https://x.com")
    assert isinstance(result, FetchJDResponse)


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("SERPER_API_KEY")),
    reason="Integration test requires OPENAI_API_KEY and SERPER_API_KEY",
)
def test_tc_f_int_01_fetch_real_api():
    agent = JDFetcherAgent()
    response = agent.fetch("Google India", "Software Engineer / SDE")
    assert response.status in ["found", "multiple", "not_found"]
    assert response.status != "error"
    if response.status == "found":
        assert response.jd_text is not None and len(response.jd_text) > 500
        print(response.source_url)
        print(response.jd_text[:300])


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") and os.getenv("SERPER_API_KEY")),
    reason="Integration test requires OPENAI_API_KEY and SERPER_API_KEY",
)
def test_tc_f_int_02_fetch_direct_url_real_api():
    agent = JDFetcherAgent()
    response = agent.fetch(
        "Google India",
        "Software Engineer / SDE",
        direct_url="https://www.linkedin.com/jobs/view/software-engineer-at-google-0000000000",
    )
    assert response.status == "found"
    assert response.jd_text is not None
