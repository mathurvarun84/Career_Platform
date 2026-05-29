"""
Deterministic retrieval from question_bank.json.

No embeddings, no vector DB. Filter → shuffle → pick.

Two-tier logic:
  1. Company-specific questions for the target company (if available)
  2. Generic questions as fallback / supplement

Returns up to ``candidates_per_slot`` templates per dimension so the LLM
has structural variety when personalizing.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

_BANK: dict | None = None
_BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "question_bank.json"


def _load() -> dict:
    global _BANK
    if _BANK is None:
        with open(_BANK_PATH, encoding="utf-8") as f:
            _BANK = json.load(f)
    return _BANK


def _generic_pool(generic: dict, dim: str, question_type: str) -> list[dict]:
    """Return generic templates for a dimension, preferring scenario keys when needed."""
    if question_type == "scenario":
        scenario_key = f"scenario_{dim}"
        pool = list(generic.get(scenario_key, []))
        if pool:
            return pool
    return list(generic.get(dim, []))


def retrieve_templates(
    target_dimensions: list[str],
    company: str,
    question_type_needed: str = "any",
    type_by_dimension: dict[str, str] | None = None,
    candidates_per_slot: int = 2,
    seed: Optional[int] = None,
) -> dict[str, list[dict]]:
    """
    Return ``{ dimension: [template, ...] }`` for each requested dimension.

    Precedence: company_specific first, generic as fallback.
    If company_specific has only one template, supplements with generic.
    """
    bank = _load()
    rng = random.Random(seed)

    generic = bank.get("generic", {})
    company_specific = bank.get("company_specific", {}).get(company.lower(), {})

    result: dict[str, list[dict]] = {}

    for dim in target_dimensions:
        slot_type = (type_by_dimension or {}).get(dim, question_type_needed)

        cs_questions = list(company_specific.get(dim, []))
        generic_questions = _generic_pool(generic, dim, slot_type)

        if slot_type != "any":
            cs_questions = [
                q for q in cs_questions if q.get("question_type") == slot_type
            ]
            generic_questions = [
                q for q in generic_questions if q.get("question_type") == slot_type
            ]

        pool = cs_questions + generic_questions
        if not pool:
            continue

        rng.shuffle(pool)
        result[dim] = pool[:candidates_per_slot]

    return result
