"""Unit tests for deterministic question bank retrieval."""

import unittest

from backend.utils.question_bank_retriever import retrieve_templates
from backend.utils.question_ledger import (
    ALL_DIMENSIONS,
    get_available_dimensions,
    get_excluded_dimensions,
    get_ledger,
    resume_fingerprint,
    update_ledger,
)


class QuestionBankRetrieverTests(unittest.TestCase):
    def test_retrieves_company_specific_first(self) -> None:
        result = retrieve_templates(
            target_dimensions=["ownership"],
            company="amazon",
            question_type_needed="behavioral",
            candidates_per_slot=2,
            seed=42,
        )
        self.assertIn("ownership", result)
        self.assertGreaterEqual(len(result["ownership"]), 1)
        self.assertEqual(result["ownership"][0].get("question_type"), "behavioral")

    def test_scenario_uses_scenario_pool(self) -> None:
        result = retrieve_templates(
            target_dimensions=["problem_solving"],
            company="unknown_co",
            type_by_dimension={"problem_solving": "scenario"},
            candidates_per_slot=2,
            seed=7,
        )
        self.assertIn("problem_solving", result)
        for template in result["problem_solving"]:
            self.assertEqual(template.get("question_type"), "scenario")

    def test_deterministic_with_seed(self) -> None:
        dims = ["ownership", "collaboration", "problem_solving"]
        a = retrieve_templates(dims, "amazon", seed=99)
        b = retrieve_templates(dims, "amazon", seed=99)
        self.assertEqual(
            [t["question"] for t in a["ownership"]],
            [t["question"] for t in b["ownership"]],
        )


class QuestionLedgerWrapperTests(unittest.TestCase):
    def test_available_resets_after_full_cycle(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from memory import session_store

        with tempfile.TemporaryDirectory() as tmp:
            users_dir = Path(tmp) / "users"
            users_dir.mkdir()
            with patch.object(session_store, "USERS_DIR", users_dir):
                user_id = "wrapper-user"
                fp = resume_fingerprint("test resume body")
                for dim in ALL_DIMENSIONS[:5]:
                    update_ledger(
                        user_id,
                        fp,
                        [{"id": f"q-{dim}", "dimension": dim, "why_this_question": dim}],
                    )
                available = get_available_dimensions(user_id, fp)
                self.assertEqual(len(available), 7)
                self.assertEqual(get_excluded_dimensions(user_id, fp), [])


if __name__ == "__main__":
    unittest.main()
