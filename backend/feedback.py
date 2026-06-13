"""User feedback collection: quick reactions, feature pulses, PMF signals, free text."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth import get_current_user_id
from backend.db import get_db
from backend.email_service import send_feedback_email

router = APIRouter()
logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    """Body for POST /api/feedback."""

    run_id: Optional[str] = None
    session_id: Optional[str] = None
    moment_type: str
    # quick_reaction | feature_pulse | pmf_signal | reengagement | product_feedback
    feature_name: Optional[str] = None
    response_value: Optional[str] = None
    failure_category: Optional[str] = None
    open_text: Optional[str] = None
    include_email: bool = True
    ats_score: Optional[float] = None
    role_fit_band: Optional[str] = None
    run_count: Optional[int] = None


@router.post("/api/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Persist a feedback response and update display state to avoid re-prompting."""
    logger.info(
        "[FEEDBACK] moment=%s feature=%s user=%s",
        request.moment_type,
        request.feature_name,
        user_id[:8],
    )

    db = get_db()

    # Truncate open text — 500 chars for product_feedback, 280 for everything else
    char_limit = 500 if request.moment_type == "product_feedback" else 280
    open_text = request.open_text[:char_limit] if request.open_text else None

    # Write response row
    db.table("feedback_responses").insert({
        "user_id": user_id,
        "run_id": request.run_id,
        "session_id": request.session_id,
        "moment_type": request.moment_type,
        "feature_name": request.feature_name,
        "response_value": request.response_value,
        "failure_category": request.failure_category,
        "open_text": open_text,
        "include_email": request.include_email,
        "ats_score_at_feedback": request.ats_score,
        "role_fit_band_at_feedback": request.role_fit_band,
        "run_count_at_feedback": request.run_count,
    }).execute()

    # Update display state to prevent re-showing this moment
    updates: dict = {"last_active_at": datetime.now(timezone.utc).isoformat()}

    if request.moment_type == "feature_pulse" and request.feature_name:
        updates[f"feature_pulse_{request.feature_name}_done"] = True
    elif request.moment_type == "pmf_signal":
        updates["pmf_completed"] = True
        updates["pmf_shown"] = True
    elif request.moment_type == "reengagement":
        updates["last_reengagement_shown_at"] = datetime.now(timezone.utc).isoformat()

    db.table("feedback_display_state").upsert({
        "user_id": user_id,
        **updates,
    }).execute()

    # Send email only when open_text is present
    if open_text:
        await send_feedback_email(
            moment_type=request.moment_type,
            response_value=request.response_value,
            open_text=open_text,
            include_email=request.include_email,
            user_id=user_id,
            ats_score=request.ats_score,
            role_fit_band=request.role_fit_band,
        )

    return {"ok": True}


@router.get("/api/feedback/state")
async def get_feedback_state(user_id: str = Depends(get_current_user_id)):
    """Return the user's feedback display state, seeding a default row on first call."""
    db = get_db()

    result = (
        db.table("feedback_display_state")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not result.data:
        # First-time user — seed their display state row
        db.table("feedback_display_state").insert({"user_id": user_id}).execute()
        return _default_state()

    state = result.data

    # Increment session_count if last_active_at was on a different calendar day
    last_active = state.get("last_active_at")
    if last_active:
        last_day = datetime.fromisoformat(last_active).date()
        today = datetime.now(timezone.utc).date()
        if last_day < today:
            new_count = (state.get("session_count") or 0) + 1
            db.table("feedback_display_state").update({
                "session_count": new_count,
                "last_active_at": datetime.now(timezone.utc).isoformat(),
            }).eq("user_id", user_id).execute()
            state["session_count"] = new_count

    return state


def _default_state() -> dict:
    return {
        "feature_pulse_coach_done": False,
        "feature_pulse_interview_done": False,
        "feature_pulse_rewriter_done": False,
        "feature_pulse_gap_analysis_done": False,
        "pmf_shown": False,
        "pmf_skipped": False,
        "pmf_completed": False,
        "last_reengagement_shown_at": None,
        "session_count": 0,
        "last_active_at": None,
    }
