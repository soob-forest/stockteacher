from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

from ingestion.connectors.base import TransientError
from ingestion.connectors.news_api import NewsAPIConnector
from ingestion.connectors.rss import RSSConnector


def _news_provider_success(_ticker: str, _since: Optional[datetime]):
    return [
        {
            "title": "Apple hits new high",
            "description": "AAPL rallies on earnings",
            "url": "https://example.com/aapl1",
            "publishedAt": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "language": "en",
        },
        {  # duplicate by url+title
            "title": "Apple hits new high",
            "description": "duplicate",
            "url": "https://example.com/aapl1",
            "publishedAt": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "language": "en",
        },
    ]


def test_newsapi_connector_normalizes_and_dedupes():
    connector = NewsAPIConnector(provider=_news_provider_success)
    items = connector.fetch("AAPL")

    assert len(items) == 1
    item = items[0]
    assert item.ticker == "AAPL"
    assert item.source == "news_api"
    assert item.title.startswith("Apple")
    assert item.url.host == "example.com"
    assert item.published_at.year == 2025
    assert len(item.fingerprint) == 64


def test_rss_connector_normalizes():
    def _rss_fetcher(_ticker: str, _since: Optional[datetime]):
        return [
            {
                "title": "TSLA delivery update",
                "summary": "Q4 deliveries beat",
                "link": "https://example.com/tsla1",
                "published": datetime(2025, 2, 1, tzinfo=timezone.utc),
                "language": "en",
            }
        ]

    connector = RSSConnector(fetcher=_rss_fetcher)
    items = connector.fetch("TSLA")

    assert len(items) == 1
    assert items[0].source == "rss"
    assert items[0].url.scheme == "https"


def test_connector_retries_on_transient_error():
    calls = {"n": 0}

    def _flaky_provider(_ticker: str, _since: Optional[datetime]):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("temp outage")
        return _news_provider_success(_ticker, _since)

    connector = NewsAPIConnector(provider=_flaky_provider)
    items = connector.fetch("AAPL", max_attempts=3)

    assert calls["n"] == 3
    assert len(items) == 1

