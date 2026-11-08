# BUILD STEPS (prompts for DeepSeek in VS Code chat)

## How to use
1. Put the whole plan folder in your project (`PROJECT_CONTEXT.md` at the root, the rest in `docs/`).
2. For **every** step, attach `PROJECT_CONTEXT.md` plus the spec files listed in that step. Attach only those files to save context.
3. Paste the prompt. Generate one step at a time. Do not start the next step until the acceptance checks pass.
4. If the model drifts from the spec, paste: "You deviated from <file>. Fix only the deviation. Do not change anything else."
5. Commit after each step (`git commit -m "step N"`).
6. Log every AI mistake you notice in `docs/AI_USAGE_LOG` (table in `SUBMISSION_CHECKLIST.md`). You need at least one for the submission.
7. If your extension supports a rules file, paste `PROJECT_CONTEXT.md` into it once.

Common footer to add to every prompt:
> Output complete files only. No TODOs. End with: files changed, how to run, how to test, and "Assumptions" (max 3 lines).

---

## Step 0 - Skeleton and config
**Attach:** PROJECT_CONTEXT.md, ARCHITECTURE.md, API_SPEC.md, LLM_LAYER.md

**Prompt:**
```
Create the project skeleton exactly as in ARCHITECTURE.md (empty files for modules not yet built).
Implement now: requirements.txt (flask, openai, pdfplumber, python-docx, python-dateutil,
python-dotenv, jsonschema, pytest), .env.example (copy from LLM_LAYER.md), .gitignore
(.env, .venv, __pycache__; do NOT ignore outputs/), config.py (env loading, constants:
MAX_UPLOAD_MB, LONG_DOC_CHAR_THRESHOLD, LAWYER_ADVISE_DEPOSIT_INR=500000, session TTL 2h,
max sessions 200), store.py (in-memory sessions per ARCHITECTURE.md with TTL cleanup),
and app.py with an app factory, GET /api/health, POST /api/session and a central JSON error
handler using the error codes in API_SPEC.md. Do not implement other endpoints.
```
**Accept:** `python app.py` starts; `/api/health` returns JSON; `/api/session` returns a uuid; unknown route returns the JSON error shape.

## Step 1 - LLM layer
**Attach:** PROJECT_CONTEXT.md, LLM_LAYER.md

**Prompt:**
```
Implement llm.py exactly as specified in LLM_LAYER.md: provider order from env, OpenAI-compatible
client, retries/backoff, provider fallback, complete(), complete_json() with fence stripping,
jsonschema validation and one repair retry, a fake provider reading tests/fixtures/fake_llm.json,
custom exceptions (LLMRateLimited, LLMUnavailable, LLMBadOutput), and safe logging (no content,
no keys). Also write tests/test_llm.py using mocks and the fake provider.
```
**Accept:** `pytest tests/test_llm.py` passes; with a real key in `.env`, a tiny script returns a JSON answer; swapping `LLM_PROVIDER_ORDER` works without code changes.

## Step 2 - Knowledge base
**Attach:** PROJECT_CONTEXT.md, KNOWLEDGE_BASE.md

**Prompt:**
```
Create kb.json from the starter entries in KNOWLEDGE_BASE.md (copy the JSON array exactly) and
implement kb.py: load_kb() with validation (unique ids, required fields, domain values), get(id),
ids(), render_for_prompt(domain) returning compact JSON of id/title/plain/rule/verified,
and allowlist() returning a normalized set of every allowed_refs item. Fail fast at startup on an
invalid file. Write tests/test_kb.py.
```
**Accept:** tests pass; duplicate id test fails as expected; then YOU manually verify each entry against official sources and flip `verified` honestly.

## Step 3 - Safety checks
**Attach:** PROJECT_CONTEXT.md, SAFETY_AND_CHECKS.md, KNOWLEDGE_BASE.md

**Prompt:**
```
Implement checks.py exactly as in SAFETY_AND_CHECKS.md: normalize, scan_citations,
warn_unverified_numbers, verify_quote, verify_items, parse_date, escalate, scan_injection.
Pure functions, no network, no LLM calls. Then write tests/test_checks.py covering every case in
section 9 of that file, plus edge cases (Devanagari sentence end "।", empty input, very long input).
```
**Accept:** `pytest tests/test_checks.py` passes; "Section 420 IPC" is removed; escalation level never decreases.

## Step 4 - Document processing
**Attach:** PROJECT_CONTEXT.md, DOCUMENT_PROCESSING.md

**Prompt:**
```
Implement docs.py exactly as in DOCUMENT_PROCESSING.md: validate_upload, extract_text (PDF via
pdfplumber, DOCX via python-docx including tables, TXT), chunk_text, and the custom errors mapped
to the API error codes. Work from bytes in memory only. In tests/test_docs.py create tiny sample
PDF/DOCX/TXT files programmatically (python-docx for DOCX; for PDF use a small pre-built fixture
bytes or reportlab only if added to requirements - prefer a fixture) and test size limits, magic
byte mismatch, scanned-PDF rejection, chunk size and overlap.
```
**Accept:** tests pass; a 6-page sample text PDF extracts with `[Page n]` markers.

## Step 5 - Prompts and schemas
**Attach:** PROJECT_CONTEXT.md, PROMPTS.md, API_SPEC.md, ARCHITECTURE.md

**Prompt:**
```
Implement prompts.py (all prompt templates from PROMPTS.md with {{PLACEHOLDER}} rendering via a
render(template, **values) helper that raises on missing values) and schemas.py (JSON Schemas:
CHAT_SCHEMA, SUMMARY_SCHEMA, TIMELINE_SCHEMA, NOTICE_SCHEMA, SUMMARY_MERGE_SCHEMA) matching the
fields in PROMPTS.md and API_SPEC.md. Do not add any legal content to prompts. Write a test that
renders each prompt with dummy values and validates one sample object per schema.
```
**Accept:** tests pass; no section numbers or Act names appear anywhere in `prompts.py`.

## Step 6 - Services
**Attach:** PROJECT_CONTEXT.md, ARCHITECTURE.md, PROMPTS.md, DOCUMENT_PROCESSING.md, SAFETY_AND_CHECKS.md

**Prompt:**
```
Implement services/summary_service.py, services/timeline_service.py, services/chat_service.py and
services/notice_service.py following the flows in DOCUMENT_PROCESSING.md (map-reduce, quote
verification, dedupe, sorting), the chat lifecycle in ARCHITECTURE.md, and the checks in
SAFETY_AND_CHECKS.md. Each service is a plain function taking a session and returning the exact
response dict from API_SPEC.md. Cache summary/timeline per (doc_id, task). Services call llm.py,
kb.py, checks.py, docs.py and prompts.py only. Write service tests with the fake LLM provider,
including a case where the fake model returns a fabricated quote (must be dropped) and a reply
containing an unlisted section number (must be removed).
```
**Accept:** service tests pass with the fake LLM; with a real key, a manual call for D1 returns a sensible reply.

## Step 7 - API routes
**Attach:** PROJECT_CONTEXT.md, API_SPEC.md

**Prompt:**
```
Extend app.py with POST /api/chat, POST /api/upload (multipart), POST /api/summarize,
POST /api/timeline, POST /api/notice, GET /api/case/<session_id> and GET /api/kb (id, title,
verified only). Routes only validate input, call a service and return JSON per API_SPEC.md.
Enforce limits (message length, upload size) and return the specified error codes. Write
tests/test_api.py with Flask's test client and the fake LLM.
```
**Accept:** every endpoint tested incl. error paths; no stack traces in responses.

## Step 8 - Frontend
**Attach:** PROJECT_CONTEXT.md, FRONTEND_SPEC.md, API_SPEC.md

**Prompt:**
```
Build templates/index.html, static/app.js and static/style.css exactly per FRONTEND_SPEC.md:
chat, upload, tabs (Documents, Summary, Timeline, Notice, Case file), escalation banner, KB
chips, flags notes, loading and error states, light/dark via CSS variables, accessible, mobile
friendly, vanilla JS, no CDN. Never insert model output with innerHTML without escaping.
```
**Accept:** full flow works in a browser on desktop and phone width: chat, upload a sample doc, summary shows the arbitration card, timeline shows source quotes.

## Step 9 - Eval harness and test cases
**Attach:** PROJECT_CONTEXT.md, TESTING_AND_EVAL.md, API_SPEC.md

**Prompt:**
```
Create tests/cases.json with the 12 cases in TESTING_AND_EVAL.md (realistic synthetic messages
in the right languages) and synthetic documents in tests/docs/ (rental agreement with an
arbitration clause, invoice + warranty text, T&C with a no-refund clause, and a document
containing a prompt-injection sentence). Implement scripts/run_eval.py per the spec: play each
case, call all endpoints, write unedited raw outputs to outputs/run_<timestamp>/<case_id>/,
evaluate the expect rules, and write report.md with per-case results and the metrics table.
Support --provider and --url flags. Never modify model outputs.
```
**Accept:** a full run completes with a real key; `report.md` exists; at least some failures are visible and kept.

## Step 10 - Run, review, fix, document
**Attach:** PROJECT_CONTEXT.md, TESTING_AND_EVAL.md, SUBMISSION_CHECKLIST.md

**Prompt (after you have a real eval run):**
```
Here is outputs/<run>/report.md (pasted below). List the failures by root cause (prompt, check,
KB gap, model limit). Propose the smallest fixes. Do not change specs; list any spec change
separately. Then update only the files needed for the fixes.
```
Then: fill `docs/FAILURES.md`, re-run eval, keep the first run as evidence of honest failures, and write the 2-page PDF using `SUBMISSION_CHECKLIST.md`.

---

## Reusable prompts

**Review against spec**
```
Review <file> against <spec file>. List every mismatch (field names, status codes, schemas,
missing checks). Do not rewrite the file; give a numbered list of exact fixes.
```

**Debug**
```
Error: <paste traceback>. Relevant file: <file>. Explain the root cause in two sentences, then
give the minimal patch as a diff. Do not refactor.
```

**Security pass**
```
Audit the repo for: secrets in code, logging of user text, unescaped HTML insertion, path use of
filenames, missing size limits, error messages that leak internals. Report findings with file and
line; propose minimal fixes.
```

**Anti-hallucination pass (manual too)**
```
Search all prompts, services and the UI for any legal statement (section numbers, Act names, case
names, deadlines, fees, helpline numbers) that does not come from kb.json. List each occurrence.
```
