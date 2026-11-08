"""Job archive: what the user sent in and what the assistant sent back.

Every user task becomes one job folder, grouped by the day it happened:

    jobs/2026-11-08/<job_id>/
        request.json      what the user asked for
        response.json     exactly what the API returned
        meta.json         job id, kind, timing, and which model answered
        document.txt      extracted document text (upload jobs only)

Deliberate limits:
- Raw uploaded bytes (the original PDF/DOCX) are never written.
- ``jobs/`` is gitignored, so user data never reaches the repository.
- The console log records only identifiers and timings, never message or
  document text.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

JOB_KINDS: frozenset[str] = frozenset({"chat", "upload", "summary", "timeline", "notice"})


def new_job_id() -> str:
    """Return a fresh job identifier."""
    return str(uuid.uuid4())


def _duration_ms(started_at: float | None) -> int | None:
    """Milliseconds since ``started_at``, or ``None`` when unknown."""
    if not started_at:
        return None
    return int((time.perf_counter() - started_at) * 1000)


def _write_json(path: Path, payload: object) -> None:
    """Write JSON so that a partially written file never looks complete."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def job_folder(now: datetime | None = None, job_id: str | None = None) -> Path:
    """Path of a job folder: ``jobs/<YYYY-MM-DD>/<job_id>/``."""
    moment = now or datetime.now()
    return config.JOBS_DIR / moment.strftime("%Y-%m-%d") / (job_id or new_job_id())


def record(
    kind: str,
    session_id: str | None,
    request_payload: dict | None,
    response: dict,
    *,
    llm_meta: list[dict] | None = None,
    document_text: str | None = None,
    started_at: float | None = None,
    now: datetime | None = None,
) -> str | None:
    """Archive one task and return its job id, or ``None`` when not written.

    Never raises: a failing disk must not break a user's request.
    """
    if not config.JOBS_ENABLED:
        return None
    if kind not in JOB_KINDS:
        logger.warning("job_record_skipped kind=%s", kind)
        return None
    moment = now or datetime.now()
    job_id = new_job_id()
    try:
        folder = job_folder(moment, job_id)
        folder.mkdir(parents=True, exist_ok=True)
        _write_json(folder / "request.json", request_payload or {})
        _write_json(folder / "response.json", response)
        if document_text is not None:
            (folder / "document.txt").write_text(document_text, encoding="utf-8")
        meta = {
            "job_id": job_id,
            "kind": kind,
            "session_id": session_id,
            "created_at": moment.isoformat(timespec="seconds"),
            "duration_ms": _duration_ms(started_at),
            "llm": [entry for entry in llm_meta or [] if entry],
        }
        _write_json(folder / "meta.json", meta)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("job_write_failed kind=%s error=%s", kind, type(exc).__name__)
        return None
    logger.info(
        "job_recorded kind=%s job_id=%s duration_ms=%s llm_calls=%d",
        kind,
        job_id,
        meta["duration_ms"],
        len(meta["llm"]),
    )
    return job_id


def list_jobs(day: str | None = None) -> list[dict]:
    """Read archived job metadata, newest first, optionally for one day."""
    root = config.JOBS_DIR
    if not root.exists():
        return []
    pattern = f"{day}/*/meta.json" if day else "*/*/meta.json"
    found: list[dict] = []
    for path in root.glob(pattern):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(found, key=lambda job: job.get("created_at", ""), reverse=True)
