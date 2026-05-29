"""Unit tests for mock-interview question ledger in session_store."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import session_store


class QuestionLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._users_dir = Path(self._tmpdir.name) / "users"
        self._users_dir.mkdir(parents=True)
        patcher = patch.object(session_store, "USERS_DIR", self._users_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmpdir.cleanup)

    def test_fingerprint_is_deterministic(self) -> None:
        text = "Software Engineer at Flipkart\nAI adoption lead"
        fp1 = session_store.compute_resume_fingerprint(text)
        fp2 = session_store.compute_resume_fingerprint(text)
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)

    def test_fingerprint_normalizes_case_and_prefix(self) -> None:
        long_text = "A" * 600
        fp_full = session_store.compute_resume_fingerprint(long_text)
        fp_prefix = session_store.compute_resume_fingerprint("a" * 500)
        self.assertEqual(fp_full, fp_prefix)

    def test_update_and_load_ledger(self) -> None:
        user_id = "user-ledger-test"
        resume_fp = session_store.compute_resume_fingerprint("Flipkart AI rollout resume")

        session_store.update_question_ledger(
            user_id,
            resume_fp,
            [
                {
                    "id": "q1",
                    "dimension": "ownership",
                    "why_this_question": "AI-assisted adoption at Flipkart. Tests ownership.",
                },
                {
                    "id": "q2",
                    "dimension": "collaboration",
                    "why_this_question": "Cross-team Copilot rollout with platform team",
                },
            ],
        )

        ledger = session_store.load_question_ledger(user_id, resume_fp)
        self.assertEqual(ledger["asked_dimensions"], ["ownership", "collaboration"])
        self.assertIn("AI-assisted adoption at Flipkart", ledger["asked_signals"])
        self.assertEqual(ledger["asked_question_ids"], ["q1", "q2"])
        self.assertIsNotNone(ledger["last_session_at"])

    def test_ledger_dedupes_repeat_updates(self) -> None:
        user_id = "user-dedupe"
        resume_fp = session_store.compute_resume_fingerprint("same resume")
        question = {
            "id": "q1",
            "dimension": "ownership",
            "why_this_question": "Flipkart AI story",
        }

        session_store.update_question_ledger(user_id, resume_fp, [question])
        session_store.update_question_ledger(user_id, resume_fp, [question])

        ledger = session_store.load_question_ledger(user_id, resume_fp)
        self.assertEqual(ledger["asked_dimensions"], ["ownership"])
        self.assertEqual(len(ledger["asked_signals"]), 1)

    def test_exclusion_block_formats_constraints(self) -> None:
        from backend.agents.interview_agent import InterviewAgent

        block = InterviewAgent._build_exclusion_block(
            {
                "asked_dimensions": ["ownership"],
                "asked_signals": ["AI adoption at Flipkart"],
            }
        )
        self.assertIn("HARD CONSTRAINTS", block)
        self.assertIn("ownership", block)
        self.assertIn("AI adoption at Flipkart", block)


if __name__ == "__main__":
    unittest.main()
