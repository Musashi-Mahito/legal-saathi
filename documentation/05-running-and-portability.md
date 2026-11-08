# 5. Running and portability

## What the other machine needs

Only **[uv](https://docs.astral.sh/uv/)**. Python is not required — `uv` downloads
a suitable interpreter (3.11+) on first run if the machine has none.

```bash
# install uv (one line, any OS)
# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Start the app

```bash
cd legal-saathi
uv run app.py
```

Then open <http://127.0.0.1:5000>.

The first run creates `.venv` from `uv.lock` and installs the exact pinned
dependency set; later runs start in about a second. Nothing is written outside the
project folder.

## Verify it works

```bash
uv run pytest -q          # 143 tests, offline, no API key needed
```

Expected: `143 passed`. If this passes, the install is sound.

## Configuration

Every setting lives in `.env` at the project root and is read once at import.
Nothing is hardcoded; no path in the codebase is absolute.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER_ORDER` | `groq,gemini` | Providers tried in order. `fake` = offline fixture |
| `GROQ_API_KEY` / `GROQ_BASE_URL` / `GROQ_MODEL` | empty / Groq URL / `qwen/qwen3.8-27b` | Groq connection |
| `GEMINI_API_KEY` / `GEMINI_BASE_URL` / `GEMINI_MODEL` | empty / Gemini URL / `gemini-2.5-flash` | Gemini connection |
| `CUSTOM_API_KEY` / `CUSTOM_BASE_URL` / `CUSTOM_MODEL` | empty | Any other OpenAI-compatible endpoint |
| `LONG_DOC_PROVIDER` | `gemini` | Preferred provider for documents over the threshold |
| `LONG_DOC_CHAR_THRESHOLD` | `12000` | "Long document" cut-off |
| `LLM_TIMEOUT_SECONDS` | `45` | Per-request timeout |
| `MAX_UPLOAD_MB` | `5` | Upload limit |
| `JOBS_ARCHIVE` | `1` | `0` disables the `jobs/` archive |
| `FLASK_SECRET_KEY` | `change-me` | Flask session secret |
| `FLASK_HOST` / `FLASK_PORT` | `127.0.0.1` / `5000` | Bind address |

### Three ways to run it

```ini
# 1. Offline demo - no key, fixed sample answers (ships this way by default)
LLM_PROVIDER_ORDER=fake
```

```ini
# 2. Real model on a free tier
LLM_PROVIDER_ORDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=qwen/qwen3.8-27b
```

```ini
# 3. Any other OpenAI-compatible endpoint - no code change
LLM_PROVIDER_ORDER=custom
CUSTOM_API_KEY=...
CUSTOM_BASE_URL=https://your-endpoint/v1
CUSTOM_MODEL=your-model
```

Swapping the model is only ever a `.env` edit. That is enforced by design:
`llm.py` is the only module that imports `openai`.

## Making the zip

`uv.lock` is portable — it pins versions, and `uv` resolves the right wheels for
whatever platform opens it. Architecture-specific files are not committed.

**Include:** everything except the four folders below. **Exclude:**

| Exclude | Why |
|---|---|
| `.venv/` | Rebuilt automatically; contains the previous machine's binary paths |
| `__pycache__/`, `.pytest_cache/` | Machine-specific bytecode |
| `jobs/` | Your own chat history and uploaded document text |
| `.env` | **May contain a real API key** — see below |

Ship `.env.example` instead. On the other machine:

```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
```

`.env.example` defaults to `LLM_PROVIDER_ORDER=fake`, so `uv run app.py` works
immediately with no key. Add a key when you want real answers.

> **Never ship `.env`.** If it ever held a real key, treat that key as leaked and
> rotate it in the provider console. `.gitignore` excludes `.env`, but a zip
> bypasses git — this is the one file to check by hand before sending.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Chat says "I'm having trouble right now" and the log shows `HTTP/1.1 404` | The provider retired the model id in `GROQ_MODEL` | List what your key can use (below) and update `.env` |
| `401` / `403` in the log | Bad or missing key | Check `GROQ_API_KEY`; the key is never logged or returned |
| Slow replies, `429` in the log | Free-tier per-minute limits | Expected; the app backs off and retries. Tests and the eval harness use the offline provider and cost nothing |
| `OSError: [WinError 10048]` / port in use | Something else on 5000 | Set `FLASK_PORT=5001` in `.env` |
| Page loads but styling or behaviour is old | Browser cached the previous CSS/JS | Hard refresh (`Ctrl+Shift+R`). Static files are served with `no-cache` |
| A test fails on a different Python | Version drift | `requires-python` is `>=3.11`; run `uv python pin 3.15` if the machine has an unusual build |

See which models a Groq key can actually use:

```bash
uv run python -c "import os,openai; from dotenv import load_dotenv; load_dotenv('.env'); c=openai.OpenAI(api_key=os.environ['GROQ_API_KEY'], base_url=os.environ['GROQ_BASE_URL']); print('\n'.join(sorted(m.id for m in c.models.list().data)))"
```

## Re-running the evaluation

```bash
uv run python scripts/run_eval.py                  # uses .env
uv run python scripts/run_eval.py --provider groq  # explicit provider
uv run python scripts/run_eval.py --url http://127.0.0.1:5000   # against a running server
```

Raw outputs and `report.md` are written to `outputs/run_<timestamp>/`. The harness
never edits model output.
