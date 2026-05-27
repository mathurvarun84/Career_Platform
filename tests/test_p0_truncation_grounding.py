"""P0 fixes: A1 truncation repair and A4 tech grounding."""

from validator.resume_understanding_validator import (
    _entry_looks_truncated,
    _repair_truncated_sub_entries,
)
from validator.rewriter_validator import _strip_ungrounded_tech_lines


def test_entry_looks_truncated_by_length_ratio() -> None:
    short = "Built models using Python and SQL for fraud"
    long = (
        "Built models using Python and SQL for fraud detection across 50+ portfolios\n"
        "- Designed NLP pipeline to extract clauses from legal contracts\n"
        "- Deployed Flask APIs in Docker containers with CI/CD"
    )
    assert _entry_looks_truncated(short, long) is True
    assert _entry_looks_truncated(long, long) is False


def test_repair_truncated_sub_entries_replaces_short_verbatim() -> None:
    block = {
        "label": "Flipkart | EM",
        "text": (
            "Flipkart | EM\n"
            "Led team of 10 engineers\n"
            "- Shipped fraud model reducing losses by 23%\n"
            "- Built Kafka pipeline for real-time events"
        ),
    }
    entries = [{"label": "Flipkart | EM", "verbatim_text": "Led team of 10 engineers"}]
    repaired, anomalies = _repair_truncated_sub_entries(entries, [block], "experience")
    assert len(anomalies) == 1
    assert "Kafka" in repaired[0]["verbatim_text"]


def test_strip_ungrounded_tech_removes_invented_kafka_line() -> None:
    source = "Developed Python applications handling 10K+ daily transactions"
    rewrite = (
        "##COMPANY##Eval Co##ROLE##Engineer##END_HEADER##\n"
        "• Developed Python applications handling 10K+ daily transactions\n"
        "• Built Kafka-based event pipeline processing 500K msgs/day"
    )
    cleaned, stripped = _strip_ungrounded_tech_lines(rewrite, source)
    assert "Kafka" not in cleaned
    assert len(stripped) == 1
    assert "Python" in cleaned
