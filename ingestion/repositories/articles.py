"""Repositories for persisting articles and job runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.db.models import JobRun, JobStage, JobStatus, RawArticle
from ingestion.models.domain import RawArticleDTO


def get_existing_fingerprints(session: Session, fps: Iterable[str]) -> set[str]:
    stmt = select(RawArticle.fingerprint).where(RawArticle.fingerprint.in_(list(fps)))
    return {row[0] for row in session.execute(stmt)}


def save_articles(session: Session, items: Sequence[RawArticleDTO]) -> int:
    count = 0
    for dto in items:
        entity = RawArticle(
            ticker=dto.ticker,
            source=dto.source,
            source_type=dto.source_type,
            title=dto.title,
            body=dto.body,
            url=str(dto.url),
            fingerprint=dto.fingerprint,
            collected_at=dto.collected_at,
            published_at=dto.published_at,
            language=dto.language,
        )
        session.add(entity)
        count += 1
    return count


class JobRunRecorder:
    """Context manager to record job run lifecycle."""

    def __init__(
        self,
        session: Session,
        *,
        stage: JobStage = JobStage.COLLECT,
        ticker: str | None,
        source: str | None,
        task_name: str,
        trace_id: str | None = None,
    ) -> None:
        self._session = session
        self._job = JobRun(
            stage=stage,
            status=JobStatus.RUNNING,
            ticker=ticker,
            source=source,
            task_name=task_name,
            trace_id=trace_id,
            started_at=datetime.now(timezone.utc),
        )

    def __enter__(self) -> JobRun:
        self._session.add(self._job)
        # Commit initial RUNNING state so we have a durable record even if later work fails
        self._session.commit()
        return self._job

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if exc is None:
            self._job.status = JobStatus.SUCCEEDED
        else:
            self._job.status = JobStatus.FAILED
            self._job.error_message = str(exc)[:512]
        self._job.finished_at = datetime.now(timezone.utc)
        self._session.add(self._job)
        # Commit final state before outer transaction may roll back
        try:
            self._session.commit()
        except Exception:  # pragma: no cover - defensive; do not mask original error
            self._session.rollback()
