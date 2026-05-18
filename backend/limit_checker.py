"""Upload limit enforcement for free tier."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

logger = logging.getLogger(__name__)

_DEFAULT_FREE_TIER_MONTHLY_LIMIT = 2


def _free_tier_monthly_limit() -> int:
    """Monthly analysis cap for free tier (from FREE_TIER_MONTHLY_LIMIT in .env)."""
    raw = (os.getenv("FREE_TIER_MONTHLY_LIMIT") or "").strip()
    if not raw:
        return _DEFAULT_FREE_TIER_MONTHLY_LIMIT
    try:
        value = int(raw)
        if value < 1:
            raise ValueError("must be >= 1")
        return value
    except ValueError:
        logger.warning(
            "Invalid FREE_TIER_MONTHLY_LIMIT=%r; using default %d",
            raw,
            _DEFAULT_FREE_TIER_MONTHLY_LIMIT,
        )
        return _DEFAULT_FREE_TIER_MONTHLY_LIMIT


FREE_TIER_MONTHLY_LIMIT = _free_tier_monthly_limit()


def _get_or_create_usage_row(db, user_id: str) -> dict:
    """Return usage_limits row for user, creating a zeroed row if missing."""
    result = (
        db.table("usage_limits")
        .select("total_uploads, uploads_this_month")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    created = (
        db.table("usage_limits")
        .insert(
            {
                "user_id": user_id,
                "total_uploads": 0,
                "uploads_this_month": 0,
            }
        )
        .execute()
    )
    if created.data:
        return created.data[0]

    # Race: another request inserted first — re-fetch.
    retry = (
        db.table("usage_limits")
        .select("total_uploads, uploads_this_month")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if retry.data:
        return retry.data[0]

    raise RuntimeError(f"Could not load or create usage_limits for user {user_id}")


def get_upload_usage(db, user_id: str) -> dict:
    """Return current monthly usage without raising."""
    row = _get_or_create_usage_row(db, user_id)
    uploads_this_month = int(row.get("uploads_this_month") or 0)
    limit = int(row.get("monthly_limit") or FREE_TIER_MONTHLY_LIMIT)
    allowed = uploads_this_month < limit
    return {
        "allowed": allowed,
        "uploads_this_month": uploads_this_month,
        "limit": limit,
        "code": None if allowed else "LIMIT_REACHED",
    }


def check_upload_limit(db, user_id: str) -> None:
    """Check if user exceeded monthly limit. Raise 402 if over.

    Raises:
        HTTPException: 402 if limit reached
    """
    row = _get_or_create_usage_row(db, user_id)
    uploads_this_month = int(row.get("uploads_this_month") or 0)
    limit = int(row.get("monthly_limit") or FREE_TIER_MONTHLY_LIMIT)

    if uploads_this_month >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "LIMIT_REACHED",
                "message": f"Free tier limited to {limit} analyses per month",
                "uploads_this_month": uploads_this_month,
                "limit": limit,
            },
        )


def reset_user_limit(db, user_id: str) -> dict:
    """Admin: reset user's monthly upload counter."""
    result = (
        db.table("usage_limits")
        .update({"uploads_this_month": 0})
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise ValueError(f"User {user_id} not found")

    return result.data[0]
