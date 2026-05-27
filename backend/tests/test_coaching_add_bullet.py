"""Tests for coaching add-bullet: found_in_doc truth and fuzzy sub_label insert."""

from __future__ import annotations

from backend.api.routes import coaching as coaching_routes
from backend.api.routes.coaching import AddBulletRequest, add_bullet
from backend.schemas.career_memory import CareerMemoryEntry, career_memory_store


def _make_job() -> dict:
    flipkart_verbatim = (
        "Flipkart — Engineering Manager\n"
        "Bengaluru\n"
        "• Led team of 10 engineers"
    )
    infosys_verbatim = (
        "Infosys — Senior Engineer\n"
        "• Built internal tools"
    )
    experience_full = f"{flipkart_verbatim}\n\n{infosys_verbatim}"
    return {
        "resume_text": experience_full,
        "resume_text_patched": experience_full,
        "result": {
            "resume": {
                "resume_sections": {
                    "experience": {
                        "full_text": experience_full,
                        "sub_entries": [
                            {
                                "label": "Flipkart — Engineering Manager",
                                "verbatim_text": flipkart_verbatim,
                            },
                            {
                                "label": "Infosys — Senior Engineer",
                                "verbatim_text": infosys_verbatim,
                            },
                        ],
                    }
                }
            }
        },
        "coaching_answers": {},
    }


def _configure_store(job: dict, session_id: str) -> None:
    jobs = {session_id: job}

    def require_job(sid: str) -> dict:
        return jobs[sid]

    coaching_routes.configure_coaching_routes(require_job, lambda _sid: None)


def test_found_in_doc_false_when_approved_but_not_inserted() -> None:
    session_id = "sess-approve-only"
    memory_id = "mem-1"
    job = _make_job()
    _configure_store(job, session_id)

    career_memory_store.add(
        CareerMemoryEntry(
            id=memory_id,
            session_id=session_id,
            gap_reason="leadership",
            coaching_question="Describe team leadership",
            raw_answer="I mentored five engineers weekly",
            generated_bullet="Mentored 5 engineers through weekly 1:1s",
            section="experience",
            sub_label="Amazon — VP",
            gap_id="gap-1",
        )
    )

    resp = add_bullet(
        AddBulletRequest(
            session_id=session_id,
            career_memory_id=memory_id,
            section="experience",
            sub_label="Amazon — VP",
            bullet_text="Mentored 5 engineers through weekly 1:1s",
        )
    )

    assert resp.success is True
    assert resp.inserted is False
    assert resp.found_in_doc is False
    assert "Mentored 5 engineers" not in job["resume_text_patched"]


def test_fuzzy_sub_label_inserts_into_correct_entry_not_file_end() -> None:
    session_id = "sess-fuzzy"
    job = _make_job()
    _configure_store(job, session_id)
    bullet = "Scaled Kafka pipeline to 2M events/day"

    resp = add_bullet(
        AddBulletRequest(
            session_id=session_id,
            career_memory_id="unused",
            section="experience",
            sub_label="Flipkart Engineering Manager",
            bullet_text=bullet,
            placement="end",
        )
    )

    assert resp.inserted is True
    assert resp.found_in_doc is True

    patched = job["resume_text_patched"]
    assert bullet in patched
    assert patched.rstrip().endswith(bullet) is False

    flipkart = job["result"]["resume"]["resume_sections"]["experience"]["sub_entries"][0]
    assert bullet in flipkart["verbatim_text"]
    assert "Infosys" in job["result"]["resume"]["resume_sections"]["experience"]["sub_entries"][1]["verbatim_text"]
    assert bullet not in job["result"]["resume"]["resume_sections"]["experience"]["sub_entries"][1]["verbatim_text"]
