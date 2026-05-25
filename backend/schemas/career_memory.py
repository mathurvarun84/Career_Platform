"""Career memory schema and in-memory store for coaching answers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class CareerMemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    skill_category: Literal[
        "leadership", "technical", "delivery", "communication"
    ] = "technical"
    gap_reason: str

    company: str | None = None
    role: str | None = None
    section: str = "experience"

    coaching_question: str
    raw_answer: str
    generated_bullet: str
    grounding_check: bool = True
    user_approved: bool = False

    gap_id: str = ""
    sub_label: str | None = None


class CareerMemoryStore:
    """Simple in-memory store keyed by session_id. Replace with DB later."""

    def __init__(self) -> None:
        self._store: dict[str, list[CareerMemoryEntry]] = {}

    def add(self, entry: CareerMemoryEntry) -> CareerMemoryEntry:
        self._store.setdefault(entry.session_id, []).append(entry)
        return entry

    def get(self, session_id: str) -> list[CareerMemoryEntry]:
        return list(self._store.get(session_id, []))

    def approve(self, session_id: str, entry_id: str) -> bool:
        for entry in self._store.get(session_id, []):
            if entry.id == entry_id:
                entry.user_approved = True
                return True
        return False


career_memory_store = CareerMemoryStore()
