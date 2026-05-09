"""
ATS provider classifier.

Detects which Applicant Tracking System (ATS) is hosting a job posting URL so
the JD fetcher can pick the right extraction strategy:

- Greenhouse / Lever -> deterministic HTML parse (no LLM cost)
- Workday            -> Jina Reader + Haiku (their JSON endpoints are
                        session-token dependent and break constantly)
- Generic            -> Jina Reader + Haiku
"""

from __future__ import annotations

from enum import Enum


class ATSProvider(Enum):
    """Hosting ATS provider for a job posting URL."""

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    GENERIC = "generic"


# Substring fingerprints. Order matters only for documentation; the classify
# function checks each independent group below.
_GREENHOUSE_MARKERS = ("boards.greenhouse.io", "greenhouse.io/jobs")
_LEVER_MARKERS = ("jobs.lever.co",)
_WORKDAY_MARKERS = ("myworkdayjobs.com", "workday.com")


def classify_url(url: str) -> ATSProvider:
    """Classify a job posting URL by its hosting ATS.

    Pure string-matching — no network calls. Anything we don't recognize
    falls through to GENERIC, which routes to Jina Reader + Haiku.
    """
    if not url:
        return ATSProvider.GENERIC

    url_lower = url.lower()

    if any(marker in url_lower for marker in _GREENHOUSE_MARKERS):
        return ATSProvider.GREENHOUSE
    if any(marker in url_lower for marker in _LEVER_MARKERS):
        return ATSProvider.LEVER
    if any(marker in url_lower for marker in _WORKDAY_MARKERS):
        return ATSProvider.WORKDAY

    return ATSProvider.GENERIC
