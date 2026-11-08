# 4. API reference

Base: `http://<FLASK_HOST>:<FLASK_PORT>` (defaults `127.0.0.1:5000`). All responses
are JSON.

Every error uses one shape:

```json
{ "error": { "code": "not_found", "message": "Session not found." } }
```

| code | HTTP | Meaning |
|---|---|---|
| `bad_request` | 400 | Missing or invalid field |
| `not_found` | 404 | Unknown session, document or route |
| `file_too_large` | 413 | Over `MAX_UPLOAD_MB` |
| `unsupported_type` | 415 | Not PDF/DOCX/TXT, or content does not match the extension |
| `empty_document` | 422 | No extractable text |
| `scanned_pdf_unsupported` | 422 | PDF has almost no text layer |
| `rate_limited` | 429 | Every provider rate-limited |
| `llm_bad_output` | 502 | Model output invalid after one repair retry |
| `llm_unavailable` | 503 | No provider reachable, or provider misconfigured |
| `internal_error` | 500 | Unexpected server error (details only in the log) |

---

## `GET /api/health`

```json
{ "status": "ok", "providers": ["groq"], "models": { "groq": "qwen/qwen3.8-27b" } }
```

Never returns keys.

## `POST /api/session`

Creates a session. No body.

```
201 { "session_id": "<uuid>" }
```

## `POST /api/chat`

```json
{ "session_id": "uuid", "message": "My landlord is not returning my deposit of 60000" }
```

```json
{
  "reply": "… [KB:deposit_forum_civil] … Which city or state are you in?",
  "domain": "deposit",
  "language": "en",
  "case_file": { "…": "full case file" },
  "missing_info": ["landlord's reason for keeping the deposit"],
  "kb_used": ["deposit_forum_civil"],
  "escalation": { "level": "none", "reasons": [], "resources": [] },
  "flags": []
}
```

- The server keeps the history; the client sends only the new message.
- `message` ≤ 2,000 characters.
- `[KB:id]` tags stay in `reply`; the UI renders them as source chips.
- `reply` never contains more than one question.

## `POST /api/upload` (multipart/form-data)

Fields: `session_id`, `file`.

```json
{
  "doc_id": "uuid", "filename": "rent_agreement.pdf",
  "pages": 6, "chars": 14230, "truncated": false,
  "warnings": [], "flags": ["possible_prompt_injection"]
}
```

## `POST /api/summarize`

```json
{ "session_id": "uuid", "doc_id": "uuid" }
```

```json
{
  "summary": {
    "doc_type": "rental_agreement",
    "parties": [{ "name": "A. Sharma", "role": "landlord" }],
    "key_amounts": [{ "label": "security deposit", "amount_inr": 60000, "quote": "…" }],
    "key_dates": [{ "label": "agreement start", "date_raw": "1 January 2025", "date_iso": "2025-01-01", "quote": "…" }],
    "key_clauses": [{ "topic": "deductions", "summary": "…", "quote": "…" }],
    "arbitration_clause": {
      "found": true, "quote": "…", "plain_explanation": "…",
      "kb_ids": ["arb_clause_basics"]
    },
    "red_flags": ["The landlord alone appoints the arbitrator."],
    "plain_summary": "…"
  },
  "dropped_unverified": 1,
  "flags": []
}
```

`date_iso` is filled by code from `date_raw`, never by the model. Results are
cached per document.

## `POST /api/timeline`

```json
{ "session_id": "uuid", "doc_ids": ["uuid"], "include_chat": true }
```

`doc_ids` is optional (default: all uploaded documents). `include_chat` defaults
to `true`.

```json
{
  "events": [{
    "date_raw": "30 November 2025", "date_iso": "2025-11-30",
    "event": "Tenant vacated the flat", "quote": "I vacated on 30 November 2025",
    "source": "chat", "doc_id": null,
    "confidence": "high", "grounded": true
  }],
  "undated": [{ "event": "…", "quote": "…", "source": "document", "doc_id": "uuid" }],
  "dropped_unverified": 2,
  "flags": []
}
```

Sorted by `date_iso` ascending. Items without a parseable date go to `undated`.
`source` is `document`, `chat`, or `both` when both produced the same event.

## `POST /api/notice`

```json
{ "session_id": "uuid", "doc_ids": [] }
```

```json
{
  "notice_markdown": "DRAFT - for your review … [YOUR ADDRESS] …",
  "missing_placeholders": ["[YOUR ADDRESS]", "[OTHER PARTY ADDRESS]"],
  "kb_used": ["legal_notice_optional"],
  "flags": []
}
```

Returns `422 bad_request` when the domain is not yet `deposit` or `refund`.

## `GET /api/case/<session_id>`

Returns the full case file.

## `GET /api/kb`

The UI's source chips need titles and verification state — nothing more.

```json
[{ "id": "cpa_limitation_2y", "title": "Time limit for a consumer complaint", "verified": false }]
```

Rules are never exposed by this endpoint.

---

## Flags

| Flag | Where | Meaning |
|---|---|---|
| `unverified_reference_removed` | chat, notice | A sentence citing an unknown law was deleted |
| `unverified_number` | chat | A rupee amount or duration appears in no source |
| `unknown_kb_tag` | chat, summary | A `[KB:id]` did not exist and was stripped |
| `possible_prompt_injection` | upload, summary, timeline | A document contains AI-directed instructions |
| `partial_result` | summary, timeline | Rate limiting stopped some chunks |
| `llm_failure` | chat | The model layer failed; a fixed safe reply was returned |

## Limits

| Limit | Value | Config key |
|---|---|---|
| Message length | 2,000 chars | `MAX_MESSAGE_CHARS` |
| Upload size | 5 MB | `MAX_UPLOAD_MB` |
| PDF pages read | 30 | `MAX_PDF_PAGES` |
| Extracted text | 120,000 chars | `MAX_DOC_CHARS` |
| Sessions | 200, 2 h idle TTL | `MAX_SESSIONS`, `SESSION_TTL_SECONDS` |
| History turns sent | 10 | `HISTORY_TURNS` |
