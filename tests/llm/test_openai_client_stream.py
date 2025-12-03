from __future__ import annotations

import time
from typing import Any, Dict, Iterator

import pytest

from llm.client.openai_client import OpenAIClient, PermanentLLMError, TransientLLMError
from llm.settings import reset_analysis_settings_cache


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    reset_analysis_settings_cache()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("ANALYSIS_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ANALYSIS_MAX_TOKENS", "128")
    monkeypatch.setenv("ANALYSIS_TEMPERATURE", "0.2")
    monkeypatch.setenv("ANALYSIS_REQUEST_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("ANALYSIS_RETRY_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("ANALYSIS_COST_LIMIT_USD", "0.05")
    yield
    reset_analysis_settings_cache()


def _streaming_provider(_: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    yield {"choices": [{"delta": {"content": "hello"}}]}
    yield {"choices": [{"delta": {"content": " world"}}]}


def test_stream_chat_yields_chunks():
    client = OpenAIClient.from_env(stream_provider=_streaming_provider)
    chunks = list(
        client.stream_chat(
            messages=[{"role": "user", "content": "hi"}],
            retry_max_attempts=0,
        )
    )
    assert chunks == ["hello", " world"]


def test_stream_chat_cost_guard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANALYSIS_COST_LIMIT_USD", "0.00001")
    reset_analysis_settings_cache()

    called = {"n": 0}

    def provider(_: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        called["n"] += 1
        yield {"choices": [{"delta": {"content": "should-not-run"}}]}

    client = OpenAIClient.from_env(stream_provider=provider)
    with pytest.raises(PermanentLLMError):
        list(
            client.stream_chat(
                messages=[{"role": "user", "content": "x" * 1200}],
                retry_max_attempts=0,
            )
        )
    assert called["n"] == 0


def test_stream_chat_timeout(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANALYSIS_REQUEST_TIMEOUT_SECONDS", "1")
    reset_analysis_settings_cache()

    def slow_provider(_: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        time.sleep(1.2)
        yield {"choices": [{"delta": {"content": "late"}}]}

    client = OpenAIClient.from_env(stream_provider=slow_provider)
    with pytest.raises(TransientLLMError):
        list(
            client.stream_chat(
                messages=[{"role": "user", "content": "hello"}],
                retry_max_attempts=0,
            )
        )
