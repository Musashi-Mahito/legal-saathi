"""Shared pytest fixtures: offline fake LLM and a clean session store."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["LLM_PROVIDER_ORDER"] = "fake"

import pytest  # noqa: E402

import config  # noqa: E402
import jobs  # noqa: E402
import llm  # noqa: E402
import kb  # noqa: E402
import store  # noqa: E402


@pytest.fixture(autouse=True)
def clean_sessions(tmp_path, monkeypatch):
    """Give every test an empty session store, no fake override, a temp jobs dir."""
    monkeypatch.setattr(config, "JOBS_DIR", tmp_path / "jobs")
    store.clear_all()
    llm.set_fake_responder(None)
    kb.reset()
    yield
    store.clear_all()
    llm.set_fake_responder(None)
    kb.reset()


@pytest.fixture
def job_files():
    """Read back the archived job folders written during a test."""

    def _read() -> list[dict]:
        return jobs.list_jobs()

    return _read


@pytest.fixture
def fake_llm():
    """Install a custom fake responder for the duration of a test."""

    def _install(payloads: dict | callable):
        if callable(payloads):
            llm.set_fake_responder(payloads)
        else:
            llm.set_fake_responder(lambda messages, json_mode: payloads)
        return payloads

    return _install
