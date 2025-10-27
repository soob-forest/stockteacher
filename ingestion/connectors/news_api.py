"""News API connector (provider-injected for tests/offline)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from ingestion.settings import get_settings

from .base import BaseConnector, PermanentError, TransientError


ProviderFn = Callable[[str, Optional[datetime]], List[Dict[str, Any]]]


class NewsAPIConnector(BaseConnector):
    """Connector for NewsAPI-like sources.

    - provider 주입 시: 오프라인 모드(기존 동작)
    - provider 미주입 시: 실제 HTTP 호출
    """

    source = "news_api"
    source_type = "news"

    def __init__(self, provider: Optional[ProviderFn] = None):
        self._provider = provider

    def _fetch_raw(self, ticker: str, since: Optional[datetime]):
        if self._provider is not None:
            return self._provider(ticker, since)

        cfg = get_settings()
        if not cfg.news_api_key:
            raise PermanentError("NEWS_API_KEY가 설정되지 않았습니다.")

        headers = {"X-Api-Key": cfg.news_api_key.get_secret_value()}
        params = {
            "q": ticker,
            "language": cfg.news_api_lang,
            "pageSize": int(cfg.news_api_page_size),
            "sortBy": cfg.news_api_sort_by,
            "page": 1,
        }

        articles: List[Dict[str, Any]] = []
        max_pages = 2
        for page in range(1, max_pages + 1):
            params["page"] = page
            try:
                resp = httpx.get(
                    cfg.news_api_endpoint,
                    headers=headers,
                    params=params,
                    timeout=float(cfg.news_api_timeout_seconds),
                )
            except httpx.TimeoutException as exc:  # pragma: no cover - rare
                raise TransientError("NewsAPI 타임아웃") from exc
            except httpx.HTTPError as exc:  # pragma: no cover - rare
                raise TransientError("NewsAPI 호출 오류") from exc

            if resp.status_code in (429,) or resp.status_code >= 500:
                raise TransientError(f"NewsAPI 일시 오류: {resp.status_code}")
            if resp.status_code >= 400:
                raise PermanentError(f"NewsAPI 오류: {resp.status_code}")

            data = resp.json()
            items = data.get("articles") or []
            if not items:
                break
            # normalize field names for BaseConnector
            for it in items:
                it.setdefault("body", it.get("description"))
                it.setdefault("publishedAt", it.get("publishedAt"))
                # language is optional; NewsAPI may not include per-article language
            articles.extend(items)
        return articles
