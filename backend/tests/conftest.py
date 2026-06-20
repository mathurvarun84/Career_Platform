"""Pytest hooks shared across backend/tests.

test_jd_fetch_endpoint.py registers a stub `engine` module at import time for FastAPI
isolation. Restore the repo-root engine package after collection so readiness and other
engine-dependent tests see the real package.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _restore_repo_engine() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    eng = sys.modules.get("engine")
    if eng is not None and not hasattr(eng, "__path__"):
        for key in list(sys.modules):
            if key == "engine" or key.startswith("engine."):
                del sys.modules[key]


def pytest_collection_finish(session) -> None:
    _restore_repo_engine()
