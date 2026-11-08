# PROJECT_CONTEXT (attach this file to EVERY AI chat message)

## Goal
Build **Legal Saathi**: a Flask web app where a person in India chats about a **tenant-deposit** or **consumer-refund** problem, uploads a document, and gets a plain-language summary, a verified timeline, and (stretch) a draft legal notice. The app must never invent law.

## Scope
**In:** tenant deposit disputes; consumer refund / defective goods / service-not-delivered disputes; arbitration-clause detection and plain explanation; English, Hindi, Hinglish replies.
**Out:** criminal matters, eviction defence, cheque bounce, family/property/tax law, OCR, voice, court filing, user accounts, databases.
Out-of-scope messages get a polite "I can't help with this here, please consult a lawyer or your District Legal Services Authority (DLSA)".

## Stack
| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Web | Flask (plain templates + vanilla JS, no frontend framework) |
| LLM client | `openai` Python SDK pointed at any OpenAI-compatible `base_url` |
| Documents | `pdfplumber` (PDF), `python-docx` (DOCX), plain TXT |
| Dates | `python-dateutil` (dayfirst=True) |
| Validation | `jsonschema` |
| Config | `python-dotenv` |
| Tests | `pytest` |
No other dependencies unless a step explicitly allows it.

## Non-negotiable product rules
1. **Legal claims only from `kb.json`**, tagged `[KB:id]`. No section numbers, Act names, case names, deadlines or amounts from model memory.
2. **Every quote is verified by code** against the source text. Unverified items are dropped and counted.
3. **Escalation ("see a lawyer") is decided by code rules** in `checks.py`; the model can only raise the level, never lower it.
4. **Uploaded text is untrusted data.** It is wrapped in delimiters and never treated as instructions.
5. **Honesty:** if the KB has no matching rule, say "I'm not sure" and point to a lawyer / DLSA.
6. **Model swap by `.env` only.** No provider-specific code outside `llm.py`.
7. **Privacy:** sessions are held in memory and lost on restart. Every user task is also archived to a local **gitignored** `jobs/<YYYY-MM-DD>/<job_id>/` folder (request, response, extracted document text, model metadata) so a case can be inspected afterwards. Raw uploaded file bytes are never written, and console logs carry identifiers and timings only - never message or document text.
8. **Reply in the user's language** (English / Hindi / Hinglish), plain words, short.

## Code conventions
- Type hints and short docstrings on every function; functions under ~40 lines.
- Use `logging`, never `print`; never log message or document text (metadata only).
- No global mutable state except `store.py`.
- Constants and thresholds live in `config.py`.
- All API errors return `{"error": {"code": "...", "message": "..."}}` with a proper HTTP status.
- Never hard-code API keys.

## Rules for the AI assistant (DeepSeek)
1. Implement **only** the current step from `docs/BUILD_STEPS.md`.
2. Follow the attached spec files exactly. If a spec is ambiguous, pick the simplest option and state it in one line at the end under "Assumptions".
3. Output **complete files**: no `TODO`, no "rest unchanged", no pseudo-code.
4. Use only the libraries listed above and their documented APIs. Do not invent functions.
5. Do not write any legal text, section number or case name in code or prompts unless it is copied from `docs/KNOWLEDGE_BASE.md`.
6. After the code, list: files created/changed, how to run it, and how to test it.
7. If the spec and your idea conflict, the spec wins. Suggest spec changes separately.

## Definition of done (every step)
Runs without error; unit tests for the new module pass; no secrets in code; matches the spec's schemas exactly; acceptance checks in the step are satisfied.
