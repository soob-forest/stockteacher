"""Celery tasks for analysis stage."""

from __future__ import annotations

import uuid
from typing import Callable, List, Optional

from celery import shared_task
from sqlalchemy import select

from analysis.client.openai_client import (
    OpenAIClient,
    PermanentLLMError,
    ProviderFn,
    TransientLLMError,
)
from analysis.models.domain import AnalysisInput, InputArticle
from analysis.repositories.insights import save_insight
from analysis.settings import get_analysis_settings
from ingestion.db.models import Base, RawArticle, JobStage
from ingestion.db.session import get_engine, session_scope
from ingestion.repositories.articles import JobRunRecorder
from ingestion.utils.logging import get_logger


# Provider factory injection point for tests (returns provider fn or None for real OpenAI)
PROVIDER_FACTORY: Callable[[], Optional[ProviderFn]] | None = None


def _ensure_schema() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def _select_recent_articles(session, ticker: str, limit: int = 5) -> List[RawArticle]:
    stmt = (
        select(RawArticle)
        .where(RawArticle.ticker == ticker.upper())
        .order_by(RawArticle.collected_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def analyze_core(ticker: str, *, max_chars: int | None = None) -> int:
    """Analyze recent articles for ticker and persist a single insight.

    Returns the number of insights saved (0 or 1).
    """
    _ensure_schema()
    logger = get_logger(__name__)
    trace_id = str(uuid.uuid4())
    settings = get_analysis_settings()
    with session_scope() as session, JobRunRecorder(
        session,
        stage=JobStage.ANALYZE,
        ticker=ticker,
        source="openai",
        task_name="analyze_articles_for_ticker",
        trace_id=trace_id,
    ):
        rows = _select_recent_articles(session, ticker)
        if not rows:
            logger.info("analyze.no_articles", extra={"trace_id": trace_id, "ticker": ticker})
            return 0
        logger.info(
            "analyze.start",
            extra={"trace_id": trace_id, "ticker": ticker, "articles": len(rows)},
        )
        items = [
            InputArticle(title=r.title, body=r.body, url=r.url, language=r.language, published_at=r.published_at)
            for r in rows
        ]
        inp = AnalysisInput(
            ticker=ticker,
            locale=settings.default_locale,
            items=items,
            max_chars=max_chars or 5000,
        )
        extra = {"trace_id": trace_id, "ticker": ticker}
        provider = PROVIDER_FACTORY() if PROVIDER_FACTORY else None
        client = OpenAIClient.from_env(provider=provider)
        try:
            result = client.analyze(inp)
        except PermanentLLMError as exc:
            logger.warning("analyze.permanent_error", extra={**extra, "error": str(exc)})
            raise
        except TransientLLMError as exc:
            logger.warning("analyze.transient_error", extra={**extra, "error": str(exc)})
            raise
        except Exception:
            logger.exception("analyze.unexpected_error", extra=extra)
            raise
        source_refs = [{"url": r.url, "collected_at": r.collected_at.isoformat()} for r in rows]
        save_insight(session, result, source_refs=source_refs)
        logger.info(
            "analyze.saved",
            extra={
                "trace_id": trace_id,
                "ticker": ticker,
                "model": result.llm_model,
                "tokens_prompt": result.llm_tokens_prompt,
                "tokens_completion": result.llm_tokens_completion,
                "cost": result.llm_cost,
                "articles": len(rows),
            },
        )
        return 1


@shared_task(
    name="analysis.tasks.analyze.analyze_articles_for_ticker",
    queue="analysis.analyze",
    autoretry_for=(TransientLLMError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def analyze_articles_for_ticker(ticker: str) -> int:  # pragma: no cover - thin wrapper
    return analyze_core(ticker)

