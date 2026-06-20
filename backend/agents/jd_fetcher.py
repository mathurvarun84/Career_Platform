"""
JD Auto-Fetch Agent (v2 — ATS-aware pipeline).

Pipeline
--------
    User Input
        |
        v
    Serper Search   (5 ATS-first query variants, India-region)
        |
        v
    ATS URL Classifier  (greenhouse / lever / workday / generic)
        |
        v
    Provider-Specific Extractor
        - Greenhouse / Lever -> deterministic HTML parse via BeautifulSoup
        - Workday / Generic  -> Jina AI Reader -> Claude Haiku extraction
        |
        v
    Confidence score (heuristic, 0.0..1.0)
        - >= 0.55 -> return found
        - <  0.55 -> rescue with Haiku + aggressive prompt + best partial text
        |
        v
    JDFetchResult

Design notes
------------
- Stops at the first extraction whose confidence >= 0.55. Otherwise it keeps
  the highest-scoring partial across all queries and tries one rescue pass.
- URLs are deduplicated across queries by normalized form.
- Per-URL failures are logged and skipped — the agent NEVER raises out of
  fetch(). Top-level errors collapse to status="error".
- Every LLM call is logged with a "[LLM]" prefix so cost can be audited via
  `grep "\[LLM\]" logs.txt`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import httpx
from anthropic import Anthropic
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from backend.agents.ats_classifier import ATSProvider, classify_url


logger = logging.getLogger("jd_fetcher")


def _utc_now_iso() -> str:
    """Return an API-friendly UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _configure_jd_fetcher_logging() -> None:
    """Attach a dedicated file handler once so JD fetch audit logs persist."""
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    log_path = logs_dir / "jd_fetcher.log"

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            existing_path = getattr(handler, "baseFilename", "")
            if existing_path == str(log_path):
                return

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = True


_configure_jd_fetcher_logging()


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SERPER_URL = "https://google.serper.dev/search"
JINA_READER_BASE = "https://r.jina.ai/"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Title-alias data — two separate files, two separate concerns:
#   role_taxonomy.json      -> role_family + seniority_ladder + generic_title
#                              (also the source of truth the frontend dropdown
#                              should be generated from — see jdFetchData.ts)
#   role_title_aliases.json -> company-specific internal titles per
#                              (role_family, seniority_rank), used only to
#                              widen search queries + confidence scoring.
# Neither file is required for the agent to function — both loaders fail
# soft to {} so a missing/malformed file degrades to current behavior
# (literal company/role strings only), never raises.
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ROLE_TAXONOMY_PATH = _DATA_DIR / "role_taxonomy.json"
ROLE_ALIASES_PATH = _DATA_DIR / "role_title_aliases.json"

USER_AGENT = "Mozilla/5.0 (compatible; JobBot/2.0)"

SERPER_TIMEOUT_SECONDS = 8.0
SCRAPE_TIMEOUT_SECONDS = 15.0
JINA_TIMEOUT_SECONDS = 15.0

SERPER_NUM_RESULTS = 5
RESULTS_PER_QUERY = 3
CONFIDENCE_THRESHOLD = 0.55

# Cap text fed into Haiku to keep token cost predictable.
MAX_TEXT_CHARS = 8000
HAIKU_MAX_TOKENS = 1500
HAIKU_RESCUE_MAX_TOKENS = 2000

STRIPPED_TAGS = ("script", "style", "nav", "footer", "header", "noscript")


# Aggregator/listing hosts whose URLs do NOT identify the employer (so we
# defer to the LLM-extracted employer field for these).
_AGGREGATOR_HOSTS = (
    "linkedin.com",
    "indeed.com",
    "naukri.com",
    "glassdoor.",
    "instahyre.com",
    "shine.com",
    "uplers.com",
    "hubmub.com",
    "x.com",
    "twitter.com",
    "instagram.com",
    "facebook.com",
    "ycombinator.com",
    "wellfound.com",
    "angel.co",
    "monster.com",
)


def _extract_url_employer(url: str) -> str:
    """Pull the employer slug out of a known-ATS URL, or "" when undeterminable.

    For ATS hosts the URL is authoritative — `moengage.hire.trakstar.com` is
    MoEngage's ATS, full stop. We use that to reject wrong-employer URLs before
    spending Jina + Haiku tokens on them.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.lower())
    except Exception:
        return ""
    host = parsed.netloc
    path_parts = [p for p in parsed.path.split("/") if p]
    if not host:
        return ""

    if "boards.greenhouse.io" in host:
        return path_parts[0] if path_parts else ""
    if host.endswith(".greenhouse.io"):
        return host.split(".")[0]
    if host == "jobs.lever.co":
        return path_parts[0] if path_parts else ""
    if host.endswith(".lever.co"):
        return host.split(".")[0]
    if "myworkdayjobs.com" in host:
        return host.split(".")[0]
    if host.endswith(".trakstar.com"):
        return host.split(".")[0]
    if host.endswith(".workable.com"):
        return host.split(".")[0]
    if host.endswith(".bamboohr.com"):
        return host.split(".")[0]
    if host.endswith(".smartrecruiters.com"):
        return host.split(".")[0]
    if host.endswith(".ashbyhq.com"):
        return host.split(".")[0]

    # Aggregators don't identify the employer in the URL.
    if any(agg in host for agg in _AGGREGATOR_HOSTS):
        return ""

    return ""


def _employer_matches(candidate_employer: str, target_company: str) -> bool:
    """Return True if `candidate_employer` plausibly belongs to `target_company`.

    Used both for URL-host slugs (deterministic) and LLM-extracted employer
    names (fuzzy). Empty candidate_employer means "unknown" and yields True so
    we don't reject on missing data.
    """
    if not candidate_employer or not target_company.strip():
        return True

    target = target_company.strip().lower()
    if target == "other (type manually)":
        return True

    employer_compact = re.sub(r"[\s\-_/.,]+", "", candidate_employer.lower())
    target_compact = re.sub(r"[\s\-_/.,]+", "", target)
    if not employer_compact or not target_compact:
        return True

    if employer_compact in target_compact or target_compact in employer_compact:
        return True

    target_tokens = [t for t in re.split(r"[\s\-_/.,()]+", target) if len(t) >= 3]
    if any(token in employer_compact for token in target_tokens):
        return True

    employer_tokens = [
        t for t in re.split(r"[\s\-_/.,()]+", candidate_employer.lower()) if len(t) >= 3
    ]
    return any(token in target_compact for token in employer_tokens)


# --------------------------------------------------------------------------- #
# Role title aliases (company-specific internal titles)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load_role_aliases() -> dict[str, Any]:
    """Load role_title_aliases.json once per process. Never raises — a
    missing or malformed file just means no alias expansion happens, which
    is exactly today's behavior."""
    try:
        with open(ROLE_ALIASES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.warning("role_title_aliases load failed path=%s err=%s", ROLE_ALIASES_PATH, exc)
        return {}


def _resolve_company_alias_key(company: str, aliases: dict[str, Any]) -> str:
    """Map a free-text company name (as typed/selected by the user) to its
    key in role_title_aliases.json, using the same compacted-string fuzzy
    match `_employer_matches` already uses elsewhere in this file — so a
    user-selected 'Amazon' or a slightly different casing/spacing still
    resolves to the 'amazon' entry."""
    if not company:
        return ""
    target_compact = re.sub(r"[\s\-_/.,]+", "", company.lower())
    if not target_compact:
        return ""
    for key, entry in aliases.items():
        if key.startswith("_") or not isinstance(entry, dict):
            continue
        display = entry.get("display_name", key)
        display_compact = re.sub(r"[\s\-_/.,]+", "", str(display).lower())
        key_compact = re.sub(r"[\s\-_/.,]+", "", key.lower())
        if target_compact in (display_compact, key_compact):
            return key
    return ""


def _resolve_title_aliases(
    company: str,
    role_family: str | None,
    seniority_rank: str | None,
) -> list[str]:
    """Look up company-specific internal titles for (role_family, seniority_rank).

    Returns [] whenever role_family/seniority_rank weren't supplied (e.g. a
    free-text 'Other' role with no taxonomy match) or the company/family/rank
    isn't in the table yet — callers treat [] as 'no aliasing, fall back to
    the literal role string', so an incomplete table never breaks a search
    that would have worked before this feature existed.
    """
    if not role_family or not seniority_rank:
        return []
    aliases = _load_role_aliases()
    company_key = _resolve_company_alias_key(company, aliases)
    if not company_key:
        return []
    family_block = aliases.get(company_key, {}).get(role_family, {})
    if not isinstance(family_block, dict):
        return []
    titles = family_block.get(seniority_rank, [])
    return [t for t in titles if isinstance(t, str) and t.strip()]


# --------------------------------------------------------------------------- #
# Public types
# --------------------------------------------------------------------------- #
class JDFetchResult(BaseModel):
    """Wire contract with /api/fetch-jd and the frontend. Do not rename."""

    status: Literal["found", "not_found", "multiple", "error"]
    jd_text: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: str = Field(default_factory=_utc_now_iso)
    is_cached: bool = False
    company: str
    role: str
    error_message: Optional[str] = None


@dataclass
class _Candidate:
    """One extraction attempt — its text, source URL, score and method label."""

    url: str
    text: str
    score: float
    method: str  # greenhouse_parse | lever_parse | jina_reader | rescue


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
HAIKU_EXTRACT_PROMPT = """You extract job descriptions from web page content.

Target company: {company}
Target role: {role}
Source URL: {source_url}

--- PAGE CONTENT ---
{page_text}
--- END PAGE CONTENT ---

INSTRUCTIONS
- The "employer" field MUST be the EXACT name of the company that is hiring
  for this posting, as it appears on the page (often near the title, in the
  header, or in the URL). It is NOT necessarily the target company above.
  If the page mentions multiple companies (e.g. customer logos, "we work with X"),
  the employer is the one that owns the posting, not the ones being mentioned.
- If the employer on the page is clearly different from the target company,
  still fill "employer" honestly — the caller will reject the mismatch.
- If the page has ANY job-related content for this company/role, set status to "found".
- Extract partial JDs when possible. Do NOT return "not_found" unless the page is
  clearly irrelevant (a news article, a generic team landing page with no role,
  a 404, a login wall).
- Reconstruct a clean, well-formatted job description in jd_text including
  overview, responsibilities, requirements and tech stack when present.

Respond with ONLY this JSON. No markdown fences. No preamble. No commentary.
{{
  "status": "found" | "not_found",
  "employer": "<exact name of the company that owns this posting>",
  "job_title": "...",
  "responsibilities": ["..."],
  "requirements": ["..."],
  "tech_stack": ["..."],
  "jd_text": "full clean JD text reconstructed from page"
}}"""


HAIKU_RESCUE_PROMPT = """You are extracting a job description from low-quality
or incomplete page content. Be aggressive — extract whatever job-related content
exists, even if fragmentary.

Target company: {company}
Target role: {role}
Source URL: {source_url}

--- PAGE CONTENT ---
{page_text}
--- END PAGE CONTENT ---

RULES
- The "employer" field MUST be the EXACT name of the company that owns the
  posting, as shown on the page. If it's clearly different from the target
  company above, still fill it honestly — the caller will reject the mismatch.
- Do NOT return "not_found" unless this page has ZERO job content.
- Stitch together fragments. Infer structure from headings, bullets and lists.
- Even if only partial info is present (e.g., responsibilities but no
  requirements), still set status to "found" and put everything you can
  extract into jd_text.
- Output a coherent jd_text even from messy input.

Respond with ONLY this JSON. No markdown fences. No preamble. No commentary.
{{
  "status": "found" | "not_found",
  "employer": "<exact name of the company that owns this posting>",
  "job_title": "...",
  "responsibilities": ["..."],
  "requirements": ["..."],
  "tech_stack": ["..."],
  "jd_text": "full reconstructed JD text"
}}"""


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class JDFetcherAgent:
    """Fetch a job description for a given (company, role) using the
    Serper -> ATS-classify -> provider-extract -> Haiku-rescue pipeline."""

    def __init__(self) -> None:
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.jina_api_key = os.getenv("JINA_API_KEY")  # optional, lifts rate limits
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=anthropic_key) if anthropic_key else None
        self.model = HAIKU_MODEL

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #
    def fetch(
        self,
        company: str,
        role: str,
        direct_url: str | None = None,
        role_family: str | None = None,
        seniority_rank: str | None = None,
    ) -> JDFetchResult:
        """Main entry point. Returns a JDFetchResult and never raises.

        role_family / seniority_rank are optional — pass them when the
        caller knows them (e.g. the role came from the TOP_ROLES_BY_GROUP
        dropdown, which carries both). When omitted (e.g. a free-text
        'Other' role), behavior is identical to before this feature existed:
        only the literal `role` string is searched/scored.
        """
        try:
            if self.anthropic is None:
                return JDFetchResult(
                    status="error",
                    company=company,
                    role=role,
                    error_message="ANTHROPIC_API_KEY not configured",
                )

            if direct_url:
                return self._fetch_single_url(
                    direct_url, company, role, role_family, seniority_rank,
                )

            if not self.serper_api_key:
                return JDFetchResult(
                    status="error",
                    company=company,
                    role=role,
                    error_message="SERPER_API_KEY not configured",
                )

            return self._fetch_via_search(company, role, role_family, seniority_rank)

        except Exception as exc:  # noqa: BLE001 - top-level safety net
            logger.exception("fetch failed company=%r role=%r", company, role)
            return JDFetchResult(
                status="error",
                company=company,
                role=role,
                error_message=str(exc),
            )

    # ------------------------------------------------------------------ #
    # Direct URL path (used by /api/fetch-jd when caller supplies a URL)
    # ------------------------------------------------------------------ #
    def _fetch_single_url(
        self,
        url: str,
        company: str,
        role: str,
        role_family: str | None = None,
        seniority_rank: str | None = None,
    ) -> JDFetchResult:
        provider = classify_url(url)
        logger.info("direct_url url=%s provider=%s", url, provider.value)

        aliases = _resolve_title_aliases(company, role_family, seniority_rank)
        if aliases:
            logger.info("title_aliases resolved company=%r aliases=%r", company, aliases)

        candidate = self._extract_for_url(url, provider, company, role, aliases)

        if candidate is None or not candidate.text:
            logger.info("status=not_found (direct_url, no text extracted) url=%s", url)
            return JDFetchResult(
                status="not_found",
                company=company,
                role=role,
                source_url=url,
            )

        logger.info(
            "confidence url=%s score=%.2f method=%s",
            candidate.url, candidate.score, candidate.method,
        )

        if candidate.score >= CONFIDENCE_THRESHOLD:
            logger.info("status=found url=%s score=%.2f", url, candidate.score)
            return JDFetchResult(
                status="found",
                jd_text=candidate.text,
                source_url=url,
                company=company,
                role=role,
            )

        rescued = self._rescue(candidate, company, role, aliases)
        if rescued is not None and rescued.score >= CONFIDENCE_THRESHOLD:
            logger.info("status=found (via rescue) url=%s score=%.2f", url, rescued.score)
            return JDFetchResult(
                status="found",
                jd_text=rescued.text,
                source_url=url,
                company=company,
                role=role,
            )

        logger.info("status=not_found (rescue insufficient) url=%s", url)
        return JDFetchResult(
            status="not_found",
            company=company,
            role=role,
            source_url=url,
        )

    # ------------------------------------------------------------------ #
    # Search path
    # ------------------------------------------------------------------ #
    def _fetch_via_search(
        self,
        company: str,
        role: str,
        role_family: str | None = None,
        seniority_rank: str | None = None,
    ) -> JDFetchResult:
        aliases = _resolve_title_aliases(company, role_family, seniority_rank)
        if aliases:
            logger.info("title_aliases resolved company=%r aliases=%r", company, aliases)

        queries = self._build_queries(company, role, aliases)
        seen_urls: set[str] = set()
        best: _Candidate | None = None

        for query in queries:
            try:
                organic = self._serper_search(query)
            except Exception as exc:  # noqa: BLE001 - tolerate per-query failure
                logger.warning("serper query failed query=%r err=%s", query, exc)
                continue

            logger.info("serper query=%r results=%d", query, len(organic))

            for item in organic[:RESULTS_PER_QUERY]:
                url = (item.get("link") or "").strip()
                if not url:
                    continue
                normalized = url.rstrip("/").lower()
                if normalized in seen_urls:
                    continue
                seen_urls.add(normalized)

                provider = classify_url(url)
                logger.info("processing url=%s provider=%s", url, provider.value)

                candidate = self._extract_for_url(url, provider, company, role, aliases)
                if candidate is None or not candidate.text:
                    continue

                logger.info(
                    "confidence url=%s score=%.2f method=%s",
                    candidate.url, candidate.score, candidate.method,
                )

                if candidate.score >= CONFIDENCE_THRESHOLD:
                    logger.info(
                        "status=found url=%s score=%.2f method=%s",
                        candidate.url, candidate.score, candidate.method,
                    )
                    return JDFetchResult(
                        status="found",
                        jd_text=candidate.text,
                        source_url=candidate.url,
                        company=company,
                        role=role,
                    )

                if best is None or candidate.score > best.score:
                    best = candidate

        # All extractions came back below threshold (or empty) — try rescue.
        if best is not None and best.text:
            rescued = self._rescue(best, company, role, aliases)
            if rescued is not None and rescued.score >= CONFIDENCE_THRESHOLD:
                logger.info(
                    "status=found (via rescue) url=%s score=%.2f",
                    best.url, rescued.score,
                )
                return JDFetchResult(
                    status="found",
                    jd_text=rescued.text,
                    source_url=best.url,
                    company=company,
                    role=role,
                )

        logger.info(
            "status=not_found (best_score=%.2f)",
            best.score if best else 0.0,
        )
        return JDFetchResult(
            status="not_found",
            company=company,
            role=role,
            source_url=best.url if best else None,
        )

    # ------------------------------------------------------------------ #
    # Per-URL extraction dispatcher
    # ------------------------------------------------------------------ #
    def _extract_for_url(
        self,
        url: str,
        provider: ATSProvider,
        company: str,
        role: str,
        aliases: list[str] | None = None,
    ) -> _Candidate | None:
        # Cheap pre-flight guard: the URL host alone tells us the employer for
        # ATS-hosted postings (greenhouse/lever/workday/trakstar/...). If it
        # disagrees with the requested company, drop it before spending any
        # Jina + Haiku tokens on extraction.
        url_employer = _extract_url_employer(url)
        if url_employer and not _employer_matches(url_employer, company):
            logger.info(
                "rejecting url=%s reason=url_employer_mismatch url_employer=%r company=%r",
                url, url_employer, company,
            )
            return None

        try:
            if provider == ATSProvider.GREENHOUSE:
                text = self._parse_greenhouse(url)
                method = "greenhouse_parse"
            elif provider == ATSProvider.LEVER:
                text = self._parse_lever(url)
                method = "lever_parse"
            else:
                # WORKDAY and GENERIC both go through Jina + Haiku — Workday's
                # JSON endpoints are session-token dependent and unreliable.
                markdown = self._fetch_jina(url)
                if not markdown:
                    return None
                text = self._haiku_extract(markdown, company, role, url)
                method = "jina_reader"
        except Exception as exc:  # noqa: BLE001 - tolerate per-URL failure
            logger.warning("extraction failed url=%s err=%s", url, exc)
            return None

        if not text or not text.strip():
            return None

        score = self._compute_confidence(text, company, role, aliases)
        return _Candidate(url=url, text=text, score=score, method=method)

    # ------------------------------------------------------------------ #
    # Greenhouse / Lever deterministic parsers
    # ------------------------------------------------------------------ #
    def _parse_greenhouse(self, url: str) -> str:
        html = self._fetch_html(url)
        if not html:
            return ""
        soup = self._soup(html)
        if soup is None:
            return ""

        for tag in soup(list(STRIPPED_TAGS)):
            tag.decompose()

        container = (
            soup.select_one("div#app_body")
            or soup.select_one("div.content")
            or soup.find("article")
        )
        if container is None:
            logger.debug("greenhouse: no known container url=%s", url)
            return ""

        title_el = soup.select_one("h1.app-title") or soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        body_text = container.get_text(separator="\n", strip=True)

        location_el = soup.select_one(".location") or soup.select_one(".app-location")
        location = location_el.get_text(strip=True) if location_el else ""

        parts = [p for p in (title, location, body_text) if p]
        return "\n\n".join(parts)[:MAX_TEXT_CHARS]

    def _parse_lever(self, url: str) -> str:
        html = self._fetch_html(url)
        if not html:
            return ""
        soup = self._soup(html)
        if soup is None:
            return ""

        for tag in soup(list(STRIPPED_TAGS)):
            tag.decompose()

        container = (
            soup.select_one("div.content")
            or soup.select_one('div[data-qa="job-description"]')
            or soup.find("main")
        )
        if container is None:
            logger.debug("lever: no known container url=%s", url)
            return ""

        title_el = soup.select_one("h2.posting-headline") or soup.find("h2")
        title = title_el.get_text(strip=True) if title_el else ""

        categories_el = soup.select_one(".posting-categories") or soup.select_one(".posting-category")
        categories = categories_el.get_text(separator=" | ", strip=True) if categories_el else ""

        body_text = container.get_text(separator="\n", strip=True)

        parts = [p for p in (title, categories, body_text) if p]
        return "\n\n".join(parts)[:MAX_TEXT_CHARS]

    @staticmethod
    def _soup(html: str) -> BeautifulSoup | None:
        try:
            return BeautifulSoup(html, "lxml")
        except Exception:
            try:
                return BeautifulSoup(html, "html.parser")
            except Exception as exc:  # noqa: BLE001
                logger.debug("BeautifulSoup parse failed err=%s", exc)
                return None

    # ------------------------------------------------------------------ #
    # HTTP fetch helpers
    # ------------------------------------------------------------------ #
    def _fetch_html(self, url: str) -> str:
        try:
            with httpx.Client(
                timeout=SCRAPE_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("html fetch failed url=%s err=%s", url, exc)
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("html fetch unexpected error url=%s err=%s", url, exc)
            return ""

    def _fetch_jina(self, url: str) -> str:
        """Fetch a URL through https://r.jina.ai/ which returns clean markdown."""
        jina_url = f"{JINA_READER_BASE}{url}"
        headers = {"User-Agent": USER_AGENT}
        if self.jina_api_key:
            headers["Authorization"] = f"Bearer {self.jina_api_key}"
        try:
            with httpx.Client(
                timeout=JINA_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(jina_url)
                response.raise_for_status()
                return response.text[:MAX_TEXT_CHARS]
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("jina fetch failed url=%s err=%s", url, exc)
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("jina fetch unexpected error url=%s err=%s", url, exc)
            return ""

    # ------------------------------------------------------------------ #
    # Serper
    # ------------------------------------------------------------------ #
    def _serper_search(self, query: str) -> list[dict[str, Any]]:
        headers = {
            "X-API-KEY": self.serper_api_key or "",
            "Content-Type": "application/json",
        }
        body = {"q": query, "gl": "in", "num": SERPER_NUM_RESULTS}
        with httpx.Client(timeout=SERPER_TIMEOUT_SECONDS) as client:
            response = client.post(SERPER_URL, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        organic = payload.get("organic") or []
        return organic if isinstance(organic, list) else []

    # ------------------------------------------------------------------ #
    # Query building (ATS-first)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_queries(
        company: str,
        role: str,
        aliases: list[str] | None = None,
    ) -> list[str]:
        company_clean = company.strip()
        role_clean = role.strip()
        if company_clean.lower() == "other (type manually)":
            company_clean = role_clean.split("/")[0].strip() or "India"

        queries = [
            f'site:jobs.lever.co "{company_clean}" "{role_clean}"',
            f'site:boards.greenhouse.io "{company_clean}" "{role_clean}"',
            f'site:myworkdayjobs.com "{company_clean}" "{role_clean}"',
            f'"{company_clean}" careers "{role_clean}" -recruiter -blog',
            f'"{company_clean}" "{role_clean}" hiring',
        ]

        # Alias expansion: a company's internal title (e.g. Amazon's "SDE 2"
        # for the dropdown's "Senior Software Engineer") often appears on the
        # ATS verbatim when the generic dropdown label never does. Bounded to
        # the single most-canonical alias (first in the list) so a company
        # with many known variants doesn't multiply Serper call volume.
        if aliases:
            alias_title = aliases[0]
            queries.extend([
                f'site:jobs.lever.co "{company_clean}" "{alias_title}"',
                f'site:boards.greenhouse.io "{company_clean}" "{alias_title}"',
                f'"{company_clean}" "{alias_title}" hiring',
            ])

        return queries

    # ------------------------------------------------------------------ #
    # Haiku extraction + rescue
    # ------------------------------------------------------------------ #
    def _haiku_extract(
        self,
        page_text: str,
        company: str,
        role: str,
        url: str,
    ) -> str:
        if not page_text or self.anthropic is None:
            return ""
        logger.info(
            "[LLM] model=%s reason=generic_extraction url=%s",
            HAIKU_MODEL, url,
        )
        prompt = HAIKU_EXTRACT_PROMPT.format(
            company=company,
            role=role,
            source_url=url,
            page_text=page_text[:MAX_TEXT_CHARS],
        )
        return self._call_haiku(
            prompt, max_tokens=HAIKU_MAX_TOKENS, url=url, target_company=company,
        )

    def _rescue(
        self,
        candidate: _Candidate,
        company: str,
        role: str,
        aliases: list[str] | None = None,
    ) -> _Candidate | None:
        if self.anthropic is None or not candidate.text:
            return None

        logger.info(
            "[LLM] model=%s reason=rescue_path confidence=%.2f",
            HAIKU_MODEL, candidate.score,
        )
        logger.info("rescue triggered url=%s best_score=%.2f", candidate.url, candidate.score)

        prompt = HAIKU_RESCUE_PROMPT.format(
            company=company,
            role=role,
            source_url=candidate.url,
            page_text=candidate.text[:MAX_TEXT_CHARS],
        )
        rescued_text = self._call_haiku(
            prompt,
            max_tokens=HAIKU_RESCUE_MAX_TOKENS,
            url=candidate.url,
            target_company=company,
        )
        if not rescued_text:
            return None

        score = self._compute_confidence(rescued_text, company, role, aliases)
        logger.info("rescue confidence=%.2f url=%s", score, candidate.url)
        return _Candidate(
            url=candidate.url,
            text=rescued_text,
            score=score,
            method="rescue",
        )

    def _call_haiku(
        self,
        prompt: str,
        max_tokens: int,
        url: str,
        target_company: str,
    ) -> str:
        """Invoke Claude Haiku and return the parsed jd_text, or "" on failure.

        Cross-checks the LLM-extracted "employer" field against `target_company`
        and rejects the candidate (returns "") on mismatch — this catches the
        aggregator-page case where the URL host doesn't identify the employer
        but the LLM can read it off the page (e.g. a LinkedIn listing that
        actually surfaces a MoEngage JD when the user asked for Flipkart).
        """
        if self.anthropic is None:
            return ""
        try:
            message = self.anthropic.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - tolerate API failure per URL
            logger.warning("haiku call failed url=%s err=%s", url, exc)
            return ""

        raw = "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", None) == "text"
        ).strip()

        parsed = self._parse_haiku_json(raw)
        if not parsed:
            logger.warning("haiku json parse failed url=%s", url)
            return ""

        if parsed.get("status") != "found":
            return ""

        parsed_employer = (parsed.get("employer") or "").strip()
        if parsed_employer and not _employer_matches(parsed_employer, target_company):
            logger.info(
                "rejecting url=%s reason=llm_employer_mismatch parsed_employer=%r company=%r",
                url, parsed_employer, target_company,
            )
            return ""

        return (parsed.get("jd_text") or "").strip()

    @staticmethod
    def _parse_haiku_json(raw: str) -> Optional[dict[str, Any]]:
        if not raw:
            return None
        text = raw.strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                data = json.loads(text[start:end])
            except (ValueError, json.JSONDecodeError):
                return None

        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------ #
    # Confidence scoring
    # ------------------------------------------------------------------ #
    @staticmethod
    def _compute_confidence(
        jd_text: str,
        company: str,
        role: str,
        aliases: list[str] | None = None,
    ) -> float:
        """Heuristic confidence in [0.0, 1.0] for a candidate JD text.

        `aliases` (company-specific internal titles, e.g. Amazon's 'SDE 2'
        for a dropdown role of 'Senior Software Engineer') widen the role-
        match component below so a correctly-found JD doesn't get scored
        down just because the company never uses the generic dropdown
        wording. An exact alias phrase match counts as a full role match;
        otherwise we take whichever of (literal role tokens, alias tokens)
        scores higher, so this can only help a score, never hurt one
        relative to pre-alias behavior.
        """
        if not jd_text:
            return 0.0

        text_lower = jd_text.lower()
        score = 0.0

        if len(jd_text) > 300:
            score += 0.25
        if len(jd_text) > 800:
            score += 0.15

        section_keywords = (
            "responsibilities",
            "requirements",
            "qualifications",
            "what you'll do",
        )
        if any(kw in text_lower for kw in section_keywords):
            score += 0.25

        role_words = [
            w for w in re.split(r"[\s/\-_,()]+", role.lower())
            if len(w) >= 3 and not w.isdigit()
        ]
        role_match_ratio = 0.0
        if role_words:
            matched = sum(1 for w in role_words if w in text_lower)
            role_match_ratio = matched / len(role_words)

        for alias in aliases or []:
            alias_lower = alias.strip().lower()
            if not alias_lower:
                continue
            if alias_lower in text_lower:
                role_match_ratio = 1.0
                break
            alias_words = [
                w for w in re.split(r"[\s/\-_,()]+", alias_lower)
                if len(w) >= 3 and not w.isdigit()
            ]
            if alias_words:
                alias_matched = sum(1 for w in alias_words if w in text_lower)
                role_match_ratio = max(role_match_ratio, alias_matched / len(alias_words))

        score += 0.20 * role_match_ratio

        company_clean = company.strip().lower()
        if company_clean and company_clean in text_lower:
            score += 0.15

        return min(score, 1.0)
