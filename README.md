# Legal Saathi

A conversational assistant that helps an ordinary person in India act on two everyday problems:

1. **Tenant security-deposit disputes** (landlord will not return or unfairly deducts a deposit)
2. **Consumer refund disputes** (refund never came, defective product, service not delivered)

Built with Flask + Python and a **swappable, free, OpenAI-compatible LLM** (Groq / Gemini Flash / any custom endpoint).

> Legal Saathi gives information, not legal advice. It is not a lawyer, says so, and tells the user when they need a real one.

## Documentation

Full documentation for review and submission is in **[documentation/](documentation/README.md)**.
Start there: problem and scope, architecture, safety model, API reference, setup
and portability, verification results, limitations, and the AI usage log.

## What it does

| Feature | Endpoint | Summary |
|---|---|---|
| Chat | `POST /api/chat` | Plain-language conversation in the user's language; collects facts into a "case file"; explains options using only a verified knowledge base |
| Upload | `POST /api/upload` | Accepts PDF / DOCX / TXT (rental agreement, invoice, notice), extracts text |
| Summary | `POST /api/summarize` | Structured summary: parties, amounts, dates, key clauses, **arbitration-clause check**, red flags |
| Timeline | `POST /api/timeline` | Dated events built from the document and the chat; every event carries a verified quote |
| Draft notice (stretch) | `POST /api/notice` | Draft legal notice with `[PLACEHOLDERS]` for missing facts |

## Using the app

Open `http://127.0.0.1:5000`. The page is a single screen with two columns
(single column on a phone):

- **Chat (left)** – describe the problem in English, Hindi or Hinglish. The
  answer shows small "Source:" chips for each `[KB:id]` it used; chips with a
  dashed border are KB entries a human has not verified yet. Notes appear under
  an answer when a legal reference was removed or a number could not be checked.
- **Workspace (right)** – five tabs:
  - **Documents** – upload a PDF, DOCX or TXT (5 MB limit).
  - **Summary** – structured summary with a highlighted **Arbitration clause**
    card; every amount, date and clause has a "Show source quote" toggle.
  - **Timeline** – dated events with confidence and source badges, undated items
    listed separately, plus how many items were dropped as unverifiable.
  - **Notice** – a draft notice with `[PLACEHOLDERS]` highlighted, Copy and
    Download .txt buttons. Enabled only once the case type is known.
  - **Case file** – the facts, evidence and open questions the assistant holds.
- A banner turns amber ("worth checking with a lawyer") or red ("talk to a lawyer
  now") when the code rules decide the user needs human help.

Light and dark themes follow the operating system preference. No CDN, no build
step, no framework.

## How it avoids invented law

- Legal rules live only in `kb.json`. The model may state a rule only by KB id (`[KB:id]`).
- Code scans every reply for section numbers, Act names and case names that are not in the KB and removes those sentences.
- Every timeline/summary item must quote the source text; code checks the quote really exists and drops items that fail.
- "Talk to a lawyer now" decisions are made by code rules, not by the model.
- The model is allowed, and instructed, to say "I am not sure".

## Quick start with uv (recommended)

[uv](https://docs.astral.sh/uv/) creates the virtual environment, installs the exact
locked versions and runs the app in one step.

```bash
cp .env.example .env    # then add at least one free API key
uv run app.py           # http://127.0.0.1:5000
```

The first `uv run` builds `.venv` and installs everything from `uv.lock`; later runs
start immediately. Other commands:

```bash
uv run pytest -q                     # unit tests (offline, fake LLM)
uv run python scripts/run_eval.py    # all eval cases -> outputs/
```

`pyproject.toml` is the source of truth for dependencies. It needs Python 3.11 or
newer; if your machine has none, uv downloads a suitable interpreter itself.

## Quick start with plain pip

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # add at least one free API key
python app.py                      # http://127.0.0.1:5000
pytest -q                          # unit tests (no API key needed, uses fake LLM)
python scripts/run_eval.py         # runs all test cases, writes raw outputs to outputs/
```

### Offline demo without an API key

Set `LLM_PROVIDER_ORDER=fake` in `.env` to run the whole app against the canned
test fixture in `tests/fixtures/fake_llm.json`. The UI, the safety checks and the
eval harness all work; the answers are fixed text and always describe a deposit
case, so refund cases will fail the eval rules. This mode exists for tests, not
for real use.

With no API key set at all, the chat still loads and answers honestly with
"I'm having trouble right now ..." plus an `llm_failure` note, instead of failing
the page. Add a key to `.env` for real replies.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "I'm having trouble right now" and the log shows `HTTP/1.1 404` | The provider retired the model id in `GROQ_MODEL` / `GEMINI_MODEL`. A 404 from an OpenAI-compatible endpoint means a dead model, not a broken connection. | List what your key can use, then update `.env`: see the snippet below. |
| `HTTP/1.1 401` / `403` | Bad or missing key, or the key has no access to that model. | Check `GROQ_API_KEY`. The key is never logged or returned by the API. |
| Slow replies, `429` in the log | Free-tier per-minute limits. | Expected; the app backs off and retries. `uv run pytest -q` and the eval harness use the offline fake provider and cost nothing. |

See which models a Groq key can actually use:

```bash
uv run python -c "import os,openai; from dotenv import load_dotenv; load_dotenv('.env'); c=openai.OpenAI(api_key=os.environ['GROQ_API_KEY'], base_url=os.environ['GROQ_BASE_URL']); print('\n'.join(sorted(m.id for m in c.models.list().data)))"
```

## Swapping the model

Edit `.env` only. No code change. See `docs/LLM_LAYER.md`.

## Limits (be honest)

- Covers only tenant-deposit and consumer-refund problems.
- No OCR: scanned PDFs / photos are rejected with a clear message.
- No voice input. Languages: English, Hindi, Hinglish (best effort).
- Knowledge base is small and must be verified against official sources by a human.
- In-memory sessions: restarting the server clears everything.
- **Every task is written to `jobs/<date>/<job_id>/`**, including extracted document text. That folder is gitignored and never committed, but it does sit on the local disk: delete it when you are done, or run with `JOBS_ARCHIVE=0` to switch archiving off.
- Do not upload real personal documents to the demo. Free LLM tiers may use inputs for training.

## Job archive

Each user task writes one folder, so you can see exactly what was asked and what came back:

```
jobs/2026-11-08/4e391f42-.../
├── request.json    what the user asked for
├── response.json   exactly what the API returned (no internal fields)
├── meta.json       job id, kind, timing, provider/model/token counts
└── document.txt    extracted document text (uploads only)
```

`kind` is one of `chat`, `upload`, `summary`, `timeline`, `notice`. Failed requests
are not archived. A disk error is logged and the request still succeeds.

Browse what was recorded:

```bash
uv run python -c "import jobs; [print(j['created_at'], j['kind'], j['job_id'], j['llm']) for j in jobs.list_jobs()]"
```

## Planning documents

Start with `PROJECT_CONTEXT.md`. The build order and ready-to-paste prompts are in `docs/BUILD_STEPS.md`.

| File | Purpose |
|---|---|
| `PROJECT_CONTEXT.md` | Always attach to the AI chat. Scope, rules, stack, conventions |
| `docs/ARCHITECTURE.md` | Folder layout, data flow, case-file schema, AI vs code split |
| `docs/API_SPEC.md` | Every endpoint with JSON examples and error codes |
| `docs/LLM_LAYER.md` | `llm.py` spec, env vars, fallback, JSON handling |
| `docs/PROMPTS.md` | System prompts and output schemas |
| `docs/KNOWLEDGE_BASE.md` | `kb.json` format and starter entries (verify before use) |
| `docs/SAFETY_AND_CHECKS.md` | Citation scan, quote verification, escalation, injection defence |
| `docs/DOCUMENT_PROCESSING.md` | Upload, extraction, chunking, merging |
| `docs/FRONTEND_SPEC.md` | Single-page UI |
| `docs/TESTING_AND_EVAL.md` | Test cases, metrics, raw-output format |
| `docs/BUILD_STEPS.md` | Step-by-step prompts for DeepSeek in VS Code |
| `docs/SUBMISSION_CHECKLIST.md` | 2-page doc outline, video outline, final checks |
