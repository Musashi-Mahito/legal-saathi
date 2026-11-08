# 2. Architecture

## Shape

One small Flask app. Routes validate input, call exactly one service, and return
JSON. Services own the logic. Every model call goes through `llm.py`; every legal
fact comes from `kb.json`; every safety decision is made by `checks.py`.

```
Browser  (templates/index.html + static/app.js + static/style.css)
   │  JSON / multipart
   ▼
app.py  ──►  jobs.py            (archive request + response per task)
   │
   ▼
services/chat_service.py      services/summary_service.py
services/timeline_service.py  services/notice_service.py
   │
   ├─► prompts.py   + schemas.py     (what to ask, what shape to expect)
   ├─► kb.py        ──► kb.json      (the only source of legal content)
   ├─► llm.py       ──► Groq / Gemini / custom / fake provider
   ├─► checks.py                     (verify, remove, escalate, limit)
   ├─► docs.py                       (extract + chunk, in memory)
   └─► store.py                      (in-memory sessions)
```

## Module responsibilities

| Module | Responsibility | Never does |
|---|---|---|
| `app.py` | HTTP validation, status codes, error shape, job archiving | Business logic, prompt building |
| `config.py` | Env vars, thresholds, upload limits, provider config | Legal content |
| `llm.py` | Provider order, retries, JSON repair, exceptions | Know what a "deposit" is |
| `prompts.py` | Prompt templates, `{{PLACEHOLDER}}` rendering | Contain legal content |
| `schemas.py` | JSON Schema for every model output | — |
| `kb.py` / `kb.json` | Load, validate, render, allowlist legal rules | Fetch from the internet |
| `checks.py` | Deterministic safety: citations, quotes, dates, escalation, injection, question limit | Call a model or the network |
| `docs.py` | Upload validation, text extraction, chunking | Write to disk |
| `store.py` | Sessions, history, documents, caches | Persist anything |
| `jobs.py` | Write one folder per task under `jobs/<date>/<job_id>/` | Store raw uploaded bytes |
| `services/*` | Compose the above into one response per endpoint | Talk HTTP |

Rules that keep this honest:

- **No global mutable state** outside `store.py` (sessions) and `llm.py` (only the
  test responder used by unit tests).
- **No provider-specific code** outside `llm.py`. Swapping models is a `.env`
  change.
- **No legal text in code or prompts.** It lives in `kb.json`, and a test asserts
  that `prompts.py` mentions no Act or section.

## Chat request lifecycle

1. `app.py` validates `session_id` (must be a UUID with a live session) and
   `message` (≤ 2,000 characters).
2. `chat_service` builds the system prompt: rules + today's date + the KB block
   for the active domain + the case file + compact document summaries, then the
   last 10 turns and the new message.
3. `llm.complete_json` asks for JSON matching `CHAT_SCHEMA`. Invalid output is
   repaired once, then raises `LLMBadOutput`.
4. `checks.scan_citations` removes any sentence citing a section, Act, case or
   code that is not in the KB allowlist.
5. `checks.limit_questions` keeps only the first question, so the reply cannot
   turn into an interrogation.
6. `case_updates` are merged into the case file: unknown keys ignored, dates
   parsed to ISO by code, amounts and booleans coerced.
7. `checks.escalate` computes `none | advise | urgent` from code rules; the model
   can raise the level but never lower it.
8. Turns are appended to history; the response is archived to `jobs/` and
   returned.

## Document pipeline (map-reduce)

```
upload ──► docs.validate_upload ──► docs.extract_text ──► docs.chunk_text
                                                              │
                          ┌───────────────────────────────────┘
                          ▼
        for each chunk: SUMMARY_SCHEMA  (temperature 0)
                          │
                          ▼
     checks.verify_items against the FULL document text
                  (fabricated quotes are dropped + counted)
                          │
                          ▼
     code merges lists, de-duplicates, takes the first verified
     arbitration quote, then fills date_iso with dateutil
                          │
                          ▼
     more than one chunk? one SUMMARY_MERGE call for plain_summary
```

The same pattern drives the timeline, except that chat-sourced events are verified
against the user's own messages and de-duplicated against document events
(`source: "both"` when they collide).

## The case file

Every session carries one mutable case file: `domain`, `language`,
`facts.common`, `facts.deposit`, `facts.refund`, `evidence`, `doc_ids`,
`missing_info`, `flags`, `escalation`. It is the single source of truth for the
conversation, and it is what the UI's **Case file** tab renders.

## AI vs code

The split is the whole design. Anything that can be wrong in a way a user would
not notice is done by code.

| Task | Done by | Why |
|---|---|---|
| Understand a messy story, extract facts | LLM | Language understanding |
| Choose which rules apply | LLM selects KB ids | — |
| Supply the actual rule text | **KB only** | Prevents invented law |
| Parse and order dates | Code (`dateutil`) | Deterministic |
| Prove a quote exists in the source | Code | A model cannot verify itself |
| Delete unverified legal references | Code (regex vs allowlist) | Safety net |
| Decide "see a lawyer" | Code rules | Auditable, testable |
| Keep the reply to one question | Code | A prompt alone was not reliable |
| Merge chunks, de-duplicate, sort | Code | Cheaper and deterministic |
| Wording, plain summaries, notice drafting | LLM | Writing quality |

## Sessions, storage and privacy

- Sessions live in a dict in `store.py`, expire after 2 hours of inactivity, and
  are capped at 200. Restarting the process clears everything. Run with a single
  worker.
- Uploaded files are parsed from bytes in memory; the original bytes are never
  written anywhere.
- `jobs.py` archives each task to `jobs/<YYYY-MM-DD>/<job_id>/` containing
  `request.json`, `response.json`, `meta.json` and, for uploads, `document.txt`.
  The folder is gitignored. Set `JOBS_ARCHIVE=0` to switch it off.
- Console logs carry route, status, provider, model, latency, token counts and
  flags — never message or document text.

## Why there is no database

A session is a conversation. Persisting it would create a store of personal
disputes that has to be secured, backed up and eventually deleted under a privacy
regime. For a demo that is pure risk with no benefit. The job archive exists for
debugging and is explicitly local and disposable.
