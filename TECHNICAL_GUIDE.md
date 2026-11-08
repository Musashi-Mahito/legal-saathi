# Legal Saathi — Technical Guide & Architecture Manual

A conversational legal information assistant for ordinary citizens in India navigating **tenant security-deposit disputes** and **consumer refund disputes**, built with Flask, vanilla JavaScript, and OpenAI-compatible LLMs.

---

## Table of Contents
1. [Prerequisites & System Requirements](#1-prerequisites--system-requirements)
2. [Configuration & Environment (.env)](#2-configuration--environment-env)
3. [Quick Start & Execution Guide](#3-quick-start--execution-guide)
   - [Method A: Fast Setup with uv (Recommended)](#method-a-fast-setup-with-uv-recommended)
   - [Method B: Standard Setup with venv + pip](#method-b-standard-setup-with-venv--pip)
4. [Pushing to GitHub](#4-pushing-to-github)
5. [Verification & Evaluation Harness](#5-verification--evaluation-harness)
6. [Troubleshooting Common Runtime Issues](#6-troubleshooting-common-runtime-issues)
7. [System Architecture & Design Philosophy](#7-system-architecture--design-philosophy)
8. [Module-by-Module Responsibilities](#8-module-by-module-responsibilities)
9. [The Anti-Hallucination Safety Model (8 Core Guarantees)](#9-the-anti-hallucination-safety-model-8-core-guarantees)
10. [Data Processing Pipelines](#10-data-processing-pipelines)
    - [Chat Turn Pipeline](#chat-turn-pipeline)
    - [Document Map-Reduce Pipeline](#document-map-reduce-pipeline)
    - [Chronological Timeline Grounding](#chronological-timeline-grounding)
    - [Legal Notice Draft Generation](#legal-notice-draft-generation)
11. [Knowledge Base & The Arbitration Problem](#11-knowledge-base--the-arbitration-problem)
12. [In-Memory State & Privacy Architecture](#12-in-memory-state--privacy-architecture)
13. [API Specification Summary](#13-api-specification-summary)

---

## 1. Prerequisites & System Requirements

- **Operating System**: macOS, Linux, or Windows.
- **Python**: Version `3.11` or higher.
- **Supported Document Uploads**: Text-based PDF, DOCX, TXT (up to 5 MB).
- **OCR / Scanned Files**: Not supported (scanned PDFs without a text layer are safely rejected with a clear message).
- **Supported Languages**: English, Hindi, Hinglish.

---

## 2. Configuration & Environment (.env)

All runtime parameters are read from a root `.env` file via `config.py`. Copy the provided `.env.example` template:

```bash
cp .env.example .env
```

### Available Configuration Modes

#### Mode 1: Offline Demo (Zero API Key Required)
Runs completely offline using canned fixture responses in `tests/fixtures/fake_llm.json`. Ideal for verifying UI, safety checks, and test suites without internet access or API credits.
```ini
LLM_PROVIDER_ORDER=fake
```

#### Mode 2: Free-Tier Cloud LLMs (Groq & Google Gemini)
```ini
LLM_PROVIDER_ORDER=groq,gemini

# Groq Configuration (Ultra-fast inference)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=qwen/qwen3.8-27b

# Google Gemini Configuration (Fallback & Large Documents)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL=gemini-2.5-flash
```

#### Mode 3: Custom OpenAI-Compatible Endpoint (Local Ollama / vLLM / OpenAI)
```ini
LLM_PROVIDER_ORDER=custom
CUSTOM_API_KEY=your_key_or_empty
CUSTOM_BASE_URL=http://localhost:11434/v1
CUSTOM_MODEL=llama3.1
```

### Additional Settings
| Setting | Default | Description |
|---|---|---|
| `LONG_DOC_PROVIDER` | `gemini` | Preferred provider for inputs exceeding the character threshold. |
| `LONG_DOC_CHAR_THRESHOLD` | `12000` | Character cut-off triggering large-context routing. |
| `LLM_TIMEOUT_SECONDS` | `45` | Maximum wait duration before timeout and retry. |
| `MAX_UPLOAD_MB` | `5` | Maximum upload size for PDF/DOCX/TXT files. |
| `JOBS_ARCHIVE` | `1` | `1` archives completed turns to `jobs/<date>/<id>/`; `0` disables. |
| `FLASK_HOST` / `FLASK_PORT` | `127.0.0.1` / `5000` | Web server host and port binding. |

---

## 3. Quick Start & Execution Guide

### Method A: Fast Setup with uv (Recommended)

[uv](https://docs.astral.sh/uv/) resolves dependencies directly from `uv.lock` and builds a virtual environment automatically.

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Start the web application
uv run app.py

# 3. Run the unit test suite
uv run pytest -q

# 4. Run the 12-case benchmark evaluation
uv run python scripts/run_eval.py
```

### Method B: Standard Setup with venv + pip

```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 2. Install pinned dependencies
pip install -r requirements.txt

# 3. Start the Flask application
python app.py

# 4. Open in browser
# Navigate to: http://127.0.0.1:5000
```

---

## 4. Pushing to GitHub

The repository is configured to push to:
`https://github.com/Musashi-Mahito/legal-saathi.git`

To push the codebase from your terminal:

```bash
# 1. Authenticate with GitHub CLI
gh auth login

# 2. Ensure the repository exists on GitHub
# Create it at https://github.com/new with name: legal-saathi (leave empty)

# 3. Push branch to GitHub
git branch -M main
git push -u origin main
```

*(Note: Sensitive data such as `.env` and `jobs/` are excluded by `.gitignore` and will never be committed or pushed).*

---

## 5. Verification & Evaluation Harness

### 1. Offline Unit Tests (143 Tests)
Run offline without internet access or API keys using canned fixtures:
```bash
pytest -q
```
Expected output:
```text
143 passed in ~1.5s
```

Test coverage includes:
- `test_checks.py`: Regex-based citation removal, quote matching, date parsing, and monotonic escalation.
- `test_docs.py`: Text extraction, magic bytes validation, and scanned-PDF detection.
- `test_services.py`: Map-reduce chunking, timeline deduplication, and draft notice generation.
- `test_llm.py`: Provider fallback, exponential backoff, and JSON repair retries.
- `test_kb.py`: Startup validation of knowledge base integrity.
- `test_prompts.py`: Verification that prompt templates contain zero invented legal sections.

### 2. End-to-End Evaluation Suite
Executes 12 dispute cases (D1-D4 tenant deposit, R1-R4 consumer refund, E1-E4 edge/adversarial cases) and outputs Markdown reports and logs to `outputs/`:
```bash
python scripts/run_eval.py                  # Uses active .env configuration
python scripts/run_eval.py --provider groq  # Evaluates explicitly against Groq
```

---

## 6. Troubleshooting Common Runtime Issues

| Symptom | Root Cause | Solution |
|---|---|---|
| **Chat displays: *"I'm having trouble right now"* & HTTP 404 in logs** | The LLM provider decommissioned or renamed the model ID in `GROQ_MODEL` or `GEMINI_MODEL`. | Query your key's available models and update the model identifier in `.env`. |
| **HTTP 401 / 403 in logs** | API key is missing or invalid. | Verify `GROQ_API_KEY` or `GEMINI_API_KEY` in `.env` without surrounding quotes. |
| **HTTP 429 in logs (Rate Limited)** | Free tier tokens-per-minute threshold reached. | The application automatically backs off and retries, or falls back to the next provider in `LLM_PROVIDER_ORDER`. |
| **Port 5000 in use (`OSError`)** | AirPlay receiver or another service is occupying port 5000. | Set `FLASK_PORT=5001` in `.env`. |
| **Upload returns HTTP 422: `scanned_pdf_unsupported`** | The uploaded PDF is a scanned image or photo lacking a digital text layer. | Provide a digitally created PDF, a DOCX file, or paste text in plain `.txt` format. |

---

## 7. System Architecture & Design Philosophy

The core architectural tenet of Legal Saathi is:
> **Anything that can be wrong in a way a user would not notice is verified or enforced by deterministic Python code.**

```
┌────────────────────────────────────────────────────────────────────────┐
│             Browser UI (Vanilla JS + HTML5 + Responsive CSS)            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP JSON / Multipart
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                app.py (HTTP Validation & Error Shaping)                │
└─────────┬─────────────────────────┬──────────────────────────┬─────────┘
          │                         │                          │
          ▼                         ▼                          ▼
   services/chat_service     services/summary_service   services/timeline_service
   services/notice_service
          │
          ├────────► prompts.py & schemas.py (Structured JSON schema contracts)
          ├────────► kb.py ──► kb.json (The ONLY source of statutory law)
          ├────────► llm.py ──► Providers (Groq / Gemini / Custom / Fake)
          ├────────► checks.py (Deterministic regex, verification & escalation)
          ├────────► docs.py (In-memory text extraction & chunking)
          ├────────► store.py (In-memory session & case file state)
          └────────► jobs.py (Audit archiving to jobs/<date>/<id>/)
```

### Division of Responsibility
| Task | Execution Engine | Rationale |
|---|---|---|
| Natural language interpretation | LLM | Comprehends conversational nuances in English/Hindi/Hinglish. |
| Statutory law & legal rules | **Knowledge Base Only** | Eliminates invented sections, acts, or cases. |
| Citation verification | **Deterministic Code** | Removes unapproved section numbers and acts via regex. |
| Document quote verification | **Deterministic Code** | Checks substring existence in source text (NFKC normalized). |
| Chronological ordering | **Deterministic Code** | Parses dates to ISO format using `dateutil` with `dayfirst=True`. |
| Escalation ("Talk to a lawyer") | **Deterministic Code** | Code-enforced rules; the LLM can raise urgency, never lower it. |
| Single-question limit | **Deterministic Code** | Drops extra questions to prevent interrogating the user. |

---

## 8. Module-by-Module Responsibilities

- **`app.py`**: Flask factory, input validation, and route mapping. Returns consistent error payloads: `{"error": {"code": "...", "message": "..."}}`. Never contains business or legal logic.
- **`config.py`**: Reads `.env` parameters and centralizes limits (`MAX_UPLOAD_MB=5`, `MAX_MESSAGE_CHARS=2000`).
- **`kb.json` & `kb.py`**: Contains 15 validated legal rules. Validates on startup; crashes immediately on duplicate IDs, missing fields, or schema errors to prevent fallback to memory-based law.
- **`checks.py`**: Pure, deterministic safety library without network or LLM dependencies. Implements citation allowlisting, verbatim quote verification, injection detection, and date parsing.
- **`llm.py`**: Single gateway handling all OpenAI-compatible completions, provider failover, JSON validation, and single-turn automated JSON repair.
- **`docs.py`**: Parses in-memory buffers for PDF (`pdfplumber`), DOCX (`python-docx`), and TXT. Evaluates character densities to reject image-only scans.
- **`store.py`**: Manages transient in-memory `Session`, `Document`, and `CaseFile` objects. Sessions expire after 2 hours.
- **`jobs.py`**: Archives requests, responses, and execution metadata locally to `jobs/<YYYY-MM-DD>/<job_id>/` for auditing. Raw uploaded bytes are never stored.

---

## 9. The Anti-Hallucination Safety Model (8 Core Guarantees)

1. **Grounded Legal Knowledge Base**: Legal claims are derived solely from `kb.json` and tagged as `[KB:id]`.
2. **Sentence-Level Citation Allowlisting (`checks.scan_citations`)**: Replies are split into sentences. Any sentence referencing an Act, Section, Order, Rule, Case Name, or Penal Code (`IPC`, `BNS`, `CrPC`) not explicitly included in the knowledge base `allowed_refs` is completely excised and replaced with a notice:
   > *"I removed a part of this answer because I could not verify it. Please check with a lawyer."*
3. **Verifiable Quotation Validation (`checks.verify_quote`)**: Summary points and timeline milestones must provide a verbatim quote from source documents. Quotes are normalized (NFKC, lowercased, straight quotes). If a quote is absent or shorter than 8 characters, the item is dropped and counted under `dropped_unverified`.
4. **Monotonic Code-Decided Escalation (`checks.escalate`)**: Escalation levels (`none`, `advise`, `urgent`) are decided by code rules (e.g. keywords like `police`, `fir`, `tala`, `lock changed`, or limitation periods exceeding 24 months). The LLM can raise the escalation level, but code strictly prevents it from ever lowering it.
5. **Prompt Injection Containment**: Document text is wrapped in `<document id="...">` delimiters and treated as untrusted data. Prompts forbid treating document text as instructions, and `checks.scan_injection` flags prompt override attempts.
6. **Single-Question Rule (`checks.limit_questions`)**: Detects and drops all but the first interrogative question in assistant answers to avoid overwhelming the user.
7. **Fail-Safe Degradation**: If LLM providers fail or output invalid schemas, the chat API safely returns HTTP 200 with fallback assistance guidance rather than crashing.
8. **Currency & Duration Sanity Checks (`checks.warn_unverified_numbers`)**: Verifies that rupee amounts and time durations mentioned by the LLM exist within the conversation context, documents, or knowledge base.

---

## 10. Data Processing Pipelines

### Chat Turn Pipeline
1. `app.py` validates `session_id` and message length ($\le 2,000$ chars).
2. `chat_service.py` builds the prompt using today's ISO date, the domain-filtered KB slice, the active case file, and document summaries.
3. `llm.complete_json` requests a completion matching `CHAT_SCHEMA` (retrying once with repair instructions if schema validation fails).
4. `checks.scan_citations` purges unallowlisted legal references.
5. `checks.limit_questions` removes extraneous questions.
6. `_merge_facts` and `_merge_evidence` update the session's case file. Coerces numbers (including Indian denominations like `lakh` and `crore`), parses dates to ISO, and coerces Hindi affirmative/negative words.
7. `checks.escalate` recalculates urgency level monotonically.
8. History is updated, turn metadata is archived to `jobs/`, and the payload is returned.

### Document Map-Reduce Pipeline
1. Upload validated by extension, size, and magic bytes; text extracted via `docs.py`.
2. Extracted text divided into overlapping chunks (~4,000 chars with 400 chars overlap).
3. **Map Phase**: Each chunk evaluated via `SUMMARY_SCHEMA` with temperature 0.0.
4. **Verification**: Extracted parties, amounts, dates, and clauses are verified against the full source document text using `checks.verify_items()`.
5. **Reduce Phase**: Verified items are merged and de-duplicated by code. If multiple chunks exist, a secondary pass synthesizes a consolidated `plain_summary`.

### Chronological Timeline Grounding
1. Extracts dated events from both uploaded documents and the user's conversational messages.
2. Events are cross-referenced: document quotes must exist in document text; chat quotes must exist in user messages.
3. Dates parsed to ISO format (`YYYY-MM-DD`). Events with ambiguous date strings (day $\le 12$ and month $\le 12$) have their confidence downgraded to `low`.
4. Overlapping milestones occurring in both chat and documents are merged with `source: "both"`.

### Legal Notice Draft Generation
1. Verifies that the dispute domain is resolved (`deposit` or `refund`).
2. Synthesizes a formal demand notice following Indian legal notice conventions.
3. Uses bracketed tokens (e.g. `[YOUR FULL NAME]`, `[LANDLORD'S ADDRESS]`) for missing facts.
4. `notice_service.py` extracts all bracketed tokens via regex into `missing_placeholders` for UI highlighting.

---

## 11. Knowledge Base & The Arbitration Problem

The knowledge base (`kb.json`) contains 15 curated legal rules:

### Arbitration Clause Protections
- **`arb_consumer_no_bar`**: Cites the Supreme Court landmark ruling in *Emaar MGF Land Ltd v. Aftab Singh (2018)*, clarifying that arbitration clauses in agreements do not prevent a consumer from filing a complaint before the Consumer Commission.
- **`arb_clause_basics`**: Cites the Arbitration and Conciliation Act 1996, highlighting that under Section 12(5) and the Seventh Schedule, unilateral appointment of a sole arbitrator by one interested party is invalid.
- **`arb_notice_urgent`**: Warns users that receiving an official arbitration notice requires urgent legal consultation due to strict statutory timelines.

---

## 12. In-Memory State & Privacy Architecture

```
Case File (In-Memory)
├── session_id: UUID
├── domain: deposit | refund | unknown | out_of_scope
├── language: en | hi | hinglish
├── facts:
│   ├── common: other_party_name, amount_inr, state_or_city, cause_of_action_date
│   ├── deposit: monthly_rent_inr, deposit_paid_inr, move_out_date, deduction_claimed_inr
│   └── refund: item_or_service, seller_or_platform, purchase_date, amount_paid_inr
├── evidence: [{type, description, have}]
├── missing_info: [list of missing facts]
├── flags: [diagnostic & safety flags]
└── escalation: {level: none | advise | urgent, reasons, resources}
```

- **In-Memory Volatility**: All sessions are held in RAM (`store.py`) with a 2-hour inactivity timeout. Server restarts purge all data.
- **Zero Raw File Storage**: Uploaded PDF/DOCX bytes are processed entirely in memory; raw binary files are never saved to disk.
- **Disposable Audit Trails**: If enabled, `jobs.py` stores execution metadata, structured payloads, and extracted text under `jobs/<YYYY-MM-DD>/<job_id>/`. This folder is excluded by `.gitignore` and can be deleted at any time.

---

## 13. API Specification Summary

All endpoints return JSON and use standard error formatting: `{"error": {"code": "...", "message": "..."}}`.

| Route | Method | Payload / Parameters | Response |
|---|---|---|---|
| `/api/health` | `GET` | None | `{"status": "ok", "providers": [...], "models": {...}}` |
| `/api/session` | `POST` | None | `201 {"session_id": "UUID"}` |
| `/api/chat` | `POST` | `{"session_id": "...", "message": "..."}` | `{"reply": "...", "domain": "...", "case_file": {...}, "kb_used": [...]}` |
| `/api/upload` | `POST` | Multipart: `session_id`, `file` | `201 {"doc_id": "...", "filename": "...", "pages": N, "chars": N}` |
| `/api/summarize` | `POST` | `{"session_id": "...", "doc_id": "..."}` | `{"summary": {parties, amounts, dates, arbitration_clause}, "dropped_unverified": N}` |
| `/api/timeline` | `POST` | `{"session_id": "...", "doc_ids": [...]}` | `{"events": [{date_iso, event, quote, source, confidence}], "undated": [...]}` |
| `/api/notice` | `POST` | `{"session_id": "...", "doc_ids": [...]}` | `{"notice_markdown": "...", "missing_placeholders": [...]}` |
| `/api/case/<id>` | `GET` | URL parameter: `session_id` | Full `case_file` dictionary. |
| `/api/kb` | `GET` | None | All verified knowledge base entries for UI source chips. |

