"""Chat turn: prompt, safety checks, case-file merge and escalation."""

from __future__ import annotations

import json
import logging
import re
from datetime import date

import checks
import config
import kb
import llm
import prompts
import schemas
import store
from services import common
from store import Session

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "I'm having trouble right now. Please try again in a minute. "
    "If this is urgent, contact a lawyer or your DLSA."
)

FACT_KEYS: dict[str, set[str]] = {
    "common": {"other_party_name", "amount_inr", "state_or_city", "cause_of_action_date"},
    "deposit": {
        "monthly_rent_inr",
        "deposit_paid_inr",
        "agreement_start",
        "agreement_end",
        "move_out_date",
        "deduction_claimed_inr",
        "landlord_reason",
        "written_agreement",
        "demand_made",
    },
    "refund": {
        "item_or_service",
        "seller_or_platform",
        "purchase_date",
        "amount_paid_inr",
        "refund_promised_date",
        "complaints_to_seller",
        "seller_response",
        "warranty_or_policy_exists",
        "payment_mode",
    },
}
DATE_KEYS = {
    "cause_of_action_date",
    "agreement_start",
    "agreement_end",
    "move_out_date",
    "purchase_date",
    "refund_promised_date",
}
AMOUNT_KEYS = {
    "amount_inr",
    "monthly_rent_inr",
    "deposit_paid_inr",
    "deduction_claimed_inr",
    "amount_paid_inr",
}
BOOL_KEYS = {"written_agreement", "demand_made", "warranty_or_policy_exists"}
LIST_KEYS = {"complaints_to_seller"}
DOMAINS = {"deposit", "refund", "unknown", "out_of_scope"}
_TRUE_WORDS = {"yes", "y", "true", "haan", "ha", "हाँ", "हां"}
_FALSE_WORDS = {"no", "n", "false", "nahi", "nahin", "नहीं"}
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _coerce_amount(value: object) -> int | float | None:
    """Turn a model-provided amount into a number, understanding lakh/crore."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = checks.normalize(str(value)).replace(",", "")
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    number = float(match.group(1))
    if "crore" in text:
        number *= 10_000_000
    elif "lakh" in text or "lac " in f"{text} " or "lacs" in text:
        number *= 100_000
    return int(number) if number.is_integer() else number


def _coerce_bool(value: object) -> bool | None:
    """Turn a model-provided yes/no into a boolean."""
    if isinstance(value, bool):
        return value
    text = checks.normalize(str(value))
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    return None


def _coerce_value(key: str, value: object) -> object:
    """Coerce one fact value, or return ``None`` to ignore it."""
    if value is None:
        return None
    if key in DATE_KEYS:
        iso, _ = checks.parse_date(str(value))
        return iso
    if key in AMOUNT_KEYS:
        return _coerce_amount(value)
    if key in BOOL_KEYS:
        return _coerce_bool(value)
    text = str(value).strip()
    return text[:300] or None


def _merge_facts(case_file: dict, updates: dict | None) -> None:
    """Merge model-provided facts, ignoring unknown keys and bad types."""
    facts = case_file.setdefault("facts", {})
    incoming_facts = (updates or {}).get("facts") or {}
    if not isinstance(incoming_facts, dict):
        return
    for group, allowed in FACT_KEYS.items():
        incoming = incoming_facts.get(group)
        if not isinstance(incoming, dict):
            continue
        target = facts.setdefault(group, {})
        for key, value in incoming.items():
            if key not in allowed:
                continue
            if key in LIST_KEYS:
                _merge_list_fact(target, key, value)
                continue
            coerced = _coerce_value(key, value)
            if coerced is not None:
                target[key] = coerced


def _merge_list_fact(target: dict, key: str, value: object) -> None:
    """Merge a list-valued fact such as complaints sent to the seller."""
    existing = target.get(key)
    items = list(existing) if isinstance(existing, list) else []
    new_items = value if isinstance(value, list) else [value]
    for item in new_items:
        text = str(item).strip()
        if text and text not in items:
            items.append(text[:300])
    target[key] = items


def _merge_evidence(case_file: dict, updates: dict | None) -> None:
    """Merge evidence items, de-duplicated by type and description."""
    incoming = (updates or {}).get("evidence")
    if not isinstance(incoming, list):
        return
    existing = case_file.setdefault("evidence", [])
    seen = {
        (checks.normalize(item.get("type", "")), checks.normalize(item.get("description", "")))
        for item in existing
    }
    for item in incoming:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "").strip()[:80]
        description = str(item.get("description") or "").strip()[:300]
        if not kind and not description:
            continue
        key = (checks.normalize(kind), checks.normalize(description))
        if key in seen:
            continue
        seen.add(key)
        have = str(item.get("have") or "unknown").lower()
        existing.append(
            {
                "type": kind,
                "description": description,
                "have": have if have in {"yes", "no", "unknown"} else "unknown",
            }
        )


def _system_prompt(session: Session, kb_json: str) -> str:
    """Render the chat system prompt with the case file and document summaries."""
    return prompts.render(
        prompts.CHAT_SYSTEM,
        TODAY=date.today().isoformat(),
        KB_JSON=kb_json,
        CASE_FILE_JSON=json.dumps(session.case_file, ensure_ascii=False),
        DOC_SUMMARIES=common.doc_summaries_json(session),
    ) + "\n\n" + prompts.CHAT_SCHEMA_HINT


def _build_messages(session: Session, message: str, kb_json: str) -> list[dict]:
    """System prompt plus the last turns of history plus the new message."""
    messages: list[dict] = [{"role": "system", "content": _system_prompt(session, kb_json)}]
    for turn in session.history[-config.HISTORY_TURNS :]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})
    return messages


def _fallback(session: Session, message: str) -> dict:
    """Friendly reply used when the LLM layer fails mid-chat."""
    session.add_turn("user", message)
    session.add_turn("assistant", FALLBACK_REPLY)
    case_file = session.case_file
    return {
        "reply": FALLBACK_REPLY,
        "domain": case_file.get("domain", "unknown"),
        "language": case_file.get("language", "en"),
        "case_file": case_file,
        "missing_info": case_file.get("missing_info", []),
        "kb_used": [],
        "escalation": case_file.get("escalation", {"level": "none", "reasons": [], "resources": []}),
        "flags": ["llm_failure"],
    }


def _normalize_domain(value: object, previous: str) -> str:
    """Keep the model's domain only when it is one we accept."""
    domain = str(value or "").strip().lower()
    return domain if domain in DOMAINS else previous


def _normalize_language(value: object) -> str:
    """Map the model's language label onto our four values."""
    language = str(value or "").strip().lower()
    if language in {"en", "english"}:
        return "en"
    if language in {"hi", "hindi", "हिंदी"}:
        return "hi"
    if language in {"hinglish", "hi-en"}:
        return "hinglish"
    return language or "en"


def handle_chat(session: Session, message: str) -> dict:
    """Run one chat turn and return the API response body."""
    case_file = session.case_file
    kb_json = kb.render_for_prompt(case_file.get("domain"))
    messages = _build_messages(session, message, kb_json)
    try:
        data, result = llm.complete_json(
            messages, schemas.CHAT_SCHEMA, temperature=0.2, max_tokens=1200
        )
    except (llm.LLMBadOutput, llm.LLMUnavailable, llm.LLMRateLimited):
        logger.warning("chat_llm_failure")
        return _fallback(session, message)

    reply = str(data.get("reply") or "")
    clean_reply, removed, flags = checks.scan_citations(reply, kb.allowlist(), set(kb.ids()))
    if removed:
        logger.info("chat_unverified_reference_removed count=%d", removed)
    clean_reply, extra_questions = checks.limit_questions(clean_reply)
    if extra_questions:
        logger.info("chat_extra_questions_dropped count=%d", extra_questions)
    _merge_facts(case_file, data.get("case_updates"))
    _merge_evidence(case_file, data.get("case_updates"))
    case_file["domain"] = _normalize_domain(data.get("domain"), case_file.get("domain", "unknown"))
    case_file["language"] = _normalize_language(data.get("language"))
    case_file["missing_info"] = [str(item)[:200] for item in data.get("missing_info") or []][:8]

    escalation = checks.escalate(
        case_file,
        message,
        common.doc_summary_payload(session),
        {
            "needs_lawyer": bool(data.get("needs_lawyer")),
            "needs_lawyer_reason": data.get("needs_lawyer_reason"),
        },
        date.today(),
        documents_text=store.all_text(session),
    )
    case_file["escalation"] = escalation
    flags += checks.warn_unverified_numbers(
        clean_reply, case_file, session.user_messages() + [message], kb.render_for_prompt(None)
    )
    flags = common.dedupe(flags)
    case_file["flags"] = common.dedupe(case_file.get("flags", []) + flags)

    session.add_turn("user", message)
    session.add_turn("assistant", clean_reply)
    return {
        "reply": clean_reply,
        "domain": case_file["domain"],
        "language": case_file["language"],
        "case_file": case_file,
        "missing_info": case_file["missing_info"],
        "kb_used": [entry for entry in data.get("kb_used") or [] if kb.get(entry)],
        "escalation": escalation,
        "flags": flags,
        "_llm": [common.llm_meta(result) or {}],
    }
