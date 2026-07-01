"""
Product analytics tracker for RIP V2.
Writes structured events to Supabase analytics_events table.
All events fire async (non-blocking) — analytics must never break the main flow.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from supabase import create_client, Client

_supabase: Client | None = None


def _get_client() -> Client | None:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if url and key:
            _supabase = create_client(url, key)
        else:
            logging.warning(
                "Analytics: SUPABASE_URL or SUPABASE_SERVICE_KEY / "
                "SUPABASE_SERVICE_ROLE_KEY not set — events will be dropped"
            )
    return _supabase


def track(
    event_name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
    properties: dict[str, Any] | None = None,
    ats_score: int | None = None,
    jd_match_score: int | None = None,
    role_fit_band: str | None = None,
    has_jd: bool | None = None,
    seniority: str | None = None,
) -> None:
    """
    Fire a non-blocking analytics event.
    Silently swallows all exceptions — analytics must never break the main flow.
    """
    try:
        client = _get_client()
        if client is None:
            return

        row: dict[str, Any] = {
            "event_name": event_name,
            "session_id": session_id or "unknown",
            "properties": properties or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if user_id:                    row["user_id"]        = user_id
        if run_id:                     row["run_id"]          = run_id
        if ats_score is not None:      row["ats_score"]       = ats_score
        if jd_match_score is not None: row["jd_match_score"]  = jd_match_score
        if role_fit_band:              row["role_fit_band"]   = role_fit_band
        if has_jd is not None:         row["has_jd"]          = has_jd
        if seniority:                  row["seniority"]       = seniority

        client.table("analytics_events").insert(row).execute()

    except Exception as exc:
        logging.warning("Analytics.track failed (non-fatal): %s", exc)
