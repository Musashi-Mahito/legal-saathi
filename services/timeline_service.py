"""Timeline building: dates parsed and quotes verified by code."""

from __future__ import annotations

import logging
from datetime import date

import checks
import docs
import prompts
import schemas
import store
from services import common
from store import Document, Session

logger = logging.getLogger(__name__)

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def _timeline_messages(source: str, kb_free_system: str) -> list[dict]:
    """Build the messages for one timeline source block."""
    return [
        {"role": "system", "content": kb_free_system},
        {"role": "user", "content": source},
    ]


def _build_events(
    raw_events: list[dict],
    source_text: str,
    source: str,
    doc_id: str | None,
) -> tuple[list[dict], int]:
    """Verify quotes, parse dates and normalize one batch of events."""
    events: list[dict] = []
    dropped = 0
    for raw in raw_events or []:
        quote = str(raw.get("quote") or "")
        if not checks.verify_quote(quote, source_text):
            dropped += 1
            continue
        date_raw = raw.get("date_raw")
        date_iso, ambiguous = checks.parse_date(date_raw)
        confidence = str(raw.get("confidence") or "medium").lower()
        if confidence not in CONFIDENCE_RANK:
            confidence = "medium"
        if ambiguous:
            confidence = "low"
        events.append(
            {
                "date_raw": date_raw,
                "date_iso": date_iso,
                "event": str(raw.get("event") or "").strip(),
                "quote": quote,
                "source": source,
                "doc_id": doc_id,
                "confidence": confidence,
                "grounded": True,
            }
        )
    return events, dropped


def _system_prompt() -> str:
    """Render the timeline system prompt for today's date."""
    return prompts.render(prompts.TIMELINE_SYSTEM, TODAY=date.today().isoformat())


def _document_events(session: Session, doc: Document) -> tuple[list[dict], int, list[str], list[dict]]:
    """Timeline events for one document, cached per document."""
    cache_key = f"{doc.doc_id}:timeline"
    cached = session.cache.get(cache_key)
    if cached is not None:
        return (
            cached["events"],
            cached["dropped_unverified"],
            cached["flags"],
            cached["calls"],
        )

    system = _system_prompt()
    events: list[dict] = []
    dropped = 0
    flags = docs.injection_flags(doc.text)
    calls: list[dict] = []
    partial = False
    for chunk in doc.chunks or [doc.text]:
        data, flag = common.complete_json_resilient(
            _timeline_messages(prompts.wrap_document(doc.doc_id, chunk), system),
            schemas.TIMELINE_SCHEMA,
            temperature=0.0,
            prefer=common.prefer_for(chunk),
            calls=calls,
        )
        if data is None:
            if flag == "rate_limited":
                partial = True
                continue
            raise common.llm_error(flag)
        chunk_events, lost = _build_events(data.get("events") or [], doc.text, "document", doc.doc_id)
        events.extend(chunk_events)
        dropped += lost
    if partial:
        flags.append("partial_result")
    session.cache[cache_key] = {
        "events": events,
        "dropped_unverified": dropped,
        "flags": flags,
        "calls": calls,
    }
    return events, dropped, flags, calls


def _chat_events(session: Session) -> tuple[list[dict], int, list[dict]]:
    """Timeline events taken from the user's own messages."""
    messages = session.user_messages()
    if not messages:
        return [], 0, []
    chat_text = session.chat_text()
    calls: list[dict] = []
    data, flag = common.complete_json_resilient(
        _timeline_messages(prompts.wrap_user_messages(messages), _system_prompt()),
        schemas.TIMELINE_SCHEMA,
        temperature=0.0,
        calls=calls,
    )
    if data is None:
        if flag == "rate_limited":
            return [], 0, calls
        raise common.llm_error(flag)
    events, dropped = _build_events(data.get("events") or [], chat_text, "chat", None)
    return events, dropped, calls


def _event_key(event: dict) -> tuple[str, str]:
    """Dedupe key: the date plus the normalized event text."""
    date_key = event.get("date_iso") or checks.normalize(event.get("date_raw") or "")
    return date_key, checks.normalize(event.get("event", ""))


def _dedupe(events: list[dict]) -> list[dict]:
    """Collapse duplicate events, keeping the most confident copy."""
    chosen: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for event in events:
        key = _event_key(event)
        existing = chosen.get(key)
        if existing is None:
            chosen[key] = dict(event)
            order.append(key)
            continue
        best, other = (
            (event, existing)
            if CONFIDENCE_RANK[event["confidence"]] > CONFIDENCE_RANK[existing["confidence"]]
            else (existing, event)
        )
        merged = dict(best)
        if best["source"] != other["source"]:
            merged["source"] = "both"
        chosen[key] = merged
    return [chosen[key] for key in order]


def _select_documents(session: Session, doc_ids: list[str] | None) -> list[Document]:
    """Resolve the requested documents, or all of them."""
    if not doc_ids:
        return list(session.documents.values())
    selected: list[Document] = []
    for doc_id in doc_ids:
        doc = store.get_document(session, str(doc_id))
        if doc is None:
            raise common.ServiceError("not_found", "Document not found.", 404)
        selected.append(doc)
    return selected


def build_timeline(
    session: Session,
    doc_ids: list[str] | None = None,
    include_chat: bool = True,
) -> dict:
    """Build a sorted, verified timeline from documents and the chat."""
    documents = _select_documents(session, doc_ids)
    events: list[dict] = []
    dropped = 0
    flags: list[str] = []
    calls: list[dict] = []
    for doc in documents:
        doc_events, lost, doc_flags, doc_calls = _document_events(session, doc)
        events.extend(doc_events)
        dropped += lost
        flags.extend(doc_flags)
        calls.extend(doc_calls)
    if include_chat:
        chat_events, lost, chat_calls = _chat_events(session)
        events.extend(chat_events)
        dropped += lost
        calls.extend(chat_calls)

    merged = _dedupe(events)
    dated = sorted(
        (event for event in merged if event.get("date_iso")),
        key=lambda event: event["date_iso"],
    )
    undated = [event for event in merged if not event.get("date_iso")]
    return {
        "events": dated,
        "undated": undated,
        "dropped_unverified": dropped,
        "flags": common.dedupe(flags),
        "_llm": calls,
    }
