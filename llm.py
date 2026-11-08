"""The only module that talks to an LLM provider.

Providers are OpenAI-compatible endpoints configured through ``.env``. Swapping a
model is a configuration change, never a code change.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Callable

import jsonschema

import config

logger = logging.getLogger(__name__)

REPAIR_INSTRUCTION = (
    "Your last output was not valid JSON for the required schema. "
    "Return only the corrected JSON."
)
TASK_MARKER = "TASK:"


class LLMError(Exception):
    """Base class for every LLM layer failure."""


class LLMRateLimited(LLMError):
    """Every provider answered with a rate-limit error."""


class LLMUnavailable(LLMError):
    """No provider could be reached or kept failing.

    ``retryable`` is False for configuration mistakes such as a retired model
    id or a rejected key: retrying those only costs time.
    """

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMBadOutput(LLMError):
    """The model output was not valid JSON for the required schema."""


@dataclass
class LLMResult:
    """One completion plus the metadata we are allowed to log."""

    text: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int = 0


_fake_responder: Callable[[list[dict], bool], str | dict] | None = None


def set_fake_responder(responder: Callable[[list[dict], bool], str | dict] | None) -> None:
    """Install (or clear) a test responder used by the fake provider."""
    global _fake_responder
    _fake_responder = responder


def task_hint(messages: list[dict]) -> str:
    """Read the ``TASK:`` marker that services put at the top of system prompts."""
    for message in messages:
        if message.get("role") != "system":
            continue
        for line in str(message.get("content", "")).splitlines():
            stripped = line.strip()
            if stripped.upper().startswith(TASK_MARKER):
                return stripped[len(TASK_MARKER) :].strip().lower()
    return "default"


def _fake_responses() -> dict:
    """Load the canned fake-provider responses."""
    path = config.FAKE_LLM_PATH
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        logger.warning("fake_llm_fixture_missing")
        return {}


def _fake_complete(messages: list[dict], json_mode: bool) -> LLMResult:
    """Return a canned answer for unit tests without touching the network."""
    started = time.perf_counter()
    if _fake_responder is not None:
        raw = _fake_responder(messages, json_mode)
    else:
        responses = _fake_responses()
        raw = responses.get(task_hint(messages), responses.get("default", {}))
    text = json.dumps(raw, ensure_ascii=False) if isinstance(raw, (dict, list)) else str(raw)
    latency = int((time.perf_counter() - started) * 1000)
    result = LLMResult(text=text, provider="fake", model="fake-1", latency_ms=latency)
    logger.info(
        "llm_call provider=fake model=fake-1 latency_ms=%d task=%s",
        latency,
        task_hint(messages),
    )
    return result


def _ordered_providers(prefer: str | None) -> list[config.ProviderConfig]:
    """Return usable provider configs in the order they should be tried."""
    names = config.provider_order()
    if prefer:
        prefer = prefer.strip().lower()
        if prefer in names:
            names = [prefer] + [name for name in names if name != prefer]
        else:
            names = [prefer] + names
    ordered: list[config.ProviderConfig] = []
    for name in names:
        if name == "fake":
            continue
        candidate = config.provider_config(name)
        if candidate.usable:
            ordered.append(candidate)
    return ordered


def available_providers() -> list[str]:
    """Provider names that are configured and could be called."""
    names = [cfg.name for cfg in _ordered_providers(None)]
    return ["fake"] + names if _uses_fake() else names


def provider_models() -> dict[str, str]:
    """Provider name to model id, for ``GET /api/health``."""
    models = {cfg.name: cfg.model for cfg in _ordered_providers(None)}
    if _uses_fake():
        models["fake"] = "fake-1"
    return models


def _uses_fake() -> bool:
    """True when the fake provider is enabled in the provider order."""
    return "fake" in config.provider_order()


def _error_code(exc: Exception) -> str:
    """Extract the provider's short error code, never its message or the key."""
    body = getattr(exc, "body", None)
    code: object = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("code") or error.get("type")
        else:
            code = body.get("code")
    if code is None:
        code = getattr(exc, "code", None)
    if code is None:
        return "unknown"
    return str(code)[:60]


def _call_provider(
    cfg: config.ProviderConfig,
    messages: list[dict],
    json_mode: bool,
    temperature: float,
    max_tokens: int,
) -> LLMResult:
    """Call one provider once, mapping failures onto our exception types."""
    import openai

    started = time.perf_counter()
    kwargs: dict = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        client = openai.OpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        try:
            response = client.chat.completions.create(**kwargs)
        except openai.BadRequestError:
            if not json_mode:
                raise
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
    except openai.RateLimitError as exc:
        raise LLMRateLimited(f"{cfg.name} rate limited") from exc
    except (openai.APITimeoutError, openai.APIConnectionError) as exc:
        raise LLMUnavailable(f"{cfg.name} unreachable", retryable=True) from exc
    except openai.APIStatusError as exc:
        status = getattr(exc, "status_code", 0) or 0
        if status == 429:
            raise LLMRateLimited(f"{cfg.name} rate limited") from exc
        retryable = status >= 500 or status == 0
        logger.warning(
            "llm_provider_error provider=%s status=%d code=%s retryable=%s",
            cfg.name,
            status,
            _error_code(exc),
            retryable,
        )
        raise LLMUnavailable(f"{cfg.name} returned status {status}", retryable=retryable) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        raise LLMUnavailable(f"{cfg.name} failed", retryable=True) from exc

    latency = int((time.perf_counter() - started) * 1000)
    choice = response.choices[0].message.content if response.choices else ""
    usage = getattr(response, "usage", None)
    return LLMResult(
        text=choice or "",
        provider=cfg.name,
        model=cfg.model,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        latency_ms=latency,
    )


def complete(
    messages: list[dict],
    *,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    prefer: str | None = None,
) -> LLMResult:
    """Complete a chat conversation using the first provider that answers."""
    if _uses_fake():
        return _fake_complete(messages, json_mode)

    providers = _ordered_providers(prefer)
    if not providers:
        raise LLMUnavailable("no provider is configured")

    only_rate_limited = True
    last_reason = "no provider is reachable"
    for cfg in providers:
        for attempt in range(config.LLM_MAX_RETRIES + 1):
            try:
                result = _call_provider(cfg, messages, json_mode, temperature, max_tokens)
            except LLMRateLimited:
                last_reason = f"{cfg.name} rate limited"
                logger.warning("llm_rate_limited provider=%s attempt=%d", cfg.name, attempt)
                _sleep_before_retry(attempt, cfg.name)
                continue
            except LLMUnavailable as exc:
                only_rate_limited = False
                last_reason = str(exc)
                logger.warning(
                    "llm_unavailable provider=%s attempt=%d retryable=%s reason=%s",
                    cfg.name,
                    attempt,
                    getattr(exc, "retryable", True),
                    exc,
                )
                if not getattr(exc, "retryable", True):
                    break
                _sleep_before_retry(attempt, cfg.name)
                continue
            logger.info(
                "llm_call provider=%s model=%s latency_ms=%d prompt_tokens=%s "
                "completion_tokens=%s task=%s",
                result.provider,
                result.model,
                result.latency_ms,
                result.prompt_tokens,
                result.completion_tokens,
                task_hint(messages),
            )
            return result

    if only_rate_limited:
        raise LLMRateLimited("all providers are rate limited")
    raise LLMUnavailable(last_reason)


def _sleep_before_retry(attempt: int, provider: str) -> None:
    """Wait before the next attempt, if retries remain."""
    if attempt >= config.LLM_MAX_RETRIES:
        return
    backoff = config.LLM_RETRY_BACKOFF_SECONDS
    delay = backoff[attempt] if attempt < len(backoff) else backoff[-1]
    logger.info("llm_retry_sleep provider=%s seconds=%.1f", provider, delay)
    time.sleep(delay)


def strip_fences(text: str) -> str:
    """Remove markdown code fences around a JSON payload."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _loads(text: str) -> dict | None:
    """Best-effort JSON parse of model output."""
    cleaned = strip_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = min(
            [idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx >= 0],
            default=-1,
        )
        if start < 0:
            return None
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end <= start:
            return None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _validate(text: str, schema: dict) -> dict | None:
    """Parse and schema-validate model output, returning ``None`` on failure."""
    data = _loads(text)
    if data is None:
        return None
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError:
        return None
    return data


def complete_json(
    messages: list[dict],
    schema: dict,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1800,
    prefer: str | None = None,
) -> tuple[dict, LLMResult]:
    """Complete and parse JSON, repairing one invalid answer before failing."""
    first = complete(
        messages,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
        prefer=prefer,
    )
    parsed = _validate(first.text, schema)
    if parsed is not None:
        return parsed, first

    logger.warning("llm_json_invalid provider=%s task=%s", first.provider, task_hint(messages))
    repair_messages = list(messages)
    repair_messages.append({"role": "assistant", "content": first.text})
    repair_messages.append({"role": "user", "content": REPAIR_INSTRUCTION})
    second = complete(
        repair_messages,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
        prefer=prefer,
    )
    parsed = _validate(second.text, schema)
    if parsed is None:
        logger.warning("llm_json_invalid_after_repair task=%s", task_hint(messages))
        raise LLMBadOutput("model output was not valid JSON for the required schema")
    return parsed, second
