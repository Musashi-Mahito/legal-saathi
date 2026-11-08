"""Tests for the job archive."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pytest

import config
import jobs
from app import create_app

SAMPLE_TEXT = (
    "RENTAL AGREEMENT\n\n"
    "This rental agreement is made on 1 January 2025 between Mr Rakesh Sharma (Landlord) "
    "and Ms Neha Verma (Tenant).\n"
    "The tenant has paid a security deposit of Rs. 60,000 to the landlord.\n"
)


@pytest.fixture
def client():
    """A Flask test client using the fake LLM provider."""
    with create_app(testing=True).test_client() as test_client:
        yield test_client


@pytest.fixture
def session_id(client) -> str:
    return client.post("/api/session").get_json()["session_id"]


def _job_dir(job: dict) -> Path:
    day = job["created_at"][:10]
    return config.JOBS_DIR / day / job["job_id"]


def test_job_folder_layout_uses_date_then_job_id():
    folder = jobs.job_folder(datetime(2026, 11, 8, 14, 30), "abc-123")
    assert folder.parent.name == "2026-11-08"
    assert folder.name == "abc-123"
    assert folder.parent.parent == config.JOBS_DIR


def test_chat_job_is_archived(client, session_id, job_files):
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "My landlord is not returning my deposit."},
    )
    assert response.status_code == 200

    archived = job_files()
    assert len(archived) == 1
    job = archived[0]
    assert job["kind"] == "chat"
    assert job["session_id"] == session_id
    assert job["llm"] and job["llm"][0]["provider"] == "fake"

    folder = _job_dir(job)
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    reply = json.loads((folder / "response.json").read_text(encoding="utf-8"))
    assert request["message"] == "My landlord is not returning my deposit."
    assert reply["reply"]
    assert reply["domain"] == "deposit"


def test_internal_llm_field_never_reaches_the_api(client, session_id, job_files):
    bodies = [
        client.post(
            "/api/chat", json={"session_id": session_id, "message": "Deposit not returned."}
        ).get_data(as_text=True)
    ]
    doc_id = client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(SAMPLE_TEXT.encode()), "rent.txt")},
        content_type="multipart/form-data",
    ).get_json()["doc_id"]
    bodies.append(
        client.post(
            "/api/summarize", json={"session_id": session_id, "doc_id": doc_id}
        ).get_data(as_text=True)
    )
    bodies.append(
        client.post("/api/timeline", json={"session_id": session_id}).get_data(as_text=True)
    )
    bodies.append(
        client.post("/api/notice", json={"session_id": session_id}).get_data(as_text=True)
    )
    for body in bodies:
        assert "_llm" not in body

    for job in job_files():
        reply = (_job_dir(job) / "response.json").read_text(encoding="utf-8")
        assert "_llm" not in reply


def test_upload_job_stores_extracted_text_but_not_bytes(client, session_id, job_files):
    client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(SAMPLE_TEXT.encode()), "rent.txt")},
        content_type="multipart/form-data",
    )
    job = job_files()[0]
    assert job["kind"] == "upload"
    folder = _job_dir(job)
    assert "security deposit of Rs. 60,000" in (folder / "document.txt").read_text(encoding="utf-8")
    names = {path.name for path in folder.iterdir()}
    assert names == {"request.json", "response.json", "meta.json", "document.txt"}


def test_summary_timeline_and_notice_each_get_a_job(client, session_id, job_files):
    client.post(
        "/api/chat", json={"session_id": session_id, "message": "My landlord keeps my 60000 deposit."}
    )
    doc_id = client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(SAMPLE_TEXT.encode()), "rent.txt")},
        content_type="multipart/form-data",
    ).get_json()["doc_id"]

    client.post("/api/summarize", json={"session_id": session_id, "doc_id": doc_id})
    client.post("/api/timeline", json={"session_id": session_id})
    client.post("/api/notice", json={"session_id": session_id})

    kinds = [job["kind"] for job in job_files()]
    assert sorted(kinds) == ["chat", "notice", "summary", "timeline", "upload"]


def test_failed_requests_are_not_archived(client, session_id, job_files):
    response = client.post("/api/chat", json={"session_id": session_id})
    assert response.status_code == 400
    assert job_files() == []


def test_archive_can_be_disabled(client, session_id, job_files, monkeypatch):
    monkeypatch.setattr(config, "JOBS_ENABLED", False)
    client.post("/api/chat", json={"session_id": session_id, "message": "Hello"})
    assert job_files() == []


def test_disk_failure_does_not_break_the_request(client, session_id, monkeypatch):
    def boom(self, parents=False, exist_ok=False):
        raise OSError("no space left on device")

    monkeypatch.setattr(Path, "mkdir", boom)
    response = client.post(
        "/api/chat", json={"session_id": session_id, "message": "My landlord is silent."}
    )
    assert response.status_code == 200
    assert response.get_json()["reply"]


def test_unknown_kind_is_ignored():
    assert jobs.record("not_a_kind", "s1", {}, {}) is None


def test_record_returns_job_id_and_writes_meta(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "JOBS_DIR", tmp_path / "jobs")
    job_id = jobs.record(
        "chat",
        "session-1",
        {"message": "hi"},
        {"reply": "hello"},
        llm_meta=[{"provider": "fake", "model": "fake-1"}],
    )
    assert job_id
    meta = json.loads(
        (tmp_path / "jobs" / datetime.now().strftime("%Y-%m-%d") / job_id / "meta.json").read_text(
            encoding="utf-8"
        )
    )
    assert meta["job_id"] == job_id
    assert meta["llm"][0]["provider"] == "fake"


def test_list_jobs_can_filter_by_day(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "JOBS_DIR", tmp_path / "jobs")
    jobs.record("chat", "s1", {}, {}, now=datetime(2026, 11, 8, 10, 0))
    jobs.record("chat", "s2", {}, {}, now=datetime(2026, 11, 9, 10, 0))
    assert len(jobs.list_jobs()) == 2
    assert len(jobs.list_jobs("2026-11-08")) == 1
    assert jobs.list_jobs()[0]["session_id"] == "s2"
