# Legal Saathi — documentation

Legal Saathi is a Flask web app that helps a person in India act on one of two
everyday legal problems: a **tenant security deposit** that is not returned, or a
**consumer refund** that never arrives. The person chats in English, Hindi or
Hinglish, can upload the agreement or invoice, and gets a plain-language answer,
a verified timeline and a draft notice.

The single most important design rule: **the model is never allowed to state law
from memory.** Every legal statement must come from `kb.json` and carry a
`[KB:id]` tag, and code removes any sentence that cites something outside that
knowledge base.

> Legal Saathi gives information, not legal advice. It is not a lawyer, and it
> tells the user when they need a real one.

---

## Run it

```bash
uv run app.py          # http://127.0.0.1:5000
```

`uv` creates the virtual environment from `uv.lock` and starts the app. No API key
is needed for the bundled offline provider. To use a real model, edit `.env`:

```ini
LLM_PROVIDER_ORDER=groq          # or gemini, or custom
GROQ_API_KEY=<your key>
GROQ_MODEL=qwen/qwen3.8-27b
```

Full details, including troubleshooting and a clean-machine checklist:
[05-running-and-portability.md](05-running-and-portability.md).

---

## Read in this order

| # | Document | What it answers |
|---|---|---|
| 1 | [01-problem-and-scope.md](01-problem-and-scope.md) | Why these two problems, and what is deliberately out of scope |
| 2 | [02-architecture.md](02-architecture.md) | Module map, request lifecycle, and the AI-vs-code split |
| 3 | [03-safety-model.md](03-safety-model.md) | The eight guarantees and the code that enforces each one |
| 4 | [04-api-reference.md](04-api-reference.md) | Every endpoint, payload, flag and error code |
| 5 | [05-running-and-portability.md](05-running-and-portability.md) | Fresh-machine setup, configuration, troubleshooting |
| 6 | [06-verification.md](06-verification.md) | Test suite, evaluation run, metrics, and honest failures |
| 7 | [07-limitations-and-roadmap.md](07-limitations-and-roadmap.md) | What it cannot do, and what would come next |
| 8 | [08-ai-usage-log.md](08-ai-usage-log.md) | Which AI tools were used, and where they were wrong |
| 9 | [09-submission-readiness.md](09-submission-readiness.md) | Every item of `docs/SUBMISSION_CHECKLIST.md`, with real status |
| — | [solution-doc-2page.md](solution-doc-2page.md) / [PDF](legal-saathi-solution-doc.pdf) | The 2-page solution document for the submission form |
| — | [walkthrough-video-script.md](walkthrough-video-script.md) | Timed 3-minute demo script |

Planning material that predates the build (product rules, prompt specs, the
knowledge-base format) stays in [`../docs/`](../docs/).

---

## What is in the box

```
app.py            Flask routes: validate, call one service, return JSON
config.py         every threshold and env var in one place
llm.py            the only module that talks to a model provider
prompts.py        prompt templates, no legal content
schemas.py        JSON Schemas for every model output
kb.json / kb.py   15 legal rules + loader/validator
checks.py         citation scan, quote verification, dates, escalation, injection
docs.py           PDF/DOCX/TXT extraction and chunking, in memory
store.py          in-memory sessions (no database)
jobs.py           per-task archive under jobs/<date>/<job_id>/
services/         chat, summary, timeline, notice
templates/ static/ single-page UI, vanilla JS, no build step, no CDN
tests/            143 tests, offline
scripts/run_eval.py  plays 12 cases, writes raw output + report.md
outputs/          real, unedited evaluation runs
```

---

## At a glance

| Item | Value |
|---|---|
| Language / runtime | Python 3.11+ (tested on 3.15) |
| Web | Flask, server-rendered page + vanilla JS |
| Model access | any OpenAI-compatible endpoint, swapped by `.env` only |
| Unit tests | 143, all offline |
| Evaluation cases | 12 synthetic scenarios |
| Knowledge-base entries | 15, **all `verified: false`** until a human checks them |
| Storage | sessions in memory; tasks archived to gitignored `jobs/` |

---

## Honest summary of quality

- The **safety machinery works and is tested**: unverified legal references are
  removed, fabricated quotes are dropped, escalation is decided by code.
- The **evaluation numbers in [06-verification.md](06-verification.md) come from
  the offline provider**, because no paid key is assumed. They demonstrate the
  harness, not model quality. Re-run with a real key for meaningful figures.
- **Every knowledge-base entry is unverified**, so the assistant hedges on almost
  every answer. That is intentional and is the correct state until a lawyer or a
  human checks each entry against an official source.
