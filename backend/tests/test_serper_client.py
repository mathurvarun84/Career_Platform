from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.serper_client import SearchResult, SerperClient, SerperError


def _mock_response(status_code: int = 200, payload: dict | None = None, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = payload or {}
    return response


@patch("backend.services.serper_client.requests.post")
def test_tc_s_01_search_returns_search_results(mock_post: MagicMock):
    mock_post.return_value = _mock_response(
        payload={
            "organic": [
                {"title": "A", "link": "https://a.com", "snippet": "sa"},
                {"title": "B", "link": "https://b.com", "snippet": "sb"},
                {"title": "C", "link": "https://c.com", "snippet": "sc"},
            ]
        }
    )
    client = SerperClient(api_key="test-key")
    results = client.search("query", num_results=3)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)
    assert all(r.title and r.url and r.snippet for r in results)


@patch("backend.services.serper_client.requests.post")
def test_tc_s_02_search_raises_on_401(mock_post: MagicMock):
    mock_post.return_value = _mock_response(status_code=401, text="Unauthorized")
    client = SerperClient(api_key="test-key")
    with pytest.raises(SerperError, match="401"):
        client.search("query")


@patch("backend.services.serper_client.requests.post")
def test_tc_s_03_search_raises_on_429(mock_post: MagicMock):
    mock_post.return_value = _mock_response(status_code=429, text="Too many requests")
    client = SerperClient(api_key="test-key")
    with pytest.raises(SerperError, match="rate limit|429"):
        client.search("query")


@patch("backend.services.serper_client.requests.post", side_effect=requests.exceptions.Timeout())
def test_tc_s_04_search_raises_on_timeout(_: MagicMock):
    client = SerperClient(api_key="test-key")
    with pytest.raises(SerperError):
        client.search("query")


@patch("backend.services.serper_client.requests.post")
def test_tc_s_05_search_handles_empty_organic(mock_post: MagicMock):
    mock_post.return_value = _mock_response(payload={"organic": []})
    client = SerperClient(api_key="test-key")
    results = client.search("query")
    assert results == []


def test_tc_s_06_search_multi_deduplicates_by_url():
    client = SerperClient(api_key="test-key")
    with patch.object(
        client,
        "search",
        side_effect=[
            [
                SearchResult("A", "https://x.com/a", "1"),
                SearchResult("B", "https://x.com/b", "2"),
            ],
            [
                SearchResult("B dup", "https://x.com/b/", "2"),
                SearchResult("C", "https://x.com/c", "3"),
            ],
        ],
    ):
        results = client.search_multi(["q1", "q2"])
    urls = [r.url.rstrip("/") for r in results]
    assert len(urls) == len(set(urls))


def test_tc_s_07_search_multi_merges_unique_results():
    client = SerperClient(api_key="test-key")
    with patch.object(
        client,
        "search",
        side_effect=[
            [SearchResult(f"A{i}", f"https://a.com/{i}", "a") for i in range(3)],
            [SearchResult(f"B{i}", f"https://b.com/{i}", "b") for i in range(3)],
        ],
    ):
        results = client.search_multi(["q1", "q2"], num_results_each=3)
    assert len(results) == 6


def test_tc_s_08_reads_api_key_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    client = SerperClient()
    assert client.api_key == "test-key"


def test_tc_s_09_raises_when_no_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    with pytest.raises(ValueError):
        SerperClient()


@patch("backend.services.serper_client.requests.post")
def test_tc_s_10_search_passes_correct_headers_and_body(mock_post: MagicMock):
    mock_post.return_value = _mock_response(payload={"organic": []})
    client = SerperClient(api_key="serper-key")
    client.search("my query", num_results=7)
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["X-API-KEY"] == "serper-key"
    assert kwargs["json"]["q"] == "my query"
    assert kwargs["json"]["num"] == 7
    assert kwargs["json"]["gl"] == "in"
    assert kwargs["json"]["hl"] == "en"
