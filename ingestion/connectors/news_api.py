"""News API connector (provider-injected for tests/offline)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import BaseConnector


ProviderFn = Callable[[str, Optional[datetime]], List[Dict[str, Any]]]


class NewsAPIConnector(BaseConnector):
    """Connector that normalizes NewsAPI-like payloads.

    This offline-friendly version accepts a provider function that returns a list
    of raw article dicts shaped similarly to NewsAPI responses.
    """

    source = "news_api"
    source_type = "news"

    def __init__(self, provider: ProviderFn):
        self._provider = provider

    def _fetch_raw(self, ticker: str, since: Optional[datetime]):
        return self._provider(ticker, since)

