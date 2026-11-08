"""Knowledge base loader and prompt rendering.

``kb.json`` is the only place legal content may live. The loader validates the
file at startup and refuses to run on bad data, so the app can never fall back
to invented law.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import config
from checks import normalize

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "domain",
    "title",
    "rule",
    "plain",
    "allowed_refs",
    "source_url",
    "verified",
    "last_verified",
)
ALLOWED_DOMAINS: frozenset[str] = frozenset({"deposit", "refund", "both"})

_LOCK = threading.RLock()
_entries: list[dict] | None = None
_index: dict[str, dict] = {}
_allowed_refs: set[str] = set()


class KBError(Exception):
    """The knowledge base file is missing or malformed."""


def _validate_entry(entry: object, position: int, seen: set[str]) -> dict:
    """Validate one entry and return it, raising ``KBError`` when invalid."""
    if not isinstance(entry, dict):
        raise KBError(f"entry {position} is not an object")
    for field in REQUIRED_FIELDS:
        if field not in entry:
            raise KBError(f"entry {position} is missing field '{field}'")
    entry_id = entry["id"]
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise KBError(f"entry {position} has an invalid id")
    if entry_id in seen:
        raise KBError(f"duplicate id '{entry_id}'")
    seen.add(entry_id)
    if entry["domain"] not in ALLOWED_DOMAINS:
        raise KBError(f"entry '{entry_id}' has an invalid domain")
    for field in ("title", "rule", "plain"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise KBError(f"entry '{entry_id}' has an invalid '{field}'")
    refs = entry["allowed_refs"]
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        raise KBError(f"entry '{entry_id}' has invalid allowed_refs")
    if not isinstance(entry["verified"], bool):
        raise KBError(f"entry '{entry_id}' has a non-boolean 'verified'")
    last_verified = entry["last_verified"]
    if last_verified is not None and not isinstance(last_verified, str):
        raise KBError(f"entry '{entry_id}' has an invalid 'last_verified'")
    if not isinstance(entry["source_url"], str):
        raise KBError(f"entry '{entry_id}' has an invalid 'source_url'")
    return entry


def load_kb(path: Path | None = None) -> list[dict]:
    """Load, validate and cache the knowledge base. Raises ``KBError``."""
    global _entries, _index, _allowed_refs
    kb_path = Path(path) if path is not None else config.KB_PATH
    try:
        with open(kb_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise KBError(f"cannot read knowledge base: {kb_path}") from exc
    except json.JSONDecodeError as exc:
        raise KBError("knowledge base is not valid JSON") from exc
    if not isinstance(raw, list) or not raw:
        raise KBError("knowledge base must be a non-empty JSON array")
    seen: set[str] = set()
    validated = [_validate_entry(entry, position, seen) for position, entry in enumerate(raw)]
    with _LOCK:
        _entries = validated
        _index = {entry["id"]: entry for entry in validated}
        _allowed_refs = {
            normalize(ref) for entry in validated for ref in entry["allowed_refs"] if ref.strip()
        }
    return validated


def reset() -> None:
    """Forget the cached knowledge base (used by tests)."""
    global _entries, _index, _allowed_refs
    with _LOCK:
        _entries = None
        _index = {}
        _allowed_refs = set()


def _ensure_loaded() -> list[dict]:
    """Load the knowledge base on first use."""
    with _LOCK:
        if _entries is None:
            return load_kb()
        return _entries


def entries() -> list[dict]:
    """Every knowledge base entry."""
    return list(_ensure_loaded())


def get(entry_id: str) -> dict | None:
    """Return one entry by id, or ``None``."""
    _ensure_loaded()
    return _index.get(entry_id)


def ids() -> list[str]:
    """All entry ids in file order."""
    return [entry["id"] for entry in _ensure_loaded()]


def allowlist() -> set[str]:
    """Normalized set of every allowed legal reference."""
    _ensure_loaded()
    return set(_allowed_refs)


def entries_for_domain(domain: str | None) -> list[dict]:
    """Entries relevant to a domain (``both`` always included)."""
    active = (domain or "unknown").strip().lower()
    if active not in {"deposit", "refund"}:
        return entries()
    return [
        entry
        for entry in _ensure_loaded()
        if entry["domain"] in {active, "both"}
    ]


def render_for_prompt(domain: str | None) -> str:
    """Compact JSON block of the knowledge base for a prompt."""
    payload = [
        {
            "id": entry["id"],
            "title": entry["title"],
            "plain": entry["plain"],
            "rule": entry["rule"],
            "verified": entry["verified"],
        }
        for entry in entries_for_domain(domain)
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def summary_for_ui() -> list[dict]:
    """Minimal entry list for the UI's source chips."""
    return [
        {"id": entry["id"], "title": entry["title"], "verified": entry["verified"]}
        for entry in _ensure_loaded()
    ]
