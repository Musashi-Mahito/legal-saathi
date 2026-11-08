"""Tests for the provider-agnostic LLM layer (no network)."""

from __future__ import annotations

import json

import pytest

import config
import llm
import schemas

MESSAGES = [
    {"role": "system", "content": "TASK: chat"},
    {"role": "user", "content": "My landlord is not returning my deposit"},
]

CHAT_PAYLOAD = {
    "reply": "Here is what you can do.",
    "domain": "deposit",
    "language": "en",
    "case_updates": {"facts": {"common": {}, "deposit": {}, "refund": {}}, "evidence": []},
    "missing_info": ["move-out date"],
    "kb_used": ["deposit_forum_civil"],
    "needs_lawyer": False,
    "needs_lawyer_reason": None,
}


def _cfg(name: str) -> config.ProviderConfig:
    return config.ProviderConfig(
        name=name,
        api_key=f"{name}-secret-key",
        base_url="https://example.invalid/v1",
        model=f"{name}-model",
    )


def test_task_hint_reads_system_marker():
    assert llm.task_hint(MESSAGES) == "chat"
    assert llm.task_hint([{"role": "user", "content": "hello"}]) == "default"


def test_fake_provider_returns_fixture():
    result = llm.complete(MESSAGES, json_mode=True)
    payload = json.loads(result.text)
    assert result.provider == "fake"
    assert payload["domain"] == "deposit"


def test_strip_fences_variants():
    assert llm.strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert llm.strip_fences('{"a": 1}') == '{"a": 1}'
    assert llm.strip_fences("```\n[1, 2]\n```") == "[1, 2]"


def test_falls_back_to_second_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,gemini")
    monkeypatch.setattr(config, "provider_config", _cfg)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    calls: list[str] = []

    def fake_call(cfg, messages, json_mode, temperature, max_tokens):
        calls.append(cfg.name)
        if cfg.name == "groq":
            raise llm.LLMUnavailable("down")
        return llm.LLMResult(text='{"ok": true}', provider=cfg.name, model=cfg.model)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    result = llm.complete(MESSAGES)
    assert result.provider == "gemini"
    assert calls == ["groq", "groq", "groq", "gemini"]


def test_prefer_moves_provider_to_front(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,gemini")
    monkeypatch.setattr(config, "provider_config", _cfg)
    seen: list[str] = []

    def fake_call(cfg, messages, json_mode, temperature, max_tokens):
        seen.append(cfg.name)
        return llm.LLMResult(text="ok", provider=cfg.name, model=cfg.model)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    llm.complete(MESSAGES, prefer="gemini")
    assert seen == ["gemini"]


def test_all_rate_limited_raises_rate_limited(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,gemini")
    monkeypatch.setattr(config, "provider_config", _cfg)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)

    def fake_call(cfg, messages, json_mode, temperature, max_tokens):
        raise llm.LLMRateLimited("busy")

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    with pytest.raises(llm.LLMRateLimited):
        llm.complete(MESSAGES)


def test_mixed_failures_raise_unavailable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq")
    monkeypatch.setattr(config, "provider_config", _cfg)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    calls = {"n": 0}

    def fake_call(cfg, messages, json_mode, temperature, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            raise llm.LLMRateLimited("busy")
        raise llm.LLMUnavailable("down")

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    with pytest.raises(llm.LLMUnavailable):
        llm.complete(MESSAGES)


def test_configuration_error_is_not_retried(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,gemini")
    monkeypatch.setattr(config, "provider_config", _cfg)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    calls: list[str] = []

    def fake_call(cfg, messages, json_mode, temperature, max_tokens):
        calls.append(cfg.name)
        raise llm.LLMUnavailable(f"{cfg.name} returned status 404", retryable=False)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.complete(MESSAGES)
    assert calls == ["groq", "gemini"]
    assert "404" in str(excinfo.value)


def test_server_error_is_retried(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq")
    monkeypatch.setattr(config, "provider_config", _cfg)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    calls: list[str] = []

    def fake_call(cfg, messages, json_mode, temperature, max_tokens):
        calls.append(cfg.name)
        raise llm.LLMUnavailable(f"{cfg.name} returned status 503", retryable=True)

    monkeypatch.setattr(llm, "_call_provider", fake_call)
    with pytest.raises(llm.LLMUnavailable):
        llm.complete(MESSAGES)
    assert len(calls) == config.LLM_MAX_RETRIES + 1


def test_error_code_extraction():
    import openai

    exc = openai.NotFoundError(
        "Error code: 404",
        response=_FakeResponse(404),
        body={"error": {"message": "The model does not exist", "code": "model_not_found"}},
    )
    assert llm._error_code(exc) == "model_not_found"
    plain = llm.LLMUnavailable("boom")
    assert llm._error_code(plain) == "unknown"


class _FakeResponse:
    """Minimal stand-in for an httpx response on an SDK error."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.headers: dict = {}
        self.request = None

    def json(self) -> dict:
        return {}


def test_no_configured_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq")
    monkeypatch.setattr(config, "provider_config", lambda name: _cfg(name))
    monkeypatch.setattr(
        config,
        "provider_config",
        lambda name: config.ProviderConfig(name=name, api_key="", base_url="", model=""),
    )
    with pytest.raises(llm.LLMUnavailable):
        llm.complete(MESSAGES)


def test_json_repair_retry_succeeds():
    state = {"calls": 0}

    def responder(messages, json_mode):
        state["calls"] += 1
        if state["calls"] == 1:
            return "This is not JSON at all."
        return CHAT_PAYLOAD

    llm.set_fake_responder(responder)
    data, result = llm.complete_json(MESSAGES, schemas.CHAT_SCHEMA)
    assert data["domain"] == "deposit"
    assert state["calls"] == 2
    assert result.provider == "fake"


def test_json_repair_failure_raises_bad_output():
    llm.set_fake_responder(lambda messages, json_mode: "still not json")
    with pytest.raises(llm.LLMBadOutput):
        llm.complete_json(MESSAGES, schemas.CHAT_SCHEMA)


def test_fenced_json_is_accepted():
    payload = "```json\n" + json.dumps(CHAT_PAYLOAD) + "\n```"
    llm.set_fake_responder(lambda messages, json_mode: payload)
    data, _ = llm.complete_json(MESSAGES, schemas.CHAT_SCHEMA)
    assert data["reply"] == CHAT_PAYLOAD["reply"]


def test_schema_violation_is_treated_as_invalid():
    llm.set_fake_responder(lambda messages, json_mode: {"reply": "hi"})
    with pytest.raises(llm.LLMBadOutput):
        llm.complete_json(MESSAGES, schemas.CHAT_SCHEMA)


def test_api_key_never_appears_in_errors(monkeypatch):
    import openai

    class Boom:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "groq-secret-key"
            raise RuntimeError(f"connection failed for key {kwargs['api_key']}")

    monkeypatch.setattr(openai, "OpenAI", Boom)
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq")
    monkeypatch.setattr(config, "provider_config", _cfg)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.complete(MESSAGES)
    assert "groq-secret-key" not in str(excinfo.value)


def test_available_providers_skips_missing_keys(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,gemini")
    monkeypatch.setattr(
        config,
        "provider_config",
        lambda name: config.ProviderConfig(
            name=name,
            api_key="key" if name == "groq" else "",
            base_url="https://example.invalid/v1",
            model="m",
        ),
    )
    assert llm.available_providers() == ["groq"]
    assert llm.provider_models() == {"groq": "m"}
