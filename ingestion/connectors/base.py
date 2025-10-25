"""Connector abstraction, errors, and helpers."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from ingestion.models.domain import RawArticleDTO


class ConnectorError(Exception):
    """Base connector error."""


class TransientError(ConnectorError):
    """Retryable error (e.g., rate limit, network hiccup)."""


class PermanentError(ConnectorError):
    """Non-retryable error (e.g., 4xx semantics)."""


def _fingerprint(url: str, title: str) -> str:
    data = (url.strip() + "\n" + title.strip()).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class BaseConnector(ABC):
    """Abstract connector interface with retry and normalization hooks."""

    source: str
    source_type: str

    def fetch(self, ticker: str, since: Optional[datetime] = None, *, max_attempts: int = 3) -> List[RawArticleDTO]:
        attempts = 0
        last_error: Optional[Exception] = None
        while attempts < max_attempts:
            attempts += 1
            try:
                raw = self._fetch_raw(ticker, since)
                return self._normalize_and_dedupe(ticker, raw)
            except TransientError as exc:  # retry
                last_error = exc
                if attempts >= max_attempts:
                    raise
            except PermanentError:
                raise
        assert last_error is not None
        raise last_error

    @abstractmethod
    def _fetch_raw(self, ticker: str, since: Optional[datetime]) -> List[Dict[str, Any]]:
        """Return a list of raw item dicts from the upstream."""

    def _normalize_and_dedupe(self, ticker: str, items: Iterable[Dict[str, Any]]) -> List[RawArticleDTO]:
        seen: set[str] = set()
        normalized: List[RawArticleDTO] = []
        now = datetime.now(timezone.utc)
        for item in items:
            dto = self._normalize_item(ticker, item, now)
            if dto.fingerprint in seen:
                continue
            seen.add(dto.fingerprint)
            normalized.append(dto)
        return normalized

    def _normalize_item(self, ticker: str, item: Dict[str, Any], collected_at: datetime) -> RawArticleDTO:
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or item.get("description") or item.get("summary") or "").strip()
        url = str(item.get("url") or item.get("link") or "").strip()
        published_at = item.get("published_at") or item.get("published") or item.get("publishedAt")
        language = item.get("language")
        fp = _fingerprint(url, title)
        return RawArticleDTO(
            ticker=ticker.upper(),
            source=self.source,
            source_type=self.source_type,
            title=title,
            body=body,
            url=url,  # pydantic validates as HttpUrl
            collected_at=collected_at,
            published_at=published_at,
            language=language,
            fingerprint=fp,
        )

