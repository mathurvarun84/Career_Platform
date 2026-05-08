"""SerperClient - Thin wrapper around Serper Dev Google Search API."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests


SERPER_URL = "https://google.serper.dev/search"
DEFAULT_TIMEOUT_SECONDS = 8


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SerperError(Exception):
    """Raised when Serper requests fail."""


class SerperClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is required for SerperClient")

    @staticmethod
    def _normalize_url(url: str) -> str:
        return url.rstrip("/")

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        """Call Serper and return top organic results."""
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        body = {
            "q": query,
            "num": num_results,
            "gl": "in",
            "hl": "en",
        }
        try:
            response = requests.post(
                SERPER_URL,
                headers=headers,
                json=body,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.exceptions.Timeout as exc:
            raise SerperError("Serper request timed out after 8 seconds") from exc
        except requests.RequestException as exc:
            raise SerperError(f"Serper network failure: {exc}") from exc

        if response.status_code != 200:
            detail = response.text.strip() if response.text else "no response body"
            if response.status_code == 429:
                raise SerperError(f"Serper rate limit (429): {detail}")
            raise SerperError(f"Serper HTTP {response.status_code}: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SerperError("Serper returned invalid JSON") from exc

        organic = payload.get("organic") or []
        results: list[SearchResult] = []
        for item in organic[:num_results]:
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=(item.get("link") or "").strip(),
                    snippet=(item.get("snippet") or "").strip(),
                )
            )
        return results

    def search_multi(
        self,
        queries: list[str],
        num_results_each: int = 4,
    ) -> list[SearchResult]:
        """Run multiple searches and deduplicate by normalized URL."""
        merged: list[SearchResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            for result in self.search(query=query, num_results=num_results_each):
                normalized = self._normalize_url(result.url)
                if normalized and normalized not in seen_urls:
                    seen_urls.add(normalized)
                    merged.append(result)

        return merged
