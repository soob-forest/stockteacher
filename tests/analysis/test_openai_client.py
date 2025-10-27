from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from analysis.client.openai_client import (
    LLMError,
    OpenAIClient,
    PermanentLLMError,
    TransientLLMError,
)
from analysis.models.domain import AnalysisInput, InputArticle
from analysis.settings import get_analysis_settings, reset_analysis_settings_cache


def _ai():
    item = InputArticle(
        title="Apple hits new high",
        body="Earnings beat expectations.",
        url="https://example.com/aapl",
        language="en",
    )
    return AnalysisInput(ticker="AAPL", locale="ko_KR", items=[item], max_chars=2000)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    reset_analysis_settings_cache()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("ANALYSIS_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ANALYSIS_MAX_TOKENS", "256")
    monkeypatch.setenv("ANALYSIS_TEMPERATURE", "0.2")
    monkeypatch.setenv("ANALYSIS_REQUEST_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("ANALYSIS_RETRY_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("ANALYSIS_COST_LIMIT_USD", "0.05")
    yield
    reset_analysis_settings_cache()


def _make_provider_ok(_: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "summary_text": "Strong results and positive outlook",
        "keywords": ["apple", "earnings", "growth"],
        "sentiment_score": 0.6,
        "anomalies": [],
    }
    return {
        "choices": [{"message": {"content": json.dumps(data)}}],
        "usage": {"prompt_tokens": 300, "completion_tokens": 150},
        "model": "gpt-4o-mini",
    }


def test_analyze_success():
    client = OpenAIClient.from_env(provider=_make_provider_ok)
    res = client.analyze(_ai())
    assert res.ticker == "AAPL"
    assert res.summary_text.startswith("Strong")
    assert res.llm_tokens_prompt == 300
    assert res.llm_model == "gpt-4o-mini"
    assert 0.0 <= res.llm_cost < 0.05


def test_analyze_retry_then_success():
    calls = {"n": 0}

    def provider(payload: Dict[str, Any]) -> Dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            # 첫 응답은 잘못된 JSON
            return {
                "choices": [{"message": {"content": "not-json"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                "model": "gpt-4o-mini",
            }
        return _make_provider_ok(payload)

    client = OpenAIClient.from_env(provider=provider)
    res = client.analyze(_ai())
    assert res.keywords[0] == "apple"
    assert calls["n"] == 2


def test_analyze_cost_limit_exceeded():
    def provider(_: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "choices": [{"message": {"content": json.dumps({"summary_text": "ok", "keywords": ["a"], "sentiment_score": 0, "anomalies": []})}}],
            "usage": {"prompt_tokens": 200000, "completion_tokens": 200000},
            "model": "gpt-4o-mini",
        }

    client = OpenAIClient.from_env(provider=provider)
    with pytest.raises(PermanentLLMError):
        client.analyze(_ai())


def test_timeout_raises_transient(monkeypatch):
    def slow_provider(_: Dict[str, Any]) -> Dict[str, Any]:
        import time as _t

        _t.sleep(2)
        return _make_provider_ok({})

    # 짧은 타임아웃으로 유도
    monkeypatch.setenv("ANALYSIS_REQUEST_TIMEOUT_SECONDS", "1")
    reset_analysis_settings_cache()
    client = OpenAIClient.from_env(provider=slow_provider)
    with pytest.raises(TransientLLMError):
        client.analyze(_ai())
