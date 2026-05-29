"""
Memory layer – per‑user JSON store.

Stores session history, tracks runs, and keeps a running style decision log.
Supports flexible agent output storage keyed by run_id + agent_name.

All I/O is protected by try/except with descriptive error messages.
"""

import json
import os
import pathlib
import datetime
import hashlib
import logging
import uuid

# Directory for per‑user JSON files – ensure existence lazily
BASE_DIR = pathlib.Path("resume_platform/memory")
USERS_DIR = BASE_DIR / "users"

logger = logging.getLogger(__name__)

MAX_LEDGER_SIGNALS = 50
MAX_RESUME_FINGERPRINTS = 20

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
        "agent_data": {},  # Keyed by run_id.agent_name → stores individual agent outputs
        "resume_fingerprints": {},  # resume_fp → question ledger for mock interviews
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
    # Add agent_data if missing (backward compatibility)
    if "agent_data" not in data:
        data["agent_data"] = {}
    if "resume_fingerprints" not in data:
        data["resume_fingerprints"] = {}
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

# -------------------------------------------------------------------------------------------------
# Agent Data Storage – flexible per-run agent output storage
# -------------------------------------------------------------------------------------------------

def generate_run_id() -> str:
    """Generate a unique run ID."""
    return str(uuid.uuid4())[:8]

def save_agent_output(user_id: str, run_id: str, agent_name: str, data: dict) -> None:
    """Save an individual agent's output for a given run.

    Args:
        user_id: User identifier.
        run_id: Run identifier (can be generated via generate_run_id).
        agent_name: Agent identifier (e.g., 'resume_understanding', 'gap_analyzer').
        data: Agent output dict to store.
    """
    session = load_session(user_id)
    key = f"{run_id}.{agent_name}"
    try:
        session["agent_data"][key] = data
        save_session(user_id, session)
    except Exception as e:
        logger.error("Failed to save agent output %s: %s", key, e)
        raise

def get_agent_output(user_id: str, run_id: str, agent_name: str) -> dict | None:
    """Retrieve a saved agent output.

    Args:
        user_id: User identifier.
        run_id: Run identifier.
        agent_name: Agent identifier.

    Returns:
        Agent output dict, or None if not found.
    """
    session = load_session(user_id)
    key = f"{run_id}.{agent_name}"
    return session.get("agent_data", {}).get(key)

def save_full_run_result(user_id: str, run_id: str, full_result: dict) -> None:
    """Save the complete orchestrator output for a run.

    Args:
        user_id: User identifier.
        run_id: Run identifier.
        full_result: Full dict returned by orchestrator.run_full_evaluation().
    """
    session = load_session(user_id)
    key = f"{run_id}.full_result"
    try:
        session["agent_data"][key] = full_result
        save_session(user_id, session)
    except Exception as e:
        logger.error("Failed to save full run result %s: %s", key, e)
        raise

def get_full_run_result(user_id: str, run_id: str) -> dict | None:
    """Retrieve the complete orchestrator output for a run.

    Args:
        user_id: User identifier.
        run_id: Run identifier.

    Returns:
        Full result dict, or None if not found.
    """
    session = load_session(user_id)
    key = f"{run_id}.full_result"
    return session.get("agent_data", {}).get(key)


# -------------------------------------------------------------------------------------------------
# Mock interview question ledger — per resume fingerprint
# -------------------------------------------------------------------------------------------------

def compute_resume_fingerprint(resume_text: str) -> str:
    """Deterministic sha256 of the first 500 normalized chars of resume text."""
    prefix = (resume_text or "")[:500].strip().lower()
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()


def _empty_ledger_entry() -> dict:
    return {
        "asked_dimensions": [],
        "asked_signals": [],
        "asked_question_ids": [],
        "last_session_at": None,
    }


def load_question_ledger(user_id: str, resume_fingerprint: str) -> dict:
    """Return prior asked dimensions/signals for this user + resume fingerprint."""
    session = load_session(user_id)
    fp_data = session.get("resume_fingerprints", {}).get(resume_fingerprint, {})
    return {
        "asked_dimensions": list(fp_data.get("asked_dimensions") or []),
        "asked_signals": list(fp_data.get("asked_signals") or []),
        "asked_question_ids": list(fp_data.get("asked_question_ids") or []),
        "last_session_at": fp_data.get("last_session_at"),
    }


def extract_signal_phrase(why_this_question: str) -> str:
    """Pull a short resume-signal phrase from why_this_question for dedup."""
    text = (why_this_question or "").strip()
    if not text:
        return ""
    for sep in (".", ";", "—", " - ", " because ", " since "):
        idx = text.lower().find(sep)
        if idx > 0:
            text = text[:idx].strip()
            break
    return text[:120]


def update_question_ledger(
    user_id: str,
    resume_fingerprint: str,
    completed_questions: list[dict],
) -> None:
    """Append dimensions/signals from a completed mock interview session."""
    if not resume_fingerprint or not completed_questions:
        return

    session = load_session(user_id)
    fingerprints = session.setdefault("resume_fingerprints", {})
    ledger = fingerprints.setdefault(resume_fingerprint, _empty_ledger_entry())

    asked_dims = list(ledger.get("asked_dimensions") or [])
    asked_signals = list(ledger.get("asked_signals") or [])
    asked_ids = list(ledger.get("asked_question_ids") or [])

    dim_set = {d.lower() for d in asked_dims}
    signal_set = {s.lower() for s in asked_signals}
    id_set = set(asked_ids)

    for q in completed_questions:
        dim = (q.get("dimension") or "").strip()
        if dim and dim.lower() not in dim_set:
            asked_dims.append(dim)
            dim_set.add(dim.lower())

        signal = extract_signal_phrase(q.get("why_this_question", ""))
        if signal and signal.lower() not in signal_set:
            asked_signals.append(signal)
            signal_set.add(signal.lower())

        qid = q.get("id")
        if qid and qid not in id_set:
            asked_ids.append(qid)
            id_set.add(qid)

    ledger["asked_dimensions"] = asked_dims
    ledger["asked_signals"] = asked_signals[-MAX_LEDGER_SIGNALS:]
    ledger["asked_question_ids"] = asked_ids
    ledger["last_session_at"] = datetime.datetime.utcnow().isoformat()
    fingerprints[resume_fingerprint] = ledger

    if len(fingerprints) > MAX_RESUME_FINGERPRINTS:
        ranked = sorted(
            fingerprints.items(),
            key=lambda item: item[1].get("last_session_at") or "",
            reverse=True,
        )
        session["resume_fingerprints"] = dict(ranked[:MAX_RESUME_FINGERPRINTS])

    try:
        save_session(user_id, session)
    except Exception as exc:
        logger.warning("update_question_ledger failed for %s: %s", user_id, exc)
