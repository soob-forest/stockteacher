from __future__ import annotations

import pytest

from llm.settings import (
    AnalysisSettings,
    get_analysis_settings,
    reset_analysis_settings_cache,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    reset_analysis_settings_cache()
    yield
    reset_analysis_settings_cache()


def _set_env(monkeypatch, **overrides):
    defaults = {
        "OPENAI_API_KEY": "sk-test-123",
        "ANALYSIS_MODEL": "gpt-4o-mini",
        "ANALYSIS_MAX_TOKENS": "512",
        "ANALYSIS_TEMPERATURE": "0.2",
        "ANALYSIS_COST_LIMIT_USD": "0.02",
        "ANALYSIS_REQUEST_TIMEOUT_SECONDS": "15",
        "ANALYSIS_RETRY_MAX_ATTEMPTS": "2",
        "DEFAULT_LOCALE": "ko_KR",
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        monkeypatch.setenv(k, str(v))


def test_get_analysis_settings_reads_env(monkeypatch):
    _set_env(monkeypatch, ANALYSIS_TEMPERATURE="0.3")
    cfg = get_analysis_settings()
    assert cfg.openai_api_key.startswith("sk-")
    assert cfg.analysis_model == "gpt-4o-mini"
    assert cfg.analysis_max_tokens == 512
    assert cfg.analysis_temperature == 0.3
    assert cfg.analysis_cost_limit_usd > 0


def test_missing_api_key_raises(monkeypatch):
    # Ensure OPENAI_API_KEY invalid/empty
    monkeypatch.setenv("OPENAI_API_KEY", " ")
    with pytest.raises(RuntimeError):
        get_analysis_settings()
