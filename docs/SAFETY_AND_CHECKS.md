# SAFETY AND CHECKS (`checks.py`)

These are deterministic Python functions. They are the safety net behind the prompts. Each one needs unit tests.

## 1. `normalize(text) -> str`
Unicode NFKC, lowercase, replace curly quotes/dashes with plain ones, collapse all whitespace to one space, strip. Used by every comparison below.

## 2. Citation scan: `scan_citations(reply, allowlist) -> (clean_reply, removed_count, flags)`
Goal: no legal reference in a reply unless it is in the KB allowlist (built from every entry's `allowed_refs`).

Detect with regex (case-insensitive):
- Sections/articles/orders: `\b(?:section|sec\.?|s\.|article|order|rule)\s+\d+[a-z]?(?:\(\d+\))?`
- Acts, Rules, Codes: `\b[A-Z][A-Za-z&' ]{3,80}\b(?:Act|Rules|Code|Regulations)(?:,?\s*\d{4})?`
- Case names: `\b[A-Z][\w.&' ]{2,60}\s(?:v\.?|vs\.?|versus)\s[A-Z][\w.&' ]{2,60}`
- Citations: `AIR\s+\d{4}`, `\(\d{4}\)\s+\d+\s+SCC`, `\bSCC\s+OnLine\b`
- Common penal/criminal codes: `\b(?:IPC|BNS|CrPC|BNSS)\b`

A detected reference is **allowed** if its normalized form equals, contains, or is contained in a normalized `allowed_refs` item.
For each disallowed reference: remove the whole sentence containing it (split on `(?<=[.!?\u0964])\s+`), increment `removed_count`, add flag `unverified_reference_removed`.
If any sentence was removed, append: "I removed a part of this answer because I could not verify it. Please check with a lawyer."
Also verify every `[KB:id]` tag exists in the KB; strip unknown tags and flag `unknown_kb_tag`.

## 3. Number warning: `warn_unverified_numbers(reply, case_file, user_messages, kb_text) -> flags`
Find rupee amounts (`₹|Rs\.?|INR` followed by a number) and durations (`\d+\s*(?:days?|months?|years?)`). If the number does not appear in the case file, the user's messages, uploaded-document text or the KB, add flag `unverified_number`. Warn only (UI shows a small note); do not remove.

## 4. Quote verification: `verify_quote(quote, source_text) -> bool`
`normalize(quote)` must be a substring of `normalize(source_text)`. Minimum quote length 8 characters. No fuzzy matching in v1 (log failures so thresholds can be tuned later).
`verify_items(items, source_text) -> (kept, dropped_count)` keeps items whose quote verifies. For chat-sourced events, `source_text` is the concatenation of the user's messages.
Every API response that returns extracted items includes `dropped_unverified`.

## 5. Date parsing: `parse_date(raw) -> (iso | None, ambiguous: bool)`
- Use `dateutil.parser.parse(raw, dayfirst=True, fuzzy=False)`; return `(None, False)` on failure.
- `ambiguous=True` when day and month are both ≤ 12 and different (for example "04/05/2025"): the event's confidence is lowered to `low`.
- Words like "last month" or "yesterday" return `(None, False)` and the event goes to `undated`.
- Reject years outside 2000 to current year + 1.

## 6. Escalation: `escalate(case_file, user_message, doc_summaries, model_flag, today) -> dict`
Returns `{"level": "none|advise|urgent", "reasons": [...], "resources": [...]}`. The level only goes up; combine all triggers and keep the highest.

**URGENT triggers**
- Keywords in user message or documents (case-insensitive, include common Hinglish): `police, fir, arrest, threat, threaten, dhamki, lock changed, locked me out, locked out, tala, forcibly, evict, eviction, summons, court notice, hearing, arbitration notice, arbitral award, tribunal, ex parte, cheque bounce, violence, harass`.
- Any document with `doc_type == "legal_notice"` or a summary mentioning a court or tribunal.
- A deadline date in the case file or documents within 7 days of `today`.
- Refund domain: `cause_of_action_date` more than 24 months before `today` (possible time bar). Reason text: "This may be past the usual time limit; a lawyer can advise whether delay can be excused."

**ADVISE triggers**
- Refund `cause_of_action_date` between 21 and 24 months before `today` (limit is near).
- Claim amount above `LAWYER_ADVISE_DEPOSIT_INR` (default 500000) for deposits, or above 5000000 for refunds (different forum).
- Domain `out_of_scope`.
- Model returned `needs_lawyer: true` (use its reason).
- Arbitration clause found in a document **and** the user mentions receiving a notice.

**Resources** (text only, verify each): "District Legal Services Authority (DLSA) - free legal aid if eligible", "National Consumer Helpline 1915 (consumer problems)". Never invent phone numbers; use only those in the KB.
Thresholds live in `config.py`. Keyword matching can over-trigger; that is acceptable and should be reported as a known limitation.

## 7. Prompt-injection defence
- `scan_injection(text) -> bool`: regex for phrases such as `ignore (all )?(previous|above) instructions`, `you are now`, `system prompt`, `disregard`, `reveal your prompt`, `act as`, plus Hindi/Hinglish variants you add. If true, add flag `possible_prompt_injection` at upload and in summary.
- Always wrap documents in `<document>` tags; the system prompts say content inside is data.
- Never execute, fetch or follow URLs or commands found in documents.
- Output validation is the real defence: even if the model is tricked, citation scan, quote verification and schema validation still run.

## 8. Fail-safe replies
If the LLM layer raises `LLMBadOutput` or `LLMUnavailable` in chat, return a friendly fixed reply ("I'm having trouble right now. Please try again in a minute. If this is urgent, contact a lawyer or your DLSA.") with HTTP 200 and flag `llm_failure`; the summary/timeline/notice endpoints return the error codes from `docs/API_SPEC.md`.

## 9. Required unit tests (pytest, no network)
- Reply with "Section 420 IPC" and an unlisted case name: sentence removed, flags set.
- Reply using only KB refs: unchanged.
- Quote present with different spacing/case: verifies. Fabricated quote: drops.
- `parse_date` for "5 March 2025", "05/03/2025" (ambiguous), "last week" (None), "31 Feb 2025" (None).
- Escalation: each urgent keyword, 24+ month refund, 7-day deadline, level never decreases.
- Injection phrases detected; normal text not flagged.
