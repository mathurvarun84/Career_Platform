"""JDFetcherAgent - Fetches JDs via Serper and GPT-4.1 Mini."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

from backend.schemas.jd_fetch_schema import FetchJDResponse
from backend.services.serper_client import SearchResult, SerperClient

SYSTEM_PROMPT = """You are a job description extraction specialist for an Indian job market platform.
Your sole task is to analyze web search results and extract or reconstruct a clean,
complete job description.

You respond ONLY with valid JSON. No markdown, no preamble, no explanation."""

SEARCH_USER_PROMPT_TEMPLATE = """Company: {company}
Role: {role}

Web search results:
{formatted_results}

---

EXTRACTION TASK:

Step 1 - Filter: Identify which results are genuine job postings.
REJECT these: blog posts, news articles, recruiter spam, results >12 months old (if date visible).
ACCEPT these: official company careers pages, LinkedIn job postings, Naukri/Indeed listings.

Step 2 - Extract from the best accepted result(s). Include ALL of the following if present:
  - Job title and level (e.g. SDE-1, SDE-2, L4, Senior)
  - Role summary / overview (2-4 sentences)
  - Key responsibilities (bulleted)
  - Required qualifications: education, years of experience, must-have skills
  - Preferred / nice-to-have qualifications
  - Tech stack and tools (explicit and implied)
  - Team or product context

Step 3 - Disambiguation: If you find multiple DISTINCT seniority levels of the same role
(e.g. SDE-1 AND SDE-2 AND SDE-3 as separate listings), return status "multiple" with
each variant listed. Do NOT merge them. Do NOT split a single JD artificially.

Step 4 - If no genuine JD found after filtering, return status "not_found".

Respond with ONLY this JSON (no markdown fences, no extra text):
{{
  "status": "found" | "not_found" | "multiple",
  "jd_text": "<complete reconstructed JD text, preserve all bullet points and structure, or null>",
  "source_url": "<canonical URL of best source, or null>",
  "alternatives": [
    {{"title": "Senior Software Engineer (SDE-2)", "level": "3–6 years", "url": "https://..."}}
  ]
}}

If status is "found", jd_text must be non-null and at least 200 characters.
If status is "multiple", jd_text must be null and alternatives must have 2+ items.
If status is "not_found", jd_text must be null."""

DIRECT_URL_PROMPT_TEMPLATE = """Company: {company}
Role: {role}

Raw page content from: {url}

---

{raw_content}

---

EXTRACTION TASK:
Extract the complete job description from this page content.
Include: job title, level, summary, responsibilities, requirements, tech stack, team context.

Respond with ONLY this JSON:
{{
  "status": "found" | "not_found",
  "jd_text": "<complete extracted JD text or null>",
  "source_url": "{url}",
  "alternatives": null
}}"""


class JDFetcherAgent:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.serper = SerperClient()
        self.model = "gpt-4.1-mini"

    def fetch(self, company: str, role: str, direct_url: str | None = None) -> FetchJDResponse:
        try:
            if direct_url:
                raw_content = self._fetch_url_content(direct_url)
                return self._call_gpt_extraction(
                    company=company,
                    role=role,
                    raw_content=raw_content,
                    direct_url=direct_url,
                )

            queries = self._build_queries(company=company, role=role)
            search_results = self.serper.search_multi(queries=queries, num_results_each=4)
            return self._call_gpt_extraction(
                company=company,
                role=role,
                search_results=search_results,
            )
        except Exception as exc:
            return FetchJDResponse(
                status="error",
                company=company,
                role=role,
                error_message=str(exc),
            )

    def _build_queries(self, company: str, role: str) -> list[str]:
        company_clean = company.strip()
        role_clean = role.strip()
        if company_clean.lower() == "other (type manually)":
            company_clean = role_clean.split("/")[0].strip() or "India"

        return [
            f'{company_clean} {role_clean} careers India site:{company_clean.split()[0].lower()}.com jobs',
            f'"{company_clean}" "{role_clean}" LinkedIn Jobs India',
            f'"{company_clean}" "{role_clean}" Naukri Indeed India',
        ]

    def _fetch_url_content(self, url: str) -> str:
        try:
            resp = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 JD-Fetcher"},
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"URL fetch failure: {exc}") from exc

        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000]

    def _format_results(self, results: list[SearchResult]) -> str:
        lines: list[str] = []
        for i, result in enumerate(results, 1):
            lines.append(f"[{i}] Title: {result.title}")
            lines.append(f"    URL: {result.url}")
            lines.append(f"    Snippet: {result.snippet}")
            lines.append("")
        return "\n".join(lines)

    def _call_gpt_extraction(
        self,
        company: str,
        role: str,
        search_results: list[SearchResult] | None = None,
        raw_content: str | None = None,
        direct_url: str | None = None,
    ) -> FetchJDResponse:
        if search_results is None and raw_content is None:
            raise ValueError("Either search_results or raw_content must be provided")

        if raw_content is not None:
            prompt = DIRECT_URL_PROMPT_TEMPLATE.format(
                company=company,
                role=role,
                url=direct_url or "",
                raw_content=raw_content,
            )
        else:
            prompt = SEARCH_USER_PROMPT_TEMPLATE.format(
                company=company,
                role=role,
                formatted_results=self._format_results(search_results or []),
            )

        completion = self.openai_client.chat.completions.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw = completion.choices[0].message.content or ""
        return self._parse_gpt_response(raw=raw, company=company, role=role)

    def _parse_gpt_response(self, raw: str, company: str, role: str) -> FetchJDResponse:
        text = raw.strip()
        fenced_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
        if fenced_match:
            text = fenced_match.group(1).strip()

        try:
            parsed: dict[str, Any] = json.loads(text)
            return FetchJDResponse(
                status=parsed.get("status", "error"),
                jd_text=parsed.get("jd_text"),
                source_url=parsed.get("source_url"),
                company=company,
                role=role,
                alternatives=parsed.get("alternatives"),
                error_message=parsed.get("error_message"),
            )
        except Exception:
            if len(text) > 300:
                return FetchJDResponse(
                    status="found",
                    jd_text=text,
                    source_url=None,
                    company=company,
                    role=role,
                    alternatives=None,
                )
            return FetchJDResponse(
                status="error",
                company=company,
                role=role,
                error_message="Unable to parse GPT response as valid JD JSON",
            )
