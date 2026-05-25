"""Tests for stage cache TTL helpers in backend.main."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from backend import main as main_module


@pytest.fixture
def sample_stage_data() -> dict:
    return {
        "resume_und": {"experience_years": 5},
        "jd_intel": {"role_title": "Engineer"},
        "resume_sections": {},
    }


def test_get_returns_none_when_ttl_disabled(sample_stage_data) -> None:
    cache = {"k": {"cached_at": time.time(), "data": sample_stage_data}}
    with patch.object(main_module, "_stage_cache_ttl_seconds", return_value=0):
        assert main_module._get_stage_cache_entry(cache, "k") is None


def test_get_returns_data_when_fresh(sample_stage_data) -> None:
    cache = {"k": {"cached_at": time.time(), "data": sample_stage_data}}
    with patch.object(main_module, "_stage_cache_ttl_seconds", return_value=3600):
        got = main_module._get_stage_cache_entry(cache, "k")
    assert got == sample_stage_data


def test_get_returns_none_when_expired(sample_stage_data) -> None:
    cache = {
        "k": {
            "cached_at": time.time() - 7200,
            "data": sample_stage_data,
        }
    }
    with patch.object(main_module, "_stage_cache_ttl_seconds", return_value=3600):
        assert main_module._get_stage_cache_entry(cache, "k") is None


def test_legacy_unwrapped_entry_is_miss(sample_stage_data) -> None:
    cache = {"k": sample_stage_data}
    with patch.object(main_module, "_stage_cache_ttl_seconds", return_value=3600):
        assert main_module._get_stage_cache_entry(cache, "k") is None


def test_merge_stage_cache_preserves_existing_keys(sample_stage_data) -> None:
    cache: dict = {}
    with patch.object(main_module, "_stage_cache_ttl_seconds", return_value=3600):
        main_module._set_stage_cache_entry(cache, "k", sample_stage_data)
        main_module._merge_stage_cache_entry(
            cache,
            "k",
            {"recruiter_sim": {"personas": [{"persona": "Test"}]}},
        )
        got = main_module._get_stage_cache_entry(cache, "k")
    assert got is not None
    assert got["resume_und"] == sample_stage_data["resume_und"]
    assert got["recruiter_sim"]["personas"][0]["persona"] == "Test"


def test_prune_drops_expired_and_legacy(sample_stage_data) -> None:
    now = time.time()
    cache = {
        "fresh": {"cached_at": now, "data": sample_stage_data},
        "stale": {"cached_at": now - 99999, "data": sample_stage_data},
        "legacy": sample_stage_data,
    }
    pruned = main_module._prune_expired_stage_cache(cache, 3600)
    assert "fresh" in pruned
    assert "stale" not in pruned
    assert "legacy" not in pruned
