# ARCHITECTURE

## Folder layout

```
legal-saathi/
├── app.py                  # Flask app factory + routes (thin: validate, call service, return JSON)
├── config.py               # env + constants/thresholds
├── llm.py                  # the ONLY file that talks to an LLM provider
├── prompts.py              # prompt templates (see docs/PROMPTS.md)
├── schemas.py              # JSON Schemas for every LLM output
├── kb.py                   # loads/validates kb.json, builds prompt block + allowlist
├── kb.json                 # verified legal rules (see docs/KNOWLEDGE_BASE.md)
├── checks.py               # citation scan, quote verification, date parsing, escalation, injection scan
├── docs.py                 # file validation, text extraction, chunking
├── store.py                # in-memory sessions + documents
├── services/
│   ├── chat_service.py
│   ├── summary_service.py
│   ├── timeline_service.py
│   └── notice_service.py
├── templates/index.html
├── static/app.js
├── static/style.css
├── tests/                  # pytest unit tests + cases.json
├── scripts/run_eval.py     # runs all cases, writes outputs/
├── outputs/                # raw, unedited eval outputs (commit these)
├── docs/                   # these planning files
├── requirements.txt
├── .env.example
└── README.md
```

## Data flow

```
Browser (index.html + app.js)
   │  JSON / multipart
   ▼
app.py (routes) ──► services/* ──► prompts.py + schemas.py
                         │            kb.py (kb.json)
                         │            llm.py ──► Groq / Gemini / custom (OpenAI-compatible)
                         │            checks.py (verify + escalate)
                         └──► store.py (sessions, docs)      docs.py (extract + chunk)
```

## Chat request lifecycle

1. `app.py` validates `session_id` and `message` (length ≤ 2,000 chars).
2. `chat_service` loads the session: case file, last 10 turns, summaries of uploaded docs.
3. Build messages: system prompt (rules + today's date + KB block) + case-file block + doc-summary block + history + user message.
4. `llm.complete_json` returns the chat JSON (see `docs/PROMPTS.md`).
5. `checks.scan_citations` removes unverified legal references from `reply`; records flags.
6. `checks.escalate` computes the escalation level from code rules plus the model's `needs_lawyer`.
7. Merge `case_updates` into the case file (code validates types, parses dates).
8. Append turns to history; return reply, case file, escalation, flags.

## Case file schema (single source of truth per session)

```json
{
  "session_id": "uuid",
  "domain": "unknown",
  "language": "en",
  "facts": {
    "common": {
      "other_party_name": null, "amount_inr": null,
      "state_or_city": null, "cause_of_action_date": null
    },
    "deposit": {
      "monthly_rent_inr": null, "deposit_paid_inr": null,
      "agreement_start": null, "agreement_end": null, "move_out_date": null,
      "deduction_claimed_inr": null, "landlord_reason": null,
      "written_agreement": null, "demand_made": null
    },
    "refund": {
      "item_or_service": null, "seller_or_platform": null,
      "purchase_date": null, "amount_paid_inr": null,
      "refund_promised_date": null, "complaints_to_seller": [],
      "seller_response": null, "warranty_or_policy_exists": null,
      "payment_mode": null
    }
  },
  "evidence": [ {"type": "agreement", "description": "...", "have": "yes"} ],
  "events": [],
  "doc_ids": [],
  "missing_info": [],
  "flags": [],
  "escalation": {"level": "none", "reasons": [], "resources": []}
}
```
Rules: unknown = `null`; dates are ISO `YYYY-MM-DD` or `null`; `have` is `yes | no | unknown`; `domain` is `deposit | refund | unknown | out_of_scope`.

## What is AI, what is code

| Task | Done by | Why |
|---|---|---|
| Understand messy story, extract facts | LLM | Language understanding |
| Decide which law applies | LLM selects KB ids; **KB provides the text** | Prevents invented law |
| Date parsing and ordering | Code (`dateutil`) | Deterministic |
| Verify quotes exist in source | Code | LLMs cannot self-verify |
| Remove unverified legal references | Code (regex vs KB allowlist) | Safety net |
| Escalation to a lawyer | Code rules (+ model can raise) | Auditable |
| Merge chunk results, dedupe | Code | Cheaper, deterministic |
| Plain-language summary text, reply wording, notice drafting | LLM | Writing quality |
| File type, size, injection checks | Code | Security |

## Sessions and storage
- `store.py`: dict of sessions in memory, each with case file, history, documents (`doc_id -> {filename, text, chunks, summary}`).
- Expire sessions after 2 hours of inactivity. Cap 200 sessions. Run with a single worker (note in README).
- Uploaded files are parsed from memory; the original bytes are never saved.
- `jobs.py` archives each task to `jobs/<YYYY-MM-DD>/<job_id>/` (`request.json`, `response.json`, `meta.json`, and `document.txt` for uploads). The folder is gitignored. Set `JOBS_ARCHIVE=0` to turn it off.

## Errors and logging
- Central error handler returns JSON error objects (see `docs/API_SPEC.md`).
- Log: route, status, provider, model, latency, token usage, flags. Never log text content.
