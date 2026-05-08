"""
Dry-run validation of JDFetcherAgent with fully mocked dependencies.
Run: python scripts/validate_jd_fetcher.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.agents.jd_fetcher import JDFetcherAgent
from backend.schemas.jd_fetch_schema import FetchJDResponse
from backend.services.serper_client import SearchResult

MOCK_SEARCH_RESULTS = [
    SearchResult(
        title="Software Engineer | Google Careers",
        url="https://careers.google.com/jobs/1",
        snippet="Join Google as SDE. 2+ years required.",
    ),
    SearchResult(
        title="Google SDE on LinkedIn",
        url="https://linkedin.com/jobs/123",
        snippet="Google India is hiring Software Engineers.",
    ),
    SearchResult(
        title="Google Software Engineer - Naukri",
        url="https://naukri.com/job/456",
        snippet="Role: SDE at Google Bangalore.",
    ),
]

MOCK_GPT_RESPONSE = """{
  "status": "found",
  "jd_text": "Software Engineer at Google India\\n\\nAbout the Role:\\nWe are looking for a talented Software Engineer to join our team in Bangalore. You will design, develop, and maintain software systems at scale.\\n\\nResponsibilities:\\n- Design and implement scalable backend systems\\n- Collaborate with cross-functional teams\\n- Write clean, testable code\\n\\nRequirements:\\n- B.Tech/M.Tech in CS or related field\\n- 2+ years of software development experience\\n- Strong knowledge of data structures and algorithms\\n- Proficiency in Python, Java, or C++",
  "source_url": "https://careers.google.com/jobs/1",
  "alternatives": null
}"""


def run_validation():
    print("\n=== JD Fetcher Dry-Run Validation ===\n")
    errors = []

    # Test 1: Standard fetch path
    print("TEST 1: Standard search path (Serper -> GPT)...")
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
        agent.model = "gpt-4.1-mini"
        agent.serper = MagicMock()
        agent.serper.search_multi.return_value = MOCK_SEARCH_RESULTS
        agent.openai_client = MagicMock()
        agent.openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=MOCK_GPT_RESPONSE))]
        )
        result = agent.fetch("Google India", "Software Engineer / SDE")
        assert isinstance(result, FetchJDResponse), "Result must be FetchJDResponse"
        assert result.status == "found", f"Expected 'found', got '{result.status}'"
        assert result.jd_text is not None, "jd_text must not be None"
        assert len(result.jd_text) > 200, f"jd_text too short: {len(result.jd_text)} chars"
        assert result.company == "Google India"
        assert result.role == "Software Engineer / SDE"
        print(f"  PASS - status=found, jd_text={len(result.jd_text)} chars, source={result.source_url}")

    # Test 2: Multiple path
    print("\nTEST 2: Multiple roles disambiguation...")
    mock_multiple = """{
      "status": "multiple",
      "jd_text": null,
      "source_url": null,
      "alternatives": [
        {"title": "Software Engineer (SDE-1)", "level": "0–2 years", "url": "https://careers.google.com/sde1"},
        {"title": "Senior Software Engineer (SDE-2)", "level": "3–6 years", "url": "https://careers.google.com/sde2"}
      ]
    }"""
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
        agent.model = "gpt-4.1-mini"
        agent.serper = MagicMock()
        agent.serper.search_multi.return_value = MOCK_SEARCH_RESULTS
        agent.openai_client = MagicMock()
        agent.openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=mock_multiple))]
        )
        result = agent.fetch("Google India", "Software Engineer / SDE")
        assert result.status == "multiple"
        assert result.alternatives is not None and len(result.alternatives) == 2
        assert result.jd_text is None
        print(f"  PASS - status=multiple, {len(result.alternatives)} alternatives found")

    # Test 3: Not found path
    print("\nTEST 3: Not found path...")
    mock_not_found = '{"status": "not_found", "jd_text": null, "source_url": null, "alternatives": null}'
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
        agent.model = "gpt-4.1-mini"
        agent.serper = MagicMock()
        agent.serper.search_multi.return_value = []
        agent.openai_client = MagicMock()
        agent.openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=mock_not_found))]
        )
        result = agent.fetch("BYJU'S", "Data Scientist")
        assert result.status == "not_found"
        assert result.jd_text is None
        print("  PASS - status=not_found")

    # Test 4: Error resilience - Serper fails
    print("\nTEST 4: Error resilience (Serper failure)...")
    from backend.services.serper_client import SerperError

    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
        agent.model = "gpt-4.1-mini"
        agent.serper = MagicMock()
        agent.serper.search_multi.side_effect = SerperError("Invalid API key")
        agent.openai_client = MagicMock()
        result = agent.fetch("TCS", "SDE")
        assert result.status == "error"
        assert result.error_message is not None
        print(f"  PASS - status=error, message='{result.error_message}'")

    # Test 5: Markdown fence stripping
    print("\nTEST 5: Markdown fence stripping in _parse_gpt_response...")
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
        fenced = f"```json\n{MOCK_GPT_RESPONSE}\n```"
        result = agent._parse_gpt_response(fenced, "Google", "SDE")
        assert result.status == "found"
        print("  PASS - markdown fences stripped correctly")

    # Test 6: Direct URL path skips Serper
    print("\nTEST 6: Direct URL path (second fetch, no Serper)...")
    with patch.object(JDFetcherAgent, "__init__", lambda self: None):
        agent = JDFetcherAgent.__new__(JDFetcherAgent)
        agent.model = "gpt-4.1-mini"
        agent.serper = MagicMock()
        agent.openai_client = MagicMock()
        agent.openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=MOCK_GPT_RESPONSE))]
        )
        with patch.object(agent.__class__, "_fetch_url_content", return_value="<job posting content>"):
            result = agent.fetch("Google India", "SDE-2", direct_url="https://careers.google.com/sde2")
        agent.serper.search_multi.assert_not_called()
        assert result.status == "found"
        print("  PASS - Serper not called, status=found")

    print(f"\n{'=' * 40}")
    if errors:
        print(f"FAILED - {len(errors)} error(s):")
        for err in errors:
            print(f"   - {err}")
    else:
        print("ALL 6 VALIDATION TESTS PASSED")
    print(f"{'=' * 40}\n")


if __name__ == "__main__":
    run_validation()
