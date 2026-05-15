"""Upload limit enforcement for free tier."""

from fastapi import HTTPException

FREE_TIER_MONTHLY_LIMIT = 2


def check_upload_limit(db, user_id: str) -> None:
    """Check if user exceeded monthly limit. Raise 402 if over.

    Args:
        db: Supabase client
        user_id: Supabase user UUID

    Raises:
        HTTPException: 402 if limit reached
    """
    try:
        result = (
            db.table("usage_limits")
            .select("total_uploads, uploads_this_month")
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        if not result.data:
            return

        uploads_this_month = result.data.get("uploads_this_month", 0)
        limit = result.data.get("limit", FREE_TIER_MONTHLY_LIMIT)  # optional column

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
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.warning("check_upload_limit failed: %s", exc)


def reset_user_limit(db, user_id: str) -> dict:
    """Admin: reset user's monthly upload counter. For testing/support.

    Args:
        db: Supabase client
        user_id: Supabase user UUID

    Returns:
        Updated usage_limits row
    """
    result = db.table("usage_limits").update({
        "uploads_this_month": 0,
    }).eq("user_id", user_id).execute()

    if not result.data:
        raise ValueError(f"User {user_id} not found")

    return result.data[0]
