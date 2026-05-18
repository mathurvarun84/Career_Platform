from __future__ import annotations

import sys
import importlib.util
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(REPO_ROOT))

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

spec = importlib.util.spec_from_file_location("backend_main", BACKEND_DIR / "main.py")
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules["backend_main"] = module
spec.loader.exec_module(module)
app = module.app
from backend.schemas.jd_fetch_schema import FetchJDResponse


client = TestClient(app)


def test_tc_e_01_fetch_jd_found():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="found",
            jd_text="A" * 220,
            source_url="https://careers.tcs.com/1",
            company="TCS",
            role="Software Engineer / SDE",
            alternatives=None,
        )
        response = client.post("/api/fetch-jd", json={"company": "TCS", "role": "Software Engineer / SDE"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert body["jd_text"] is not None


def test_tc_e_02_fetch_jd_multiple():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="multiple",
            jd_text=None,
            source_url=None,
            company="TCS",
            role="SDE",
            alternatives=[
                {"title": "SDE-1", "level": "0-2 years", "url": "https://a.com"},
                {"title": "SDE-2", "level": "3-6 years", "url": "https://b.com"},
            ],
        )
        response = client.post("/api/fetch-jd", json={"company": "TCS", "role": "SDE"})
    assert response.status_code == 200
    assert len(response.json()["alternatives"]) > 0


def test_tc_e_03_fetch_jd_not_found():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="not_found",
            jd_text=None,
            source_url=None,
            company="TCS",
            role="SDE",
            alternatives=None,
        )
        response = client.post("/api/fetch-jd", json={"company": "TCS", "role": "SDE"})
    assert response.status_code == 200
    assert response.json()["jd_text"] is None


def test_tc_e_04_fetch_jd_error_status():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="error",
            jd_text=None,
            source_url=None,
            company="TCS",
            role="SDE",
            alternatives=None,
            error_message="Serper timeout",
        )
        response = client.post("/api/fetch-jd", json={"company": "TCS", "role": "SDE"})
    assert response.status_code == 200
    assert response.json()["status"] == "error"


def test_tc_e_05_returns_422_for_empty_company():
    response = client.post("/api/fetch-jd", json={"company": "", "role": "SDE"})
    assert response.status_code == 422


def test_tc_e_06_returns_422_for_missing_role():
    response = client.post("/api/fetch-jd", json={"company": "TCS"})
    assert response.status_code == 422


def test_tc_e_07_direct_url_is_passed_to_agent():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="found",
            jd_text="B" * 210,
            source_url="https://careers.google.com/123",
            company="Google India",
            role="SDE",
            alternatives=None,
        )
        client.post(
            "/api/fetch-jd",
            json={
                "company": "Google India",
                "role": "SDE",
                "direct_url": "https://careers.google.com/123",
            },
        )
    _, kwargs = mock_agent_cls.return_value.fetch.call_args
    assert kwargs["direct_url"] == "https://careers.google.com/123"


def test_tc_e_08_response_matches_schema_fields():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="found",
            jd_text="C" * 210,
            source_url="https://source.com/jd",
            company="Infosys",
            role="Data Scientist",
            alternatives=[{"title": "DS-1", "level": "1-3 years", "url": "https://alt.com/1"}],
            error_message=None,
        )
        response = client.post("/api/fetch-jd", json={"company": "Infosys", "role": "Data Scientist"})
    body = response.json()
    assert set(body.keys()) == {
        "status",
        "jd_text",
        "source_url",
        "fetched_at",
        "is_cached",
        "company",
        "role",
        "alternatives",
        "error_message",
    }


def test_tc_e_09_input_whitespace_is_stripped():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="not_found",
            jd_text=None,
            source_url=None,
            company="TCS",
            role="SDE",
            alternatives=None,
        )
        client.post("/api/fetch-jd", json={"company": "  TCS  ", "role": "  SDE  "})
    _, kwargs = mock_agent_cls.return_value.fetch.call_args
    assert kwargs["company"] == "TCS"
    assert kwargs["role"] == "SDE"


def test_tc_e_10_fetch_jd_route_reachable():
    with patch("backend_main.JDFetcherAgent") as mock_agent_cls:
        mock_agent_cls.return_value.fetch.return_value = FetchJDResponse(
            status="not_found",
            jd_text=None,
            source_url=None,
            company="TCS",
            role="SDE",
            alternatives=None,
        )
        response = client.post("/api/fetch-jd", json={"company": "TCS", "role": "SDE"})
    assert response.status_code != 404
