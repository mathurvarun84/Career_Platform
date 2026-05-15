"""Supabase client singleton for backend persistence."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

_client = None


def get_db():
    """Singleton Supabase client using service_role_key."""
    global _client
    if _client is None:
        url = (os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required in .env"
            )
        _client = create_client(url, key)
    return _client
