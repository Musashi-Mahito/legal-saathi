"""Document summary: per-chunk extraction, quote verification and merging."""

from __future__ import annotations

import logging
from datetime import date

import checks
import docs
import kb
import prompts
import schemas
import store
from services import common
from store import Document, Session

logger = logging.getLogger(__name__)

LIST_FIELDS: tuple[str, ...] = ("key_amounts", "key_dates", "key_clauses")


def _empty_summary() -> dict:
    """Start an empty merge target."""
    return {
        "doc_type": "other",
        "parties": [],
        "key_amounts": [],
        "key_dates": [],
        "key_clauses": [],
        "arbitration_clause": {
            "found": False,
            "quote": None,
            "plain_explanation": None,
            "kb_ids": [],
        },
        "red_flags": [],
        "plain_summary": "",
    }


def _summary_messages(chunk: str, kb_json: str, doc_id: str) -> list[dict]:
    """Build the messages for one summary chunk."""
    system = prompts.render(
        prompts.SUMMARY_SYSTEM,
        TODAY=date.today().isoformat(),
        KB_JSON=kb_json,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompts.wrap_document(doc_id, chunk)},
    ]


def _merge_parties(target: list[dict], parties: list[dict] | None) -> None:
    """Merge parties, de-duplicated by name."""
    seen = {checks.normalize(item.get("name", "")) for item in target}
    for party in parties or []:
        name = str(party.get("name") or "").strip()
        key = checks.normalize(name)
        if not key or key in seen:
            continue
        seen.add(key)
        target.append({"name": name, "role": str(party.get("role") or "").strip()})


def _merge_items(target: list[dict], items: list[dict], source_text: str, seen: set[str]) -> int:
    """Verify, de-duplicate and append verified list items. Returns dropped count."""
    kept, dropped = checks.verify_items(items, source_text)
    for item in kept:
        key = checks.normalize(item.get("quote", ""))
        if key in seen:
            continue
        seen.add(key)
        target.append(item)
    return dropped


def _merge_arbitration(target: dict, raw: dict | None, source_text: str) -> int:
    """Merge arbitration findings, keeping only a verified quote."""
    if not isinstance(raw, dict) or not raw.get("found"):
        return 0
    quote = raw.get("quote") or ""
    if not checks.verify_quote(quote, source_text):
        return 1
    if not target.get("found"):
        target.update(
            {
                "found": True,
                "quote": quote,
                "plain_explanation": raw.get("plain_explanation"),
                "kb_ids": [],
            }
        )
    target["kb_ids"].extend(str(entry) for entry in raw.get("kb_ids") or [])
    return 0


def _merge_chunks(chunk_results: list[dict], source_text: str, flags: list[str]) -> tuple[dict, int]:
    """Merge per-chunk summaries with code, not with the model."""
    merged = _empty_summary()
    dropped = 0
    seen_quotes: set[str] = set()
    for data in chunk_results:
        if merged["doc_type"] == "other" and data.get("doc_type") not in (None, "other"):
            merged["doc_type"] = data["doc_type"]
        _merge_parties(merged["parties"], data.get("parties"))
        for field in LIST_FIELDS:
            dropped += _merge_items(merged[field], data.get(field) or [], source_text, seen_quotes)
        dropped += _merge_arbitration(
            merged["arbitration_clause"], data.get("arbitration_clause"), source_text
        )
        merged["red_flags"] = common.dedupe(
            merged["red_flags"] + [str(flag) for flag in data.get("red_flags") or []]
        )
        if not merged["plain_summary"]:
            merged["plain_summary"] = str(data.get("plain_summary") or "")
    known = set(kb.ids())
    kb_ids = [entry for entry in merged["arbitration_clause"]["kb_ids"] if entry in known]
    if len(kb_ids) != len(merged["arbitration_clause"]["kb_ids"]):
        flags.append("unknown_kb_tag")
    merged["arbitration_clause"]["kb_ids"] = common.dedupe(kb_ids)
    for item in merged["key_dates"]:
        item["date_iso"], _ = checks.parse_date(item.get("date_raw"))
    return merged, dropped


def _merge_plain_summary(summaries: list[str], calls: list[dict]) -> str | None:
    """Ask the model for one short summary covering every chunk."""
    system = prompts.render(
        prompts.SUMMARY_MERGE_SYSTEM,
        SUMMARIES="\n".join(f"- {summary}" for summary in summaries if summary),
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Return the combined JSON now."},
    ]
    data, flag = common.complete_json_resilient(
        messages, schemas.SUMMARY_MERGE_SCHEMA, temperature=0.0, max_tokens=400, calls=calls
    )
    if data is None:
        logger.warning("summary_merge_failed flag=%s", flag)
        return None
    return str(data.get("plain_summary") or "")


def _finalize_summary(
    doc: Document,
    results: list[dict],
    flags: list[str],
    calls: list[dict],
) -> tuple[dict, int]:
    """Merge chunk results, adding a combined plain summary when needed."""
    summary, dropped = _merge_chunks(results, doc.text, flags)
    if len(results) > 1:
        combined = _merge_plain_summary(
            [str(data.get("plain_summary") or "") for data in results], calls
        )
        if combined:
            summary["plain_summary"] = combined
    return summary, dropped


def summarize(session: Session, doc_id: str) -> dict:
    """Return the verified summary of one uploaded document."""
    doc = store.get_document(session, doc_id)
    if doc is None:
        raise common.ServiceError("not_found", "Document not found.", 404)
    cache_key = f"{doc_id}:summary"
    if cache_key in session.cache:
        return session.cache[cache_key]

    kb_json = kb.render_for_prompt(session.case_file.get("domain"))
    flags: list[str] = docs.injection_flags(doc.text)
    results: list[dict] = []
    calls: list[dict] = []
    partial = False
    for chunk in doc.chunks or [doc.text]:
        data, flag = common.complete_json_resilient(
            _summary_messages(chunk, kb_json, doc.doc_id),
            schemas.SUMMARY_SCHEMA,
            temperature=0.0,
            prefer=common.prefer_for(chunk),
            calls=calls,
        )
        if data is None:
            if flag == "rate_limited":
                partial = True
                continue
            raise common.llm_error(flag)
        results.append(data)
    if not results:
        raise common.llm_error("rate_limited" if partial else None)

    summary, dropped = _finalize_summary(doc, results, flags, calls)
    doc.summary = summary
    if partial:
        flags.append("partial_result")
    payload = {
        "summary": summary,
        "dropped_unverified": dropped,
        "flags": common.dedupe(flags),
        "_llm": calls,
    }
    session.cache[cache_key] = payload
    return payload
