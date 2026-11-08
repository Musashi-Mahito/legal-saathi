"""Tests for prompt rendering and output schemas."""

from __future__ import annotations

import re
from pathlib import Path

import jsonschema
import pytest

import prompts
import schemas

VALUES = {
    "TODAY": "2026-01-10",
    "KB_JSON": '{"id": "test"}',
    "CASE_FILE_JSON": '{"domain": "deposit"}',
    "DOC_SUMMARIES": "[]",
    "SUMMARIES": "- a part summary",
}

TEMPLATES = (
    prompts.CHAT_SYSTEM,
    prompts.SUMMARY_SYSTEM,
    prompts.TIMELINE_SYSTEM,
    prompts.NOTICE_SYSTEM,
    prompts.SUMMARY_MERGE_SYSTEM,
)

SAMPLES = {
    "chat": {
        "reply": "Try asking in writing [KB:legal_notice_optional].",
        "domain": "deposit",
        "language": "en",
        "case_updates": {
            "facts": {"common": {"amount_inr": 60000}, "deposit": {}, "refund": {}},
            "evidence": [{"type": "chat", "description": "WhatsApp messages", "have": "yes"}],
        },
        "missing_info": ["move-out date"],
        "kb_used": ["legal_notice_optional"],
        "needs_lawyer": False,
        "needs_lawyer_reason": None,
    },
    "summary": {
        "doc_type": "rental_agreement",
        "parties": [{"name": "A", "role": "landlord"}],
        "key_amounts": [{"label": "deposit", "amount_inr": 60000, "quote": "deposit of Rs. 60,000"}],
        "key_dates": [
            {"label": "start", "date_raw": "1 January 2025", "date_iso": None, "quote": "from 1 January 2025"}
        ],
        "key_clauses": [{"topic": "deductions", "summary": "capped", "quote": "not exceeding Rs. 5,000"}],
        "arbitration_clause": {
            "found": True,
            "quote": "referred to a sole arbitrator",
            "plain_explanation": "A private arbitrator decides.",
            "kb_ids": ["arb_clause_basics"],
        },
        "red_flags": ["The landlord appoints the arbitrator."],
        "plain_summary": "A rent agreement.",
    },
    "timeline": {
        "events": [
            {"date_raw": "1 January 2025", "event": "Agreement signed", "quote": "made on 1 January 2025", "confidence": "high"}
        ]
    },
    "notice": {"notice_markdown": "DRAFT " + "x" * 60, "kb_used": ["legal_notice_optional"]},
    "summary_merge": {"plain_summary": "A combined summary."},
}

SCHEMA_FOR = {
    "chat": schemas.CHAT_SCHEMA,
    "summary": schemas.SUMMARY_SCHEMA,
    "timeline": schemas.TIMELINE_SCHEMA,
    "notice": schemas.NOTICE_SCHEMA,
    "summary_merge": schemas.SUMMARY_MERGE_SCHEMA,
}


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_renders(template):
    rendered = prompts.render(template, **VALUES)
    assert "{{" not in rendered
    assert "2026-01-10" in rendered or "TODAY" not in template


@pytest.mark.parametrize("template", TEMPLATES)
def test_missing_value_raises(template):
    with pytest.raises(KeyError):
        prompts.render(template)


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_sample_validates_against_schema(name):
    jsonschema.validate(instance=SAMPLES[name], schema=SCHEMA_FOR[name])


def test_chat_schema_rejects_bad_domain():
    bad = dict(SAMPLES["chat"])
    bad["domain"] = "criminal"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schemas.CHAT_SCHEMA)


def test_wrap_helpers():
    assert prompts.wrap_document("abc", "text").startswith('<document id="abc">')
    assert "<user_messages>" in prompts.wrap_user_messages(["one", "two"])


def test_prompts_contain_no_legal_content():
    source = Path(prompts.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\bSection\s+\d", source)
    assert not re.search(r"\b(?:IPC|BNS|CrPC|BNSS)\b", source)
    for act_name in (
        "Consumer Protection Act",
        "Limitation Act",
        "Arbitration and Conciliation Act",
        "Model Tenancy Act",
        "Legal Services Authorities Act",
    ):
        assert act_name not in source
