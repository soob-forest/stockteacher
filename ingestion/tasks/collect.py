"""Celery tasks for collection workflow."""

from __future__ import annotations

from typing import Callable, Iterable, List
import uuid

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
from ingestion.services.deduplicator import InMemoryKeyStore, RedisKeyStore
from ingestion.settings import get_settings
from ingestion.utils.logging import get_logger


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
    trace_id = str(uuid.uuid4())
    logger = get_logger(__name__)
    logger.info(
        "collect.start",
        extra={"trace_id": trace_id, "ticker": ticker, "source": source},
    )
    with session_scope() as session, JobRunRecorder(
        session, ticker=ticker, source=source, task_name="collect_articles_for_ticker", trace_id=trace_id
    ):
        fetched: List[RawArticleDTO] = connector.fetch(ticker)
        # Dedupe: prefer RedisKeyStore if redis-py is available; fallback to in-memory
        keystore = _build_keystore(logger)
        unique = _dedupe_with_keystore(fetched, keystore)
        saved = _persist_new_articles(session, source, ticker, unique)
        logger.info(
            "collect.saved",
            extra={
                "trace_id": trace_id,
                "ticker": ticker,
                "source": source,
                "fetched": len(fetched),
                "unique": len(unique),
                "saved": saved,
            },
        )
        return saved


def _build_keystore(logger) -> InMemoryKeyStore | RedisKeyStore:
    settings = get_settings()
    try:
        import redis as redislib  # type: ignore

        client = redislib.Redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
        # 연결 확인; 실패 시 폴백
        try:
            client.ping()
        except Exception:
            logger.info("dedupe.keystore.memory", extra={"reason": "redis_ping_failed"})
            return InMemoryKeyStore()
        ks = RedisKeyStore(client, prefix="dedup", default_ttl_seconds=int(settings.dedup_redis_ttl_seconds))
        logger.info("dedupe.keystore.redis", extra={"redis_url": settings.redis_url})
        return ks
    except Exception:  # pragma: no cover - best-effort fallback when redis-py is absent/unavailable
        logger.info("dedupe.keystore.memory", extra={"reason": "redis_lib_unavailable"})
        return InMemoryKeyStore()


@shared_task(name="ingestion.tasks.collect.collect_articles_for_ticker")
def collect_articles_for_ticker(ticker: str, source: str) -> int:  # pragma: no cover - wrapper
    return collect_core(ticker, source)
