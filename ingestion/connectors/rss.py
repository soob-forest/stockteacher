"""RSS connector (fetcher-injected for tests/offline)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import BaseConnector


FetcherFn = Callable[[str, Optional[datetime]], List[Dict[str, Any]]]


class RSSConnector(BaseConnector):
    """Connector that normalizes RSS-like items.

    This offline-friendly version accepts a fetcher function that returns a list
    of raw entry dicts (title, summary, link, published, language optional).
    """

    source = "rss"
    source_type = "news"

    def __init__(self, fetcher: FetcherFn):
        self._fetcher = fetcher

    def _fetch_raw(self, ticker: str, since: Optional[datetime]):
        return self._fetcher(ticker, since)

