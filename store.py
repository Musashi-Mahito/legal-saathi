"""In-memory session and document store.

This is the only module allowed to hold mutable global state. Nothing is ever
written to disk: restarting the process clears every session.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

import config

_LOCK = threading.RLock()
_SESSIONS: dict[str, "Session"] = {}


def empty_case_file(session_id: str) -> dict:
    """Return a brand-new case file for a session."""
    return {
        "session_id": session_id,
        "domain": "unknown",
        "language": "en",
        "facts": {
            "common": {
                "other_party_name": None,
                "amount_inr": None,
                "state_or_city": None,
                "cause_of_action_date": None,
            },
            "deposit": {
                "monthly_rent_inr": None,
                "deposit_paid_inr": None,
                "agreement_start": None,
                "agreement_end": None,
                "move_out_date": None,
                "deduction_claimed_inr": None,
                "landlord_reason": None,
                "written_agreement": None,
                "demand_made": None,
            },
            "refund": {
                "item_or_service": None,
                "seller_or_platform": None,
                "purchase_date": None,
                "amount_paid_inr": None,
                "refund_promised_date": None,
                "complaints_to_seller": [],
                "seller_response": None,
                "warranty_or_policy_exists": None,
                "payment_mode": None,
            },
        },
        "evidence": [],
        "events": [],
        "doc_ids": [],
        "missing_info": [],
        "flags": [],
        "escalation": {"level": "none", "reasons": [], "resources": []},
    }


@dataclass
class Document:
    """An uploaded document held in memory for the life of its session."""

    doc_id: str
    filename: str
    text: str
    chunks: list[str]
    pages: int | None
    truncated: bool
    warnings: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    summary: dict | None = None
    cache: dict[str, dict] = field(default_factory=dict)


@dataclass
class Session:
    """A conversation plus its documents and case file."""

    session_id: str
    case_file: dict
    history: list[dict] = field(default_factory=list)
    documents: dict[str, Document] = field(default_factory=dict)
    cache: dict[str, dict] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Mark the session as recently used."""
        self.last_seen = time.time()

    def user_messages(self) -> list[str]:
        """Return the user's messages in order (assistant turns are excluded)."""
        return [turn["content"] for turn in self.history if turn.get("role") == "user"]

    def chat_text(self) -> str:
        """Concatenated user messages, used as a quote-verification source."""
        return "\n".join(self.user_messages())

    def add_turn(self, role: str, content: str) -> None:
        """Append one conversation turn to the history."""
        self.history.append({"role": role, "content": content})


def _purge_expired(now: float) -> None:
    """Drop sessions that have been idle for longer than the TTL."""
    expired = [
        sid
        for sid, session in _SESSIONS.items()
        if now - session.last_seen > config.SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _SESSIONS[sid]


def _enforce_capacity() -> None:
    """Evict the least recently used session when the cap is exceeded."""
    while len(_SESSIONS) >= config.MAX_SESSIONS:
        oldest = min(_SESSIONS.items(), key=lambda item: item[1].last_seen)
        del _SESSIONS[oldest[0]]


def create_session() -> Session:
    """Create and register a new session."""
    with _LOCK:
        _purge_expired(time.time())
        _enforce_capacity()
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id, case_file=empty_case_file(session_id))
        _SESSIONS[session_id] = session
        return session


def get_session(session_id: str) -> Session | None:
    """Return a live session or ``None`` when it is unknown or expired."""
    if not session_id:
        return None
    with _LOCK:
        _purge_expired(time.time())
        session = _SESSIONS.get(session_id)
        if session is not None:
            session.touch()
        return session


def delete_session(session_id: str) -> None:
    """Remove a session and everything held in memory for it."""
    with _LOCK:
        _SESSIONS.pop(session_id, None)


def clear_all() -> None:
    """Remove every session (used by tests)."""
    with _LOCK:
        _SESSIONS.clear()


def session_count() -> int:
    """Return the number of live sessions (used by tests)."""
    with _LOCK:
        return len(_SESSIONS)


def get_document(session: Session, doc_id: str) -> Document | None:
    """Return one of the session's documents."""
    return session.documents.get(doc_id)


def all_text(session: Session) -> str:
    """Concatenated text of every document in the session."""
    return "\n".join(doc.text for doc in session.documents.values())
