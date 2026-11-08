# LLM LAYER (`llm.py`)

## Purpose
One module hides every provider. Any OpenAI-compatible endpoint works, so swapping to a stronger model is an `.env` change.

## `.env.example`
```
LLM_PROVIDER_ORDER=groq,gemini
GROQ_API_KEY=
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=qwen/qwen3.8-27b
GEMINI_API_KEY=
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL=gemini-2.5-flash
CUSTOM_API_KEY=
CUSTOM_BASE_URL=
CUSTOM_MODEL=
LONG_DOC_PROVIDER=gemini
LONG_DOC_CHAR_THRESHOLD=12000
LLM_TIMEOUT_SECONDS=45
FLASK_SECRET_KEY=change-me
MAX_UPLOAD_MB=5
```
**Verify** model IDs, base URLs and free-tier limits in each provider's console: they change often. A retired model id is the most common cause of a `404` from a provider, and it looks like "the app is broken" until you read the error code. Check what a key can actually use with `GET <BASE_URL>/models`. Free tiers have per-minute token caps, so keep prompts small and chunk documents.

## Public API

```python
@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int

def complete(messages: list[dict], *, json_mode: bool = False, temperature: float = 0.2,
             max_tokens: int = 1500, prefer: str | None = None) -> LLMResult: ...

def complete_json(messages: list[dict], schema: dict, *, temperature: float = 0.0,
                  max_tokens: int = 1800, prefer: str | None = None) -> tuple[dict, LLMResult]: ...
```

## Behaviour
1. Providers are tried in `LLM_PROVIDER_ORDER`. A provider without an API key is skipped. `prefer` moves one provider to the front (used for long documents via `LONG_DOC_PROVIDER` when text length > `LONG_DOC_CHAR_THRESHOLD`).
2. Use `openai.OpenAI(api_key=..., base_url=..., timeout=LLM_TIMEOUT_SECONDS)` and `client.chat.completions.create(...)`.
3. For `json_mode=True` pass `response_format={"type": "json_object"}`. If the provider rejects it, retry once without it and rely on parsing.
4. On HTTP 429, 5xx or timeout: wait 1s then 2s (2 retries), then move to the next provider. If all fail, raise `LLMRateLimited` (all 429) or `LLMUnavailable`.
   Other 4xx responses are configuration mistakes (bad key, retired model id, wrong base URL) and are **not** retried: the provider is skipped immediately, and the provider's status and error code are logged (never the key).
5. `complete_json`: strip markdown code fences, `json.loads`, validate with `jsonschema`. On failure, append one user message "Your last output was not valid JSON for the required schema. Return only the corrected JSON." and retry once. Second failure raises `LLMBadOutput`.
6. Temperature 0 for extraction (summary, timeline), 0.2 for chat and notice.
7. **Fake provider:** if `LLM_PROVIDER_ORDER=fake`, return canned JSON from `tests/fixtures/fake_llm.json` keyed by a `task` hint in the system prompt. All unit tests use this; no API key needed.
8. Log provider, model, latency and token usage only. Never log messages or outputs.
9. Never put an API key in a log line, an exception message or an API response.

## Swap checklist (for the interview)
Set `LLM_PROVIDER_ORDER=custom` and fill `CUSTOM_*`, restart, run `python scripts/run_eval.py`, compare `outputs/<run>/report.md`.
