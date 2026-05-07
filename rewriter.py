"""Compatibility re-export for gates that import ``rewriter`` from repo root."""

from agents.rewriter import (  # noqa: F401
    COMPANY_HEADER_START,
    COMPANY_ROLE_START,
    HEADER_END,
    RewriterAgent,
    SectionRewrite,
    _ensure_experience_markers,
)
