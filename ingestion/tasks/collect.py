"""Celery tasks for collection workflow."""

from __future__ import annotations

from typing import Callable, Iterable, List

from celery import shared_task
from sqlalchemy import select

from ingestion.db.models import Base
from ingestion.db.session import get_engine, session_scope
from ingestion.models.domain import RawArticleDTO
from ingestion.repositories.articles import (
    JobRunRecorder,
    get_existing_fingerprints,
    save_articles,
)
from ingestion.services.deduplicator import InMemoryKeyStore


# Connector factory is kept pluggable for tests; it must return an object with .fetch(ticker).
CONNECTOR_FACTORY: Callable[[str], object] | None = None


def _get_connector(source: str):
    if CONNECTOR_FACTORY is None:
        raise RuntimeError("CONNECTOR_FACTORY가 설정되지 않았습니다.")
    return CONNECTOR_FACTORY(source)


def _ensure_schema() -> None:
    # For local runs/tests, ensure schema exists (idempotent)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def _dedupe_with_keystore(items: Iterable[RawArticleDTO], keystore: InMemoryKeyStore) -> List[RawArticleDTO]:
    unique: List[RawArticleDTO] = []
    for it in items:
        if keystore.has(it.fingerprint):
            continue
        keystore.add(it.fingerprint)
        unique.append(it)
    return unique


def _persist_new_articles(session, source: str, ticker: str, items: List[RawArticleDTO]) -> int:
    # DB-level dedupe by fingerprint
    existing = get_existing_fingerprints(session, (i.fingerprint for i in items))
    to_insert = [i for i in items if i.fingerprint not in existing]
    if not to_insert:
        return 0
    saved = save_articles(session, to_insert)
    return saved


def collect_core(ticker: str, source: str) -> int:
    """Core logic to collect and persist articles; test-friendly."""
    _ensure_schema()
    connector = _get_connector(source)
    with session_scope() as session, JobRunRecorder(
        session, ticker=ticker, source=source, task_name="collect_articles_for_ticker"
    ):
        fetched: List[RawArticleDTO] = connector.fetch(ticker)
        # In-memory/Redis-like dedupe first
        keystore = InMemoryKeyStore()
        unique = _dedupe_with_keystore(fetched, keystore)
        return _persist_new_articles(session, source, ticker, unique)


@shared_task(name="ingestion.tasks.collect.collect_articles_for_ticker")
def collect_articles_for_ticker(ticker: str, source: str) -> int:  # pragma: no cover - wrapper
    return collect_core(ticker, source)
