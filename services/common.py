"""Helpers shared by the service layer."""

from __future__ import annotations

import json
import logging
import time

import config
import llm
from store import Session

logger = logging.getLogger(__name__)

_ERROR_STATUS = {
    "rate_limited": (429, "All model providers are busy. Please try again in a minute."),
    "llm_bad_output": (502, "The model did not return a usable answer. Please try again."),
    "llm_failure": (503, "The model service is unavailable. Please try again in a minute."),
}


class ServiceError(Exception):
    """A service-level failure that maps onto an API error."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def llm_error(flag: str | None) -> ServiceError:
    """Build the API-mapped error for an LLM failure flag."""
    status, message = _ERROR_STATUS.get(flag or "", _ERROR_STATUS["llm_failure"])
    return ServiceError(flag or "llm_failure", message, status)


def doc_summary_payload(session: Session) -> list[dict]:
    """Compact summaries of the session's documents for prompts and checks."""
    payload: list[dict] = []
    for doc in session.documents.values():
        summary = doc.summary or {}
        arbitration = summary.get("arbitration_clause") or {}
        payload.append(
            {
                "filename": doc.filename,
                "doc_id": doc.doc_id,
                "doc_type": summary.get("doc_type"),
                "plain_summary": summary.get("plain_summary"),
                "arbitration_clause": {
                    "found": bool(arbitration.get("found")),
                    "quote": arbitration.get("quote"),
                },
                "red_flags": summary.get("red_flags") or [],
            }
        )
    return payload


def doc_summaries_json(session: Session) -> str:
    """JSON text of the document summary payload."""
    return json.dumps(doc_summary_payload(session), ensure_ascii=False)


def prefer_for(text: str) -> str | None:
    """Preferred provider for this text length (long documents use one provider)."""
    if len(text or "") > config.LONG_DOC_CHAR_THRESHOLD:
        name = config.long_doc_provider()
        return name or None
    return None


def llm_meta(result: llm.LLMResult | None) -> dict | None:
    """Describe one model call for the job archive (no prompt or output text)."""
    if result is None:
        return None
    return {
        "provider": result.provider,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


def complete_json_resilient(
    messages: list[dict],
    schema: dict,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1800,
    prefer: str | None = None,
    calls: list[dict] | None = None,
) -> tuple[dict | None, str | None]:
    """Call the LLM, waiting once when rate limited.

    Returns ``(data, None)`` on success or ``(None, flag)`` on failure. When
    ``calls`` is given, one meta entry per successful model call is appended.
    """
    try:
        data, result = llm.complete_json(
            messages,
            schema,
            temperature=temperature,
            max_tokens=max_tokens,
            prefer=prefer,
        )
        if calls is not None:
            calls.append(llm_meta(result) or {})
        return data, None
    except llm.LLMRateLimited:
        logger.warning("service_rate_limited_retry")
        time.sleep(config.CHUNK_RATE_LIMIT_WAIT_SECONDS)
    except llm.LLMUnavailable:
        return None, "llm_failure"
    except llm.LLMBadOutput:
        return None, "llm_bad_output"
    try:
        data, result = llm.complete_json(
            messages,
            schema,
            temperature=temperature,
            max_tokens=max_tokens,
            prefer=prefer,
        )
        if calls is not None:
            calls.append(llm_meta(result) or {})
        return data, None
    except llm.LLMRateLimited:
        return None, "rate_limited"
    except llm.LLMUnavailable:
        return None, "llm_failure"
    except llm.LLMBadOutput:
        return None, "llm_bad_output"


def dedupe(values: list[str]) -> list[str]:
    """Remove duplicates while keeping order."""
    return list(dict.fromkeys(value for value in values if value))
