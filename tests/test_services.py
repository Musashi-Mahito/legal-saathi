"""Service-layer tests: everything runs against the fake LLM."""

from __future__ import annotations

import pytest

import config
import llm
import store
from services import chat_service, common, notice_service, summary_service, timeline_service
from store import Document

RENTAL_TEXT = """RENTAL AGREEMENT

This rental agreement is made on 1 January 2025 between Mr Rakesh Sharma (Landlord) and Ms Neha Verma (Tenant) for the flat at 12 Rose Villa, Pune.
The tenancy is for a period of eleven months commencing from 1 January 2025 and ending on 30 November 2025.
The tenant shall pay a monthly rent of Rs. 20,000. The tenant has paid a security deposit of Rs. 60,000 to the landlord.
The landlord may deduct the cost of painting, not exceeding Rs. 5,000, from the security deposit.
Any dispute arising out of this agreement shall be referred to a sole arbitrator appointed by the Landlord. The decision of the arbitrator shall be final.
The landlord shall refund the security deposit within 15 days of the tenant vacating the premises.
"""


def _session_with_doc(text: str = RENTAL_TEXT):
    """Create a session holding one short document."""
    session = store.create_session()
    document = Document(
        doc_id="doc-1",
        filename="rent_agreement.txt",
        text=text,
        chunks=[text],
        pages=None,
        truncated=False,
    )
    session.documents[document.doc_id] = document
    session.case_file["doc_ids"].append(document.doc_id)
    return session, document


def _task_responder(payloads: dict):
    """Return a fake responder that answers by task hint."""

    def responder(messages, json_mode):
        return payloads[llm.task_hint(messages)]

    return responder


def test_chat_merges_facts_and_ignores_unknown_keys():
    session = store.create_session()
    result = chat_service.handle_chat(session, "My landlord is not returning my deposit of 60000.")
    facts = result["case_file"]["facts"]
    assert result["domain"] == "deposit"
    assert facts["common"]["amount_inr"] == 60000
    assert facts["deposit"]["deposit_paid_inr"] == 60000
    assert facts["deposit"]["move_out_date"] == "2025-11-30"
    assert facts["deposit"]["written_agreement"] is True
    assert "unknown_key_that_must_be_ignored" not in facts["deposit"]
    assert result["escalation"]["level"] == "none"
    assert session.history[-1]["role"] == "assistant"


def test_chat_removes_unlisted_section_number(fake_llm):
    payload = {
        "reply": "You should cite Section 420 IPC and the case of Sharma v. Verma. Keep your receipts.",
        "domain": "deposit",
        "language": "en",
        "case_updates": {"facts": {"common": {}, "deposit": {}, "refund": {}}, "evidence": []},
        "missing_info": [],
        "kb_used": [],
        "needs_lawyer": False,
        "needs_lawyer_reason": None,
    }
    fake_llm(payload)
    session = store.create_session()
    result = chat_service.handle_chat(session, "My landlord will not pay me back.")
    assert "Section 420" not in result["reply"]
    assert "Sharma" not in result["reply"]
    assert "unverified_reference_removed" in result["flags"]
    assert "I removed a part of this answer" in result["reply"]


def test_chat_flags_unverified_number(fake_llm):
    payload = {
        "reply": "Ask for Rs. 95,000 back within 12 days.",
        "domain": "deposit",
        "language": "en",
        "case_updates": {"facts": {"common": {"amount_inr": 60000}, "deposit": {}, "refund": {}}},
        "missing_info": [],
        "kb_used": [],
        "needs_lawyer": False,
        "needs_lawyer_reason": None,
    }
    fake_llm(payload)
    session = store.create_session()
    result = chat_service.handle_chat(session, "My deposit was 60000.")
    assert "unverified_number" in result["flags"]


def test_chat_falls_back_when_llm_fails(fake_llm):
    def boom(messages, json_mode):
        raise llm.LLMUnavailable("down")

    fake_llm(boom)
    session = store.create_session()
    result = chat_service.handle_chat(session, "My landlord is silent.")
    assert result["reply"] == chat_service.FALLBACK_REPLY
    assert result["flags"] == ["llm_failure"]


def test_chat_escalates_on_lock_change():
    session = store.create_session()
    result = chat_service.handle_chat(
        session, "My landlord changed the lock and kept my belongings inside."
    )
    assert result["escalation"]["level"] == "urgent"
    assert result["escalation"]["resources"]


def test_chat_language_is_reported(fake_llm):
    payload = {
        "reply": "आप लिखित में मांग कर सकते हैं।",
        "domain": "deposit",
        "language": "hi",
        "case_updates": {"facts": {"common": {}, "deposit": {}, "refund": {}}},
        "missing_info": [],
        "kb_used": [],
        "needs_lawyer": False,
        "needs_lawyer_reason": None,
    }
    fake_llm(payload)
    session = store.create_session()
    result = chat_service.handle_chat(session, "Mera landlord deposit wapas nahi kar raha.")
    assert result["language"] == "hi"


def test_summary_keeps_verified_items_and_fills_dates():
    session, doc = _session_with_doc()
    payload = summary_service.summarize(session, doc.doc_id)
    summary = payload["summary"]
    assert summary["doc_type"] == "rental_agreement"
    assert len(summary["key_amounts"]) == 1
    assert summary["key_dates"][0]["date_iso"] == "2025-01-01"
    assert summary["arbitration_clause"]["found"] is True
    assert summary["arbitration_clause"]["kb_ids"] == ["arb_clause_basics"]
    assert payload["dropped_unverified"] == 0
    assert "unknown_kb_tag" in payload["flags"]


def test_summary_drops_fabricated_quote(fake_llm):
    fabricated = {
        "doc_type": "rental_agreement",
        "parties": [{"name": "Rakesh Sharma", "role": "landlord"}],
        "key_amounts": [
            {"label": "deposit", "amount_inr": 60000, "quote": "The deposit was returned twice over"}
        ],
        "key_dates": [],
        "key_clauses": [],
        "arbitration_clause": {"found": False, "quote": None, "plain_explanation": None, "kb_ids": []},
        "red_flags": [],
        "plain_summary": "A rent agreement.",
    }
    fake_llm(fabricated)
    session, doc = _session_with_doc()
    payload = summary_service.summarize(session, doc.doc_id)
    assert payload["summary"]["key_amounts"] == []
    assert payload["dropped_unverified"] == 1


def test_summary_is_cached(fake_llm):
    calls = {"n": 0}

    def responder(messages, json_mode):
        calls["n"] += 1
        return {
            "doc_type": "other",
            "parties": [],
            "key_amounts": [],
            "key_dates": [],
            "key_clauses": [],
            "arbitration_clause": {"found": False, "quote": None, "plain_explanation": None, "kb_ids": []},
            "red_flags": [],
            "plain_summary": "Short.",
        }

    fake_llm(responder)
    session, doc = _session_with_doc()
    summary_service.summarize(session, doc.doc_id)
    summary_service.summarize(session, doc.doc_id)
    assert calls["n"] == 1


def test_summary_unknown_document_raises():
    session = store.create_session()
    with pytest.raises(common.ServiceError) as excinfo:
        summary_service.summarize(session, "missing")
    assert excinfo.value.status == 404


def test_summary_rate_limited_raises_429(monkeypatch, fake_llm):
    monkeypatch.setattr(config, "CHUNK_RATE_LIMIT_WAIT_SECONDS", 0)

    def responder(messages, json_mode):
        raise llm.LLMRateLimited("busy")

    fake_llm(responder)
    session, doc = _session_with_doc()
    with pytest.raises(common.ServiceError) as excinfo:
        summary_service.summarize(session, doc.doc_id)
    assert excinfo.value.status == 429


def test_timeline_sorts_and_drops_unverified():
    session, doc = _session_with_doc()
    payload = timeline_service.build_timeline(session, include_chat=False)
    events = payload["events"]
    assert [event["date_iso"] for event in events] == ["2025-01-01", "2025-11-30"]
    assert payload["dropped_unverified"] == 1
    assert all(event["grounded"] for event in events)
    assert all(event["source"] == "document" for event in events)


def test_timeline_ambiguous_date_lowers_confidence(fake_llm):
    def responder(messages, json_mode):
        return {
            "events": [
                {
                    "date_raw": "04/05/2025",
                    "event": "Agreement signed",
                    "quote": "made on 1 January 2025",
                    "confidence": "high",
                }
            ]
        }

    fake_llm(responder)
    session, _ = _session_with_doc()
    payload = timeline_service.build_timeline(session, include_chat=False)
    assert payload["events"][0]["confidence"] == "low"
    assert payload["events"][0]["date_iso"] == "2025-05-04"


def test_timeline_marks_source_both_for_duplicate_events(fake_llm):
    session, _ = _session_with_doc()
    session.add_turn("user", "I vacated the flat on 30 November 2025 and nobody replied.")

    def responder(messages, json_mode):
        return {
            "events": [
                {
                    "date_raw": "30 November 2025",
                    "event": "Tenancy ended",
                    "quote": "30 November 2025",
                    "confidence": "high",
                }
            ]
        }

    fake_llm(responder)
    payload = timeline_service.build_timeline(session)
    assert len(payload["events"]) == 1
    assert payload["events"][0]["source"] == "both"


def test_timeline_unknown_document_raises():
    session = store.create_session()
    with pytest.raises(common.ServiceError) as excinfo:
        timeline_service.build_timeline(session, ["nope"])
    assert excinfo.value.status == 404


def test_notice_requires_known_domain():
    session = store.create_session()
    with pytest.raises(common.ServiceError) as excinfo:
        notice_service.draft_notice(session)
    assert excinfo.value.status == 422
    assert excinfo.value.code == "bad_request"


def test_notice_lists_missing_placeholders():
    session = store.create_session()
    session.case_file["domain"] = "deposit"
    payload = notice_service.draft_notice(session)
    assert "DRAFT" in payload["notice_markdown"]
    assert "[OTHER PARTY ADDRESS]" in payload["missing_placeholders"]
    assert payload["kb_used"] == ["legal_notice_optional"]


def test_placeholder_extraction_handles_mixed_case():
    text = (
        "From: [Your Name], [YOUR ADDRESS]\n"
        "To: [Landlord's Name]\n"
        "Date: [DATE]\n"
        "Ref: [KB:legal_notice_optional] and a [see the link](http://example.test) link."
    )
    found = set(notice_service.PLACEHOLDER_RE.findall(text))
    assert found == {"Your Name", "YOUR ADDRESS", "Landlord's Name", "DATE"}


def test_service_error_carries_code_and_status():
    error = common.ServiceError("not_found", "gone", 404)
    assert (error.code, error.message, error.status) == ("not_found", "gone", 404)
