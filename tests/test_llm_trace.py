"""Tests for LLM trace helpers."""

import json

from engine.llm_trace import (
    PhaseTimer,
    build_trace_summary,
    log_trace_summary,
    record_llm_call,
    reset_trace,
    trace_output_dir,
)


def test_trace_summary_ranks_llm_calls(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_TRACE_FILE", "1")

    reset_trace("test-run")
    record_llm_call(
        agent="GapAnalyzerAgent",
        provider="openai",
        model="gpt-4o-mini",
        duration_ms=5000,
        prompt_chars=12000,
    )
    record_llm_call(
        agent="RewriterAgent",
        provider="anthropic",
        model="claude-haiku",
        duration_ms=12000,
        prompt_chars=8000,
        call_label="sub_entry:experience:Acme",
    )
    with PhaseTimer("sectioner_merge"):
        pass

    written = log_trace_summary()
    assert written is not None
    assert written.name == "test-run.json"
    assert (tmp_path / "test-run.txt").is_file()
    assert (tmp_path / "latest.json").is_file()
    assert (tmp_path / "latest.txt").is_file()

    summary = json.loads(written.read_text(encoding="utf-8"))
    assert summary["run_id"] == "test-run"
    assert summary["totals"]["llm_calls"] == 2
    assert summary["totals"]["total_llm_ms"] == 17000.0
    assert summary["slowest_llm"]["agent"] == "RewriterAgent"
    assert summary["llm_calls"][0]["rank"] == 1
    assert summary["llm_calls"][0]["duration_ms"] == 12000.0
    assert summary["llm_calls"][1]["agent"] == "GapAnalyzerAgent"
    assert summary["phases"][0]["name"] == "sectioner_merge"

    text = (tmp_path / "latest.txt").read_text(encoding="utf-8")
    assert "Slowest LLM: RewriterAgent" in text
    assert "#1 RewriterAgent" in text


def test_build_trace_summary_empty_run():
    reset_trace("empty-run")
    summary = build_trace_summary()
    assert summary["run_id"] == "empty-run"
    assert summary["totals"]["llm_calls"] == 0
    assert summary["slowest_llm"] is None


def test_trace_file_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_TRACE_FILE", "0")

    reset_trace("disabled-run")
    record_llm_call(
        agent="ResumeUnderstandingAgent",
        provider="openai",
        model="gpt-4o-mini",
        duration_ms=100,
        prompt_chars=500,
    )
    assert log_trace_summary() is None
    assert list(tmp_path.iterdir()) == []


def test_default_trace_dir_under_logs():
    assert trace_output_dir().name == "llm_traces"
    assert trace_output_dir().parent.name == "logs"
