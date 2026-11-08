# API SPEC

Base: `http://127.0.0.1:5000`. All responses are JSON. Errors use one shape:

```json
{ "error": { "code": "not_found", "message": "Session not found." } }
```

| code | HTTP | meaning |
|---|---|---|
| `bad_request` | 400 | missing/invalid field |
| `not_found` | 404 | unknown session or doc |
| `file_too_large` | 413 | over `MAX_UPLOAD_MB` |
| `unsupported_type` | 415 | not PDF/DOCX/TXT or content mismatch |
| `empty_document` | 422 | no extractable text |
| `scanned_pdf_unsupported` | 422 | PDF has almost no text (likely scanned) |
| `rate_limited` | 429 | all providers rate-limited |
| `llm_bad_output` | 502 | model output invalid after one repair retry |
| `llm_unavailable` | 503 | no provider reachable |

## GET /api/health
`200 {"status":"ok","providers":["groq","gemini"],"models":{"groq":"...","gemini":"..."}}` (no keys ever returned)

## POST /api/session
Creates a session. `201 {"session_id":"<uuid>"}`

## POST /api/chat
Request:
```json
{ "session_id": "uuid", "message": "My landlord is not returning my deposit of 60000" }
```
Response `200`:
```json
{
  "reply": "I'm sorry you're dealing with this ... [KB:deposit_forum_civil] ... Did you sign a written agreement?",
  "domain": "deposit",
  "language": "en",
  "case_file": { "...": "full case file, see ARCHITECTURE.md" },
  "missing_info": ["move-out date", "landlord's reason"],
  "kb_used": ["deposit_forum_civil"],
  "escalation": { "level": "none", "reasons": [], "resources": [] },
  "flags": []
}
```
Notes: server keeps history; client sends only the new message. `[KB:id]` tags may stay in `reply` and are rendered by the UI as small "source" chips.

## POST /api/upload  (multipart/form-data)
Fields: `session_id`, `file`.
Response `201`:
```json
{
  "doc_id": "uuid", "filename": "rent_agreement.pdf",
  "pages": 6, "chars": 14230, "truncated": false,
  "warnings": [], "flags": ["possible_prompt_injection"]
}
```

## POST /api/summarize
Request: `{ "session_id": "uuid", "doc_id": "uuid" }`
Response `200`:
```json
{
  "summary": {
    "doc_type": "rental_agreement",
    "parties": [{"name": "A. Sharma", "role": "landlord"}],
    "key_amounts": [{"label": "security deposit", "amount_inr": 60000, "quote": "security deposit of Rs. 60,000"}],
    "key_dates": [{"label": "agreement start", "date_raw": "1 January 2025", "date_iso": "2025-01-01", "quote": "commencing from 1 January 2025"}],
    "key_clauses": [{"topic": "deductions", "summary": "...", "quote": "..."}],
    "arbitration_clause": {"found": true, "quote": "...", "plain_explanation": "...", "kb_ids": ["arb_consumer_no_bar"]},
    "red_flags": ["Landlord alone appoints the arbitrator"],
    "plain_summary": "..."
  },
  "dropped_unverified": 1,
  "flags": []
}
```
The summary is also stored on the document and added to the case file context.

## POST /api/timeline
Request: `{ "session_id": "uuid", "doc_ids": ["uuid"], "include_chat": true }` (`doc_ids` optional: default all uploaded docs)
Response `200`:
```json
{
  "events": [
    {
      "date_raw": "30 November 2025", "date_iso": "2025-11-30",
      "event": "Tenant vacated the flat",
      "quote": "I vacated on 30 November 2025",
      "source": "chat", "doc_id": null,
      "confidence": "high", "grounded": true
    }
  ],
  "undated": [ { "event": "...", "quote": "...", "source": "document", "doc_id": "uuid" } ],
  "dropped_unverified": 2,
  "flags": []
}
```
Sorted by `date_iso` ascending; items without a parseable date go to `undated`.

## POST /api/notice  (stretch)
Request: `{ "session_id": "uuid", "doc_ids": [] }`
Response `200`:
```json
{
  "notice_markdown": "**DRAFT - review before sending** ...",
  "missing_placeholders": ["[LANDLORD ADDRESS]", "[YOUR ADDRESS]"],
  "kb_used": ["legal_notice_optional"],
  "flags": []
}
```
Returns `422 bad_request` ("domain unknown") if the domain is not `deposit` or `refund`.

## GET /api/case/<session_id>
`200` full case file (debug / export).

## Limits
Message ≤ 2,000 chars. Upload ≤ `MAX_UPLOAD_MB` (default 5). Extracted text cap 120,000 chars (set `truncated: true` if cut).
