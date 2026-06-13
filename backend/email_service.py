"""Resend-based email notifications for the feedback system."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FEEDBACK_RECIPIENT = "varun@zenteiq.ai"
FROM_ADDRESS = "feedback@rip.zenteiq.ai"   # verified domain in Resend

SENTIMENT_EMOJI = {
    "loving_it": "\U0001F60A",
    "okay": "\U0001F610",
    "not_good": "\U0001F615",
    "surprised": "\U0001F62E",
    "useful": "\U0001F60A",
    "confused": "\U0001F615",
    "expected": "\U0001F610",
    "very_disappointed": "\U0001F614",
    "somewhat_disappointed": "\U0001F610",
    "not_disappointed": "\U0001F937",
    "thumbs_up": "\U0001F44D",
    "thumbs_down": "\U0001F44E",
}


async def send_feedback_email(
    moment_type: str,
    response_value: Optional[str],
    open_text: str,
    include_email: bool,
    user_id: str,
    ats_score: Optional[float],
    role_fit_band: Optional[str],
) -> None:
    """Send feedback email via Resend.

    This function MUST NEVER raise — email failure must not break the API response.
    """
    if not RESEND_API_KEY:
        logger.warning("[EMAIL] RESEND_API_KEY not set - skipping email")
        return

    emoji = SENTIMENT_EMOJI.get(response_value or "", "")
    subject = f"[RIP V2 Feedback] {emoji} {moment_type.replace('_', ' ').title()}"

    body_lines = [
        f"<b>Moment:</b> {moment_type}",
        f"<b>Sentiment:</b> {emoji} {response_value or '—'}",
        f"<b>ATS score:</b> {ats_score if ats_score is not None else '—'}",
        f"<b>Role fit band:</b> {role_fit_band or '—'}",
        f"<b>User ID:</b> {user_id[:8]}...",
        "",
        "<b>Feedback:</b>",
        f"<blockquote>{open_text}</blockquote>",
    ]

    reply_to: Optional[str] = None
    if include_email:
        try:
            from backend.db import get_db

            db = get_db()
            user_data = db.auth.admin.get_user_by_id(user_id)
            reply_to = user_data.user.email
            body_lines.append(f"<b>Reply-to:</b> {reply_to}")
        except Exception:
            pass  # Non-fatal

    html_body = "<br>".join(body_lines)

    payload: dict = {
        "from": FROM_ADDRESS,
        "to": [FEEDBACK_RECIPIENT],
        "subject": subject,
        "html": html_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=8.0,
            )
            resp.raise_for_status()
            logger.info("[EMAIL] Feedback email sent for moment=%s", moment_type)
    except Exception as e:
        logger.error("[EMAIL] Failed to send feedback email: %s", e)
        # Never raise — email failure must never break the API response
