"""API tests: every endpoint, including error paths."""

from __future__ import annotations

import io
import json

import pytest

import config
from app import create_app

SAMPLE_TEXT = (
    "RENTAL AGREEMENT\n\n"
    "This rental agreement is made on 1 January 2025 between Mr Rakesh Sharma (Landlord) "
    "and Ms Neha Verma (Tenant).\n"
    "The tenant has paid a security deposit of Rs. 60,000 to the landlord.\n"
    "Any dispute arising out of this agreement shall be referred to a sole arbitrator "
    "appointed by the Landlord.\n"
    "The landlord shall refund the security deposit within 15 days of the tenant vacating "
    "the premises.\n"
)


@pytest.fixture
def client():
    """A Flask test client using the fake LLM provider."""
    app = create_app(testing=True)
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def session_id(client) -> str:
    response = client.post("/api/session")
    assert response.status_code == 201
    return response.get_json()["session_id"]


def _error(response) -> dict:
    payload = response.get_json()
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message"}
    return payload["error"]


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert isinstance(payload["providers"], list)
    assert "models" in payload


def test_create_session(session_id):
    assert len(session_id) == 36


def test_chat_success(client, session_id):
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "My landlord is not returning my deposit."},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["domain"] == "deposit"
    assert payload["reply"]
    assert payload["case_file"]["session_id"] == session_id
    assert isinstance(payload["flags"], list)
    assert "Traceback" not in response.get_data(as_text=True)


def test_chat_missing_message(client, session_id):
    response = client.post("/api/chat", json={"session_id": session_id})
    assert response.status_code == 400
    assert _error(response)["code"] == "bad_request"


def test_chat_message_too_long(client, session_id):
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "x" * (config.MAX_MESSAGE_CHARS + 1)},
    )
    assert response.status_code == 400
    assert _error(response)["code"] == "bad_request"


def test_chat_unknown_session(client):
    response = client.post(
        "/api/chat",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "message": "hello"},
    )
    assert response.status_code == 404
    assert _error(response)["code"] == "not_found"


def test_chat_invalid_session_id(client):
    response = client.post("/api/chat", json={"session_id": "not-a-uuid", "message": "hello"})
    assert response.status_code == 400
    assert _error(response)["code"] == "bad_request"


def test_upload_and_summary(client, session_id):
    response = client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(SAMPLE_TEXT.encode()), "rent.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    upload = response.get_json()
    assert upload["filename"] == "rent.txt"
    assert upload["chars"] > 100
    assert upload["truncated"] is False

    summary = client.post(
        "/api/summarize", json={"session_id": session_id, "doc_id": upload["doc_id"]}
    )
    assert summary.status_code == 200
    payload = summary.get_json()
    assert payload["summary"]["doc_type"] == "rental_agreement"
    assert payload["summary"]["arbitration_clause"]["found"] is True


def test_upload_without_file(client, session_id):
    response = client.post(
        "/api/upload",
        data={"session_id": session_id},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert _error(response)["code"] == "bad_request"


def test_upload_wrong_type(client, session_id):
    response = client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(b"\xff\xd8\xff"), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 415
    assert _error(response)["code"] == "unsupported_type"


def test_upload_empty_file(client, session_id):
    response = client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(b""), "empty.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert _error(response)["code"] == "empty_document"


def test_upload_too_large(client, session_id, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/upload",
        data={"session_id": session_id, "file": (io.BytesIO(b"a" * 50), "big.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413
    assert _error(response)["code"] == "file_too_large"


def test_summarize_unknown_document(client, session_id):
    response = client.post("/api/summarize", json={"session_id": session_id, "doc_id": "nope"})
    assert response.status_code == 404
    assert _error(response)["code"] == "not_found"


def test_summarize_missing_doc_id(client, session_id):
    response = client.post("/api/summarize", json={"session_id": session_id})
    assert response.status_code == 400
    assert _error(response)["code"] == "bad_request"


def test_timeline_from_chat(client, session_id):
    client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "My landlord is not returning my deposit. I vacated on 30 November 2025.",
        },
    )
    response = client.post("/api/timeline", json={"session_id": session_id})
    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {"events", "undated", "dropped_unverified", "flags"}


def test_notice_requires_known_domain(client, session_id):
    response = client.post("/api/notice", json={"session_id": session_id})
    assert response.status_code == 422
    assert _error(response)["code"] == "bad_request"


def test_notice_after_chat(client, session_id):
    client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "My landlord keeps my 60000 deposit."},
    )
    response = client.post("/api/notice", json={"session_id": session_id})
    assert response.status_code == 200
    payload = response.get_json()
    assert "DRAFT" in payload["notice_markdown"]
    assert payload["missing_placeholders"]


def test_case_file_endpoint(client, session_id):
    response = client.get(f"/api/case/{session_id}")
    assert response.status_code == 200
    assert response.get_json()["session_id"] == session_id

    missing = client.get("/api/case/11111111-1111-1111-1111-111111111111")
    assert missing.status_code == 404
    assert _error(missing)["code"] == "not_found"


def test_kb_endpoint(client):
    response = client.get("/api/kb")
    assert response.status_code == 200
    entries = response.get_json()
    assert entries
    assert set(entries[0]) == {"id", "title", "verified"}


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Legal Saathi" in response.data
    assert b"/static/app.js" in response.data
    assert b"/static/style.css" in response.data


def test_static_assets_are_served(client):
    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert b"use strict" in script.data
    styles = client.get("/static/style.css")
    assert styles.status_code == 200
    assert b"--accent" in styles.data


def test_unknown_route_returns_json_error(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert _error(response)["code"] == "not_found"


def test_method_not_allowed(client):
    response = client.get("/api/chat")
    assert response.status_code == 405
    assert _error(response)["code"] == "bad_request"


def test_invalid_json_body(client):
    response = client.post("/api/chat", data="not json", content_type="application/json")
    assert response.status_code == 400
    assert _error(response)["code"] == "bad_request"
