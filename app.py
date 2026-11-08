"""Flask app factory and HTTP routes.

Routes only validate input, call one service and return JSON.
"""

from __future__ import annotations

import logging
import time
import uuid
from uuid import UUID

from flask import Flask, jsonify, render_template, request

import config
import jobs
import kb
import llm
import store
from docs import DocError, chunk_text, extract_text, injection_flags, sanitize_filename, validate_upload
from services import chat_service, notice_service, summary_service, timeline_service
from services.common import ServiceError
from store import Document, Session

logger = logging.getLogger(__name__)

DOC_ERROR_STATUS = {
    "bad_request": 400,
    "file_too_large": 413,
    "unsupported_type": 415,
    "empty_document": 422,
    "scanned_pdf_unsupported": 422,
}


class ApiError(Exception):
    """An HTTP-level error that is rendered as the standard JSON shape."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int):
    """Build the standard error payload."""
    return jsonify({"error": {"code": code, "message": message}}), status


def _json_body() -> dict:
    """Return the request body as a dict or raise ``bad_request``."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError("bad_request", "Send a JSON object in the request body.")
    return body


def _session(session_id: object) -> Session:
    """Resolve a session id to a live session or raise ``not_found``."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ApiError("bad_request", "session_id is required.")
    try:
        UUID(session_id)
    except ValueError as exc:
        raise ApiError("bad_request", "session_id must be a UUID.") from exc
    session = store.get_session(session_id)
    if session is None:
        raise ApiError("not_found", "Session not found.", 404)
    return session


def _message(body: dict) -> str:
    """Validate the chat message."""
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ApiError("bad_request", "message is required.")
    if len(message) > config.MAX_MESSAGE_CHARS:
        raise ApiError(
            "bad_request",
            f"message must be {config.MAX_MESSAGE_CHARS} characters or fewer.",
        )
    return message.strip()


def _doc_ids(body: dict) -> list[str] | None:
    """Validate an optional ``doc_ids`` list."""
    raw = body.get("doc_ids")
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ApiError("bad_request", "doc_ids must be a list of document ids.")
    return raw


def _upload(session: Session):
    """Store an uploaded document and return the API payload."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise ApiError("bad_request", "Attach a file in the 'file' field.")
    filename = sanitize_filename(upload.filename)
    data = upload.read()
    ext = validate_upload(filename, data)
    result = extract_text(data, ext)
    document = Document(
        doc_id=str(uuid.uuid4()),
        filename=filename,
        text=result.text,
        chunks=chunk_text(result.text),
        pages=result.pages,
        truncated=result.truncated,
        warnings=list(result.warnings),
        flags=injection_flags(result.text),
    )
    session.documents[document.doc_id] = document
    if document.doc_id not in session.case_file["doc_ids"]:
        session.case_file["doc_ids"].append(document.doc_id)
    logger.info("upload_stored chars=%d pages=%s", len(result.text), result.pages)
    return {
        "doc_id": document.doc_id,
        "filename": document.filename,
        "pages": document.pages,
        "chars": len(document.text),
        "truncated": document.truncated,
        "warnings": document.warnings,
        "flags": document.flags,
    }


def _finish(
    payload: dict,
    *,
    kind: str,
    session_id: str,
    request_payload: dict | None = None,
    document_text: str | None = None,
    status: int = 200,
):
    """Archive the exchange, then return the payload without internal fields."""
    llm_calls = payload.pop("_llm", [])
    jobs.record(
        kind,
        session_id,
        request_payload or {},
        payload,
        llm_meta=llm_calls,
        document_text=document_text,
        started_at=getattr(request, "started_at", None),
    )
    return jsonify(payload), status


def _register_routes(app: Flask) -> None:
    """Attach every route to the app."""

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "providers": llm.available_providers(),
                "models": llm.provider_models(),
            }
        )

    @app.post("/api/session")
    def create_session():
        session = store.create_session()
        return jsonify({"session_id": session.session_id}), 201

    @app.post("/api/chat")
    def chat():
        body = _json_body()
        session = _session(body.get("session_id"))
        message = _message(body)
        payload = chat_service.handle_chat(session, message)
        return _finish(
            payload,
            kind="chat",
            session_id=session.session_id,
            request_payload={"message": message},
        )

    @app.post("/api/upload")
    def upload():
        session = _session(request.form.get("session_id"))
        payload = _upload(session)
        document = store.get_document(session, payload["doc_id"])
        return _finish(
            payload,
            kind="upload",
            session_id=session.session_id,
            request_payload={
                "filename": payload["filename"],
                "pages": payload["pages"],
                "chars": payload["chars"],
            },
            document_text=document.text if document else None,
            status=201,
        )

    @app.post("/api/summarize")
    def summarize():
        body = _json_body()
        session = _session(body.get("session_id"))
        doc_id = body.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id:
            raise ApiError("bad_request", "doc_id is required.")
        payload = summary_service.summarize(session, doc_id)
        return _finish(
            payload,
            kind="summary",
            session_id=session.session_id,
            request_payload={"doc_id": doc_id},
        )

    @app.post("/api/timeline")
    def timeline():
        body = _json_body()
        session = _session(body.get("session_id"))
        include_chat = bool(body.get("include_chat", True))
        doc_ids = _doc_ids(body)
        payload = timeline_service.build_timeline(session, doc_ids, include_chat)
        return _finish(
            payload,
            kind="timeline",
            session_id=session.session_id,
            request_payload={"doc_ids": doc_ids, "include_chat": include_chat},
        )

    @app.post("/api/notice")
    def notice():
        body = _json_body()
        session = _session(body.get("session_id"))
        doc_ids = _doc_ids(body)
        payload = notice_service.draft_notice(session, doc_ids)
        return _finish(
            payload,
            kind="notice",
            session_id=session.session_id,
            request_payload={"doc_ids": doc_ids},
        )

    @app.get("/api/case/<session_id>")
    def case_file(session_id: str):
        session = _session(session_id)
        return jsonify(session.case_file)

    @app.get("/api/kb")
    def knowledge_base():
        return jsonify(kb.summary_for_ui())


def _register_error_handlers(app: Flask) -> None:
    """Render every error in the documented JSON shape."""

    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return error_response(exc.code, exc.message, exc.status)

    @app.errorhandler(ServiceError)
    def handle_service_error(exc: ServiceError):
        return error_response(exc.code, exc.message, exc.status)

    @app.errorhandler(DocError)
    def handle_doc_error(exc: DocError):
        status = DOC_ERROR_STATUS.get(exc.code, 400)
        return error_response(exc.code, str(exc), status)

    @app.errorhandler(413)
    def handle_too_large(_exc):
        return error_response(
            "file_too_large",
            f"Files must be {config.MAX_UPLOAD_MB} MB or smaller.",
            413,
        )

    @app.errorhandler(404)
    def handle_not_found(_exc):
        return error_response("not_found", "Unknown endpoint.", 404)

    @app.errorhandler(405)
    def handle_method_not_allowed(_exc):
        return error_response("bad_request", "Method not allowed.", 405)

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        logger.exception("unhandled_error type=%s", type(exc).__name__)
        return error_response("internal_error", "Something went wrong on our side.", 500)


def _register_request_logging(app: Flask) -> None:
    """Log method, path, status and duration. Never log request bodies."""

    @app.before_request
    def _start_timer():
        request.started_at = time.perf_counter()

    @app.after_request
    def _log_request(response):
        started = getattr(request, "started_at", None)
        duration_ms = int((time.perf_counter() - started) * 1000) if started else 0
        logger.info(
            "request method=%s path=%s status=%d duration_ms=%d",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response


def create_app(testing: bool = False) -> Flask:
    """Build the Flask application, validating the knowledge base first."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.FLASK_SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES + 64 * 1024
    # Revalidate static files so an edited app.js or style.css is never served stale.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["TESTING"] = testing
    kb.load_kb()
    _register_routes(app)
    _register_error_handlers(app)
    _register_request_logging(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
