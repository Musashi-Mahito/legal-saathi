"""JSON Schemas for every LLM output.

The schemas are the contract between ``prompts.py`` and the services: anything
that does not validate is repaired once and then rejected.
"""

from __future__ import annotations

DOC_TYPES: list[str] = [
    "rental_agreement",
    "invoice_or_receipt",
    "warranty_or_policy",
    "terms_and_conditions",
    "legal_notice",
    "email_or_chat",
    "other",
]

CONFIDENCE_LEVELS: list[str] = ["high", "medium", "low"]

CHAT_SCHEMA: dict = {
    "type": "object",
    "required": ["reply", "domain", "language"],
    "properties": {
        "reply": {"type": "string", "minLength": 1},
        "domain": {
            "type": "string",
            "enum": ["deposit", "refund", "unknown", "out_of_scope"],
        },
        "language": {"type": "string"},
        "case_updates": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "object",
                    "properties": {
                        "common": {"type": "object"},
                        "deposit": {"type": "object"},
                        "refund": {"type": "object"},
                    },
                },
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["type", "description"],
                        "properties": {
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "have": {"type": "string", "enum": ["yes", "no", "unknown"]},
                        },
                    },
                },
            },
        },
        "missing_info": {"type": "array", "items": {"type": "string"}},
        "kb_used": {"type": "array", "items": {"type": "string"}},
        "needs_lawyer": {"type": "boolean"},
        "needs_lawyer_reason": {"type": ["string", "null"]},
    },
}

SUMMARY_SCHEMA: dict = {
    "type": "object",
    "required": [
        "doc_type",
        "parties",
        "key_amounts",
        "key_dates",
        "key_clauses",
        "arbitration_clause",
        "red_flags",
        "plain_summary",
    ],
    "properties": {
        "doc_type": {"type": "string", "enum": DOC_TYPES},
        "parties": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
        },
        "key_amounts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "quote"],
                "properties": {
                    "label": {"type": "string"},
                    "amount_inr": {"type": ["number", "null"]},
                    "quote": {"type": "string"},
                },
            },
        },
        "key_dates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "quote"],
                "properties": {
                    "label": {"type": "string"},
                    "date_raw": {"type": ["string", "null"]},
                    "date_iso": {"type": ["string", "null"]},
                    "quote": {"type": "string"},
                },
            },
        },
        "key_clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["topic", "summary", "quote"],
                "properties": {
                    "topic": {"type": "string"},
                    "summary": {"type": "string"},
                    "quote": {"type": "string"},
                },
            },
        },
        "arbitration_clause": {
            "type": "object",
            "required": ["found"],
            "properties": {
                "found": {"type": "boolean"},
                "quote": {"type": ["string", "null"]},
                "plain_explanation": {"type": ["string", "null"]},
                "kb_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "plain_summary": {"type": "string"},
    },
}

TIMELINE_SCHEMA: dict = {
    "type": "object",
    "required": ["events"],
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["event", "quote"],
                "properties": {
                    "date_raw": {"type": ["string", "null"]},
                    "event": {"type": "string"},
                    "quote": {"type": "string"},
                    "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
                },
            },
        }
    },
}

NOTICE_SCHEMA: dict = {
    "type": "object",
    "required": ["notice_markdown"],
    "properties": {
        "notice_markdown": {"type": "string", "minLength": 50},
        "kb_used": {"type": "array", "items": {"type": "string"}},
    },
}

SUMMARY_MERGE_SCHEMA: dict = {
    "type": "object",
    "required": ["plain_summary"],
    "properties": {"plain_summary": {"type": "string"}},
}
