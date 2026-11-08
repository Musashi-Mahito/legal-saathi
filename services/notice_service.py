"""Draft notice: facts only, placeholders for anything missing."""

from __future__ import annotations

import json
import logging
import re
from datetime import date

import checks
import kb
import prompts
import schemas
import store
from services import common
from store import Session

logger = logging.getLogger(__name__)

PLACEHOLDER_RE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9 _\-/'.]{0,48})\](?!\()")
NOTICE_DOMAINS = {"deposit", "refund"}


def _build_messages(session: Session) -> list[dict]:
    """Build the notice prompt from the case file and document summaries."""
    system = prompts.render(
        prompts.NOTICE_SYSTEM,
        TODAY=date.today().isoformat(),
        KB_JSON=kb.render_for_prompt(session.case_file.get("domain")),
        CASE_FILE_JSON=json.dumps(session.case_file, ensure_ascii=False),
        DOC_SUMMARIES=common.doc_summaries_json(session),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Draft the notice as JSON now."},
    ]


def draft_notice(session: Session, doc_ids: list[str] | None = None) -> dict:
    """Draft a notice for a known deposit or refund case."""
    domain = session.case_file.get("domain")
    if domain not in NOTICE_DOMAINS:
        raise common.ServiceError(
            "bad_request",
            "The case type is not known yet, so a notice cannot be drafted.",
            422,
        )
    for doc_id in doc_ids or []:
        if store.get_document(session, str(doc_id)) is None:
            raise common.ServiceError("not_found", "Document not found.", 404)

    calls: list[dict] = []
    data, flag = common.complete_json_resilient(
        _build_messages(session),
        schemas.NOTICE_SCHEMA,
        temperature=0.2,
        max_tokens=1800,
        calls=calls,
    )
    if data is None:
        raise common.llm_error(flag)

    notice, removed, flags = checks.scan_citations(
        str(data.get("notice_markdown") or ""), kb.allowlist(), set(kb.ids())
    )
    if removed:
        logger.info("notice_unverified_reference_removed count=%d", removed)
    kb_used = [entry for entry in data.get("kb_used") or [] if kb.get(entry)]
    return {
        "notice_markdown": notice,
        "missing_placeholders": sorted({match.group(0) for match in PLACEHOLDER_RE.finditer(notice)}),
        "kb_used": common.dedupe(kb_used),
        "flags": common.dedupe(flags),
        "_llm": calls,
    }
