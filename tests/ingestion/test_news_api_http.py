from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

pytest.importorskip("pytest_httpx")

from ingestion.connectors.news_api import NewsAPIConnector
from ingestion.settings import reset_settings_cache


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("NEWS_API_KEY", "test-key")
    monkeypatch.setenv("NEWS_API_ENDPOINT", "https://newsapi.org/v2/everything")
    monkeypatch.setenv("NEWS_API_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("NEWS_API_PAGE_SIZE", "20")
    monkeypatch.setenv("NEWS_API_MAX_RETRIES", "1")
    monkeypatch.setenv("NEWS_API_LANG", "ko")
    monkeypatch.setenv("INGESTION_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("POSTGRES_DSN", "sqlite:///./var/dev.db")
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_newsapi_success_paginates(httpx_mock):
    # callback sequence returns page1 then page2 regardless of querystring
    responses = [
        {
            "status": "ok",
            "articles": [
                {"title": "AAPL up", "description": "Apple rises", "url": "https://ex.com/1", "publishedAt": "2025-01-01T00:00:00Z"},
                {"title": "AAPL down", "description": "Apple falls", "url": "https://ex.com/2", "publishedAt": "2025-01-02T00:00:00Z"},
            ],
        },
        {"status": "ok", "articles": []},
    ]

    base = "https://newsapi.org/v2/everything"
    httpx_mock.add_response(method="GET", url=f"{base}?q=AAPL&language=ko&pageSize=20&sortBy=publishedAt&page=1", json=responses[0], status_code=200)
    httpx_mock.add_response(method="GET", url=f"{base}?q=AAPL&language=ko&pageSize=20&sortBy=publishedAt&page=2", json=responses[1], status_code=200)

    connector = NewsAPIConnector()  # real HTTP path
    items = connector._fetch_raw("AAPL", None)
    assert len(items) == 2
    dtos = connector._normalize_and_dedupe("AAPL", items)
    assert len(dtos) == 2
    assert dtos[0].url.host == "ex.com"


def test_newsapi_rate_limit_raises_transient(httpx_mock):
    base = "https://newsapi.org/v2/everything"
    httpx_mock.add_response(method="GET", url=f"{base}?q=AAPL&language=ko&pageSize=20&sortBy=publishedAt&page=1", json={"status": "error"}, status_code=429)
    connector = NewsAPIConnector()
    with pytest.raises(Exception):
        connector.fetch("AAPL", max_attempts=1)
