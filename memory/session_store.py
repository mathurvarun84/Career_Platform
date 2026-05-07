"""
Memory layer – per‑user JSON store.

Stores session history, tracks runs, and keeps a running style decision log.

All I/O is protected by try/except with descriptive error messages.
"""

import json
import os
import pathlib
import datetime
import logging

# Directory for per‑user JSON files – ensure existence lazily
BASE_DIR = pathlib.Path("resume_platform/memory")
USERS_DIR = BASE_DIR / "users"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: ensure file system structure exists
# ---------------------------------------------------------------------------

def _ensure_users_dir() -> None:
    try:
        USERS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("Failed to create memory users directory: %s", e)
        raise

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _scaffold(user_id: str) -> dict:
    """Return a fresh session scaffold for the given user_id."""
    now = datetime.datetime.utcnow().isoformat()
    return {
        "user_id": user_id,
        "created_at": now,
        "runs": [],
        "style_decisions": {"accepted": [], "rejected": []},
    }

# -------------------------------------------------------------------------------------------------
# Load
# -------------------------------------------------------------------------------------------------

def load_session(user_id: str) -> dict:
    """Load the JSON session file for *user_id*.

    Returns an empty scaffold if the file is missing.
    """
    _ensure_users_dir()
    path = USERS_DIR / f"{user_id}.json"
    if not path.exists():
        return _scaffold(user_id)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Error reading session file %s: %s", path, e)
        return _scaffold(user_id)

    # Basic sanity: ensure keys exist
    for key in ["user_id", "created_at", "runs", "style_decisions"]:
        if key not in data:
            logger.warning("Missing key '%s' in session, resetting", key)
            return _scaffold(user_id)
    return data

# -------------------------------------------------------------------------------------------------
# Save – overwrite entire file
# -------------------------------------------------------------------------------------------------

def save_session(user_id: str, session_data: dict) -> None:
    """Persist *session_data* for *user_id*.

    Args:
        user_id: Identifier for the user.
        session_data: Full session dict to write – must already be JSON‑serialisable.
    """
    _ensure_users_dir()
    path = USERS_DIR / f"{user_id}.json"
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, sort_keys=True)
    except Exception as e:
        logger.error("Failed to write session file %s: %s", path, e)
        raise

# -------------------------------------------------------------------------------------------------
# Update – append a new run
# -------------------------------------------------------------------------------------------------

def update_session(user_id: str, run_result: dict) -> None:
    """Append *run_result* to the user's session history.

    Maintains a maximum of 50 runs – oldest runs are dropped.

    Expected keys in run_result: timestamp, ats_score, match_score,
    accepted_sections, rejected_sections.
    """
    session = load_session(user_id)

    # Validate required keys – minimal sanity check
    required = {
        "timestamp",
        "ats_score",
        "match_score",
        "accepted_sections",
        "rejected_sections",
    }
    missing = required - run_result.keys()
    if missing:
        raise ValueError(f"update_session: missing keys {missing}")

    session["runs"].append(run_result)
    # Keep only the most recent 50
    if len(session["runs"]) > 50:
        session["runs"] = session["runs"][-50:]

    save_session(user_id, session)
