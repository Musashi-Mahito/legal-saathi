"""Deterministic safety checks: the net behind the prompts.

Every function here is pure: no network, no LLM calls, no global state. They are
the reason a model cannot smuggle invented law into an answer.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, timedelta

from dateutil import parser as date_parser

import config

MIN_QUOTE_CHARS = 8

REMOVED_NOTICE = (
    "I removed a part of this answer because I could not verify it. "
    "Please check with a lawyer."
)

_QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
    }
)

_NAME_TOKEN = r"\(?[A-Z][A-Za-z&'\-]*\)?"

SECTION_RE = re.compile(
    r"\b(?:section|sec\.?|s\.|article|order|rule)\s+\d+[a-z]?(?:\(\d+\))?",
    re.IGNORECASE,
)
ACT_RE = re.compile(
    rf"(?<![\w]){_NAME_TOKEN}(?:\s{_NAME_TOKEN}){{0,6}}\s"
    r"(?:Act|Rules|Code|Regulations)\b(?:,?\s*\d{4})?"
)
CASE_RE = re.compile(
    r"\b[A-Z][\w.&'\-]*(?:\s[\w.&'\-]+){0,6}\s(?:v\.?|vs\.?|versus)\s"
    r"[A-Z][\w.&'\-]*(?:\s[\w.&'\-]+){0,6}"
)
CITATION_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAIR\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\(\d{4}\)\s+\d+\s+SCC", re.IGNORECASE),
    re.compile(r"\bSCC\s+OnLine\b", re.IGNORECASE),
)
PENAL_RE = re.compile(r"\b(?:IPC|BNS|CrPC|BNSS)\b")
KB_TAG_RE = re.compile(r"\[KB:([A-Za-z0-9_\-]+)\]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u0964])\s+")
ABBREVIATION_RE = re.compile(
    r"(?:\b(?:v|vs|no|nos|rs|inr|sec|mr|mrs|ms|dr|hon|approx|etc|eg|ie|ltd|pvt|co)\.|\b[A-Z]\.)$",
    re.IGNORECASE,
)
RUPEE_RE = re.compile(r"(?:₹|\brs\.?|\binr\b)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
DURATION_RE = re.compile(r"(\d+)\s*(?:days?|months?|years?|weeks?)\b", re.IGNORECASE)
DIGIT_DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

URGENT_KEYWORDS: tuple[str, ...] = (
    "police",
    "fir",
    "arrest",
    "threat",
    "threaten",
    "dhamki",
    "lock changed",
    "changed the lock",
    "changed lock",
    "locked me out",
    "locked out",
    "tala",
    "forcibly",
    "evict",
    "eviction",
    "summons",
    "court notice",
    "hearing",
    "arbitration notice",
    "arbitral award",
    "tribunal",
    "ex parte",
    "cheque bounce",
    "violence",
    "harass",
)

COURT_WORDS: tuple[str, ...] = ("court", "tribunal", "arbitration", "summons", "hearing")

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|above|prior|earlier)\s+instructions",
        r"disregard\s+(?:all\s+)?(?:the\s+)?(?:\w+\s+){0,3}"
        r"(?:instructions|rules|prompt|above|previous|prior|earlier)",
        r"forget\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?instructions",
        r"you\s+are\s+now\s+",
        r"\bsystem\s+prompt\b",
        r"reveal\s+(?:your|the)\s+(?:prompt|instructions)",
        r"act\s+as\s+(?:a|an|the)\s+",
        r"\bjailbreak\b",
        r"new\s+instructions\s*:",
        r"pichli\s+hidaayat",
        r"\bअब\s+तुम\b",
        r"निर्देश\s*भूल",
        r"सिस्टम\s*प्रॉम्प्ट",
        r"पिछली\s*हिदायत",
    )
)

_LEVEL_RANK = {"none": 0, "advise": 1, "urgent": 2}


def normalize(text: str) -> str:
    """Case-fold, unify quotes and dashes, and collapse whitespace."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text)).translate(_QUOTE_MAP)
    normalized = normalized.lower()
    return re.sub(r"\s+", " ", normalized).strip()


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, keeping abbreviations such as ``v.`` attached."""
    parts = [part for part in SENTENCE_SPLIT_RE.split((text or "").strip()) if part.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and ABBREVIATION_RE.search(merged[-1].strip()):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def _references_in(sentence: str) -> list[str]:
    """Every legal-reference-looking string in one sentence."""
    found: list[str] = []
    found.extend(match.group(0) for match in SECTION_RE.finditer(sentence))
    found.extend(match.group(0) for match in ACT_RE.finditer(sentence))
    found.extend(match.group(0) for match in CASE_RE.finditer(sentence))
    for pattern in CITATION_RES:
        found.extend(match.group(0) for match in pattern.finditer(sentence))
    found.extend(match.group(0) for match in PENAL_RE.finditer(sentence))
    return found


def _is_allowed(reference: str, allowlist: set[str]) -> bool:
    """True when a reference matches an allowed KB reference."""
    ref = normalize(reference)
    if not ref:
        return True
    return any(ref == allowed or ref in allowed or allowed in ref for allowed in allowlist)


def _strip_unknown_kb_tags(reply: str, known_ids: set[str]) -> tuple[str, bool]:
    """Remove ``[KB:id]`` tags whose id is not in the knowledge base."""
    removed = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal removed
        if match.group(1) in known_ids:
            return match.group(0)
        removed = True
        return ""

    return KB_TAG_RE.sub(_replace, reply), removed


def scan_citations(
    reply: str,
    allowlist: set[str],
    known_ids: set[str] | None = None,
) -> tuple[str, int, list[str]]:
    """Remove sentences that cite legal sources outside the knowledge base."""
    flags: list[str] = []
    text = reply or ""
    if known_ids is not None:
        text, removed_tag = _strip_unknown_kb_tags(text, known_ids)
        if removed_tag:
            flags.append("unknown_kb_tag")
    kept: list[str] = []
    removed_sentences = 0
    for sentence in split_sentences(text):
        if not sentence.strip():
            continue
        disallowed = [
            reference
            for reference in _references_in(sentence)
            if not _is_allowed(reference, allowlist)
        ]
        if disallowed:
            removed_sentences += 1
            continue
        kept.append(sentence.strip())
    clean = " ".join(kept).strip()
    if removed_sentences:
        flags.append("unverified_reference_removed")
        clean = f"{clean} {REMOVED_NOTICE}".strip() if clean else REMOVED_NOTICE
    return clean, removed_sentences, flags


def warn_unverified_numbers(
    reply: str,
    case_file: dict | None,
    user_messages: list[str] | None,
    kb_text: str = "",
) -> list[str]:
    """Flag rupee amounts or durations that no source supports."""
    corpus_parts = [
        json.dumps(case_file or {}, ensure_ascii=False),
        " ".join(user_messages or []),
        kb_text or "",
    ]
    corpus = normalize(" ".join(corpus_parts)).replace(",", "")
    known_numbers = set(re.findall(r"\d+", corpus))
    for match in list(RUPEE_RE.finditer(reply or "")) + list(DURATION_RE.finditer(reply or "")):
        number = match.group(1).replace(",", "").split(".")[0]
        if number and number not in known_numbers:
            return ["unverified_number"]
    return []


def verify_quote(quote: str, source_text: str) -> bool:
    """True when the quote appears verbatim in the source text."""
    if not quote or not source_text:
        return False
    normalized_quote = normalize(quote)
    if len(normalized_quote) < MIN_QUOTE_CHARS:
        return False
    return normalized_quote in normalize(source_text)


def verify_items(
    items: list[dict] | None,
    source_text: str,
    quote_key: str = "quote",
) -> tuple[list[dict], int]:
    """Keep only the items whose quote is verified against the source."""
    kept: list[dict] = []
    dropped = 0
    for item in items or []:
        if not isinstance(item, dict):
            dropped += 1
            continue
        if verify_quote(str(item.get(quote_key) or ""), source_text):
            kept.append(item)
        else:
            dropped += 1
    return kept, dropped


def _is_ambiguous_date_text(text: str) -> bool:
    """True for numeric dates where day and month could be swapped."""
    for match in DIGIT_DATE_RE.finditer(text):
        first, second, year = match.group(1), match.group(2), match.group(3)
        if len(year) not in (2, 4):
            continue
        if int(first) <= 12 and int(second) <= 12 and int(first) != int(second):
            return True
    return False


def parse_date(raw: str | None, today: date | None = None) -> tuple[str | None, bool]:
    """Parse a human date into ISO form, reporting day/month ambiguity."""
    if raw is None:
        return None, False
    text = str(raw).strip()
    if not text:
        return None, False
    try:
        parsed = date_parser.parse(text, dayfirst=True, fuzzy=False)
    except (ValueError, OverflowError, TypeError):
        return None, False
    current = today or date.today()
    if parsed.year < 2000 or parsed.year > current.year + 1:
        return None, False
    return parsed.date().isoformat(), _is_ambiguous_date_text(text)


def _iter_iso_dates(node: object) -> list[str]:
    """Every ISO date string found in a nested structure."""
    found: list[str] = []
    if isinstance(node, dict):
        for value in node.values():
            found.extend(_iter_iso_dates(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_iter_iso_dates(value))
    elif isinstance(node, str) and ISO_DATE_RE.match(node.strip()):
        found.append(node.strip())
    return found


def _to_date(value: str | None) -> date | None:
    """Convert an ISO date string to ``date``, or ``None``."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _months_between(earlier: date, later: date) -> int:
    """Whole months between two dates."""
    months = (later.year - earlier.year) * 12 + (later.month - earlier.month)
    if later.day < earlier.day:
        months -= 1
    return months


def _fact(case_file: dict, group: str, key: str) -> object:
    """Read one case-file fact safely."""
    facts = (case_file or {}).get("facts") or {}
    return (facts.get(group) or {}).get(key)


def _claim_amount(case_file: dict, domain: str) -> int:
    """Best available claim value for threshold checks."""
    keys = ["amount_inr"]
    if domain == "deposit":
        keys += ["deposit_paid_inr", "deduction_claimed_inr"]
    else:
        keys += ["amount_paid_inr"]
    values = []
    for key in keys:
        value = _fact(case_file, "common", key)
        if value is None:
            value = _fact(case_file, "deposit", key)
        if value is None:
            value = _fact(case_file, "refund", key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return int(max(values)) if values else 0


def _summary_text(doc_summaries: list[dict] | None) -> str:
    """Serialized text of all document summaries."""
    return json.dumps(doc_summaries or [], ensure_ascii=False).lower()


def _urgent_reasons(
    case_file: dict,
    haystack: str,
    doc_summaries: list[dict] | None,
    today: date,
) -> list[str]:
    """Reasons that force the ``urgent`` level."""
    reasons: list[str] = []
    for keyword in URGENT_KEYWORDS:
        if keyword in haystack:
            reasons.append(f"Your message mentions '{keyword}', which needs a lawyer quickly.")
            break
    for summary in doc_summaries or []:
        if not isinstance(summary, dict):
            continue
        if summary.get("doc_type") == "legal_notice":
            reasons.append("An uploaded document looks like a legal notice.")
            break
    if any(word in _summary_text(doc_summaries) for word in COURT_WORDS):
        reasons.append("An uploaded document mentions a court or tribunal.")
    for iso in _iter_iso_dates((case_file or {}).get("facts") or {}):
        moment = _to_date(iso)
        if moment and today <= moment <= today + timedelta(days=config.DEADLINE_URGENT_DAYS):
            reasons.append("A date within the next week may be a deadline.")
            break
    if (case_file or {}).get("domain") == "refund":
        cause = _to_date(_fact(case_file, "common", "cause_of_action_date"))
        if cause and _months_between(cause, today) > config.REFUND_LIMITATION_MONTHS:
            reasons.append(
                "This may be past the usual time limit; a lawyer can advise whether "
                "delay can be excused."
            )
    return reasons


def _advise_reasons(
    case_file: dict,
    user_message: str,
    doc_summaries: list[dict] | None,
    model_flag: dict | bool | None,
    today: date,
) -> list[str]:
    """Reasons that force at least the ``advise`` level."""
    reasons: list[str] = []
    domain = (case_file or {}).get("domain") or "unknown"
    if domain == "refund":
        cause = _to_date(_fact(case_file, "common", "cause_of_action_date"))
        if cause:
            months = _months_between(cause, today)
            if config.REFUND_APPROACHING_MONTHS <= months <= config.REFUND_LIMITATION_MONTHS:
                reasons.append("The two-year time limit for a consumer complaint may be near.")
    limit = (
        config.LAWYER_ADVISE_DEPOSIT_INR
        if domain == "deposit"
        else config.LAWYER_ADVISE_REFUND_INR
    )
    if _claim_amount(case_file, domain) > limit:
        reasons.append("The amount involved is high enough to check with a lawyer.")
    if domain == "out_of_scope":
        reasons.append("This problem is outside what this assistant can safely cover.")
    reason = _model_reason(model_flag)
    if reason is not None:
        reasons.append(reason)
    if _arbitration_with_notice(user_message, doc_summaries):
        reasons.append("An arbitration clause and a notice are involved; a lawyer should look.")
    return reasons


def _model_reason(model_flag: dict | bool | None) -> str | None:
    """Normalize the model's ``needs_lawyer`` signal into a reason string."""
    if isinstance(model_flag, dict):
        if not model_flag.get("needs_lawyer"):
            return None
        return str(
            model_flag.get("needs_lawyer_reason")
            or "The assistant thinks this needs a lawyer's view."
        )
    if model_flag:
        return "The assistant thinks this needs a lawyer's view."
    return None


def _arbitration_with_notice(user_message: str, doc_summaries: list[dict] | None) -> bool:
    """True when a document has an arbitration clause and a notice is mentioned."""
    has_clause = any(
        isinstance(summary, dict)
        and isinstance(summary.get("arbitration_clause"), dict)
        and summary["arbitration_clause"].get("found")
        for summary in doc_summaries or []
    )
    return has_clause and "notice" in normalize(user_message)


def escalate(
    case_file: dict,
    user_message: str,
    doc_summaries: list[dict] | None,
    model_flag: dict | bool | None,
    today: date | None = None,
    documents_text: str = "",
) -> dict:
    """Decide the lawyer-escalation level from code rules only.

    The level can only go up: an earlier ``urgent`` never becomes ``advise``.
    """
    current_day = today or date.today()
    haystack = normalize(f"{user_message} {documents_text}")
    urgent = _urgent_reasons(case_file, haystack, doc_summaries, current_day)
    advise = _advise_reasons(case_file, user_message, doc_summaries, model_flag, current_day)
    level = "none"
    if urgent:
        level = "urgent"
    elif advise:
        level = "advise"
    previous = ((case_file or {}).get("escalation") or {}).get("level", "none")
    if _LEVEL_RANK.get(str(previous), 0) > _LEVEL_RANK[level]:
        level = str(previous)
    reasons = list(dict.fromkeys(urgent + advise))
    return {"level": level, "reasons": reasons, "resources": _resources(level, case_file)}


def _resources(level: str, case_file: dict) -> list[str]:
    """Plain-text help resources for the given level."""
    if level == "none":
        return []
    resources = [config.RESOURCE_DLSA]
    if (case_file or {}).get("domain") == "refund":
        resources.append(config.RESOURCE_CONSUMER_HELPLINE)
    return resources


def limit_questions(reply: str) -> tuple[str, int]:
    """Keep only the first question in a reply and drop later question sentences.

    The prompt asks for one question, but small models drift; this guarantees the
    rule deterministically. Returns ``(text, dropped_count)``.
    """
    sentences = split_sentences(reply)
    if sum(1 for sentence in sentences if "?" in sentence) <= 1:
        return reply, 0
    kept: list[str] = []
    seen_question = False
    dropped = 0
    for sentence in sentences:
        if "?" in sentence:
            if seen_question:
                dropped += 1
                continue
            seen_question = True
        kept.append(sentence)
    return " ".join(kept).strip(), dropped


def scan_injection(text: str) -> bool:
    """True when the text contains a phrase typical of a prompt injection."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)
